"""适配器统一接口与基础数据结构。

每个数据源实现自己的字段语义，禁止用一个通用脚本假定四套数据同构。
"""
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from backend.app.core.config import SOURCES, Settings


@dataclass(frozen=True)
class NutrientDef:
    id: int
    nbr: str
    name_en: str
    unit_name: str
    rank: float | None


@dataclass
class FoodRow:
    fdc_id: int
    data_type: str
    description_en: str
    category_source: str
    category_code: str | None
    category_en: str | None
    publication_date: str | None
    source_dataset: str
    source_version: str
    library_scope: str
    is_default_library: int
    brand_owner: str | None = None
    brand_name: str | None = None
    gtin_upc: str | None = None
    serving_size: float | None = None
    serving_unit: str | None = None
    household_serving: str | None = None
    ingredients_en: str | None = None


@dataclass
class NutrientRow:
    fdc_id: int
    nutrient_id: int | None
    raw_nutrient_id: str
    amount_raw: float | None
    amount_text: str
    data_points: str = ""
    extra: dict = field(default_factory=dict)


@dataclass
class PortionRow:
    fdc_id: int
    amount: float | None
    modifier: str | None
    portion_description: str | None
    gram_weight: float | None
    unit_name: str | None
    quality_flag: str


@dataclass(frozen=True)
class AmountParse:
    value: float | None
    status: str  # ok / empty / invalid / nonfinite


def parse_amount(text: str | None) -> AmountParse:
    """解析 CSV 中的 amount，空值保持缺失，非法值不猜测。"""
    if text is None or text.strip() == "":
        return AmountParse(None, "empty")
    try:
        value = float(text)
    except ValueError:
        return AmountParse(None, "invalid")
    if not math.isfinite(value):
        return AmountParse(None, "nonfinite")
    return AmountParse(value, "ok")


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


class SourceAdapter(ABC):
    """四个数据集适配器的统一只读接口。"""

    key: str
    library_scope: str

    def __init__(self, settings: Settings):
        self.settings = settings
        self.source = SOURCES[self.key]

    @property
    def zip_path(self) -> Path:
        return self.settings.zip_path(self.key)

    @property
    def dataset_name(self) -> str:
        return self.source.dataset_name

    @property
    def version(self) -> str:
        return self.source.version

    @abstractmethod
    def iter_foods(self, ids: set[int] | None = None) -> Iterator[FoodRow]:
        """产出食品主表记录；ids 为 None 表示全量。"""

    @abstractmethod
    def iter_nutrients(self, ids: set[int] | None = None) -> Iterator[NutrientRow]:
        """产出每 100g 营养行，nutrient_id 已按数据集语义归一为规范 ID。"""

    @abstractmethod
    def iter_portions(self, ids: set[int] | None = None) -> Iterator[PortionRow]:
        """产出份量行；品牌数据源没有 food_portion.csv，返回空迭代。"""

    def estimated_rows(self, filename: str) -> int:
        """返回 CSV 行数估计，用于日志与进度；无统计时返回 0。"""
        return 0
