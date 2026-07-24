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
        recent = "\n".join(f"{m.user_name}: {m.content}" for m in self.recent_messages[-10:]) or "没有消息"
        return f"名字：{self.name}\n设定：{self.role}\n\n最近消息：\n{recent}"

    async def process(self, messages_chunk: list[Message], llm: LLMClient,
                      cached_stickers: list[dict] | None = None) -> list[TextMessage | MemeMessage | AtMessage] | None:
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

        # 调用 LLM
        response_str = await llm.generate_response(
            prompt, plugin_config.aigf_chat_openai_model,
            images=sticker_images if sticker_images else None,
        )
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
            await self.memory.apply_ops(result.get("memory", {}))
        except Exception as e:
            logger.error(f"执行记忆操作失败: {e}")

        # 处理表情包保存
        save_meme = result.get("memory", {}).get("save_meme")

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
                        logger.info(f"[表情包收集] 收藏结果: id={cache_id}, 成功={collected}")
                    except Exception as e:
                        logger.error(f"表情包保存失败: {e}")

        # 解析回复
        reply_raw = result.get("reply", [])
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
        return reply_messages or None

    def _build_prompt(self, short_term: list[str], long_term: list[str],
                      friends: dict[str, dict], messages_chunk: list[Message],
                      cached_stickers: list[dict] | None = None) -> str:
        # 预设知识
        preset_knowledge = ""
        preset = PRESETS.get(plugin_config.aigf_default_preset)
        if preset and preset.knowledges:
            preset_knowledge = "\n".join(f"- {k}" for k in preset.knowledges)

        # 短期记忆
        short_term_str = "\n".join(f"- {item}" for item in short_term) if short_term else "无"

        # 长期记忆
        long_term_str = "\n".join(f"- {f}" for f in long_term) if long_term else "无"

        # 群友信息（按 QQ 号存储，显示时带昵称）
        friends_str = ""
        # 已有记忆的群友
        for uid, data in friends.items():
            display_name = data.get("name", uid)
            info_list = data.get("info", [])
            info_str = "、".join(info_list) if info_list else "暂无信息"
            friends_str += f"- {display_name}（QQ:{uid}）：{info_str}\n"
        # 当前聊天中但还没有记忆的群友
        active_users = MemoryManager.get_active_users(messages_chunk)
        existing_ids = set(friends.keys())
        new_users = [u for u in active_users if u["id"] not in existing_ids]
        for u in new_users:
            friends_str += f"- {u['name']}（QQ:{u['id']}）：暂无信息\n"
        friends_str = friends_str or "无"

        # 最近 10 条消息
        recent = self.recent_messages[-10:]
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

## 当前消息中出现的表情包（可收藏）
以上图片是本次对话中别人发的表情包。请看图判断是否值得收藏（适合在群聊中反复使用）。
如果值得收藏，请在 memory 中加入 "save_meme" 字段，格式为列表，每项包含 id、你写的简短描述和关键词。
可用的 id：""" + ", ".join(sticker_ids)
            else:
                # VLM 模式：显示 VLM 的文字描述
                sticker_lines = []
                for s in cached_stickers:
                    sticker_lines.append(f"- id: {s['id']}，VLM 描述: {s['description']}，情感: {s['emotion']}")
                sticker_section = """

## 当前消息中出现的表情包（可收藏）
以下是本次对话中别人发的表情包，如果你觉得值得收藏（适合在群聊中反复使用），
请在 memory 中加入 "save_meme" 字段，填入 id、你写的简短描述和关键词：
""" + "\n".join(sticker_lines)

        # 群友列表（用于 @）
        user_list_str = ", ".join(f"{data.get('name', uid)}(QQ:{uid})" for uid, data in friends.items()) if friends else "无"

        prompt = f"""
你是 {self.name}，{self.role}

{f"## 你的知识{chr(10)}{preset_knowledge}" if preset_knowledge else ""}

## 你的记忆

### 短期记忆
{short_term_str}
这是你对近期对话的记忆。你应该积极管理：
- 添加：新的对话内容、临时上下文、有趣的梗
- 修改：对话有新进展时，更新已有条目（用 index 指定要改哪条）
- 删除：已结束的话题、已解决的问题、不再 relevant 的内容（用 index 指定要删哪条）

### 长期记忆
{long_term_str}
这是你记住的重要信息。你应该积极管理：
- 添加：新的事件、知识、规则
- 修改：发现旧信息不准确或需要更新时（用 index 指定要改哪条）
- 删除：被证伪、过时、不再适用的信息（用 index 指定要删哪条）
不要记：临时性的对话内容、无关紧要的闲聊。

### 相关群友信息
{friends_str}
这是你对群友的了解。你应该积极管理：
- 添加：群友透露的新信息（职业、爱好、性格等）
- 修改：发现之前记错了，或信息有变化时（用 index 指定要改哪条）
- 删除：不再准确的信息（用 index 指定要删哪条）
- update_name：群友改名时更新昵称
注意：index 从 0 开始计数，对应上面列表中的第几条。修改和删除时必须指定正确的 index。

## 最近的聊天记录
{recent_str}

## 新消息
{new_msgs_str}
{meme_section}
{sticker_section}

## 已知群友昵称
{user_list_str}

---

你可以在回复的同时管理你的记忆。请输出 JSON：

```json
{{
  "reply": [
    {{"type": "text", "content": "回复内容"}},
    {{"type": "at", "name": "群友昵称"}},
    {{"type": "meme", "id": "表情包id"}}
  ],
  "memory": {{
    "short_term": {{
      "add": ["小明说他周末要去爬山"],
      "modify": [{{"index": 0, "content": "小明说周末要去爬山，小红也想去"}}],
      "delete": [2]
    }},
    "long_term": {{
      "add": ["群里组织过一次聚餐"],
      "modify": [{{"index": 0, "content": "群规更新：不允许发广告和链接"}}],
      "delete": [1]
    }},
    "friends": {{
      "123456": {{
        "add": ["职业：程序员", "爱好：打游戏"],
        "modify": [{{"index": 0, "content": "职业：前端工程师"}}],
        "delete": [1],
        "update_name": "新昵称"
      }}
    }}
  }}
}}
```

示例说明：
- "modify" 中的 "index" 是要修改的条目在列表中的位置（从 0 开始）
- "delete" 中的数字是要删除的条目的 index
- 修改和删除前，请先确认列表中对应 index 的内容是否正确
- 如果不需要修改或删除，可以省略对应字段

注意：
- reply 中的元素也可以是纯字符串，等同于 {{"type": "text", "content": "..."}}
- memory 中的所有字段都是可选的，不需要的操作可以省略
- at 的 name 必须是上面列出的群友昵称
- 当群友的话题与你无关、你不感兴趣、或没有值得补充的内容时，不需要回复
- 如果不想回复，reply 设为空数组 []
- 不要编造表情包 id，只能使用上面列出的
- friends 的 key 必须是 QQ 号（数字），绝对不要用昵称做 key
"""
        return prompt
