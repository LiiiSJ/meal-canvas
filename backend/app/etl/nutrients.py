"""营养规范化：传统编号映射、核心营养白名单、能量唯一化规则。"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from backend.app.etl.archive import read_rows
from backend.app.etl.base import NutrientDef, NutrientRow, parse_amount

# 规范能量：按 1008 → 2048 → 2047 只取一个值。1062 是 kJ，必须隔离。
ENERGY_PRIORITY = (1008, 2048, 2047)
ENERGY_IDS = frozenset(ENERGY_PRIORITY)
KJ_ID = 1062

KNOWN_UNITS = frozenset({"G", "MG", "UG", "KCAL", "kJ", "IU"})


class NutrientDataError(RuntimeError):
    pass


def load_nutrient_defs(zip_path: Path, filename: str = "nutrient.csv") -> dict[int, NutrientDef]:
    """读取数据源自带的 nutrient.csv。"""
    defs: dict[int, NutrientDef] = {}
    for row in read_rows(zip_path, filename):
        rank_text = (row.get("rank") or "").strip()
        defs[int(row["id"])] = NutrientDef(
            id=int(row["id"]),
            nbr=(row.get("nutrient_nbr") or "").strip(),
            name_en=(row.get("name") or "").strip(),
            unit_name=(row.get("unit_name") or "").strip(),
            rank=float(rank_text) if rank_text else None,
        )
    return defs


def build_nbr_map(defs: dict[int, NutrientDef]) -> dict[str, int]:
    """传统编号 → FDC 营养 ID。用于 FNDDS 的 nutrient_nbr 语义。"""
    mapping: dict[str, int] = {}
    for nutrient in defs.values():
        if nutrient.nbr:
            mapping[nutrient.nbr] = nutrient.id
    return mapping


def compare_definitions(canonical: dict[int, NutrientDef], other: dict[int, NutrientDef]) -> list[str]:
    """比较两个数据源对同一营养 ID 的定义，返回不一致描述。"""
    conflicts: list[str] = []
    for nid, mine in canonical.items():
        theirs = other.get(nid)
        if theirs is None:
            continue
        if (mine.nbr, mine.name_en, mine.unit_name) != (theirs.nbr, theirs.name_en, theirs.unit_name):
            conflicts.append(
                f"营养 {nid}：{mine.nbr}/{mine.name_en}/{mine.unit_name} "
                f"vs {theirs.nbr}/{theirs.name_en}/{theirs.unit_name}"
            )
    return conflicts


@dataclass
class EnergyResolution:
    nutrient_id: int | None
    value: float | None
    quality_flag: str
    conflict: bool
    candidates: dict[int, float | None]


def resolve_energy(candidates: dict[int, float | None]) -> EnergyResolution:
    """按优先级取唯一 kcal 值；负数/非有限值不可用，但原始值已被保留。"""
    present = {k: v for k, v in candidates.items() if k in ENERGY_IDS}
    distinct = {v for v in present.values() if v is not None}
    conflict = len(distinct) > 1

    for nid in ENERGY_PRIORITY:
        if nid not in present:
            continue
        value = present[nid]
        if value is None:
            continue
        if not math.isfinite(value) or value < 0:
            return EnergyResolution(nid, None, "negative", conflict, present)
        return EnergyResolution(nid, value, "ok", conflict, present)

    return EnergyResolution(None, None, "missing", conflict, present)


def normalize_row(
    row: NutrientRow,
    allowed_ids: frozenset[int],
    unit_by_id: dict[int, str],
) -> tuple[int | None, float | None, str]:
    """把原始营养行转换为（规范 ID，可用值，质量标记）。

    - 空值：quality_flag='missing'，不写 0
    - 负数：保留 raw_amount，amount=NULL，quality_flag='negative'
    - 未知单位：amount=NULL，quality_flag='unit_unknown'
    - 不在白名单：返回 None，由调用方记为 unmapped_nutrient
    """
    if row.nutrient_id is None or row.nutrient_id not in allowed_ids:
        return None, None, "unmapped_nutrient"

    unit = unit_by_id.get(row.nutrient_id, "")
    if unit not in KNOWN_UNITS:
        return row.nutrient_id, None, "unit_unknown"

    if row.amount_text.strip() == "":
        return row.nutrient_id, None, "missing"

    parsed = parse_amount(row.amount_text)
    if parsed.status != "ok":
        return row.nutrient_id, None, "missing"

    value = parsed.value
    assert value is not None
    if value < 0:
        return row.nutrient_id, None, "negative"
    return row.nutrient_id, value, "ok"
