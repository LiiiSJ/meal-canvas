"""食品搜索、列表、详情、营养。"""
from __future__ import annotations

import logging
import re
import sqlite3
from typing import Annotated, Literal

from backend.app.api import db as dbmod
from backend.app.api import errors, formatters
from backend.app.usage import BASIC_INGREDIENT, PROCESSED_INGREDIENT
from fastapi import APIRouter, Query

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/foods", tags=["食品"])

UsageScope = Literal["ingredients", "all"]
UsageClass = Literal["basic_ingredient", "processed_ingredient", "prepared_dish", "ready_to_eat", "unknown"]


# --------------------------------------------------------------------------- 辅助


def _resolve_db_path(library_scope: str | None):
    """library_scope → 对应的数据库文件路径。

    - None 或 'default' → 默认食材库 meal_canvas.sqlite
    - 'branded' → 品牌库 meal_canvas_branded.sqlite
    品牌库不存在时，dbmod.connect() 会抛 DatabaseUnavailableError → 503。
    """
    if library_scope == "branded":
        return dbmod.branded_db_path()
    return dbmod.default_db_path()


def _paginate(page: int, page_size: int) -> tuple[int, int]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    return (page - 1) * page_size, page_size


def _status_weight(zh_status: str) -> int:
    # verified(0) 优先 > glossary(1) > none(2)
    return {"verified": 0, "glossary": 1, "none": 2}.get(zh_status or "", 3)


def _build_search_filters(
    conn: sqlite3.Connection,
    q: str | None,
    category_code: str | None,
    data_type: str | None,
    library_scope: str | None,
    usage_scope: str,
    usage_class: str | None,
) -> tuple[str, list]:
    """返回 SQL WHERE 片段 + 参数列表。

    食品准入与中文化状态分离：列表不再因 zh_status='none' 排除食品；中文名只是展示层信息。
    食品用途由独立的 usage.food_usage 表表达（basic/processed/prepared/ready/unknown），
    与 USDA data_type、中文映射状态互不混用。默认 usage_scope='ingredients' 只展示
    基础食材与加工食材；成品菜、即食与 unknown 需显式 usage_scope='all' 或按 usage_class 查询。
    """
    where_clauses: list[str] = []
    params: list = []

    # 1) 关键词：用三个来源合并 fdc_id 集合
    if q:
        term = q.strip()
        if term:
            # FTS 5 查询语法对引号、逗号、括号等标点敏感，先清洗为字母数字与中文，
            # 避免用户输入 "Milk, human" 这类描述时直接 500；LIKE 与别名查询仍是兜底。
            safe_tokens = [t for t in re.sub(r"[^\w\u4e00-\u9fff ]+", " ", term).split() if t]
            fts_ids: set[int] = set()
            if safe_tokens:
                # FTS 5 unicode61 tokenizer 对中文按单字切分，对英文按空白标点切分
                fts_match = "*".join(safe_tokens) + "*"
                fts_rows = conn.execute(
                    "SELECT fdc_id FROM food_fts WHERE food_fts MATCH ?",
                    (fts_match,),
                ).fetchall()
                fts_ids = {r[0] for r in fts_rows}

            en_like = f"%{term}%"
            en_rows = conn.execute(
                "SELECT fdc_id FROM food WHERE lower(description_en) LIKE lower(?)",
                (en_like,),
            ).fetchall()
            en_ids = {r[0] for r in en_rows}

            alias_rows = conn.execute(
                "SELECT DISTINCT fdc_id FROM food_alias WHERE lower(alias) LIKE lower(?)",
                (en_like,),
            ).fetchall()
            alias_ids = {r[0] for r in alias_rows}

            matched = fts_ids | en_ids | alias_ids
            if not matched:
                # 完全没匹配，返回一个永假条件让主查询直接返回空
                where_clauses.append("1 = 0")
            else:
                placeholders = ",".join("?" * len(matched))
                where_clauses.append(f"f.fdc_id IN ({placeholders})")
                params.extend(sorted(matched))

    if category_code:
        where_clauses.append("f.category_code = ?")
        params.append(category_code)
    if data_type:
        where_clauses.append("f.data_type = ?")
        params.append(data_type)
    if library_scope:
        where_clauses.append("f.library_scope = ?")
        params.append(library_scope)

    # 用途筛选：显式 usage_class 优先；否则按 usage_scope 决定是否限定为烹饪原料。
    if usage_class:
        where_clauses.append("u.usage_class = ?")
        params.append(usage_class)
    elif usage_scope == "ingredients":
        where_clauses.append("u.usage_class IN (?, ?)")
        params.extend([BASIC_INGREDIENT, PROCESSED_INGREDIENT])

    sql = "" if not where_clauses else "WHERE " + " AND ".join(where_clauses)
    return sql, params


def _food_row_to_dict(row: sqlite3.Row) -> dict:
    """food 表单行转 API 输出字段。"""
    zh_status = row["zh_status"] or ""
    zh_review_status = row["zh_review_status"] or ""
    name_zh = row["name_zh"] or None
    display_name = name_zh if name_zh and zh_status == "verified" else row["description_en"]
    keys = row.keys()
    return {
        "fdc_id": row["fdc_id"],
        "data_type": row["data_type"],
        "source_dataset": row["source_dataset"],
        "source_version": row["source_version"],
        "description_en": row["description_en"],
        "name_zh": name_zh,
        "display_name": display_name,
        "zh_status": zh_status,
        "zh_review_status": zh_review_status,
        "category_code": row["category_code"],
        "category_en": row["category_en"],
        "category_zh": row["category_zh"],
        "brand_owner": row["brand_owner"],
        "brand_name": row["brand_name"],
        "gtin_upc": row["gtin_upc"],
        "serving_size": row["serving_size"],
        "serving_unit": row["serving_unit"],
        "household_serving": row["household_serving"],
        "publication_date": row["publication_date"],
        "is_default_library": bool(row["is_default_library"]),
        "library_scope": row["library_scope"],
        "usage_class": row["usage_class"] if "usage_class" in keys else None,
        "usage_rule_source": row["usage_rule_source"] if "usage_rule_source" in keys else None,
        "usage_rule_id": row["usage_rule_id"] if "usage_rule_id" in keys else None,
        "usage_reason": row["usage_reason"] if "usage_reason" in keys else None,
    }


# --------------------------------------------------------------------------- 路由


@router.get("")
def list_foods(
    q: str | None = Query(default=None, description="搜索词：中文名/英文/别名（支持拼音首字母，FTS5 自动分词）"),
    category_code: str | None = Query(default=None, description="按 FDC/WWEIA category_code 筛选"),
    data_type: str | None = Query(default=None, description="按 data_type 筛选：foundation_food / sr_legacy_food / survey_fndds_food / branded_food"),
    library_scope: Literal["default", "branded"] | None = Query(default=None, description="按库类型筛选"),
    usage_scope: Annotated[UsageScope, Query(description="用途范围：ingredients 只含基础食材与加工食材（默认）；all 含全部用途类别")] = "ingredients",
    usage_class: Annotated[UsageClass | None, Query(description="精确用途筛选：basic_ingredient / processed_ingredient / prepared_dish / ready_to_eat / unknown")] = None,
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, description="每页数量，后端强制上限 100"),
    sort: Literal["relevance", "alpha_zh", "alpha_en"] = Query(
        default="relevance", description="排序：relevance（verified 优先）/ alpha_zh / alpha_en"
    ),
) -> dict:
    """分页搜索食品。默认只返回烹饪用途的基础食材与加工食材。"""
    target_db = _resolve_db_path(library_scope)
    with dbmod.connect(db_path=target_db) as conn:
        dbmod.attach_usage(conn)
        where_sql, params = _build_search_filters(
            conn, q, category_code, data_type, library_scope, usage_scope, usage_class
        )

        joins = (
            "FROM food f LEFT JOIN usage.food_usage u"
            " ON u.fdc_id = f.fdc_id AND u.library_scope = f.library_scope"
        )
        total = dbmod.count(conn, f"SELECT COUNT(*) {joins} {where_sql}", params)

        offset, limit = _paginate(page, page_size)
        page_size = limit  # 用 clamp 后的值
        order_clause: str
        if sort == "alpha_zh":
            order_clause = "COALESCE(f.name_zh, f.description_en) COLLATE NOCASE ASC, f.fdc_id ASC"
        elif sort == "alpha_en":
            order_clause = "f.description_en COLLATE NOCASE ASC, f.fdc_id ASC"
        else:  # relevance: verified > glossary > none, 然后 alphabetical
            order_clause = (
                "CASE f.zh_status WHEN 'verified' THEN 0 WHEN 'glossary' THEN 1 ELSE 2 END ASC, "
                "COALESCE(f.name_zh, f.description_en) COLLATE NOCASE ASC, f.fdc_id ASC"
            )

        rows = dbmod.rows(
            conn,
            "SELECT f.*, u.usage_class AS usage_class, u.rule_source AS usage_rule_source,"
            " u.rule_id AS usage_rule_id, u.reason AS usage_reason "
            f"{joins} {where_sql} ORDER BY {order_clause} LIMIT ? OFFSET ?",
            [*params, limit, offset],
        )

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "usage_scope": usage_scope,
        "usage_class": usage_class,
        "items": [_food_row_to_dict(r) for r in rows],
    }


@router.get("/{food_key}")
def get_food(
    food_key: str,
    library_scope: Literal["default", "branded"] | None = Query(
        default=None,
        description="指定库：default / branded。默认先查 default 库，查不到再查 branded 库；显式指定时只查对应库",
    ),
) -> dict:
    """查询单条食品详情。food_key 可以是 fdc_id（整数）或英文/中文名。"""

    def _lookup(conn: sqlite3.Connection) -> sqlite3.Row | None:
        dbmod.attach_usage(conn)
        select_sql = (
            "SELECT f.*, u.usage_class AS usage_class, u.rule_source AS usage_rule_source,"
            " u.rule_id AS usage_rule_id, u.reason AS usage_reason"
            " FROM food f LEFT JOIN usage.food_usage u"
            " ON u.fdc_id = f.fdc_id AND u.library_scope = f.library_scope"
        )
        if food_key.isdigit():
            row = dbmod.row(conn, f"{select_sql} WHERE f.fdc_id = ?", (int(food_key),))
        else:
            row = None
        if row is None:
            row = dbmod.row(
                conn,
                f"{select_sql} WHERE f.description_en = ? OR f.name_zh = ? ORDER BY "
                "CASE f.zh_status WHEN 'verified' THEN 0 ELSE 1 END ASC, f.fdc_id ASC LIMIT 1",
                (food_key, food_key),
            )
        return row

    row: sqlite3.Row | None = None
    used_scope: str = "default"

    if library_scope is None:
        # 先查 default，查不到再查 branded（兼容向后：默认库优先）
        with dbmod.connect(db_path=dbmod.default_db_path()) as conn:
            row = _lookup(conn)
        if row is None:
            with dbmod.connect(db_path=dbmod.branded_db_path()) as conn:
                row = _lookup(conn)
                if row is not None:
                    used_scope = "branded"
    else:
        target = _resolve_db_path(library_scope)
        used_scope = library_scope
        with dbmod.connect(db_path=target) as conn:
            row = _lookup(conn)

    if row is None:
        errors.raise_not_found("食品", food_key)

    fdc_id = row["fdc_id"]

    # 后续 portions / aliases / summary / quality_events 必须查同一个库
    target_db = _resolve_db_path(used_scope)
    with dbmod.connect(db_path=target_db) as conn:
        # 食品详情（含份量列表）
        food = _food_row_to_dict(row)

        portions = [
            {
                "fdc_id": p["fdc_id"],
                "amount": p["amount"],
                "modifier": p["modifier"],
                "portion_description": p["portion_description"],
                "gram_weight": p["gram_weight"],
                "unit_name": p["unit_name"],
                "quality_flag": p["quality_flag"],
            }
            for p in dbmod.rows(
                conn,
                "SELECT * FROM food_portion WHERE fdc_id = ? ORDER BY id ASC",
                (fdc_id,),
            )
        ]

        aliases = [
            {
                "alias": a["alias"],
                "alias_type": a["alias_type"],
                "status": a["status"],
                "review_status": a["review_status"],
            }
            for a in dbmod.rows(
                conn,
                "SELECT alias, alias_type, status, review_status FROM food_alias WHERE fdc_id = ? ORDER BY alias_type, alias ASC",
                (fdc_id,),
            )
        ]

        summary_row = dbmod.row(
            conn, "SELECT * FROM food_summary WHERE fdc_id = ?", (fdc_id,)
        )
        summary = {
            "energy_kcal": summary_row["energy_kcal"] if summary_row else None,
            "protein_g": summary_row["protein_g"] if summary_row else None,
            "fat_g": summary_row["fat_g"] if summary_row else None,
            "carb_g": summary_row["carb_g"] if summary_row else None,
            "fiber_g": summary_row["fiber_g"] if summary_row else None,
            "sugar_g": summary_row["sugar_g"] if summary_row else None,
            "sodium_mg": summary_row["sodium_mg"] if summary_row else None,
            "known_core_count": summary_row["known_core_count"] if summary_row else 0,
            "baseline": "每 100 克",
        }

        events = [
            {
                "event_type": e["event_type"],
                "nutrient_id": e["nutrient_id"],
                "raw_amount": e["raw_amount"],
                "detail": e["detail"],
            }
            for e in dbmod.rows(
                conn,
                "SELECT event_type, nutrient_id, raw_amount, detail FROM quality_event "
                "WHERE fdc_id = ? ORDER BY id ASC",
                (fdc_id,),
            )
        ]

    food["portions"] = portions
    food["aliases"] = aliases
    food["summary_per_100g"] = summary
    food["quality_events"] = events
    return food


@router.get("/{food_key}/nutrients")
def get_food_nutrients(
    food_key: str,
    library_scope: Literal["default", "branded"] | None = Query(
        default=None,
        description="指定库：default / branded。默认先查 default 库，查不到再查 branded 库；显式指定时只查对应库",
    ),
) -> dict:
    """返回该食品的营养指标，含缺失状态。缺失值返回 amount=null，零值返回 amount=0.0 且 quality_flag='ok'。"""

    def _lookup_foodrow(conn: sqlite3.Connection) -> sqlite3.Row | None:
        if food_key.isdigit():
            row = dbmod.row(conn, "SELECT * FROM food WHERE fdc_id = ?", (int(food_key),))
        else:
            row = None
        if row is None:
            row = dbmod.row(
                conn,
                "SELECT * FROM food WHERE description_en = ? OR name_zh = ? ORDER BY fdc_id ASC LIMIT 1",
                (food_key, food_key),
            )
        return row

    food_row: sqlite3.Row | None = None
    used_scope: str = "default"

    if library_scope is None:
        with dbmod.connect(db_path=dbmod.default_db_path()) as conn:
            food_row = _lookup_foodrow(conn)
        if food_row is None:
            with dbmod.connect(db_path=dbmod.branded_db_path()) as conn:
                food_row = _lookup_foodrow(conn)
                if food_row is not None:
                    used_scope = "branded"
    else:
        used_scope = library_scope
        with dbmod.connect(db_path=_resolve_db_path(library_scope)) as conn:
            food_row = _lookup_foodrow(conn)

    if food_row is None:
        errors.raise_not_found("食品", food_key)

    # 查 nutrients 必须用同一个库
    with dbmod.connect(db_path=_resolve_db_path(used_scope)) as conn:
        fdc_id = food_row["fdc_id"]
        rows = dbmod.rows(
            conn,
            """
            SELECT fn.fdc_id, fn.nutrient_id, fn.amount, fn.raw_amount, fn.quality_flag,
                   fn.origin_nutrient_id, n.name_en as nutrient_name_en, n.name_zh as nutrient_name_zh,
                   n.unit_name as unit_en, n.unit_zh, n.decimals, n.is_core
            FROM food_nutrient fn
            JOIN nutrient n ON n.id = fn.nutrient_id
            WHERE fn.fdc_id = ?
            ORDER BY n.rank ASC, n.id ASC
            """,
            (fdc_id,),
        )

    items = [
        {
            "nutrient_id": r["nutrient_id"],
            "origin_nutrient_id": r["origin_nutrient_id"],
            "name_en": r["nutrient_name_en"],
            "name_zh": r["nutrient_name_zh"],
            "unit_en": r["unit_en"],
            "unit_zh": r["unit_zh"],
            "decimals": r["decimals"],
            "is_core": bool(r["is_core"]),
            "baseline": "每 100 克",
            "amount": formatters.round_amount(r["amount"], r["decimals"]),
            "raw_amount": r["raw_amount"],
            "quality_flag": r["quality_flag"],
            "is_available": r["quality_flag"] == "ok" and r["amount"] is not None,
        }
        for r in rows
    ]

    # 缺失状态汇总
    missing = [it for it in items if not it["is_available"]]
    return {
        "fdc_id": fdc_id,
        "display_name": food_row["name_zh"] or food_row["description_en"],
        "baseline": "每 100 克",
        "total_nutrients_returned": len(items),
        "missing_count": len(missing),
        "nutrients": items,
    }
