# Copyright (C) 2025 shadow3aaa <shadow3aaaa@gmail.com>
# Modified by Funny1Potato, 2026
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

import base64
import json
import random
import re
from datetime import datetime

import anyio
from nonebot import logger

from .client import LLMClient
from .config import plugin_config
from .meme_manager import AtMessage, MemeMessage, TextMessage, meme_manager
from .memory import MemoryManager
from .mem import Message
from .presets import PRESETS
from .search import get_search_client


# 搜索工具定义（用于 Function Calling 模式）
SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_internet",
        "description": "搜索互联网获取最新信息，用于理解不懂的梗、网络用语或新词",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索查询词，应该是简洁的关键词"
                }
            },
            "required": ["query"]
        }
    }
}


class Session:
    def __init__(self, id: str = "global", name: str = "小助手", role: str = "一个友好的群聊助手"):
        self.id = id
        self.name = name
        self.role = role
        self.memory = MemoryManager(group_id=id)
        self.recent_messages: list[Message] = []
        self.social_energy: float = 0.7

    async def load_preset(self, preset_name: str) -> bool:
        if preset_name not in PRESETS:
            return False
        preset = PRESETS[preset_name]
        self.name = preset.name
        self.role = preset.role
        return True

    def status(self) -> str:
        recent = "\n".join(f"{m.user_name}: {m.content}" for m in self.recent_messages[-15:]) or "没有消息"
        return f"名字：{self.name}\n设定：{self.role}\n\n社交能量：{self.social_energy:.2f}\n\n最近消息：\n{recent}"

    @staticmethod
    def _merge_consecutive(messages: list[Message], window: float) -> list[Message]:
        """合并同一用户在时间窗口内的连续消息为一条"""
        if not messages:
            return []
        merged: list[Message] = []
        for msg in messages:
            if (merged and msg.user_id and
                    msg.user_id == merged[-1].user_id and
                    (msg.time - merged[-1].time).total_seconds() <= window):
                merged[-1] = Message(
                    time=merged[-1].time,
                    user_name=merged[-1].user_name,
                    content=merged[-1].content + " " + msg.content,
                    user_id=merged[-1].user_id,
                )
            else:
                merged.append(msg)
        return merged

    def _get_energy_description(self) -> str:
        if self.social_energy >= 0.8:
            return "精力充沛，看到什么都想插嘴"
        elif self.social_energy >= 0.6:
            return "状态不错，有兴趣的话题会主动参与"
        elif self.social_energy >= 0.4:
            return "一般般，有人找就回，不太主动"
        elif self.social_energy >= 0.2:
            return "有点懒，倾向于潜水"
        else:
            return "完全不想说话"

    def _build_analysis_prompt(self, messages_chunk: list[Message], culture: list[dict]) -> str:
        """构建分析 prompt，用于判断是否需要搜索"""
        # 合并消息
        merged_chunk = self._merge_consecutive(messages_chunk, plugin_config.aigf_merge_window)
        new_msgs_str = "\n".join(f"{m.user_name}: '{m.content}'" for m in merged_chunk)
        
        # 已有的文化词汇
        known_terms = [t.get("term", "") for t in culture]
        known_terms_str = ", ".join(known_terms) if known_terms else "无"
        
        return f"""请分析以下群聊消息，判断是否有你不理解的梗、网络用语或新词需要搜索。

## 已知文化词汇
{known_terms_str}

## 新消息
{new_msgs_str}

## 分析要求
- 检查消息中是否有你不理解的梗、网络用语、流行语
- 如果已知文化词汇中已包含该词，则不需要搜索
- 只有当你真的不理解某个词的含义时才需要搜索
- 普通的中文词汇不需要搜索

请输出 JSON：
```json
{{
  "need_search": true/false,
  "search_query": "要搜索的关键词（如果不需要搜索可以省略）",
  "reason": "判断理由（可选）"
}}
```
"""

    async def process(self, messages_chunk: list[Message], llm: LLMClient,
                      cached_stickers: list[dict] | None = None) -> list[TextMessage | MemeMessage | AtMessage] | None:
        logger.debug(f"[process] 开始处理 {len(messages_chunk)} 条消息")
        # 更新最近消息
        self.recent_messages.extend(messages_chunk)
        if len(self.recent_messages) > 50:
            self.recent_messages = self.recent_messages[-50:]

        # 加载记忆
        short_term = await self.memory.load_short_term()
        long_term = await self.memory.load_long_term()
        active_users = MemoryManager.get_active_users(messages_chunk)
        friends = await self.memory.load_friends_batch(active_users)
        culture = await self.memory.load_culture()

        # LLM 模式：读取缓存图片的 base64
        sticker_images: list[str] = []
        if plugin_config.aigf_image_mode == "llm" and cached_stickers:
            for s in cached_stickers:
                cache_info = meme_manager._cache_index.get(s["id"])
                if cache_info:
                    try:
                        async with await anyio.open_file(cache_info["path"], "rb") as f:
                            sticker_images.append(base64.b64encode(await f.read()).decode())
                    except Exception as e:
                        logger.error(f"读取缓存图片失败: {e}")

        # 构建 prompt
        # 更新社交能量
        self.social_energy += (0.6 - self.social_energy) * 0.15
        self.social_energy += random.uniform(-0.08, 0.08)
        self.social_energy = max(0.0, min(1.0, self.social_energy))
        logger.debug(f"[process] 社交能量: {self.social_energy:.2f}")

        # 匹配当前聊天中的文化词汇
        all_text = " ".join(m.content for m in messages_chunk)
        matched_culture = self.memory.match_culture_terms(culture, all_text)

        search_results = None

        # 搜索模式处理
        if plugin_config.aigf_search_enabled:
            search_client = get_search_client()
            
            if plugin_config.aigf_search_mode == "two_stage" and search_client:
                # 两阶段模式：先分析是否需要搜索
                analysis_prompt = self._build_analysis_prompt(messages_chunk, culture)
                logger.debug("[process] 两阶段模式 - 第一阶段：分析是否需要搜索")
                
                analysis_response = await llm.generate_response(analysis_prompt, plugin_config.aigf_chat_openai_model)
                if analysis_response:
                    try:
                        analysis_response = re.sub(r"^```json\s*|\s*```$", "", analysis_response.strip())
                        analysis = json.loads(analysis_response)
                        
                        if analysis.get("need_search") and analysis.get("search_query"):
                            logger.info(f"[搜索] 需要搜索: {analysis['search_query']}")
                            search_results = await search_client.search(
                                analysis["search_query"],
                                plugin_config.aigf_search_max_results
                            )
                    except Exception as e:
                        logger.error(f"[搜索] 分析结果解析失败: {e}")
            
            elif plugin_config.aigf_search_mode == "function_call" and search_client:
                # Function Calling 模式：在下方处理
                pass

        # 构建主 prompt
        prompt = self._build_prompt(short_term, long_term, friends, messages_chunk, 
                                     cached_stickers or [], search_results, matched_culture)

        logger.debug(f"[process] 调用 LLM, sticker_images: {len(sticker_images)} 张")
        
        # 调用 LLM
        if plugin_config.aigf_search_enabled and plugin_config.aigf_search_mode == "function_call" and get_search_client():
            # Function Calling 模式
            logger.debug("[process] Function Calling 模式")
            
            async def tool_executor(name: str, args: dict) -> str:
                if name == "search_internet":
                    client = get_search_client()
                    if client:
                        results = await client.search(args.get("query", ""), plugin_config.aigf_search_max_results)
                        return client.format_results(results)
                    return "搜索客户端不可用"
                return f"未知工具: {name}"
            
            response_str, used_search = await llm.generate_response_with_tools(
                prompt, plugin_config.aigf_chat_openai_model,
                tools=[SEARCH_TOOL],
                tool_executor=tool_executor,
            )
            if used_search:
                logger.info("[搜索] Function Calling 模式使用了搜索工具")
        else:
            # 普通模式或两阶段模式（已完成搜索）
            response_str = await llm.generate_response(
                prompt, plugin_config.aigf_chat_openai_model,
                images=sticker_images if sticker_images else None,
            )
        logger.debug(f"[process] LLM 返回: {response_str[:200] if response_str else None}")
        if not response_str:
            return None

        # 解析 JSON
        response_str = re.sub(r"^```json\s*|\s*```$", "", response_str.strip())
        try:
            result = json.loads(response_str)
        except json.JSONDecodeError:
            logger.error(f"LLM 返回非法 JSON: {response_str[:200]}")
            return None

        # 执行记忆操作
        try:
            memory_ops = result.get("memory", {})
            if memory_ops:
                ops_summary = []
                if memory_ops.get("short_term"): ops_summary.append("短期记忆")
                if memory_ops.get("long_term"): ops_summary.append("长期记忆")
                if memory_ops.get("friends"): ops_summary.append("群友信息")
                if memory_ops.get("save_meme"): ops_summary.append("表情包收藏")
                if memory_ops.get("culture"): ops_summary.append("文化记忆")
                if ops_summary:
                    logger.info(f"[记忆] 操作: {'、'.join(ops_summary)}")
            await self.memory.apply_ops(memory_ops)
            
            # 处理文化记忆操作
            culture_ops = memory_ops.get("culture", {})
            if culture_ops:
                await self.memory.apply_culture_ops(culture_ops)
        except Exception as e:
            logger.error(f"执行记忆操作失败: {e}")

        # 处理表情包保存
        save_meme = result.get("memory", {}).get("save_meme")
        if save_meme:
            logger.info(f"[表情包收藏] LLM 决定收藏: {save_meme}")

        if save_meme and plugin_config.aigf_meme_enabled:
            save_list = save_meme if isinstance(save_meme, list) else [save_meme]
            current_cache = meme_manager.get_cached_stickers()
            current_ids = {s["id"] for s in current_cache}
            for item in save_list:
                cache_id = item.get("id", "")
                description = item.get("description", "")
                keywords = item.get("keywords", ["表情包"])
                if not isinstance(keywords, list):
                    keywords = ["表情包"]
                if cache_id and description and cache_id in current_ids:
                    try:
                        collected = await meme_manager.save_from_cache(cache_id, description, keywords)
                        logger.success(f"[表情包收藏] 决策保存: id={cache_id}, 描述: {description[:30]}")
                    except Exception as e:
                        logger.error(f"表情包保存失败: {e}")

        # 解析回复
        reply_raw = result.get("reply", [])
        logger.debug(f"[process] LLM 返回 reply: {reply_raw}")
        if not reply_raw:
            return None

        reply_messages = []
        for item in reply_raw:
            if isinstance(item, str):
                reply_messages.append(TextMessage(content=item))
            elif isinstance(item, dict):
                msg_type = item.get("type", "text")
                if msg_type == "meme":
                    mid = item.get("id", "")
                    if mid:
                        reply_messages.append(MemeMessage(meme_id=mid))
                elif msg_type == "at":
                    name = item.get("name", "")
                    if name:
                        reply_messages.append(AtMessage(user_name=name))
                elif msg_type == "text":
                    content = item.get("content", "")
                    if content:
                        reply_messages.append(TextMessage(content=content))

        # 把 bot 的回复存入最近消息
        if reply_messages:
            # 消耗社交能量
            text_length = sum(len(m.content) for m in reply_messages if isinstance(m, TextMessage))
            energy_cost = 0.03 + min(0.12, text_length * 0.002)
            self.social_energy = max(0.0, self.social_energy - energy_cost)
            logger.debug(f"[process] 回复消耗能量: {energy_cost:.3f}, 剩余: {self.social_energy:.2f}")

            for msg in reply_messages:
                if isinstance(msg, TextMessage):
                    self.recent_messages.append(
                        Message(time=datetime.now(), user_name=self.name, content=msg.content))
                elif isinstance(msg, MemeMessage):
                    meme = meme_manager.memes.get(msg.meme_id)
                    desc = meme.description if meme else msg.meme_id
                    self.recent_messages.append(
                        Message(time=datetime.now(), user_name=self.name, content=f"[表情包] {desc}"))
                elif isinstance(msg, AtMessage):
                    self.recent_messages.append(
                        Message(time=datetime.now(), user_name=self.name, content=f"@{msg.user_name}"))

        return reply_messages or None

    def _build_prompt(self, short_term: list[str], long_term: list[str],
                      friends: dict[str, dict], messages_chunk: list[Message],
                      cached_stickers: list[dict] | None = None,
                      search_results: list[dict] | None = None,
                      matched_culture: list[dict] | None = None) -> str:
        # 预设知识
        preset_knowledge = ""
        preset = PRESETS.get(plugin_config.aigf_default_preset)
        if preset and preset.knowledges:
            preset_knowledge = "\n".join(f"- {k}" for k in preset.knowledges)

        # 短期记忆（JSON 数组格式，index 即数组下标）
        short_term_str = json.dumps(short_term, ensure_ascii=False, indent=2) if short_term else "[]"

        # 长期记忆（JSON 数组格式，index 即数组下标）
        long_term_str = json.dumps(long_term, ensure_ascii=False, indent=2) if long_term else "[]"

        # 群友信息（JSON 对象格式）
        friends_dict = {}
        # 已有记忆的群友
        for uid, data in friends.items():
            friends_dict[uid] = {
                "nickname": data.get("nickname", ""),
                "aliases": data.get("aliases", []),
                "past_nicknames": data.get("past_nicknames", []),
                "info": data.get("info", []),
            }
        # 当前聊天中但还没有记忆的群友
        active_users = MemoryManager.get_active_users(messages_chunk)
        existing_ids = set(friends.keys())
        for u in active_users:
            if u["id"] not in existing_ids:
                friends_dict[u["id"]] = {
                    "nickname": u["name"],
                    "aliases": [],
                    "past_nicknames": [],
                    "info": [],
                }
        friends_str = json.dumps(friends_dict, ensure_ascii=False, indent=2) if friends_dict else "{}"

        # 最近 15 条消息（合并同一用户短时间内的连续消息）
        recent = self.recent_messages[-plugin_config.aigf_recent_messages:]
        recent = self._merge_consecutive(recent, plugin_config.aigf_merge_window)
        recent_str = "\n".join(f"{m.user_name}: {m.content}" for m in recent) or "无"

        # 新消息（合并同一用户短时间内的连续消息）
        merged_chunk = self._merge_consecutive(messages_chunk, plugin_config.aigf_merge_window)
        new_msgs_str = "\n".join(f"{m.user_name}: '{m.content}'" for m in merged_chunk)

        # 表情包列表
        meme_section = ""
        if plugin_config.aigf_meme_enabled:
            meme_list = meme_manager.prompt_list()
            if meme_list:
                meme_section = f"""

## 可用的表情包（用于发送）
{meme_list}
"""

        # 缓存中的表情包（可供收藏）
        sticker_section = ""

        if cached_stickers and plugin_config.aigf_meme_enabled:
            if plugin_config.aigf_image_mode == "llm":
                # LLM 模式：图片已附在 prompt 中，LLM 直接看图
                sticker_ids = [s['id'] for s in cached_stickers]
                sticker_section = """

## 当前消息中出现的图片（可收藏）
以上图片是本次对话中出现的。请结合上下文判断：
- 如果是表情包（能表达一定的情感，适合在群聊中反复使用），且你的表情包库内没有类似的图片，且你觉得值得保存的，可以收藏。
- 如果只是群友分享的照片、截图、梗图、普通图片，或者表情包库内已有类似图片，则不要收藏。
- 若群友连续发了多张图片，通常是在分享普通图片
- 若群友只发了一张图片，而前后均没有与这张图片相关的内容，或是在图片前后仅有对该图片的介绍或评论，通常是在分享普通图片
- 若群友发的图片内容与之前的内容有关联，或这张图片是在其它群友发言之后发出的，且包含较为明显的情感（开心、愤怒、疑惑等），则可能是表情包
如果值得收藏，在 memory.save_meme 中填入下方对应的 id、你写的简短描述和关键词。
可用的 id（仅供 save_meme 使用，不要在 reply 中提及）：""" + ", ".join(sticker_ids)
            else:
                # VLM 模式：显示 VLM 的文字描述
                sticker_lines = []
                for s in cached_stickers:
                    sticker_lines.append(f"- id: {s['id']}，描述: {s['description']}")
                sticker_section = """

## ⭐ 有新的图片可以收藏！
以下是本次对话中出现的图片。请结合上下文判断：
- 如果是表情包（能表达一定的情感，适合在群聊中反复使用），且你的表情包库内没有类似的图片，且你觉得值得保存的，可以收藏。
- 如果只是群友分享的照片、截图、梗图、普通图片，或者表情包库内已有类似图片，则不要收藏。
- 若群友连续发了多张图片，通常是在分享普通图片
- 若群友只发了一张图片，而前后均没有与这张图片相关的内容，或是在图片前后仅有对该图片的介绍或评论，通常是在分享普通图片
- 若群友发的图片内容与之前的内容有关联，或这张图片是在其它群友发言之后发出的，且包含较为明显的情感（开心、愤怒、疑惑等），则可能是表情包
如果值得收藏，在 memory.save_meme 中填入 id 和你写的简短描述。
可用 id：""" + ", ".join(s['id'] for s in cached_stickers) + """
""" + "\n".join(sticker_lines)

        # 群友列表（用于 @）
        user_list_str = ", ".join(f"{data.get('name', uid)}(QQ:{uid})" for uid, data in friends.items()) if friends else "无"

        prompt = "你是 " + self.name + "，" + self.role + "\n\n"
        prompt += """## 回复风格
你是一个真实的群聊参与者，不是AI助手。
- 回复要像发微信一样自然、口语化
- 一句话能说完不要分两句，尽量简短
- 可以使用网络用语（"神了"、"逆天"、"确实"、"666"等）
- 回复长度要有变化：有时一两个字，有时几句话
- 不要表现得过于热情或乐于助人
- 有时候可以敷衍（"善"、"确实"、"哈哈哈"）
- 不要对每条消息都认真回复

## 当前状态
社交能量：""" + self._get_energy_description() + """
（这会影响你是否想说话、回复的热情程度）

"""
        # 文化知识段落
        if matched_culture:
            culture_str = "\n".join(
                f"- {t.get('term', '')}: {t.get('meaning', '')} ({t.get('context', '')})"
                for t in matched_culture
            )
            prompt += f"""## 相关文化知识
以下是当前聊天中涉及的文化词汇，你已经了解它们的含义：
{culture_str}

"""
        
        # 搜索结果段落
        if search_results:
            from .search import get_search_client
            client = get_search_client()
            if client:
                search_str = client.format_results(search_results)
                prompt += f"""## 搜索结果
以下是你搜索到的信息，可以帮助你理解群友提到的梗或新词：
{search_str}

"""
        
        if preset_knowledge:
            prompt += "## 你的知识\n" + preset_knowledge + "\n\n"
        prompt += """## 你的记忆

### 短期记忆
```json
""" + short_term_str + """
```
这是你对近期对话的记忆。管理原则：优先修改，能改就不加；积极删除，不让列表无限增长。
- modify：对话有新进展时，直接更新已有条目（优先使用）
- delete：已结束的话题、已解决的问题、不再相关的内容（积极使用）
- add：仅当列表中没有相关内容时才添加
index 对应上面数组的下标（从 0 开始）。

### 长期记忆
```json
""" + long_term_str + """
```
这是你记住的重要信息。管理原则：优先修改，能改就不加；发现旧信息不准确时直接修改，而不是新增一条纠正。
- modify：信息有变化时，直接修改原条目（优先使用）
- delete：被证伪、过时、不再适用的信息（积极使用）
- add：仅当完全没有相关内容时才添加
不要记：临时性的对话内容、无关紧要的闲聊。

### 相关群友信息
```json
""" + friends_str + """
```
这是你对群友的了解。每个群友是一个对象，包含以下字段：
- info：一般信息数组，用 add/modify/delete 操作
- aliases：称呼数组，用 add_alias/remove_alias 操作
- nickname：QQ 全局昵称（系统自动更新，无需手动管理）
- past_nicknames：曾用昵称（系统自动记录，无需手动管理）

你应该积极管理：
- add：群友透露的新信息（追加到 info 数组）
- modify：发现记错了，用 index 指定 info 数组中要改的元素
- delete：不再准确的信息，用 index 指定 info 数组中要删的元素
- add_alias：听到别人叫 ta 某个称呼时添加
- remove_alias：称呼不再使用时移除

## 理解群聊对话
- 消息按时间顺序排列，时间接近的消息通常在互相回复
- [回复 xxx 的消息: "yyy"] 表示这条消息是在回复 xxx 的 yyy
- @某人 表示这条消息是发给那个人的
- 如果消息没有 @ 也没有回复标记，可能是在对所有人说
- 如果不确定某条消息是发给你的，不要回复
- 同一个人连续发的多条消息可能是一个完整表达，判断是否在和你说话时，要把这几条消息合在一起看，不要只看最后一条
- 若你发现收到的群友消息不完整，可能是ta没有发完，可以不用回复

## 最近的聊天记录
""" + recent_str + """

## 新消息
""" + new_msgs_str + meme_section + sticker_section + """

## 已知群友昵称
""" + user_list_str + """

---

你可以在回复的同时管理你的记忆。请输出 JSON：

```json
{
  "reply": [
    { "type": "text", "content": "回复内容" },
    { "type": "at", "name": "群友昵称" },
    { "type": "meme", "id": "表情包id" }
  ],
  "memory": {
    "short_term": {
      "add": ["小明说他周末要去爬山"],
      "modify": [{ "index": 0, "content": "小明说周末要去爬山，小红也想去" }],
      "delete": [2]
    },
    "long_term": {
      "add": ["群里组织过一次聚餐"],
      "modify": [{ "index": 0, "content": "群规更新：不允许发广告和链接" }],
      "delete": [1]
    },
    "friends": {
      "123456": {
        "add": ["职业：程序员", "爱好：打游戏"],
        "modify": [{ "index": 0, "content": "职业：前端工程师" }],
        "delete": [1],
        "add_alias": ["小明哥"],
        "remove_alias": ["老王"]
      }
    },
    "save_meme": [{ "id": "表情包cache_id", "description": "你写的简短描述", "keywords": ["关键词"] }],
    "culture": {
      "add": [{ "term": "yyds", "meaning": "永远的神", "context": "表示赞美、崇拜" }],
      "modify": [{ "index": 0, "term": "yyds", "meaning": "永远滴神" }],
      "delete": [1]
    }
  }
}
```

示例说明：
- "modify" 中的 "index" 是要修改的条目在列表中的位置（从 0 开始）
- "delete" 中的数字是要删除的条目的 index
- 修改和删除前，请先确认列表中对应 index 的内容是否正确
- 如果不需要修改或删除，可以省略对应字段

### 文化记忆
当你遇到新的梗、网络用语、流行语时，可以将其添加到文化记忆中：
- add：添加新学到的文化词汇，包含 term（词汇）、meaning（含义）、context（使用场景）
- modify：更新已有词汇的含义或用法
- delete：删除不再使用或错误的词汇
- 当你通过搜索理解了某个梗的含义后，应该将其添加到文化记忆中
- 当群友解释了某个梗的含义后，也应该添加到文化记忆中

注意：
- memory 中的所有字段都是可选的，不需要的操作可以省略
- at 的 name 必须是上面列出的群友昵称

## 回复决策
结合你当前的社交能量来决定是否回复：
- 有人 @ 你 → 通常回复（但能量很低时也可能敷衍一下）
- 有人回复了你之前的消息 → 回复
- 消息是对所有人说的 → 看你是否感兴趣、是否有话想说
- 话题很有趣 → 即使没 @ 你也可以插嘴
- 话题与你无关、不感兴趣 → 不回复
- 不确定是否在和你说话 → 不回复
- 社交能量低时 → 可以选择不回复，或简单敷衍
- 如果不想回复，reply 设为空数组 []
- 不要对群友发的图片做任何回复，除非群友指明让你评论

## 其他规则
- 不要编造表情包 id，只能使用上面列出的
- 绝对不要在 reply 的正文中提及任何 id（包括表情包 id 和缓存 id），id 只能用在 type:meme 和 memory.save_meme 的结构化字段中
- 发送表情包时只能用 {{ "type": "meme", "id": "xxx" }} 格式，绝对不要在 reply 的文字中描述表情包内容（如"[表情包] xxx"、"发个xxx的表情包"），文字回复只写你想说的话
- 你就是 """ + self.name + """，不要暴露自己是 AI、语言模型或任何模型的真实身份，不要提及任何模型名称（如 GPT、Claude、Qwen 等）
- friends 的 key 必须是 QQ 号（数字），绝对不要用昵称做 key
- aliases 和 info 是独立的字段，add 只影响 info，add_alias/remove_alias 只影响 aliases
"""
        return prompt
