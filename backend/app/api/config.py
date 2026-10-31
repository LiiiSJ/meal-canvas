"""后端全局配置（环境变量可覆盖）。"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_DB = PROJECT_ROOT / "data" / "build" / "meal_canvas.sqlite"
DEFAULT_BRANDED_DB = PROJECT_ROOT / "data" / "build" / "meal_canvas_branded.sqlite"
DEFAULT_USAGE_DB = PROJECT_ROOT / "data" / "build" / "meal_canvas_usage.sqlite"


@dataclass(frozen=True)
class AppSettings:
    db_path: Path
    branded_db_path: Path
    usage_db_path: Path
    host: str
    port: int
    cors_origins: tuple[str, ...]
    default_page_size: int
    max_page_size: int

    def db_exists(self) -> bool:
        return self.db_path.is_file()

    def branded_db_exists(self) -> bool:
        return self.branded_db_path.is_file()

    def usage_db_exists(self) -> bool:
        return self.usage_db_path.is_file()


def load_api_settings() -> AppSettings:
    db_path = Path(os.environ.get("MEAL_CANVAS_DB_PATH_API", str(DEFAULT_DB))).expanduser()
    branded_db_path = Path(os.environ.get("MEAL_CANVAS_BRANDED_DB_PATH_API", str(DEFAULT_BRANDED_DB))).expanduser()
    usage_db_path = Path(os.environ.get("MEAL_CANVAS_USAGE_DB_PATH_API", str(DEFAULT_USAGE_DB))).expanduser()
    host = os.environ.get("MEAL_CANVAS_HOST", "127.0.0.1")
    port = int(os.environ.get("MEAL_CANVAS_PORT", "8000"))
    cors_raw = os.environ.get("MEAL_CANVAS_CORS", "")
    cors = tuple(o.strip() for o in cors_raw.split(",") if o.strip()) if cors_raw else ("http://localhost:5173",)
    return AppSettings(
        db_path=db_path,
        branded_db_path=branded_db_path,
        usage_db_path=usage_db_path,
        host=host,
        port=port,
        cors_origins=cors,
        default_page_size=20,
        max_page_size=100,
    )
