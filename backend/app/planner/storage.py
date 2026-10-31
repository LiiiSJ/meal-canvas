"""每周膳食计划存储层。

独立 SQLite 库（默认 data/build/meal_canvas_planner.sqlite），
与 USDA 食品库、品牌库、外部营养补全库物理隔离；本模块不会连接任何食品库。

三张表：
- weekly_plan  以周一日期（YYYY-MM-DD）唯一标识的一周计划
- meal         某一天的某个餐次（早餐/午餐/晚餐/加餐，加餐可有多条）
- meal_item    餐次中的食品引用（food_key + library_scope + 克数）
"""
from __future__ import annotations

import os
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PLANNER_DB = PROJECT_ROOT / "data" / "build" / "meal_canvas_planner.sqlite"

MEAL_TYPES: tuple[str, ...] = ("breakfast", "lunch", "dinner", "snack")
MAIN_MEAL_TYPES: tuple[str, ...] = ("breakfast", "lunch", "dinner")
MEAL_TYPE_ORDER: dict[str, int] = {"breakfast": 0, "lunch": 1, "dinner": 2, "snack": 9}
DEFAULT_MEAL_NAMES: dict[str, str] = {
    "breakfast": "早餐",
    "lunch": "午餐",
    "dinner": "晚餐",
    "snack": "加餐",
}
LIBRARY_SCOPES: tuple[str, ...] = ("default", "branded")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS weekly_plan (
    plan_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    week_start TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meal (
    meal_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id    INTEGER NOT NULL REFERENCES weekly_plan(plan_id) ON DELETE CASCADE,
    meal_date  TEXT NOT NULL,
    meal_type  TEXT NOT NULL,
    meal_name  TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    notes      TEXT
);

CREATE TABLE IF NOT EXISTS meal_item (
    item_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    meal_id       INTEGER NOT NULL REFERENCES meal(meal_id) ON DELETE CASCADE,
    food_key      TEXT NOT NULL,
    library_scope TEXT NOT NULL,
    amount_g      REAL NOT NULL,
    sort_order    INTEGER NOT NULL DEFAULT 0,
    name_snapshot TEXT
);

CREATE INDEX IF NOT EXISTS idx_meal_plan ON meal(plan_id, meal_date);
CREATE INDEX IF NOT EXISTS idx_meal_item_meal ON meal_item(meal_id);
"""


def planner_db_path() -> Path:
    """每次调用时读取环境变量，便于测试指向临时库。"""
    raw = os.environ.get("MEAL_CANVAS_PLANNER_DB_PATH", str(DEFAULT_PLANNER_DB))
    return Path(raw).expanduser()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def week_dates(week_start: str) -> list[str]:
    """以周一到周日为自然周，返回 7 个 YYYY-MM-DD 日期（纯日期运算，无时区转换）。"""
    start = date.fromisoformat(week_start)
    return [(start + timedelta(days=offset)).isoformat() for offset in range(7)]


def _meal_sort_key(meal_type: str, sort_order: int, meal_id: int) -> tuple[int, int, int]:
    return (MEAL_TYPE_ORDER.get(meal_type, 99), sort_order, meal_id)


class PlannerStorage:
    """计划库读写。所有写入只发生在本库。"""

    def __init__(self, db_path: Path | None = None) -> None:
        self._path = db_path or planner_db_path()
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    @property
    def path(self) -> Path:
        return self._path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            conn = sqlite3.connect(str(self._path), timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)

    # ------------------------------------------------------------ 读取

    def get_plan(self, week_start: str) -> dict:
        """返回指定周的完整计划；未保存时返回 plan_id=None 与 7 个空日。"""
        with self.connect() as conn:
            plan = conn.execute(
                "SELECT plan_id, week_start, created_at, updated_at "
                "FROM weekly_plan WHERE week_start = ?",
                (week_start,),
            ).fetchone()
            meals = []
            if plan is not None:
                meals = conn.execute(
                    "SELECT meal_id, plan_id, meal_date, meal_type, meal_name, sort_order, notes "
                    "FROM meal WHERE plan_id = ?",
                    (int(plan["plan_id"]),),
                ).fetchall()
                items = conn.execute(
                    "SELECT item_id, meal_id, food_key, library_scope, amount_g, sort_order, "
                    "name_snapshot FROM meal_item WHERE meal_id IN "
                    "(SELECT meal_id FROM meal WHERE plan_id = ?)",
                    (int(plan["plan_id"]),),
                ).fetchall()
            else:
                items = []

        items_by_meal: dict[int, list[dict]] = {}
        for item in items:
            items_by_meal.setdefault(int(item["meal_id"]), []).append(
                {
                    "item_id": int(item["item_id"]),
                    "food_key": item["food_key"],
                    "library_scope": item["library_scope"],
                    "amount_g": float(item["amount_g"]),
                    "sort_order": int(item["sort_order"]),
                    "name_snapshot": item["name_snapshot"],
                }
            )
        for bucket in items_by_meal.values():
            bucket.sort(key=lambda row: (row["sort_order"], row["item_id"]))

        meals_by_date: dict[str, list[dict]] = {}
        for meal in meals:
            meals_by_date.setdefault(meal["meal_date"], []).append(
                {
                    "meal_id": int(meal["meal_id"]),
                    "meal_date": meal["meal_date"],
                    "meal_type": meal["meal_type"],
                    "meal_name": meal["meal_name"],
                    "sort_order": int(meal["sort_order"]),
                    "notes": meal["notes"],
                    "items": items_by_meal.get(int(meal["meal_id"]), []),
                }
            )
        for bucket in meals_by_date.values():
            bucket.sort(key=lambda row: _meal_sort_key(
                row["meal_type"], row["sort_order"], row["meal_id"]
            ))

        return {
            "week_start": week_start,
            "plan_id": int(plan["plan_id"]) if plan is not None else None,
            "created_at": plan["created_at"] if plan is not None else None,
            "updated_at": plan["updated_at"] if plan is not None else None,
            "days": [
                {"date": day, "meals": meals_by_date.get(day, [])}
                for day in week_dates(week_start)
            ],
        }

    def week_start_for_meal(self, meal_id: int) -> str | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT p.week_start FROM meal m "
                "JOIN weekly_plan p ON p.plan_id = m.plan_id WHERE m.meal_id = ?",
                (meal_id,),
            ).fetchone()
        return row["week_start"] if row is not None else None

    # ------------------------------------------------------------ 整周保存

    def save_plan(self, week_start: str, days: list[dict]) -> dict:
        """整周覆盖保存：同一 week_start 永不重复创建，旧餐次与食品会被替换。"""
        now = _now_iso()
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO weekly_plan (week_start, created_at, updated_at) "
                "VALUES (?, ?, ?) ON CONFLICT(week_start) DO UPDATE SET "
                "updated_at = excluded.updated_at",
                (week_start, now, now),
            )
            row = conn.execute(
                "SELECT plan_id FROM weekly_plan WHERE week_start = ?", (week_start,)
            ).fetchone()
            assert row is not None
            plan_id = int(row["plan_id"])
            conn.execute("DELETE FROM meal WHERE plan_id = ?", (plan_id,))

            for day in days:
                for meal_index, meal in enumerate(day["meals"]):
                    meal_type = meal["meal_type"]
                    meal_name = meal.get("meal_name") or DEFAULT_MEAL_NAMES[meal_type]
                    sort_order = meal.get("sort_order")
                    if sort_order is None:
                        sort_order = (
                            MEAL_TYPE_ORDER.get(meal_type, 9) * 10
                            + (meal_index if meal_type == "snack" else 0)
                        )
                    cursor = conn.execute(
                        "INSERT INTO meal "
                        "(plan_id, meal_date, meal_type, meal_name, sort_order, notes) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            plan_id,
                            day["date"],
                            meal_type,
                            meal_name,
                            int(sort_order),
                            meal.get("notes"),
                        ),
                    )
                    meal_id = int(cursor.lastrowid)
                    for item_index, item in enumerate(meal["items"]):
                        conn.execute(
                            "INSERT INTO meal_item "
                            "(meal_id, food_key, library_scope, amount_g, sort_order, "
                            "name_snapshot) VALUES (?, ?, ?, ?, ?, ?)",
                            (
                                meal_id,
                                item["food_key"],
                                item["library_scope"],
                                float(item["amount_g"]),
                                int(item.get("sort_order", item_index)),
                                item.get("name_snapshot"),
                            ),
                        )
        return self.get_plan(week_start)

    def delete_plan(self, week_start: str) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM weekly_plan WHERE week_start = ?", (week_start,))

    # ------------------------------------------------------------ 餐次

    def _plan_id_for_week(self, conn: sqlite3.Connection, week_start: str) -> int | None:
        row = conn.execute(
            "SELECT plan_id FROM weekly_plan WHERE week_start = ?", (week_start,)
        ).fetchone()
        return int(row["plan_id"]) if row is not None else None

    def _ensure_plan(self, conn: sqlite3.Connection, week_start: str) -> int:
        now = _now_iso()
        conn.execute(
            "INSERT INTO weekly_plan (week_start, created_at, updated_at) "
            "VALUES (?, ?, ?) ON CONFLICT(week_start) DO UPDATE SET "
            "updated_at = excluded.updated_at",
            (week_start, now, now),
        )
        plan_id = self._plan_id_for_week(conn, week_start)
        assert plan_id is not None
        return plan_id

    def _next_item_sort(self, conn: sqlite3.Connection, meal_id: int) -> int:
        row = conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 AS next FROM meal_item "
            "WHERE meal_id = ?",
            (meal_id,),
        ).fetchone()
        return int(row["next"]) if row is not None else 0

    def _next_snack_sort(self, conn: sqlite3.Connection, plan_id: int, meal_date: str) -> int:
        row = conn.execute(
            "SELECT COALESCE(MAX(sort_order), 29) + 1 AS next FROM meal "
            "WHERE plan_id = ? AND meal_date = ? AND meal_type = 'snack'",
            (plan_id, meal_date),
        ).fetchone()
        return int(row["next"]) if row is not None else 30

    def _find_or_create_meal(
        self, conn: sqlite3.Connection, plan_id: int, meal_date: str, meal_type: str
    ) -> int:
        """定位某天某餐次；不存在时自动创建（加餐取该天最早的加餐）。"""
        meal = conn.execute(
            "SELECT meal_id FROM meal WHERE plan_id = ? AND meal_date = ? "
            "AND meal_type = ? ORDER BY sort_order, meal_id LIMIT 1",
            (plan_id, meal_date, meal_type),
        ).fetchone()
        if meal is not None:
            return int(meal["meal_id"])
        sort_order = (
            self._next_snack_sort(conn, plan_id, meal_date)
            if meal_type == "snack"
            else MEAL_TYPE_ORDER[meal_type] * 10
        )
        cursor = conn.execute(
            "INSERT INTO meal "
            "(plan_id, meal_date, meal_type, meal_name, sort_order, notes) "
            "VALUES (?, ?, ?, ?, ?, NULL)",
            (plan_id, meal_date, meal_type, DEFAULT_MEAL_NAMES[meal_type], sort_order),
        )
        return int(cursor.lastrowid)

    def _insert_item(self, conn: sqlite3.Connection, meal_id: int, item: dict) -> None:
        conn.execute(
            "INSERT INTO meal_item "
            "(meal_id, food_key, library_scope, amount_g, sort_order, name_snapshot) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                meal_id,
                item["food_key"],
                item["library_scope"],
                float(item["amount_g"]),
                self._next_item_sort(conn, meal_id),
                item.get("name_snapshot"),
            ),
        )

    def add_entry(
        self,
        *,
        week_start: str,
        meal_date: str,
        meal_type: str,
        item: dict,
    ) -> dict:
        """向某天某餐次追加一个食品；餐次不存在时自动创建（加餐可重复创建）。"""
        return self.add_entries(
            week_start=week_start, meal_date=meal_date, meal_type=meal_type, items=[item]
        )

    def add_entries(
        self,
        *,
        week_start: str,
        meal_date: str,
        meal_type: str,
        items: list[dict],
    ) -> dict:
        """一次事务向某天某餐次追加多个食品（例如整盘加入计划）。"""
        with self.connect() as conn:
            plan_id = self._ensure_plan(conn, week_start)
            meal_id = self._find_or_create_meal(conn, plan_id, meal_date, meal_type)
            for item in items:
                self._insert_item(conn, meal_id, item)
        return self.get_plan(week_start)

    def create_meal(self, week_start: str, meal: dict) -> dict:
        with self.connect() as conn:
            plan_id = self._ensure_plan(conn, week_start)
            sort_order = (
                self._next_snack_sort(conn, plan_id, meal["meal_date"])
                if meal["meal_type"] == "snack"
                else MEAL_TYPE_ORDER[meal["meal_type"]] * 10
            )
            conn.execute(
                "INSERT INTO meal "
                "(plan_id, meal_date, meal_type, meal_name, sort_order, notes) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    plan_id,
                    meal["meal_date"],
                    meal["meal_type"],
                    meal.get("meal_name") or DEFAULT_MEAL_NAMES[meal["meal_type"]],
                    int(meal.get("sort_order", sort_order)),
                    meal.get("notes"),
                ),
            )
        return self.get_plan(week_start)

    def update_meal(self, meal_id: int, week_start: str, meal: dict) -> dict:
        with self.connect() as conn:
            conn.execute(
                "UPDATE meal SET meal_date = ?, meal_type = ?, meal_name = ?, "
                "sort_order = ?, notes = ? WHERE meal_id = ?",
                (
                    meal["meal_date"],
                    meal["meal_type"],
                    meal.get("meal_name") or DEFAULT_MEAL_NAMES[meal["meal_type"]],
                    int(meal.get("sort_order", 0)),
                    meal.get("notes"),
                    meal_id,
                ),
            )
            if "items" in meal:
                conn.execute("DELETE FROM meal_item WHERE meal_id = ?", (meal_id,))
                for index, item in enumerate(meal["items"]):
                    conn.execute(
                        "INSERT INTO meal_item "
                        "(meal_id, food_key, library_scope, amount_g, sort_order, "
                        "name_snapshot) VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            meal_id,
                            item["food_key"],
                            item["library_scope"],
                            float(item["amount_g"]),
                            int(item.get("sort_order", index)),
                            item.get("name_snapshot"),
                        ),
                    )
        return self.get_plan(week_start)

    def delete_meal(self, meal_id: int) -> str | None:
        week_start = self.week_start_for_meal(meal_id)
        with self.connect() as conn:
            conn.execute("DELETE FROM meal WHERE meal_id = ?", (meal_id,))
        return week_start

    # ------------------------------------------------------------ 食品

    def add_item(self, meal_id: int, week_start: str, item: dict) -> dict:
        with self.connect() as conn:
            sort_order = self._next_item_sort(conn, meal_id)
            conn.execute(
                "INSERT INTO meal_item "
                "(meal_id, food_key, library_scope, amount_g, sort_order, name_snapshot) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    meal_id,
                    item["food_key"],
                    item["library_scope"],
                    float(item["amount_g"]),
                    int(item.get("sort_order", sort_order)),
                    item.get("name_snapshot"),
                ),
            )
        return self.get_plan(week_start)

    def update_item(self, meal_id: int, item_id: int, week_start: str, amount_g: float) -> dict:
        with self.connect() as conn:
            conn.execute(
                "UPDATE meal_item SET amount_g = ? WHERE item_id = ? AND meal_id = ?",
                (float(amount_g), item_id, meal_id),
            )
        return self.get_plan(week_start)

    def delete_item(self, meal_id: int, item_id: int, week_start: str) -> dict:
        with self.connect() as conn:
            conn.execute(
                "DELETE FROM meal_item WHERE item_id = ? AND meal_id = ?",
                (item_id, meal_id),
            )
        return self.get_plan(week_start)
