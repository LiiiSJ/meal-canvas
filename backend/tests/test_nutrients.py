"""营养规范化规则的纯函数测试。"""
from __future__ import annotations

from backend.app.etl.base import NutrientRow
from backend.app.etl.nutrients import (
    build_nbr_map,
    load_nutrient_defs,
    normalize_row,
    resolve_energy,
)


def test_energy_priority_prefers_1008():
    result = resolve_energy({1008: 34.0, 2048: 33.0, 2047: 32.0})
    assert result.nutrient_id == 1008
    assert result.value == 34.0
    assert result.quality_flag == "ok"
    assert result.conflict is True


def test_energy_falls_back_to_2048_then_2047():
    assert resolve_energy({2048: 33.0, 2047: 32.0}).nutrient_id == 2048
    assert resolve_energy({2047: 32.0}).nutrient_id == 2047


def test_energy_ignores_empty_higher_priority():
    result = resolve_energy({1008: None, 2048: 33.0})
    assert result.nutrient_id == 2048
    assert result.value == 33.0


def test_energy_missing_returns_no_value():
    result = resolve_energy({})
    assert result.nutrient_id is None
    assert result.value is None
    assert result.quality_flag == "missing"


def test_energy_negative_is_flagged_not_zeroed():
    result = resolve_energy({1008: -5.0})
    assert result.nutrient_id == 1008
    assert result.value is None
    assert result.quality_flag == "negative"


def test_nbr_map_maps_traditional_numbers():
    defs = {
        1008: type("D", (), {"id": 1008, "nbr": "208"})(),
        1087: type("D", (), {"id": 1087, "nbr": "301"})(),
    }
    mapping = build_nbr_map(defs)
    assert mapping["208"] == 1008
    assert mapping["301"] == 1087


def test_load_nutrient_defs_from_synthetic_zip(synthetic_env):
    from backend.app.core.config import load_settings

    defs = load_nutrient_defs(load_settings().zip_path("survey"))
    assert defs[1008].nbr == "208"
    assert defs[1062].unit_name == "kJ"


def _row(nutrient_id, amount_text):
    return NutrientRow(
        fdc_id=1,
        nutrient_id=nutrient_id,
        raw_nutrient_id=str(nutrient_id),
        amount_raw=None,
        amount_text=amount_text,
    )


def test_normalize_row_keeps_missing_absent():
    allowed = frozenset({1003})
    nutrient_id, value, flag = normalize_row(_row(1003, ""), allowed, {1003: "G"})
    assert (nutrient_id, value, flag) == (1003, None, "missing")


def test_normalize_row_flags_negative():
    allowed = frozenset({1005})
    nutrient_id, value, flag = normalize_row(_row(1005, "-1.0"), allowed, {1005: "G"})
    assert (nutrient_id, value, flag) == (1005, None, "negative")


def test_normalize_row_unknown_unit():
    allowed = frozenset({1003})
    nutrient_id, value, flag = normalize_row(_row(1003, "5"), allowed, {1003: "PH"})
    assert (nutrient_id, value, flag) == (1003, None, "unit_unknown")


def test_normalize_row_unmapped():
    allowed = frozenset({1003})
    nutrient_id, value, flag = normalize_row(_row(2066, "5"), allowed, {2066: "G"})
    assert nutrient_id is None
    assert flag == "unmapped_nutrient"
