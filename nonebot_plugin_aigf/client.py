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

import json
import re

import httpx
from nonebot import logger
from openai import AsyncOpenAI

from .config import plugin_config


def make_http_client() -> httpx.AsyncClient | None:
    if not plugin_config.aigf_proxy_enabled:
        return None
    proxy = plugin_config.aigf_https_proxy or plugin_config.aigf_http_proxy
    if not proxy:
        return None
    return httpx.AsyncClient(proxy=proxy)


class LLMClient:
    def __init__(self, client: AsyncOpenAI):
        self.client = client

    async def generate_response(self, prompt: str, model: str, images: list[str] | None = None) -> str | None:
        if images:
            content = [{"type": "text", "text": prompt}]
            for img_b64 in images:
                content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}})
            messages = [{"role": "user", "content": content}]
        else:
            messages = [{"role": "user", "content": prompt}]

        kwargs = {
            "messages": messages,
            "model": model,
            "temperature": 0.5,
            "timeout": 300,
        }
        if plugin_config.aigf_json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = await self.client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        if content:
            return remove_leading_think(content)
        else:
            return None

    async def generate_response_with_tools(
        self, prompt: str, model: str, tools: list[dict], tool_executor
    ) -> tuple[str | None, bool]:
        """支持 function calling 的响应生成
        
        Args:
            prompt: 用户 prompt
            model: 模型名称
            tools: 工具定义列表
            tool_executor: 工具执行函数，签名: async def executor(name: str, args: dict) -> str
            
        Returns:
            (response_text, used_search): 回复内容和是否使用了搜索工具
        """
        messages = [{"role": "user", "content": prompt}]
        used_search = False
        
        # 第一次调用
        response = await self.client.chat.completions.create(
            messages=messages,
            model=model,
            tools=tools,
            temperature=0.5,
            timeout=300,
        )
        
        message = response.choices[0].message
        
        # 检查是否有 tool_calls
        if message.tool_calls:
            logger.debug(f"[LLM] 检测到 {len(message.tool_calls)} 个 tool_calls")
            
            # 将 assistant 消息加入历史
            messages.append(message)
            
            # 执行每个工具调用
            for tool_call in message.tool_calls:
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments)
                
                logger.info(f"[LLM] 调用工具: {func_name}, 参数: {func_args}")
                
                # 执行工具
                try:
                    result = await tool_executor(func_name, func_args)
                    used_search = True
                except Exception as e:
                    logger.error(f"[LLM] 工具执行失败: {e}")
                    result = f"工具执行失败: {e}"
                
                # 添加工具响应
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })
            
            # 第二次调用获取最终回复
            kwargs = {
                "messages": messages,
                "model": model,
                "temperature": 0.5,
                "timeout": 300,
            }
            if plugin_config.aigf_json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            response = await self.client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
            if content:
                return remove_leading_think(content), used_search
            return None, used_search
        
        # 没有 tool_calls，直接返回
        content = message.content
        if content:
            return remove_leading_think(content), False
        return None, False


def remove_leading_think(text: str) -> str:
    pattern = r"^(?:\s*<think>(.*?)</think>\s*|\s*<think\s*/?>\s*)+"
    return re.sub(pattern, "", text, flags=re.DOTALL).lstrip()
