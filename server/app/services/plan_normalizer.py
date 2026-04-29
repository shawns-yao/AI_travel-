from __future__ import annotations

from typing import Any


def normalize_daily_plans(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            continue

        day = dict(item)
        day["day"] = int(day.get("day") or index)
        day["date"] = str(day.get("date") or "")
        day["activities"] = day.get("activities") if isinstance(day.get("activities"), list) else []

        meals = day.get("meals") if isinstance(day.get("meals"), list) else []
        dinner = next(
            (
                meal
                for meal in meals
                if isinstance(meal, dict)
                and (meal.get("type") == "dinner" or "晚" in str(meal.get("time", "")))
            ),
            meals[0] if meals and isinstance(meals[0], dict) else None,
        )

        if isinstance(dinner, dict):
            dinner = dict(dinner)
            dinner["type"] = "dinner"
            dinner["time"] = "晚上"
            day["meals"] = [dinner]
        else:
            day["meals"] = []

        day["notes"] = str(day.get("notes") or "")
        normalized.append(day)

    return normalized
