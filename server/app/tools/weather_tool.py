"""Tools: QWeather API integration for location ID lookup and weather forecast."""

from app.core.config import settings
from app.core.tool import BaseTool
from app.core.logging import get_logger
from app.services.information_cache import InformationCache

logger = get_logger("weather_tool")


def _qweather_headers() -> dict[str, str]:
    return {"X-QW-Api-Key": settings.qweather_api_key}


class LocationIdTool(BaseTool):
    name = "get_location_id"
    description = "Convert a city/location name to a QWeather LocationId needed for weather queries."

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "description": "City or location name, e.g. 'Beijing', 'Chengdu'",
                },
            },
            "required": ["address"],
        }

    async def execute(self, address: str = "", **kwargs) -> str:
        import httpx

        cache = InformationCache("qweather_location", ttl_seconds=30 * 24 * 3600)
        cached = await cache.get(address.lower())
        if cached and not (settings.qweather_api_key and cached.get("fallback")):
            return cached["location_id"]

        if not settings.qweather_api_key:
            logger.warning("weather.no_api_key", tool="get_location_id")
            location_id = self._mock_location_id(address)
            await cache.set(address.lower(), {"location_id": location_id})
            return location_id

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{settings.qweather_geo_base_url.rstrip('/')}/v2/city/lookup",
                    params={"location": address},
                    headers=_qweather_headers(),
                )
                data = resp.json()
                if data.get("code") == "200" and data.get("location"):
                    location_id = data["location"][0]["id"]
                    await cache.set(address.lower(), {"location_id": location_id, "raw": data["location"][0]})
                    return location_id
        except Exception as e:
            logger.error("weather.location_lookup_failed", error=str(e))

        location_id = self._mock_location_id(address)
        await cache.set(address.lower(), {"location_id": location_id, "fallback": True})
        return location_id

    @staticmethod
    def _mock_location_id(address: str) -> str:
        """Realistic mock LocationIds for common destinations."""
        mock_ids = {
            "北京": "101010100",
            "beijing": "101010100",
            "上海": "101020100",
            "shanghai": "101020100",
            "杭州": "101210101",
            "hangzhou": "101210101",
            "成都": "101270101",
            "chengdu": "101270101",
            "重庆": "101040100",
            "chongqing": "101040100",
            "青岛": "101120201",
            "qingdao": "101120201",
            "西安": "101110101",
            "xian": "101110101",
            "南京": "101190101",
            "nanjing": "101190101",
            "广州": "101280101",
            "guangzhou": "101280101",
            "深圳": "101280601",
            "shenzhen": "101280601",
            "九寨沟": "101271906",
            "jiuzhaigou": "101271906",
        }
        return mock_ids.get(address.lower(), "101010100")


class WeatherTool(BaseTool):
    name = "get_weather_by_location_id"
    description = "Get 7-day weather forecast for a LocationId. Returns daily weather including condition, high/low temp, humidity."

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "locationId": {
                    "type": "string",
                    "description": "QWeather LocationId from get_location_id",
                },
                "dates": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of dates in YYYY-MM-DD format to get weather for",
                },
            },
            "required": ["locationId", "dates"],
        }

    async def execute(self, locationId: str = "", dates: list | None = None, **kwargs) -> list[dict]:
        import httpx

        if dates is None:
            dates = []
        cache_key = f"{locationId}:{','.join(dates)}"
        cache = InformationCache("qweather_forecast", ttl_seconds=6 * 3600)
        cached = await cache.get(cache_key)
        if cached and not (settings.qweather_api_key and cached.get("fallback")):
            return cached["forecast"]

        if not settings.qweather_api_key:
            logger.warning("weather.no_api_key", tool="get_weather")
            forecast = self._mock_weather(dates)
            await cache.set(cache_key, {"forecast": forecast, "fallback": True})
            return forecast

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{settings.qweather_weather_base_url.rstrip('/')}/v7/weather/7d",
                    params={"location": locationId},
                    headers=_qweather_headers(),
                )
                data = resp.json()
                if data.get("code") == "200" and data.get("daily"):
                    forecast = self._parse_weather(data["daily"], dates)
                    await cache.set(cache_key, {"forecast": forecast})
                    return forecast
        except Exception as e:
            logger.error("weather.fetch_failed", error=str(e))

        forecast = self._mock_weather(dates)
        await cache.set(cache_key, {"forecast": forecast, "fallback": True})
        return forecast

    def _parse_weather(self, daily: list[dict], dates: list[str]) -> list[dict]:
        result = []
        fc_dates = {d["fxDate"]: d for d in daily}
        for date in dates:
            if date in fc_dates:
                d = fc_dates[date]
                result.append({
                    "date": date,
                    "condition": d.get("textDay", "unknown"),
                    "temp_high": int(d.get("tempMax", 0)),
                    "temp_low": int(d.get("tempMin", 0)),
                    "humidity": int(d.get("humidity", 60)),
                    "recommendation": self._recommendation(d.get("textDay", "unknown")),
                    "risk_level": self._risk_level(d.get("textDay", "unknown")),
                    "source": "qweather",
                })
            else:
                result.append({
                    "date": date,
                    "condition": "no_data",
                    "temp_high": 0,
                    "temp_low": 0,
                    "humidity": 0,
                    "recommendation": "和风 7 日天气未覆盖该日期，规划时保留室内备选。",
                    "risk_level": "LOW",
                    "source": "qweather",
                })
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

    @staticmethod
    def _mock_weather(dates: list[str]) -> list[dict]:
        """Seasonal mock weather for demo without API key."""
        import random

        results = []
        for date_str in dates:
            try:
                month = int(date_str.split("-")[1])
            except (IndexError, ValueError):
                month = 6

            if month in (12, 1, 2):  # Winter
                results.append({
                    "date": date_str,
                    "condition": random.choice(["sunny", "cloudy", "snow"]),
                    "temp_high": random.randint(0, 8),
                    "temp_low": random.randint(-8, 0),
                    "humidity": random.randint(30, 60),
                })
            elif month in (3, 4, 5):  # Spring
                results.append({
                    "date": date_str,
                    "condition": random.choice(["sunny", "cloudy", "rain"]),
                    "temp_high": random.randint(15, 25),
                    "temp_low": random.randint(5, 15),
                    "humidity": random.randint(40, 70),
                })
            elif month in (6, 7, 8):  # Summer
                results.append({
                    "date": date_str,
                    "condition": random.choice(["sunny", "cloudy", "rain", "thunderstorm"]),
                    "temp_high": random.randint(28, 36),
                    "temp_low": random.randint(20, 28),
                    "humidity": random.randint(60, 90),
                })
            else:  # Autumn
                results.append({
                    "date": date_str,
                    "condition": random.choice(["sunny", "cloudy"]),
                    "temp_high": random.randint(15, 25),
                    "temp_low": random.randint(5, 15),
                    "humidity": random.randint(40, 65),
                })
        for item in results:
            condition = item.get("condition", "unknown")
            item["recommendation"] = WeatherTool._recommendation(condition)
            item["risk_level"] = WeatherTool._risk_level(condition)
            item["source"] = "fallback"
        return results
