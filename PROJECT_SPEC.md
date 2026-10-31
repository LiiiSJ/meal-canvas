# Meal Canvas · 营养餐盘设计师 — 项目规格

| 项目 | 内容 |
| --- | --- |
| 文档版本 | v1.4（每周膳食计划与今日餐单阶段修订） |
| 状态 | 审计、sample 数据、中文化映射与后端 API 已完成；前端页面、食材库、餐盘与每周计划已完成 |
| 日期 | 2026-10-31 |
| 技术负责人 | TRAE（本项目） |
| 产品形态 | 本地运行的 Web 应用（React + FastAPI + SQLite） |
| 数据来源 | USDA FoodData Central 四个 CSV 数据集 |

---

## 1. 项目定位

### 1.1 一句话描述

Meal Canvas（营养餐盘设计师）是一个以真实食品营养数据为基础的中文交互式膳食设计与营养对比平台：用户直接拖拽、称量、替换食材，实时看到餐盘营养结构的变化，并能继续追问“变化从哪里来”。

### 1.2 核心价值

本项目不是“营养计算器 + 几张图”，而是三个连续闭环：

1. **操作闭环**：添加、删除、调整克数、替换食材，营养结果即时变化。
2. **理解闭环**：任何总量都能下钻到“哪些食材贡献了多少”，而不是只给一个数字。
3. **对比闭环**：两套餐盘的差异不仅显示“差多少”，还能解释“由哪些食材、哪些替换造成”。

所有可视化都必须服务于这三个闭环。图表不是装饰，不能以普通柱状图/饼图作为主要视觉亮点。

### 1.3 目标用户

- 想了解日常食物营养结构的普通成年人。
- 想设计一日三餐或单餐组合，并比较不同组合的人。
- 需要向他人解释“这盘饭营养为什么不同”的学习者、健身人群、家庭教育场景。

不面向：临床患者、需要医学营养治疗的个体、专业餐饮配方成本核算。

### 1.4 明确的目标与非目标

**目标**

- 使用四个 USDA 数据集的真实数值，保留食品 ID、英文名、数据类型与来源。
- 中文界面完整、一致，中文名称有独立映射层。
- 交互优先：默认视图突出少量关键信息，复杂图表按需展开。
- 本地方案管理与导出，无需账号体系。
- 可在 Windows 本地一条命令启动前后端。

**非目标（本期不做）**

- 不做用户注册、云端同步、社交分享。
- 不做疾病诊断、处方、医学建议。
- 不伪造、不插值、不推测任何缺失营养值。
- 不把数 GB 原始数据打包进前端。
- 不在本期引入机器学习推荐或“AI 营养师”。
- 不做真实食物照片；全部使用统一风格的扁平插画图标。

---

## 2. 用户与关键场景

| 场景 | 用户动作 | 系统反馈重点 |
| --- | --- | --- |
| 认识一种食物 | 搜索“西兰花”，打开详情 | 每 100g 营养、数据来源、缺失项、常用份量 |
| 设计一盘饭 | 拖入米饭、鸡胸肉、西兰花，调克数 | 总能量与三大营养素、数据覆盖率、缺失提示 |
| 理解贡献 | 点击“蛋白质” | 哪些食材贡献最多、各占多少、谁未提供该数据 |
| 比较两餐 | 方案 A/B 并排 | 3 个关键差异 + 差异来源下钻 |
| 做替换决策 | 把“猪肉”换成“鸡胸肉”预览 | 替换前后差值，确认后才应用 |
| 设定目标 | 设定能量/蛋白质目标 | 当前值与目标距离，超出/不足一目了然 |
| 探索规律 | 打开营养探索地图 | 高蛋白低脂、高纤维等分布，可筛选 |
| 追溯来源 | 打开数据说明页 | 数据集版本、口径、授权、限制 |

---

## 3. 数据基座（已核验）

> 本节数字来自 2026-10-22 对工作区外 `..\数据集` 四个 ZIP 的实际流式扫描，不是估计值。未核验的事项均明确标注。

### 3.1 数据文件

原始文件位于 `c:\Users\Markli\Desktop\营养餐盘项目\数据集`（工作区之外），保持 ZIP 原样，不解压、不入库：

| 数据集 | 文件名 | ZIP 大小 | 说明 |
| --- | --- | ---: | --- |
| Foundation Foods | `FoodData_Central_foundation_food_csv_2026-04-30.zip` | 3,825,741 B | 2026-04 版本 |
| SR Legacy | `FoodData_Central_sr_legacy_food_csv_2018-04.zip` | 6,074,592 B | 2018-04 版本 |
| FNDDS / Survey Foods | `FoodData_Central_survey_food_csv_2024-10-31.zip` | 3,325,692 B | 文件内 `start_date=2021-01-01`、`end_date=2023-12-31`，即 2021–2023 FNDDS |
| Branded Foods | `FoodData_Central_branded_food_csv_2026-04-30.zip` | 448,767,220 B | 2026-04 版本，约 428 MiB |

ETL 直接以流式方式读取 ZIP 内的 CSV（`zipfile.ZipFile.open()` + `TextIOWrapper`），避免解压出约 3 GB 中间文件。

**路径配置（2026-10-23 复核有效）**：上述目录当前实际存在，四个 ZIP 均可读。后端通过环境变量 `MEAL_CANVAS_DATA_DIR` 指定原始数据目录，默认值即该路径；不复制 ZIP 到工作区。若路径无效，启动/构建必须失败并输出中文错误，明确列出缺失的 ZIP 名称与期望目录，禁止静默回退或假装文件存在。`data/raw/foundation/` 等四个标准子目录仍不存在，ETL 不以它们为前提。

### 3.2 四个数据集的结构差异（关键，不可假定一致）

| 维度 | Foundation | SR Legacy | FNDDS / Survey | Branded |
| --- | --- | --- | --- | --- |
| `food.csv` 列 | `fdc_id, data_type, description, food_category_id, publication_date`（5 列） | 同 Foundation（5 列） | 同 SR（5 列） | `fdc_id, data_type, description, food_category_id, publication_date, market_country, trade_channel, microbe_data`（8 列，多 3 列） |
| 真实食品记录 | **仅 469 条** `data_type=foundation_food` | 7,793 条 | 5,432 条 | 1,999,950 条 |
| `food.csv` 中的非食品记录 | 有：`sub_sample_food` 75,055、`market_acquisition` 7,577、`sample_food` 4,079、`agricultural_acquisition` 810 | 无 | 无 | 无 |
| 分类来源 | `food_category.csv`（`food_category_id`） | 同 Foundation | `food.food_category_id` 即 WWEIA 类别代码，可直接关联 `wweia_food_category`；实测与 `survey_fndds_food.wweia_category_number` 0 处不一致 | `branded_food.branded_food_category` 文本；`food.food_category_id` 为空 |
| `food_nutrient.nutrient_id` 语义 | FDC 营养 ID（如 `1003`） | FDC 营养 ID | **传统营养编号（legacy number，如 `301`、`208`）** | FDC 营养 ID |
| `food_portion.csv` | 有 | 有 | 有 | **没有该文件**，份量信息在 `branded_food.serving_size / serving_size_unit / household_serving_fulltext` |
| `nutrient.csv` 行数 | 477 | 474 | 477 | 477 |
| `food_nutrient.csv` 行数 | 170,469（其中 469 个真实食品占 21,459 行） | 644,125 | 353,015 | 26,027,437 |

**已实证的 FNDDS 陷阱**：`Survey` 的 `food_nutrient.nutrient_id` 实际存放的是 `nutrient.csv.nutrient_nbr`（传统编号）。例如 survey 首行 `nutrient_id=301` 对应 `1087`（Calcium, Ca），`nutrient_id=208` 对应 `1008`（Energy）。若按 FDC ID 直接匹配，会得到 **0 条核心营养记录**（已实际验证）。

**已实证的 Foundation 陷阱**：`food.csv` 87,990 行中只有 469 行是真正的 foundation food，其余为样本/采购记录。若不按 `data_type` 过滤，食品库会被 8 万多条实验样本污染。`foundation_food.csv` 只有 395 行，**不能**作为 469 个食品的完整白名单。

**已实证的 FNDDS 分类事实**：`food.food_category_id` 存放的就是 WWEIA 类别代码，172 个类别全部能在 `wweia_food_category.csv` 找到；与 `survey_fndds_food.wweia_category_number` 的 5,432 条记录 0 处不一致。因此可直接用 `food.food_category_id` 关联分类，`survey_fndds_food` 用于交叉校验。

**已实证的能量陷阱**：同一食品可能同时存在 `1008 Energy`、`2047 Energy (Atwater General Factors)`、`2048 Energy (Atwater Specific Factors)`。三者是不同口径，**绝不能相加**。Foundation 469 个食品中 318 个存在多口径，277 个数值冲突；按 `1008 → 2048 → 2047` 取一个后，来源分布为 `1008` 135、`2048` 214、`2047` 29，另有 91 个无能量值。

### 3.3 实际规模与覆盖率（已扫描）

| 数据集 | 食品数 | 有能量记录 | 有蛋白质 | 有脂肪 | 有碳水 | 备注 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Foundation | 469 | 378（80.6%，1008/2047/2048 三者并集） | 425 | 413 | 377 | 1008 仅 135 条，必须回退到 2047/2048 |
| SR Legacy | 7,793 | 7,793（100%） | 7,793 | 7,793 | 7,793 | 覆盖完整 |
| FNDDS | 5,432 | 5,432（以 `208` 存储） | 5,432 | 5,432 | 5,432 | 每个食品固定 65 项营养 |
| Branded | 1,999,950 | 1,862,097 | 1,883,865 | 1,862,116 | 1,874,577 | 部分商品标签未申报某些项 |

非品牌基础食材合计 **13,694 条**；全部食品合计 **2,013,644 条**。品牌食品占 99.3%，因此**默认食材库不含品牌商品**，否则基础食材会被淹没。

**四个数据源的使用方式（已确认）**：

| 数据源 | 角色 | 默认食材库 | 界面标识 |
| --- | --- | --- | --- |
| Foundation Foods | 实验分析基础食材 | 是（469） | “基础食材 · 实验分析” |
| SR Legacy | 历史基础食材 | 是（7,793） | “基础食材 · 历史数据” |
| FNDDS | 膳食调查食品 / 组合食品 | 是（5,432），但必须单独标记 | “膳食调查食品 / 组合食品” |
| Branded Foods | 可选品牌商品库 | **否**，独立保存 | 界面不提供入口（后端保留） |

- 四个数据源都纳入数据处理设计，**不得删除 Branded Foods** 数据与后端能力。
- Branded 使用独立数据库文件 `meal_canvas_branded.sqlite`；**前端界面不提供品牌库切换入口**，后端保留 `library_scope=branded` 查询能力以便后续恢复。
- 默认食材库列表不因中文映射状态排除食品：`zh_status` 只是展示层信息，不是准入条件。`zh_status='none'` 的食品以英文原名展示并标注“暂无中文名”，可正常搜索、加入餐盘与参与计算。
- **食品用途是独立分类层**，与 USDA `data_type`、`zh_status` 互不混用。用途类别为 `basic_ingredient`（基础烹饪食材）、`processed_ingredient`（烹饪用加工食材）、`prepared_dish`（成品菜 / 组合菜）、`ready_to_eat`（即食成品）、`unknown`（证据不足）。
- 用途判定来源：`data/curation/usage_categories.csv`（按 `(category_source, category_code)` 的类别映射）+ `usage_rules.csv`（带优先级的两阶段描述规则）+ `usage_overrides.csv`（按 `fdc_id` 的人工覆盖）。规则引擎在 `backend/app/usage/`，生成独立用途库 `data/build/sample/meal_canvas_usage.sqlite`（`food_usage(fdc_id, library_scope, usage_class, rule_source, rule_id, reason)`）。
- **不得把 `data_type` 当作用途分类**：Foundation / SR Legacy 中也存在成品或即食记录；FNDDS 也不得整体归为成品菜或基础食材，须逐条按类别与名称证据判断。
- 默认搜索只返回 `basic_ingredient` 与 `processed_ingredient`（`usage_scope=ingredients`）；`prepared_dish` / `ready_to_eat` / `unknown` 需显式选择“全部用途”（`usage_scope=all`）或按用途精确筛选（`usage_class`）。用途未知记录保留原记录，不猜测、不删除、不合并。
- 用途过滤在后端 SQL 中完成（LEFT JOIN 用途库），搜索、筛选、总数与分页共用同一条件；不得只过滤前端当前页。
- FNDDS 不得与基础食材混为一类；列表、详情、搜索排序都必须显示其数据类型标识。

### 3.4 单位与计算口径

- Foundation / SR Legacy / FNDDS 的 `food_nutrient.amount` 均为 **每 100g 可食部**。
- Branded 的 `food_nutrient.amount` 同样按 **每 100g** 归一（由标签值换算）。
  - 已用样本 `fdc_id=1105904`（WESSON Vegetable Oil）核验：`fat=93.33g/100g`、`energy=867 kcal/100g`，与标签 1 Tbsp(15ml)=120 kcal/14g 按密度换算到 100g 的量级一致。
- 本项目统一以 **克（g）** 为餐盘计量单位；液体也按克计，界面上不提供“毫升→克”的自动密度换算，避免引入无来源假设。
- 微量营养素显示单位沿用 `nutrient.unit_name`（G / MG / UG / KCAL / IU），不在前端擅自换算。
- `food_nutrient` 只导入 `nutrient_zh.csv` 已中文化的 37 个营养素；其余原始营养行不写入数据库，按数据源计入 `nutrient_rows_skipped`，不属于错误。
- 求和时必须使用全精度，只在最终展示时四舍五入。

### 3.5 缺失值规则（硬约束）

**缺失 ≠ 0。** 数据层用“行不存在”表示未报告；API 用 `null` 表示未知；UI 用“—”加说明表示未知。

- 不允许把空字符串、空值、缺失营养行填成 0。
- 餐盘合计只累加已知值；同时返回该营养素的**克重覆盖率**：`已知该值的食材克重 / 餐盘总克重`。
- 覆盖率 < 100% 时，图表与数值旁必须显示“部分食材缺少该数据”，并可列出缺失食材。
- 对比两个餐盘时，如果某营养素的覆盖率差异 > 10 个百分点，必须提示“差异可能来自数据完整度，而非真实摄入差异”。
- 未知值不得参与排序或“贡献占比”的分母；贡献占比的分母是该营养素已知贡献之和，并标注覆盖率。

### 3.6 能量口径

ETL 为每个食品解析出一个规范能量值，优先级固定为：

1. `1008 Energy`（首选）
2. `2048 Energy (Atwater Specific Factors)`（回退）
3. `2047 Energy (Atwater General Factors)`（再回退）

- **只取一个值**，绝不求和。
- 在 `food_nutrient` 中写入规范营养 ID `1008` 的一行，并保留 `origin_nutrient_id` 以便追溯。
- 同一食品的其他能量口径不写入规范行；其原始值记入质量报告（`raw_amount`）并以 `energy_conflict` 计数。
- `1062 Energy (kJ)` 只作为独立的单位记录，不参与 kcal 优先级，也不得与任何 kcal 值相加。
- FNDDS 先将 `208` 映射为 `1008`，再按同样规则处理。
- 三个来源都不存在时，能量记为未知（`null`），UI 不得显示 0 kcal。

### 3.7 数据源展示规则

每个食品详情必须展示：

- 原始 FDC ID
- 英文原始名称（不改写）
- 数据类型（Foundation / SR Legacy / FNDDS / Branded）
- 数据集版本（如 2026-04）
- 分类来源（FDC 分类 / WWEIA 分类 / 品牌分类）
- 中文名称状态（已核验 / 词典译名 / 暂无中文名）
- 品牌食品额外展示品牌名、GTIN/UPC（若有）、标签份量
- 指向 `https://fdc.nal.usda.gov/food-details/{fdc_id}` 的外链（如该 URL 结构在实现时仍有效，需实测）

### 3.8 审计发现的已知异常（ETL 必须处理）

| 数据集 | 异常 | 实测数量 | 处理规则 |
| --- | --- | ---: | --- |
| Foundation | `nutrient_id=2066` 不在营养字典且 `amount` 为空 | 33 行 | 丢弃并记入质量报告；不得导入空值 |
| Foundation | 负碳水 `1005 Carbohydrate, by difference` | 10 行 | 原始值留档，规范值标记不可用；不得改为 0 |
| Foundation | 食品内重复营养对 | 4 对 | 保留第一条并记录冲突 |
| Foundation | 非 ISO 日期 `M/D/YYYY` | 80 行（全部 `sub_sample_food`） | 不导入样本；如需导入必须显式解析 |
| Foundation | `foundation_food.csv` 行数不足 | 395 vs 469 | 不得作为白名单，必须用 `data_type` 过滤 |
| FNDDS | `Milk, human` 无任何营养记录 | 1 个（`2705383`） | 保留记录并标记“数据不完整” |
| FNDDS | 份量克重为 0 | 1 行（`2705383`） | 份量视为无效，不参与换算 |
| Branded | GTIN 重复行 | 1,534,840（唯一 465,110） | 保留全部版本；最新版本按 `publication_date` 取 |
| Branded | 无营养记录的食品 | 103,700 | 允许存在，界面显示未知，不填 0 |
| Branded | 份量单位含 `GRM/GM/MLT/MG/IU/MC` | 见审计报告 | 仅 `g/GRM/GM` 视为质量；`ml/MLT` 不转克；`MG/IU/MC` 不可用于营养换算 |
| Branded | `food_portion.csv` 不存在 | — | 只展示标签份量，不伪造家庭份量 |
| 全部 | 非质量单位 `IU/PH/SP_GR/MCG_RE/MG_ATE/UMOL_TE/MG_GAE` | 见审计报告 | 独立单位展示，不相加、不换克 |

`food_nutrient` 规范表必须增加 `quality_flag` 与 `raw_amount`，使异常值可追溯而不进入计算；完整证据见 `data/reports/DATASET_AUDIT.md`。

**Foundation 395 与 469 差异（已实测，2026-10-23 复核）**：

- `food.csv` 中 `data_type='foundation_food'` 的真实食品为 **469** 条，这是唯一正确的食品集合。
- `foundation_food.csv` 只有 **395** 行，且这 395 行全部带有唯一 `NDB_number`；它是一张“有 NDB 编号的交叉子集表”，不是食品主表，也不是白名单。
- 差值 **74** 条：`foundation_food.csv` 中不存在任何 `fdc_id` 不在 469 条内的记录（额外记录为 0）；74 条全部是“469 有、交叉表无”。
- 这 74 条中有 **73 条有营养记录、33 条有份量记录**，并包含常见基础食材，例如 `321359 Milk, reduced fat`、`321505 Salt, table, iodized`、`321900 Broccoli, raw`、`322228/322559/322892` 多种牛奶、`323444 Cheese, ricotta`、`324157 Sausage, breakfast`、`324860 Peanut butter`。
- 因此若以 `foundation_food.csv` 为白名单，会静默丢失 74 条真实食品与其中 73 条营养数据。ETL 与校验脚本都必须以 `food.data_type` 为准，并在校验报告中输出“469 / 395 / 74”三个数字及实际缺失清单，差异不为 0 时不得判定构建通过，除非用户书面确认。

**质量问题字段约定（ETL 与 API 一致）**：

| 字段 | 取值 | 含义 |
| --- | --- | --- |
| `food_nutrient.raw_amount` | REAL / NULL | 原始 CSV 中的 `amount` 原值，不做任何修正 |
| `food_nutrient.amount` | REAL / NULL | 规范化后用于计算的值；`NULL` 表示不可用 |
| `food_nutrient.quality_flag` | `ok` / `missing` / `negative` / `duplicate` / `unit_unknown` / `unmapped_nutrient` / `energy_conflict` | 该记录的可用性判定 |
| `food_portion.quality_flag` | `ok` / `zero_weight` / `amount_missing` / `non_mass_unit` | 份量是否可用于克重换算 |
| `food.zh_status` | `verified` / `glossary` / `none` | 中文显示名的可信级别 |
| `food.zh_review_status` | `verified` / `pending` | 该中文名是否已人工核验 |
| `food.library_scope` | `default` / `branded` | 属于默认基础食材库还是独立品牌库 |

规则：`quality_flag != 'ok'` 的记录不得进入营养合计与排序分母；原始值仍保留在 `raw_amount` 与质量报告中，禁止把负数、空值改写为 `0`。

### 3.9 外部营养补全（联网检索与合并，硬约束）

当食品存在缺失营养指标时（检查范围为 nutrient 元数据表全部 37 项营养素，不止 7 项核心），后端可从可靠外部来源检索并补全。**外部补全绝不等于估算**：所有数值必须可追溯到真实来源，且食品身份与计量基准足够一致。

**来源优先级**：

1. USDA FoodData Central API（同一食品的其他官方记录；需要 `MEAL_CANVAS_FDC_API_KEY`）。
2. Open Food Facts v2 API（仅限有明确 GTIN/商品身份的包装食品；免 Key，遵守 ≤1 req/s 与自定义 User-Agent，署名 ODbL / CC-BY-SA）。
3. 其他网页只能作为候选参考展示，绝不允许自动写入数值。

**身份匹配（必须在数值之前成立）**：只用原始英文描述、GTIN、状态词（raw/cooked/dried…）判断，禁止用中文名匹配。分级：`exact`（GTIN 一致——UPC-A/EAN-13 去前导零比较，或归一化描述逐词一致且状态一致）→ 允许自动补全；`similar` / `partial` → 仅作候选展示，永不写入计算；`none` → 丢弃。

**逐项处理**：只补缺失项（`null`），不覆盖有效 USDA 值，不把真实 0 当缺失；能量 kJ 不并入 kcal（独立 `energy_kj` 键）；IU 口径营养素（维生素 A IU、维生素 D IU）不做 IU↔µg 换算，来源单位不符时降级候选；单位换算只用显式白名单（g↔mg↔µg、serving(g) 线性），`ml` 份量与单位不明的值一律不进入计算；多个来源冲突时全部降级为候选，不静默选值。

**独立存储**：补全数据写入独立 SQLite 库（默认 `data/build/meal_canvas_enrichment.sqlite`，表 `enrich_source` / `enrich_value` / `enrich_attempt`），完整保留：外部来源与 URL、原始值/单位/基准、每 100g 标准化值与换算方法、匹配级别与证据、检索时间、许可说明、状态（`verified_external` / `candidate_review` / `rejected`）。USDA sample/正式库保持只读（`PRAGMA query_only=ON` 不取消），任何情况下不得写回。

**缓存与失效**：`not_found`/`partial` 负缓存 24h、`error` 10min 内不重复外呼；`POST refresh` 可强制绕过；同 fdc_id 并发请求进程内去重；超时/重试/限速由 Provider 基类统一处理。

**配置（环境变量，密钥绝不入前端或仓库）**：`MEAL_CANVAS_ENRICH_ENABLED`（默认 true）、`MEAL_CANVAS_FDC_API_KEY`、`MEAL_CANVAS_ENRICH_DB_PATH`、`MEAL_CANVAS_ENRICH_FDC_ENABLED` / `MEAL_CANVAS_ENRICH_OFF_ENABLED`、`MEAL_CANVAS_ENRICH_OFF_NAME_SEARCH`（默认 true；品牌库批量补全置 false 仅用 GTIN 精确查询）、`MEAL_CANVAS_ENRICH_TIMEOUT`、`MEAL_CANVAS_ENRICH_MAX_RETRIES`、`MEAL_CANVAS_ENRICH_OFF_INTERVAL`、`MEAL_CANVAS_ENRICH_FDC_INTERVAL`、`MEAL_CANVAS_ENRICH_NEGATIVE_TTL_MINUTES`、`MEAL_CANVAS_ENRICH_ERROR_TTL_MINUTES`、`MEAL_CANVAS_ENRICH_MAX_CANDIDATES`。

**批量补全**：`scripts/enrichment_batch.py` 对整库分批执行补全（缺核心营养最多者优先），进度实时落盘 `data/build/enrichment_batch_progress_<library>.json`，中断后同一命令断点续跑；负缓存与请求去重由服务层保证，补全库 verified 值全局计数随轮次报告。

**前端合并规则**：前端 `features/enrichment/merge.ts` 只采纳 `origin==='external' && status==='verified_external'` 的值填充缺失键；USDA 原值与真实 0 永不覆盖；合并副本立即参与餐盘计算；详情抽屉显示补全状态（查找中 / 已补全 / 候选待确认 / 未找到 / 服务不可用）与外部值徽标（悬浮可见来源与原始基准）；全部营养素列表中，USDA 无可用值而外部已核实的行以「外部补全」徽标补位展示（可点击打开来源），USDA 完全无记录的营养素按 nutrient 元数据追加展示行。

---

## 4. 数据处理与存储

### 4.1 ETL 总流程

```
四个 ZIP
  → 逐行流式读取（不解压全量）
  → 数据集适配器（字段语义归一）
  → 食品主表清洗（data_type 白名单、ID 唯一性）
  → 营养规范化（nbr → 规范 nutrient_id；能量回退；单位）
  → 中文映射层叠加（不修改原始字段）
  → 份量归一（food_portion 或 branded serving 字段）
  → SQLite 写入（事务分批）
  → 搜索索引构建（bigram + 英文 token + 拼音）
  → 质量校验报告
```

**适配器必须独立**，禁止用一个通用脚本假定四套数据同构：

- `FoundationAdapter`：只接收 `data_type=foundation_food`；分类取 `food_category_id`；营养 ID 直通。
- `SRLegacyAdapter`：全量 7,793 条；营养 ID 直通。
- `SurveyAdapter`：`food_nutrient.nutrient_id` 按 `nutrient_nbr` 解释，映射为 FDC 营养 ID；分类走 WWEIA；所有记录必须写入 `data_type='survey_fndds_food'` 并在界面标注“膳食调查食品 / 组合食品”。
- `BrandedAdapter`：只取 `data_type=branded_food`；分类取 `branded_food_category`；份量只读 `serving_size / serving_size_unit / household_serving_fulltext`；**写入独立品牌库**，`library_scope='branded'`，不进入默认食材库。

**双库落点（已确认）**：

| 目标库 | 内容 | 写入方式 | 默认查询 |
| --- | --- | --- | --- |
| `data/build/meal_canvas.sqlite` | Foundation + SR Legacy + FNDDS | 独立构建，先写 `.tmp` 再原子替换 | 是 |
| `data/build/meal_canvas_branded.sqlite` | Branded Foods | 独立构建，先写 `.tmp` 再原子替换 | 否，用户显式切换 |

- 两个库必须能独立构建、独立失败；品牌库构建失败不得影响主库。
- 两库共享同一套 `nutrient` 字典与 schema 版本号。
- 主库不存在时默认食材库 API 返回 503；品牌库不存在时品牌查询返回明确的“品牌库尚未构建”中文提示，而不是空结果。
- 任何 mode 都不得覆盖已存在的正式库（见 4.6）。

### 4.2 SQLite 逻辑模型

```sql
-- 食品主表
food (
  fdc_id            INTEGER PRIMARY KEY,
  data_type         TEXT NOT NULL,        -- foundation_food / sr_legacy_food / survey_fndds_food / branded_food
  description_en    TEXT NOT NULL,        -- USDA 原文，禁止改写
  name_zh           TEXT,                 -- 可为 NULL；NULL 表示暂无中文名
  zh_status         TEXT NOT NULL,        -- verified / glossary / none
  zh_review_status  TEXT NOT NULL,        -- verified（已人工核验）/ pending（待核验）
  brand_owner       TEXT,
  brand_name        TEXT,
  gtin_upc          TEXT,
  category_source   TEXT,                 -- fdc / wweia / branded
  category_code     TEXT,
  category_en       TEXT,
  category_zh       TEXT,
  publication_date  TEXT,
  source_dataset    TEXT NOT NULL,
  source_version    TEXT NOT NULL,
  serving_size      REAL,
  serving_unit      TEXT,
  household_serving TEXT,
  ingredients_en    TEXT,
  is_default_library INTEGER NOT NULL,    -- 1=非品牌基础食材
  library_scope     TEXT NOT NULL,        -- default / branded
  search_tokens     TEXT NOT NULL
);

-- 规范营养字典
nutrient (
  id          INTEGER PRIMARY KEY,        -- FDC nutrient id
  nbr         TEXT NOT NULL UNIQUE,       -- 传统编号，跨数据集稳定键
  name_en     TEXT NOT NULL,
  unit_name   TEXT NOT NULL,
  rank        REAL,
  name_zh     TEXT NOT NULL,
  group_zh    TEXT NOT NULL,
  is_core     INTEGER NOT NULL,
  decimals    INTEGER NOT NULL
);

-- 每 100g 营养值；行不存在 = 未报告（禁止用 0 代替）
food_nutrient (
  fdc_id            INTEGER NOT NULL,
  nutrient_id       INTEGER NOT NULL,
  amount            REAL,                 -- 规范值；NULL 表示不可用（不给计算）
  raw_amount        REAL,                 -- CSV 原值，不做修正
  quality_flag      TEXT NOT NULL,        -- ok / missing / negative / duplicate / unit_unknown / unmapped_nutrient / energy_conflict
  origin_nutrient_id INTEGER,             -- 原始行里的 ID，便于追溯
  PRIMARY KEY (fdc_id, nutrient_id)
);

food_portion (
  id INTEGER PRIMARY KEY,
  fdc_id INTEGER NOT NULL,
  amount REAL,
  modifier TEXT,
  portion_description TEXT,
  gram_weight REAL,
  quality_flag TEXT NOT NULL              -- ok / zero_weight / amount_missing / non_mass_unit
);

food_alias (                               -- 中文搜索别名，独立映射层
  fdc_id INTEGER NOT NULL,
  alias TEXT NOT NULL,
  alias_type TEXT NOT NULL,                -- zh / pinyin / en
  status TEXT NOT NULL,                    -- verified / glossary / none
  review_status TEXT NOT NULL,             -- verified / pending
  PRIMARY KEY (fdc_id, alias, alias_type)
);

food_summary (                             -- ETL 物化，列表页快速读取
  fdc_id INTEGER PRIMARY KEY,
  energy_kcal REAL,
  protein_g REAL,
  fat_g REAL,
  carb_g REAL,
  fiber_g REAL,
  sugar_g REAL,
  sodium_mg REAL,
  known_core_count INTEGER NOT NULL
);

meta (key TEXT PRIMARY KEY, value TEXT);   -- data_version / schema_version / build_mode / build_time / source_counts
```

约束：

- `food_nutrient` 主键天然防止同一食品同一营养素重复；ETL 若遇到重复行必须记录冲突并取 USDA 提供的第一条且报告，不得静默累加。
- `amount` 允许为 `NULL`，但 `raw_amount` 必须保留原始值；`quality_flag` 必填，禁止用 `0` 表示缺失或不可用。
- `food.library_scope` 与 `is_default_library` 必须一致：`default` ↔ 1，`branded` ↔ 0；校验脚本必须检查不一致为 0。
- 所有原始文本保留英文原值；中文只写入 `name_zh`、`category_zh`、`nutrient.name_zh` 等附加字段。
- 建立索引：`food(data_type)`、`food(library_scope)`、`food(is_default_library, category_code)`、`food(gtin_upc)`、`food_nutrient(fdc_id)`、`food_nutrient(quality_flag)`、`food_summary(energy_kcal, protein_g)`。

### 4.3 搜索索引

**已实测**：SQLite 3.51.0 支持 FTS5 trigram，但 trigram 对 **2 个汉字**的查询返回空结果（如“鸡胸”），不适合中文食材搜索。

采用方案：

- 将中文名、别名、英文名、拼音规范化为 **token 串**：中文按 **bigram（二元字组）** 切分并空格连接；英文按单词切分；拼音按全拼与首字母写入。
- 使用 `FTS5(tokenize='unicode61')` 索引 token 串，查询时同样把中文查询切成 bigram，做 AND 匹配；单字查询退化为前缀/子串匹配。
- 排序权重：完全匹配中文名 > 别名完全匹配 > 中文名前缀 > 子串 > 分词命中；同分时 Foundation `+10`、SR `+6`、FNDDS `+4`、Branded `0`，再做数据完整度加分。
- 品牌商品默认不参与搜索；用户显式切到“品牌商品”后才查询。
- 搜索框 250ms 防抖；空查询不返回全量，展示推荐分类。

### 4.4 中文名称映射层

**不直接修改 USDA 原始数据**。映射文件放在 `data/curation/`，随代码版本管理：

| 文件 | 字段 | 用途 |
| --- | --- | --- |
| `food_zh.csv` | `fdc_id, name_zh, aliases, pinyin, category_zh, status, review_status, source_note, verified_at` | 食品中文显示名与别名 |
| `nutrient_zh.csv` | `nutrient_id, nbr, name_en, name_zh, unit_zh, group_zh, decimals, is_core` | 营养名称与单位中文 |
| `category_zh.csv` | `category_source, category_code, name_en, name_zh, note` | FDC / WWEIA / 品牌分类中文 |
| `glossary_rules.csv` | `match_pattern, name_zh, status, note` | 规则译名（如 `Broccoli, raw` → `西兰花（生）`） |

**生成与核验策略（正式数据处理阶段执行）**：

1. **基础框架先行**：先生成 `nutrient_zh.csv` 与 `category_zh.csv`，因为这两类条目数量有限且可完整覆盖；营养单位中文映射必须覆盖全部核心营养与常见微量营养。
2. **常见食材人工核验**：首期人工核验不少于 150 个常见基础食材（谷物、面食、蛋、禽畜肉、鱼虾、豆制品、奶、蔬菜、水果、坚果、油脂、调味品），`status=verified` 且 `review_status=verified`。
3. **规则译名候选**：其余非品牌食品按 `glossary_rules.csv` 生成候选中文名，`status=glossary`、`review_status=pending`；界面必须显示“词典译名（待核验）”标签。
4. **无法可靠翻译**：`name_zh=NULL`、`status=none`、`review_status=pending`，界面显示英文原名 + “暂无中文名”。
5. **待核验清单**：ETL 每次构建生成待核验清单（full 为 `data/build/zh_pending.csv`，sample 为 `data/build/sample/zh_pending.csv`；字段 `fdc_id, description_en, candidate_zh, rule_matched`），仅供人工核验使用，不进入版本库。
6. **核验回写**：人工核验结果只写回 `data/curation/*.csv`，不得在数据库里直接改中文名；重建后自动生效。
7. **覆盖统计**：校验报告必须输出 `verified / glossary / pending-none` 三类数量与占比，以及品牌商品中被翻译的通用描述数量。

三级状态，界面必须可区分：

| 状态 | 含义 | 界面表现 |
| --- | --- | --- |
| `verified` | 人工核验过的常见食品中文名 | 正常显示中文名 |
| `glossary` | 基于人工维护术语词典的规则译名（如 `Broccoli, raw` → `西兰花（生）`） | 显示中文名 + 小标签“词典译名” |
| `none` | 无可靠中文名 | 显示 USDA 英文原名 + 标签“暂无中文名” |

`review_status` 与 `zh_status` 正交：`verified` 名称必然 `review_status=verified`；`glossary` 与 `none` 默认 `pending`，人工核验后才升为 `verified`。

品牌商品：

- **品牌名、商品名保留英文原名**，不机翻。
- 可在英文名后补充“品牌分类”的中文（如 `Oils Edible` → “食用油”），但必须标明这是分类而非商品译名。
- 绝不编造品牌中文名。

首期人工核验目标：不少于 150 个常见基础食材（谷物、面食、蛋、禽畜肉、鱼虾、豆制品、奶、蔬菜、水果、坚果、油脂、调味品），每个都带中文别名与拼音；后续按使用频率扩充。覆盖不到的部分按三级规则老实展示，不假装全部翻译完成。

### 4.5 质量校验（每次重建数据库必须生成报告）

构建脚本必须在临时库写入完成后、原子替换前执行以下校验；任一硬性项失败即中止，保留旧库不动。

**计数与结构**

- 各数据集实际导入行数，与本文档 3.3 的基准比对：主库 Foundation 469、SR 7,793、FNDDS 5,432；品牌库 1,999,950（full）或 manifest 数量（sample）。
- 非食品 `data_type` 被排除的数量（Foundation 必须报告排除 87,521 条样本/采购记录）。
- `fdc_id` 重复数必须为 0；跨源 `fdc_id` 交集必须为 0。
- `library_scope` 与 `is_default_library` 不一致数必须为 0。
- 主库中 `library_scope='branded'` 的行数必须为 0；品牌库中 `library_scope='default'` 的行数必须为 0。

**Foundation 数量差异**

- 报告 `food.csv(data_type=foundation_food)` 计数、`foundation_food.csv` 计数、差值与差值清单。
- 实际值：469 / 395 / 74（73 条有营养、33 条有份量）。差异非 0 时必须在报告中解释；若与基准不一致且无书面说明，构建不得标记成功。

**营养与能量**

- 每个规范营养的缺失率；Foundation 能量覆盖率应为 378/469（80.6%）。
- 能量来源分布必须为 `1008` 135、`2048` 214、`2047` 29、无能量 91；与基准不符必须解释。
- 同一食品同时存在 1008/2047/2048 时，只允许 1 条规范能量值；`energy_conflict` 记录仅用于追溯，不计入计算。
- `1062 Energy (kJ)` 不得写入 kcal 字段，不得与任何 kcal 值相加；校验必须报告 kJ 行是否被正确隔离。
- 负值（如 10 行负碳水）必须保留 `raw_amount`、`amount=NULL`、`quality_flag='negative'`；负值进入计算的数量必须为 0。
- `amount` 为 `NULL` 且 `quality_flag='ok'` 的记录数必须为 0。
- 所有进入计算的 `amount` 必须为非负有限数；`NaN`/`Inf` 数量必须为 0。

**份量与单位**

- 品牌库 `food_portion` 行数必须为 0（不得伪造份量）。
- `serving_size_unit` 为 `ml/MLT` 的记录不得产生克重换算；`MG/IU/MC` 不得进入克重字段。
- 主库中 `gram_weight=0` 或空的份量必须标记 `zero_weight` / `amount_missing`，不得用于换算。

**中文化与追溯**

- 中文映射覆盖数量与状态分布：`verified`、`glossary`、`none` 各自数量与占比；`review_status` 分布。
- 待核验清单行数与数据库 `glossary + none` 数量一致：full 写 `data/build/zh_pending.csv`，sample 写 `data/build/sample/zh_pending.csv`。
- 随机抽取 10 个食品，逐项与原始 CSV 对照（脚本输出对照结果，含 `raw_amount`）。
- 报告写入 `data/build/validation_report.md` 与机器可读的 `data/build/validation_report.json`（sample 模式为 `data/build/sample/` 下同名文件；生成物，不入库）。

### 4.6 sample / full 双模式（硬性）

ETL 必须显式指定 mode，禁止默认全量执行。

| 项 | `sample` | `full` |
| --- | --- | --- |
| 用途 | 开发联调、口径回归、CI | 正式交付数据库 |
| 数据来源 | 真实 CSV，但只导入固定 manifest 中的 `fdc_id` | 全量 |
| 输出目录 | `data/build/sample/` | `data/build/` |
| 是否可覆盖正式库 | **否**，物理隔离 | 只能写 `.tmp` 后原子替换，不得直接写正式文件 |
| 触发方式 | `--mode sample`（默认拒绝无 mode 调用） | `--mode full --confirm-full` |
| 校验 | 必须通过 4.5 的全部结构项；计数以 manifest 为准 | 必须通过 4.5 全部项且计数与基准一致 |

**sample 输出命名（固定，不得混用）**：

| 文件 | 路径 | 说明 |
| --- | --- | --- |
| sample 主库 | `data/build/sample/meal_canvas.sqlite` | Foundation + SR Legacy + FNDDS |
| sample 品牌库 | `data/build/sample/meal_canvas_branded.sqlite` | Branded |
| sample manifest | `data/build/sample/manifest.json` | 固定抽样结果与规则 |
| 校验报告 | `data/build/sample/validation_report.md` / `.json` | 本次构建的质量报告 |
| 待核验清单 | `data/build/sample/zh_pending.csv` | 中文名待人工核验 |
| 中文化报告 | `data/build/sample/DATA_LOCALIZATION_REPORT.md` | 中文化覆盖与状态分布 |
| 构建日志 | `data/build/sample/logs/*.log` | 每次运行的真实日志 |

正式库固定为 `data/build/meal_canvas.sqlite` / `data/build/meal_canvas_branded.sqlite`，临时库为对应路径加 `.tmp`。sample 目录与正式库路径必须不同，相同即拒绝执行。

**sample manifest**：`data/build/sample/manifest.json` 由脚本生成并记录每个数据集的真实 `fdc_id` 列表、抽样规则、分类分布、生成时间与回查结果。manifest 中不得出现原始 CSV 不存在的 ID；生成后必须逐条回查原始数据确认存在。

**覆盖范围（sample 必须覆盖）**：

- Foundation：全部 469 条（体量小，且包含负值、多能量口径、无能量、无份量等异常样本）。
- SR Legacy：按 25 个分类分层抽样，约 300–400 条，保证每个分类至少 5 条。
- FNDDS：**先统计各 WWEIA 分类的真实食品数**，从“至少 5 条真实食品记录”的分类中选择至少 100 个分类，每个选中分类抽至少 5 条；预计 500–600 条，**实际数量由分类分布决定**。若满足条件的分类不足 100 个，必须如实报告实际覆盖分类数，不得生成或伪造记录。必须包含 `2705383 Milk, human`（无营养）与至少 1 条份量克重为 0 的记录。
- Branded：按六类真实边界情况**按类型定向选取并逐项记录**：①同一 GTIN 的多个版本；②无营养记录的商品；③已停售商品（`market_country` 等停售标记，按实际字段判定）；④`serving_size_unit` 为 `ml/MLT`；⑤非质量单位（`MG/IU/MC` 等）；⑥`branded_food_category` 为空的商品。目录之外再补足约 500 条常规样本。manifest 必须为每类列出实际选中的 `fdc_id` 与验证结果，不得只随机抽取 500 条就声称覆盖边界情况。
- 三源核心营养映射必须全部被 sample 覆盖（FNDDS 的 `208 → 1008`、`301 → 1087` 等至少各命中一次）。

**验证方式**：

1. sample 构建完成后，逐条核对 manifest 与数据库行数一致。
2. 对 4.5 的全部硬性项执行校验，异常类型必须在 sample 中至少出现一次（用于证明处理规则生效）。
3. 用 5–10 个黄金样本对照原始 CSV 的 `raw_amount` 与规范 `amount`。
4. sample 报告必须写明“这是真实数据子集，不是正式库”，且 API 不得默认加载 sample 库。
5. full 模式只有在 sample 校验通过、用户明确确认后才允许执行。

---

## 5. 技术架构

### 5.1 总体结构

```
┌──────────────────────────────────────────────┐
│ 浏览器（React + TypeScript + Vite）           │
│  食材库 / 餐盘 / 每周计划 / 今日餐单 / 对比     │
│  探索 / 方案 / 数据说明                        │
│  ECharts（按需加载） + dnd-kit + Lucide        │
│  IndexedDB / localStorage：方案与偏好          │
└───────────────┬──────────────────────────────┘
                │ 仅本地 HTTP，/api/*
┌───────────────▼──────────────────────────────┐
│ FastAPI（127.0.0.1:8000）                      │
│  食品查询 / 营养计算 / 对比 / 替代候选 / 探索   │
│  每周计划读写（独立计划库）                     │
└───────────────┬──────────────────────────────┘
        ┌───────┴──────────────────────────────┐
        │ 只读连接                              │ 可写连接（仅计划库）
┌───────▼──────────────────────────────┐ ┌────▼─────────────────────────────────┐
│ 食品类 SQLite（只读）                 │ │ SQLite：meal_canvas_planner.sqlite   │
│  meal_canvas.sqlite：默认食材库       │ │  每周膳食计划（weekly_plan / meal /  │
│  meal_canvas_branded.sqlite：品牌库   │ │  meal_item），与食品库物理隔离        │
│  meal_canvas_usage.sqlite：用途库     │ │  用户计划数据，不含 USDA 原始数据     │
│  meal_canvas_enrichment.sqlite：补全  │ │                                      │
│  均由 ETL 从 ../数据集/*.zip 流式构建 │ │                                      │
└──────────────────────────────────────┘ └──────────────────────────────────────┘
```

### 5.2 前端技术选型

| 能力 | 选择 | 理由 |
| --- | --- | --- |
| 框架 | React 19 + TypeScript + Vite | 类型安全、开发快 |
| 路由 | react-router-dom | 页面与详情深链 |
| 数据请求 | TanStack Query | 缓存、重试、加载/错误状态统一 |
| 全局状态 | Zustand | 餐盘与对比槽位，轻量 |
| 拖拽 | @dnd-kit/core + @dnd-kit/sortable | 可访问、支持键盘、TS 友好 |
| 图表 | Apache ECharts（按需模块引入） | 散点、桑基、热力、自定义系列 |
| 图标 | lucide-react | 界面图标统一 |
| 食材插画 | 自建 SVG 图标库 | 扁平、统一、无照片、可控 |
| 样式 | CSS Modules + 设计令牌（CSS 变量） | 精确控制卡通风格，避免类名堆砌 |
| 本地存储 | IndexedDB（idb） | 方案快照容量大；偏好用 localStorage |
| 测试 | Vitest + Testing Library；Playwright 冒烟 | 计算逻辑与关键交互 |

不引入 UI 组件库（避免风格被默认主题带偏）；基础控件自行封装，保证统一视觉。

### 5.3 后端技术选型

| 能力 | 选择 |
| --- | --- |
| Web 框架 | FastAPI |
| 服务器 | Uvicorn |
| 数据访问 | 标准库 `sqlite3` + 手写 SQL（不引入 ORM） |
| 校验/序列化 | Pydantic v2 |
| 配置 | pydantic-settings，读取 `.env` |
| CSV | 标准库 `csv` + `zipfile` 流式读取 |
| 拼音/分词（ETL） | pypinyin（仅构建期依赖） |
| 测试 | pytest + httpx |
| 代码质量 | ruff |

食品类 SQLite 以只读方式提供服务：`PRAGMA query_only=ON`；ETL 是离线单写者，不与 API 并发写。唯一可写库是独立的每周计划库 `meal_canvas_planner.sqlite`，由 `/api/planner` 写入，不读写任何食品数据。

### 5.4 本地持久化

- 方案（餐盘）保存在 IndexedDB，结构见 7.10。
- 用户偏好（默认数据集、目标、显示单位）保存在 localStorage。
- 每周膳食计划保存在后端独立应用库 `data/build/meal_canvas_planner.sqlite`，通过 `/api/planner` 读写；不得写入 USDA 食品库、品牌库、用途库或外部补全库。计划库只存计划结构（周、餐次、食品引用与克数），食品营养仍按 `food_key` + `library_scope` 实时查询。
- 每个方案保存 `dataVersion`（数据库构建哈希）与食材营养快照；数据更新后打开旧方案显示“使用保存时快照”的提示，而不是悄悄换数。
- 除每周计划外不上传任何用户数据。

### 5.5 配置与启动

环境变量（后端）：

```dotenv
MEAL_CANVAS_DATA_DIR=C:\Users\Markli\Desktop\营养餐盘项目\数据集
MEAL_CANVAS_DB_PATH=./data/build/meal_canvas.sqlite
MEAL_CANVAS_BRANDED_DB_PATH=./data/build/meal_canvas_branded.sqlite
MEAL_CANVAS_SAMPLE_DIR=./data/build/sample
MEAL_CANVAS_USAGE_DB_PATH_API=./data/build/sample/meal_canvas_usage.sqlite
MEAL_CANVAS_PLANNER_DB_PATH=./data/build/meal_canvas_planner.sqlite
MEAL_CANVAS_CORS_ORIGIN=http://localhost:5173
```

- `MEAL_CANVAS_DATA_DIR` 必须指向四个 ZIP 所在目录；路径无效时构建/启动立即失败，输出中文错误并列出缺失 ZIP 名称与期望路径。
- `MEAL_CANVAS_DB_PATH` 只用于默认食材库；品牌库路径独立，缺失时品牌功能返回“品牌库尚未构建”。
- `MEAL_CANVAS_SAMPLE_DIR` 用于 sample 模式输出，禁止与正式库路径相同；脚本必须校验两者不同，相同即拒绝执行。
- `MEAL_CANVAS_USAGE_DB_PATH_API` 指向用途分类库；缺失时食品列表/详情接口返回 503 中文错误，提示先运行 `python -m backend.app.usage.build --mode sample`。
- `MEAL_CANVAS_PLANNER_DB_PATH` 指向每周计划库；首次访问计划 API 时自动建库建表，不依赖任何食品库。

本地环境事实：

- Python 3.13.9（Anaconda），使用项目内 `.venv` 隔离。
- Node v24.21.0；PowerShell 执行策略禁止运行 `.ps1`，**npm 必须用 `npm.cmd`**（如 `npm.cmd install`、`npm.cmd run dev`）。
- Git 2.55 可用；本轮未初始化仓库，是否初始化由用户决定。

---

## 6. API 契约

所有响应 JSON 使用 camelCase；服务端错误统一为 `{code, message, detail?}`，`message` 为中文。食品类接口只读、无鉴权；每周计划接口可写，仅监听 127.0.0.1、无用户体系（当前实现中 `/api/foods` 与 `/api/planner` 的字段沿用 snake_case）。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/health` | 健康检查，返回主库/品牌库各自是否可用、版本与构建时间 |
| GET | `/api/meta/sources` | 四个数据集版本、记录数、许可与口径；标明品牌库是否已构建 |
| GET | `/api/meta/nutrients` | 规范营养字典（含中文名、单位、是否核心） |
| GET | `/api/meta/categories` | 分类树（按数据集区分来源；品牌分类需显式请求） |
| GET | `/api/foods` | 搜索/筛选/分页；`library=branded` 时查询品牌库 |
| GET | `/api/foods/{fdc_id}` | 食品详情 + 全部营养 + 份量 + 来源（先主库后品牌库） |
| POST | `/api/foods/batch` | 按 ID 批量取详情（方案恢复，最多 100） |
| POST | `/api/plans/calculate` | 营养合计、覆盖率、缺失清单、逐食材贡献 |
| POST | `/api/plans/compare` | 两方案差异、关键差异、逐食材差异分解 |
| POST | `/api/substitutes` | 替换候选与预览 |
| GET | `/api/explore` | 散点探索数据（限定点数、排除缺失） |
| GET | `/api/enrichment/foods/{fdc_id}/resolved` | 缺失检测 + 已核实外部补全值的统一解析；缺失时按缓存策略自动检索 |
| POST | `/api/enrichment/foods/{fdc_id}/refresh` | 忽略负缓存强制重新检索（用户主动触发） |
| GET | `/api/planner/plans/{week_start}` | 读取整周计划；未保存时 `plan_id=null` 且返回 7 个空日 |
| PUT | `/api/planner/plans/{week_start}` | 整周覆盖保存 |
| DELETE | `/api/planner/plans/{week_start}` | 删除整周计划 |
| POST | `/api/planner/plans/{week_start}/meals` | 新建餐次 |
| PUT | `/api/planner/meals/{meal_id}` | 修改餐次；传 `items` 时整组替换食品 |
| DELETE | `/api/planner/meals/{meal_id}` | 删除餐次 |
| POST | `/api/planner/meals/{meal_id}/items` | 添加食品 |
| PUT | `/api/planner/meals/{meal_id}/items/{item_id}` | 修改克数 |
| DELETE | `/api/planner/meals/{meal_id}/items/{item_id}` | 删除食品 |
| POST | `/api/planner/entries` | 从食品详情直接加入某天某餐；餐次不存在时自动创建 |
| POST | `/api/planner/entries/batch` | 一次向某天某餐追加多个食品（整盘加入）；餐次不存在时自动创建，单事务写入 |

### 6.1 `GET /api/foods`

参数：

- `q`：关键词，可空；空时不返回全量。
- `library`：`default`（默认，查主库）或 `branded`（查品牌库）；`branded` 必须显式指定。
- `dataset`：逗号分隔，主库默认 `foundation,sr_legacy,survey`；查询品牌库时固定为 `branded`，其他值返回 422。
- `category`：分类编码。
- `usage_scope`：`ingredients`（默认，只含基础食材与加工食材）/ `all`（全部用途类别）。
- `usage_class`：`basic_ingredient` / `processed_ingredient` / `prepared_dish` / `ready_to_eat` / `unknown`；与 `usage_scope` 同时出现时以 `usage_class` 为准。
- `page`（默认 1）、`pageSize`（默认 24，最大 100）。
- `sort`：`relevance` / `energy_asc` / `protein_desc` / `name`。
- 响应新增 `usage_scope`、`usage_class`，列表项新增 `usage_class / usage_rule_source / usage_rule_id / usage_reason`。

品牌库未构建时，`library=branded` 返回 503，中文消息“品牌商品库尚未构建，请先运行品牌数据构建命令”；不得返回空列表冒充无结果。

响应：

```json
{
  "items": [{
    "fdcId": 747447,
    "nameZh": "西兰花（生）",
    "nameEn": "Broccoli, raw",
    "translationStatus": "verified",
    "translationReviewStatus": "verified",
    "dataset": "foundation_food",
    "libraryScope": "default",
    "dataTypeLabelZh": "基础食材 · 实验分析",
    "categoryZh": "蔬菜及蔬菜制品",
    "energyKcal": 34,
    "proteinG": 2.8,
    "knownCoreCount": 18
  }],
  "total": 1,
  "page": 1,
  "pageSize": 24,
  "dataVersion": "2026-10-22T..."
}
```

### 6.2 `POST /api/plans/calculate`

请求：

```json
{ "items": [{ "fdcId": 747447, "grams": 150 }] }
```

约束：1–50 项；`grams` 范围 1–5000；重复 `fdcId` 合并或拒绝（实现时统一合并并提示）。

响应核心字段：

```json
{
  "totalGrams": 150,
  "nutrients": {
    "1008": {
      "amount": 51,
      "unit": "KCAL",
      "coverage": 1.0,
      "missingFoods": []
    }
  },
  "contributions": [
    { "fdcId": 747447, "nutrientId": "1008", "amount": 51, "share": 1.0 }
  ],
  "dataVersion": "..."
}
```

`amount` 与 `share` 在覆盖率不足时仍需返回，但 `coverage < 1` 让前端明确标注；`missingFoods` 列出未提供该营养的食材。

### 6.3 `POST /api/plans/compare`

请求包含 `planA`、`planB`（各自 items），响应：

- `totals`：两方案各营养总量与覆盖率。
- `deltas`：绝对差、相对差（对方为 0 或未知时 `null`，不得除零）。
- `keyDifferences`：最多 3 条，按“绝对差 × 相对差”综合排序，并附中文解释片段所需数据。
- `drivers`：按食材的差异贡献分解（`deltaContribution`），正负分明。
- `warnings`：覆盖率差异、未知值、克重差异过大（默认 > 30%）等。

### 6.4 `POST /api/substitutes`

请求：`{ "fdcId": 123, "grams": 100, "planItems": [...] }`

返回最多 12 个候选，必须：

- 同分类优先；无同分类时退化为营养向量相似。
- 不包含原食材。
- 每个候选返回与原食材的逐营养差值，以及自身覆盖率。
- 明确标记“候选仅基于数据相似度，不代表营养建议”。

### 6.5 未知与错误

- 未知营养一律 `null`，并在响应中提供 `coverage` 与 `missingFoods`。
- 食品不存在：404，中文消息“未找到该食品”。
- 主库缺失：503，中文消息“营养数据库尚未构建，请先运行数据构建命令”。
- 品牌库缺失：503，中文消息“品牌商品库尚未构建，请先运行品牌数据构建命令”。
- 参数非法：422，中文说明具体字段（如 `library` 取值不是 `default`/`branded`）。

### 6.6 外部补全 `GET /api/enrichment/foods/{fdc_id}/resolved`

响应核心结构（字段与现有 `/api/foods` 实现一致，均为 snake_case）：

```json
{
  "fdc_id": 408968,
  "display_name": "照烧酱",
  "baseline": "每 100 克",
  "values": [{
    "key": "fiber_g", "value": 0.0, "origin": "external",
    "status": "verified_external", "usda_value": null,
    "source_name": "openfoodfacts",
    "source_url": "https://world.openfoodfacts.org/product/0075050006128.html",
    "conversion_method": null, "original_basis": "per_100g", "note": null,
    "nutrient_id": 1079, "name_zh": "膳食纤维", "unit_zh": "克", "decimals": 1
  }],
  "missing_keys": ["fiber_g"],
  "enrichment": { "attempted": true, "outcome": "enriched", "message": "已通过外部来源补全 1 项缺失指标。" },
  "candidates": [],
  "sources_enabled": [{ "name": "usda_fdc", "enabled": false, "reason": "未配置环境变量 MEAL_CANVAS_FDC_API_KEY…" }]
}
```

- `values` 固定覆盖 nutrient 元数据表全部 37 项营养素（不止核心 7 项），每项附带 `nutrient_id` / `name_zh` / `unit_zh` / `decimals` 供前端直接渲染非核心补全行。
- `values[].origin`：`usda`（原始值）/ `external`（已核实外部补全）/ `none`（缺失未知）。
- `outcome`：`no_missing` / `disabled` / `enriched` / `partial` / `not_found` / `error` / `cached`；`message` 为中文，可直接展示。
- `candidates` 只作参考展示，`match_level` 为 `similar`/`partial` 的记录永不进入 `values` 的计算路径。
- 该端点检索时可能访问外部网络；检索失败不产生 HTTP 错误，而是 `outcome=error` 并保留全部 USDA 原始数据。

### 6.7 每周计划 `/api/planner/*`

- 日期参数一律为 `YYYY-MM-DD` 纯日期字符串，服务端不做 UTC 转换；`week_start` 必须是周一，否则返回 400 中文错误。
- 餐次日期必须落在 `week_start` 至 `week_start + 6` 天内。
- 早餐/午餐/晚餐每天各最多一条；`snack` 可多条。违反时返回 400 中文错误。
- `amount_g` 必须 `> 0` 且 `≤ 10000`；`library_scope` 为 `default` / `branded`。
- 响应以 `{week_start, plan_id, created_at, updated_at, days:[{date, meals:[{meal_id, meal_date, meal_type, meal_name, sort_order, notes, items:[{item_id, food_key, library_scope, amount_g, sort_order, name_snapshot}]}]}]}` 为统一结构；写操作返回受影响周的最新整周计划。
- 整周保存先删除旧餐次（级联删除食品）再写入新结构，`weekly_plan.week_start` 唯一约束保证同一周只有一条计划。
- 计划写入独立库 `meal_canvas_planner.sqlite`，不触碰任何食品类数据库。

---

## 7. 功能规格

### 7.1 食材库

**目标**：快速找到基础食材，并看懂它的数据来源与完整度。

- 搜索：中文名、别名、拼音、英文名；2 字中文可用（bigram 索引）。
- 筛选：数据集（默认“基础食材”= Foundation + SR + FNDDS；品牌商品单独开关）、分类、营养排序（能量/蛋白质）。
- 卡片：统一食材图标、中文名（或英文名+状态标签）、分类、能量/蛋白质、数据完整度小标。
- 详情抽屉：
  - 原始信息：FDC ID、英文名、数据类型、数据集版本、分类来源、FDC 外链。
  - 每 100g 营养表：核心项在前，微量项可展开；未知显示“—”。
  - 常用份量（若 `food_portion` 有数据）；品牌商品显示标签份量。
  - 中文名状态与免责说明。
- 状态：加载骨架、空结果（中文提示+建议）、错误（可重试）、品牌未开启时的说明。
- 验收：搜索“西兰花”“jixiong”“broccoli”均能命中；缺失项不显示 0；所有文字为简体中文。

### 7.2 动态餐盘

**目标**：通过直接操作理解营养变化。

- 添加：点击卡片“加入餐盘”，或拖拽到餐盘区；触屏与键盘均可添加。
- 餐盘视觉：柔和盘形画布，食材以统一插画卡片分布在盘内；卡片大小只做轻微视觉暗示，**不按热量切分饼图**。
- 编辑：克数输入、滑杆、快捷份量（50/100/150/200g）；删除；拖拽排序。
- 实时合计：默认只突出能量、蛋白质、脂肪、碳水 + 数据覆盖率；其他营养在“查看全部”后展开。
- 克数变化即时反馈（前端用已缓存的每 100g 快照计算）；保存/对比前调用后端校验，前后端算法必须一致。
- 空状态：插画 + “从左侧食材库拖入第一样食材”。
- 验收：调整克数 1g 即更新；缺失营养显示“—”与提示；总克重与逐项之和一致；键盘可完成添加与调克。

### 7.3 营养聚光灯

**目标**：回答“这项营养主要来自哪里”。

- 入口：点击任一营养指标（默认视图中的四项或展开后的任意项）。
- 视觉：横向“贡献河带”——按贡献从大到小排列的食材段，带宽表示贡献占比；鼠标悬停放大，点击聚焦该食材。
- 右侧列表：食材名、贡献量、占比、克重；未提供该营养的食材单独列出，标注“未提供数据”，不计入分母。
- 覆盖率 < 100% 时，河带末端显示斜纹“未知”段，并说明未知克重。
- 禁止用饼图。
- 验收：占比之和（在已知部分）为 100%；点击食材可定位到餐盘卡片；未知项不被当作 0。

### 7.4 双餐盘变化透视

**目标**：比较两套方案，先给结论，再给来源。

- 两个槽位 A/B，可分别从已保存方案载入或复制当前餐盘。
- 首屏只显示 3 条“关键差异”卡片：例如“能量 +180 kcal（+23%）”“蛋白质 −12g”“膳食纤维 +4.1g”，附一句来源提示（如“主要因为少了鸡胸肉，多了西兰花”）。
- 下钻：
  - 点击差异卡 → 展开该营养的食材差异分解（正/负贡献河流或成对斜率图，不用普通双柱）。
  - 可查看“仅某一食材变化造成的影响”。
- 警告：覆盖率差异 > 10 个百分点、未知值、总克重差异 > 30%。
- 验收：任意差异可追溯到食材与克数；除零/未知不产生 `Infinity` 或 `NaN`；A/B 交换后符号正确。

### 7.5 食材替换模拟器

**目标**：先预览，再决定。

- 选中餐盘中的食材 → 打开候选抽屉（同分类优先）。
- 候选卡片展示：替换后总能量/蛋白质/脂肪/碳水差值、该食材自身差异、覆盖率变化。
- “预览”状态：餐盘中原食材显示为半透明“幽灵卡”，新食材以虚线卡叠加；合计区显示“替换前 → 替换后”。
- 只有点击“应用替换”才写入方案；可一键取消。
- 若候选缺少某核心营养，明确提示“该候选数据不完整，预览为部分结果”。
- 验收：应用前后可撤销；预览不污染当前方案；差异计算与后端一致。

### 7.6 营养目标指示器

**目标**：把“离目标多远”变成直观距离。

- 用户可为能量、蛋白质、脂肪、碳水、膳食纤维、钠设置目标值与容差（下限/上限）。
- 视觉：环形“距离弧”，弧长表示完成度；超出容差用柔和橙色，未达用柔绿色，达标用中性成功色；不使用普通仪表盘。
- 文案：`距目标还差 23g` / `超出目标 12%` / `数据覆盖 86%，结果可能偏低`。
- 目标仅保存在本地；不提供“推荐摄入量”，避免无来源的医学建议。
- 验收：目标为空时不显示弧；覆盖率不足时提示；负数/超大目标有校验与中文错误。

### 7.7 食材营养探索地图

**目标**：在多维空间中发现食材特征与聚集。

- 散点图：X/Y 轴可选任意核心营养（默认蛋白质 vs 脂肪），可选对数轴；点颜色按分类，点大小按能量（或固定）。
- 交互：悬停详情、框选、点击加入餐盘、按数据集/分类筛选。
- 缺失处理：任一轴缺失的食品不绘制，并在图例旁显示“已排除 N 项（数据缺失）”。
- 默认最多展示 2,000 点；超过时按分类分层抽样，并明确提示“显示抽样结果”。
- 默认不包含品牌商品。
- 验收：坐标轴切换后重新查询；缺失提示准确；框选不会误选未绘制点。

### 7.8 营养流向图

**目标**：展示“食材 → 分类 → 所选营养”的贡献流向。

- 先选一项营养（单选），再渲染 Sankey：左列为食材（Top 8，其余合并“其他”），中列为食物分类，右列为该营养素总量。
- 流量值 = 该食材对该营养的贡献量；未知不计入，单独在图下方文字说明。
- 交互：悬停高亮路径与数值；点击食材定位餐盘；避免过多标签，默认只显示 Top 路径标签。
- 验收：流量总和等于该营养已知贡献合计；覆盖率不足时有提示；节点数受控，不出现连线蜘蛛网。

### 7.9 差异热力矩阵

**目标**：一次看清多个营养指标上的差异结构。

- 行 = 营养指标（默认 8 项核心，可展开），列 = 两方案中差异最大的 Top 12 食材 + 合计列。
- 单元格 = 该食材在 B 相对 A 的差异贡献（带符号），使用发散色阶（减少/增加），数值标签可开关。
- 缺失单元格使用斜纹而非 0；悬停显示原值、差值、覆盖率。
- 点击单元格 → 打开该食材差异解释。
- 验收：合计列等于各食材差异之和（在已知范围内）；缺失不显示为 0；色阶正负对称。

### 7.10 方案管理

**目标**：让方案可保存、可复用、可比较、可导出。

- 保存：名称必填（默认“未命名餐盘 + 日期”）、备注可选；同一方案可覆盖保存。
- 列表：卡片显示名称、食材数、总克重、能量、更新时间；支持打开、重命名、复制、删除、加入对比槽。
- 存储：IndexedDB；最多 100 个方案，超出提示删除。
- 快照结构：

```json
{
  "id": "uuid",
  "name": "高蛋白午餐",
  "createdAt": "ISO",
  "updatedAt": "ISO",
  "dataVersion": "build-hash",
  "items": [{
    "fdcId": 123,
    "grams": 120,
    "snapshot": {
      "nameZh": "鸡胸肉（生）",
      "nameEn": "Chicken, breast, raw",
      "dataset": "foundation_food",
      "per100g": { "1008": 120, "1003": 22.5, "1004": 2.6, "1005": 0 }
    }
  }],
  "goals": { "1008": { "min": 500, "max": 700 } }
}
```

- 导出：JSON（完整快照）、CSV（长表：方案、食材、克数、营养、数值、是否缺失）。
- 导入：仅接受本应用导出的 JSON，校验版本与结构；不执行任意代码。
- 数据版本变化：打开旧方案时提示“当前营养库版本与保存时不同，正在使用保存时快照”，提供“用最新数据重算”按钮。
- 验收：刷新后方案仍在；复制不共享引用；删除有确认；导出可被本应用重新导入。

**当前实现（阶段 4 子集：双方案快照）**

- 餐盘设计页可直接把当前餐盘「存为方案 A / 存为方案 B」，无需切换到对比页。
- 快照存于 IndexedDB 数据库 `meal-canvas` 的 `plans` store，key 为 `A` / `B`，结构为 `{ entries: [{ food, grams }], capturedAt: ISO }`。
- 快照与当前餐盘完全解耦：清空餐盘、刷新页面、切换页面都不影响已保存的方案。
- 对比页差异区：左侧为营养结构雷达图（每根轴按该指标双方较大值独立缩放，只比形状与相对高低），右侧为逐项明细（A 值 → B 值、绝对差与百分比差）；只要一侧有已知数据就参与比较，并标出覆盖率（如 `A 6/7`，低于 50% 橙色提示）；仅当两侧均无该项数据时不绘制，缺失值不按 0 补；雷达图按需懒加载。
- 尚未实现：方案命名、最多 100 个方案、JSON/CSV 导入导出、`dataVersion` 变更提示（对应上文完整方案管理）。

### 7.11 数据说明与授权

**目标**：让用户知道数据从哪来、能做什么、不能做什么。

- 四个数据集卡片：版本、记录数、用途、口径、下载来源链接。
- 说明：每 100g、缺失值处理、能量回退规则、FNDDS 使用传统编号、品牌数据来自标签、中文名三级状态。
- 明确：本项目不是医学建议；不用于疾病管理；品牌商品信息以包装标签为准。
- 显示数据库构建时间与 `dataVersion`。
- 许可：USDA FoodData Central 数据按美国政府公开数据政策属于公共领域（实际发布前需再次核对官方说明）；本项目保留出处与版本，不声称拥有数据版权。
- 外部补全来源署名：Open Food Facts 数据（ODbL / CC-BY-SA，需署名，openfoodfacts.org）；仅在存在明确 GTIN/商品身份时用于包装食品补全，补全值在界面标注“外部补全”并可查看来源链接。USDA FDC API 结果同样保留来源标注；未配置 API Key 时界面如实显示该来源不可用。

### 7.12 每周膳食计划与今日餐单

**目标**：提前安排周一到周日的早餐、午餐、晚餐与加餐，保存后随时查看当天该吃什么、各多少克。

- 入口：主导航「每周计划」(`/weekly`) 与「今日餐单」(`/today`)。
- 周视图：以周一至周日为自然周，默认当前周；顶部显示周日期范围、上一周/下一周/返回本周、当前日期标识；切换周读取对应周计划；某天无安排显示空状态。
- 餐次：每天默认早餐、午餐、晚餐三条主餐次，另可添加多个加餐；主餐次清空后保留卡片，加餐可单独删除。
- 食品：复用食材库搜索与选择组件（`FoodLibrary`），可一次暂存多种食品、分别填克数后一次确认全部加入；每餐可添加、改克数、删除食品，并显示该餐营养合计。
- 整盘加入：餐盘设计页与方案对比页可把当前餐盘 / A/B 快照整盘一次加入某天某餐（`/api/planner/entries/batch` 单事务写入）。
- 食品身份：引用 `food_key` + `library_scope`，并保存 `name_snapshot` 作为名称兜底；不写死任何食品。
- 营养：复用 `computePlateNutrition` 与 `mergeEnrichment`；缺失值显示“—”，不填 0；每餐显示能量、蛋白质、脂肪、碳水化合物、膳食纤维，整天显示四餐合计，周视图只提供每日能量横条概览。
- 保存：通过 `/api/planner` 写入独立计划库；刷新与来回切周不丢失；状态明确显示尚未保存/正在保存/已保存/保存失败；未保存切周弹窗提供保存并切换、放弃并切换、留在本页。
- 删除与复制：删除食品/清空餐次提供撤销条；支持把某天某餐复制到另一天同类型餐次（主餐替换目标、加餐追加），源餐次不变，复制后各自独立可改。
- 今日餐单：按本地日期定位今天，展示四餐食品与克数及营养合计；每餐可跳回计划页对应位置修改；今天无计划时显示空状态与「去制定今日餐单」。
- 从详情加入：食品详情抽屉与餐盘条目提供「加入计划」，选择日期、餐次与克数后调用 `/api/planner/entries`，餐次不存在时自动创建。
- 本阶段不做：自动生成整周菜单、AI 菜谱、购物清单、复杂饮食目标、账号与多用户。

---

## 8. 视觉设计系统

### 8.1 风格关键词

温暖奶油底、柔和绿色、浅橙色点缀；扁平、圆润、克制的卡通感；精致而非幼稚；留白充足，拒绝拥挤的数据大屏。

### 8.2 设计令牌

```css
:root {
  --bg-cream: #FFF8EE;
  --bg-card: #FFFFFF;
  --bg-soft: #F7EDDF;
  --green-500: #7FAE83;
  --green-300: #B9D3B3;
  --green-100: #E8F1E4;
  --orange-500: #F2A65A;
  --orange-300: #F8C99B;
  --orange-100: #FDEBDD;
  --berry-500: #D97B66;
  --sky-300: #A9CFDD;
  --ink-900: #3E3A34;
  --ink-600: #6E665C;
  --ink-400: #9A9186;
  --line: #EADFD2;
  --radius-lg: 24px;
  --radius-md: 16px;
  --radius-sm: 10px;
  --shadow-soft: 0 8px 24px rgba(94, 76, 56, 0.08);
  --motion-fast: 160ms;
  --motion-base: 240ms;
}
```

- 字体：中文使用系统栈 `"PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif`；数字与英文可用 `Nunito`（本地打包或回退系统字体），避免依赖不可访问的 CDN。
- 圆角：卡片 24px，控件 12–16px。
- 阴影：低对比、暖色阴影，不使用高科技蓝光大屏风。
- 图标：Lucide 线性图标，统一 1.75–2px 描边。

### 8.3 食材插画规范

- 自建 SVG，约 40 个基础图标（谷物、面、面包、蛋、鸡、猪、牛、鱼、虾、豆腐、奶、酸奶、叶菜、花菜、根茎、番茄、水果、坚果、油、调料等）。
- 统一：48×48 视框、圆头线条、扁平双色填充（主色 + 奶油高光）、统一光源在左上、无渐变噪点、无真实照片。
- 映射规则：按“分类 + 关键词”确定图标，同一食品在食材库、餐盘、替换、对比、方案卡片中必须使用同一个图标与同一主色。
- 未匹配食品使用分类兜底图标，不允许每页各画一套。
- 所有图标带 `aria-label`（食品中文名或“未命名食品”）。

### 8.4 布局

- 桌面（≥1200px）：左侧导航（食材库/餐盘/对比/探索/方案/说明）+ 中央工作区 + 右侧洞察栏。餐盘页为三栏，洞察栏默认只显示 4 个核心指标与覆盖率。
- 平板（768–1199px）：导航折叠为图标栏，洞察栏下移。
- 手机（<768px）：底部 Tab；食材库以底部抽屉呈现；图表最小高度 260px，横向可滚动表格需有替代视图。
- 默认视图原则：首屏最多 4 个数字 + 1 个主视觉 + 1 条提示；复杂图表需点击“深入分析”后出现。

---

## 9. 可视化规范

### 9.1 总体原则

- 不用普通柱状图/饼图作为卖点；不用 3D、不用无意义动画、不用彩虹色。
- 一屏只允许一个视觉主角；颜色数量默认不超过 6 个分类色。
- 所有图表必须能回答一个具体问题，并在标题中写出问题式文案（如“蛋白质主要来自哪里？”）。
- 图例、坐标轴、tooltip、空状态、加载状态全部中文。
- 未知数据必须显式表达（斜纹、虚线、灰点），绝不画成 0。

### 9.2 图表任务分配

| 功能 | 主视觉 | 明确不使用 |
| --- | --- | --- |
| 餐盘 | 盘形画布 + 食材插画卡 | 热量饼图 |
| 聚光灯 | 贡献河带（自定义系列/HTML） | 饼图、普通柱状图 |
| 双餐盘 | 双盘对照 + 关键差异卡 + 成对斜率/差异河 | 双柱状图 |
| 替换预览 | 幽灵叠加 + 差值胶囊 | 前后双饼图 |
| 目标 | 环形距离弧（自定义 SVG） | 仪表盘、进度条堆叠 |
| 探索 | 散点图（对数可选、框选） | 3D 散点 |
| 流向 | 桑基图（食材→分类→营养） | 复杂弦图（首期不做） |
| 热力矩阵 | 发散色阶热力图 + 斜纹缺失 | 普通表格替代交互 |

### 9.3 ECharts 使用约束

- 按需引入 `echarts/core` + 所需 chart/component，避免整包。
- 图表组件统一封装（`ChartShell`），负责尺寸、主题、空状态、加载、错误与 `prefers-reduced-motion`。
- 自定义主题从 CSS 令牌读取，不在各图表里散落硬编码颜色。
- 大数据散点使用 `large: true` 或抽样；不超过 2,000 点。
- 所有图表提供文本摘要（`aria-label` 或隐藏描述），保证屏幕阅读器可理解主要结论。

---

## 10. 中文与文案规范

- 所有界面文字为简体中文：导航、按钮、占位符、错误、空状态、加载、图表标题、图例、提示、帮助、设置、导出文件名说明。
- 集中管理文案：`frontend/src/i18n/zh-CN.ts`，禁止在组件中散落硬编码长句（短标签可例外）。
- 术语统一：
  - nutrient → 营养素；energy → 能量；protein → 蛋白质；fat → 脂肪；carbohydrate → 碳水化合物；dietary fiber → 膳食纤维；sodium → 钠。
  - data coverage → 数据覆盖率；per 100 g → 每 100 克；serving → 份量。
- 英文保留场景：USDA 原始食品名、品牌名、FDC ID、GTIN/UPC、科学单位（kcal、g、mg、µg）。保留时必须同时给出中文说明。
- 错误文案必须可行动：说明发生了什么 + 用户能做什么，例如“营养数据库尚未构建。请在项目根目录运行 `python -m backend.app.etl.build` 后重试。”
- 不使用“治愈”“疗效”“必须”“最佳”等医疗或绝对化措辞。

---

## 11. 性能、可访问性与响应式

### 11.1 性能预算

- 首屏 JS（不含图表 chunk）≤ 300 KB gzip；图表按页面懒加载。
- 基础食材搜索 p95 ≤ 200 ms（13,694 条）；品牌搜索 p95 ≤ 500 ms。
- 餐盘克数调整到界面更新 ≤ 50 ms（本地快照计算）。
- 首屏可交互 ≤ 2.5 s（本地环境）。
- 数据库：不含品牌 ≤ 400 MB；含品牌（仅核心营养）目标 ≤ 2 GB。
- 任何列表接口单页 ≤ 100 条；探索接口 ≤ 2,000 点。

### 11.2 可访问性

- 所有拖拽操作有键盘与按钮替代路径。
- 焦点可见；模态抽屉焦点锁定与 Esc 关闭。
- 文本对比度 ≥ 4.5:1；不仅靠颜色传达差异（配合符号/纹理/数值）。
- 图表提供文字结论；表单错误与字段关联。
- 尊重 `prefers-reduced-motion`。

### 11.3 响应式

- 手机端保留全部核心功能；复杂图表可折叠为“展开查看”。
- 餐盘在窄屏使用纵向卡片列表 + 盘形缩略图，不强行三栏。
- 桌面端不使用固定像素大屏布局，内容最大宽度 1440px。

---

## 12. 数据授权、隐私与免责声明

- 数据来源：USDA FoodData Central（Foundation Foods、SR Legacy、FNDDS、Branded Foods）。界面与数据说明页必须标注数据集名称、版本、下载日期与 FDC 链接。
- 许可：FDC 数据按美国政府公开数据政策提供，通常视为公共领域；**正式对外发布前需再次核对官方页面说明**，本规格不替代法律意见。
- 品牌食品数据由厂商或第三方提供，可能与最新包装标签不一致；以包装标签为准。
- 隐私：无账号、无埋点、无上传；方案只存浏览器本地。若未来增加分析，必须另行说明并征得同意。
- 免责声明（固定文案，数据说明页与首次使用提示中展示）：
  > 本工具用于营养知识学习与膳食结构探索，不构成医疗、营养或健康建议。数据来自 USDA FoodData Central，可能存在缺失、更新滞后或与实物标签不一致的情况。如有疾病或特殊营养需求，请咨询医生或注册营养师。
- 不得声称 USDA 为本项目背书。

---

## 13. 目录结构

```text
1/  (项目根目录)
├─ PROJECT_SPEC.md               # 本文件：完整项目规格
├─ DEVELOPMENT_PLAN.md           # 分阶段开发计划与验收门槛
├─ .gitignore
├─ .trae/
│  └─ rules/
│     └─ meal-canvas.md          # 项目级开发规则
├─ backend/
│  ├─ app/
│  │  ├─ api/                    # 路由：foods / plans / substitutes / explore / meta
│  │  ├─ core/                   # 配置、日志、错误处理
│  │  ├─ db/                     # 连接、schema.sql、查询
│  │  ├─ planner/                # 每周计划存储层（独立计划库，唯一可写库）
│  │  ├─ etl/                    # 四数据集适配器、构建、校验、中文映射
│  │  ├─ models/                 # Pydantic 请求/响应模型
│  │  └─ services/               # 营养计算、对比、替代、探索
│  ├─ tests/                     # pytest：口径、缺失、能量回退、API
│  └─ (阶段 1 创建 requirements.txt / pyproject.toml)
├─ data/
│  ├─ raw/                       # 可选本地缓存；已被 .gitignore 忽略
│  ├─ curation/                  # 中文名、营养名、分类映射（纳入版本管理）
│  ├─ reports/                   # 审计与校验报告（DATASET_AUDIT.md 等）
│  └─ build/                     # SQLite、校验报告（生成物，忽略）
│     └─ meal_canvas_planner.sqlite  # 每周计划库（用户数据，不入库）
├─ frontend/
│  ├─ public/
│  └─ src/
│     ├─ app/                    # 路由、布局、Provider
│     ├─ pages/                  # 食材库、餐盘、每周计划、今日餐单、对比、探索、方案、数据说明
│     ├─ features/               # 按功能拆分的交互与图表（含 planner/）
│     ├─ components/             # 通用 UI、ChartShell、FoodIcon
│     ├─ lib/                    # API 客户端、计算、存储、格式化
│     ├─ i18n/                   # zh-CN 文案
│     ├─ styles/                 # 设计令牌与全局样式
│     └─ assets/food-icons/      # 统一 SVG 食材插画
├─ scripts/                      # 启动、构建、校验脚本（阶段 1 起）
└─ docs/                         # 后续设计记录、截图、数据说明草稿
```

`data/curation/*.csv` 是唯一允许入库的 CSV（人工维护映射）；其余 CSV、ZIP、SQLite 均忽略。

---

## 14. 验收定义

一个阶段只有同时满足以下条件才可标记完成：

1. **真实运行**：实际执行构建/启动/测试，并记录输出；未运行的不得声称通过。
2. **数据诚实**：抽查至少 5 个食品，与原始 CSV 对照一致；缺失项显示未知而非 0。
3. **中文完整**：该阶段新增界面无英文残留（允许的原始名/单位/品牌名除外）。
4. **交互可用**：主路径可用键盘完成；加载、空、错误状态齐全。
5. **视觉一致**：同一食材在全部出现位置图标一致；无真实照片。
6. **可回滚**：新增数据构建可重复执行，失败不破坏旧数据库（先写临时库再原子替换）。
7. **文档同步**：规格或计划如有变更，同阶段更新。

---

## 15. 风险与限制

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 四数据集字段语义不同（FNDDS 用传统编号） | 营养全错/全空 | 每数据集独立适配器 + 固定样本回归测试 |
| Foundation 大量缺失能量（仅 80.6%） | 用户误以为 0 | 能量三级回退；仍缺失则显示未知与覆盖率 |
| 品牌食品 200 万条、2,600 万营养行 | 搜索慢、库大 | 默认不进入食材库；仅核心营养；显式开关；索引与分页 |
| 中文名无官方标准译名 | 翻译不可靠 | 三级映射；仅常见食材人工核验；品牌保留英文 |
| FNDDS 为美国膳食调查数据 | 与中国饮食不匹配 | 数据说明页明确；中文名只做名称映射，不改数值 |
| 品牌营养值为标签换算 | 与实物有偏差 | 标注来源；以包装为准 |
| 浏览器存储配额 | 方案丢失 | 快照精简、上限 100、导出提醒 |
| 拖拽可访问性 | 键盘用户不可用 | 所有操作提供按钮/输入替代 |
| 本地 API 端口冲突 | 启动失败 | 配置化端口；启动脚本检测并给出中文提示 |
| PowerShell 禁止 .ps1 | npm 命令失败 | 统一使用 `npm.cmd`；脚本给出说明 |
| 过度可视化 | 信息拥挤、难懂 | 默认 4 指标；复杂图按需展开；每图只回答一个问题 |

---

## 16. 阶段计划摘要

详细任务、验收门槛与顺序见 [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md)。

| 阶段 | 主题 | 产出 |
| --- | --- | --- |
| 0（已完成） | 规格、规则、骨架 | 本文件、开发规则、目录、忽略规则、计划、数据审计报告 |
| 1 | 数据管道 MVP（sample 先行） | 四源适配器（含 Branded 独立库）、双库 schema、中文映射、sample 构建与校验报告、只读 API |
| 2 | 前端骨架 + 食材库 | 设计系统、统一图标、搜索筛选、详情、中文状态 |
| 3 | 餐盘 + 计算 + 聚光灯 | 拖拽/调克、实时合计、覆盖率、贡献河带 |
| 4 | 方案管理 + 双餐盘对比 | IndexedDB、保存/复制/导出、关键差异与来源 |
| 5 | 替换模拟器 + 目标指示器 | 预览后应用、环形距离弧 |
| 6 | 探索地图 + 流向图 + 热力矩阵 | 三种深入分析视图 |
| 7 | 品牌数据启用 + 打磨 + 发布 | 品牌库 full 构建、品牌开关、数据说明、可访问性、E2E 冒烟 |

**下一步建议**：进入阶段 1 的准备子阶段，只实现 sample 模式：先落地四源适配器、质量字段、双库 schema 与中文映射框架，用真实 CSV 的 manifest 子集构建 sample 库并生成校验报告；sample 校验通过并经用户确认后，再单独执行 full 构建。full 构建前不得覆盖任何已存在的正式库。
