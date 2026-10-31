"""健康检查。"""
from __future__ import annotations

from backend.app.api import db as dbmod
from fastapi import APIRouter

router = APIRouter(prefix="/api/health", tags=["健康检查"])


@router.get("")
def health() -> dict:
    db_path = dbmod.default_db_path()
    branded_path = dbmod.branded_db_path()
    status = "ok"
    db_ok = db_path.is_file()
    branded_ok = branded_path.is_file() if branded_path != db_path else db_ok
    error_msg: str | None = None
    if not db_ok:
        status = "degraded"
        error_msg = f"默认数据库不存在：{db_path}"

    food_count = None
    nutrient_count = None
    if db_ok:
        try:
            with dbmod.connect() as conn:
                food_count = dbmod.count(conn, "SELECT COUNT(*) FROM food")
                nutrient_count = dbmod.count(conn, "SELECT COUNT(*) FROM food_nutrient")
        except Exception as exc:
            status = "error"
            error_msg = f"数据库无法查询：{exc}"

    return {
        "status": status,
        "default_db_exists": db_ok,
        "branded_db_exists": branded_ok,
        "default_db_path": str(db_path),
        "branded_db_path": str(branded_path),
        "food_count": food_count,
        "nutrient_row_count": nutrient_count,
        "error": error_msg,
    }
