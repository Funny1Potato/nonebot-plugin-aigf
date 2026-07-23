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
from dataclasses import asdict, dataclass
import hashlib
import io
import json
from pathlib import Path
import anyio
from nonebot import logger
import nonebot_plugin_localstore as store
import numpy as np
from PIL import Image
from .config import plugin_config
from .vlm import VLM

IMAGE_CACHE_DIR = Path(str(store.get_plugin_cache_dir())) / "image_cache"


@dataclass
class ImageWithDescription:
    description: str
    emotion: str
    is_sticker: bool = False

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @staticmethod
    def from_json(json_str: str) -> "ImageWithDescription":
        data = json.loads(json_str)
        if not all(key in data for key in ("description", "emotion", "is_sticker")):
            raise ValueError("缺少必要字段")
        return ImageWithDescription(**data)


class ImageManager:
    _instance = None
    _initialized = False

    def __new__(cls):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._vlm = None
            # 只在 VLM 模式下初始化 VLM
            if plugin_config.nyaturingtest_image_mode == "vlm" and plugin_config.nyaturingtest_vlm_enabled:
                api_key = plugin_config.nyaturingtest_vlm_api_key or plugin_config.nyaturingtest_chat_openai_api_key
                self._vlm = VLM(api_key=api_key, model=plugin_config.nyaturingtest_vlm_model,
                                base_url=plugin_config.nyaturingtest_vlm_base_url)
            IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            self._initialized = True

    async def get_image_description(self, image_base64: str, is_sticker: bool) -> ImageWithDescription | None:
        if not self._vlm:
            logger.warning("[VLM] VLM 未启用，跳过图片分析")
            return None
        image_bytes = base64.b64decode(image_base64)
        image_hash = hashlib.md5(image_bytes).hexdigest()
        cache = IMAGE_CACHE_DIR / f"{image_hash}.json"
        if cache.exists():
            try:
                async with await anyio.open_file(cache, encoding="utf-8") as f:
                    desc = ImageWithDescription.from_json(await f.read())
                if desc.is_sticker != is_sticker:
                    desc.is_sticker = is_sticker
                    async with await anyio.open_file(cache, "w", encoding="utf-8") as f:
                        await f.write(desc.to_json())
                return desc
            except Exception:
                cache.unlink(missing_ok=True)

        image_format = Image.open(io.BytesIO(image_bytes)).format
        if not image_format:
            return None

        if image_format.upper() == "GIF":
            gif_b64 = _transform_gif(image_base64)
            if not gif_b64:
                return None
            description = await self._vlm.request("用中文描述这张动态图的内容和含义，最多100字", gif_b64, "jpeg")
            emotion = await self._vlm.request("分析这个表情包的情感，给出'情感，类型，含义'三元组", gif_b64, "jpeg")
        else:
            description = await self._vlm.request("用中文描述这张图片的内容和含义，最多100字", image_base64, image_format)
            emotion = await self._vlm.request("分析这个表情包的情感，给出'情感，类型，含义'三元组", image_base64, "jpeg")

        if not description or not emotion:
            return None

        result = ImageWithDescription(description=description, emotion=emotion, is_sticker=is_sticker)
        async with await anyio.open_file(cache, "w", encoding="utf-8") as f:
            await f.write(result.to_json())
        return result


def _transform_gif(gif_base64: str, max_frames: int = 15) -> str | None:
    try:
        gif_data = base64.b64decode(gif_base64)
        gif = Image.open(io.BytesIO(gif_data))
        all_frames = []
        try:
            while True:
                gif.seek(len(all_frames))
                all_frames.append(gif.convert("RGB").copy())
        except EOFError:
            pass
        if not all_frames:
            return None
        selected = [all_frames[0]]
        for frame in all_frames[1:]:
            mse = np.mean((np.array(frame) - np.array(selected[-1])) ** 2)
            if mse > 1000:
                selected.append(frame)
            if len(selected) >= max_frames:
                break
        target_h = 200
        w, h = selected[0].size
        target_w = max(1, int((target_h / h) * w)) if h > 0 else 1
        resized = [f.resize((target_w, target_h), Image.Resampling.LANCZOS) for f in selected]
        combined = Image.new("RGB", (target_w * len(resized), target_h))
        for i, f in enumerate(resized):
            combined.paste(f, (i * target_w, 0))
        buf = io.BytesIO()
        combined.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None


image_manager = ImageManager()
