"""每周膳食计划 API。

计划数据只写入独立应用库（backend/app/planner/storage.py），
不读写 USDA 食品库、品牌库或外部营养补全库。

日期全部使用 YYYY-MM-DD 纯日期字符串，不做 UTC 转换。
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

from backend.app.api import errors
from backend.app.planner.storage import (
    DEFAULT_MEAL_NAMES,
    MEAL_TYPES,
    PlannerStorage,
)
from fastapi import APIRouter, Path
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/planner", tags=["每周计划"])

MealType = Literal["breakfast", "lunch", "dinner", "snack"]
LibraryScope = Literal["default", "branded"]
WeekStartPath = Path(description="周一日期，格式 YYYY-MM-DD")


class ItemIn(BaseModel):
    food_key: str = Field(min_length=1, max_length=100)
    library_scope: LibraryScope = "default"
    amount_g: float = Field(gt=0, le=10000)
    sort_order: int = 0
    name_snapshot: str | None = Field(default=None, max_length=300)


class ItemAmountIn(BaseModel):
    amount_g: float = Field(gt=0, le=10000)


class MealIn(BaseModel):
    meal_type: MealType
    meal_name: str | None = Field(default=None, max_length=60)
    sort_order: int = 0
    notes: str | None = Field(default=None, max_length=500)
    items: list[ItemIn] = Field(default_factory=list)


class DayIn(BaseModel):
    date: str
    meals: list[MealIn] = Field(default_factory=list)


class WeekIn(BaseModel):
    days: list[DayIn] = Field(default_factory=list)


class MealCreateIn(BaseModel):
    meal_date: str
    meal_type: MealType
    meal_name: str | None = Field(default=None, max_length=60)
    sort_order: int = 0
    notes: str | None = Field(default=None, max_length=500)


class MealUpdateIn(MealCreateIn):
    items: list[ItemIn] | None = None


class EntryIn(BaseModel):
    meal_date: str
    meal_type: MealType
    food_key: str = Field(min_length=1, max_length=100)
    library_scope: LibraryScope = "default"
    amount_g: float = Field(gt=0, le=10000)
    name_snapshot: str | None = Field(default=None, max_length=300)


class BatchEntryItemIn(BaseModel):
    food_key: str = Field(min_length=1, max_length=100)
    library_scope: LibraryScope = "default"
    amount_g: float = Field(gt=0, le=10000)
    name_snapshot: str | None = Field(default=None, max_length=300)


class BatchEntryIn(BaseModel):
    meal_date: str
    meal_type: MealType
    items: list[BatchEntryItemIn] = Field(min_length=1, max_length=50)


# --------------------------------------------------------------------------- 校验


def _parse_date(value: str, label: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        errors.raise_bad_request(f"{label}必须是 YYYY-MM-DD 格式的日期：{value}")
        raise AssertionError("unreachable") from None


def _parse_week_start(value: str) -> date:
    start = _parse_date(value, "星期起始日期")
    if start.weekday() != 0:
        errors.raise_bad_request("周计划必须以周一日期开始，例如 2026-10-26。")
    return start


def _ensure_date_in_week(day: date, start: date) -> None:
    if not (start <= day <= start + timedelta(days=6)):
        errors.raise_bad_request(
            f"餐次日期 {day.isoformat()} 不在本周范围内（{start.isoformat()} 至 "
            f"{(start + timedelta(days=6)).isoformat()}）。"
        )


def _validate_meal(meal: MealIn | MealCreateIn) -> None:
    if meal.meal_type not in MEAL_TYPES:
        errors.raise_bad_request(f"不支持的餐次类型：{meal.meal_type}")


def _week_start_for(day: date) -> str:
    return (day - timedelta(days=day.weekday())).isoformat()


def _storage() -> PlannerStorage:
    return PlannerStorage()


# --------------------------------------------------------------------------- 路由


@router.get("/plans/{week_start}")
def get_plan(week_start: str = WeekStartPath) -> dict:
    """读取指定周的完整计划。未保存时返回 plan_id=null 与 7 个空日。"""
    start = _parse_week_start(week_start)
    return _storage().get_plan(start.isoformat())


@router.put("/plans/{week_start}")
def save_plan(week_start: str = WeekStartPath, payload: WeekIn | None = None) -> dict:
    """整周覆盖保存。同一 week_start 只会有一条计划记录，不会重复创建冲突计划。"""
    start = _parse_week_start(week_start)
    days_input = payload.days if payload is not None else []
    seen_dates: set[str] = set()
    main_types_by_date: dict[str, set[str]] = {}

    days: list[dict] = []
    for day in days_input:
        parsed = _parse_date(day.date, "餐次日期")
        _ensure_date_in_week(parsed, start)
        if day.date in seen_dates:
            errors.raise_bad_request(f"同一天不能重复保存：{day.date}")
        seen_dates.add(day.date)

        meals: list[dict] = []
        for meal in day.meals:
            _validate_meal(meal)
            if meal.meal_type in ("breakfast", "lunch", "dinner"):
                used = main_types_by_date.setdefault(day.date, set())
                if meal.meal_type in used:
                    errors.raise_bad_request(
                        f"{day.date} 的{DEFAULT_MEAL_NAMES[meal.meal_type]}最多只能有一条。"
                    )
                used.add(meal.meal_type)
            meals.append(
                {
                    "meal_type": meal.meal_type,
                    "meal_name": meal.meal_name,
                    "sort_order": meal.sort_order,
                    "notes": meal.notes,
                    "items": [item.model_dump() for item in meal.items],
                }
            )
        days.append({"date": day.date, "meals": meals})

    return _storage().save_plan(start.isoformat(), days)


@router.delete("/plans/{week_start}")
def delete_plan(week_start: str = WeekStartPath) -> dict:
    start = _parse_week_start(week_start)
    _storage().delete_plan(start.isoformat())
    return _storage().get_plan(start.isoformat())


@router.post("/plans/{week_start}/meals")
def create_meal(week_start: str = WeekStartPath, payload: MealCreateIn | None = None) -> dict:
    start = _parse_week_start(week_start)
    if payload is None:
        errors.raise_bad_request("缺少餐次内容。")
        raise AssertionError  # pragma: no cover
    day = _parse_date(payload.meal_date, "餐次日期")
    _ensure_date_in_week(day, start)
    _validate_meal(payload)
    return _storage().create_meal(start.isoformat(), payload.model_dump())


@router.put("/meals/{meal_id}")
def update_meal(payload: MealUpdateIn, meal_id: int) -> dict:
    """修改某一天某顿饭的安排；传入 items 时整组替换该餐次食品。"""
    week_start = _storage().week_start_for_meal(meal_id)
    if week_start is None:
        errors.raise_not_found("餐次", meal_id)
        raise AssertionError  # pragma: no cover
    start = date.fromisoformat(week_start)
    day = _parse_date(payload.meal_date, "餐次日期")
    _ensure_date_in_week(day, start)
    _validate_meal(payload)
    meal = payload.model_dump()
    if meal["items"] is None:
        meal.pop("items")
    return _storage().update_meal(meal_id, week_start, meal)


@router.delete("/meals/{meal_id}")
def delete_meal(meal_id: int) -> dict:
    week_start = _storage().delete_meal(meal_id)
    if week_start is None:
        errors.raise_not_found("餐次", meal_id)
        raise AssertionError  # pragma: no cover
    return _storage().get_plan(week_start)


@router.post("/meals/{meal_id}/items")
def add_item(meal_id: int, payload: ItemIn) -> dict:
    week_start = _storage().week_start_for_meal(meal_id)
    if week_start is None:
        errors.raise_not_found("餐次", meal_id)
        raise AssertionError  # pragma: no cover
    return _storage().add_item(meal_id, week_start, payload.model_dump())


@router.put("/meals/{meal_id}/items/{item_id}")
def update_item(meal_id: int, item_id: int, payload: ItemAmountIn) -> dict:
    week_start = _storage().week_start_for_meal(meal_id)
    if week_start is None:
        errors.raise_not_found("餐次", meal_id)
        raise AssertionError  # pragma: no cover
    return _storage().update_item(meal_id, item_id, week_start, payload.amount_g)


@router.delete("/meals/{meal_id}/items/{item_id}")
def delete_item(meal_id: int, item_id: int) -> dict:
    week_start = _storage().week_start_for_meal(meal_id)
    if week_start is None:
        errors.raise_not_found("餐次", meal_id)
        raise AssertionError  # pragma: no cover
    return _storage().delete_item(meal_id, item_id, week_start)


@router.post("/entries")
def add_entry(payload: EntryIn) -> dict:
    """向某天某餐次追加一个食品；餐次不存在时自动创建，便于从食品详情直接加入计划。"""
    day = _parse_date(payload.meal_date, "餐次日期")
    week_start = _week_start_for(day)
    item = {
        "food_key": payload.food_key,
        "library_scope": payload.library_scope,
        "amount_g": payload.amount_g,
        "name_snapshot": payload.name_snapshot,
    }
    return _storage().add_entry(
        week_start=week_start,
        meal_date=day.isoformat(),
        meal_type=payload.meal_type,
        item=item,
    )


@router.post("/entries/batch")
def add_entries_batch(payload: BatchEntryIn) -> dict:
    """一次向某天某餐次追加多个食品（例如把整盘设计加入计划）；餐次不存在时自动创建。"""
    day = _parse_date(payload.meal_date, "餐次日期")
    week_start = _week_start_for(day)
    return _storage().add_entries(
        week_start=week_start,
        meal_date=day.isoformat(),
        meal_type=payload.meal_type,
        items=[item.model_dump() for item in payload.items],
    )
