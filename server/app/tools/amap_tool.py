from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.core.tool import BaseTool
from app.services.information_cache import InformationCache

logger = get_logger("amap_tool")


def _parse_location(value: str | None) -> dict[str, float] | None:
    if not value or "," not in value:
        return None
    try:
        lng, lat = value.split(",", 1)
        return {"lng": float(lng), "lat": float(lat)}
    except ValueError:
        return None


class AmapGeocodeTool(BaseTool):
    name = "amap_geocode"
    description = "Convert an address or city name to AMap coordinates."

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "address": {"type": "string", "description": "Address or destination name."},
                "city": {"type": "string", "description": "Optional city filter."},
            },
            "required": ["address"],
        }

    async def execute(self, address: str = "", city: str = "", **kwargs: Any) -> dict[str, Any]:
        normalized = f"{address.strip()}:{city.strip()}".lower()
        cache = InformationCache("amap_geocode", ttl_seconds=30 * 24 * 3600)
        cached = await cache.get(normalized)
        if cached and not (settings.amap_api_key and cached.get("source") == "fallback"):
            return cached

        if not settings.amap_api_key:
            result = self._fallback_geocode(address)
            await cache.set(normalized, result)
            return result

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{settings.amap_base_url.rstrip('/')}/v3/geocode/geo",
                    params={
                        "key": settings.amap_api_key,
                        "address": address,
                        "city": city or None,
                        "output": "json",
                    },
                )
                data = resp.json()
                if data.get("status") == "1" and data.get("geocodes"):
                    item = data["geocodes"][0]
                    result = {
                        "formatted_address": item.get("formatted_address") or address,
                        "province": item.get("province") or "",
                        "city": item.get("city") if isinstance(item.get("city"), str) else city,
                        "district": item.get("district") if isinstance(item.get("district"), str) else "",
                        "adcode": item.get("adcode") or "",
                        "location": _parse_location(item.get("location")) or self._fallback_geocode(address)["location"],
                        "source": "amap",
                    }
                    await cache.set(normalized, result)
                    return result
                logger.warning("amap.geocode_non_success", status=data.get("status"), info=data.get("info"))
        except Exception as e:
            logger.warning("amap.geocode_failed", error=str(e))

        result = self._fallback_geocode(address)
        await cache.set(normalized, result)
        return result

    @staticmethod
    def _fallback_geocode(address: str) -> dict[str, Any]:
        if "鼓浪屿" in address:
            return {
                "formatted_address": address or "鼓浪屿",
                "province": "福建省",
                "city": "厦门",
                "district": "思明区",
                "adcode": "",
                "location": {"lng": 118.0676, "lat": 24.4446},
                "source": "fallback",
            }

        presets = {
            "北京": {"lng": 116.4074, "lat": 39.9042},
            "上海": {"lng": 121.4737, "lat": 31.2304},
            "杭州": {"lng": 120.1551, "lat": 30.2741},
            "成都": {"lng": 104.0665, "lat": 30.5728},
            "重庆": {"lng": 106.5516, "lat": 29.5630},
            "西安": {"lng": 108.9398, "lat": 34.3416},
            "南京": {"lng": 118.7969, "lat": 32.0603},
            "广州": {"lng": 113.2644, "lat": 23.1291},
            "深圳": {"lng": 114.0579, "lat": 22.5431},
            "厦门": {"lng": 118.0894, "lat": 24.4798},
            "青岛": {"lng": 120.3826, "lat": 36.0671},
        }
        for key, location in presets.items():
            if key in address:
                return {
                    "formatted_address": address or key,
                    "province": "",
                    "city": key,
                    "district": "",
                    "adcode": "",
                    "location": location,
                    "source": "fallback",
                }
        return {
            "formatted_address": address or "北京",
            "province": "",
            "city": address or "北京",
            "district": "",
            "adcode": "",
            "location": presets["北京"],
            "source": "fallback",
        }


class AmapPOISearchTool(BaseTool):
    name = "amap_search_poi"
    description = "Search AMap POIs by keyword, city, and optional type."

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "keywords": {"type": "string", "description": "POI keyword, e.g. 景点, 火锅, 酒店."},
                "city": {"type": "string", "description": "City name."},
                "types": {"type": "string", "description": "Optional AMap type code or category."},
                "limit": {"type": "integer", "default": 8},
            },
            "required": ["keywords", "city"],
        }

    async def execute(
        self,
        keywords: str = "",
        city: str = "",
        types: str = "",
        limit: int = 8,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit or 8), 20))
        cache_key = f"{city}:{keywords}:{types}:{limit}".lower()
        cache = InformationCache("amap_poi_search", ttl_seconds=7 * 24 * 3600)
        cached = await cache.get(cache_key)
        if cached and not (
            settings.amap_api_key
            and (cached.get("fallback") or any(poi.get("source") == "fallback" for poi in cached.get("pois", [])))
        ):
            return cached["pois"]

        if not settings.amap_api_key:
            pois = self._fallback_pois(city, keywords, limit)
            await cache.set(cache_key, {"pois": pois, "fallback": True})
            return pois

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{settings.amap_base_url.rstrip('/')}/v3/place/text",
                    params={
                        "key": settings.amap_api_key,
                        "keywords": keywords,
                        "city": city,
                        "types": types or None,
                        "offset": limit,
                        "page": 1,
                        "extensions": "all",
                        "output": "json",
                    },
                )
                data = resp.json()
                if data.get("status") == "1":
                    pois = [self._normalize_poi(item) for item in data.get("pois", [])[:limit]]
                    await cache.set(cache_key, {"pois": pois})
                    return pois
                logger.warning("amap.poi_non_success", status=data.get("status"), info=data.get("info"))
        except Exception as e:
            logger.warning("amap.poi_failed", error=str(e))

        pois = self._fallback_pois(city, keywords, limit)
        await cache.set(cache_key, {"pois": pois, "fallback": True})
        return pois

    @staticmethod
    def _normalize_poi(item: dict[str, Any]) -> dict[str, Any]:
        location = _parse_location(item.get("location"))
        photos = item.get("photos") if isinstance(item.get("photos"), list) else []
        return {
            "id": item.get("id") or "",
            "name": item.get("name") or "",
            "type": item.get("type") or "",
            "typecode": item.get("typecode") or "",
            "address": item.get("address") if isinstance(item.get("address"), str) else "",
            "location": location,
            "distance": item.get("distance") or "",
            "rating": str(item.get("biz_ext", {}).get("rating", "")) if isinstance(item.get("biz_ext"), dict) else "",
            "cost": str(item.get("biz_ext", {}).get("cost", "")) if isinstance(item.get("biz_ext"), dict) else "",
            "photo": photos[0].get("url") if photos and isinstance(photos[0], dict) else "",
            "source": "amap",
        }

    @staticmethod
    def _fallback_pois(city: str, keywords: str, limit: int) -> list[dict[str, Any]]:
        keyword = keywords or "景点"
        label = "鼓浪屿" if "鼓浪屿" in keyword or "鼓浪屿" in city else city
        center = AmapGeocodeTool._fallback_geocode(label or city)["location"]
        names = {
            "美食": ["高评分本地菜餐厅", "老字号主题餐厅", "景区周边品质餐厅", "城市地标餐厅"],
            "餐饮": ["高评分本地菜餐厅", "老字号主题餐厅", "景区周边品质餐厅", "城市地标餐厅"],
            "餐厅": ["高评分本地菜餐厅", "老字号主题餐厅", "景区周边品质餐厅", "城市地标餐厅"],
            "酒店": ["市中心舒适酒店", "交通便利酒店", "景区周边酒店", "高评分民宿"],
            "景点": ["城市核心景区", "历史文化街区", "城市公园", "博物馆"],
        }
        if label == "鼓浪屿":
            names.update({
                "美食": ["高评分闽南菜餐厅", "海景餐厅", "老字号小吃集合店", "咖啡甜品店"],
                "餐饮": ["高评分闽南菜餐厅", "海景餐厅", "老字号小吃集合店", "咖啡甜品店"],
                "餐厅": ["高评分闽南菜餐厅", "海景餐厅", "老字号小吃集合店", "咖啡甜品店"],
                "酒店": ["岛上精品酒店", "码头周边酒店", "海景民宿", "老别墅酒店"],
                "景点": ["日光岩", "菽庄花园", "皓月园", "风琴博物馆"],
            })
            exact_spots = ["鼓浪屿风景名胜区", "港仔后沙滩", "鼓浪屿沙滩", "皓月园", "长寿园", "中国电影音乐馆"]
            matched_spot = next((spot for spot in exact_spots if spot in keyword), "")
            if matched_spot:
                selected = [matched_spot]
            else:
                selected = next((v for k, v in names.items() if k in keyword), names["景点"])
        else:
            selected = next((v for k, v in names.items() if k in keyword), names["景点"])
        pois: list[dict[str, Any]] = []
        for index, name in enumerate(selected[:limit], start=1):
            pois.append(
                {
                    "id": f"fallback_{index}",
                    "name": f"{label}{name}" if label and label not in name else name,
                    "type": keyword,
                    "typecode": "",
                    "address": city,
                    "location": {
                        "lng": round(center["lng"] + index * 0.006, 6),
                        "lat": round(center["lat"] + index * 0.004, 6),
                    },
                    "distance": "",
                    "rating": "4.5",
                    "cost": "",
                    "photo": "",
                    "source": "fallback",
                }
            )
        return pois


class AmapRoutePlanningTool(BaseTool):
    name = "amap_route_planning"
    description = "Plan a route between two AMap coordinates using walking, driving, or bicycling mode."

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "origin": {"type": "string", "description": "Origin coordinate: lng,lat."},
                "destination": {"type": "string", "description": "Destination coordinate: lng,lat."},
                "mode": {"type": "string", "enum": ["walking", "driving", "bicycling"], "default": "walking"},
                "city": {"type": "string", "description": "Optional city name."},
            },
            "required": ["origin", "destination"],
        }

    async def execute(
        self,
        origin: str = "",
        destination: str = "",
        mode: str = "walking",
        city: str = "",
        **kwargs: Any,
    ) -> dict[str, Any]:
        mode = mode if mode in {"walking", "driving", "bicycling"} else "walking"
        cache_key = f"{mode}:{origin}:{destination}:{city}".lower()
        cache = InformationCache("amap_route", ttl_seconds=24 * 3600)
        cached = await cache.get(cache_key)
        if cached and not (settings.amap_api_key and cached.get("source") == "fallback"):
            return cached

        if not settings.amap_api_key:
            result = self._fallback_route(origin, destination, mode)
            await cache.set(cache_key, result)
            return result

        endpoint = {
            "walking": "/v3/direction/walking",
            "driving": "/v3/direction/driving",
            "bicycling": "/v4/direction/bicycling",
        }[mode]

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{settings.amap_base_url.rstrip('/')}{endpoint}",
                    params={
                        "key": settings.amap_api_key,
                        "origin": origin,
                        "destination": destination,
                        "city": city or None,
                        "output": "json",
                    },
                )
                data = resp.json()
                if data.get("status") == "1" and data.get("route"):
                    result = self._normalize_route(data["route"], mode)
                    await cache.set(cache_key, result)
                    return result
                logger.warning("amap.route_non_success", status=data.get("status"), info=data.get("info"))
        except Exception as e:
            logger.warning("amap.route_failed", error=str(e))

        result = self._fallback_route(origin, destination, mode)
        await cache.set(cache_key, result)
        return result

    @staticmethod
    def _normalize_route(route: dict[str, Any], mode: str) -> dict[str, Any]:
        paths = route.get("paths") or []
        first = paths[0] if paths else {}
        steps = first.get("steps") if isinstance(first.get("steps"), list) else []
        distance_m = int(float(first.get("distance") or 0))
        duration_s = int(float(first.get("duration") or 0))
        return {
            "mode": mode,
            "distance_m": distance_m,
            "duration_min": round(duration_s / 60),
            "strategy": first.get("strategy") or "",
            "taxi_cost": route.get("taxi_cost") or "",
            "steps": [
                {
                    "instruction": step.get("instruction") or "",
                    "road": step.get("road") or "",
                    "distance_m": int(float(step.get("distance") or 0)),
                    "duration_min": round(int(float(step.get("duration") or 0)) / 60),
                    "polyline": step.get("polyline") or "",
                }
                for step in steps[:12]
                if isinstance(step, dict)
            ],
            "source": "amap",
        }

    @staticmethod
    def _fallback_route(origin: str, destination: str, mode: str) -> dict[str, Any]:
        start = _parse_location(origin)
        end = _parse_location(destination)
        if start and end:
            approx_distance = int((((start["lng"] - end["lng"]) ** 2 + (start["lat"] - end["lat"]) ** 2) ** 0.5) * 100000)
        else:
            approx_distance = 1800
        speed_m_per_min = {"walking": 80, "bicycling": 220, "driving": 450}.get(mode, 80)
        return {
            "mode": mode,
            "distance_m": max(500, approx_distance),
            "duration_min": max(8, round(max(500, approx_distance) / speed_m_per_min)),
            "strategy": "fallback",
            "taxi_cost": "",
            "steps": [],
            "source": "fallback",
        }
