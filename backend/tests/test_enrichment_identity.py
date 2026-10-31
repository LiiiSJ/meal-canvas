"""身份匹配评分与营养键映射（含单位/计量基准校验）单元测试。"""
from __future__ import annotations

from backend.app.enrichment.identity import ExternalFood, LocalFood, score_match
from backend.app.enrichment.mapper import (
    STATUS_CANDIDATE,
    STATUS_REJECTED,
    STATUS_VERIFIED,
    map_fdc_food,
    map_off_product,
)

LOCAL = LocalFood(fdc_id=1001, description_en="Egg, white, raw", data_type="foundation_food")


def _ext(name: str, payload: dict | None = None, gtin: str | None = None, provider: str = "usda_fdc") -> ExternalFood:
    return ExternalFood(
        provider=provider,
        external_id="9001",
        name_en=name,
        source_url="https://example.org/9001",
        payload=payload or {},
        gtin_upc=gtin,
    )


# ---------------------------------------------------------------- 身份匹配


def test_exact_identical_description():
    m = score_match(LOCAL, _ext("Egg, white, raw"))
    assert m.level == "exact"


def test_exact_by_gtin_even_if_name_differs():
    local = LocalFood(fdc_id=5001, description_en="Brand cheese A", data_type="branded_food", gtin_upc="03017620422003")
    m = score_match(local, _ext("Some other display name", gtin="3017620422003".zfill(14)))
    assert m.level == "exact"
    assert m.evidence["method"] == "gtin"


def test_gtin_upc_a_matches_ean13_with_leading_zero():
    """真实场景：USDA 库存 UPC-A 12 位，OFF 存 EAN-13 13 位（前导 0）。"""
    local = LocalFood(
        fdc_id=408968, description_en="STIR-FRY TERIYAKI SAUCE",
        data_type="branded_food", gtin_upc="075050006128",
    )
    m = score_match(local, _ext("Korean teriyaki stirfry sauce", gtin="0075050006128"))
    assert m.level == "exact"
    assert m.evidence["method"] == "gtin"


def test_state_conflict_never_exact():
    """生食 vs 熟食：即使名称几乎一致也只允许 similar。"""
    m = score_match(LOCAL, _ext("Egg, white, cooked"))
    assert m.level in ("similar", "partial")
    assert m.level != "exact"


def test_partial_overlap_is_candidate_only():
    m = score_match(LOCAL, _ext("Egg product, white liquid"))
    assert m.level in ("similar", "partial")


def test_no_overlap_discarded():
    m = score_match(LOCAL, _ext("Beef, chuck, braised"))
    assert m.level == "none"


# ---------------------------------------------------------------- FDC 映射


def test_fdc_energy_priority_1008_over_2048_2047():
    """能量按 1008 → 2048 → 2047 取唯一值；kJ 绝不并入。"""
    mapped = map_fdc_food({
        "foodNutrients": [
            {"nutrientId": 2047, "nutrientName": "Energy (Atwater General Factors)", "unitName": "KCAL", "value": 32},
            {"nutrientId": 1008, "nutrientName": "Energy", "unitName": "KCAL", "value": 34},
            {"nutrientId": 2048, "nutrientName": "Energy (Atwater Specific Factors)", "unitName": "KCAL", "value": 33},
            {"nutrientId": 1062, "nutrientName": "Energy", "unitName": "kJ", "value": 142},
        ]
    })
    assert mapped["energy_kcal"].status == STATUS_VERIFIED
    assert mapped["energy_kcal"].value_per_100g == 34


def test_fdc_kj_only_energy_is_candidate():
    mapped = map_fdc_food({
        "foodNutrients": [
            {"nutrientId": 1062, "nutrientName": "Energy", "unitName": "kJ", "value": 142},
        ]
    })
    assert mapped["energy_kcal"].status == STATUS_CANDIDATE
    assert mapped["energy_kcal"].value_per_100g is None


def test_fdc_sodium_unit_and_missing_entries():
    mapped = map_fdc_food({
        "foodNutrients": [
            {"nutrientId": 1093, "nutrientName": "Sodium, Na", "unitName": "MG", "value": 166},
            {"nutrientId": 1003, "nutrientName": "Protein", "unitName": "G", "value": 10.9},
        ]
    })
    assert mapped["sodium_mg"].status == STATUS_VERIFIED
    assert mapped["sodium_mg"].value_per_100g == 166
    assert mapped["protein_g"].value_per_100g == 10.9
    assert "fiber_g" not in mapped


def test_fdc_unknown_unit_rejected():
    mapped = map_fdc_food({
        "foodNutrients": [
            {"nutrientId": 1093, "nutrientName": "Sodium, Na", "unitName": "PPM", "value": 166},
        ]
    })
    assert mapped["sodium_mg"].status == STATUS_REJECTED


def test_fdc_negative_value_rejected():
    mapped = map_fdc_food({
        "foodNutrients": [
            {"nutrientId": 1005, "nutrientName": "Carbohydrate, by difference", "unitName": "G", "value": -1},
        ]
    })
    assert mapped["carb_g"].status == STATUS_REJECTED


# ---------------------------------------------------------------- OFF 映射


def test_off_basic_mapping_with_sodium_unit_conversion():
    """OFF sodium_100g 常以 g 计，必须显式 ×1000 转 mg；fiber 0 是真实零值。"""
    mapped = map_off_product({
        "nutriments": {
            "energy-kcal_100g": 539,
            "proteins_100g": 6.3,
            "fat_100g": 30.9,
            "carbohydrates_100g": 57.5,
            "sugars_100g": 56.3,
            "fiber_100g": 0,
            "sodium_100g": 0.0428,
            "sodium_unit": "g",
        }
    })
    assert mapped["energy_kcal"].value_per_100g == 539
    assert mapped["sodium_mg"].status == STATUS_VERIFIED
    assert abs(mapped["sodium_mg"].value_per_100g - 42.8) < 1e-9
    assert "×1000" in (mapped["sodium_mg"].conversion_method or "")
    assert mapped["fiber_g"].status == STATUS_VERIFIED
    assert mapped["fiber_g"].value_per_100g == 0


def test_off_gram_serving_basis_converts():
    mapped = map_off_product({
        "nutriments": {
            "fiber_serving": 2.0,
            "serving_quantity": 40,
            "serving_unit": "g",
        }
    })
    assert mapped["fiber_g"].status == STATUS_VERIFIED
    assert abs(mapped["fiber_g"].value_per_100g - 5.0) < 1e-9
    assert "40 g" in (mapped["fiber_g"].conversion_method or "")


def test_off_ml_serving_rejected():
    """份量以 ml 计且无可靠密度数据：不换算，不进入补全。"""
    mapped = map_off_product({
        "nutriments": {
            "fiber_serving": 2.0,
            "serving_quantity": 240,
            "serving_unit": "ml",
        }
    })
    assert mapped["fiber_g"].status == STATUS_REJECTED
    assert mapped["fiber_g"].value_per_100g is None


def test_off_kj_energy_is_candidate():
    mapped = map_off_product({
        "nutriments": {
            "energy_100g": 500,
            "energy_unit": "kJ",
        }
    })
    assert mapped["energy_kcal"].status == STATUS_CANDIDATE
    assert mapped["energy_kcal"].value_per_100g is None
