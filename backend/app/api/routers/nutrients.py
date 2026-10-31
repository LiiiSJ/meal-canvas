"""营养指标元数据。"""
from __future__ import annotations

from backend.app.api import db as dbmod
from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/metadata/nutrients", tags=["元数据"])


@router.get("")
def list_nutrients(
    is_core: bool | None = Query(default=None, description="是否核心营养素"),
) -> dict:
    with dbmod.connect() as conn:
        if is_core is None:
            rows = dbmod.rows(conn, "SELECT * FROM nutrient ORDER BY rank ASC, id ASC")
        else:
            rows = dbmod.rows(
                conn, "SELECT * FROM nutrient WHERE is_core = ? ORDER BY rank ASC, id ASC", (1 if is_core else 0,)
            )
    return {
        "total": len(rows),
        "items": [
            {
                "nutrient_id": r["id"],
                "nbr": r["nbr"],
                "name_en": r["name_en"],
                "name_zh": r["name_zh"],
                "unit_en": r["unit_name"],
                "unit_zh": r["unit_zh"],
                "group_zh": r["group_zh"],
                "decimals": r["decimals"],
                "is_core": bool(r["is_core"]),
                "baseline": "每 100 克（部分来源如 Branded 以外包装为基准）",
            }
            for r in rows
        ],
    }
