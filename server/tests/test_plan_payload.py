from types import SimpleNamespace
from uuid import uuid4

from app.api.plans import _plan_payload
from app.services.run_service import _normalize_daily_plans


def test_normalize_daily_plans_keeps_only_one_dinner():
    result = _normalize_daily_plans([
        {
            "day": 1,
            "date": "2026-05-01",
            "activities": [],
            "meals": [
                {"id": "m1", "name": "午餐", "type": "lunch", "time": "中午"},
                {"id": "m2", "name": "晚餐", "type": "dinner", "time": "18:30"},
                {"id": "m3", "name": "夜宵", "type": "snack", "time": "晚上"},
            ],
        }
    ])

    assert result[0]["meals"] == [{"id": "m2", "name": "晚餐", "type": "dinner", "time": "晚上"}]


def test_plan_payload_normalizes_old_records_to_dinner_only():
    row = SimpleNamespace(
        id=uuid4(),
        destination="杭州",
        duration=3,
        start_date="2026-05-01",
        budget=4000,
        preferences=[],
        daily_plans=[
            {
                "day": 1,
                "date": "2026-05-01",
                "activities": [],
                "meals": [
                    {"id": "m1", "name": "早餐", "type": "breakfast", "time": "早上"},
                    {"id": "m2", "name": "晚餐", "type": "dinner", "time": "晚间"},
                ],
                "notes": "",
            }
        ],
        map_data=None,
        weather_data=None,
        budget_breakdown=None,
        critic_report=None,
        memory_context=None,
        status="generated",
        created_at=None,
        updated_at=None,
    )

    payload = _plan_payload(row)

    assert len(payload["daily_plans"][0]["meals"]) == 1
    assert payload["daily_plans"][0]["meals"][0]["type"] == "dinner"
    assert payload["daily_plans"][0]["meals"][0]["time"] == "晚上"
