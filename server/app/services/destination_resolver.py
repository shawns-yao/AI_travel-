from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DestinationResolution:
    raw: str
    display_name: str
    weather_city: str
    search_city: str
    must_include: str


_DESTINATION_ALIASES: dict[str, DestinationResolution] = {
    "夏门": DestinationResolution(
        raw="夏门",
        display_name="厦门",
        weather_city="厦门",
        search_city="厦门",
        must_include="厦门",
    ),
    "鼓浪屿": DestinationResolution(
        raw="鼓浪屿",
        display_name="鼓浪屿（厦门）",
        weather_city="厦门",
        search_city="厦门",
        must_include="鼓浪屿",
    ),
}


def resolve_destination(value: str | None) -> DestinationResolution:
    raw = str(value or "").strip() or "目的地"
    normalized = raw.replace("（", "").replace("）", "").replace("(", "").replace(")", "")
    for key, resolution in _DESTINATION_ALIASES.items():
        if key in normalized:
            return DestinationResolution(
                raw=raw,
                display_name=resolution.display_name,
                weather_city=resolution.weather_city,
                search_city=resolution.search_city,
                must_include=resolution.must_include,
            )
    return DestinationResolution(
        raw=raw,
        display_name=raw,
        weather_city=raw,
        search_city=raw,
        must_include=raw,
    )
