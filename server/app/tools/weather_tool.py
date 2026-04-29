"""Tools: QWeather API integration for location ID lookup and weather forecast."""

from app.core.config import settings
from app.core.tool import BaseTool
from app.core.logging import get_logger

logger = get_logger("weather_tool")


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

        if not settings.qweather_api_key:
            logger.warning("weather.no_api_key", tool="get_location_id")
            return self._mock_location_id(address)

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://geoapi.qweather.com/v2/city/lookup",
                    params={"location": address, "key": settings.qweather_api_key},
                )
                data = resp.json()
                if data.get("code") == "200" and data.get("location"):
                    return data["location"][0]["id"]
        except Exception as e:
            logger.error("weather.location_lookup_failed", error=str(e))

        return self._mock_location_id(address)

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

        if not settings.qweather_api_key:
            logger.warning("weather.no_api_key", tool="get_weather")
            return self._mock_weather(dates)

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://devapi.qweather.com/v7/weather/7d",
                    params={"location": locationId, "key": settings.qweather_api_key},
                )
                data = resp.json()
                if data.get("code") == "200" and data.get("daily"):
                    return self._parse_weather(data["daily"], dates)
        except Exception as e:
            logger.error("weather.fetch_failed", error=str(e))

        return self._mock_weather(dates)

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
                })
            else:
                result.append({
                    "date": date,
                    "condition": "no_data",
                    "temp_high": 0,
                    "temp_low": 0,
                    "humidity": 0,
                })
        return result

    @staticmethod
    def _mock_weather(dates: list[str]) -> list[dict]:
        """Seasonal mock weather for demo without API key."""
        import random
        from datetime import datetime

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
        return results
