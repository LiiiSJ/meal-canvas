"""FNDDS / Survey Foods 适配器。

关键陷阱：food_nutrient.nutrient_id 存的是传统编号 nutrient_nbr（如 301、208），
必须经 nutrient.csv 的 nutrient_nbr → nutrient.id 映射，不能按 FDC ID 直读。
分类直接取 food.food_category_id（即 WWEIA 类别代码）。
"""
from __future__ import annotations

import logging
from collections.abc import Iterator

from backend.app.etl.archive import open_csv, read_rows
from backend.app.etl.base import FoodRow, NutrientRow, PortionRow, SourceAdapter, clean_text, parse_amount
from backend.app.etl.nutrients import build_nbr_map, load_nutrient_defs
from backend.app.etl.sources.common import iter_portion_rows, iter_raw_nutrient_rows, load_measure_units

DATA_TYPE = "survey_fndds_food"
logger = logging.getLogger(__name__)


class SurveyAdapter(SourceAdapter):
    key = "survey"
    library_scope = "default"

    def __init__(self, settings):
        super().__init__(settings)
        self._defs = load_nutrient_defs(self.zip_path)
        self._nbr_to_id = build_nbr_map(self._defs)
        self._wweia = {
            r["wweia_food_category"]: r["wweia_food_category_description"]
            for r in read_rows(self.zip_path, "wweia_food_category.csv")
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
                yield FoodRow(
                    fdc_id=fdc_id,
                    data_type=DATA_TYPE,
                    description_en=(row.get("description") or "").strip(),
                    category_source="wweia",
                    category_code=cat_text,
                    category_en=self._wweia.get(cat_text) if cat_text else None,
                    publication_date=clean_text(row.get("publication_date")),
                    source_dataset=self.dataset_name,
                    source_version=self.version,
                    library_scope=self.library_scope,
                    is_default_library=1,
                )

    def iter_nutrients(self, ids: set[int] | None = None) -> Iterator[NutrientRow]:
        for row in iter_raw_nutrient_rows(self.zip_path, ids):
            raw_id = (row.get("nutrient_id") or "").strip()
            canonical = self._nbr_to_id.get(raw_id)
            amount_text = row.get("amount") or ""
            if canonical is None:
                logger.debug("FNDDS 传统编号无法映射：%s", raw_id)
            yield NutrientRow(
                fdc_id=int(row["fdc_id"]),
                nutrient_id=canonical,
                raw_nutrient_id=raw_id,
                amount_raw=parse_amount(amount_text).value,
                amount_text=amount_text,
                data_points=(row.get("data_points") or "").strip(),
            )

    def iter_portions(self, ids: set[int] | None = None) -> Iterator[PortionRow]:
        yield from iter_portion_rows(self.zip_path, ids, self._units)
