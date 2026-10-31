"""项目配置与路径安全校验。

所有路径均以项目根目录为基准，可通过环境变量覆盖。
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

DATA_DIR_ENV = "MEAL_CANVAS_DATA_DIR"
DB_PATH_ENV = "MEAL_CANVAS_DB_PATH"
BRANDED_DB_PATH_ENV = "MEAL_CANVAS_BRANDED_DB_PATH"
SAMPLE_DIR_ENV = "MEAL_CANVAS_SAMPLE_DIR"

DEFAULT_DATA_DIR = PROJECT_ROOT.parent / "数据集"
FORMAL_DB = PROJECT_ROOT / "data" / "build" / "meal_canvas.sqlite"
FORMAL_BRANDED_DB = PROJECT_ROOT / "data" / "build" / "meal_canvas_branded.sqlite"
SAMPLE_DIR = PROJECT_ROOT / "data" / "build" / "sample"


class ConfigError(RuntimeError):
    """配置或路径不满足要求时抛出，消息为中文。"""


@dataclass(frozen=True)
class SourceFile:
    key: str
    dataset_name: str
    version: str
    zip_name: str


SOURCES: dict[str, SourceFile] = {
    "foundation": SourceFile(
        key="foundation",
        dataset_name="Foundation Foods",
        version="2026-04",
        zip_name="FoodData_Central_foundation_food_csv_2026-04-30.zip",
    ),
    "sr_legacy": SourceFile(
        key="sr_legacy",
        dataset_name="SR Legacy",
        version="2018-04",
        zip_name="FoodData_Central_sr_legacy_food_csv_2018-04.zip",
    ),
    "survey": SourceFile(
        key="survey",
        dataset_name="FNDDS / Survey Foods",
        version="2024-10（数据期 2021–2023）",
        zip_name="FoodData_Central_survey_food_csv_2024-10-31.zip",
    ),
    "branded": SourceFile(
        key="branded",
        dataset_name="Branded Foods",
        version="2026-04",
        zip_name="FoodData_Central_branded_food_csv_2026-04-30.zip",
    ),
}

DEFAULT_LIBRARY_SOURCES = ("foundation", "sr_legacy", "survey")
BRANDED_LIBRARY_SOURCES = ("branded",)


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    formal_db: Path
    formal_branded_db: Path
    sample_dir: Path

    def zip_path(self, key: str) -> Path:
        return self.data_dir / SOURCES[key].zip_name


def load_settings() -> Settings:
    data_dir = Path(os.environ.get(DATA_DIR_ENV, DEFAULT_DATA_DIR)).expanduser()
    formal_db = Path(os.environ.get(DB_PATH_ENV, FORMAL_DB)).expanduser()
    formal_branded_db = Path(os.environ.get(BRANDED_DB_PATH_ENV, FORMAL_BRANDED_DB)).expanduser()
    sample_dir = Path(os.environ.get(SAMPLE_DIR_ENV, SAMPLE_DIR)).expanduser()
    return Settings(
        data_dir=data_dir,
        formal_db=formal_db,
        formal_branded_db=formal_branded_db,
        sample_dir=sample_dir,
    )


def validate_data_dir(settings: Settings) -> dict[str, Path]:
    """校验原始数据目录与四个 ZIP 是否存在，缺失时抛出中文错误。"""
    if not settings.data_dir.exists():
        raise ConfigError(
            f"原始数据目录不存在：{settings.data_dir}。"
            f"请将四个 USDA ZIP 放入该目录，或用环境变量 {DATA_DIR_ENV} 指定实际目录。"
        )
    resolved: dict[str, Path] = {}
    missing: list[str] = []
    for key, source in SOURCES.items():
        path = settings.zip_path(key)
        if path.is_file():
            resolved[key] = path
        else:
            missing.append(f"{source.zip_name}（期望路径：{path}）")
    if missing:
        raise ConfigError(
            "原始数据文件缺失，无法继续：" + "；".join(missing)
            + f"。请确认目录 {settings.data_dir} 中含有四个 ZIP，且未被改名。"
        )
    return resolved


def resolve_library_paths(settings: Settings, mode: str, library: str) -> tuple[Path, Path]:
    """返回（输出目录，数据库路径），并阻止 sample 与正式库路径混用。"""
    if mode not in {"sample", "full"}:
        raise ConfigError(f"未知构建模式：{mode}。必须显式指定 --mode sample 或 --mode full。")
    if library not in {"default", "branded"}:
        raise ConfigError(f"未知库类型：{library}。只能是 default 或 branded。")

    if mode == "sample":
        out_dir = settings.sample_dir
        db_path = out_dir / ("meal_canvas_branded.sqlite" if library == "branded" else "meal_canvas.sqlite")
    else:
        out_dir = settings.formal_db.parent
        db_path = settings.formal_branded_db if library == "branded" else settings.formal_db

    formal_paths = {settings.formal_db.resolve(), settings.formal_branded_db.resolve()}
    if mode == "sample" and db_path.resolve() in formal_paths:
        raise ConfigError("拒绝执行：sample 输出路径与正式数据库路径相同，会覆盖正式库。")
    if mode == "full" and out_dir.resolve() == settings.sample_dir.resolve():
        raise ConfigError("拒绝执行：full 模式输出目录与 sample 目录相同。")
    return out_dir, db_path
