"""PlannerAgent: creates structured daily travel itinerary data."""

import time
from datetime import datetime, timedelta

from app.core.agent import BaseAgent, AgentResult
from app.core.error_handler import safe_json_parse
from app.core.llm import chat_completion
from app.core.logging import get_logger, log_agent_done, log_agent_start
from app.core.prompts import prompt_manager
from app.core.tool import tool_registry
from app.services.destination_resolver import resolve_destination

logger = get_logger("planner_agent")


def _dedupe_list(values: list) -> list:
    seen: set[str] = set()
    result: list = []
    for value in values:
        key = str(value)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


class PlannerAgent(BaseAgent):
    name = "PlannerAgent"
    description = "Generates structured daily itineraries from intent, weather, budget, and memory context"
    version = "1.0.0"
    dependencies = ["IntentAgent", "WeatherAgent", "BudgetAgent", "MemoryAgent", "GuideAgent"]

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
            guide = context.get("GuideAgent", {})
            map_context = await self._load_map_context(intent, context.get("emit_event"))
            map_context = self._merge_guide_context(map_context, guide)
            map_context["variant_profile"] = intent.get("variant_profile") or {}

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
                        map_context=str(map_context)[:4200],
                    ),
                },
            ]

            response = await chat_completion(messages=messages, temperature=0.5)
            parsed = safe_json_parse(response.get("content", ""), {})
            daily_plans = parsed.get("daily_plans") or parsed.get("days") or []
            if not daily_plans:
                daily_plans = self._fallback_daily_plans(intent, weather, budget, map_context)
            daily_plans = self._sanitize_daily_plans(daily_plans, intent, map_context)

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
        resolved = resolve_destination(destination)
        try:
            geocode_tool = tool_registry.get("amap_geocode")
            poi_tool = tool_registry.get("amap_search_poi")
            route_tool = tool_registry.get("amap_route_planning")

            center = await geocode_tool.execute(address=resolved.must_include, city=resolved.search_city)
            search_city = (
                center.get("city")
                or center.get("district")
                or resolved.search_city
            ) if isinstance(center, dict) else resolved.search_city
            search_keywords = resolved.must_include.replace("（", " ").replace("）", " ").replace("(", " ").replace(")", " ").strip()
            if callable(emit_event):
                emit_event(
                    "tool.completed",
                    agent_name=self.name,
                    tool_name="amap_geocode",
                    success=True,
                    destination=destination,
                    summary=f"定位 {resolved.display_name}",
                    output={"destination": destination, "resolved_city": resolved.search_city, "center": center},
                )
            attractions = await poi_tool.execute(keywords=f"{search_keywords} 景点", city=search_city, limit=6)
            spot_notes = self._destination_spot_notes(resolved.must_include)
            spot_notes = await self._attach_spot_note_pois(spot_notes, attractions, poi_tool, search_city)
            for note in spot_notes:
                if note.get("location") and not any(p.get("name") == note.get("name") for p in attractions):
                    attractions.append({
                        "id": note.get("poi_id") or note.get("name"),
                        "name": note.get("name"),
                        "type": "景点",
                        "address": note.get("address") or search_city,
                        "location": note.get("location"),
                        "rating": "",
                        "cost": "",
                        "photo": "",
                        "source": note.get("source") or "amap",
                    })
            attractions = self._sort_route_points(resolved.must_include, attractions)
            if callable(emit_event):
                emit_event(
                    "tool.completed",
                    agent_name=self.name,
                    tool_name="amap_search_poi",
                    success=True,
                    destination=destination,
                    category="景点",
                    summary=f"查到 {len(attractions)} 个景点",
                    output={"destination": destination, "items": attractions[:5]},
                )
            food = await poi_tool.execute(keywords=f"{search_keywords} 高评分餐厅", city=search_city, limit=4)
            if callable(emit_event):
                emit_event(
                    "tool.completed",
                    agent_name=self.name,
                    tool_name="amap_search_poi",
                    success=True,
                    destination=destination,
                    category="餐饮",
                    summary=f"查到 {len(food)} 个餐饮点",
                    output={"destination": destination, "items": food[:4]},
                )
            hotels = await poi_tool.execute(keywords=f"{search_keywords} 酒店", city=search_city, limit=3)
            if callable(emit_event):
                emit_event(
                    "tool.completed",
                    agent_name=self.name,
                    tool_name="amap_search_poi",
                    success=True,
                    destination=destination,
                    category="酒店",
                    summary=f"查到 {len(hotels)} 个住宿点",
                    output={"destination": destination, "items": hotels[:3]},
                )

            route_points = [p for p in attractions if p.get("location")][:8]
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
                    destination=destination,
                    summary=f"生成 {len(routes)} 段路线",
                    output={"destination": destination, "routes": routes[:3]},
                )

            return {
                "destination": destination,
                "display_destination": resolved.display_name,
                "resolved_city": resolved.search_city,
                "weather_city": resolved.weather_city,
                "required_focus": resolved.must_include,
                "travel_tips": self._destination_tips(resolved.must_include),
                "spot_notes": spot_notes,
                "route_advice": self._destination_route_advice(resolved.must_include, intent.get("variant_profile")),
                "variant_profile": intent.get("variant_profile") or {},
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
                "display_destination": resolved.display_name,
                "resolved_city": resolved.search_city,
                "weather_city": resolved.weather_city,
                "required_focus": resolved.must_include,
                "travel_tips": self._destination_tips(resolved.must_include),
                "spot_notes": self._destination_spot_notes(resolved.must_include),
                "route_advice": self._destination_route_advice(resolved.must_include, intent.get("variant_profile")),
                "variant_profile": intent.get("variant_profile") or {},
                "center": {},
                "attractions": [],
                "food": [],
                "hotels": [],
                "routes": [],
            }

    @staticmethod
    async def _attach_spot_note_pois(spot_notes: list[dict], attractions: list[dict], poi_tool, search_city: str) -> list[dict]:
        enriched: list[dict] = []
        for note in spot_notes:
            if not isinstance(note, dict):
                continue
            next_note = dict(note)
            matched = next(
                (
                    poi for poi in attractions
                    if poi.get("name")
                    and (poi["name"] in next_note.get("name", "") or next_note.get("name", "") in poi["name"])
                ),
                None,
            )
            if not matched:
                try:
                    candidates = await poi_tool.execute(keywords=next_note.get("name", ""), city=search_city, limit=1)
                    matched = candidates[0] if candidates else None
                except Exception as e:
                    logger.warning("planner_agent.spot_note_poi_failed", spot=next_note.get("name"), error=str(e))
            if matched:
                next_note["poi_id"] = matched.get("id") or next_note.get("name")
                next_note["address"] = matched.get("address") or search_city
                next_note["location"] = matched.get("location")
                next_note["source"] = matched.get("source")
            enriched.append(next_note)
        return enriched

    @staticmethod
    def _sort_route_points(required_focus: str, pois: list[dict]) -> list[dict]:
        if "鼓浪屿" not in required_focus:
            return pois

        route_order = [
            ["三丘田", "电影音乐", "风琴博物馆", "八卦楼"],
            ["长寿园"],
            ["龙头路", "街心公园", "鼓浪屿风景名胜区"],
            ["港仔后", "日光岩", "菽庄"],
            ["皓月园"],
        ]

        def rank(poi: dict) -> tuple[int, str]:
            name = str(poi.get("name") or "")
            address = str(poi.get("address") or "")
            text = f"{name}{address}"
            for index, keywords in enumerate(route_order):
                if any(keyword in text for keyword in keywords):
                    return index, name
            return len(route_order), name

        deduped: list[dict] = []
        seen: set[str] = set()
        for poi in sorted(pois, key=rank):
            key = str(poi.get("name") or poi.get("id") or "")
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(poi)

        return PlannerAgent._nearest_neighbor_order(deduped)

    @staticmethod
    def _distance(origin: dict, target: dict) -> float:
        o = origin.get("location") if isinstance(origin.get("location"), dict) else {}
        t = target.get("location") if isinstance(target.get("location"), dict) else {}
        try:
            lng1, lat1 = float(o.get("lng")), float(o.get("lat"))
            lng2, lat2 = float(t.get("lng")), float(t.get("lat"))
        except (TypeError, ValueError):
            return float("inf")
        lat_scale = 111_000
        lng_scale = 111_000
        dx = (lng1 - lng2) * lng_scale
        dy = (lat1 - lat2) * lat_scale
        return (dx * dx + dy * dy) ** 0.5

    @staticmethod
    def _nearest_neighbor_order(pois: list[dict]) -> list[dict]:
        located = [poi for poi in pois if isinstance(poi.get("location"), dict)]
        unlocated = [poi for poi in pois if not isinstance(poi.get("location"), dict)]
        if len(located) <= 2:
            return [*located, *unlocated]

        remaining = located[:]
        start_index = min(
            range(len(remaining)),
            key=lambda i: (
                0 if any(
                    word in str(remaining[i].get("name") or "")
                    for word in ["三丘田", "电影音乐", "风琴博物馆", "八卦楼"]
                ) else 1,
                float(remaining[i].get("location", {}).get("lng", 999)),
                -float(remaining[i].get("location", {}).get("lat", -999)),
            ),
        )
        ordered = [remaining.pop(start_index)]

        while remaining:
            current = ordered[-1]
            next_index = min(range(len(remaining)), key=lambda i: PlannerAgent._distance(current, remaining[i]))
            ordered.append(remaining.pop(next_index))

        return [*ordered, *unlocated]

    @staticmethod
    def _match_poi_for_activity(activity: dict, fallback_names: list[dict]) -> dict:
        text = "".join([
            str(activity.get("name") or ""),
            str(activity.get("location") or ""),
            str(activity.get("description") or ""),
        ])
        stop_words = {"泉州", "厦门", "鼓浪屿", "码头"}
        keywords = ["皓月园", "长寿园", "电影音乐", "日光岩", "菽庄", "港仔后", "龙头路", "风琴博物馆", "沙坡尾", "南普陀"]
        for poi in fallback_names:
            name = str(poi.get("name") or "")
            if len(name) < 3 or name in stop_words:
                continue
            if name in text or str(activity.get("name") or "") in name or any(keyword in text and keyword in name for keyword in keywords):
                return poi
        return {}

    @staticmethod
    def _merge_guide_context(map_context: dict, guide: dict) -> dict:
        if not isinstance(map_context, dict):
            map_context = {}
        if not isinstance(guide, dict):
            return map_context

        tips = map_context.get("travel_tips") if isinstance(map_context.get("travel_tips"), dict) else {}
        merged_tips = dict(tips)
        for key in ["pre_trip", "food", "hotel", "avoidance", "backup"]:
            guide_values = guide.get(key)
            if isinstance(guide_values, list) and guide_values:
                current = merged_tips.get(key) if isinstance(merged_tips.get(key), list) else []
                merged_tips[key] = _dedupe_list([*current, *guide_values])

        map_context["travel_tips"] = merged_tips
        operational_constraints = guide.get("operational_constraints", [])
        if isinstance(operational_constraints, list) and operational_constraints:
            map_context["operational_constraints"] = _dedupe_list([
                *(map_context.get("operational_constraints") if isinstance(map_context.get("operational_constraints"), list) else []),
                *operational_constraints,
            ])

        map_context["guide_context"] = {
            "sources": guide.get("sources", []),
            "highlights": guide.get("highlights", []),
            "web_snippets": guide.get("web_snippets", []),
            "operational_constraints": map_context.get("operational_constraints", []),
        }
        return map_context

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
        variant_profile = intent.get("variant_profile") if isinstance(intent.get("variant_profile"), dict) else {}
        strategy_note = self._variant_strategy_note(variant_profile)

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
                            "description": self._activity_description(morning_poi, required_focus=(map_context or {}).get("required_focus") or destination, slot="上午"),
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
                            "description": self._activity_description(afternoon_poi, required_focus=(map_context or {}).get("required_focus") or destination, slot="下午"),
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
                            "description": self._activity_description(evening_poi, required_focus=(map_context or {}).get("required_focus") or destination, slot="晚上"),
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
                    "notes": "。".join([item for item in [weather_note.rstrip("。"), strategy_note] if item]),
                }
            )
        return plans

    def _sanitize_daily_plans(self, daily_plans: list, intent: dict, map_context: dict | None = None) -> list[dict]:
        if not isinstance(daily_plans, list):
            return self._fallback_daily_plans(intent, {}, {}, map_context)

        destination = intent.get("destination") or "目的地"
        required_focus = (map_context or {}).get("required_focus") or destination
        variant_profile = intent.get("variant_profile") if isinstance(intent.get("variant_profile"), dict) else {}
        strategy_note = self._variant_strategy_note(variant_profile)
        attractions = (map_context or {}).get("attractions", []) if isinstance(map_context, dict) else []
        fallback_names = [item for item in attractions if isinstance(item, dict) and item.get("name")]
        cleaned: list[dict] = []
        focus_seen = False

        for day_index, day in enumerate(daily_plans, start=1):
            if not isinstance(day, dict):
                continue
            next_day = dict(day)
            activities = []
            raw_activities = day.get("activities") if isinstance(day.get("activities"), list) else []
            for item_index, activity in enumerate(raw_activities, start=1):
                if not isinstance(activity, dict):
                    continue
                activity = dict(activity)
                name = str(activity.get("name") or "").strip()
                if self._is_transfer_activity(activity):
                    continue
                if any(word in name for word in ["自由活动", "自由安排", "机动时间", "休息"]):
                    replacement = fallback_names[(day_index + item_index - 2) % len(fallback_names)] if fallback_names else {}
                    name = replacement.get("name") or f"{required_focus}核心景点"
                    activity["name"] = name
                    activity["location"] = replacement.get("address") or required_focus
                    activity["coordinate"] = replacement.get("location")
                    activity["source"] = replacement.get("source")
                    activity["description"] = f"围绕{required_focus}安排明确景点，不生成空泛自由活动。"
                if required_focus and required_focus in name:
                    focus_seen = True
                activity["description"] = self._activity_description(
                    activity,
                    required_focus=required_focus,
                    slot=str(activity.get("time") or ""),
                )
                if not activity.get("coordinate"):
                    matched_poi = self._match_poi_for_activity(activity, fallback_names)
                    if matched_poi:
                        activity["location"] = matched_poi.get("address") or activity.get("location") or required_focus
                        activity["coordinate"] = matched_poi.get("location")
                        activity["source"] = matched_poi.get("source")
                activities.append(activity)

            if not activities:
                replacement = fallback_names[(day_index - 1) % len(fallback_names)] if fallback_names else {}
                activities.append({
                    "id": f"day{day_index}_focus",
                    "name": replacement.get("name") or f"{required_focus}核心景点",
                    "type": "sightseeing",
                    "description": f"围绕{required_focus}安排明确景点，不生成空泛自由活动。",
                    "location": replacement.get("address") or required_focus,
                    "duration": "2小时",
                    "time": "上午",
                    "cost": 0,
                    "source": replacement.get("source"),
                    "coordinate": replacement.get("location"),
                })
                focus_seen = True

            next_day["activities"] = activities
            meals = day.get("meals") if isinstance(day.get("meals"), list) else []
            next_day["meals"] = [meal for meal in meals if isinstance(meal, dict)]
            if strategy_note:
                notes = str(next_day.get("notes") or "").strip()
                next_day["notes"] = notes if strategy_note in notes else "。".join([item for item in [notes.rstrip("。"), strategy_note] if item])
            cleaned.append(next_day)

        if required_focus and cleaned and not focus_seen:
            first_poi = fallback_names[0] if fallback_names else {}
            first_activity = cleaned[0]["activities"][0]
            first_activity["name"] = first_poi.get("name") or f"{required_focus}核心景点"
            first_activity["location"] = first_poi.get("address") or required_focus
            first_activity["coordinate"] = first_poi.get("location")
            first_activity["source"] = first_poi.get("source")
            first_activity["description"] = f"{required_focus}是用户输入的核心目的地，必须进入主路线。"

        return cleaned

    @staticmethod
    def _is_transfer_activity(activity: dict) -> bool:
        text = "".join([
            str(activity.get("name") or ""),
            str(activity.get("location") or ""),
        ])
        transfer_words = [
            "抵达",
            "到达",
            "离开",
            "返程",
            "返回",
            "出发",
            "换乘",
            "乘坐",
            "高铁",
            "动车",
            "火车",
            "航班",
            "机场",
            "车站",
            "轮渡",
            "码头",
            "登岛",
            "离岛",
        ]
        return activity.get("type") == "transport" or any(word in text for word in transfer_words)

    @staticmethod
    def _variant_strategy_note(variant_profile: dict | None) -> str:
        if not isinstance(variant_profile, dict):
            return ""
        name = variant_profile.get("name")
        if name == "省钱版":
            return "本方案按公共交通优先、地铁沿线住宿和免费低价景点控制预算"
        if name == "舒适版":
            return "本方案控制步行和换乘强度，优先核心区域住宿与舒适交通"
        if name == "深度游版":
            return "本方案加入更多小众文化点，节奏更紧凑，适合体力较好的旅行者"
        return ""

    @staticmethod
    def _activity_description(activity: dict, required_focus: str, slot: str = "") -> str:
        name = str(activity.get("name") or "")
        existing = str(activity.get("description") or "").strip()
        if existing and not any(word in existing for word in ["控制步行强度", "方便按天气调整", "安排本地街区"]):
            return existing

        if "鼓浪屿风景名胜区" in name or (name == "鼓浪屿" and "鼓浪屿" in required_focus):
            return "从龙头路和街心公园一带慢慢切入，逛老别墅、小巷和咖啡馆，适合作为认识鼓浪屿的第一站。"
        if "港仔后" in name or "沙滩" in name:
            return "港仔后沙滩就在日光岩脚下，视野开阔，傍晚看日落很舒服，适合把紧凑行程放慢。"
        if "皓月园" in name:
            return "皓月园面向厦门市区，郑成功雕像和海岸线都很出片，人流通常比龙头路少。"
        if "长寿园" in name:
            return "长寿园偏安静，适合避开人流看闽南老建筑和园林细节，顺路感受岛上的老别墅氛围。"
        if "电影音乐" in name or "中国电影音乐馆" in name:
            return "靠近三丘田码头，适合喜欢电影和音乐的人，逛完后衔接离岛路线也比较顺。"
        if "日光岩" in name:
            return "日光岩是鼓浪屿制高点，适合天气好时登高看万国建筑群和海面，但节假日要错峰。"
        if "菽庄花园" in name:
            return "菽庄花园把园林和海景结合得很巧，适合接在日光岩后慢逛，钢琴博物馆也值得顺看。"
        if "关岳庙" in name:
            return "从香火很旺的关岳庙开始泉州老城 Citywalk，烟火气和闽南信仰感都很足。"
        if "开元寺" in name or "西街" in name:
            return "开元寺和西街是泉州古城的核心段，东西双塔、钟楼和老街烟火气可以连着看。"
        if "南普陀" in name:
            return "南普陀寺适合安排在厦门清晨，免费但通常需要预约，之后可以顺接环岛路。"
        if "沙坡尾" in name:
            return "沙坡尾保留老厦门避风坞气质，也有艺术西区和小店，适合拍照和轻松散步。"
        if name:
            return f"{name}放在{slot or '当天'}路线中，主要用于丰富{required_focus}的景观和文化层次，建议预留足够步行时间。"
        return f"围绕{required_focus}安排明确景点，避免空泛行程，优先保证路线连贯和体验完整。"

    @staticmethod
    def _destination_tips(required_focus: str) -> dict:
        if "鼓浪屿" not in required_focus:
            return {
                "pre_trip": ["提前确认景区开放时间和预约规则", "准备舒适步行鞋", "保留雨具和移动电源"],
                "food": [],
                "hotel": ["优先选择交通便利、靠近首日行程起点的住宿"],
                "avoidance": ["热门景区尽量错峰进入"],
                "backup": [],
            }
        return {
            "pre_trip": [
                "鼓浪屿船票建议提前通过“厦门轮渡有限公司”官方渠道预订，节假日优先抢三丘田码头",
                "岛上没有机动车，路线以步行为主，石板路和上下坡很多，务必穿舒适运动鞋",
                "鼓浪屿和泉州老城石板路较多，背包比行李箱更合适，行李尽量寄存或轻装上岛",
                "如果行程覆盖泉州到厦门，高铁动车班次多，优先选择到厦门站或厦门北站后再换乘市内交通",
            ],
            "food": [
                "龙头路适合集中解决厦门特色小吃，如鱼丸、海蛎煎、沙茶面，但不要把所有预算花在网红店",
                "想提升餐饮质感，可选择高评分闽南菜、海景餐厅或酒店附近餐厅",
                "泉州段可关注面线糊、姜母鸭、烧肉粽、润饼、石花膏等闽南特色",
            ],
            "hotel": [
                "想深度体验可提前订鼓浪屿岛上精品民宿",
                "更重性价比可住厦门岛内地铁沿线或中山路附近",
                "五一等假期住宿波动大，越早订越稳",
            ],
            "avoidance": [
                "节假日鼓浪屿巷道和龙头路人流大，注意财物和返程时间",
                "如果船票售罄，不要硬等，可切换植物园、钟鼓索道、沙坡尾方案",
            ],
            "backup": ["厦门园林植物园", "钟鼓索道", "沙坡尾", "南普陀寺"],
        }

    @staticmethod
    def _destination_spot_notes(required_focus: str) -> list[dict]:
        if "鼓浪屿" not in required_focus:
            return []
        return [
            {
                "name": "鼓浪屿风景名胜区",
                "highlight": "核心中心区靠近龙头路和街心公园，是商圈、老别墅和小巷慢生活的集中区域。",
                "tip": "适合放在上岛后的第一段，先建立方向感，再往沙滩或园林走。",
            },
            {
                "name": "鼓浪屿沙滩（港仔后沙滩）",
                "highlight": "日光岩脚下的热门沙滩，视野开阔，傍晚看日落很舒服。",
                "tip": "适合接在日光岩或菽庄花园后，别安排太赶。",
            },
            {
                "name": "皓月园",
                "highlight": "岛东南端看郑成功雕像和厦门市区天际线，人流相对少，拍照很稳。",
                "tip": "适合做下午或傍晚收尾点，注意返程码头时间。",
            },
            {
                "name": "长寿园",
                "highlight": "中部偏北的安静园林，能看到闽南老建筑和鼓浪屿老别墅氛围。",
                "tip": "适合不想挤龙头路的人慢逛，路上坡下坡多。",
            },
            {
                "name": "中国电影音乐馆",
                "highlight": "靠近三丘田码头，有老电影设备和音乐主题体验，适合电影音乐爱好者。",
                "tip": "从三丘田码头上岛或离岛时顺路安排最自然。",
            },
        ]

    @staticmethod
    def _destination_route_advice(required_focus: str, variant_profile: dict | None = None) -> list[str]:
        if "鼓浪屿" not in required_focus:
            return []
        advice = [
            "从三丘田码头上岛：三丘田码头 → 中国电影音乐馆 → 长寿园 → 龙头路/中心区 → 港仔后沙滩/日光岩/菽庄花园 → 皓月园。",
            "从内厝澳码头上岛：内厝澳码头 → 港仔后沙滩/日光岩 → 中心区 → 长寿园 → 中国电影音乐馆 → 皓月园。",
            "不要按中部、西南、东南、西北、北端来回跳点，鼓浪屿全靠步行，折返会很费体力。",
        ]
        if isinstance(variant_profile, dict) and variant_profile.get("name") == "省钱版":
            advice.insert(0, "省钱版交通策略：厦门市区优先地铁/公交到码头，岛上全程步行，少打车。")
        elif isinstance(variant_profile, dict) and variant_profile.get("name") == "舒适版":
            advice.insert(0, "舒适版交通策略：市区段减少换乘，码头和住宿尽量靠近，岛上只保留不折返路线。")
        elif isinstance(variant_profile, dict) and variant_profile.get("name") == "深度游版":
            advice.insert(0, "深度游版交通策略：允许多走一点，把小众园林、博物馆和海边点串成完整步行线。")
        return advice

    @staticmethod
    def _derive_dates(start_date: str, duration: int) -> list[str]:
        if not start_date:
            return [f"Day {i}" for i in range(1, duration + 1)]
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            return [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(duration)]
        except ValueError:
            return [f"Day {i}" for i in range(1, duration + 1)]
