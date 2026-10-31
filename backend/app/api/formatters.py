"""数字/数值通用格式化。

- amount=None 时返回 null，绝不返回 0。
- 小数位数按 nutrient.decimals 取整。
"""
from __future__ import annotations


def round_amount(value: float | None, decimals: int) -> float | int | None:
    """返回一个可 JSON 序列化的数值（无多余 0 小数）。None 保持 None。"""
    if value is None:
        return None
    if not isinstance(value, (int, float)):
        return None
    if value != value:  # NaN
        return None
    rounded = round(float(value), decimals)
    if decimals == 0 or rounded == int(rounded):
        return int(rounded)
    # 去掉多余 0
    text = f"{rounded:.{decimals}f}".rstrip("0").rstrip(".")
    return float(text) if "." in text else int(text)
