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
                "budget": 3000,
                "preferences": [],
                "extra_requirements": "",
                "travelers": 1,
            })

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
        budget = 3000
        destination = ""

        city_match = re.search(r"去([^，,。.\s]+?)(?:玩|旅游|旅行|出行|度假)", query)
        if city_match:
            destination = city_match.group(1)
        else:
            for city in ["北京", "上海", "广州", "深圳", "杭州", "成都", "重庆", "西安", "南京", "苏州", "厦门", "青岛", "大理", "丽江", "三亚"]:
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

        budget_match = re.search(r"预算\s*(\d+)", query)
        if budget_match:
            budget = int(budget_match.group(1))

        preference_words = ["自然风光", "美食", "亲子", "文化", "历史", "博物馆", "轻松", "徒步", "购物", "摄影"]
        preferences = [word for word in preference_words if word in query]

        start = datetime.now().date() + timedelta(days=7)
        all_dates = ",".join((start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(duration))

        return {
            "destination": destination or "目的地",
            "duration": duration,
            "start_date": start.strftime("%Y-%m-%d"),
            "all_dates": all_dates,
            "budget": budget,
            "preferences": preferences,
            "extra_requirements": query,
            "travelers": 1,
        }
