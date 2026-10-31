"""外部补全模块配置（环境变量可覆盖）。

密钥只从后端环境变量读取，绝不写入前端或代码仓库。
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_ENRICH_DB = PROJECT_ROOT / "data" / "build" / "meal_canvas_enrichment.sqlite"


def _env_bool(name: str, default: str) -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class EnrichSettings:
    enabled: bool
    db_path: Path
    fdc_api_key: str | None
    fdc_enabled: bool
    off_enabled: bool
    timeout_seconds: float
    max_retries: int
    off_min_interval: float
    fdc_min_interval: float
    negative_ttl_minutes: float
    error_ttl_minutes: float
    max_candidates: int
    # OFF 名称搜索开关：品牌库批量补全时关闭（GTIN 已精确，避免触发 search 端点限流）
    off_name_search: bool = True

    @property
    def fdc_available(self) -> bool:
        return self.enabled and self.fdc_enabled and bool(self.fdc_api_key)

    @property
    def off_available(self) -> bool:
        return self.enabled and self.off_enabled

    def provider_status(self) -> list[dict]:
        """各来源启用状态与不可用原因（中文，直接透出给界面）。"""
        return [
            {
                "name": "usda_fdc",
                "enabled": self.fdc_available,
                "reason": None if self.fdc_available else (
                    "后端未启用外部补全" if not self.enabled
                    else "未配置环境变量 MEAL_CANVAS_FDC_API_KEY，无法访问 USDA FDC API"
                    if not self.fdc_api_key
                    else "USDA FDC 来源已被显式禁用"
                ),
            },
            {
                "name": "openfoodfacts",
                "enabled": self.off_available,
                "reason": None if self.off_available else (
                    "后端未启用外部补全" if not self.enabled
                    else "Open Food Facts 来源已被显式禁用"
                ),
            },
        ]


def load_enrich_settings() -> EnrichSettings:
    db_path = Path(os.environ.get("MEAL_CANVAS_ENRICH_DB_PATH", str(DEFAULT_ENRICH_DB))).expanduser()
    fdc_key = (os.environ.get("MEAL_CANVAS_FDC_API_KEY", "") or "").strip() or None
    return EnrichSettings(
        enabled=_env_bool("MEAL_CANVAS_ENRICH_ENABLED", "true"),
        db_path=db_path,
        fdc_api_key=fdc_key,
        fdc_enabled=_env_bool("MEAL_CANVAS_ENRICH_FDC_ENABLED", "true"),
        off_enabled=_env_bool("MEAL_CANVAS_ENRICH_OFF_ENABLED", "true"),
        timeout_seconds=float(os.environ.get("MEAL_CANVAS_ENRICH_TIMEOUT", "8")),
        max_retries=max(0, int(os.environ.get("MEAL_CANVAS_ENRICH_MAX_RETRIES", "2"))),
        off_min_interval=float(os.environ.get("MEAL_CANVAS_ENRICH_OFF_INTERVAL", "1.0")),
        fdc_min_interval=float(os.environ.get("MEAL_CANVAS_ENRICH_FDC_INTERVAL", "0.5")),
        negative_ttl_minutes=float(os.environ.get("MEAL_CANVAS_ENRICH_NEGATIVE_TTL_MINUTES", str(24 * 60))),
        error_ttl_minutes=float(os.environ.get("MEAL_CANVAS_ENRICH_ERROR_TTL_MINUTES", "10")),
        max_candidates=max(1, int(os.environ.get("MEAL_CANVAS_ENRICH_MAX_CANDIDATES", "5"))),
        off_name_search=_env_bool("MEAL_CANVAS_ENRICH_OFF_NAME_SEARCH", "true"),
    )
