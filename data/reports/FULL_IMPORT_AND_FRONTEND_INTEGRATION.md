# 正式全量导入与前端接入验收报告

- 生成时间：2026-10-30
- 执行方式：实际构建 + 实际 API 请求 + 浏览器交互验收；所有数字来自数据库扫描或 API 返回，非估计值。

---

## 0. 结论

| 项目 | 状态 |
| --- | --- |
| Foundation / SR Legacy / FNDDS / Branded 四套数据 | 全部导入成功 |
| 正式默认食材库 | `data/build/meal_canvas.sqlite`，13,694 食品 |
| 正式品牌库 | `data/build/meal_canvas_branded.sqlite`，1,999,950 食品，独立隔离 |
| 正式用途库 | `data/build/meal_canvas_usage.sqlite`，2,013,644 行，双库覆盖 100% |
| 后端 API | 已指向正式库（`/api/health` 返回 `food_count=13694`） |
| 前端 | 浏览器实测从 full 库读取（默认 7,047 条，全部用途 13,694 条） |
| 全部测试 | 后端 pytest 114 通过；ruff 通过；前端 typecheck / lint / vitest 27 通过；生产构建成功 |

---

## 1. 四套数据导入结果

| 数据集 | 进入库 | 食品数 | 数据版本 | 与基准核对 |
| --- | --- | ---: | --- | --- |
| Foundation Foods | 默认库 | 469 | 2026-04 | 与基准 469 一致 |
| SR Legacy | 默认库 | 7,793 | 2018-04 | 与基准 7,793 一致 |
| FNDDS / Survey Foods | 默认库 | 5,432 | 2024-10（数据期 2021–2023） | 与基准 5,432 一致 |
| Branded Foods | 独立品牌库 | 1,999,950 | 2026-04 | 与基准 1,999,950 一致 |

- Foundation 能量并集（1008/2047/2048 任一非空）：378，与规则基准 378 一致。
- Foundation 469/395/74 差异：ETL 以 `food.csv` 中真实食品为准（469），未使用 `foundation_food.csv`（395）作白名单；差异 74 条为样本/采购类记录，未导入。
- 品牌库未混入默认库：默认库 `library_scope` 全部为 `default`（13,694），品牌库全部为 `branded`（1,999,950）。

## 2. 正式数据库路径与大小

| 文件 | 大小 | 说明 |
| --- | ---: | --- |
| `data/build/meal_canvas.sqlite` | 41,578,496 B（39.65 MB） | 默认库，built 2026-10-30T09:18:33+08:00，用时 10.1s |
| `data/build/meal_canvas_branded.sqlite` | 3,564,294,144 B（3,399.18 MB ≈ 3.32 GiB） | 品牌库，built 2026-10-30T09:28:16+08:00，用时 573.5s |
| `data/build/meal_canvas_usage.sqlite` | 405,929,984 B（387.12 MB） | 用途库，built 2026-10-30T09:54:35（规则修复后重建） |

sample 库未被覆盖，仍在 `data/build/sample/`（`meal_canvas.sqlite` 3,682,304 B / `meal_canvas_branded.sqlite` 761,856 B / `meal_canvas_usage.sqlite` 已按修复后规则重建 1,634 行）。

## 3. 营养与份量记录数

| 库 | food | food_nutrient | food_portion | food_alias | food_summary | quality_event |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 默认库 | 13,694 | 425,557 | 36,682 | 168 | 13,692 | 338 |
| 品牌库 | 1,999,950 | 25,134,459 | 0 | 0 | 1,896,250 | 0 |

- 品牌库 `food_portion=0`：Branded 原始数据无 `food_portion.csv`，按规则未伪造克重。
- 默认库 `food_summary` 13,692 与食品 13,694 差 2：该 2 条食品无任何可用核心营养值，按缺失规则不生成汇总行（未以 0 填充）。
- 品牌库 `food_summary` 1,896,250，与食品差 103,700：同样为全核心营养缺失的商品，未插值。
- 缺失值处理：默认库 `food_nutrient` 中 `amount IS NULL` 10 行（原始值不可用但 `raw_amount` 保留），`raw_amount` 非空 425,557 行；品牌库 0 行缺失。能量只取 1008→2048→2047 之一，未合并 kJ(1062)。

## 4. 正式用途库五类分类

总计 2,013,644 行 = 默认库 13,694 + 品牌库 1,999,950，逐行与两库 fdc_id 集合精确匹配（missing=0 / extra=0，双库 exact=true）。

| 用途 | 默认库 | 占比 | 品牌库 | 占比 |
| --- | ---: | ---: | ---: | ---: |
| basic_ingredient | 5,377 | 39.3% | 414,529 | 20.7% |
| processed_ingredient | 1,670 | 12.2% | 463,606 | 23.2% |
| prepared_dish | 3,033 | 22.1% | 226,380 | 11.3% |
| ready_to_eat | 3,155 | 23.0% | 865,822 | 43.3% |
| unknown | 459 | 3.4% | 29,613 | 1.5% |

判定来源：rule 1,397,964 / category 588,944 / default 26,736。`unknown` 保留未猜测；`(fdc_id, library_scope)` 全部落在合法 scope（mismatch=0）。

本轮修复的 6 项规则缺陷（`data/curation/usage_rules.csv`，sample+full 均已用新规则重建并回归验证）：

1. `salad dressing` 优先级 -1，先于 `salad`（L51/L52）——沙拉酱判为加工食材，沙拉成品菜不受影响（如 `Fruit salad … with salad dressing` 仍为 prepared_dish）。
2. `tea` 改为 `\btea\b`（L62/L63）——`steak` 不再误判为茶（steak 类全部落回 basic_ingredient / category 映射）。
3. `tenders?` 收紧为 `\bchicken\s+tenders?\b|\btenders\b`（L39）——`tenderloin`、`ALWAYS TENDER` 不再误判为鸡柳。
4. `nuggets?` 保持 `\bnuggets?\b` 词边界——`FENNEL SALAMI NUGGETS` 由 L45 腌腊规则优先判为加工肉制品。
5. `fried` 规则优先级降为 1（L39），低于腌腊规则 L45（priority 0）——`pan-fried bacon / sausage / chorizo` 等 5 条样本均判为 processed_ingredient。
6. `stuffed` 改为 `\bstuffed\b`（L40）——`layered` 类（如七层蘸酱）不再误判。

未做的事：未批量改 sauce / restaurant / 带配料等有争议记录；未改五类体系；未硬编码 fdc_id。

## 5. 中文覆盖

默认库：verified 249 / glossary 1,073 / none 12,372；review_status：verified 249 / pending 13,445。`name_zh` 非空 1,322。
品牌库：全部 zh_status=none（1,999,950），未机翻品牌名。

`display_name` 仅当 `zh_status='verified'` 时用中文名；glossary/none 以英文原名展示。无中文名食品仍可被搜索、加入餐盘与参与计算（API 实测：fdc 169967 `Broccoli, cooked, boiled, drained, without salt`，zh_status=none，可搜到且 display_name 为英文原名）。

## 6. 后端实际连接配置

- `backend/app/api/config.py` 默认值已指向正式库：
  - `data/build/meal_canvas.sqlite`
  - `data/build/meal_canvas_branded.sqlite`
  - `data/build/meal_canvas_usage.sqlite`
- 环境变量 `MEAL_CANVAS_DB_PATH_API` / `MEAL_CANVAS_BRANDED_DB_PATH_API` / `MEAL_CANVAS_USAGE_DB_PATH_API` 仍可覆盖，未设置时使用上述正式路径。
- `/api/health` 实测返回：`status=ok`、`default_db_path=…/data/build/meal_canvas.sqlite`、`food_count=13694`、`nutrient_row_count=425557`。

## 7. 前端接入验证（实测）

前端代码未改动数据层，继续走 `/api/*`；vite 代理到 127.0.0.1:8000。实测 API：

| 校验项 | 结果 |
| --- | --- |
| 默认 ingredients | total=7,047（5,377+1,670） |
| usage_scope=all | 13,694 |
| prepared_dish / ready / unknown | 3,033 / 3,155 / 459 |
| data_type（all 范围） | foundation 469 / sr_legacy 7,793 / survey 5,432 |
| 品牌库 ingredients / all | 878,135 / 1,999,950，全部 `library_scope=branded` |
| 品牌库搜索 `cereal` | total=28,629，scope 仅 branded |
| 中文缺失回退 | 搜到并以英文展示（见 §5） |
| 排序分页 | alpha_en 第 1/2 页无重叠、升序正确、total 一致 |
| 分类筛选 | category_code=2404 → total=41 |
| 详情+营养 | fdc 2706337（Abalone）：summary 能量 177 kcal 等 28 项核心，份量 2 条；`/nutrients` 返回 30 项、能量取 1008 单值 |
| 元数据 | categories 300 条（默认+品牌合并去重）、营养素 37 条 |

浏览器实测（http://localhost:5173）：默认 7,047 条；`Milk, human`（含逗号）搜索正常；全部用途 13,694、成品菜 3,033 与 API 一致；`Broccoli, raw` 详情营养/份量正常；加入餐盘后改 150g，能量/蛋白质实时更新；营养来源分析入口正常；品牌库入口保持隐藏。

附带修复：搜索词含 `,` `'` 等标点曾触发 FTS5 语法错误（500）。已在 `backend/app/api/routers/foods.py` 中对 FTS 查询词做标点清洗（LIKE 与别名查询不变），修复后 `Milk, human` 正常返回。

## 8. 测试真实结果

| 项 | 命令 | 结果 |
| --- | --- | --- |
| 后端 pytest | `.\.venv\Scripts\python.exe -m pytest backend\tests -q` | 114 collected，全部通过 |
| 后端 ruff | `python -m ruff check backend` | All checks passed |
| 前端 typecheck | `npm.cmd --prefix frontend run typecheck` | 通过 |
| 前端 lint | `npm.cmd --prefix frontend run lint` | 通过 |
| 前端 vitest | `npm.cmd --prefix frontend run test -- --run` | 3 文件 27 用例全部通过 |
| 前端构建 | `npm.cmd --prefix frontend run build` | 成功（39.15s；chunk>500kB 警告为既有 ECharts 懒加载分包，不影响功能） |

## 9. 尚未解决 / 已知限制

1. 默认库中文覆盖低：verified 仅 249，glossary 1,073 待核验，12,372 条暂无中文名（英文回退展示，不影响功能）。待核验清单在 `data/build/sample/zh_pending.csv` 口径，需后续人工/词典扩充。
2. 品牌库 1 条记录 `description_en` 为空（fdc 776874），来自原始数据本身；未伪造名称。
3. 品牌库无 `food_portion`，克重换算在前端按每 100g 进行；`food_summary` 缺失的 103,700 条为全核心营养未知商品，界面按 “—” 处理。
4. `data/reports/USAGE_CLASSIFICATION_REVIEW.md`（第二轮审计）基于修复前规则生成，其中已修复的 6 类问题描述已过时；sauce / restaurant / 带配料等待复核项保持不变，未批量改动。
5. FTS5 对中文按单字切分，中文长词搜索召回偏宽（既有行为，本次未改动）。
6. 用途分类 `unknown`：默认库 459 条、品牌库 29,613 条，按规则保留未猜测，可通过 `usage_scope=all` / `usage_class=unknown` 查看。
