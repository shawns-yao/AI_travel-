"""WeatherAgent: queries weather forecast and generates travel recommendations."""

import time

from app.core.agent import BaseAgent, AgentResult
from app.core.prompts import prompt_manager
from app.core.llm import chat_completion
from app.core.error_handler import safe_json_parse_list
from app.core.logging import get_logger, log_agent_start, log_agent_done

logger = get_logger("weather_agent")


class WeatherAgent(BaseAgent):
    name = "WeatherAgent"
    description = "Queries weather forecast for destination and travel dates, provides activity recommendations based on conditions"
    version = "1.0.0"
    dependencies = ["IntentAgent"]

    async def execute(self, context: dict) -> AgentResult:
        start = time.monotonic()
        run_id = context.get("run_id", "")

        log_agent_start(logger, self.name, run_id)

        try:
            intent = context.get("IntentAgent", {})
            destination = intent.get("destination", "")
            all_dates = intent.get("all_dates", "")
            preferences = intent.get("preferences", [])
            dates = [d.strip() for d in all_dates.split(",") if d.strip()] if all_dates else []

            template = prompt_manager.get("WeatherAgent")
            messages = [
                {"role": "system", "content": template.render_system()},
                {"role": "user", "content": template.render_user(
                    destination=destination,
                    dates=", ".join(dates) if dates else "unknown",
                    preferences=str(preferences),
                )},
            ]

            from app.core.tool import tool_registry as tr
            tools = []
            for name in ["get_location_id", "get_weather_by_location_id"]:
                try:
                    t = tr.get(name)
                    tools.append(t.schema.__dict__)
                except Exception:
                    pass

            response = await chat_completion(messages=messages, tools=tools if tools else None, temperature=0.5)

            # Handle sequential tool calls
            content = response.get("content", "")
            if response.get("tool_calls"):
                # Execute tool calls in order
                for tc in response["tool_calls"]:
                    tool_name = tc["name"]
                    try:
                        import json
                        args = json.loads(tc.get("arguments", "{}"))
                        tool = tr.get(tool_name)
                        result = await tool.execute(**args)
                        messages.append({"role": "assistant", "content": None, "tool_calls": [tc]})
                        messages.append({"role": "tool", "content": str(result), "tool_call_id": tc.get("id", "")})
                    except Exception as e:
                        logger.warning("weather.tool_failed", tool=tool_name, error=str(e))

                follow_up = await chat_completion(messages=messages, temperature=0.5)
                content = follow_up.get("content", content)

            parsed = safe_json_parse_list(content)
            if not parsed:
                parsed = [{
                    "date": d,
                    "condition": "unknown",
                    "temp_high": 20,
                    "temp_low": 10,
                    "humidity": 50,
                    "recommendation": "Weather data unavailable. Plan for moderate conditions.",
                    "risk_level": "LOW",
                } for d in dates] if dates else []

            # Compute overall risk
            risk_levels = [d.get("risk_level", "LOW") for d in parsed]
            risk_analysis = "All clear"
            if "CRITICAL" in risk_levels:
                risk_analysis = "Critical weather risk on some days - consider rescheduling"
            elif "HIGH" in risk_levels:
                risk_analysis = "High weather risk - prepare backup indoor plans"
            elif "MEDIUM" in risk_levels:
                risk_analysis = "Minor weather concerns - pack accordingly"

            duration_ms = (time.monotonic() - start) * 1000
            log_agent_done(logger, self.name, run_id, duration_ms, risk=risk_analysis)

            return AgentResult(
                agent_name=self.name,
                success=True,
                output={
                    "forecast": parsed,
                    "risk_analysis": risk_analysis,
                },
                duration_ms=duration_ms,
                tool_calls=[{"tool": tc["name"]} for tc in response.get("tool_calls", [])],
            )
        except Exception as e:
            duration_ms = (time.monotonic() - start) * 1000
            logger.error("weather_agent.failed", error=str(e))
            return AgentResult(
                agent_name=self.name,
                success=False,
                error=str(e),
                duration_ms=duration_ms,
            )
