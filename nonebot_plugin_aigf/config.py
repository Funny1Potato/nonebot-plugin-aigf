from nonebot import get_driver, get_plugin_config
from pydantic import BaseModel, Field


class Config(BaseModel):
    aigf_chat_openai_api_key: str = Field(..., description="LLM API Key")
    aigf_chat_openai_model: str = Field("gpt-3.5-turbo", description="LLM 模型名称")
    aigf_chat_openai_base_url: str = Field("https://api.openai.com/v1", description="LLM API 地址")
    aigf_image_mode: str = Field("vlm", description="图片理解模式: vlm=使用独立VLM, llm=直接用LLM看图")
    aigf_vlm_enabled: bool = Field(True, description="是否启用图片理解（仅 vlm 模式有效）")
    aigf_vlm_model: str = Field("Pro/Qwen/Qwen2.5-VL-7B-Instruct", description="VLM 模型名称")
    aigf_vlm_base_url: str = Field("https://api.siliconflow.cn/v1", description="VLM API 地址")
    aigf_vlm_api_key: str = Field("", description="VLM API Key（为空时使用 chat_openai_api_key）")
    aigf_enabled_groups: list[int] = Field(default_factory=list, description="启用的群号列表")
    aigf_meme_enabled: bool = Field(True, description="是否启用表情包功能")
    aigf_meme_max_count: int = Field(200, description="自动收集的表情包最大数量")
    aigf_default_preset: str = Field("default", description="默认预设名称")


plugin_config: Config = get_plugin_config(Config)
global_config = get_driver().config
