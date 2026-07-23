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
    nyaturingtest_chat_openai_api_key: str = Field(..., description="LLM API Key")
    nyaturingtest_chat_openai_model: str = Field("gpt-3.5-turbo", description="LLM 模型名称")
    nyaturingtest_chat_openai_base_url: str = Field("https://api.openai.com/v1", description="LLM API 地址")
    nyaturingtest_image_mode: str = Field("vlm", description="图片理解模式: vlm=使用独立VLM, llm=直接用LLM看图")
    nyaturingtest_vlm_enabled: bool = Field(True, description="是否启用图片理解（仅 vlm 模式有效）")
    nyaturingtest_vlm_model: str = Field("Pro/Qwen/Qwen2.5-VL-7B-Instruct", description="VLM 模型名称")
    nyaturingtest_vlm_base_url: str = Field("https://api.siliconflow.cn/v1", description="VLM API 地址")
    nyaturingtest_vlm_api_key: str = Field("", description="VLM API Key（为空时使用 chat_openai_api_key）")
    nyaturingtest_enabled_groups: list[int] = Field(default_factory=list, description="启用的群号列表")
    nyaturingtest_meme_enabled: bool = Field(True, description="是否启用表情包功能")
    nyaturingtest_meme_max_count: int = Field(200, description="自动收集的表情包最大数量")
    nyaturingtest_default_preset: str = Field("default", description="默认预设名称")


plugin_config: Config = get_plugin_config(Config)
global_config = get_driver().config
