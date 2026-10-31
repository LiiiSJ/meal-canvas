"""每周膳食计划业务存储。

与 USDA 食品库、品牌库、外部营养补全库物理隔离：
计划数据只写入独立的 application 数据库（默认 data/build/meal_canvas_planner.sqlite）。
"""
