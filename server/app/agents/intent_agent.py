"""IntentAgent: parses user travel intent into structured data."""

import re
from datetime import datetime, timedelta

from app.core.agent import BaseAgent, AgentResult
from app.core.prompts import prompt_manager
from app.core.llm import chat_completion
from app.core.error_handler import safe_json_parse
from app.core.logging import get_logger, log_agent_start, log_agent_done
from app.core.tool import tool_registry

import time

logger = get_logger("intent_agent")


class IntentAgent(BaseAgent):
    name = "IntentAgent"
    description = "Parses user travel intent from natural language into structured trip requirements"
    version = "1.0.0"
    dependencies = []

    async def execute(self, context: dict) -> AgentResult:
        start = time.monotonic()
        query = context.get("query", context.get("user_query", ""))

        log_agent_start(logger, self.name, context.get("run_id", ""))

        try:
            template = prompt_manager.get("IntentAgent")
            messages = [
                {"role": "system", "content": template.render_system()},
                {"role": "user", "content": template.render_user(user_query=query)},
            ]

            # Include date tool for relative date parsing
            tools = [t.schema.__dict__ for t in [tool_registry.get("get_current_date")]]

            response = await chat_completion(
                messages=messages,
                tools=tools,
                temperature=0.3,  # Low temperature for parsing
            )

            # Handle tool calls (get_current_date)
            content = response.get("content", "")
            if response.get("tool_calls"):
                for tc in response["tool_calls"]:
                    if tc["name"] == "get_current_date":
                        date_tool = tool_registry.get("get_current_date")
                        current_date = await date_tool.execute()
                        messages.append({"role": "assistant", "content": None, "tool_calls": response.get("tool_calls")})
                        messages.append({"role": "tool", "content": current_date,
                                        "tool_call_id": tc.get("id", "")})
                        follow_up = await chat_completion(messages=messages, temperature=0.3)
                        content = follow_up.get("content", content)

            parsed = safe_json_parse(content, {
                "destination": "",
                "duration": 3,
                "start_date": "",
                "all_dates": "",
                "budget": None,
                "budget_source": "estimated",
                "preferences": [],
                "extra_requirements": "",
                "travelers": 1,
                "plan_variant": "",
                "variant_profile": {},
            })
            parsed = self._normalize_parsed(parsed, query)

            duration_ms = (time.monotonic() - start) * 1000
            log_agent_done(logger, self.name, context.get("run_id", ""), duration_ms,
                          destination=parsed.get("destination", ""))

            return AgentResult(
                agent_name=self.name,
                success=True,
                output=parsed,
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.monotonic() - start) * 1000
            logger.warning("intent_agent.fallback", error=str(e))
            parsed = self._fallback_parse(query)
            return AgentResult(
                agent_name=self.name,
                success=True,
                output=parsed,
                duration_ms=duration_ms,
            )

    @staticmethod
    def _fallback_parse(query: str) -> dict:
        duration = 3
        budget = None
        budget_source = "estimated"
        destination = ""
        travelers = 1

        structured_destination = re.search(r"目的地[:：]\s*([^，,。.；;\s]+)", query)
        city_match = re.search(r"去([^，,。.\s]+?)(?:玩|旅游|旅行|出行|度假)", query)
        if structured_destination:
            destination = structured_destination.group(1)
        elif city_match:
            destination = city_match.group(1)
        else:
            for city in ["北京", "上海", "广州", "深圳", "杭州", "成都", "重庆", "西安", "南京", "苏州", "厦门", "鼓浪屿", "青岛", "大理", "丽江", "三亚"]:
                if city in query:
                    destination = city
                    break

        digit_days = re.search(r"(\d+)\s*天", query)
        if digit_days:
            duration = max(1, int(digit_days.group(1)))
        else:
            cn_days = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7}
            for word, value in cn_days.items():
                if f"{word}天" in query:
                    duration = value
                    break

        people_match = re.search(r"(\d+)\s*(?:人|位|个大人|个朋友)", query)
        if people_match:
            travelers = max(1, int(people_match.group(1)))
        elif re.search(r"父母同行|爸妈|父母", query):
            travelers = 3
        elif re.search(r"情侣|两个人|两人", query):
            travelers = 2

        budget_match = re.search(r"预算\s*[:：]?\s*(?:约|大概|共)?\s*(\d+(?:\.\d+)?)\s*(万|千|k|K)?", query)
        if budget_match:
            raw = float(budget_match.group(1))
            unit = budget_match.group(2)
            multiplier = 10000 if unit == "万" else 1000 if unit in {"千", "k", "K"} else 1
            budget = int(raw * multiplier)
            budget_source = "user"
        else:
            budget = IntentAgent._estimate_budget(destination, duration, travelers)

        preference_words = ["自然风光", "美食", "亲子", "文化", "历史", "博物馆", "轻松", "徒步", "购物", "摄影"]
        preferences = [word for word in preference_words if word in query]

        start = IntentAgent._default_start_date()
        all_dates = ",".join((start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(duration))

        plan_variant = IntentAgent._infer_plan_variant(query)
        variant_profile = IntentAgent._variant_profile(plan_variant)

        return {
            "destination": destination or "目的地",
            "duration": duration,
            "start_date": start.strftime("%Y-%m-%d"),
            "all_dates": all_dates,
            "budget": budget,
            "budget_source": budget_source,
            "preferences": preferences,
            "extra_requirements": query,
            "travelers": travelers,
            "plan_variant": plan_variant,
            "variant_profile": variant_profile,
        }

    @staticmethod
    def _normalize_parsed(parsed: dict, query: str) -> dict:
        fallback = IntentAgent._fallback_parse(query)
        if not isinstance(parsed, dict):
            return fallback

        normalized = dict(parsed)
        normalized["destination"] = str(normalized.get("destination") or fallback["destination"])
        normalized["travelers"] = int(normalized.get("travelers") or fallback["travelers"])

        try:
            duration = int(normalized.get("duration") or fallback["duration"])
        except (TypeError, ValueError):
            duration = fallback["duration"]
        normalized["duration"] = max(1, min(duration, 14))

        if IntentAgent._has_explicit_budget(query):
            normalized["budget"] = int(normalized.get("budget") or fallback["budget"])
            normalized["budget_source"] = "user"
        else:
            normalized["budget"] = IntentAgent._estimate_budget(
                normalized["destination"],
                normalized["duration"],
                normalized["travelers"],
            )
            normalized["budget_source"] = "estimated"

        preferences = normalized.get("preferences")
        normalized["preferences"] = preferences if isinstance(preferences, list) else fallback["preferences"]
        plan_variant = str(normalized.get("plan_variant") or "").strip() or IntentAgent._infer_plan_variant(query)
        normalized["plan_variant"] = plan_variant
        normalized["variant_profile"] = IntentAgent._variant_profile(plan_variant)
        for tag in normalized["variant_profile"].get("strategy_tags", []):
            if tag not in normalized["preferences"]:
                normalized["preferences"].append(tag)

        start_date = str(normalized.get("start_date") or "").strip()
        dates = IntentAgent._parse_dates(str(normalized.get("all_dates") or ""))

        if not start_date and dates:
            start_date = dates[0]
        start = IntentAgent._parse_date(start_date) or IntentAgent._default_start_date()

        if len(dates) < normalized["duration"]:
            dates = [
                (start + timedelta(days=i)).strftime("%Y-%m-%d")
                for i in range(normalized["duration"])
            ]

        normalized["start_date"] = start.strftime("%Y-%m-%d")
        normalized["all_dates"] = ",".join(dates[: normalized["duration"]])
        normalized.setdefault("extra_requirements", "")
        return normalized

    @staticmethod
    def _infer_plan_variant(query: str) -> str:
        if any(word in query for word in ["省钱版", "省钱", "预算低", "性价比", "公共交通优先", "地铁沿线"]):
            return "省钱版"
        if any(word in query for word in ["深度游版", "深度游", "小众", "文化体验", "更紧凑", "4到5个地点", "4-5个地点"]):
            return "深度游版"
        if any(word in query for word in ["舒适版", "少走路", "轻松", "父母", "老人", "核心区域"]):
            return "舒适版"
        return "标准版"

    @staticmethod
    def _variant_profile(plan_variant: str) -> dict:
        profiles = {
            "舒适版": {
                "name": "舒适版",
                "pace": "relaxed",
                "transport": "taxi_or_short_walk",
                "hotel": "core_area",
                "daily_spots": 3,
                "budget_strategy": "comfort_first",
                "strategy_tags": ["少走路", "核心区住宿", "2-3个精华景点", "舒适交通"],
            },
            "省钱版": {
                "name": "省钱版",
                "pace": "balanced",
                "transport": "public_transit",
                "hotel": "metro_line",
                "daily_spots": 3,
                "budget_strategy": "save_money",
                "strategy_tags": ["公共交通优先", "地铁沿线住宿", "免费/低价景点", "平价本地餐饮"],
            },
            "深度游版": {
                "name": "深度游版",
                "pace": "compact",
                "transport": "walk_and_transit",
                "hotel": "near_next_route",
                "daily_spots": 4,
                "budget_strategy": "experience_first",
                "strategy_tags": ["小众路线", "文化体验优先", "每天4-5个地点", "节奏紧凑"],
            },
        }
        return profiles.get(plan_variant) or {
            "name": "标准版",
            "pace": "balanced",
            "transport": "mixed",
            "hotel": "route_friendly",
            "daily_spots": 3,
            "budget_strategy": "balanced",
            "strategy_tags": ["路线连贯", "预算均衡", "景点优先"],
        }

    @staticmethod
    def _has_explicit_budget(query: str) -> bool:
        return bool(re.search(r"预算\s*[:：]?\s*(?:约|大概|共)?\s*\d", query))

    @staticmethod
    def _estimate_budget(destination: str, duration: int, travelers: int) -> int:
        base_per_person_day = 650
        premium_destinations = ["北京", "上海", "三亚", "鼓浪屿", "厦门", "杭州"]
        if any(city in destination for city in premium_destinations):
            base_per_person_day = 800
        return max(800, int(duration) * max(1, int(travelers)) * base_per_person_day)

    @staticmethod
    def _default_start_date():
        return datetime.now().date() + timedelta(days=1)

    @staticmethod
    def _parse_date(value: str):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_dates(value: str) -> list[str]:
        return [
            item.strip()
            for item in value.split(",")
            if IntentAgent._parse_date(item.strip())
        ]
