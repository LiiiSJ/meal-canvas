"""四个数据源适配器的语义测试。"""
from __future__ import annotations

from backend.app.core.config import load_settings
from backend.app.etl.sources import ADAPTERS


def _adapter(key: str):
    return ADAPTERS[key](load_settings())


def test_foundation_filters_by_data_type(synthetic_env):
    foods = list(_adapter("foundation").iter_foods())
    ids = {food.fdc_id for food in foods}
    assert ids == {1001, 1002}
    assert all(food.data_type == "foundation_food" for food in foods)


def test_foundation_categories_resolved(synthetic_env):
    foods = {food.fdc_id: food for food in _adapter("foundation").iter_foods()}
    assert foods[1001].category_code == "11"
    assert foods[1001].category_en == "Vegetables and Vegetable Products"


def test_survey_maps_traditional_nutrient_numbers(synthetic_env):
    adapter = _adapter("survey")
    rows = {row.raw_nutrient_id: row for row in adapter.iter_nutrients({6001})}
    assert rows["208"].nutrient_id == 1008
    assert rows["203"].nutrient_id == 1003


def test_survey_food_has_wweia_category(synthetic_env):
    foods = {food.fdc_id: food for food in _adapter("survey").iter_foods()}
    assert foods[6001].category_source == "wweia"
    assert foods[6001].category_code == "6407"


def test_branded_has_no_portions_and_keeps_label_fields(synthetic_env):
    adapter = _adapter("branded")
    assert list(adapter.iter_portions()) == []
    foods = {food.fdc_id: food for food in adapter.iter_foods({5001, 5003})}
    assert foods[5001].gtin_upc == "GTIN-A"
    assert foods[5001].serving_unit == "g"
    assert foods[5003].serving_unit == "ml"
    assert foods[5001].is_default_library == 0
    assert foods[5001].library_scope == "branded"


def test_portion_quality_flags(synthetic_env):
    portions = list(_adapter("foundation").iter_portions({1001, 1002}))
    by_food = {}
    for portion in portions:
        by_food.setdefault(portion.fdc_id, []).append(portion)
    assert by_food[1001][0].quality_flag == "ok"
    flags = {p.quality_flag for p in by_food[1002]}
    assert flags == {"amount_missing", "zero_weight"}
