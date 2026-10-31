"""API 错误映射与响应。

所有错误消息都是中文，status_code 由 HTTPException 抛出。
"""
from __future__ import annotations

from fastapi import HTTPException, status


class DatabaseUnavailableError(RuntimeError):
    """数据库文件不存在或不可读；消息为中文。"""


def raise_not_found(resource: str, key: str | int) -> None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "NOT_FOUND", "message": f"未找到{resource}：{key}"},
    )


def raise_bad_request(message: str, *, code: str = "BAD_REQUEST") -> None:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"code": code, "message": message},
    )


def raise_internal_error(message: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"code": "INTERNAL_ERROR", "message": message},
    )


def raise_db_unavailable(path_text: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "code": "DATABASE_UNAVAILABLE",
            "message": f"数据库不可用：{path_text}。请先运行 sample 或 full 构建，然后启动后端。",
        },
    )
