"""分类元数据。

同时查询 default 库和 branded 库，合并去重。品牌库不可用时跳过（不抛异常）。
"""
from __future__ import annotations

import logging
import sqlite3

from backend.app.api import db as dbmod
from fastapi import APIRouter, Query

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/metadata/categories", tags=["元数据"])


def _fetch_categories(conn: sqlite3.Connection, source_filter: str | None) -> list[sqlite3.Row]:
    """从一个库 SELECT DISTINCT category_source/code/en/zh。"""
    where_clauses = ["category_zh IS NOT NULL AND category_zh <> ''"]
    params: list = []
    if source_filter:
        where_clauses.append("category_source = ?")
        params.append(source_filter)
    where = "WHERE " + " AND ".join(where_clauses)
    return dbmod.rows(
        conn,
        f"""
        SELECT DISTINCT category_source, category_code, category_en, category_zh
        FROM food {where}
        ORDER BY category_source, category_code
        """,
        params,
    )


@router.get("")
def list_categories(
    source: str | None = Query(default=None, description="按 category_source 筛选：fdc / wweia / branded"),
) -> dict:
    """返回分类去重列表（同时覆盖 default 库 + 品牌库）。"""
    merged: list[sqlite3.Row] = []

    # default 库必须成功，否则抛出 DatabaseUnavailableError 让上层 handler 处理
    with dbmod.connect(db_path=dbmod.default_db_path()) as conn:
        merged.extend(_fetch_categories(conn, source))

    # 品牌库：有就加，没有或坏掉就跳过（不影响主流程）
    branded_path = dbmod.branded_db_path()
    if branded_path.is_file():
        try:
            with dbmod.connect(db_path=branded_path) as conn:
                merged.extend(_fetch_categories(conn, source))
        except Exception as exc:
            log.warning("品牌库分类查询失败，跳过：%s", exc)

    # 去重：(category_source, category_code, category_en, category_zh) 四元组唯一
    seen: set[tuple] = set()
    unique_rows: list[sqlite3.Row] = []
    for r in merged:
        key = (
            r["category_source"],
            r["category_code"],
            r["category_en"],
            r["category_zh"],
        )
        if key in seen:
            continue
        seen.add(key)
        unique_rows.append(r)

    # 稳定排序：source → code → zh
    unique_rows.sort(key=lambda r: (
        r["category_source"] or "",
        r["category_code"] or "",
        r["category_zh"] or "",
    ))

    return {
        "total": len(unique_rows),
        "items": [
            {
                "category_source": r["category_source"],
                "category_code": r["category_code"],
                "name_en": r["category_en"],
                "name_zh": r["category_zh"],
            }
            for r in unique_rows
        ],
    }
