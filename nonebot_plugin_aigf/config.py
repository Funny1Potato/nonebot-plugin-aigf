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

from nonebot import get_driver, get_plugin_config
from pydantic import BaseModel, Field


class Config(BaseModel):
    aigf_chat_openai_api_key: str = Field(..., description="LLM API Key")
    aigf_chat_openai_model: str = Field("gpt-3.5-turbo", description="LLM 模型名称")
    aigf_chat_openai_base_url: str = Field(..., description="LLM API 地址")
    aigf_json_mode: bool = Field(True, description="是否强制 LLM 输出 JSON（需要模型支持 response_format）")
    aigf_image_mode: str = Field("vlm", description="图片理解模式: vlm=使用独立VLM, llm=直接用LLM看图")
    aigf_vlm_enabled: bool = Field(True, description="是否启用图片理解（仅 vlm 模式有效）")
    aigf_vlm_model: str = Field("", description="VLM 模型名称")
    aigf_vlm_base_url: str = Field("", description="VLM API 地址")
    aigf_vlm_api_key: str = Field("", description="VLM API Key（为空时使用 chat_openai_api_key）")
    aigf_enabled_groups: list[int] = Field(default_factory=list, description="启用的群号列表")
    aigf_meme_enabled: bool = Field(True, description="是否启用表情包功能")
    aigf_meme_max_count: int = Field(200, description="自动收集的表情包最大数量")
    aigf_default_preset: str = Field("default", description="默认预设名称")
    aigf_batch_count: int = Field(10, description="攒满多少条消息后触发 LLM 请求")
    aigf_batch_timeout: float = Field(30.0, description="距最后一条消息多少秒后触发 LLM 请求")
    aigf_incomplete_timeout: float = Field(40.0, description="检测到消息可能不完整时的等待时间（秒），如纯@消息或连续发送")
    aigf_recent_messages: int = Field(15, description="prompt 中包含的最近历史消息条数")
    aigf_merge_window: float = Field(5.0, description="消息合并时间窗口（秒），同一用户在此时间内的连续消息会被合并为一条")
    # 社交能量
    aigf_energy_baseline: float = Field(0.7, description="社交能量基线，能量会自然向此值回归（0.0~1.0）")
    # 联网搜索
    aigf_search_enabled: bool = Field(False, description="是否启用联网搜索")
    aigf_search_mode: str = Field("two_stage", description="搜索模式: two_stage=两阶段调用, function_call=使用function calling")
    aigf_search_api: str = Field("tavily", description="搜索API: tavily/bocha/bing")
    aigf_search_api_key: str = Field("", description="搜索 API Key（tavily/bocha/bing 模式必填）")
    aigf_search_max_results: int = Field(3, description="最大搜索结果数")
    aigf_proxy_enabled: bool = Field(False, description="是否启用代理")
    aigf_http_proxy: str = Field("", description="HTTP 代理地址，如 http://127.0.0.1:7890")
    aigf_https_proxy: str = Field("", description="HTTPS 代理地址，如 http://127.0.0.1:7890")


plugin_config: Config = get_plugin_config(Config)
global_config = get_driver().config
