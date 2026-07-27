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

from abc import ABC, abstractmethod

import httpx
from nonebot import logger

from .config import plugin_config


class SearchClient(ABC):
    """搜索客户端基类"""

    @abstractmethod
    async def search(self, query: str, max_results: int = 3) -> list[dict]:
        """执行搜索
        
        Args:
            query: 搜索查询词
            max_results: 最大结果数
            
        Returns:
            搜索结果列表，每项包含 title, content, url
        """
        pass

    def format_results(self, results: list[dict]) -> str:
        """格式化搜索结果为 LLM 可读文本"""
        if not results:
            return "未找到相关搜索结果"
        
        formatted = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "")
            content = r.get("content", "")
            url = r.get("url", "")
            formatted.append(f"{i}. {title}\n   {content}\n   来源: {url}")
        
        return "\n\n".join(formatted)


class TavilySearchClient(SearchClient):
    """Tavily 搜索客户端（需要安装 tavily-python）"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._client = None

    async def _get_client(self):
        if self._client is None:
            try:
                from tavily import AsyncTavilyClient
                self._client = AsyncTavilyClient(api_key=self.api_key)
            except ImportError:
                logger.error("tavily-python 未安装，请运行: pip install tavily-python")
                raise
        return self._client

    async def search(self, query: str, max_results: int = 3) -> list[dict]:
        try:
            client = await self._get_client()
            response = await client.search(
                query=query,
                max_results=max_results,
                search_depth="basic",
                include_answer=False,
            )
            
            results = []
            for item in response.get("results", []):
                results.append({
                    "title": item.get("title", ""),
                    "content": item.get("content", ""),
                    "url": item.get("url", ""),
                })
            
            logger.info(f"[搜索] Tavily 搜索 '{query}' 返回 {len(results)} 条结果")
            return results
            
        except Exception as e:
            logger.error(f"[搜索] Tavily 搜索失败: {e}")
            return []


class DuckDuckGoSearchClient(SearchClient):
    """DuckDuckGo 搜索客户端（免费，需要安装 duckduckgo-search）"""

    def __init__(self):
        self._client = None

    async def _get_client(self):
        if self._client is None:
            try:
                from duckduckgo_search import AsyncDDGS
                self._client = AsyncDDGS()
            except ImportError:
                logger.error("duckduckgo-search 未安装，请运行: pip install duckduckgo-search")
                raise
        return self._client

    async def search(self, query: str, max_results: int = 3) -> list[dict]:
        try:
            client = await self._get_client()
            results = []
            
            async for item in client.atext(query, max_results=max_results):
                results.append({
                    "title": item.get("title", ""),
                    "content": item.get("body", ""),
                    "url": item.get("href", ""),
                })
            
            logger.info(f"[搜索] DuckDuckGo 搜索 '{query}' 返回 {len(results)} 条结果")
            return results
            
        except Exception as e:
            logger.error(f"[搜索] DuckDuckGo 搜索失败: {e}")
            return []


class BingSearchClient(SearchClient):
    """Bing Web Search API 客户端（使用 httpx 异步请求，需要 Bing API Key）"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.endpoint = "https://api.bing.microsoft.com/v7.0/search"

    async def search(self, query: str, max_results: int = 3) -> list[dict]:
        try:
            headers = {"Ocp-Apim-Subscription-Key": self.api_key}
            params = {
                "q": query,
                "count": max_results,
                "textDecorations": True,
                "textFormat": "HTML",
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.endpoint, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()
            
            results = []
            for item in data.get("webPages", {}).get("value", []):
                results.append({
                    "title": item.get("name", ""),
                    "content": item.get("snippet", ""),
                    "url": item.get("url", ""),
                })
            
            logger.info(f"[搜索] Bing 搜索 '{query}' 返回 {len(results)} 条结果")
            return results
            
        except Exception as e:
            logger.error(f"[搜索] Bing 搜索失败: {e}")
            return []


def create_search_client() -> SearchClient | None:
    """根据配置创建搜索客户端
    
    Returns:
        SearchClient 实例，如果搜索未启用则返回 None
    """
    if not plugin_config.aigf_search_enabled:
        return None
    
    api = plugin_config.aigf_search_api.lower()
    api_key = plugin_config.aigf_search_api_key
    
    if api == "tavily":
        if not api_key:
            logger.warning("[搜索] Tavily API Key 未配置（AIGF_SEARCH_API_KEY），搜索功能禁用")
            return None
        return TavilySearchClient(api_key)
    
    elif api == "duckduckgo":
        return DuckDuckGoSearchClient()
    
    elif api == "bing":
        if not api_key:
            logger.warning("[搜索] Bing API Key 未配置（AIGF_SEARCH_API_KEY），搜索功能禁用")
            return None
        return BingSearchClient(api_key)
    
    else:
        logger.warning(f"[搜索] 不支持的搜索 API: {api}")
        return None


# 全局搜索客户端实例
_search_client: SearchClient | None = None


def get_search_client() -> SearchClient | None:
    """获取全局搜索客户端实例"""
    global _search_client
    if _search_client is None and plugin_config.aigf_search_enabled:
        _search_client = create_search_client()
    return _search_client
