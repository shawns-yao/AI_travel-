"""WeatherAgent: queries weather forecast and generates travel recommendations."""

import time

from app.core.agent import BaseAgent, AgentResult
from app.core.logging import get_logger, log_agent_start, log_agent_done
from app.core.tool import tool_registry

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
            dates = [d.strip() for d in all_dates.split(",") if d.strip()] if all_dates else []

            # 天气属于确定性外部信息，不能让 LLM “看心情”决定是否调工具。
            location_tool = tool_registry.get("get_location_id")
            weather_tool = tool_registry.get("get_weather_by_location_id")
            location_id = await location_tool.execute(address=destination)
            emit_event = context.get("emit_event")
            if callable(emit_event):
                emit_event(
                    "tool.completed",
                    agent_name=self.name,
                    tool_name="get_location_id",
                    success=True,
                    summary=f"定位到 {destination}",
                    output={"destination": destination, "location_id": location_id},
                )
            parsed = await weather_tool.execute(locationId=location_id, dates=dates)
            parsed = self._normalize_forecast(parsed, dates)
            if callable(emit_event):
                emit_event(
                    "tool.completed",
                    agent_name=self.name,
                    tool_name="get_weather_by_location_id",
                    success=True,
                    summary=f"获取 {len(parsed)} 天游玩天气",
                    output={"forecast": parsed[:3], "source": parsed[0].get("source") if parsed else ""},
                )

            risk_levels = [d.get("risk_level", "LOW") for d in parsed]
            risk_analysis = "天气整体适合出行"
            if "CRITICAL" in risk_levels:
                risk_analysis = "存在严重天气风险，建议调整日期或准备室内备选"
            elif "HIGH" in risk_levels:
                risk_analysis = "存在较高天气风险，需要准备室内备选"
            elif "MEDIUM" in risk_levels:
                risk_analysis = "有轻微天气影响，注意衣物和雨具"

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
                tool_calls=[
                    {"tool": "get_location_id", "args": {"address": destination}},
                    {"tool": "get_weather_by_location_id", "args": {"locationId": location_id, "dates": dates}},
                ],
            )
        except Exception as e:
            duration_ms = (time.monotonic() - start) * 1000
            logger.warning("weather_agent.fallback", error=str(e))
            intent = context.get("IntentAgent", {})
            all_dates = intent.get("all_dates", "")
            dates = [d.strip() for d in all_dates.split(",") if d.strip()] if all_dates else []
            return AgentResult(
                agent_name=self.name,
                success=True,
                output={
                    "forecast": self._fallback_forecast(dates),
                    "risk_analysis": "Weather API or LLM unavailable, using conservative fallback.",
                },
                duration_ms=duration_ms,
            )

    @staticmethod
    def _fallback_forecast(dates: list[str]) -> list[dict]:
        return [{
            "date": d,
            "condition": "unknown",
            "temp_high": 20,
            "temp_low": 10,
            "humidity": 50,
            "recommendation": "天气数据暂不可用，优先安排可室内外切换的活动。",
            "risk_level": "LOW",
            "source": "fallback",
        } for d in dates] if dates else []

    @staticmethod
    def _normalize_forecast(forecast: list[dict], dates: list[str]) -> list[dict]:
        by_date = {item.get("date"): item for item in forecast if isinstance(item, dict)}
        result: list[dict] = []
        for date in dates:
            item = dict(by_date.get(date) or {})
            condition = item.get("condition") or "no_data"
            item["date"] = date
            item["condition"] = condition
            item["temp_high"] = int(item.get("temp_high") or 0)
            item["temp_low"] = int(item.get("temp_low") or 0)
            item["humidity"] = int(item.get("humidity") or 0)
            item.setdefault("recommendation", WeatherAgent._recommendation(condition))
            item.setdefault("risk_level", WeatherAgent._risk_level(condition))
            item.setdefault("source", "qweather" if condition not in {"unknown", "no_data"} else "fallback")
            result.append(item)
        return result

    @staticmethod
    def _recommendation(condition: str) -> str:
        if any(token in condition for token in ["雨", "雪", "雷", "rain", "snow", "thunder"]):
            return "安排室内备选，交通和排队时间预留更宽。"
        if any(token in condition for token in ["晴", "sunny"]):
            return "适合户外景点，注意防晒和补水。"
        return "适合常规行程，保留半小时机动时间。"

    @staticmethod
    def _risk_level(condition: str) -> str:
        if any(token in condition for token in ["暴", "雷", "thunderstorm"]):
            return "HIGH"
        if any(token in condition for token in ["雨", "雪", "rain", "snow"]):
            return "MEDIUM"
        return "LOW"
