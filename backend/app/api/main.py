"""FastAPI 主入口与中间件。

启动：
    .\\.venv\\Scripts\\python.exe -m uvicorn backend.app.api.main:app --port 8000
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from backend.app.api import db
from backend.app.api.config import load_api_settings
from backend.app.api.errors import DatabaseUnavailableError
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("meal-canvas")


settings = load_api_settings()
db.set_db_paths(settings.db_path, settings.branded_db_path, settings.usage_db_path)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    log.info(
        "Meal Canvas API starting — db=%s, branded=%s, usage=%s, host=%s:%d",
        settings.db_path,
        settings.branded_db_path,
        settings.usage_db_path,
        settings.host,
        settings.port,
    )
    yield


app = FastAPI(
    title="Meal Canvas 营养餐盘设计师 API",
    version="0.1.0",
    description=(
        "只读 USDA 食品数据查询 API，并额外提供独立的每周膳食计划存储。"
        "计划数据写入独立应用数据库，不写入 USDA 食品库；"
        "餐盘方案仍保存在浏览器 IndexedDB。"
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


@app.exception_handler(DatabaseUnavailableError)
async def _db_unavailable_handler(_req: Request, exc: DatabaseUnavailableError) -> JSONResponse:
    log.warning("Database unavailable: %s", exc)
    return JSONResponse(
        status_code=503,
        content={"code": "DATABASE_UNAVAILABLE", "message": str(exc)},
    )


@app.exception_handler(Exception)
async def _generic_handler(_req: Request, exc: Exception) -> JSONResponse:
    log.exception("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"code": "INTERNAL_ERROR", "message": "服务内部错误，请查看日志。"},
    )


# 引入路由
from backend.app.api.routers import (  # noqa: E402  需要在 settings/db 之后
    categories,
    enrichment,
    foods,
    health,
    nutrients,
    planner,
)

app.include_router(health.router)
app.include_router(foods.router)
app.include_router(nutrients.router)
app.include_router(categories.router)
app.include_router(enrichment.router)
app.include_router(planner.router)
