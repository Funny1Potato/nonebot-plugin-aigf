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

import asyncio
import base64
from dataclasses import dataclass, field
from datetime import datetime
import json
import re
import ssl
import traceback

import anyio
import httpx
from nonebot import logger, on_command, on_message, require
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import (
    Bot, Event, GroupMessageEvent, MessageSegment, Message as OneBotMessage, PrivateMessageEvent,
)
from nonebot.matcher import Matcher
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER
from nonebot.plugin import PluginMetadata
from openai import AsyncOpenAI

require("nonebot_plugin_localstore")

from .client import LLMClient
from .config import Config, plugin_config
from .image_manager import IMAGE_CACHE_DIR, image_manager
from .meme_manager import AtMessage, MemeMessage, TextMessage, meme_manager
from .mem import Message as MMessage
from .presets import PRESETS, load_presets, save_preset, RolePreset
from .session import Session

__plugin_meta__ = PluginMetadata(
    name="NYATuringTest", description="群聊特化LLM聊天机器人，具有记忆和表情包功能",
    usage="群聊特化LLM聊天机器人", type="application",
    config=Config, supported_adapters={"~onebot.v11"},
    extra={"author": "shadow3aaa"},
)


async def is_group_message(event: Event) -> bool:
    return isinstance(event, GroupMessageEvent)

async def is_private_message(event: Event) -> bool:
    return isinstance(event, PrivateMessageEvent)


@dataclass
class GroupState:
    event: Event | None = None
    bot: Bot | None = None
    session: Session = field(default_factory=Session)
    messages_chunk: list[MMessage] = field(default_factory=list)
    last_message_time: float = 0.0
    client: LLMClient = field(default_factory=lambda: LLMClient(
        client=AsyncOpenAI(api_key=plugin_config.nyaturingtest_chat_openai_api_key,
                           base_url=plugin_config.nyaturingtest_chat_openai_base_url)))
    lock = asyncio.Lock()


_tasks: set[asyncio.Task] = set()
group_states: dict[int, GroupState] = {}


async def _resolve_user_id(bot: Bot, event: Event, nickname: str) -> int | None:
    if not isinstance(event, GroupMessageEvent):
        return None
    try:
        members = await bot.get_group_member_list(group_id=event.group_id)
        for m in members:
            if m.get("card", "").strip() == nickname or m.get("nickname", "").strip() == nickname:
                return m["user_id"]
    except Exception as e:
        logger.error(f"获取群成员列表失败: {e}")
    return None


async def spawn_state(state: GroupState):
    while True:
        await asyncio.sleep(1.0)
        async with state.lock:
            if not state.bot or not state.event:
                continue
            if not state.messages_chunk:
                continue
            now = asyncio.get_event_loop().time()
            reached_count = len(state.messages_chunk) >= 5
            reached_time = (now - state.last_message_time) >= 5.0
            if not reached_count and not reached_time:
                continue
            messages_chunk = state.messages_chunk.copy()
            state.messages_chunk.clear()


        try:
            # 从缓存中获取待处理的表情包
            stickers = meme_manager.get_cached_stickers()
            responses = await state.session.process(messages_chunk, state.client, cached_stickers=stickers)
            # 处理完成后清空缓存（不管 LLM 是否收藏，缓存只用一次）
            meme_manager.clear_cache()
        except Exception as e:
            logger.error(f"Error: {e}")
            traceback.print_exc()
            continue

        if not responses:
            continue

        try:
            pending = OneBotMessage()
            for response in responses:
                if isinstance(response, TextMessage):
                    pending.append(MessageSegment.text(response.content))
                elif isinstance(response, AtMessage):
                    uid = await _resolve_user_id(state.bot, state.event, response.user_name)
                    if uid:
                        pending.append(MessageSegment.at(uid))
                elif isinstance(response, MemeMessage):
                    if pending:
                        await state.bot.send(message=pending, event=state.event)
                        pending = OneBotMessage()
                    path = meme_manager.resolve(response.meme_id)
                    if path:
                        await state.bot.send(message=MessageSegment.image(path), event=state.event)
                else:
                    if pending:
                        await state.bot.send(message=pending, event=state.event)
                        pending = OneBotMessage()
                    await state.bot.send(message=str(response), event=state.event)
            if pending:
                await state.bot.send(message=pending, event=state.event)
        except Exception as e:
            logger.error(f"发送消息失败: {e}")


# ---- 命令 ----

help_cmd = on_command(rule=is_group_message, permission=SUPERUSER, cmd="help", aliases={"帮助"}, priority=0, block=True)
help_pm = on_command(rule=is_private_message, permission=SUPERUSER, cmd="help", aliases={"帮助"}, priority=0, block=True)
status_cmd = on_command(rule=is_group_message, permission=SUPERUSER, cmd="status", aliases={"状态"}, priority=0, block=True)
set_role_cmd = on_command(rule=is_group_message, permission=SUPERUSER, cmd="set_role", aliases={"设置角色"}, priority=0, block=True)
reset_cmd = on_command(rule=is_group_message, permission=SUPERUSER, cmd="reset", aliases={"重置"}, priority=0, block=True)
presets_cmd = on_command(rule=is_group_message, permission=SUPERUSER, cmd="presets", aliases={"preset"}, priority=0, block=True)
set_preset_cmd = on_command(rule=is_group_message, permission=SUPERUSER, cmd="set_preset", aliases={"set_presets"}, priority=0, block=True)
reload_meme_cmd = on_command(rule=is_group_message, permission=SUPERUSER, cmd="reload_meme", aliases={"重载表情包"}, priority=0, block=True)
auto_chat = on_message(rule=is_group_message, priority=1, block=False)


def _ensure_group_state(group_id: int) -> GroupState:
    if group_id not in group_states:
        group_states[group_id] = GroupState(
            session=Session(id=str(group_id), name="小助手", role="一个友好的群聊助手"))
        task = asyncio.create_task(spawn_state(group_states[group_id]))
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)
    return group_states[group_id]


@help_cmd.handle()
async def _(event: GroupMessageEvent):
    await help_cmd.finish("命令: help status set_role reset presets set_preset reload_meme")


@status_cmd.handle()
async def _(event: GroupMessageEvent):
    state = _ensure_group_state(event.group_id)
    await status_cmd.finish(state.session.status())


@set_role_cmd.handle()
async def _(event: GroupMessageEvent, args: Message = CommandArg()):
    parts = args.extract_plain_text().strip().split(" ", 1)
    if len(parts) != 2:
        await set_role_cmd.finish("用法: set_role <名字> <设定>")
    state = _ensure_group_state(event.group_id)
    state.session.name, state.session.role = parts[0], parts[1]
    await set_role_cmd.finish(f"角色已设为: {parts[0]}\n设定: {parts[1]}")


@reset_cmd.handle()
async def _(event: GroupMessageEvent):
    state = _ensure_group_state(event.group_id)
    state.session = Session(id=str(event.group_id))
    await state.session.load_preset(plugin_config.nyaturingtest_default_preset)
    await reset_cmd.finish("已重置会话")


@presets_cmd.handle()
async def _():
    msg = "可用预设:\n" + "\n".join(f"- {k}: {v.name} {v.role}" for k, v in PRESETS.items() if not v.hidden)
    msg += "\n用法: set_preset <预设名>"
    await presets_cmd.finish(msg)


@set_preset_cmd.handle()
async def _(event: GroupMessageEvent, args: Message = CommandArg()):
    name = args.extract_plain_text().strip()
    if not name:
        await set_preset_cmd.finish("用法: set_preset <预设名>")
    state = _ensure_group_state(event.group_id)
    if await state.session.load_preset(name):
        await set_preset_cmd.finish(f"预设已加载: {name}")
    else:
        await set_preset_cmd.finish(f"不存在的预设: {name}")


@reload_meme_cmd.handle()
async def _():
    await meme_manager.load_all()
    await reload_meme_cmd.finish(
        f"已重载。管理员: {len(meme_manager.admin_memes)} 个, 自动收集: {len(meme_manager.collected_memes)} 个")


@auto_chat.handle()
async def handle_auto_chat(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    if group_id not in plugin_config.nyaturingtest_enabled_groups:
        return
    # 跳过机器人自己的消息
    if event.get_user_id() == str(bot.self_id):
        return

    state = _ensure_group_state(group_id)
    user_id = event.get_user_id()

    async with state.lock:
        message_content = await message2MMessage(
            bot_name=state.session.name, group_id=group_id,
            message=event.original_message, bot=bot, state=state)

    if not message_content:
        return

    try:
        user_info = await bot.get_group_member_info(group_id=group_id, user_id=int(user_id))
        nickname = user_info.get("card") or user_info.get("nickname") or str(user_id)
    except Exception:
        nickname = str(user_id)

    async with state.lock:
        state.event = event
        state.bot = bot
        state.messages_chunk.append(MMessage(time=datetime.now(), user_name=nickname, user_id=user_id, content=message_content))
        state.last_message_time = asyncio.get_event_loop().time()


async def message2MMessage(bot_name: str, group_id: int, message: Message, bot: Bot, state: GroupState) -> str:
    content = ""
    for seg in message:
        if seg.type == "text":
            content += seg.data.get("text", "")
        elif seg.type in ("image", "emoji"):
            try:
                url = seg.data.get("url", "")
                cache_path = IMAGE_CACHE_DIR / "raw"
                cache_path.mkdir(parents=True, exist_ok=True)
                key = re.search(r"[?&]fileid=([a-zA-Z0-9_-]+)", url)
                key = key.group(1) if key else None
                if key and (cache_path / key).exists():
                    async with await anyio.open_file(cache_path / key, "rb") as f:
                        image_bytes = await f.read()
                else:
                    ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
                    ssl_ctx.set_ciphers("ALL:@SECLEVEL=1")
                    async with httpx.AsyncClient(verify=ssl_ctx) as client:
                        resp = await client.get(url)
                        resp.raise_for_status()
                        image_bytes = resp.content
                    if key:
                        async with await anyio.open_file(cache_path / key, "wb") as f:
                            await f.write(image_bytes)

                is_sticker = seg.data.get("sub_type") == 1
                image_base64 = base64.b64encode(image_bytes).decode()

                if plugin_config.nyaturingtest_image_mode == "llm":
                    await meme_manager.save_to_cache(image_bytes=image_bytes, description="", emotion="")
                else:
                    desc = await image_manager.get_image_description(image_base64=image_base64, is_sticker=is_sticker)
                    logger.info(f"[VLM] 描述: {desc.description if desc else None}, 情感: {desc.emotion if desc else None}")
                    if desc:
                        await meme_manager.save_to_cache(
                            image_bytes=image_bytes, description=desc.description, emotion=desc.emotion,
                        )
                        if is_sticker:
                            content += f"\n[表情包] [情感:{desc.emotion}] [内容:{desc.description}]\n"
                        else:
                            content += f"\n[图片] {desc.description}\n"
            except Exception as e:
                logger.error(f"图片处理错误: {e}")
                content += "\n[图片加载失败]\n"
        elif seg.type == "at":
            uid = seg.data.get("qq")
            if not uid:
                continue
            if str(uid) == str(bot.self_id):
                content += f" @{bot_name} "
            else:
                try:
                    info = await bot.get_group_member_info(group_id=group_id, user_id=int(uid))
                    content += f" @{info.get('card') or info.get('nickname') or uid} "
                except Exception:
                    content += f" @{uid} "
    return content.strip()


# ---- 启动 ----

from nonebot import get_driver

@get_driver().on_startup
async def _():
    logger.info(f"[NYATuringTest] 图片理解模式: {plugin_config.nyaturingtest_image_mode}")
    await load_presets()
    await meme_manager.load_all()
    # 加载默认预设到所有群
    default = plugin_config.nyaturingtest_default_preset
    for gid in plugin_config.nyaturingtest_enabled_groups:
        state = _ensure_group_state(gid)
        await state.session.load_preset(default)
