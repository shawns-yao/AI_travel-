from __future__ import annotations

from enum import Enum
from typing import Any
from urllib.parse import unquote

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field


router = APIRouter(prefix="/api/config", tags=["config"])


class LLMProvider(str, Enum):
    openai_compatible = "openai-compatible"
    anthropic = "anthropic"


class ApiSettingsPayload(BaseModel):
    llm_provider: LLMProvider = Field(default=LLMProvider.openai_compatible)
    llm_base_url: str = ""
    llm_model: str = ""
    llm_api_key: str = ""
    qweather_api_key: str = ""
    qweather_host: str = "devapi.qweather.com"
    qweather_location: str = "杭州"
    qweather_adm: str = ""
    amap_api_key: str = ""
    amap_service_key: str = ""
    amap_js_url: str = "https://webapi.amap.com/maps?v=2.0&key={key}"
    backend_base_url: str = ""


class ConfigCheck(BaseModel):
    name: str
    ok: bool
    message: str


class ConfigTestResponse(BaseModel):
    status: str
    checks: list[ConfigCheck]
    models: list[str] = []


class ModelListResponse(BaseModel):
    models: list[str]


def _headers(payload: ApiSettingsPayload) -> dict[str, str]:
    if payload.llm_provider == LLMProvider.anthropic:
        return {
            "x-api-key": payload.llm_api_key,
            "anthropic-version": "2023-06-01",
        }
    return {"Authorization": f"Bearer {payload.llm_api_key}"}


def _http_url(value: str, fallback: str) -> str:
    raw = _clean_text(value or fallback).rstrip("/")
    if raw.startswith(("http://", "https://")):
        return raw
    return f"https://{raw}"


def _clean_text(value: str) -> str:
    return "".join(ch for ch in value.strip() if ch.isprintable())


def _clean_url(value: str) -> str:
    raw = _clean_text(unquote(value or ""))
    if "src=" in raw:
        quote = '"' if '"' in raw.split("src=", 1)[1][:1] else "'"
        tail = raw.split("src=", 1)[1].lstrip("\"'")
        raw = tail.split(quote, 1)[0] if quote in tail else tail.split(">", 1)[0]
    return raw.replace("您的密钥", "{key}").replace("YOUR_KEY", "{key}").strip("<>\"'")


async def _fetch_models(payload: ApiSettingsPayload) -> list[str]:
    if not payload.llm_api_key or not payload.llm_base_url:
        return []

    url = f"{payload.llm_base_url.rstrip('/')}/models"
    async with httpx.AsyncClient(timeout=12) as client:
        response = await client.get(url, headers=_headers(payload))
        response.raise_for_status()
        data: dict[str, Any] = response.json()

    raw = data.get("data")
    if not isinstance(raw, list):
        return []
    return [item.get("id") for item in raw if isinstance(item, dict) and item.get("id")][:30]


async def _test_qweather(payload: ApiSettingsPayload) -> ConfigCheck:
    if not payload.qweather_api_key:
        return ConfigCheck(name="和风天气", ok=False, message="缺少 API Key")
    location = _clean_text(payload.qweather_location or "杭州")
    adm = _clean_text(payload.qweather_adm or "")
    if not location:
        return ConfigCheck(name="和风天气", ok=False, message="请填写查询地区")
    try:
        base_url = _http_url(payload.qweather_host, "devapi.qweather.com")
        headers = {"X-QW-Api-Key": payload.qweather_api_key}
        geo_params = {"location": location}
        if adm:
            geo_params["adm"] = adm
        async with httpx.AsyncClient(timeout=10) as client:
            geo_response = await client.get(
                f"{base_url}/geo/v2/city/lookup",
                params=geo_params,
                headers=headers,
            )
            geo_text = geo_response.text
            try:
                geo_data = geo_response.json()
            except ValueError:
                return ConfigCheck(name="和风天气", ok=False, message=f"响应非 JSON: {geo_text[:80]}")

            if geo_data.get("code") != "200" or not geo_data.get("location"):
                message = str(geo_data.get("code") or geo_data.get("message") or "城市查询失败")
                if geo_data.get("code") == "404":
                    message = f"未找到 {adm + ' ' if adm else ''}{location}"
                return ConfigCheck(
                    name="和风天气",
                    ok=False,
                    message=message,
                )

            city = geo_data["location"][0]
            location_id = city["id"]
            weather_response = await client.get(
                f"{base_url}/v7/weather/now",
                params={"location": location_id},
                headers=headers,
            )
            weather_text = weather_response.text
            try:
                weather_data = weather_response.json()
            except ValueError:
                return ConfigCheck(name="和风天气", ok=False, message=f"响应非 JSON: {weather_text[:80]}")

        if weather_data.get("code") == "200" and weather_data.get("now"):
            now = weather_data["now"]
            city_name = f"{city.get('adm1', '')} {city.get('adm2', '')} {city.get('name', '')}".strip()
            return ConfigCheck(name="和风天气", ok=True, message=f"{city_name} {now.get('text', '')} {now.get('temp', '')}°C")
        return ConfigCheck(name="和风天气", ok=False, message=str(weather_data.get("code") or weather_data.get("message") or "天气查询失败"))
    except Exception as exc:
        return ConfigCheck(name="和风天气", ok=False, message=str(exc))


async def _test_amap(payload: ApiSettingsPayload) -> ConfigCheck:
    if not payload.amap_api_key:
        return ConfigCheck(name="高德地图", ok=False, message="缺少 API Key")
    try:
        key = _clean_text(payload.amap_api_key)
        url_template = _clean_url(payload.amap_js_url or "https://webapi.amap.com/maps?v=2.0&key={key}")
        url = url_template.replace("{key}", key)
        if "{key}" not in url_template and "key=" not in url:
            joiner = "&" if "?" in url else "?"
            url = f"{url}{joiner}key={key}"
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url)
            body = response.text[:1000]
        if response.status_code >= 400:
            return ConfigCheck(name="高德地图", ok=False, message=f"HTTP {response.status_code}")
        error_markers = ["INVALID_USER_KEY", "INVALID_USER_SCODE", "USERKEY_PLAT_NOMATCH", "SERVICE_NOT_AVAILABLE"]
        marker = next((item for item in error_markers if item in body), "")
        if marker:
            return ConfigCheck(name="高德地图", ok=False, message=marker)
        return ConfigCheck(name="高德地图", ok=True, message="JS API 可加载")
    except Exception as exc:
        return ConfigCheck(name="高德地图", ok=False, message=str(exc))


async def _test_amap_service(payload: ApiSettingsPayload) -> ConfigCheck:
    key = _clean_text(payload.amap_service_key or payload.amap_api_key)
    if not key:
        return ConfigCheck(name="高德服务", ok=False, message="缺少 Web 服务 Key")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                "https://restapi.amap.com/v3/place/text",
                params={"key": key, "keywords": "西湖", "city": "杭州", "offset": 1, "page": 1, "output": "json"},
            )
            data = response.json()
        if data.get("status") == "1":
            return ConfigCheck(name="高德服务", ok=True, message=f"POI 可用，返回 {data.get('count', '0')} 条")
        return ConfigCheck(name="高德服务", ok=False, message=str(data.get("info") or "不可用"))
    except Exception as exc:
        return ConfigCheck(name="高德服务", ok=False, message=str(exc))


@router.post("/models", response_model=ModelListResponse)
async def list_models(payload: ApiSettingsPayload) -> ModelListResponse:
    return ModelListResponse(models=await _fetch_models(payload))


@router.post("/test", response_model=ConfigTestResponse)
async def test_config(payload: ApiSettingsPayload) -> ConfigTestResponse:
    checks = [ConfigCheck(name="FastAPI", ok=True, message="可用")]

    try:
        models = await _fetch_models(payload)
        checks.append(
            ConfigCheck(
                name="LLM",
                ok=bool(models),
                message=f"已获取 {len(models)} 个模型" if models else "未返回模型或缺少 Key",
            )
        )
    except Exception as exc:
        models = []
        checks.append(ConfigCheck(name="LLM", ok=False, message=str(exc)))

    checks.append(await _test_qweather(payload))
    checks.append(await _test_amap(payload))
    checks.append(await _test_amap_service(payload))
    status = "ok" if all(item.ok for item in checks) else "partial"
    return ConfigTestResponse(status=status, checks=checks, models=models[:12])
