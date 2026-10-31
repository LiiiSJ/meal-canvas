"""外部营养补全路由。

GET  /api/enrichment/foods/{fdc_id}/resolved  检测缺失并按需触发外部检索，返回统一解析结果
POST /api/enrichment/foods/{fdc_id}/refresh   忽略缓存强制重新检索

只读 USDA 库（连接保持 PRAGMA query_only=ON）；补全数据只写独立补全库。
检查范围为 nutrient 元数据表全部 37 项营养素，不止核心 7 项。
"""
from __future__ import annotations

import logging
import sqlite3
from functools import lru_cache
from pathlib import Path

from backend.app.api import db as dbmod
from backend.app.api import errors
from backend.app.enrichment.identity import LocalFood
from backend.app.enrichment.mapper import ALL_NUTRIENT_KEYS, NUTRIENT_KEY_BY_ID
from backend.app.enrichment.service import get_service
from fastapi import APIRouter

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/enrichment", tags=["外部补全"])


@lru_cache(maxsize=8)
def _nutrient_meta(db_path: Path) -> dict[str, dict]:
    """按项目键返回 nutrient 元数据（id/中文名/单位/小数位），供响应标注使用。"""
    meta: dict[str, dict] = {}
    with dbmod.connect(db_path=db_path) as conn:
        rows = conn.execute("SELECT id, name_zh, unit_zh, decimals FROM nutrient").fetchall()
    for row in rows:
        key = NUTRIENT_KEY_BY_ID.get(int(row["id"]))
        if key is not None:
            meta[key] = {
                "nutrient_id": int(row["id"]),
                "name_zh": row["name_zh"],
                "unit_zh": row["unit_zh"],
                "decimals": int(row["decimals"]),
            }
    return meta


def _load_food(fdc_id: int) -> tuple[LocalFood, dict[str, float | None], str, Path]:
    """从只读 USDA 库（先默认库后品牌库）加载食品身份与全部 37 项营养 profile。"""
    row: sqlite3.Row | None = None
    scope = "default"
    with dbmod.connect(db_path=dbmod.default_db_path()) as conn:
        row = dbmod.row(conn, "SELECT * FROM food WHERE fdc_id = ?", (fdc_id,))
    if row is None:
        with dbmod.connect(db_path=dbmod.branded_db_path()) as conn:
            row = dbmod.row(conn, "SELECT * FROM food WHERE fdc_id = ?", (fdc_id,))
            if row is not None:
                scope = "branded"
    if row is None:
        errors.raise_not_found("食品", fdc_id)

    db_path = dbmod.default_db_path() if scope == "default" else dbmod.branded_db_path()
    with dbmod.connect(db_path=db_path) as conn:
        nut_rows = dbmod.rows(
            conn,
            "SELECT nutrient_id, amount FROM food_nutrient WHERE fdc_id = ?",
            (fdc_id,),
        )

    # 全部 37 项的 profile：无行或 amount 为 NULL 均为 None（视为缺失；真实 0 保留为 0）
    profile: dict[str, float | None] = {key: None for key in ALL_NUTRIENT_KEYS}
    for nut in nut_rows:
        key = NUTRIENT_KEY_BY_ID.get(int(nut["nutrient_id"]))
        if key is not None:
            profile[key] = nut["amount"]

    local = LocalFood(
        fdc_id=fdc_id,
        description_en=row["description_en"],
        data_type=row["data_type"],
        gtin_upc=row["gtin_upc"],
        brand_name=row["brand_name"],
    )
    display_name = row["name_zh"] or row["description_en"]
    return local, profile, display_name, db_path


def _to_response(result, fdc_id: int, display_name: str, db_path: Path) -> dict:
    meta = _nutrient_meta(db_path)
    return {
        "fdc_id": fdc_id,
        "display_name": display_name,
        "baseline": "每 100 克",
        "values": [
            {
                "key": v.key,
                "value": v.value,
                "origin": v.origin,
                "status": v.status,
                "usda_value": v.usda_value,
                "source_name": v.source_name,
                "source_url": v.source_url,
                "conversion_method": v.conversion_method,
                "original_basis": v.original_basis,
                "note": v.note,
                "nutrient_id": meta.get(v.key, {}).get("nutrient_id"),
                "name_zh": meta.get(v.key, {}).get("name_zh"),
                "unit_zh": meta.get(v.key, {}).get("unit_zh"),
                "decimals": meta.get(v.key, {}).get("decimals"),
            }
            for v in result.values
        ],
        "missing_keys": result.missing_keys,
        "enrichment": {
            "attempted": result.attempted,
            "outcome": result.outcome,
            "message": result.message,
        },
        "candidates": [
            {
                "source_name": c.source_name,
                "external_name_en": c.external_name_en,
                "match_level": c.match_level,
                "source_url": c.source_url,
                "nutrient_key": c.nutrient_key,
                "note": c.note,
            }
            for c in result.candidates
        ],
        "sources_enabled": result.provider_status,
    }


@router.get("/foods/{fdc_id}/resolved")
def get_resolved(fdc_id: int) -> dict:
    """返回 USDA 原始值 + 已核实外部补充值的统一解析；缺失时按缓存策略自动检索。"""
    local, profile, display_name, db_path = _load_food(fdc_id)
    result = get_service().resolve(local, profile)
    return _to_response(result, fdc_id, display_name, db_path)


@router.post("/foods/{fdc_id}/refresh")
def refresh_resolved(fdc_id: int) -> dict:
    """忽略负缓存强制重新检索（用户主动触发）。"""
    local, profile, display_name, db_path = _load_food(fdc_id)
    result = get_service().resolve(local, profile, force=True)
    return _to_response(result, fdc_id, display_name, db_path)
