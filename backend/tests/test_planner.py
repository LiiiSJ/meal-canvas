"""每周膳食计划存储与 API 测试。

计划库始终指向 tmp_path，绝不写入 data/build 下的任何正式数据库。
日期全部使用 YYYY-MM-DD，测试覆盖周一/周日边界与跨年周。
"""
from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

WEEK_START = "2026-10-26"  # 周一
WEEK_DATES = [
    "2026-10-26",
    "2026-10-27",
    "2026-10-28",
    "2026-10-29",
    "2026-10-30",
    "2026-10-31",
    "2026-11-01",
]


@pytest.fixture()
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("MEAL_CANVAS_PLANNER_DB_PATH", str(tmp_path / "planner.sqlite"))
    from backend.app.api import main as main_mod

    return TestClient(main_mod.app), tmp_path / "planner.sqlite"


def _item(food_key: str = "1001", grams: float = 100, scope: str = "default") -> dict:
    return {
        "food_key": food_key,
        "library_scope": scope,
        "amount_g": grams,
        "sort_order": 0,
        "name_snapshot": f"食品 {food_key}",
    }


def _meal(
    meal_type: str,
    items: list[dict] | None = None,
    *,
    sort_order: int = 0,
) -> dict:
    return {
        "meal_type": meal_type,
        "meal_name": None,
        "sort_order": sort_order,
        "notes": None,
        "items": items or [],
    }


def _week_payload(*, include_empty: bool = False) -> dict:
    days = []
    for day in WEEK_DATES:
        meals = [
            _meal("breakfast", [_item("1001", 100)]),
            _meal("lunch", [_item("1002", 150)]),
            _meal("dinner", [_item("1003", 120)]),
        ]
        if include_empty:
            meals.append(_meal("snack"))
        days.append({"date": day, "meals": meals})
        # 每天使用不同的 sort_order 组合，确认排序字段独立保存
        for order, meal in enumerate(meals):
            meal["sort_order"] = order
    return {"days": days}


def _find_day(plan: dict, day: str) -> dict:
    for entry in plan["days"]:
        if entry["date"] == day:
            return entry
    raise AssertionError(f"响应缺少日期 {day}")


def _find_meal(plan: dict, day: str, meal_type: str) -> dict:
    for meal in _find_day(plan, day)["meals"]:
        if meal["meal_type"] == meal_type:
            return meal
    raise AssertionError(f"{day} 缺少 {meal_type}")


def test_get_empty_week_returns_seven_days(api):
    client, _ = api
    r = client.get(f"/api/planner/plans/{WEEK_START}")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["week_start"] == WEEK_START
    assert data["plan_id"] is None
    assert [day["date"] for day in data["days"]] == WEEK_DATES
    assert all(day["meals"] == [] for day in data["days"])


def test_week_start_must_be_monday(api):
    client, _ = api
    r = client.get("/api/planner/plans/2026-10-27")
    assert r.status_code == 400
    assert "周一" in r.json()["detail"]["message"]


def test_save_full_week_and_read_back(api):
    client, _ = api
    payload = _week_payload()
    r = client.put(f"/api/planner/plans/{WEEK_START}", json=payload)
    assert r.status_code == 200, r.text
    saved = r.json()
    assert saved["plan_id"] is not None
    assert len(saved["days"]) == 7
    for day in WEEK_DATES:
        meals = _find_day(saved, day)["meals"]
        assert [meal["meal_type"] for meal in meals] == ["breakfast", "lunch", "dinner"]
        assert len(meals[0]["items"]) == 1

    again = client.get(f"/api/planner/plans/{WEEK_START}")
    assert again.status_code == 200
    assert again.json()["plan_id"] == saved["plan_id"]
    assert again.json()["days"] == saved["days"]


def test_multiple_foods_in_one_meal(api):
    client, _ = api
    payload = {
        "days": [
            {
                "date": WEEK_START,
                "meals": [
                    _meal(
                        "breakfast",
                        [
                            _item("1001", 100),
                            _item("1002", 50),
                            _item("1003", 200),
                        ],
                    )
                ],
            }
        ]
    }
    r = client.put(f"/api/planner/plans/{WEEK_START}", json=payload)
    assert r.status_code == 200, r.text
    meal = _find_meal(r.json(), WEEK_START, "breakfast")
    assert [item["food_key"] for item in meal["items"]] == ["1001", "1002", "1003"]


def test_multiple_snacks_allowed(api):
    client, _ = api
    payload = {
        "days": [
            {
                "date": WEEK_START,
                "meals": [
                    _meal("snack", [_item("2001", 30)], sort_order=30),
                    _meal("snack", [_item("2002", 40)], sort_order=31),
                    _meal("snack", [_item("2003", 50)], sort_order=32),
                ],
            }
        ]
    }
    r = client.put(f"/api/planner/plans/{WEEK_START}", json=payload)
    assert r.status_code == 200, r.text
    snacks = [m for m in _find_day(r.json(), WEEK_START)["meals"] if m["meal_type"] == "snack"]
    assert len(snacks) == 3
    assert [snack["sort_order"] for snack in snacks] == [30, 31, 32]


def test_duplicate_main_meal_type_rejected(api):
    client, _ = api
    payload = {
        "days": [
            {
                "date": WEEK_START,
                "meals": [_meal("breakfast"), _meal("breakfast")],
            }
        ]
    }
    r = client.put(f"/api/planner/plans/{WEEK_START}", json=payload)
    assert r.status_code == 400
    assert "最多只能有一条" in r.json()["detail"]["message"]


def test_date_outside_week_rejected(api):
    client, _ = api
    payload = {"days": [{"date": "2026-11-02", "meals": [_meal("breakfast")]}]}
    r = client.put(f"/api/planner/plans/{WEEK_START}", json=payload)
    assert r.status_code == 400
    assert "不在本周范围内" in r.json()["detail"]["message"]


def test_boundary_dates_accepted(api):
    """周一与周日都是本周合法日期；不能因时区转换偏移一天。"""
    client, _ = api
    payload = {
        "days": [
            {"date": "2026-10-26", "meals": [_meal("breakfast", [_item("3001")])]},
            {"date": "2026-11-01", "meals": [_meal("dinner", [_item("3002")])]},
        ]
    }
    r = client.put(f"/api/planner/plans/{WEEK_START}", json=payload)
    assert r.status_code == 200, r.text
    plan = r.json()
    assert _find_meal(plan, "2026-10-26", "breakfast")["meal_date"] == "2026-10-26"
    assert _find_meal(plan, "2026-11-01", "dinner")["meal_date"] == "2026-11-01"


def test_update_item_grams(api):
    client, _ = api
    plan = client.put(f"/api/planner/plans/{WEEK_START}", json=_week_payload()).json()
    meal = _find_meal(plan, WEEK_START, "breakfast")
    item_id = meal["items"][0]["item_id"]
    r = client.put(
        f"/api/planner/meals/{meal['meal_id']}/items/{item_id}",
        json={"amount_g": 250},
    )
    assert r.status_code == 200, r.text
    updated = _find_meal(r.json(), WEEK_START, "breakfast")
    assert updated["items"][0]["amount_g"] == 250


def test_delete_item(api):
    client, _ = api
    plan = client.put(f"/api/planner/plans/{WEEK_START}", json=_week_payload()).json()
    meal = _find_meal(plan, WEEK_START, "lunch")
    item_id = meal["items"][0]["item_id"]
    r = client.delete(f"/api/planner/meals/{meal['meal_id']}/items/{item_id}")
    assert r.status_code == 200, r.text
    assert _find_meal(r.json(), WEEK_START, "lunch")["items"] == []


def test_delete_meal(api):
    client, _ = api
    plan = client.put(f"/api/planner/plans/{WEEK_START}", json=_week_payload()).json()
    meal_id = _find_meal(plan, WEEK_START, "dinner")["meal_id"]
    r = client.delete(f"/api/planner/meals/{meal_id}")
    assert r.status_code == 200, r.text
    remaining = [m["meal_type"] for m in _find_day(r.json(), WEEK_START)["meals"]]
    assert "dinner" not in remaining


def test_update_meal_replaces_items(api):
    client, _ = api
    plan = client.put(f"/api/planner/plans/{WEEK_START}", json=_week_payload()).json()
    meal_id = _find_meal(plan, WEEK_START, "lunch")["meal_id"]
    r = client.put(
        f"/api/planner/meals/{meal_id}",
        json={
            "meal_date": WEEK_START,
            "meal_type": "lunch",
            "meal_name": "工作日午餐",
            "sort_order": 1,
            "notes": "少油",
            "items": [_item("4001", 80), _item("4002", 90)],
        },
    )
    assert r.status_code == 200, r.text
    meal = _find_meal(r.json(), WEEK_START, "lunch")
    assert meal["meal_name"] == "工作日午餐"
    assert meal["notes"] == "少油"
    assert [item["food_key"] for item in meal["items"]] == ["4001", "4002"]


def test_create_meal(api):
    client, _ = api
    r = client.post(
        f"/api/planner/plans/{WEEK_START}/meals",
        json={"meal_date": WEEK_START, "meal_type": "snack", "sort_order": 30},
    )
    assert r.status_code == 200, r.text
    snacks = [m for m in _find_day(r.json(), WEEK_START)["meals"] if m["meal_type"] == "snack"]
    assert len(snacks) == 1


def test_add_entry_creates_meal_and_item(api):
    client, _ = api
    r = client.post(
        "/api/planner/entries",
        json={
            "meal_date": "2026-10-28",
            "meal_type": "lunch",
            "food_key": "5001",
            "library_scope": "branded",
            "amount_g": 120,
            "name_snapshot": "品牌食品",
        },
    )
    assert r.status_code == 200, r.text
    plan = r.json()
    assert plan["week_start"] == WEEK_START
    meal = _find_meal(plan, "2026-10-28", "lunch")
    assert meal["items"][0]["food_key"] == "5001"
    assert meal["items"][0]["library_scope"] == "branded"
    assert meal["items"][0]["name_snapshot"] == "品牌食品"


def _batch_payload(**overrides) -> dict:
    payload = {
        "meal_date": "2026-10-27",
        "meal_type": "breakfast",
        "items": [
            {"food_key": "6001", "library_scope": "default", "amount_g": 100,
             "name_snapshot": "全麦面包"},
            {"food_key": "6002", "library_scope": "default", "amount_g": 50,
             "name_snapshot": "鸡蛋"},
            {"food_key": "6003", "library_scope": "default", "amount_g": 200,
             "name_snapshot": "牛奶"},
        ],
    }
    payload.update(overrides)
    return payload


def test_batch_entries_creates_one_meal_with_all_items(api):
    client, _ = api
    r = client.post("/api/planner/entries/batch", json=_batch_payload())
    assert r.status_code == 200, r.text
    plan = r.json()
    assert plan["week_start"] == WEEK_START
    assert plan["plan_id"] is not None  # 自动创建当周计划
    day = _find_day(plan, "2026-10-27")
    breakfasts = [m for m in day["meals"] if m["meal_type"] == "breakfast"]
    assert len(breakfasts) == 1  # 多个食品只建一条餐次
    items = breakfasts[0]["items"]
    assert [item["food_key"] for item in items] == ["6001", "6002", "6003"]
    assert [item["amount_g"] for item in items] == [100, 50, 200]
    assert [item["name_snapshot"] for item in items] == ["全麦面包", "鸡蛋", "牛奶"]
    assert [item["sort_order"] for item in items] == [0, 1, 2]


def test_batch_entries_appends_to_existing_meal(api):
    client, _ = api
    client.put(
        f"/api/planner/plans/{WEEK_START}",
        json={"days": [{"date": "2026-10-27", "meals": [_meal("breakfast", [_item("6000", 80)])]}]},
    )
    r = client.post("/api/planner/entries/batch", json=_batch_payload())
    assert r.status_code == 200, r.text
    meal = _find_meal(r.json(), "2026-10-27", "breakfast")
    assert [item["food_key"] for item in meal["items"]] == ["6000", "6001", "6002", "6003"]


def test_batch_entries_snack_reuses_first_snack_meal(api):
    client, _ = api
    first = client.post(
        "/api/planner/entries/batch",
        json=_batch_payload(meal_type="snack", items=[_batch_payload()["items"][0]]),
    )
    assert first.status_code == 200, first.text
    second = client.post(
        "/api/planner/entries/batch",
        json=_batch_payload(meal_type="snack", items=[_batch_payload()["items"][1]]),
    )
    assert second.status_code == 200, second.text
    snacks = [m for m in _find_day(second.json(), "2026-10-27")["meals"] if m["meal_type"] == "snack"]
    assert len(snacks) == 1
    assert [item["food_key"] for item in snacks[0]["items"]] == ["6001", "6002"]


def test_batch_entries_rejects_empty_items(api):
    client, _ = api
    r = client.post("/api/planner/entries/batch", json=_batch_payload(items=[]))
    assert r.status_code == 422


def test_batch_entries_rejects_invalid_amount(api):
    client, _ = api
    bad = dict(_batch_payload()["items"][0], amount_g=0)
    r = client.post("/api/planner/entries/batch", json=_batch_payload(items=[bad]))
    assert r.status_code == 422


def test_batch_entries_rejects_bad_date(api):
    client, _ = api
    r = client.post("/api/planner/entries/batch", json=_batch_payload(meal_date="27-10-2026"))
    assert r.status_code == 400
    assert "YYYY-MM-DD" in r.json()["detail"]["message"]


def test_food_key_and_library_scope_preserved(api):
    client, _ = api
    payload = {
        "days": [
            {
                "date": WEEK_START,
                "meals": [_meal("breakfast", [
                    _item("1001", 100, "default"),
                    _item("1001", 80, "branded"),
                ])],
            }
        ]
    }
    r = client.put(f"/api/planner/plans/{WEEK_START}", json=payload)
    assert r.status_code == 200, r.text
    items = _find_meal(r.json(), WEEK_START, "breakfast")["items"]
    assert [(item["food_key"], item["library_scope"]) for item in items] == [
        ("1001", "default"),
        ("1001", "branded"),
    ]


def test_switch_weeks_returns_distinct_plans(api):
    client, _ = api
    client.put(
        f"/api/planner/plans/{WEEK_START}",
        json={"days": [{"date": WEEK_START, "meals": [_meal("breakfast", [_item("1001")])]}]},
    )
    next_week = "2026-11-02"
    client.put(
        f"/api/planner/plans/{next_week}",
        json={"days": [{"date": next_week, "meals": [_meal("dinner", [_item("1002")])]}]},
    )
    first = client.get(f"/api/planner/plans/{WEEK_START}").json()
    second = client.get(f"/api/planner/plans/{next_week}").json()
    assert _find_meal(first, WEEK_START, "breakfast")["items"][0]["food_key"] == "1001"
    assert _find_meal(second, next_week, "dinner")["items"][0]["food_key"] == "1002"
    assert first["plan_id"] != second["plan_id"]


def test_cross_year_week_dates_are_exact(api):
    """跨年自然周不应出现 UTC 偏移或日期错位。"""
    client, _ = api
    week = "2026-12-28"  # 周一
    r = client.get(f"/api/planner/plans/{week}")
    assert r.status_code == 200, r.text
    dates = [day["date"] for day in r.json()["days"]]
    assert dates[0] == "2026-12-28"
    assert dates[-1] == "2027-01-03"


def test_repeated_save_keeps_single_plan_row(api):
    client, db_path = api
    client.put(f"/api/planner/plans/{WEEK_START}", json=_week_payload())
    client.put(
        f"/api/planner/plans/{WEEK_START}",
        json={"days": [{"date": WEEK_START, "meals": [_meal("lunch", [_item("6001")])]}]},
    )
    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM weekly_plan").fetchone()[0]
        meal_count = conn.execute("SELECT COUNT(*) FROM meal").fetchone()[0]
    assert count == 1
    assert meal_count == 1
    plan = client.get(f"/api/planner/plans/{WEEK_START}").json()
    assert [m["meal_type"] for m in _find_day(plan, WEEK_START)["meals"]] == ["lunch"]


def test_delete_plan(api):
    client, _ = api
    client.put(f"/api/planner/plans/{WEEK_START}", json=_week_payload())
    r = client.delete(f"/api/planner/plans/{WEEK_START}")
    assert r.status_code == 200, r.text
    assert r.json()["plan_id"] is None
    assert all(day["meals"] == [] for day in r.json()["days"])


def test_invalid_amount_rejected(api):
    client, _ = api
    payload = {
        "days": [
            {"date": WEEK_START, "meals": [_meal("breakfast", [_item("1001", 0)])]},
        ]
    }
    r = client.put(f"/api/planner/plans/{WEEK_START}", json=payload)
    assert r.status_code == 422
