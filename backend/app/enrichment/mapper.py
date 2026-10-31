"""外部营养键 → 项目键映射，含单位与计量基准校验。

规则（与项目硬约束一致）：
- 项目键覆盖 nutrient 元数据表全部 37 项营养素；其中 7 项为核心 summary 键
  （energy_kcal / protein_g / fat_g / carb_g / fiber_g / sugar_g / sodium_mg）。
- 能量只接受 kcal 基准进入 energy_kcal；FDC kcal 条目按 1008 → 2048 → 2047 取一个值；
  kJ（1062/268）只进入独立的 energy_kj 键，绝不并入 kcal，也不自动换算。
- 单位换算只允许显式规则（g↔mg↔µg）；IU 口径营养素（维生素A IU、维生素D IU）
  不做 IU↔µg 换算：来源单位非 IU 时降级为 candidate_review 并注明口径差异。
- 每 100 克基准直接可用；每份基准仅在份量克重明确且单位为 g 时线性换算；
  份量以 ml 计且无可靠密度数据时拒绝（禁止 ml→g 猜测）。
- 负数视为异常值，不进入补全。
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# 7 项核心 summary 键（与 food_summary 列一致；顺序固定）
PROJECT_KEYS = ("energy_kcal", "protein_g", "fat_g", "carb_g", "fiber_g", "sugar_g", "sodium_mg")

STATUS_VERIFIED = "verified_external"
STATUS_CANDIDATE = "candidate_review"
STATUS_REJECTED = "rejected"

BASIS_PER_100G = "per_100g"

# nutrient_id → 项目键（覆盖 nutrient 元数据表全部 37 项；能量 kcal 单列处理）
NUTRIENT_KEY_BY_ID: dict[int, str] = {
    1002: "nitrogen_g",
    1003: "protein_g",
    1004: "fat_g",
    1005: "carb_g",
    1007: "ash_g",
    1008: "energy_kcal",
    1051: "water_g",
    1062: "energy_kj",
    1079: "fiber_g",
    1087: "calcium_mg",
    1089: "iron_mg",
    1090: "magnesium_mg",
    1091: "phosphorus_mg",
    1092: "potassium_mg",
    1093: "sodium_mg",
    1095: "zinc_mg",
    1098: "copper_mg",
    1104: "vitamin_a_iu",
    1106: "vitamin_a_rae_ug",
    1109: "vitamin_e_mg",
    1110: "vitamin_d_iu",
    1162: "vitamin_c_mg",
    1165: "vitamin_b1_mg",
    1166: "vitamin_b2_mg",
    1167: "vitamin_b3_mg",
    1170: "vitamin_b5_mg",
    1175: "vitamin_b6_mg",
    1177: "folate_ug",
    1178: "vitamin_b12_ug",
    1180: "choline_mg",
    1185: "vitamin_k_ug",
    1253: "cholesterol_mg",
    1257: "trans_fat_g",
    1258: "saturated_fat_g",
    1292: "monounsaturated_fat_g",
    1293: "polyunsaturated_fat_g",
    2000: "sugar_g",
}

# 全部 37 键，按营养素 rank 排序（稳定展示顺序）
ALL_NUTRIENT_KEYS: tuple[str, ...] = (
    "water_g", "energy_kcal", "energy_kj", "nitrogen_g", "protein_g", "fat_g", "ash_g",
    "carb_g", "fiber_g", "sugar_g", "calcium_mg", "iron_mg", "magnesium_mg", "phosphorus_mg",
    "potassium_mg", "sodium_mg", "zinc_mg", "copper_mg", "vitamin_c_mg", "vitamin_b1_mg",
    "vitamin_b2_mg", "vitamin_b3_mg", "vitamin_b5_mg", "vitamin_b6_mg", "folate_ug",
    "choline_mg", "vitamin_b12_ug", "vitamin_a_rae_ug", "vitamin_a_iu", "vitamin_e_mg",
    "vitamin_d_iu", "vitamin_k_ug", "saturated_fat_g", "monounsaturated_fat_g",
    "polyunsaturated_fat_g", "trans_fat_g", "cholesterol_mg",
)


@dataclass(frozen=True)
class MappedNutrient:
    key: str
    original_amount: float
    original_unit: str
    original_basis: str
    value_per_100g: float | None
    conversion_method: str | None
    status: str
    note: str | None


_TARGET_UNIT: dict[str, str] = {
    "energy_kcal": "kcal",
    "energy_kj": "kJ",
    "protein_g": "g",
    "fat_g": "g",
    "carb_g": "g",
    "fiber_g": "g",
    "sugar_g": "g",
    "nitrogen_g": "g",
    "ash_g": "g",
    "water_g": "g",
    "sodium_mg": "mg",
    "calcium_mg": "mg",
    "iron_mg": "mg",
    "magnesium_mg": "mg",
    "phosphorus_mg": "mg",
    "potassium_mg": "mg",
    "zinc_mg": "mg",
    "copper_mg": "mg",
    "cholesterol_mg": "mg",
    "vitamin_c_mg": "mg",
    "vitamin_b1_mg": "mg",
    "vitamin_b2_mg": "mg",
    "vitamin_b3_mg": "mg",
    "vitamin_b5_mg": "mg",
    "vitamin_b6_mg": "mg",
    "vitamin_e_mg": "mg",
    "choline_mg": "mg",
    "folate_ug": "µg",
    "vitamin_b12_ug": "µg",
    "vitamin_k_ug": "µg",
    "vitamin_a_rae_ug": "µg",
    "vitamin_a_iu": "IU",
    "vitamin_d_iu": "IU",
    "trans_fat_g": "g",
    "saturated_fat_g": "g",
    "monounsaturated_fat_g": "g",
    "polyunsaturated_fat_g": "g",
}

# 显式单位换算表：(from_unit, to_unit) → (factor, 描述)
_CONVERSIONS: dict[tuple[str, str], tuple[float, str]] = {
    ("g", "mg"): (1000.0, "×1000（g→mg）"),
    ("mg", "g"): (0.001, "×0.001（mg→g）"),
    ("g", "µg"): (1_000_000.0, "×1000000（g→µg）"),
    ("µg", "g"): (0.000001, "×0.000001（µg→g）"),
    ("mg", "µg"): (1000.0, "×1000（mg→µg）"),
    ("µg", "mg"): (0.001, "×0.001（µg→mg）"),
}

_UNIT_ALIASES: dict[str, str] = {
    "kcal": "kcal", "kcals": "kcal",
    "kj": "kJ",
    "g": "g", "gram": "g", "grams": "g", "gr": "g",
    "mg": "mg", "milligram": "mg", "milligrams": "mg",
    "µg": "µg", "ug": "µg", "mcg": "µg", "μg": "µg",
    "iu": "IU",
}


def _normalize_unit(raw: str | None) -> str | None:
    if not raw:
        return None
    return _UNIT_ALIASES.get(raw.strip().lower())


def _to_target(value: float, unit: str | None, key: str) -> tuple[float, str | None] | None:
    """把外部值换算到目标单位。无法显式换算时返回 None。"""
    target = _TARGET_UNIT[key]
    if unit == target:
        return value, None
    conv = _CONVERSIONS.get((unit or "", target))
    if conv is None:
        return None
    factor, method = conv
    return value * factor, method


def _mapped(
    key: str,
    amount: float,
    unit_raw: str | None,
    basis: str,
    *,
    serving_grams: float | None = None,
) -> MappedNutrient | None:
    """单条外部营养值的统一校验入口。返回 None 表示该条完全不可用（无来源依据）。"""
    if not isinstance(amount, (int, float)) or isinstance(amount, bool) or not math.isfinite(amount):
        return None
    amount_f = float(amount)
    unit = _normalize_unit(unit_raw)
    if amount_f < 0:
        return MappedNutrient(key, amount_f, unit or (unit_raw or ""), basis, None, None,
                              STATUS_REJECTED, "外部来源为异常负值，不进入补全")

    if basis == BASIS_PER_100G:
        converted = _to_target(amount_f, unit, key)
        if converted is None:
            if unit == "kJ" and key == "energy_kcal":
                return MappedNutrient(key, amount_f, unit, basis, None, None,
                                      STATUS_CANDIDATE, "外部仅提供 kJ 能量，与 kcal 口径不同，不自动换算")
            target = _TARGET_UNIT[key]
            if target == "IU" and unit in ("µg", "mg", "g"):
                return MappedNutrient(key, amount_f, unit, basis, None, None,
                                      STATUS_CANDIDATE,
                                      f"来源单位为 {unit}，项目口径为 IU，定义不同，不自动换算")
            if target == "µg" and unit == "IU":
                return MappedNutrient(key, amount_f, unit, basis, None, None,
                                      STATUS_CANDIDATE,
                                      "来源单位为 IU，项目口径为 µg（RAE），定义不同，不自动换算")
            return MappedNutrient(key, amount_f, unit or (unit_raw or ""), basis, None, None,
                                  STATUS_REJECTED, f"单位 {unit_raw!r} 无法显式换算到目标单位，不进入补全")
        value, method = converted
        return MappedNutrient(key, amount_f, unit or (unit_raw or ""), basis, value, method,
                              STATUS_VERIFIED, None)

    # 每份基准：仅当份量克重明确且单位为 g 时线性换算（可追溯）。
    if basis.startswith("per_serving"):
        if serving_grams is None or serving_grams <= 0:
            return MappedNutrient(key, amount_f, unit or (unit_raw or ""), basis, None, None,
                                  STATUS_REJECTED, "每份基准但份量克重不明确，不进入补全")
        converted = _to_target(amount_f, unit, key)
        if converted is None:
            return MappedNutrient(key, amount_f, unit or (unit_raw or ""), basis, None, None,
                                  STATUS_REJECTED, f"单位 {unit_raw!r} 无法显式换算到目标单位，不进入补全")
        value_raw, method = converted
        value = value_raw / serving_grams * 100.0
        basis_text = f"每份（{serving_grams:g} g）"
        return MappedNutrient(key, amount_f, unit or (unit_raw or ""), basis_text, value,
                              f"按份量 {serving_grams:g} g 线性换算为每 100 克" + (f"；{method}" if method else ""),
                              STATUS_VERIFIED, None)
    return MappedNutrient(key, amount_f, unit or (unit_raw or ""), basis, None, None,
                          STATUS_REJECTED, "计量基准不明确，不进入补全")


# ---------------------------------------------------------------------- USDA FDC

# kcal 能量条目按 FDC 营养 ID 取唯一值的优先级
_ENERGY_PRIORITY = (1008, 2048, 2047)
_KJ_ENERGY_IDS = (1062, 268)
_KCAL_ENERGY_NAMES = {
    "energy": 1008,
    "energy (atwater general factors)": 2047,
    "energy (atwater specific factors)": 2048,
}
# 能量（kcal/kJ）之外的 FDC 营养 ID → 项目键（覆盖项目全部 37 项营养素）
_FDC_ID_TO_KEY = {nid: key for nid, key in NUTRIENT_KEY_BY_ID.items() if nid != 1008}


def map_fdc_food(payload: dict) -> dict[str, MappedNutrient]:
    """FDC API foodNutrients → 项目键。能量 kcal 按 1008→2048→2047 取一个值；kJ 单列 energy_kj。"""
    entries = payload.get("foodNutrients")
    if not isinstance(entries, list):
        return {}

    kcal_energy: dict[int, tuple[float, str]] = {}
    kj_energy: list[tuple[float, str]] = []
    others: dict[str, tuple[float, str]] = {}

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        value = entry.get("value")
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
            continue
        unit = _normalize_unit(entry.get("unitName"))
        nutrient_id = entry.get("nutrientId")
        name = (entry.get("nutrientName") or "").strip().lower()

        if nutrient_id in _KJ_ENERGY_IDS or (unit == "kJ" and "energy" in name):
            kj_energy.append((float(value), entry.get("unitName") or "kJ"))
            continue
        if nutrient_id in _ENERGY_PRIORITY or name in _KCAL_ENERGY_NAMES:
            effective_id = nutrient_id if nutrient_id in _ENERGY_PRIORITY else _KCAL_ENERGY_NAMES.get(name)
            if effective_id is not None and unit == "kcal":
                kcal_energy.setdefault(int(effective_id), (float(value), entry.get("unitName") or "KCAL"))
            continue
        key = _FDC_ID_TO_KEY.get(nutrient_id)
        if key is None:
            continue
        others.setdefault(key, (float(value), entry.get("unitName") or ""))

    out: dict[str, MappedNutrient] = {}
    # 能量 kcal：严格单值，按优先级取第一个 kcal 条目
    for priority_id in _ENERGY_PRIORITY:
        if priority_id in kcal_energy:
            value, unit_raw = kcal_energy[priority_id]
            mapped = _mapped("energy_kcal", value, unit_raw, BASIS_PER_100G)
            if mapped is not None:
                out["energy_kcal"] = mapped
            break
    # 能量 kJ：独立键，绝不并入 kcal
    if kj_energy:
        value, unit_raw = kj_energy[0]
        mapped = _mapped("energy_kj", value, unit_raw, BASIS_PER_100G)
        if mapped is not None:
            out["energy_kj"] = mapped
    if "energy_kcal" not in out and kj_energy:
        value, unit_raw = kj_energy[0]
        out["energy_kcal"] = MappedNutrient(
            "energy_kcal", value, unit_raw, BASIS_PER_100G, None, None,
            STATUS_CANDIDATE, "外部仅提供 kJ 能量，与 kcal 口径不同，不自动换算",
        )

    for key, (value, unit_raw) in others.items():
        mapped = _mapped(key, value, unit_raw, BASIS_PER_100G)
        if mapped is not None:
            out[key] = mapped
    return out


# ---------------------------------------------------------------------- Open Food Facts

# OFF nutriments 字段前缀 → 项目键（能量单列处理；维生素A按来源单位路由）。
# 注意：不映射 salt（盐 ≠ 钠）；不映射项目未定义的营养素。
_OFF_FIELDS = {
    "protein_g": "proteins",
    "fat_g": "fat",
    "carb_g": "carbohydrates",
    "fiber_g": "fiber",
    "sugar_g": "sugars",
    "sodium_mg": "sodium",
    "saturated_fat_g": "saturated-fat",
    "monounsaturated_fat_g": "monounsaturated-fat",
    "polyunsaturated_fat_g": "polyunsaturated-fat",
    "trans_fat_g": "trans-fat",
    "cholesterol_mg": "cholesterol",
    "vitamin_c_mg": "vitamin-c",
    "vitamin_d_iu": "vitamin-d",
    "vitamin_e_mg": "vitamin-e",
    "vitamin_k_ug": "vitamin-k",
    "vitamin_b1_mg": "vitamin-b1",
    "vitamin_b2_mg": "vitamin-b2",
    "vitamin_b3_mg": "vitamin-pp",
    "vitamin_b5_mg": "pantothenic-acid",
    "vitamin_b6_mg": "vitamin-b6",
    "folate_ug": "vitamin-b9",
    "vitamin_b12_ug": "vitamin-b12",
    "calcium_mg": "calcium",
    "iron_mg": "iron",
    "magnesium_mg": "magnesium",
    "phosphorus_mg": "phosphorus",
    "potassium_mg": "potassium",
    "zinc_mg": "zinc",
    "copper_mg": "copper",
}

# OFF 约定：宏量质量类营养素 _100g/_serving 默认单位为 g（_unit 字段存在时以其为准）。
# 微量营养素不设默认单位：来源未标注单位时降级为 candidate_review，不擅自假设。
_OFF_DEFAULT_UNIT = {
    "protein_g": "g", "fat_g": "g", "carb_g": "g",
    "fiber_g": "g", "sugar_g": "g", "sodium_mg": "g",
    "saturated_fat_g": "g", "monounsaturated_fat_g": "g",
    "polyunsaturated_fat_g": "g", "trans_fat_g": "g",
}


def _off_serving_grams(nutriments: dict) -> tuple[float | None, str | None]:
    sq = nutriments.get("serving_quantity")
    su = nutriments.get("serving_unit")
    if not isinstance(sq, (int, float)) or isinstance(sq, bool) or not math.isfinite(sq) or sq <= 0:
        return None, None
    if isinstance(su, str) and su.strip().lower() == "g":
        return float(sq), None
    return None, f"份量以 {su!r} 计，无可靠密度数据，不换算为克"


def _is_num(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def map_off_product(payload: dict) -> dict[str, MappedNutrient]:
    """OFF nutriments → 项目键。_100g 后缀即每 100 克基准；sodium 常见为 g，需显式换算。"""
    nutriments = payload.get("nutriments")
    if not isinstance(nutriments, dict):
        return {}

    out: dict[str, MappedNutrient] = {}
    serving_grams, _serving_note = _off_serving_grams(nutriments)

    def map_one(key: str, prefix: str, default_unit: str | None = None) -> MappedNutrient | None:
        value = nutriments.get(f"{prefix}_100g")
        basis = BASIS_PER_100G
        if value is None:
            value = nutriments.get(f"{prefix}_serving")
            if value is None or not _is_num(value):
                return None
            basis = "per_serving"  # 克重不明时由 _mapped 产出 rejected 记录
        if not _is_num(value):
            return None
        unit_raw = nutriments.get(f"{prefix}_unit")
        if not isinstance(unit_raw, str) or not unit_raw.strip():
            unit_raw = default_unit or _OFF_DEFAULT_UNIT.get(key)
            if unit_raw is None:
                return MappedNutrient(key, float(value), "", basis, None, None,
                                      STATUS_CANDIDATE, "来源未标注单位，不自动采纳")
        return _mapped(key, float(value), unit_raw, basis, serving_grams=serving_grams)

    # 能量：kcal 与 kJ 独立键；OFF 字段名 energy-kcal/energy-kj 本身已定义单位。
    for key, prefix, implied in (("energy_kcal", "energy-kcal", "kcal"), ("energy_kj", "energy-kj", "kJ")):
        mapped = map_one(key, prefix, default_unit=implied)
        if mapped is not None:
            out[key] = mapped
    energy_generic = nutriments.get("energy_100g")
    energy_unit = nutriments.get("energy_unit")
    if _is_num(energy_generic):
        generic_unit = energy_unit if isinstance(energy_unit, str) and energy_unit.strip() else None
        if generic_unit is not None:
            if "energy_kcal" not in out:
                mapped = _mapped("energy_kcal", float(energy_generic), generic_unit, BASIS_PER_100G)
                if mapped is not None:
                    out["energy_kcal"] = mapped
            if "energy_kj" not in out and _normalize_unit(generic_unit) == "kJ":
                mapped = _mapped("energy_kj", float(energy_generic), generic_unit, BASIS_PER_100G)
                if mapped is not None:
                    out["energy_kj"] = mapped
        elif "energy_kcal" not in out:
            # 能量未标注单位（kcal/kJ 不明）：不假设，降级为候选
            out["energy_kcal"] = MappedNutrient(
                "energy_kcal", float(energy_generic), "", BASIS_PER_100G, None, None,
                STATUS_CANDIDATE, "外部能量未标注单位（kcal/kJ 不明），不自动换算",
            )

    # 维生素 A：按来源单位路由到 IU 键或 µg(RAE) 键，互不换算。
    va_unit = _normalize_unit(nutriments.get("vitamin-a_unit"))
    va_key = "vitamin_a_iu" if va_unit == "IU" else "vitamin_a_rae_ug"
    mapped = map_one(va_key, "vitamin-a")
    if mapped is not None:
        out[va_key] = mapped

    for key, prefix in _OFF_FIELDS.items():
        mapped = map_one(key, prefix)
        if mapped is not None:
            out[key] = mapped

    return out


def map_external(provider: str, payload: dict) -> dict[str, MappedNutrient]:
    """按来源分发。payload 为 ExternalFood.payload。"""
    if provider == "usda_fdc":
        return map_fdc_food(payload)
    if provider == "openfoodfacts":
        return map_off_product(payload)
    return {}
