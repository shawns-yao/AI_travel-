from __future__ import annotations

import time
import re
from typing import Any

from app.core.agent import AgentResult, BaseAgent
from app.core.logging import get_logger, log_agent_done, log_agent_start
from app.core.tool import tool_registry
from app.services.destination_resolver import resolve_destination
from app.services.guide_corpus import curated_guide

logger = get_logger("guide_agent")


class GuideAgent(BaseAgent):
    name = "GuideAgent"
    description = "Retrieves web and curated travel guide context for route quality, ticket rules, food, hotels, and avoidance tips"
    version = "1.0.0"
    dependencies = ["IntentAgent"]

    async def execute(self, context: dict[str, Any]) -> AgentResult:
        start = time.monotonic()
        run_id = context.get("run_id", "")
        log_agent_start(logger, self.name, run_id)

        intent = context.get("IntentAgent", {}) or {}
        destination = str(intent.get("destination") or "目的地")
        resolved = resolve_destination(destination)
        emit_event = context.get("emit_event")
        web_sources: list[dict[str, str]] = []

        queries = self._queries(destination, resolved.search_city, resolved.must_include)
        search_tool = tool_registry.get("mcp_web_search")
        for query in queries:
            results = await search_tool.execute(query=query, limit=4)
            web_sources.extend(results)
            if callable(emit_event):
                emit_event(
                    "tool.completed",
                    agent_name=self.name,
                    tool_name="mcp_web_search",
                    success=True,
                    destination=destination,
                    category="攻略",
                    summary=f"检索攻略：{query}",
                    output={"destination": destination, "query": query, "items": results[:3]},
                )

        curated = curated_guide(destination)
        sources = self._dedupe_sources([*web_sources, *curated.get("sources", [])])
        source_pool = [*sources, *curated.get("sources", [])]
        output = {
            "destination": destination,
            "resolved_city": resolved.search_city,
            "required_focus": resolved.must_include,
            "sources": sources[:8],
            "highlights": curated.get("highlights", []),
            "pre_trip": curated.get("pre_trip", []),
            "food": curated.get("food", []),
            "hotel": curated.get("hotel", []),
            "avoidance": curated.get("avoidance", []),
            "backup": curated.get("backup", []),
            "operational_constraints": self._operational_constraints(source_pool),
            "web_snippets": [self._snippet(item) for item in sources[:8] if item.get("snippet")],
        }

        duration_ms = (time.monotonic() - start) * 1000
        log_agent_done(logger, self.name, run_id, duration_ms, sources=len(sources))
        return AgentResult(
            agent_name=self.name,
            success=True,
            output=output,
            duration_ms=duration_ms,
        )

    @staticmethod
    def _queries(destination: str, city: str, focus: str) -> list[str]:
        queries = [
            f"{destination} 三日游 攻略 行程 避坑",
            f"{focus} 官方 开放时间 预约 末班 交通",
            f"{city} {focus} 住宿 美食 交通 攻略",
            f"{city} {focus} 酒店 民宿 住宿 推荐 图片",
            f"{focus} 景点 图片 建筑 街区 老别墅",
        ]
        if "鼓浪屿" in focus or "厦门" in city:
            queries.append("泉州 厦门 鼓浪屿 三日游 行程 攻略")
        return queries

    @staticmethod
    def _dedupe_sources(items: list[dict[str, str]]) -> list[dict[str, str]]:
        seen: set[str] = set()
        results: list[dict[str, str]] = []
        for item in items:
            title = str(item.get("title") or "").strip()
            url = str(item.get("url") or "").strip()
            key = url or title
            if not key or key in seen:
                continue
            seen.add(key)
            results.append({
                "title": title,
                "url": url,
                "snippet": str(item.get("snippet") or "").strip(),
                "source": str(item.get("source") or "web"),
                "image": str(item.get("image") or "").strip(),
            })
        return results

    @staticmethod
    def _snippet(item: dict[str, str]) -> str:
        title = str(item.get("title") or "").strip()
        snippet = str(item.get("snippet") or "").strip()
        return f"{title}：{snippet}" if title and snippet else snippet or title

    @staticmethod
    def _operational_constraints(items: list[dict[str, str]]) -> list[str]:
        constraints: list[str] = []
        pattern = re.compile(r"(开放|闭园|预约|实名|末班|最晚|停运|返程|船票|车票|限流|入园|航班|班船|售票)")
        time_pattern = re.compile(r"\\d{1,2}[:：]\\d{2}|提前\\d+天|\\d+天")
        for item in items:
            item_constraints = item.get("constraints")
            if isinstance(item_constraints, list):
                constraints.extend(str(value) for value in item_constraints if value)
            text = " ".join([
                str(item.get("title") or ""),
                str(item.get("snippet") or ""),
            ]).strip()
            if not text or not pattern.search(text):
                continue
            if pattern.search(text) or time_pattern.search(text):
                constraints.append(text[:160])
        return GuideAgent._dedupe_text(constraints)[:6]

    @staticmethod
    def _dedupe_text(items: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in items:
            key = item.strip()
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(key)
        return result
