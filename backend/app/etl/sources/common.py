"""适配器共用的低层解析函数（不包含任何数据源语义）。"""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from backend.app.etl.archive import open_csv, read_rows
from backend.app.etl.base import PortionRow, clean_text, parse_amount


def load_measure_units(zip_path: Path) -> dict[int, str]:
    return {int(r["id"]): r["name"] for r in read_rows(zip_path, "measure_unit.csv")}


def iter_raw_nutrient_rows(
    zip_path: Path, ids: set[int] | None
) -> Iterator[dict[str, str]]:
    """流式读取 food_nutrient.csv，按 fdc_id 过滤；不解压到磁盘。"""
    with open_csv(zip_path, "food_nutrient.csv") as reader:
        for row in reader:
            fid_text = (row.get("fdc_id") or "").strip()
            if not fid_text.isdigit():
                continue
            if ids is not None and int(fid_text) not in ids:
                continue
            yield row


def iter_portion_rows(
    zip_path: Path, ids: set[int] | None, unit_names: dict[int, str]
) -> Iterator[PortionRow]:
    """读取 food_portion.csv，并标注份量是否可用于克重换算。"""
    with open_csv(zip_path, "food_portion.csv") as reader:
        for row in reader:
            fid_text = (row.get("fdc_id") or "").strip()
            if not fid_text.isdigit():
                continue
            fdc_id = int(fid_text)
            if ids is not None and fdc_id not in ids:
                continue
            gram_text = (row.get("gram_weight") or "").strip()
            gram = parse_amount(gram_text)
            unit_id = (row.get("measure_unit_id") or "").strip()
            unit_name = unit_names.get(int(unit_id)) if unit_id.isdigit() else None

            if gram.status == "empty":
                quality = "amount_missing"
                gram_value = None
            elif gram.status != "ok":
                quality = "amount_missing"
                gram_value = None
            elif gram.value == 0:
                quality = "zero_weight"
                gram_value = 0.0
            elif unit_name in {"ml", "liter", "fl oz"}:
                # USDA 直接给出的克重可保留；若缺失则不可换算。
                quality = "ok"
                gram_value = gram.value
            else:
                quality = "ok"
                gram_value = gram.value

            amount = parse_amount((row.get("amount") or "").strip())
            yield PortionRow(
                fdc_id=fdc_id,
                amount=amount.value,
                modifier=clean_text(row.get("modifier")),
                portion_description=clean_text(row.get("portion_description")),
                gram_weight=gram_value,
                unit_name=unit_name,
                quality_flag=quality,
            )
