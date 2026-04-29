"""PlannerAgent: creates structured daily travel itinerary data."""

import time
from datetime import datetime, timedelta

from app.core.agent import BaseAgent, AgentResult
from app.core.error_handler import safe_json_parse
from app.core.llm import chat_completion
from app.core.logging import get_logger, log_agent_done, log_agent_start
from app.core.prompts import prompt_manager
from app.core.tool import tool_registry

logger = get_logger("planner_agent")


class PlannerAgent(BaseAgent):
    name = "PlannerAgent"
    description = "Generates structured daily itineraries from intent, weather, budget, and memory context"
    version = "1.0.0"
    dependencies = ["IntentAgent", "WeatherAgent", "BudgetAgent", "MemoryAgent"]

    async def execute(self, context: dict) -> AgentResult:
        start = time.monotonic()
        run_id = context.get("run_id", "")
        log_agent_start(logger, self.name, run_id)

        map_context: dict = {}
        try:
            intent = context.get("IntentAgent", {})
            weather = context.get("WeatherAgent", {})
            budget = context.get("BudgetAgent", {})
            memory = context.get("MemoryAgent", {})
            map_context = await self._load_map_context(intent, context.get("emit_event"))

            template = prompt_manager.get("PlannerAgent")
            messages = [
                {"role": "system", "content": template.render_system()},
                {
                    "role": "user",
                    "content": template.render_user(
                        intent=str(intent)[:1500],
                        weather=str(weather)[:1500],
                        budget=str(budget)[:1200],
                        memory=str(memory)[:1200],
                        map_context=str(map_context)[:1800],
                    ),
                },
            ]

            response = await chat_completion(messages=messages, temperature=0.5)
            parsed = safe_json_parse(response.get("content", ""), {})
            daily_plans = parsed.get("daily_plans") or parsed.get("days") or []
            if not daily_plans:
                daily_plans = self._fallback_daily_plans(intent, weather, budget, map_context)

            output = {"daily_plans": daily_plans, "map_data": map_context}
            duration_ms = (time.monotonic() - start) * 1000
            log_agent_done(logger, self.name, run_id, duration_ms, days=len(daily_plans))
            return AgentResult(
                agent_name=self.name,
                success=True,
                output=output,
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.monotonic() - start) * 1000
            logger.warning("planner_agent.fallback", error=str(e))
            intent = context.get("IntentAgent", {})
            weather = context.get("WeatherAgent", {})
            budget = context.get("BudgetAgent", {})
            if not map_context:
                map_context = await self._load_map_context(intent, context.get("emit_event"))
            return AgentResult(
                agent_name=self.name,
                success=True,
                output={
                    "daily_plans": self._fallback_daily_plans(intent, weather, budget, map_context),
                    "map_data": map_context,
                },
                duration_ms=duration_ms,
            )

    async def _load_map_context(self, intent: dict, emit_event=None) -> dict:
        destination = intent.get("destination") or "目的地"
        try:
            geocode_tool = tool_registry.get("amap_geocode")
            poi_tool = tool_registry.get("amap_search_poi")
            route_tool = tool_registry.get("amap_route_planning")

            center = await geocode_tool.execute(address=destination, city=destination)
            if callable(emit_event):
                emit_event(
                    "tool.completed",
                    agent_name=self.name,
                    tool_name="amap_geocode",
                    success=True,
                    summary=f"定位 {destination}",
                    output={"center": center},
                )
            attractions = await poi_tool.execute(keywords="景点", city=destination, limit=6)
            if callable(emit_event):
                emit_event(
                    "tool.completed",
                    agent_name=self.name,
                    tool_name="amap_search_poi",
                    success=True,
                    category="景点",
                    summary=f"查到 {len(attractions)} 个景点",
                    output={"items": attractions[:5]},
                )
            food = await poi_tool.execute(keywords="高评分餐厅", city=destination, limit=4)
            if callable(emit_event):
                emit_event(
                    "tool.completed",
                    agent_name=self.name,
                    tool_name="amap_search_poi",
                    success=True,
                    category="餐饮",
                    summary=f"查到 {len(food)} 个餐饮点",
                    output={"items": food[:4]},
                )
            hotels = await poi_tool.execute(keywords="酒店", city=destination, limit=3)
            if callable(emit_event):
                emit_event(
                    "tool.completed",
                    agent_name=self.name,
                    tool_name="amap_search_poi",
                    success=True,
                    category="酒店",
                    summary=f"查到 {len(hotels)} 个住宿点",
                    output={"items": hotels[:3]},
                )

            route_points = [p for p in attractions if p.get("location")][:3]
            routes = []
            for origin, target in zip(route_points, route_points[1:]):
                o = origin["location"]
                t = target["location"]
                route = await route_tool.execute(
                    origin=f"{o['lng']},{o['lat']}",
                    destination=f"{t['lng']},{t['lat']}",
                    mode="walking",
                    city=destination,
                )
                routes.append({
                    "from": origin.get("name", ""),
                    "to": target.get("name", ""),
                    **route,
                })
            if callable(emit_event):
                emit_event(
                    "tool.completed",
                    agent_name=self.name,
                    tool_name="amap_route_planning",
                    success=True,
                    summary=f"生成 {len(routes)} 段路线",
                    output={"routes": routes[:3]},
                )

            return {
                "destination": destination,
                "center": center,
                "attractions": attractions,
                "food": food,
                "hotels": hotels,
                "routes": routes,
            }
        except Exception as e:
            logger.warning("planner_agent.map_context_failed", error=str(e))
            return {
                "destination": destination,
                "center": {},
                "attractions": [],
                "food": [],
                "hotels": [],
                "routes": [],
            }

    def _fallback_daily_plans(self, intent: dict, weather: dict, budget: dict, map_context: dict | None = None) -> list[dict]:
        destination = intent.get("destination") or "目的地"
        duration = int(intent.get("duration") or 3)
        start_date = intent.get("start_date") or ""
        dates = self._derive_dates(start_date, duration)
        allocated = budget.get("allocated", {}) if isinstance(budget, dict) else {}
        attraction_budget = int(allocated.get("attractions", 300)) if allocated else 300
        meal_budget = int(allocated.get("meals", 600)) if allocated else 600
        forecast = {
            item.get("date"): item
            for item in (weather.get("forecast", []) if isinstance(weather, dict) else [])
            if isinstance(item, dict)
        }

        plans: list[dict] = []
        attractions = (map_context or {}).get("attractions", []) if isinstance(map_context, dict) else []
        food = (map_context or {}).get("food", []) if isinstance(map_context, dict) else []
        for index, date in enumerate(dates, start=1):
            weather_note = forecast.get(date, {}).get("recommendation", "按轻松节奏安排，预留机动时间。")
            morning_poi = attractions[(index - 1) % len(attractions)] if attractions else {}
            afternoon_poi = attractions[index % len(attractions)] if len(attractions) > 1 else {}
            evening_poi = attractions[(index + 1) % len(attractions)] if len(attractions) > 2 else {}
            dinner_poi = food[(index - 1) % len(food)] if food else {}
            plans.append(
                {
                    "day": index,
                    "date": date,
                    "activities": [
                        {
                            "id": f"day{index}_morning",
                            "name": morning_poi.get("name") or f"{destination}核心景点慢游",
                            "type": "sightseeing",
                            "description": "选择距离住宿较近的经典景点，控制步行强度。",
                            "location": morning_poi.get("address") or destination,
                            "duration": "2-3小时",
                            "time": "上午",
                            "cost": round(attraction_budget / max(duration, 1) * 0.45),
                            "source": morning_poi.get("source"),
                            "coordinate": morning_poi.get("location"),
                        },
                        {
                            "id": f"day{index}_afternoon",
                            "name": afternoon_poi.get("name") or f"{destination}城市街区体验",
                            "type": "cultural",
                            "description": "安排本地街区、博物馆或室内备选点，方便按天气调整。",
                            "location": afternoon_poi.get("address") or destination,
                            "duration": "2小时",
                            "time": "下午",
                            "cost": round(attraction_budget / max(duration, 1) * 0.35),
                            "source": afternoon_poi.get("source"),
                            "coordinate": afternoon_poi.get("location"),
                        },
                        {
                            "id": f"day{index}_evening",
                            "name": evening_poi.get("name") or f"{destination}夜游休闲区",
                            "type": "cultural",
                            "description": "安排轻量夜游、观景或文化街区，避免把晚上只变成用餐。",
                            "location": evening_poi.get("address") or destination,
                            "duration": "1.5-2小时",
                            "time": "晚上",
                            "cost": round(attraction_budget / max(duration, 1) * 0.2),
                            "source": evening_poi.get("source"),
                            "coordinate": evening_poi.get("location"),
                        },
                    ],
                    "meals": [
                        {
                            "id": f"day{index}_dinner",
                            "name": dinner_poi.get("name") or f"{destination}品质晚餐",
                            "type": "dinner",
                            "cuisine": "local",
                            "location": dinner_poi.get("address") or destination,
                            "time": "晚上",
                            "cost": round(meal_budget / max(duration, 1) * 0.75),
                            "source": dinner_poi.get("source"),
                            "coordinate": dinner_poi.get("location"),
                        },
                    ],
                    "notes": weather_note,
                }
            )
        return plans

    @staticmethod
    def _derive_dates(start_date: str, duration: int) -> list[str]:
        if not start_date:
            return [f"Day {i}" for i in range(1, duration + 1)]
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            return [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(duration)]
        except ValueError:
            return [f"Day {i}" for i in range(1, duration + 1)]
