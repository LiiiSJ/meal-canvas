"""外部营养数据检索与补全模块。

与 ETL / 只读 USDA 库完全独立：
- 检索来源：USDA FoodData Central API（优先）、Open Food Facts v2 API。
- 身份匹配：基于原始英文描述 / GTIN / 状态词评分，仅 exact 级自动采纳。
- 存储：独立 SQLite 库 meal_canvas_enrichment.sqlite，绝不写回 USDA 数据表。
- 数值：逐营养素补全，只填缺失项（NULL），真实零值与既有值一律不动。
"""
