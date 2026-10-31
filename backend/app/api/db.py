"""SQLite 连接与只读查询封装。

所有查询只打默认库 meal_canvas.sqlite（不含品牌库），品牌库按需单独查。
"""
from __future__ import annotations

import logging
import sqlite3
import threading
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path

from backend.app.api.errors import DatabaseUnavailableError

log = logging.getLogger(__name__)

_lock = threading.Lock()
_default_db_path: Path | None = None
_branded_db_path: Path | None = None
_usage_db_path: Path | None = None


def set_db_paths(default_db: Path, branded_db: Path, usage_db: Path | None = None) -> None:
    """启动时由 main.py 调用一次。"""
    global _default_db_path, _branded_db_path, _usage_db_path
    _default_db_path = default_db
    _branded_db_path = branded_db
    _usage_db_path = usage_db


@contextmanager
def connect(db_path: Path | None = None, readonly: bool = True) -> Iterator[sqlite3.Connection]:
    path = db_path or _default_db_path
    if path is None or not path.is_file():
        raise DatabaseUnavailableError(f"数据库不存在：{path}")
    with _lock:
        conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    if readonly:
        conn.execute("PRAGMA query_only=ON")
    try:
        yield conn
    finally:
        conn.close()


def default_db_path() -> Path:
    if _default_db_path is None:
        raise DatabaseUnavailableError("后端尚未配置数据库路径")
    return _default_db_path


def branded_db_path() -> Path:
    if _branded_db_path is None:
        raise DatabaseUnavailableError("后端尚未配置品牌数据库路径")
    return _branded_db_path


def usage_db_path() -> Path:
    if _usage_db_path is None:
        raise DatabaseUnavailableError(
            "后端尚未配置用途分类数据库路径。请设置 MEAL_CANVAS_USAGE_DB_PATH_API，"
            "或运行 python -m backend.app.usage.build --mode full --confirm-full 生成正式用途库。"
        )
    return _usage_db_path


def attach_usage(conn: sqlite3.Connection) -> None:
    """把用途分类库以只读方式挂到当前连接（别名 usage）。

    缺库时抛中文错误，避免把“未分类”误当成“不属于食材”。
    """
    path = usage_db_path()
    if not path.is_file():
        raise DatabaseUnavailableError(
            f"用途分类数据库不存在：{path}。请先运行"
            " python -m backend.app.usage.build --mode full --confirm-full 生成正式用途库，"
            "再用 MEAL_CANVAS_USAGE_DB_PATH_API 指向该文件。"
        )
    conn.execute("ATTACH DATABASE ? AS usage", (str(path),))


def count(conn: sqlite3.Connection, sql: str, params: Iterable = ()) -> int:
    """执行 SELECT COUNT(*) 并返回整数。"""
    row = conn.execute(sql, tuple(params)).fetchone()
    return int(row[0]) if row else 0


def rows(conn: sqlite3.Connection, sql: str, params: Iterable = ()) -> list[sqlite3.Row]:
    return conn.execute(sql, tuple(params)).fetchall()


def row(conn: sqlite3.Connection, sql: str, params: Iterable = ()) -> sqlite3.Row | None:
    return conn.execute(sql, tuple(params)).fetchone()
