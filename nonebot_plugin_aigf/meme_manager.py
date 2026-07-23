import hashlib
import json
import re
import time
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import anyio
from nonebot import logger
import nonebot_plugin_localstore as store
from PIL import Image
from .config import plugin_config


@dataclass
class TextMessage:
    content: str

@dataclass
class MemeMessage:
    meme_id: str

@dataclass
class AtMessage:
    user_name: str

@dataclass
class Meme:
    id: str
    path: str          # 相对文件名，如 "afdba23d055a.gif"
    keywords: list[str]
    description: str


def _meme_dir() -> Path:
    """表情包目录（数据目录）"""
    d = store.get_plugin_data_dir() / "memes"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_dir() -> Path:
    """表情包缓存目录（缓存目录）"""
    d = store.get_plugin_cache_dir() / "sticker_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


class MemeManager:
    def __init__(self):
        self.admin_memes: dict[str, Meme] = {}
        self.collected_memes: dict[str, Meme] = {}
        self._recent: list[str] = []
        self._recent_max = 5
        self._cache_index: dict[str, dict] = {}

    @property
    def memes(self) -> dict[str, Meme]:
        return {**self.collected_memes, **self.admin_memes}

    def _full_path(self, filename: str) -> Path:
        """将相对文件名转为完整路径"""
        return _meme_dir() / filename

    async def load_all(self):
        self.admin_memes = await self._load_file(_meme_dir() / "memes.json")
        self.collected_memes = await self._load_file(_meme_dir() / "collected.json")
        logger.info(f"已加载表情包: 管理员 {len(self.admin_memes)} 个, 自动收集 {len(self.collected_memes)} 个")

    async def _load_file(self, path: Path) -> dict[str, Meme]:
        if not path.exists():
            return {}
        try:
            async with await anyio.open_file(path, encoding="utf-8") as f:
                data = json.loads(await f.read())
            result = {}
            for item in data:
                full_path = _meme_dir() / item["path"]
                if full_path.exists():
                    result[item["id"]] = Meme(
                        id=item["id"], path=item["path"],
                        keywords=item.get("keywords", []),
                        description=item.get("description", ""),
                    )
            return result
        except Exception as e:
            logger.error(f"加载 {path.name} 失败: {e}")
            return {}

    async def _save_index(self, memes: dict[str, Meme], path: Path):
        data = [
            {"id": m.id, "path": m.path, "keywords": m.keywords, "description": m.description}
            for m in memes.values()
        ]
        async with await anyio.open_file(path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(data, ensure_ascii=False, indent=2))

    async def _save_collected(self):
        await self._save_index(self.collected_memes, _meme_dir() / "collected.json")

    def prompt_list(self) -> str:
        lines = []
        for meme in self.memes.values():
            kw = "、".join(meme.keywords)
            lines.append(f"- [{meme.id}] {meme.description}（适用场景：{kw}）")
        return "\n".join(lines)

    def resolve(self, meme_id: str) -> str | None:
        meme = self.memes.get(meme_id)
        if not meme or meme_id in self._recent:
            return None
        self._recent.append(meme_id)
        if len(self._recent) > self._recent_max:
            self._recent.pop(0)
        return str(self._full_path(meme.path))

    async def auto_collect(self, image_bytes: bytes, description: str) -> bool:
        file_hash = hashlib.md5(image_bytes).hexdigest()[:12]
        for meme in self.memes.values():
            if file_hash in meme.path:
                return False
        filename = await self._save_image(image_bytes, file_hash)
        meme_id = self._generate_id(description)
        keywords = self._extract_keywords(description)
        self.collected_memes[meme_id] = Meme(
            id=meme_id, path=filename, keywords=keywords, description=description[:50],
        )
        await self._save_collected()
        logger.info(f"自动收藏表情包: {meme_id} - {description[:30]}")
        await self.cleanup()
        return True

    async def _save_image(self, image_bytes: bytes, file_hash: str) -> str:
        """保存图片到 memes 目录，返回相对文件名"""
        try:
            img_format = Image.open(BytesIO(image_bytes)).format
        except Exception:
            img_format = None
        ext = "gif" if img_format == "GIF" else "jpg" if img_format in ("JPEG", "JPG") else "png"
        filename = f"{file_hash}.{ext}"
        full_path = _meme_dir() / filename
        if not full_path.exists():
            async with await anyio.open_file(full_path, "wb") as f:
                await f.write(image_bytes)
        return filename

    def _generate_id(self, description: str) -> str:
        cleaned = re.sub(r"[，。！？、\s]+", "_", description[:20])
        cleaned = re.sub(r"[^\w\u4e00-\u9fff]", "", cleaned) or "meme"
        return f"{cleaned}_{hashlib.md5(description.encode()).hexdigest()[:4]}"

    def _extract_keywords(self, description: str) -> list[str]:
        parts = re.split(r"[，、,/\s]+", description.strip())
        keywords = [p.strip() for p in parts if p.strip() and len(p.strip()) <= 4]
        return keywords[:3] or ["表情包"]

    # ---- 缓存管理 ----

    async def save_to_cache(self, image_bytes: bytes, description: str, emotion: str) -> str:
        """保存表情包到缓存，返回 cache_id"""
        cache_id = hashlib.md5(image_bytes).hexdigest()[:12]
        try:
            img_format = Image.open(BytesIO(image_bytes)).format
        except Exception:
            img_format = None
        ext = "gif" if img_format == "GIF" else "jpg" if img_format in ("JPEG", "JPG") else "png"
        cache_path = _cache_dir() / f"{cache_id}.{ext}"
        if not cache_path.exists():
            async with await anyio.open_file(cache_path, "wb") as f:
                await f.write(image_bytes)
        self._cache_index[cache_id] = {
            "path": str(cache_path),
            "description": description,
            "emotion": emotion,
        }
        logger.info(f"[缓存] 表情包已缓存: {cache_id} - {description[:20]}")
        return cache_id

    def get_cached_stickers(self) -> list[dict]:
        """获取当前缓存中的所有表情包信息"""
        return [
            {"id": cid, "description": info["description"], "emotion": info["emotion"]}
            for cid, info in self._cache_index.items()
        ]

    async def save_from_cache(self, cache_id: str, description: str, keywords: list[str]) -> bool:
        """从缓存中保存表情包到正式目录，使用 LLM 提供的描述和关键词"""
        cache_info = self._cache_index.get(cache_id)
        if not cache_info:
            logger.warning(f"[缓存] 未找到 cache_id={cache_id}")
            return False
        cache_path = Path(cache_info["path"])
        if not cache_path.exists():
            logger.warning(f"[缓存] 缓存文件不存在: {cache_path}")
            return False
        async with await anyio.open_file(cache_path, "rb") as f:
            image_bytes = await f.read()
        file_hash = hashlib.md5(image_bytes).hexdigest()[:12]
        for meme in self.memes.values():
            if file_hash in meme.path:
                return False
        ext = cache_path.suffix
        filename = f"{file_hash}{ext}"
        dest = _meme_dir() / filename
        async with await anyio.open_file(dest, "wb") as f:
            await f.write(image_bytes)
        # cache_id 本身就是 hash，直接用作 meme id
        self.collected_memes[cache_id] = Meme(
            id=cache_id, path=filename, keywords=keywords, description=description,
        )
        await self._save_collected()
        logger.info(f"[缓存] 表情包已保存: {cache_id} - {description[:30]}")
        return True

    def clear_cache(self):
        """清空内存中的缓存索引（不删磁盘文件，供下次重建）"""
        self._cache_index.clear()

    async def cleanup_cache(self, max_age_hours: int = 168):
        """清理过期的缓存文件（默认 7 天）"""
        now = time.time()
        cleaned = 0
        cache = _cache_dir()
        for f in cache.iterdir():
            if f.is_file():
                age_hours = (now - f.stat().st_mtime) / 3600
                if age_hours > max_age_hours:
                    f.unlink()
                    cleaned += 1
        to_remove = [cid for cid, info in self._cache_index.items()
                     if not Path(info["path"]).exists()]
        for cid in to_remove:
            del self._cache_index[cid]
        if cleaned:
            logger.info(f"[缓存] 清理了 {cleaned} 个过期缓存文件")

    async def cleanup(self, max_count: int = 0):
        """自动收集的表情包超过上限时清理。优先级：最近未使用的先删"""
        if max_count <= 0:
            max_count = plugin_config.aigf_meme_max_count
        if len(self.collected_memes) <= max_count:
            return
        to_remove = []
        keep = []
        for meme in self.collected_memes.values():
            if meme.id not in self._recent:
                to_remove.append(meme)
            else:
                keep.append(meme)
        if len(self.collected_memes) - len(to_remove) > max_count:
            extra = keep[:len(self.collected_memes) - len(to_remove) - max_count]
            to_remove.extend(extra)
        for meme in to_remove:
            meme_path = _meme_dir() / meme.path
            if meme_path.exists():
                meme_path.unlink()
            self.collected_memes.pop(meme.id, None)
        await self._save_collected()
        logger.info(f"清理了 {len(to_remove)} 个表情包")


meme_manager = MemeManager()
