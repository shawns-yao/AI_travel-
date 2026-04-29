"""IntentAgent: parses user travel intent into structured data."""

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
            logger.error("intent_agent.failed", error=str(e))
            return AgentResult(
                agent_name=self.name,
                success=False,
                error=str(e),
                duration_ms=duration_ms,
            )
