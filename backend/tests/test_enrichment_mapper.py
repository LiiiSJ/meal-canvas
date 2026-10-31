"""外部营养键 → 项目键映射（mapper）单元测试。

覆盖 37 项营养素扩展后的关键规则：
- FDC 营养 ID 全量映射、能量 kcal/kJ 分离、仅 kJ 时 kcal 降级候选。
- IU 口径不做 IU↔µg 换算（来源单位不符降级候选）。
- OFF 微量营养素未标注单位时降级候选，不擅自假设单位。
- OFF 维生素 A 按来源单位路由到 IU 键或 µg(RAE) 键。
- OFF salt（盐）不映射为钠；每份基准仅在份量克重明确时换算。
"""
from __future__ import annotations

from backend.app.enrichment.mapper import (
    ALL_NUTRIENT_KEYS,
    NUTRIENT_KEY_BY_ID,
    STATUS_CANDIDATE,
    STATUS_REJECTED,
    STATUS_VERIFIED,
    map_fdc_food,
    map_off_product,
)


def nut(nid: int, name: str, unit: str, value: float) -> dict:
    return {"nutrientId": nid, "nutrientName": name, "unitName": unit, "value": value}


# ---------------------------------------------------------------------- 基础常量


def test_all_nutrient_keys_cover_metadata_table():
    """37 项键与 nutrient_id 映射一一对应，无重复、无遗漏。"""
    assert len(ALL_NUTRIENT_KEYS) == 37
    assert len(set(ALL_NUTRIENT_KEYS)) == 37
    assert set(NUTRIENT_KEY_BY_ID.values()) == set(ALL_NUTRIENT_KEYS)


# ---------------------------------------------------------------------- USDA FDC


def test_fdc_maps_full_nutrient_range():
    """FDC 各类营养素（矿物质/维生素/脂肪酸）均映射到对应项目键。"""
    mapped = map_fdc_food({"foodNutrients": [
        nut(1008, "Energy", "KCAL", 52),
        nut(1003, "Protein", "G", 0.3),
        nut(1087, "Calcium, Ca", "MG", 6),
        nut(1089, "Iron, Fe", "MG", 0.12),
        nut(1092, "Potassium, K", "MG", 107),
        nut(1162, "Vitamin C, total ascorbic acid", "MG", 4.6),
        nut(1178, "Vitamin B-12", "UG", 0.0),
        nut(1258, "Fatty acids, total saturated", "G", 0.028),
        nut(1293, "Fatty acids, total polyunsaturated", "G", 0.051),
        nut(1253, "Cholesterol", "MG", 0),
        nut(1051, "Water", "G", 85.56),
    ]})
    assert mapped["energy_kcal"].value_per_100g == 52
    assert mapped["energy_kcal"].status == STATUS_VERIFIED
    assert mapped["calcium_mg"].value_per_100g == 6
    assert mapped["iron_mg"].value_per_100g == 0.12
    assert mapped["potassium_mg"].value_per_100g == 107
    assert mapped["vitamin_c_mg"].value_per_100g == 4.6
    assert mapped["vitamin_b12_ug"].value_per_100g == 0.0  # 真实 0 保留
    assert mapped["vitamin_b12_ug"].status == STATUS_VERIFIED
    assert mapped["saturated_fat_g"].value_per_100g == 0.028
    assert mapped["polyunsaturated_fat_g"].value_per_100g == 0.051
    assert mapped["cholesterol_mg"].value_per_100g == 0
    assert mapped["water_g"].value_per_100g == 85.56


def test_fdc_energy_kj_goes_to_separate_key():
    """1062 kJ 进入 energy_kj 独立键，绝不并入 kcal。"""
    mapped = map_fdc_food({"foodNutrients": [
        nut(1008, "Energy", "KCAL", 200),
        nut(1062, "Energy", "KJ", 837),
    ]})
    assert mapped["energy_kcal"].value_per_100g == 200
    assert mapped["energy_kj"].value_per_100g == 837
    assert mapped["energy_kj"].status == STATUS_VERIFIED


def test_fdc_only_kj_energy_kcal_becomes_candidate():
    """外部仅提供 kJ 能量时：energy_kj 可用，energy_kcal 降级为候选（不换算）。"""
    mapped = map_fdc_food({"foodNutrients": [
        nut(1062, "Energy", "KJ", 837),
    ]})
    assert mapped["energy_kj"].value_per_100g == 837
    assert mapped["energy_kcal"].status == STATUS_CANDIDATE
    assert mapped["energy_kcal"].value_per_100g is None


def test_fdc_energy_priority_single_value():
    """1008 优先于 2048/2047，能量只取一个值。"""
    mapped = map_fdc_food({"foodNutrients": [
        nut(2047, "Energy (Atwater General Factors)", "KCAL", 199),
        nut(1008, "Energy", "KCAL", 200),
        nut(2048, "Energy (Atwater Specific Factors)", "KCAL", 201),
    ]})
    assert mapped["energy_kcal"].value_per_100g == 200


def test_fdc_vitamin_a_iu_verified_with_iu_unit():
    """维生素 A（1104）来源单位为 IU 时直接可用。"""
    mapped = map_fdc_food({"foodNutrients": [
        nut(1104, "Vitamin A, IU", "IU", 54),
    ]})
    assert mapped["vitamin_a_iu"].value_per_100g == 54
    assert mapped["vitamin_a_iu"].status == STATUS_VERIFIED


def test_fdc_vitamin_a_iu_key_rejects_mass_unit():
    """IU 口径键收到 µg 来源值时不换算，降级为候选。"""
    mapped = map_fdc_food({"foodNutrients": [
        nut(1104, "Vitamin A, IU", "UG", 54),
    ]})
    assert mapped["vitamin_a_iu"].status == STATUS_CANDIDATE
    assert mapped["vitamin_a_iu"].value_per_100g is None


def test_fdc_vitamin_a_rae_rejects_iu_unit():
    """µg(RAE) 口径键收到 IU 来源值时不换算，降级为候选。"""
    mapped = map_fdc_food({"foodNutrients": [
        nut(1106, "Vitamin A, RAE", "IU", 100),
    ]})
    assert mapped["vitamin_a_rae_ug"].status == STATUS_CANDIDATE
    assert mapped["vitamin_a_rae_ug"].value_per_100g is None


def test_fdc_negative_value_rejected():
    """异常负值不进入补全。"""
    mapped = map_fdc_food({"foodNutrients": [
        nut(1005, "Carbohydrate, by difference", "G", -1.5),
    ]})
    assert mapped["carb_g"].status == STATUS_REJECTED
    assert mapped["carb_g"].value_per_100g is None


def test_fdc_unknown_nutrient_ignored():
    """项目未定义的营养素（如 9999）直接忽略。"""
    mapped = map_fdc_food({"foodNutrients": [
        nut(9999, "Something else", "G", 1.0),
    ]})
    assert mapped == {}


# ---------------------------------------------------------------------- Open Food Facts


def test_off_sodium_grams_converted_to_mg():
    """OFF sodium 常以 g 标注，显式 ×1000 换算为 mg。"""
    mapped = map_off_product({"nutriments": {
        "sodium_100g": 0.12, "sodium_unit": "g",
        "proteins_100g": 8.0,
    }})
    assert mapped["sodium_mg"].value_per_100g == 120.0
    assert "×1000" in (mapped["sodium_mg"].conversion_method or "")
    assert mapped["protein_g"].value_per_100g == 8.0


def test_off_micronutrient_without_unit_becomes_candidate():
    """微量营养素未标注单位时不假设单位，降级为候选。"""
    mapped = map_off_product({"nutriments": {
        "vitamin-c_100g": 12,
    }})
    assert mapped["vitamin_c_mg"].status == STATUS_CANDIDATE
    assert mapped["vitamin_c_mg"].value_per_100g is None


def test_off_micronutrient_with_unit_verified():
    """微量营养素单位明确且可显式换算时可用。"""
    mapped = map_off_product({"nutriments": {
        "vitamin-c_100g": 12, "vitamin-c_unit": "mg",
        "iron_100g": 0.0018, "iron_unit": "g",
        "calcium_100g": 120, "calcium_unit": "mg",
    }})
    assert mapped["vitamin_c_mg"].value_per_100g == 12
    assert mapped["iron_mg"].value_per_100g == 1.8  # g→mg
    assert mapped["calcium_mg"].value_per_100g == 120


def test_off_salt_not_mapped_to_sodium():
    """OFF salt（盐）不等于钠，绝不映射。"""
    mapped = map_off_product({"nutriments": {
        "salt_100g": 1.5, "salt_unit": "g",
    }})
    assert "sodium_mg" not in mapped


def test_off_vitamin_a_routed_by_unit():
    """维生素 A 按来源单位路由：IU → vitamin_a_iu；µg → vitamin_a_rae_ug。"""
    mapped_iu = map_off_product({"nutriments": {
        "vitamin-a_100g": 300, "vitamin-a_unit": "IU",
    }})
    assert mapped_iu["vitamin_a_iu"].value_per_100g == 300
    assert "vitamin_a_rae_ug" not in mapped_iu

    mapped_ug = map_off_product({"nutriments": {
        "vitamin-a_100g": 90, "vitamin-a_unit": "µg",
    }})
    assert mapped_ug["vitamin_a_rae_ug"].value_per_100g == 90
    assert "vitamin_a_iu" not in mapped_ug


def test_off_energy_kj_100g_goes_to_kj_key():
    """OFF energy-kj_100g 进入 energy_kj 独立键。"""
    mapped = map_off_product({"nutriments": {
        "energy-kj_100g": 1500, "energy-kj_unit": "kJ",
        "energy-kcal_100g": 359, "energy-kcal_unit": "kcal",
    }})
    assert mapped["energy_kj"].value_per_100g == 1500
    assert mapped["energy_kcal"].value_per_100g == 359


def test_off_generic_energy_without_unit_becomes_candidate():
    """energy_100g 未标注 kcal/kJ 时不假设，降级为候选。"""
    mapped = map_off_product({"nutriments": {
        "energy_100g": 1500,
    }})
    assert mapped["energy_kcal"].status == STATUS_CANDIDATE
    assert mapped["energy_kcal"].value_per_100g is None


def test_off_serving_basis_converted_with_grams():
    """每份基准在份量克重明确（g）时线性换算为每 100 克。"""
    mapped = map_off_product({"nutriments": {
        "proteins_serving": 6.0,
        "serving_quantity": 30, "serving_unit": "g",
    }})
    assert mapped["protein_g"].value_per_100g == 20.0
    assert "每份" in (mapped["protein_g"].original_basis or "")


def test_off_serving_basis_ml_rejected():
    """份量以 ml 计且无可靠密度数据时不换算为克，记录为 rejected。"""
    mapped = map_off_product({"nutriments": {
        "proteins_serving": 6.0,
        "serving_quantity": 250, "serving_unit": "ml",
    }})
    assert mapped["protein_g"].status == STATUS_REJECTED
    assert mapped["protein_g"].value_per_100g is None


def test_off_real_zero_kept():
    """外部明确 0 值是真实零值，按 0 采纳。"""
    mapped = map_off_product({"nutriments": {
        "fiber_100g": 0,
    }})
    assert mapped["fiber_g"].value_per_100g == 0.0
    assert mapped["fiber_g"].status == STATUS_VERIFIED
