from __future__ import annotations

import html
import re
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.core.tool import BaseTool
from app.services.information_cache import InformationCache

logger = get_logger("web_search_tool")


class MCPWebSearchTool(BaseTool):
    name = "mcp_web_search"
    description = "Search the public web for travel guide context, tickets, routes, food, hotels, and avoidance tips."

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query."},
                "limit": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        }

    async def execute(self, query: str = "", limit: int = 5, **kwargs: Any) -> list[dict[str, str]]:
        query = str(query or "").strip()
        if not query:
            return []
        limit = max(1, min(int(limit or 5), 10))
        provider = (settings.web_search_provider or "duckduckgo").strip().lower()
        cache_key = f"{provider}:{query}:{limit}"
        cache = InformationCache("mcp_web_search", ttl_seconds=12 * 3600)
        try:
            cached = await cache.get(cache_key)
            if cached and isinstance(cached.get("results"), list) and cached["results"]:
                return cached["results"]
        except Exception as e:
            logger.warning("web_search.cache_get_failed", query=query, error=str(e))

        if provider == "disabled":
            return []

        try:
            if provider == "brave":
                results = await self._search_brave(query, limit)
            elif provider == "tavily":
                results = await self._search_tavily(query, limit)
            elif provider == "baidu":
                results = await self._search_baidu(query, limit)
            elif provider == "bing":
                results = await self._search_bing(query, limit)
            else:
                try:
                    results = await self._search_duckduckgo(query, limit)
                except Exception as e:
                    logger.warning("web_search.duckduckgo_failed", query=query, error=str(e))
                    results = []
                if not results:
                    results = await self._search_bing(query, limit)
            try:
                await cache.set(cache_key, {"results": results})
            except Exception as e:
                logger.warning("web_search.cache_set_failed", query=query, error=str(e))
            return results
        except Exception as e:
            logger.warning("web_search.failed", provider=provider, query=query, error=str(e))
            return []

    async def _search_brave(self, query: str, limit: int) -> list[dict[str, str]]:
        if not settings.web_search_api_key:
            return []
        base_url = settings.web_search_base_url or "https://api.search.brave.com/res/v1/web/search"
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.get(
                base_url,
                params={"q": query, "count": limit, "country": "CN", "search_lang": "zh-hans"},
                headers={"X-Subscription-Token": settings.web_search_api_key},
            )
            response.raise_for_status()
            data = response.json()
        items = data.get("web", {}).get("results", []) if isinstance(data, dict) else []
        return [self._result(item.get("title"), item.get("url"), item.get("description"), "brave") for item in items[:limit]]

    async def _search_tavily(self, query: str, limit: int) -> list[dict[str, str]]:
        if not settings.web_search_api_key:
            return []
        base_url = settings.web_search_base_url or "https://api.tavily.com/search"
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                base_url,
                json={
                    "api_key": settings.web_search_api_key,
                    "query": query,
                    "max_results": limit,
                    "search_depth": "basic",
                    "include_answer": False,
                },
            )
            response.raise_for_status()
            data = response.json()
        items = data.get("results", []) if isinstance(data, dict) else []
        return [self._result(item.get("title"), item.get("url"), item.get("content"), "tavily") for item in items[:limit]]

    async def _search_baidu(self, query: str, limit: int) -> list[dict[str, str]]:
        if not settings.web_search_api_key:
            return []
        base_url = settings.web_search_base_url or "https://qianfan.baidubce.com/v2/ai_search/web_search"
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                base_url,
                json={
                    "messages": [{"role": "user", "content": query}],
                    "edition": "lite",
                    "search_source": "baidu_search_v2",
                    "resource_type_filter": [
                        {"type": "web", "top_k": limit},
                        {"type": "image", "top_k": min(limit, 6)},
                    ],
                    "safe_search": True,
                },
                headers={
                    "Authorization": f"Bearer {settings.web_search_api_key}",
                    "X-Appbuilder-Authorization": f"Bearer {settings.web_search_api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()
        items = data.get("references", []) if isinstance(data, dict) else []
        results = [
            self._result(
                item.get("title") or item.get("web_anchor"),
                item.get("url"),
                item.get("content"),
                "baidu",
                image=item.get("image"),
            )
            for item in items
            if isinstance(item, dict)
        ]
        results.sort(key=lambda item: 0 if item.get("image") else 1)
        return results[:limit]

    async def _search_duckduckgo(self, query: str, limit: int) -> list[dict[str, str]]:
        base_url = settings.web_search_base_url or "https://duckduckgo.com/html/"
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            response = await client.get(
                base_url,
                params={"q": query},
                headers={"User-Agent": "Mozilla/5.0 AI-Travel-Agent/0.1"},
            )
            response.raise_for_status()
            body = response.text
        return self._parse_duckduckgo(body, limit)

    async def _search_bing(self, query: str, limit: int) -> list[dict[str, str]]:
        base_url = settings.web_search_base_url or "https://www.bing.com/search"
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            response = await client.get(
                base_url,
                params={"q": query, "mkt": "zh-CN"},
                headers={"User-Agent": "Mozilla/5.0 AI-Travel-Agent/0.1"},
            )
            response.raise_for_status()
            body = response.text
        return self._parse_bing(body, limit)

    @classmethod
    def _parse_duckduckgo(cls, body: str, limit: int) -> list[dict[str, str]]:
        results: list[dict[str, str]] = []
        blocks = re.split(r'class="result__body"', body)
        for block in blocks[1:]:
            title_match = re.search(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
            snippet_match = re.search(r'class="result__snippet"[^>]*>(.*?)</a>|class="result__snippet"[^>]*>(.*?)</div>', block, re.S)
            if not title_match:
                continue
            url = cls._clean_html(title_match.group(1))
            title = cls._clean_html(title_match.group(2))
            snippet = cls._clean_html((snippet_match.group(1) or snippet_match.group(2)) if snippet_match else "")
            if title and url:
                results.append(cls._result(title, url, snippet, "duckduckgo"))
            if len(results) >= limit:
                break
        return results

    @classmethod
    def _parse_bing(cls, body: str, limit: int) -> list[dict[str, str]]:
        results: list[dict[str, str]] = []
        blocks = re.findall(r'<li class="b_algo".*?</li>', body, flags=re.S)
        for block in blocks:
            title_match = re.search(r"<h2[^>]*>.*?<a[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>.*?</h2>", block, re.S)
            snippet_match = re.search(r"<p[^>]*>(.*?)</p>", block, re.S)
            if not title_match:
                continue
            url = cls._clean_html(title_match.group(1))
            title = cls._clean_html(title_match.group(2))
            snippet = cls._clean_html(snippet_match.group(1) if snippet_match else "")
            if title and url:
                results.append(cls._result(title, url, snippet, "bing"))
            if len(results) >= limit:
                break
        return results

    @staticmethod
    def _clean_html(value: str | None) -> str:
        cleaned = re.sub(r"<.*?>", "", value or "", flags=re.S)
        return html.unescape(cleaned).strip()

    @staticmethod
    def _result(title: str | None, url: str | None, snippet: str | None, source: str, image: str | None = None) -> dict[str, str]:
        return {
            "title": str(title or "").strip(),
            "url": str(url or "").strip(),
            "snippet": str(snippet or "").strip(),
            "source": source,
            "image": str(image or "").strip(),
        }
