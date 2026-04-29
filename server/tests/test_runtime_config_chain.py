import pytest

from app.agents.weather_agent import WeatherAgent
from app.core.config import settings
from app.core.llm import _normalize_messages, _normalize_tools
from app.services.run_service import _apply_runtime_api_settings


def test_apply_runtime_api_settings_updates_agent_runtime(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "openai-compatible")
    monkeypatch.setattr(settings, "dashscope_api_key", "")
    monkeypatch.setattr(settings, "llm_base_url", "https://old.example/v1")
    monkeypatch.setattr(settings, "chat_model", "old-model")
    monkeypatch.setattr(settings, "qweather_api_key", "")
    monkeypatch.setattr(settings, "qweather_weather_base_url", "https://old-weather.example")
    monkeypatch.setattr(settings, "qweather_geo_base_url", "https://old-geo.example")
    monkeypatch.setattr(settings, "amap_api_key", "")

    _apply_runtime_api_settings({
        "llm_provider": "openai-compatible",
        "llm_api_key": "llm-key",
        "llm_base_url": "https://llm.example/v1",
        "llm_model": "deepseek-chat",
        "qweather_api_key": "weather-key",
        "qweather_host": "devapi.qweather.com",
        "amap_service_key": "amap-service-key",
    })

    assert settings.llm_provider == "openai-compatible"
    assert settings.dashscope_api_key == "llm-key"
    assert settings.llm_base_url == "https://llm.example/v1"
    assert settings.chat_model == "deepseek-chat"
    assert settings.qweather_api_key == "weather-key"
    assert settings.qweather_weather_base_url == "https://devapi.qweather.com"
    assert settings.qweather_geo_base_url == "https://devapi.qweather.com/geo"
    assert settings.amap_api_key == "amap-service-key"


def test_openai_tool_schema_is_normalized():
    normalized = _normalize_tools([{
        "name": "get_weather_by_location_id",
        "description": "Get weather",
        "parameters": {"type": "object", "properties": {}},
    }])

    assert normalized == [{
        "type": "function",
        "function": {
            "name": "get_weather_by_location_id",
            "description": "Get weather",
            "parameters": {"type": "object", "properties": {}},
        },
    }]


def test_openai_tool_call_messages_are_normalized():
    normalized = _normalize_messages([{
        "role": "assistant",
        "content": None,
        "tool_calls": [{
            "id": "call_1",
            "name": "get_current_date",
            "arguments": "{}",
        }],
    }])

    assert normalized[0]["tool_calls"] == [{
        "id": "call_1",
        "type": "function",
        "function": {
            "name": "get_current_date",
            "arguments": "{}",
        },
    }]


@pytest.mark.asyncio
async def test_weather_agent_calls_tools_directly(monkeypatch):
    calls: list[tuple[str, dict]] = []

    class FakeLocationTool:
        async def execute(self, **kwargs):
            calls.append(("get_location_id", kwargs))
            return "101270101"

    class FakeWeatherTool:
        async def execute(self, **kwargs):
            calls.append(("get_weather_by_location_id", kwargs))
            return [{
                "date": "2026-05-01",
                "condition": "晴",
                "temp_high": 25,
                "temp_low": 16,
                "humidity": 50,
                "recommendation": "适合户外景点，注意防晒和补水。",
                "risk_level": "LOW",
                "source": "qweather",
            }]

    def fake_get(name):
        return {
            "get_location_id": FakeLocationTool(),
            "get_weather_by_location_id": FakeWeatherTool(),
        }[name]

    monkeypatch.setattr("app.agents.weather_agent.tool_registry.get", fake_get)

    result = await WeatherAgent().execute({
        "run_id": "test-run",
        "IntentAgent": {
            "destination": "成都",
            "all_dates": "2026-05-01",
        },
    })

    assert result.success is True
    assert calls == [
        ("get_location_id", {"address": "成都"}),
        ("get_weather_by_location_id", {"locationId": "101270101", "dates": ["2026-05-01"]}),
    ]
    assert result.output["forecast"][0]["source"] == "qweather"
