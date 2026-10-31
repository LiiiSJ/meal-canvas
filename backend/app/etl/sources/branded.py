"""Branded Foods 适配器。

- 只取 data_type='branded_food'，写入独立品牌库。
- 分类取 branded_food.csv 的 branded_food_category（food.food_category_id 全为空）。
- 没有 food_portion.csv，份量只读标签字段，绝不伪造克重。
- 商品名、品牌名保留英文，不做机器翻译。
"""
from __future__ import annotations

import logging
from collections.abc import Iterator

from backend.app.etl.archive import open_csv
from backend.app.etl.base import FoodRow, NutrientRow, PortionRow, SourceAdapter, clean_text, parse_amount
from backend.app.etl.sources.common import iter_raw_nutrient_rows

DATA_TYPE = "branded_food"
logger = logging.getLogger(__name__)


class BrandedAdapter(SourceAdapter):
    key = "branded"
    library_scope = "branded"

    def _load_meta(self, ids: set[int] | None) -> dict[int, dict[str, str]]:
        """流式读取 branded_food.csv，只为需要的 fdc_id 保留标签字段。"""
        meta: dict[int, dict[str, str]] = {}
        with open_csv(self.zip_path, "branded_food.csv") as reader:
            for row in reader:
                fid_text = (row.get("fdc_id") or "").strip()
                if not fid_text.isdigit():
                    continue
                fdc_id = int(fid_text)
                if ids is not None and fdc_id not in ids:
                    continue
                meta[fdc_id] = row
                if ids is not None and len(meta) == len(ids):
                    break
        return meta

    def iter_foods(self, ids: set[int] | None = None) -> Iterator[FoodRow]:
        meta = self._load_meta(ids)
        with open_csv(self.zip_path, "food.csv") as reader:
            for row in reader:
                if (row.get("data_type") or "").strip() != DATA_TYPE:
                    continue
                fdc_id = int(row["fdc_id"])
                if ids is not None and fdc_id not in ids:
                    continue
                label = meta.get(fdc_id, {})
                serving = parse_amount(label.get("serving_size"))
                yield FoodRow(
                    fdc_id=fdc_id,
                    data_type=DATA_TYPE,
                    description_en=(row.get("description") or "").strip(),
                    category_source="branded",
                    category_code=None,
                    category_en=clean_text(label.get("branded_food_category")),
                    publication_date=clean_text(row.get("publication_date")),
                    source_dataset=self.dataset_name,
                    source_version=self.version,
                    library_scope=self.library_scope,
                    is_default_library=0,
                    brand_owner=clean_text(label.get("brand_owner")),
                    brand_name=clean_text(label.get("brand_name")),
                    gtin_upc=clean_text(label.get("gtin_upc")),
                    serving_size=serving.value,
                    serving_unit=clean_text(label.get("serving_size_unit")),
                    household_serving=clean_text(label.get("household_serving_fulltext")),
                    ingredients_en=clean_text(label.get("ingredients")),
                )

    def iter_nutrients(self, ids: set[int] | None = None) -> Iterator[NutrientRow]:
        for row in iter_raw_nutrient_rows(self.zip_path, ids):
            raw_id = (row.get("nutrient_id") or "").strip()
            amount_text = row.get("amount") or ""
            yield NutrientRow(
                fdc_id=int(row["fdc_id"]),
                nutrient_id=int(raw_id) if raw_id.isdigit() else None,
                raw_nutrient_id=raw_id,
                amount_raw=parse_amount(amount_text).value,
                amount_text=amount_text,
                data_points=(row.get("data_points") or "").strip(),
            )

    def iter_portions(self, ids: set[int] | None = None) -> Iterator[PortionRow]:
        """Branded 没有 food_portion.csv，返回空迭代。"""
        if False:  # pragma: no cover - 保持生成器签名
            yield PortionRow(0, None, None, None, None, None, "amount_missing")
