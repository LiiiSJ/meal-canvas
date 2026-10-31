# Meal Canvas 数据预处理简要报告

生成时间：2026-10-23 · 适用范围：sample 导入模式（真实数据有限抽样）。
本报告以当前最新 sample 数据库与构建日志为依据，面向论文初稿中的数据预处理章节。

---

## 1. 数据来源与版本

| 数据源 | 类型标识 | 版本/日期 | 原始行数 | 用途 |
| --- | --- | --- | ---: | --- |
| Foundation Foods | `foundation_food` | 2026-04-30 | 469（真实食品，`food.csv` 全部 `data_type=foundation_food`） | 默认食材库，全量纳入 |
| SR Legacy | `sr_legacy_food` | 2018-04 | 7,793 | 默认食材库，分层抽样 |
| FNDDS / Survey Foods | `survey_fndds_food` | 2021—2023 | 5,432 | 默认食材库，分层抽样；标记为"膳食调查食品/组合食品" |
| Branded Foods | `branded_food` | 2026-04-30 | 1,999,950 | 独立品牌库，不混入默认库 |

**数据源路径**：`C:\Users\Markli\Desktop\营养餐盘项目\数据集\` 下四个 USDA ZIP 文件，只读、不复制、不修改。

---

## 2. 样例抽样与筛选方法

抽样由 `backend/app/etl/sample_manifest.py` 生成确定性清单（`manifest.json`，含 SHA256 校验），保证任意两次 sample 构建结果一致。

| 数据源 | 抽样规则 | 实际选中 |
| --- | --- | ---: |
| Foundation | 全量 469 条 `food.csv` 中 `data_type='foundation_food'` 的食品。**不**使用 `foundation_food.csv` 白名单（395 条是 Foundation food.csv 的子集，差 74 条已纳入） | 469 |
| SR Legacy | 按 `food_category_id` 分层，每类最多等距 12 条；另强制加入 15 条核心食材（米饭煮熟形态、土豆形态、豆腐基础形态） | 315 |
| FNDDS | 统计 `wweia_food_category` 真实食品数，从 ≥5 条的分类中取至少 100 个，每类等距 5 条；额外强制加入无营养的 FDC 2705383（Milk, human） | 501 |
| Branded | 分批扫描 1,999,950 条商品，定向覆盖 20 组 GTIN 多版本、无营养记录、已停售、ml/MLT 份量、非质量单位、无品牌分类六类边界（每类 10 条），再按 fdc_id 等距补 250 条常规样本 | 349 |

样例仅作为开发/测试基线，**非全量数据的清洗结果**。

---

## 3. 数据清洗规则

| 阶段 | 规则 | 影响的记录 |
| --- | --- | --- |
| 食品类型筛选 | Foundation 用 `food.csv` 的 `data_type='foundation_food'`（469 条），**不**用 `foundation_food.csv`（395 条） | 确保不遗漏任何真实 Foundation 食品 |
| 营养白名单过滤 | 只处理 37 个已中文化的核心营养素（`data/curation/nutrient_zh.csv`）；其余营养行记入 `nutrient_rows_skipped`，**不是错误数据** | Foundation 11,830 / SR 15,765 / Survey 17,500 行被抽样规则跳过 |
| 能量候选值折叠 | Foundation 318 个食品的原始 CSV 存在 2+ 个 kcal 口径（1008、2047、2048 同时出现），按 1008 → 2048 → 2047 优先级只写入一条 `nutrient_id=1008`；候选者折叠，记入 `energy_conflict` 质量事件 | Foundation 416 行候选折叠为 1 条，实际写入 378 条能量 |
| 未知营养素定义 | Foundation `nutrient_id=2066`（"Unknown nutrient"）不在 Foundation `nutrient.csv` 定义中，跳过 | Foundation 33 行，记入 `unmapped_nutrient` 质量事件 |
| 重复营养行 | 同一食品同一营养素出现多行时取第一条（能量候选值折叠之外的情况） | Foundation 1 行，记入 `duplicate` 质量事件 |
| 负数值 | 保留 `raw_amount`、`amount=NULL`、`quality_flag='negative'`；不静默改成 0 | Foundation / SR 共 10 行 |
| 原始零值 | `amount=0` 共 3,157 行，**全部来自原始数据**；ETL 不凭空补 0 | 0 行被凭空补 0 |
| 缺失值 | `quality_flag='missing'` 为 0；`amount=NULL` 仅出现在 negative/unmapped 情况 | 0 行；Foundation 91 个食品无能量记录（客观缺失） |
| 单位未知 | 单位不在 `{g, mg, µg, kcal, kJ, IU}` 集合时标记 `quality_flag='unit_unknown'` | 0 行（sample 未触发） |
| FNDDS 传统编号映射 | FNDDS `food_nutrient.nutrient_id` 是传统编号（如 `301`、`208`），必须经 `nutrient.nutrient_nbr → nutrient.id` 映射，**禁止**直接用作 FDC nutrient_id | Survey 500 个能量、14,500 个其他营养行全部通过此映射 |
| Branded 无份量 | Branded 数据源无 `food_portion.csv`，不伪造克重；`ml/MLT/MG/IU` 份量**不**换算成克 | Branded sample 0 行份量记录 |
| Branded GTIN 多版本 | 同一 GTIN 的多个 `publication_date` 版本**全部保留**，不视为重复脏数据 | 20 组多版本，每组 2—3 条全部入库 |

---

## 4. 主要关联方式

```
food (fdc_id, PK)
 ├── food_nutrient (fdc_id + nutrient_id, PK)
 │    └── nutrient (id, PK)
 ├── food_portion (fdc_id → food.fdc_id)
 ├── food_summary (fdc_id, PK) — 核心营养快速查询
 ├── food_alias (fdc_id + alias, PK) — 中文搜索别名
 └── quality_event (fdc_id → food.fdc_id) — 只用于追溯

food_fts (fdc_id + search_tokens) — 中文 FTS5 搜索
```

`fdc_id` 贯穿所有表作为关联键，同时保留原始 `data_type`、`source_dataset`、`source_version` 可追溯字段。

---

## 5. 营养单位标准化与缺失值

**统一基准**：所有纳入 `food_nutrient` 的 `amount` 值都以**每 100 克**为基准，来源：

- Foundation / SR Legacy：`food_nutrient.amount` 字段直接是每 100 克值
- FNDDS：`food_nutrient.amount` 字段直接是每 100 克值（FNDDS 已统一）
- Branded：`food_nutrient.amount` 字段是每包装值，**不自动换算**

**食材实际营养贡献**（后端计算逻辑）：

```
实际营养量 = 每100克营养含量 × 食材实际克数 ÷ 100
```

**能量归一化**：

| nutrient_id | 含义 | 处理 |
| --- | --- | --- |
| 1008 | Energy (kcal) | 优先写入；若 CSV 缺失则从 2048 回退，再从 2047 回退 |
| 2048 | Energy (Atwater General Factors) | 1008 为空时的候选 |
| 2047 | Energy (Atwater Specific Factors) | 2048 也为空时的候选 |
| 1062 | Energy (kJ) | **独立存储**（`quality_flag='ok'`），不并入 kcal |

四个能量编号**不允许相加**。Foundation 469 条真实食品中：1008=135、2048=214、2047=29、无能量=91。

**缺失 vs 零 vs 负数**：

| 情况 | `amount` | `quality_flag` | 实际行数 |
| --- | --- | --- | ---: |
| 原始零值 | 0.0 | ok | 3,157 |
| 原始负数 | NULL | negative | 10 |
| 原始空值/缺失 | — | missing | 0 |
| 能量候选折叠 | 仅最优候选保留 | ok/negative | 折叠 416 |

---

## 6. 食材中文化方法

三层映射表，**全部独立于 USDA 原始数据**（不修改原始英文描述）：

| 文件 | 行数 | 内容 | 来源 |
| --- | ---: | --- | --- |
| `data/curation/nutrient_zh.csv` | 37 | 核心营养素中文名称、单位、分组、小数位、是否核心 | 人工核验，对照 Foundation nutrient.csv |
| `data/curation/category_zh.csv` | 303 | FDC 分类 28 条 + WWEIA 分类 172 条 + 品牌分类 103 条 | 人工核验 + 词典规则（品牌名保留英文） |
| `data/curation/food_zh.csv` | 249 | 常见食材人工核验中文名、别名、拼音 | 人工核验，对照 Foundation / SR Legacy 原始英文描述 |
| `data/curation/glossary_rules.csv` | 67 | 术语规则生成的候选翻译（如 `broccoli → 西兰花`） | 词典规则，标记 `glossary` 状态 |

**三级状态**：

| `zh_status` | 含义 | 后端是否显示中文名 |
| --- | --- | --- |
| `verified` | 人工核验，对照原始英文描述前缀匹配 | 显示中文名 |
| `glossary` | 词典规则自动生成候选翻译 | 显示中文名 + "词典译名" 标签 |
| `none` | 未映射 | 显示英文原名 |

**关键约束**：

- Branded 商品**全部保留英文原名**（`zh_status='none'`），禁止伪造品牌中文商品名
- 人工核验覆盖 **249 条**不同 fdc_id 的食材，含 10 种常见核心食材的全部真实形态
- 待核验清单 `zh_pending.csv`（默认库 1,036 条）和 `zh_pending_branded.csv`（品牌库 349 条）作为后续工作输入

---

## 7. 样例数据库真实记录数

### 默认食材库 `meal_canvas.sqlite`（1,285 食品 / 33,869 营养行 / 2,773 份量）

| 数据源 | 食品 | 营养行（已写入） | 份量 | energy_conflict | unmapped | duplicate | zh_verified |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Foundation | 469 | 9,179 | 187 | 304 | 33 | 1 | 234 |
| SR Legacy | 315 | 10,216 | 599 | — | — | — | 15 |
| FNDDS | 501 | 15,000 | 1,987 | — | — | — | — |
| **合计** | **1,285** | **33,869** | **2,773** | **304** | **33** | **1** | **249** |

逐数据源对账（不变量全部 `diff_vs_db=0`）：

```
Foundation  : 21,459 input − 11,830 skipped(白名单) − 416 energy_collapsed − 33 unmapped − 1 duplicate = 9,179 written  ✓
SR Legacy   : 25,981 input − 15,765 skipped(白名单) = 10,216 written  ✓
Survey      : 32,500 input − 17,500 skipped(白名单) = 15,000 written  ✓
```

**450 差额完整解释**：Foundation 21,459 − 11,830 − 9,179 = **450 = 416(energy_collapsed) + 33(unmapped) + 1(duplicate)**。SR Legacy 与 Survey 无能量多口径、无未知营养、无重复行，差量为 0。

### 品牌独立库 `meal_canvas_branded.sqlite`（349 商品 / 4,430 营养行 / 0 份量）

| 数据源 | 商品 | 营养行 | 份量 | zh_verified | GTIN 多版本 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Branded | 349 | 4,430 | 0 | 0（全部 none） | 20 组保留 |

---

## 8. 最新测试与数据质量检查

| 类别 | 数量 | 全部通过 |
| --- | ---: | --- |
| pytest 单元 / 端到端测试 | 32 | ✓ |
| ruff lint 检查 | All checks passed | ✓ |
| validate 数据质量检查 | 32 | ✓ |

数据质量核心指标（实测值）：

| 指标 | 结果 |
| --- | --- |
| 默认库不含品牌商品 | 0 条 |
| 品牌库不含非品牌食品 | 0 条 |
| 品牌库不伪造 food_portion | 0 行 |
| 营养表无孤儿记录 | 0 行 |
| 份量表无孤儿记录 | 0 行 |
| 营养表无重复主键 | 0 组 |
| 0 值仅来自原始数据 | 0 行被凭空补 0 |
| 负数保留 raw_amount | 10 行 negative |
| 黄金样本能量对照 | 12/12 一致 |
| 清单覆盖完整度 | Foundation 469/469、SR 315/315、Survey 501/501、Branded 349/349 |

---

## 9. 尚未完成的工作

| 工作项 | 状态 | 说明 |
| --- | --- | --- |
| full 模式全量导入 | **未执行** | 需要 `--mode full --confirm-full` 显式授权；当前仅 sample |
| 中文食品名人工核验 | 249 / 1,285 ≈ 19% | 待核验清单 1,036 条（默认）+ 349 条（品牌） |
| 品牌商品中文名 | 全 none | 品牌商品禁止自动翻译；需要人工确认后才能补充 |
| 份量信息 | Branded 全部 0 行 | 无 `food_portion.csv`；ml/MLT/MG/IU 份量不换算成克 |
| 前端 / FastAPI API | **未开始** | 下一阶段 |
| 正式数据库路径 | **未创建** | sample 与 full 物理隔离；full 会写 `data/build/meal_canvas.sqlite` |
| Foundation 部分食品无能量 | 91 / 469 ≈ 19% | Foundation 能量覆盖率 80.6%；属于原始数据客观缺失 |

---

## 10. 论文数据预处理方法参考文本（中文初稿）

### 数据来源

本研究采用美国农业部（USDA）FoodData Central（FDC）数据库中的四个独立数据集作为营养基础数据来源：Foundation Foods（2026 年 4 月版本，469 条真实基础食品）、SR Legacy（2018 年 4 月版本，7,793 条传统营养数据）、FNDDS 膳食调查食品（2021—2023 年，5,432 条）和 Branded Foods（2026 年 4 月版本，约 200 万条品牌商品）。原始数据以 ZIP 压缩包形式只读存放，不做任何复制或修改。

### 数据清洗与标准化

数据清洗在三个层次上独立进行：食品类型筛选、营养素关联标准化和数据质量标记。Foundation Foods 使用 `food.csv` 中 `data_type="foundation_food"` 字段筛选出 469 条真实基础食品记录，而非 USDA 官方提供的白名单文件（395 条是子集，差 74 条全部纳入）。四个数据集的食品、营养素和份量表各自具有不同的字段结构：FNDDS 的 `nutrient_id` 使用传统编号（如 208、301）而非 FDC 编号，必须通过 `nutrient.nutrient_nbr → nutrient.id` 映射表建立关联。

营养素标准化建立在 USDA 原始编号基础上，优先处理 37 个核心营养素。能量字段涉及三种可能的计算口径（FDC 编号 1008、2048、2047），同一食品若同时拥有多个 kcal 值，按 1008 → 2048 → 2047 优先级只保留一条；而 1062（kJ）独立存储，不与 kcal 合并。缺失值、原始零值和负值被严格区分：负值保留在 `raw_amount` 字段中，标记 `amount=NULL` 和 `quality_flag="negative"`，不静默改写为零；原始零值（3,157 行）全部来自 USDA 原始数据，ETL 不凭空补充零值。

### 中文化处理

中文名称映射通过独立的 curation 层实现，不修改 USDA 原始英文描述。建立了五个独立 CSV 文件：`nutrient_zh.csv`（37 个核心营养素）、`category_zh.csv`（303 条 FDC/WWEIA/品牌分类）、`food_zh.csv`（249 条人工核验常见食材）、`glossary_rules.csv`（67 条词典规则）和 `zh_pending.csv`（待核验清单）。每种食品有三级状态：`verified`（人工核验）、`glossary`（词典规则生成）、`none`（未映射）。品牌商品不自动生成中文商品名，全部保留英文原名。

### 样例数据库

为开发和测试构建了两个分离的 SQLite 数据库：`meal_canvas.sqlite`（Foundation 469 + SR 315 + FNDDS 501 = 1,285 食品 / 33,869 营养行）和 `meal_canvas_branded.sqlite`（349 品牌商品 / 4,430 营养行）。Foundation 的 450 行营养差额完全可追溯：能量多口径折叠 416 行、未知营养素跳过 33 行、重复行去重 1 行，逐数据源对账全部 diff=0。数据完整性通过 32 项自动化测试和 32 项数据质量校验持续保障。
