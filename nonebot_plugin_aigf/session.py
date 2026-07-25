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


class Session:
    def __init__(self, id: str = "global", name: str = "小助手", role: str = "一个友好的群聊助手"):
        self.id = id
        self.name = name
        self.role = role
        self.memory = MemoryManager(group_id=id)
        self.recent_messages: list[Message] = []

    async def load_preset(self, preset_name: str) -> bool:
        if preset_name not in PRESETS:
            return False
        preset = PRESETS[preset_name]
        self.name = preset.name
        self.role = preset.role
        return True

    def status(self) -> str:
        recent = "\n".join(f"{m.user_name}: {m.content}" for m in self.recent_messages[-15:]) or "没有消息"
        return f"名字：{self.name}\n设定：{self.role}\n\n最近消息：\n{recent}"

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
        prompt = self._build_prompt(short_term, long_term, friends, messages_chunk, cached_stickers or [])

        logger.debug(f"[process] 调用 LLM, sticker_images: {len(sticker_images)} 张")
        # 调用 LLM
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
                if ops_summary:
                    logger.info(f"[记忆] 操作: {'、'.join(ops_summary)}")
            await self.memory.apply_ops(memory_ops)
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
                      cached_stickers: list[dict] | None = None) -> str:
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

        # 最近 15 条消息
        recent = self.recent_messages[-15:]
        recent_str = "\n".join(f"{m.user_name}: {m.content}" for m in recent) or "无"

        # 新消息
        new_msgs_str = "\n".join(f"{m.user_name}: '{m.content}'" for m in messages_chunk)

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
- 如果是表情包、贴图、梗图（适合在群聊中反复使用），且你的表情包库内没有类似的图片，且你觉得值得保存的，可以收藏。
如果只是群友分享的照片、截图、普通图片，或者表情包库内已有类似图片，则不要收藏。
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
- 如果是表情包、贴图、梗图（适合在群聊中反复使用），且你的表情包库内没有类似的图片，且你觉得值得保存的，可以收藏。
如果只是群友分享的照片、截图、普通图片，或者表情包库内已有类似图片，则不要收藏。
如果值得收藏，在 memory.save_meme 中填入 id 和你写的简短描述。
可用 id：""" + ", ".join(s['id'] for s in cached_stickers) + """
""" + "\n".join(sticker_lines)

        # 群友列表（用于 @）
        user_list_str = ", ".join(f"{data.get('name', uid)}(QQ:{uid})" for uid, data in friends.items()) if friends else "无"

        prompt = "你是 " + self.name + "，" + self.role + "\n\n"
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
    "save_meme": [{ "id": "表情包cache_id", "description": "你写的简短描述", "keywords": ["关键词"] }]
  }
}
```

示例说明：
- "modify" 中的 "index" 是要修改的条目在列表中的位置（从 0 开始）
- "delete" 中的数字是要删除的条目的 index
- 修改和删除前，请先确认列表中对应 index 的内容是否正确
- 如果不需要修改或删除，可以省略对应字段

注意：
- memory 中的所有字段都是可选的，不需要的操作可以省略
- at 的 name 必须是上面列出的群友昵称
- 只有以下情况才回复：
  1. 有人 @ 了你
  2. 有人回复了你之前的消息
  3. 消息明显是对所有人说的，且你有有价值的内容要补充
  4. 你非常确定有人在和你说话
- 如果不确定消息是否在和你说话，不要回复（宁可不回也不要误回）
- 当群友的话题与你无关、你不感兴趣、或没有值得补充的内容时，不需要回复
- 如果不想回复，reply 设为空数组 []
- 不要编造表情包 id，只能使用上面列出的
- 绝对不要在 reply 的正文中提及任何 id（包括表情包 id 和缓存 id），id 只能用在 type:meme 和 memory.save_meme 的结构化字段中
- 发送表情包时只能用 {{ "type": "meme", "id": "xxx" }} 格式，绝对不要在 reply 的文字中描述表情包内容（如"[表情包] xxx"、"发个xxx的表情包"），文字回复只写你想说的话
- 你就是 """ + self.name + """，不要暴露自己是 AI、语言模型或任何模型的真实身份，不要提及任何模型名称（如 GPT、Claude、Qwen 等）
- friends 的 key 必须是 QQ 号（数字），绝对不要用昵称做 key
- aliases 和 info 是独立的字段，add 只影响 info，add_alias/remove_alias 只影响 aliases
"""
        return prompt
