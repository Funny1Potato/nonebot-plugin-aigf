# Copyright (C) 2026 Funny1Potato
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
import anyio
from nonebot import logger
import nonebot_plugin_localstore as store


class MemoryManager:
    def __init__(self, group_id: str = "default"):
        self.group_id = group_id
        # 短期/长期记忆按群隔离
        self.data_dir = store.get_plugin_data_dir() / "memory" / group_id
        self.data_dir.mkdir(parents=True, exist_ok=True)
        # 群友信息全局共享
        self.friends_dir = store.get_plugin_data_dir() / "memory" / "friends"
        self.friends_dir.mkdir(parents=True, exist_ok=True)

    async def load_short_term(self) -> list[str]:
        path = self.data_dir / "short_term.json"
        if not path.exists():
            return []
        try:
            async with await anyio.open_file(path, encoding="utf-8") as f:
                return json.loads(await f.read()).get("items", [])
        except Exception as e:
            logger.error(f"加载短期记忆失败: {e}")
            return []

    async def save_short_term(self, items: list[str]):
        path = self.data_dir / "short_term.json"
        async with await anyio.open_file(path, "w", encoding="utf-8") as f:
            await f.write(json.dumps({"items": items}, ensure_ascii=False, indent=2))

    async def load_long_term(self) -> list[str]:
        path = self.data_dir / "long_term.json"
        if not path.exists():
            return []
        try:
            async with await anyio.open_file(path, encoding="utf-8") as f:
                return json.loads(await f.read()).get("facts", [])
        except Exception as e:
            logger.error(f"加载长期记忆失败: {e}")
            return []

    async def save_long_term(self, facts: list[str]):
        path = self.data_dir / "long_term.json"
        async with await anyio.open_file(path, "w", encoding="utf-8") as f:
            await f.write(json.dumps({"facts": facts}, ensure_ascii=False, indent=2))

    async def load_friend(self, user_id: str) -> dict | None:
        path = self.friends_dir / f"{user_id}.json"
        if not path.exists():
            return None
        try:
            async with await anyio.open_file(path, encoding="utf-8") as f:
                return json.loads(await f.read())
        except Exception as e:
            logger.error(f"加载群友 {user_id} 信息失败: {e}")
            return None

    async def save_friend(self, user_id: str, data: dict):
        path = self.friends_dir / f"{user_id}.json"
        async with await anyio.open_file(path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(data, ensure_ascii=False, indent=2))

    async def load_friends_batch(self, users: list[dict[str, str]]) -> dict[str, dict]:
        """批量加载当前群的群友信息"""
        result = {}
        for user in users:
            data = await self.load_friend(user["id"])
            if data and self.group_id in data.get("groups", []):
                result[user["id"]] = data
        return result

    async def apply_ops(self, memory_ops: dict):
        if not memory_ops:
            return
        logger.debug(f"[记忆] 开始执行记忆操作")

        st_ops = memory_ops.get("short_term", {})
        if st_ops:
            logger.debug(f"[记忆] 短期记忆操作: add={len(st_ops.get('add', []))}, modify={len(st_ops.get('modify', []))}, delete={len(st_ops.get('delete', []))}")
            items = await self.load_short_term()
            for idx in sorted([int(i) for i in st_ops.get("delete", [])], reverse=True):
                if 0 <= idx < len(items):
                    items.pop(idx)
            for mod in st_ops.get("modify", []):
                idx, content = int(mod.get("index", -1)), mod.get("content", "")
                if 0 <= idx < len(items) and content:
                    items[idx] = content
            for item in st_ops.get("add", []):
                if item and item not in items:
                    items.append(item)
            await self.save_short_term(items)

        lt_ops = memory_ops.get("long_term", {})
        if lt_ops:
            logger.debug(f"[记忆] 长期记忆操作: add={len(lt_ops.get('add', []))}, modify={len(lt_ops.get('modify', []))}, delete={len(lt_ops.get('delete', []))}")
            facts = await self.load_long_term()
            for idx in sorted([int(i) for i in lt_ops.get("delete", [])], reverse=True):
                if 0 <= idx < len(facts):
                    facts.pop(idx)
            for mod in lt_ops.get("modify", []):
                idx, content = int(mod.get("index", -1)), mod.get("content", "")
                if 0 <= idx < len(facts) and content:
                    facts[idx] = content
            for item in lt_ops.get("add", []):
                if item and item not in facts:
                    facts.append(item)
            await self.save_long_term(facts)

        # 构建昵称→QQ号反查表（从当前已加载的群友数据中）
        nickname_to_id: dict[str, str] = {}
        for f in self.friends_dir.iterdir():
            if f.suffix == ".json":
                try:
                    async with await anyio.open_file(f, encoding="utf-8") as fh:
                        data = json.loads(await fh.read())
                    if data.get("name") and data.get("id"):
                        nickname_to_id[data["name"]] = data["id"]
                except Exception:
                    pass

        friends_ops = memory_ops.get("friends", {})
        if friends_ops:
            logger.debug(f"[记忆] 群友信息操作: {len(friends_ops)} 个群友")
        for key, ops in friends_ops.items():
            # 如果 key 不是纯数字（QQ号），尝试从反查表中找到对应的 QQ 号
            user_id = key if key.isdigit() else nickname_to_id.get(key, key)
            friend = await self.load_friend(user_id) or {
                "id": user_id,
                "nickname": key if not key.isdigit() else "",
                "aliases": [],
                "past_nicknames": [],
                "info": [],
                "groups": [],
            }
            # 确保当前群在 groups 列表中
            if self.group_id not in friend.get("groups", []):
                friend.setdefault("groups", []).append(self.group_id)
            # 处理 info 的增删改
            info = friend.get("info", [])
            for idx in sorted([int(i) for i in ops.get("delete", [])], reverse=True):
                if 0 <= idx < len(info):
                    info.pop(idx)
            for mod in ops.get("modify", []):
                idx, content = int(mod.get("index", -1)), mod.get("content", "")
                if 0 <= idx < len(info) and content:
                    info[idx] = content
            for item in ops.get("add", []):
                if item and item not in info:
                    info.append(item)
            friend["info"] = info
            # 处理 aliases 的增删
            aliases = friend.get("aliases", [])
            for item in ops.get("add_alias", []):
                if item and item not in aliases:
                    aliases.append(item)
            for item in ops.get("remove_alias", []):
                if item in aliases:
                    aliases.remove(item)
            friend["aliases"] = aliases
            # 更新昵称
            if ops.get("update_name"):
                friend["nickname"] = ops["update_name"]
            await self.save_friend(user_id, friend)
            logger.debug(f"[记忆] 群友信息已保存: {user_id}")

    async def update_nickname(self, user_id: str, qq_nickname: str):
        """自动更新群友的 QQ 全局昵称"""
        if not user_id or not qq_nickname:
            return
        friend = await self.load_friend(user_id)
        if friend is None:
            # 新群友，初始化
            friend = {
                "id": user_id,
                "nickname": qq_nickname,
                "aliases": [],
                "past_nicknames": [],
                "info": [],
                "groups": [self.group_id],
            }
        else:
            old_nick = friend.get("nickname", "")
            if old_nick and old_nick != qq_nickname:
                # 昵称变了，记录到 past_nicknames
                past = friend.get("past_nicknames", [])
                if old_nick not in past:
                    past.append(old_nick)
                friend["past_nicknames"] = past
            friend["nickname"] = qq_nickname
            if self.group_id not in friend.get("groups", []):
                friend.setdefault("groups", []).append(self.group_id)
        await self.save_friend(user_id, friend)
        logger.info(f"[记忆] 群友昵称更新: {user_id} -> {qq_nickname}")

    @staticmethod
    def get_active_users(messages: list) -> list[dict[str, str]]:
        """返回 [{"id": "QQ号", "name": "昵称"}, ...]"""
        seen = set()
        users = []
        for msg in messages:
            uid = msg.user_id if hasattr(msg, "user_id") else str(msg.get("user_id", ""))
            name = msg.user_name if hasattr(msg, "user_name") else str(msg.get("user_name", ""))
            if uid and uid not in seen:
                seen.add(uid)
                users.append({"id": uid, "name": name})
        return users

    # ========== 文化记忆管理 ==========

    async def load_culture(self) -> list[dict]:
        """加载文化记忆（梗、网络用语等）"""
        path = self.data_dir / "culture.json"
        if not path.exists():
            return []
        try:
            async with await anyio.open_file(path, encoding="utf-8") as f:
                return json.loads(await f.read()).get("terms", [])
        except Exception as e:
            logger.error(f"加载文化记忆失败: {e}")
            return []

    async def save_culture(self, terms: list[dict]):
        """保存文化记忆"""
        path = self.data_dir / "culture.json"
        async with await anyio.open_file(path, "w", encoding="utf-8") as f:
            await f.write(json.dumps({"terms": terms}, ensure_ascii=False, indent=2))

    async def apply_culture_ops(self, ops: dict):
        """处理文化记忆操作（add/modify/delete）
        
        ops 格式:
        {
            "add": [{"term": "yyds", "meaning": "永远的神", "context": "表示赞美"}],
            "modify": [{"index": 0, "term": "yyds", "meaning": "永远滴神", "context": "..."}],
            "delete": [1]
        }
        """
        if not ops:
            return
        
        terms = await self.load_culture()
        
        # 删除操作
        for idx in sorted([int(i) for i in ops.get("delete", [])], reverse=True):
            if 0 <= idx < len(terms):
                removed = terms.pop(idx)
                logger.debug(f"[文化记忆] 删除: {removed.get('term', '')}")
        
        # 修改操作
        for mod in ops.get("modify", []):
            idx = int(mod.get("index", -1))
            if 0 <= idx < len(terms):
                # 更新字段
                for key in ["term", "meaning", "context", "usage_examples"]:
                    if key in mod and mod[key]:
                        terms[idx][key] = mod[key]
                logger.debug(f"[文化记忆] 修改: {terms[idx].get('term', '')}")
        
        # 添加操作
        for item in ops.get("add", []):
            if item and item.get("term"):
                # 检查是否已存在
                existing = next((t for t in terms if t.get("term") == item["term"]), None)
                if existing:
                    # 更新使用次数
                    existing["usage_count"] = existing.get("usage_count", 0) + 1
                    logger.debug(f"[文化记忆] 更新使用次数: {item['term']}")
                else:
                    # 新增条目
                    from datetime import datetime
                    new_term = {
                        "term": item["term"],
                        "meaning": item.get("meaning", ""),
                        "context": item.get("context", ""),
                        "usage_examples": item.get("usage_examples", []),
                        "first_seen": datetime.now().strftime("%Y-%m-%d"),
                        "usage_count": 1,
                        "source": item.get("source", "learned"),
                    }
                    terms.append(new_term)
                    logger.info(f"[文化记忆] 新增: {item['term']} - {item.get('meaning', '')}")
        
        await self.save_culture(terms)

    def match_culture_terms(self, terms: list[dict], text: str) -> list[dict]:
        """根据文本内容匹配相关的文化词汇
        
        Args:
            terms: 文化记忆列表
            text: 要匹配的文本
            
        Returns:
            匹配到的文化词汇列表
        """
        matched = []
        text_lower = text.lower()
        
        for term in terms:
            term_str = term.get("term", "").lower()
            if term_str and term_str in text_lower:
                matched.append(term)
        
        return matched
