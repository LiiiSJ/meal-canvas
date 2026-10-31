"""Foundation Foods 适配器。

只接收 food.csv 中 data_type='foundation_food' 的 469 条真实食品；
禁止使用 foundation_food.csv（仅 395 行）作为白名单。
"""
from __future__ import annotations

from collections.abc import Iterator

from backend.app.etl.archive import open_csv, read_rows
from backend.app.etl.base import FoodRow, NutrientRow, PortionRow, SourceAdapter, clean_text, parse_amount
from backend.app.etl.sources.common import (
    iter_portion_rows,
    iter_raw_nutrient_rows,
    load_measure_units,
)

DATA_TYPE = "foundation_food"


class FoundationAdapter(SourceAdapter):
    key = "foundation"
    library_scope = "default"

    def __init__(self, settings):
        super().__init__(settings)
        self._categories = {
            int(r["id"]): (r["code"], r["description"])
            for r in read_rows(self.zip_path, "food_category.csv")
        }
        self._units = load_measure_units(self.zip_path)

    def iter_foods(self, ids: set[int] | None = None) -> Iterator[FoodRow]:
        with open_csv(self.zip_path, "food.csv") as reader:
            for row in reader:
                if (row.get("data_type") or "").strip() != DATA_TYPE:
                    continue
                fdc_id = int(row["fdc_id"])
                if ids is not None and fdc_id not in ids:
                    continue
                cat_text = clean_text(row.get("food_category_id"))
                cat_code, cat_en = self._categories.get(int(cat_text), (None, None)) if cat_text else (None, None)
                yield FoodRow(
                    fdc_id=fdc_id,
                    data_type=DATA_TYPE,
                    description_en=(row.get("description") or "").strip(),
                    category_source="fdc",
                    category_code=cat_text,
                    category_en=cat_en,
                    publication_date=clean_text(row.get("publication_date")),
                    source_dataset=self.dataset_name,
                    source_version=self.version,
                    library_scope=self.library_scope,
                    is_default_library=1,
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
        yield from iter_portion_rows(self.zip_path, ids, self._units)
