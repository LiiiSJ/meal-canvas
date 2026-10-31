"""食品用途分类体系。

用途分类是产品使用分类，与 USDA `data_type`、中文映射状态 `zh_status` 相互独立：

- `basic_ingredient`：基础烹饪食材。
- `processed_ingredient`：适合用于烹饪搭配的加工食材。
- `prepared_dish`：已经组合或烹制完成的菜肴。
- `ready_to_eat`：即食食品或不适合当作基础烹饪原料的成品食品。
- `unknown`：现有证据不足，暂时无法可靠判断用途。
"""

from __future__ import annotations

BASIC_INGREDIENT = "basic_ingredient"
PROCESSED_INGREDIENT = "processed_ingredient"
PREPARED_DISH = "prepared_dish"
READY_TO_EAT = "ready_to_eat"
UNKNOWN = "unknown"

USAGE_CLASSES: tuple[str, ...] = (
    BASIC_INGREDIENT,
    PROCESSED_INGREDIENT,
    PREPARED_DISH,
    READY_TO_EAT,
    UNKNOWN,
)

# 默认基础食材搜索范围：基础食材 + 适合烹饪搭配的加工食材。
INGREDIENT_CLASSES: frozenset[str] = frozenset({BASIC_INGREDIENT, PROCESSED_INGREDIENT})

# 分类口径版本：规则或映射语义变化时递增，并写入用途库 meta。
CLASSIFICATION_VERSION = "1"
