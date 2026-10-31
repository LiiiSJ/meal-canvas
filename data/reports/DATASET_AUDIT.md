# USDA FoodData Central 四数据集审计报告

| 项目 | 内容 |
| --- | --- |
| 报告版本 | v1.0 |
| 审计日期 | 2026-10-22 |
| 审计对象 | Foundation Foods 2026-04、SR Legacy 2018-04、FNDDS（Survey 2024-10-31 包，数据期 2021–2023）、Branded Foods 2026-04 |
| 审计方式 | 只读流式逐行扫描 ZIP 内 CSV；不落盘解压、不一次性载入内存；未修改原始文件 |
| 结论状态 | 审计完成，等待人工检查后进入 ETL 阶段 |
| 规格同步 | 已修正 `PROJECT_SPEC.md` 至 v1.1：`food.csv` 列、FNDDS 分类来源、审计异常、`data/reports/` 目录 |
| 报告位置 | `data/reports/DATASET_AUDIT.md` |

> 本报告所有计数、缺失数、重复数与示例值均来自对原始 ZIP 的实际扫描或包内官方字段说明。未实际核验的事项在第 12 节明确标注为“未验证”。

---

## 0. 结论摘要

1. **用户指定的四个目录全部不存在**：`data/raw/foundation/`、`data/raw/sr_legacy/`、`data/raw/fndds/`、`data/raw/branded/` 均为 `MISSING_DIRECTORY`。实际 ZIP 位于工作区之外的同级目录 `c:\Users\Markli\Desktop\营养餐盘项目\数据集\`。
2. **四个 ZIP 均存在且可读**，但结构并不一致：三个非品牌数据集的 `food.csv` 只有 5 列；Branded 有 8 列。Branded **没有 `food_portion.csv`**。
3. **Foundation 的 `food.csv` 有 87,990 行，但真实食品只有 469 行**（`data_type=foundation_food`）。其余 87,521 行是样本、采购和农业样本记录，必须过滤。`foundation_food.csv` 本身只有 395 行，不能当作 469 个食品的白名单。
4. **FNDDS 的 `food_nutrient.nutrient_id` 存的是传统编号 `nutrient_nbr`**（如 `301`、`208`），不是 FDC 营养 ID。按 FDC ID 直读会得到 0 条核心营养记录。必须通过 `nutrient.nutrient_nbr → nutrient.id` 映射。
5. **所有数据集的 `food_nutrient.amount` 都是“每 100g 食品”**，单位由 `nutrient.unit_name` 决定。`serving_size` 是标签份量，不是营养值的计算基准；CSV 中不存在“每份营养值”字段。
6. **能量有多个口径**：`1008 Energy (kcal)`、`2047 Atwater General`、`2048 Atwater Specific`、`1062 Energy (kJ)`。前三者只可选一个，后者是 kJ，不能与 kcal 相加。Foundation 有 318 个食品同时存在多种能量值，其中 277 个数值冲突。
7. **Branded 的 GTIN 大量重复**：1,999,950 行中唯一 GTIN 只有 465,110 个，重复行 1,534,840 行。重复码表示产品更新，不是可直接删除的重复记录，应按 `publication_date` 选最新版本。
8. **Branded 有 103,700 个食品没有任何营养记录**；其余食品营养项数从 1 到 48 不等。品牌数据不能假定“标签完整”。
9. **缺失必须继续表示为缺失**：数据库无行、API `null`、界面“—”。零值（如 Branded 的 8,522,624 个 0）是明确申报值，既不是缺失，也不能当作“完整”。
10. **默认食材库建议只含非品牌三源，共 13,694 条**：Foundation 469 + SR Legacy 7,793 + FNDDS 5,432。Branded 作为可选数据层，默认不进入食材库，避免 199 万商品淹没基础食材。

---

## 1. 审计范围、目录核查与文件实况

### 1.1 目录核查（关键）

审计开始前实际检查了用户指定的四个目录：

| 用户指定路径 | 实际状态 | 说明 |
| --- | --- | --- |
| `data/raw/foundation/` | **MISSING_DIRECTORY** | 不存在 |
| `data/raw/sr_legacy/` | **MISSING_DIRECTORY** | 不存在 |
| `data/raw/fndds/` | **MISSING_DIRECTORY** | 不存在 |
| `data/raw/branded/` | **MISSING_DIRECTORY** | 不存在 |

`data/raw/` 下当前只有 `.gitkeep`。因此本报告**没有从上述四个目录读取任何文件**，也没有假装读取成功。

实际使用的数据位于：

```text
c:\Users\Markli\Desktop\营养餐盘项目\数据集\
```

该目录在工作区之外，符合项目规则“原始数据只读、不入库”。本次审计未复制、解压或改写任何原始文件。

### 1.2 原始 ZIP 与校验值

| 数据集 | 文件名 | ZIP 大小 | SHA-256 |
| --- | --- | ---: | --- |
| Foundation Foods | `FoodData_Central_foundation_food_csv_2026-04-30.zip` | 3,825,741 B | `70457EE9D9342F43BDA2010318C85F04210C689FDEB9CD2DA4C513B0E8DBC655` |
| SR Legacy | `FoodData_Central_sr_legacy_food_csv_2018-04.zip` | 6,074,592 B | `B80817294B8850530AAEDF2E515C02593B1824F763A0FF356E5C2081643E6FD0` |
| FNDDS / Survey | `FoodData_Central_survey_food_csv_2024-10-31.zip` | 3,325,692 B | `5CCC25EC2777A8982FBB61378A42F415316173EB11E48C9A8BA4CB19F5A4F29C` |
| Branded Foods | `FoodData_Central_branded_food_csv_2026-04-30.zip` | 448,767,220 B | `26050A5D03197469813754743A21EE0FAD4CCF22B6AAC2A995846A987719FC49` |

### 1.3 ZIP 内部文件清单（实测未压缩大小）

#### Foundation Foods

| 文件 | 未压缩字节 |
| --- | ---: |
| `food.csv` | 7,229,830 |
| `food_nutrient.csv` | 10,089,141 |
| `food_portion.csv` | 714,051 |
| `nutrient.csv` | 21,556 |
| `food_category.csv` | 997 |
| `measure_unit.csv` | 1,969 |
| `food_attribute.csv` | 753,585 |
| `foundation_food.csv` | 17,257 |
| `sample_food.csv` | 39,068 |
| `sub_sample_food.csv` | 1,478,511 |
| `sub_sample_result.csv` | 5,294,585 |
| `market_acquisition.csv` | 914,133 |
| `agricultural_samples.csv` | 38,059 |
| `acquisition_samples.csv` | 155,247 |
| `input_food.csv` | 327,265 |
| 其他：实验室方法、换算因子、更新日志、字段说明 xlsx | — |

#### SR Legacy

| 文件 | 未压缩字节 |
| --- | ---: |
| `food.csv` | 793,104 |
| `food_nutrient.csv` | 36,366,059 |
| `food_portion.csv` | 918,790 |
| `nutrient.csv` | 21,464 |
| `food_category.csv` | 997 |
| `measure_unit.csv` | 1,955 |
| `food_attribute.csv` | 63,688 |
| `sr_legacy_food.csv` | 130,404 |
| `food_nutrient_derivation.csv` | 6,853 |
| `food_nutrient_source.csv` | 602 |
| `retention_factor.csv` | 13,304 |
| 其他：蛋白/热量换算因子、更新日志、记录数清单、字段说明 xlsx | — |

#### FNDDS / Survey

| 文件 | 未压缩字节 |
| --- | ---: |
| `food.csv` | 480,475 |
| `food_nutrient.csv` | 19,047,892 |
| `food_portion.csv` | 1,692,573 |
| `nutrient.csv` | 21,566 |
| `wweia_food_category.csv` | 5,119 |
| `survey_fndds_food.csv` | 293,397 |
| `input_food.csv` | 1,982,818 |
| `food_attribute.csv` | 1,608,165 |
| `measure_unit.csv` | 1,955 |
| `fndds_derivation.csv` | 4,826 |
| 其他：更新日志、字段说明 xlsx | — |

#### Branded Foods

| 文件 | 未压缩字节 |
| --- | ---: |
| `food.csv` | 375,881,194 |
| `branded_food.csv` | 954,002,257 |
| `food_nutrient.csv` | 1,496,063,311 |
| `nutrient.csv` | 21,556 |
| `food_attribute.csv` | 133,026,234 |
| `food_update_log_entry.csv` | 132,826,299 |
| `measure_unit.csv` | 1,969 |
| `microbe.csv` | 1,579 |
| **`food_portion.csv`** | **不存在** |
| `food_category.csv` | 不存在 |
| 字段说明 xlsx | 32,849 |

> Branded 的 `food_nutrient.csv` 解压后约 1.50 GB，`branded_food.csv` 约 954 MB，`food.csv` 约 376 MB。ETL 必须流式读取，不能一次性载入内存。

---

## 2. 核心文件真实表头

以下列名来自实际读取的 CSV 表头，不是按官方文档推测。

### 2.1 `food.csv`

| 数据集 | 列名 |
| --- | --- |
| Foundation | `fdc_id, data_type, description, food_category_id, publication_date` |
| SR Legacy | `fdc_id, data_type, description, food_category_id, publication_date` |
| FNDDS | `fdc_id, data_type, description, food_category_id, publication_date` |
| Branded | `fdc_id, data_type, description, food_category_id, publication_date, market_country, trade_channel, microbe_data` |

### 2.2 `nutrient.csv`（四个数据集同名同构）

```text
id, name, unit_name, nutrient_nbr, rank
```

- `id`：FDC 营养 ID（如 `1003`、`1008`）。
- `nutrient_nbr`：传统营养编号（如 `203`、`208`、`301`），是跨数据集稳定键；Foundation/SR/FNDDS 的字典中有 12 个营养素该字段为空。
- `unit_name`：该营养素的标准单位，官方说明为“per 100g of food”。
- 行数：Foundation 477、FNDDS 477、Branded 477、SR Legacy 474。

### 2.3 `food_nutrient.csv`（四个数据集同名同构）

```text
id, fdc_id, nutrient_id, amount, data_points, derivation_id, min, max, median, footnote, min_year_acquired
```

**关键差异**：`nutrient_id` 的语义随数据集变化。

| 数据集 | `nutrient_id` 实际含义 |
| --- | --- |
| Foundation | FDC 营养 ID（`nutrient.id`） |
| SR Legacy | FDC 营养 ID（`nutrient.id`） |
| FNDDS | **传统编号**（`nutrient.nutrient_nbr`），如 `301`、`208` |
| Branded | FDC 营养 ID（`nutrient.id`） |

### 2.4 `food_portion.csv`

```text
id, fdc_id, seq_num, amount, measure_unit_id, portion_description, modifier, gram_weight, data_points, footnote, min_year_acquired
```

- Foundation、SR Legacy、FNDDS 有该文件；**Branded 没有**。
- FNDDS 的 `amount` 按官方说明“Not defined for survey (FNDDS) foods (amount is instead embedded in portion description)”，实测 22,046 行全部为空。
- Foundation/SR/FNDDS 的 `measure_unit_id` 大量为 `9999`（SR 和 FNDDS 全部为 `9999`），表示份量单位写在 `portion_description`/`modifier` 中，不能直接按 `measure_unit.csv` 解析。

### 2.5 分类与调查关联表

| 文件 | 列名 | 存在数据集 |
| --- | --- | --- |
| `food_category.csv` | `id, code, description` | Foundation、SR Legacy |
| `wweia_food_category.csv` | `wweia_food_category, wweia_food_category_description` | FNDDS |
| `survey_fndds_food.csv` | `fdc_id, food_code, wweia_category_number, start_date, end_date` | FNDDS |
| `branded_food.csv` | `fdc_id, brand_owner, brand_name, subbrand_name, gtin_upc, ingredients, not_a_significant_source_of, serving_size, serving_size_unit, household_serving_fulltext, branded_food_category, data_source, package_weight, modified_date, available_date, market_country, discontinued_date, preparation_state_code, trade_channel, short_description, material_code` | Branded |

### 2.6 辅助表（本阶段不导入，但确认存在）

| 文件 | 列名 |
| --- | --- |
| `measure_unit.csv` | `id, name` |
| `food_attribute.csv` | `id, fdc_id, seq_num, food_attribute_type_id, name, value` |
| `food_update_log_entry.csv` | `id, description, last_updated` |
| `foundation_food.csv` | `fdc_id, NDB_number, footnote` |
| `sample_food.csv` | `fdc_id` |
| `sub_sample_food.csv` | `fdc_id, fdc_id_of_sample_food` |
| `market_acquisition.csv` | `fdc_id, brand_description, expiration_date, label_weight, location, acquisition_date, sales_type, sample_lot_nbr, sell_by_date, store_city, store_name, store_state, upc_code, acquisition_number` |
| `agricultural_samples.csv` | `fdc_id, acquisition_date, market_class, treatment, state` |
| `acquisition_samples.csv` | `fdc_id_of_sample_food, fdc_id_of_acquisition_food` |
| `input_food.csv` | `id, fdc_id, fdc_of_input_food, seq_num, amount, ingredient_code, ingredient_description, unit, portion_code, portion_description, gram_weight, retention_code` |
| `sr_legacy_food.csv` | 存在，未作为主食品表使用 |
| `food_nutrient_derivation.csv` | 存在（SR） |
| `retention_factor.csv` | 存在（SR） |
| `fndds_derivation.csv` | 存在（FNDDS） |

### 2.7 抽样行（实测，仅用于确认字段语义）

`food.csv`：

| 数据集 | 抽样行 |
| --- | --- |
| Foundation | `319874, sample_food, HUMMUS, SABRA CLASSIC, 16, 2019-04-01` |
| SR Legacy | `167512, sr_legacy_food, Pillsbury Golden Layer Buttermilk Biscuits..., 18, 2019-04-01` |
| FNDDS | `2705383, survey_fndds_food, Milk, human, 9602, 2022-10-28` |
| Branded | `1105904, branded_food, WESSON Vegetable Oil 1 GAL, , 2020-11-13, United States, , [{"min_value":null,...}]` |

`food_nutrient.csv`：

| 数据集 | 抽样行（id, fdc_id, nutrient_id, amount, ...） |
| --- | --- |
| Foundation | `2201847, 319877, 1051, 56.3, 1, 1, ...` |
| SR Legacy | `1283674, 167512, 1003, 5.88, 1, 46, ...` |
| FNDDS | `34136169, 2705384, 301, 125, ...`（`301` 是传统编号，映射到 `1087`） |
| Branded | `13706927, 1105904, 1257, 0.0, , 71, ...` |

`food_portion.csv`：

| 数据集 | 抽样行 |
| --- | --- |
| Foundation | `id=118702, fdc_id=319875, amount=2.0, measure_unit_id=1001, gram_weight=35.8` |
| SR Legacy | `id=81549, fdc_id=167512, amount=1, measure_unit_id=9999, modifier=serving, gram_weight=34` |
| FNDDS | `id=290506, fdc_id=2705383, amount=（空）, measure_unit_id=9999, portion_description=1 cup, modifier=10205, gram_weight=246.0` |
| Branded | 无 `food_portion.csv` |

`branded_food.csv` 抽样行：

```text
fdc_id=1105904, brand_owner=Richardson Oilseed Products (US) Limited,
brand_name=（空）, gtin_upc=00027000612323, serving_size=15.0,
serving_size_unit=ml, household_serving_fulltext=1 Tbsp (15 ml),
branded_food_category=Oils Edible, data_source=GDSN, package_weight=（空）
```


---

## 3. 实体关系与关联键

### 3.1 通用关系

```text
food (fdc_id) 1 ─── N food_nutrient (fdc_id, nutrient_id)
food (fdc_id) 1 ─── N food_portion (fdc_id)
food (food_category_id) N ─── 1 food_category (id)            # Foundation / SR
food (food_category_id) N ─── 1 wweia_food_category (code)    # FNDDS，实测完全一致
food (fdc_id) 1 ─── 1 branded_food (fdc_id)                   # Branded
food (fdc_id) 1 ─── 1 survey_fndds_food (fdc_id)             # FNDDS
```

### 3.2 关联规则

1. **食品与营养**：始终用 `food.fdc_id = food_nutrient.fdc_id`。
2. **营养字典**：
   - Foundation / SR / Branded：`food_nutrient.nutrient_id = nutrient.id`。
   - FNDDS：`food_nutrient.nutrient_id = nutrient.nutrient_nbr`，再取 `nutrient.id` 作为统一营养键。
   - 实测 FNDDS 的 65 个营养键全部能在 `nutrient.csv` 的 `nutrient_nbr` 中找到；未解析键为 0。
3. **食品与份量**：`food.fdc_id = food_portion.fdc_id`；`gram_weight` 是该份量的克重。
4. **食品与分类**：
   - Foundation / SR：`food.food_category_id = food_category.id`。
   - FNDDS：`food.food_category_id` 实际是 WWEIA 类别代码，可直接关联 `wweia_food_category.wweia_food_category`；实测与 `survey_fndds_food.wweia_category_number` 的 5,432 条记录 **0 处不一致**。
   - Branded：`food.food_category_id` 全部为空；只能使用 `branded_food.branded_food_category` 文本。
5. **品牌与商品**：`food.fdc_id = branded_food.fdc_id`；实测 0 个孤儿记录，1:1 对齐。
6. **GTIN 不是关联键**：重复 GTIN 表示产品更新，不能用于跨食品合并或去重。

### 3.3 FNDDS 编号映射示例（实测）

| `food_nutrient.nutrient_id`（FNDDS） | `nutrient.nutrient_nbr` | `nutrient.id`（统一键） | 名称 | 单位 |
| --- | --- | --- | --- | --- |
| `208` | `208` | `1008` | Energy | KCAL |
| `203` | `203` | `1003` | Protein | G |
| `204` | `204` | `1004` | Total lipid (fat) | G |
| `205` | `205` | `1005` | Carbohydrate, by difference | G |
| `301` | `301` | `1087` | Calcium, Ca | MG |
| `307` | `307` | `1093` | Sodium, Na | MG |

---

## 4. 官方口径：单位与计算基准

以下内容摘自各 ZIP 内附带的官方字段说明 xlsx（Foundation/Branded 与 FNDDS 的 `Download API Field Descriptions.xlsx`、SR 的 `Download & API Field Descriptions-2019-10-11-16-22.xlsx`）。

### 4.1 营养数值的基准

原文：

> **amount**：“Amount of the nutrient per 100g of food. Specified in unit defined in the nutrient table.”
>
> **unit_name**：“The standard unit of measure for the nutrient (per 100g of food)”

结论：

- 四个数据集的 `food_nutrient.amount` 都是 **每 100g 食品** 的量，不是每份。
- 单位为 `nutrient.unit_name`：`G`、`MG`、`UG`、`KCAL`、`kJ`、`IU`、`MCG_RE`、`MG_ATE`、`MG_GAE`、`PH`、`SP_GR`、`UMOL_TE`。
- `serving_size` / `household_serving_fulltext` 是标签份量描述，不是营养值基准。
- 本项目餐盘以克为单位；要计算 `克数 / 100 × amount`，不能把 `amount` 当作“每份”。

### 4.2 能量口径

| 营养 ID | `nutrient_nbr` | 名称 | 单位 | 处理 |
| --- | --- | --- | --- | --- |
| `1008` | `208` | Energy | KCAL | 首选 |
| `2048` | `958` | Energy (Atwater Specific Factors) | KCAL | 次选 |
| `2047` | `957` | Energy (Atwater General Factors) | KCAL | 再次选 |
| `1062` | `268` | Energy | kJ | **不参与 kcal 合并** |

- 固定优先级：`1008 → 2048 → 2047`，只取一个值。
- `1062` 是千焦，按定义 `1 kcal = 4.184 kJ` 可换算，但本项目**不做换算**，也不把 `1062` 与 `1008` 相加。
- 三个 kcal 口径同时存在时，保留 `origin_nutrient_id` 以追溯来源。

### 4.3 份量口径

- `food_portion.amount`：组成该份量的测量单位数量；例如 3 tsp 时 `amount=3`。
- 官方明确：**FNDDS 的 `amount` 未定义**，份量描述在 `portion_description` 中。实测 22,046 行全部为空，符合说明。
- `food_portion.gram_weight`：该份量的克重，是唯一可可靠用于计算的份量字段。
- `measure_unit_id=9999` 表示单位不是 `measure_unit.csv` 中的标准单位；不能强行用 `measure_unit.name` 解释。
- Branded 的 `serving_size` 只能是 `gram` 或 `ml`（官方说明）；`serving_size_unit` 实测还出现 `GRM`、`GM`、`MLT`、`MG`、`IU`、`MC`，必须按同义词/异常单位分类处理。
- Branded 的 `package_weight` 是自由文本，含 `g`、`mL`、`oz`、`ONZ`、`L`、`LBR`、`kg`、`lbs`、`G` 等混用单位；**不能直接解析为克**。

### 4.4 商品标识

官方说明：

> “Duplicate codes signify an update to the product, use the publication_date found in the food table to distinguish when each update was published, e.g. the latest publication date will be the most recent update of the product.”

结论：GTIN 重复不是数据错误，而是同一商品的多版本。保留所有 `fdc_id`，需要“最新版本”视图时按 GTIN 分组取最新 `publication_date`。

---

## 5. 分数据集审计结果

### 5.1 Foundation Foods

#### 规模与类型

| 项目 | 实测值 |
| --- | ---: |
| `food.csv` 总行数 | 87,990 |
| `fdc_id` 唯一数 | 87,990（无重复） |
| `foundation_food` | **469** |
| `sub_sample_food` | 75,055 |
| `market_acquisition` | 7,577 |
| `sample_food` | 4,079 |
| `agricultural_acquisition` | 810 |
| 空 `description` | 8（全部为 `sub_sample_food`） |
| 空 `food_category_id` | 3,811（`sample_food` 15、`market_acquisition` 7、`sub_sample_food` 3,789） |
| `foundation_food.csv` 行数 | 395（**不等于 469，不能作白名单**） |

#### 真实食品（469 条）

- 空描述 0、空分类 0。
- 使用 19 个 FDC 分类；`food_category.csv` 共 28 行，未使用分类不影响。
- 分类分布：蔬菜 99、水果 75、豆类 61、乳蛋 50、谷物 44、鱼贝 24、牛肉 21、坚果 19、香肠 18、油脂 12、禽肉 12、烘焙 8、猪肉 7、餐厅 5、饮料 4、香料 3、汤酱 3、甜食 2、羊肉 2。
- `food_nutrient` 中属于这 469 个食品的行数：**21,459 行**；每食品 12–159 项，平均约 45.8 项。
- 有份量记录的食品：**116 / 469**，共 187 行。

#### 核心营养覆盖率（469 个食品）

| 营养素 | 有值食品数 | 覆盖率 |
| --- | ---: | ---: |
| 蛋白质 `1003` | 425 | 90.6% |
| 脂肪 `1004` | 413 | 88.1% |
| 碳水 `1005` | 377 | 80.4% |
| 纤维 `1079` | 241 | 51.4% |
| 钠 `1093` | 403 | 85.9% |
| 能量 `1008` | 135 | 28.8% |
| 能量 `2048` | 312 | 66.5% |
| 能量 `2047` | 347 | 74.0% |
| 能量三者并集 | **378** | **80.6%** |

按 `1008 → 2048 → 2047` 取一个值后的来源分布：

| 规范能量来源 | 食品数 |
| --- | ---: |
| `1008` | 135 |
| `2048` | 214 |
| `2047` | 29 |
| 三个都没有 | **91** |

#### 数据质量异常

| 问题 | 实测数量 | 具体内容 |
| --- | ---: | --- |
| 空 `amount` | 33 行 | 全部指向 `nutrient_id=2066`；而 `nutrient.csv` 中**不存在 2066** |
| 负值 | 10 行 | 全部为 `1005 Carbohydrate, by difference`，如 `-0.47505`、`-0.17255` |
| 食品内重复营养对 | 4 对 | `2758990/2758991/2758992` 的 `2066` 空值；`2768188` 的 `1106` 两行均为 `2.61` |
| 纯零值 | 36,484 行（全文件） | 零是申报值，不等于缺失 |
| `fdc_id` 顺序回退 | 1 处 | 只能说明文件局部未排序，不能据此证明全局唯一 |
| 多能量口径 | 318 个真实食品 | 277 个数值冲突；例 `321358`：`1008=229`、`2047=243`、`2048=229` |
| 非 ISO 日期 | 80 行（全部 `sub_sample_food`） | 形如 `8/16/2023`；469 个真实食品日期均为 ISO `YYYY-MM-DD` |
| 英文描述重复 | 67 组 | 同名但不同 `fdc_id`，不能自动合并 |
| 全部 `food_category_id` 使用 | 19 类 | 与 `food_category.csv` 的 19 个 ID 全部可关联 |

#### Foundation 专属陷阱

1. `food.csv` 混入 87,521 条非食品记录，必须按 `data_type='foundation_food'` 过滤。
2. `foundation_food.csv` 只有 395 行，与 469 不一致；不得用它作为完整白名单。
3. `sub_sample_food` 与 `sample_food` 通过 `fdc_id_of_sample_food` 关联，不属于可食用食品条目，不导入。
4. 2066 不在营养字典中，且对应值全为空；ETL 必须丢弃并记录异常。
5. 负碳水不能直接展示或参与计算；应保留原始值并标记 `negative_value`，规范值按缺失处理，不得改成 0。

### 5.2 SR Legacy

| 项目 | 实测值 |
| --- | ---: |
| `food.csv` 行数 | 7,793 |
| 数据类型 | 全部 `sr_legacy_food` |
| 空描述 / 空分类 | 0 / 0 |
| 分类 | 25 个已使用；`food_category.csv` 共 28 行 |
| `food_nutrient` 行数 | 644,125 |
| 有营养记录的食品 | 7,793（100%） |
| 每食品营养项数 | 8–138 |
| 空 `amount` / 非法值 / 负值 | 0 / 0 / 0 |
| 零值 | 175,731 行 |
| 食品内重复营养对 | 0 |
| `fdc_id` 顺序回退 | 0 |
| 份量记录 | 14,449 行，覆盖 7,533 个食品（96.7%） |
| 份量 `gram_weight` 空值/非正 | 0 / 0 |
| `measure_unit_id=9999` | 14,449 行（全部） |
| 能量 | `1008` 与 `1062` 各 7,793 行；每个食品都有 |

**结论**：SR Legacy 是四源中结构最干净、覆盖最完整的数据集。主要限制是 260 个食品没有份量记录，以及 `measure_unit_id` 全部为 `9999`，只能依赖 `portion_description`/`modifier` 展示份量文本。

### 5.3 FNDDS / Survey

| 项目 | 实测值 |
| --- | ---: |
| `food.csv` 行数 | 5,432 |
| 数据类型 | 全部 `survey_fndds_food` |
| 空描述 / 空分类 | 0 / 0 |
| 分类 | 172 个 WWEIA 类别 |
| `food_category_id` 与 `survey_fndds_food.wweia_category_number` 不一致 | **0 条** |
| WWEIA 代码在 `wweia_food_category.csv` 中缺失 | 0 |
| 日期范围 | `2021-01-01` 至 `2023-12-31`（全部记录一致） |
| `food_nutrient` 行数 | 353,015 |
| 有营养记录的食品 | 5,431 / 5,432 |
| 每食品营养项数 | 除 1 个食品外，全部恰好 65 项 |
| 无营养记录的食品 | `2705383` **Milk, human** |
| 零值 | 104,083 行 |
| 空 `amount` / 非法 / 负值 | 0 / 0 / 0 |
| 食品内重复营养对 | 0 |
| 份量记录 | 22,046 行，覆盖 5,395 个食品（99.3%） |
| `food_portion.amount` | 22,046 行全部为空（官方定义为 FNDDS 不适用） |
| `measure_unit_id=9999` | 22,046 行（全部） |
| 坏份量 | `fdc_id=2705383`，`gram_weight=0.0`，`portion_description='Quantity not specified'` |
| 营养键 | 65 个传统编号，全部可映射到 `nutrient.id` |

**结论**：FNDDS 的分类关联是可靠的，可以直接用 `food.food_category_id`，不必绕道 `survey_fndds_food`；后者可用于交叉校验（实测 0 差异）。FNDDS 是“调查食品/混合菜品”，不是基础食材，UI 必须标注数据类型，避免与 Foundation 的原料混淆。

### 5.4 Branded Foods

#### 食品与商品

| 项目 | 实测值 |
| --- | ---: |
| `food.csv` 行数 | 1,999,950 |
| `fdc_id` 唯一数 | 1,999,950（无重复） |
| 空 `description` | 1（`fdc_id=776874`） |
| 空 `food_category_id` | **1,999,950（全部为空）** |
| `branded_food.csv` 行数 | 1,999,950 |
| 孤儿 `branded_food.fdc_id` | 0 |
| 空 `brand_owner` | 19,737 |
| 空 `brand_name` | 544,426 |
| 空 `gtin_upc` | 0 |
| GTIN 重复行 | **1,534,840** |
| 唯一 GTIN | **465,110** |
| 空 `serving_size` | 10,755 |
| 有 `serving_size` 但无单位 | 8,237 |
| 空 `household_serving_fulltext` | 40,765 |
| 空 `ingredients` | 5,368 |
| 空 `package_weight` | 1,135,504 |
| 空 `branded_food_category` | 10,630 |
| 已停售（`discontinued_date` 非空） | 3,702 |

`serving_size_unit` 实际分布：

| 单位 | 行数 |
| --- | ---: |
| `g` | 1,507,343 |
| `GRM` | 192,465 |
| `ml` | 240,963 |
| `MLT` | 28,568 |
| 空 | 18,992 |
| `MG` | 7,549 |
| `IU` | 3,663 |
| `GM` | 344 |
| `MC` | 63 |

`package_weight` 主要单位（自由文本，非穷举）：

| 单位 | 行数 |
| --- | ---: |
| `g` | 502,809 |
| `mL` | 75,496 |
| `oz` | 74,221 |
| `ONZ` | 65,693 |
| `L` | 41,533 |
| `LBR` | 30,155 |
| `kg` | 24,914 |
| `OZA` | 8,658 |
| `lbs` | 7,765 |
| `G` | 4,690 |

#### 营养

| 项目 | 实测值 |
| --- | ---: |
| `food_nutrient` 行数 | 26,027,437 |
| 有营养记录的食品 | 1,896,250 |
| **无营养记录的食品** | **103,700** |
| 空 `amount` / 非法 / 负值 | 0 / 0 / 0 |
| 未知 `nutrient_id` | 0 |
| 孤儿 `fdc_id` | 0 |
| 零值 | 8,522,624（约 32.7%） |
| 每食品营养项数 | 1–48 |
| 食品内重复营养对 | 0（邻接分组） |
| `fdc_id` 顺序回退 | 4,304 |
| 能量 `1008` | 1,862,097 行 |
| 能量 `1062`（kJ） | 33 行 |
| 多能量口径 | 0 |
| `food_portion.csv` | **不存在** |

#### 分类

`branded_food_category` 是自由文本，不是 FDC 分类 ID。前 10 类（按行数）：

| 分类 | 行数 |
| --- | ---: |
| Popcorn, Peanuts, Seeds & Related Snacks | 91,579 |
| Candy | 88,810 |
| Cheese | 80,757 |
| Ice Cream & Frozen Yogurt | 60,617 |
| Cookies & Biscuits | 53,275 |
| Chips, Pretzels & Snacks | 50,638 |
| Breads & Buns | 46,923 |
| Pickles, Olives, Peppers & Relishes | 44,203 |
| Chocolate | 41,448 |
| Fruit & Vegetable Juice, Nectars & Fruit Drinks | 41,036 |

#### Branded 的特别说明

1. 无 `food_portion.csv`，不能伪造家庭份量；只能展示 `serving_size`、`serving_size_unit` 和 `household_serving_fulltext` 原文。
2. `serving_size_unit` 含 `MG`、`IU`、`MC`，这些不是质量单位，不能用于把营养值换算到“每份”。
3. `serving_size` 为 `ml`/`MLT` 时是体积，换算成克需要密度；本项目没有密度来源，禁止自动换算。
4. `package_weight` 是自由文本，不能用于营养计算。
5. 1,534,840 行 GTIN 重复是商品版本，不是可删除的重复；需要最新版本时按 GTIN 分组、取 `publication_date` 最大者。
6. 103,700 个食品无营养记录，必须允许“数据不完整”的商品存在，不能默认为 0。
7. `brand_name` 缺失 544,426 行，但 `brand_owner` 通常仍存在；展示时优先 `brand_name`，为空则回退 `brand_owner`，再为空则显示“品牌未提供”。

---

## 6. 跨数据集问题

### 6.1 `fdc_id` 交集

对 Foundation、SR Legacy、FNDDS 三源做了两两交集：

| 组合 | 交集数量 |
| --- | ---: |
| Foundation & SR Legacy | 0 |
| Foundation & FNDDS | 0 |
| SR Legacy & FNDDS | 0 |

Branded 与其他三源的 `fdc_id` 交集本次未单独扫描（见第 12 节限制），ETL 仍必须以 `fdc_id` 主键做冲突兜底。

### 6.2 英文描述重复（精确匹配，转小写后）

| 范围 | 重复组数/交集数 |
| --- | ---: |
| Foundation 内部 | 67 组 |
| Foundation 与 SR Legacy | 99 个相同描述 |
| Foundation 与 FNDDS | 23 个 |
| SR Legacy 与 FNDDS | 100 个 |

**结论**：同名不等于同一食品。同名可能来自不同数据源、不同加工方式、不同版本。禁止按英文描述自动合并；保留 `fdc_id`，界面可做“同名记录分组/来源提示”，但每条记录独立。

### 6.3 营养字典差异

- Foundation 477、FNDDS 477、Branded 477、SR Legacy 474。
- 477 个营养素中有 12 个 `nutrient_nbr` 为空：
  `2052, 2053, 2054, 2055, 2057, 2058, 2059, 2060, 2061, 2062, 2063, 2064`。
- 因此不能假设“所有营养素都有传统编号”；统一键必须用 `nutrient.id`，`nutrient_nbr` 只作为 FNDDS 的解析入口和辅助键。

---

## 7. 数据质量问题清单（按严重度）

| 级别 | 数据集 | 问题 | 实测证据 | 建议处理 |
| --- | --- | --- | --- | --- |
| 阻断 | 目录 | 四个指定目录不存在 | 全部 `MISSING_DIRECTORY` | ETL 配置改为实际路径 `..\数据集`，或由用户建立软链接/复制；不得静默失败 |
| 阻断 | Foundation | 87,521 条非食品记录 | `sub_sample_food` 75,055 等 | 按 `data_type='foundation_food'` 白名单过滤 |
| 阻断 | FNDDS | `nutrient_id` 是传统编号 | 65 个键均对应 `nutrient_nbr` | 通过 `nutrient_nbr → nutrient.id` 映射 |
| 阻断 | Branded | 无 `food_portion.csv` | 文件不存在 | 只展示标签份量，不生成份量克重 |
| 高 | Branded | GTIN 大量重复 | 1,534,840 重复行 / 465,110 唯一 | 保留全部；按 GTIN 分组取最新 `publication_date` |
| 高 | Branded | 103,700 个食品无营养 | 1,896,250 有营养 | 允许存在；UI 标记“无营养数据”；不得填 0 |
| 高 | Foundation | 三种能量口径冲突 | 318 个多口径，277 个冲突 | 按 `1008 → 2048 → 2047` 取一个，记录 `origin_nutrient_id` |
| 高 | Foundation | `nutrient_id=2066` 不在字典 | 33 行空值 | 丢弃并记录异常；不导入空值 |
| 高 | Foundation | 10 行负碳水 | 全部 `1005` | 原始值留档，规范值标记不可用；不得改为 0 |
| 中 | Foundation | 4 对食品内重复营养 | 2066 空值、1106 重复 | 唯一键冲突时保留第一条并写冲突报告 |
| 中 | Foundation | 同名不同 ID | 67 组 | 不自动合并；按 `fdc_id` 独立 |
| 中 | FNDDS | 1 个食品无营养 | `2705383 Milk, human` | 保留记录，标记不完整；不进入默认推荐 |
| 中 | FNDDS | 1 个 0g 份量 | `2705383`，`gram_weight=0.0` | 份量视为无效，不参与换算 |
| 中 | FNDDS | `food_portion.amount` 全空 | 22,046 行 | 只使用 `gram_weight` 与 `portion_description` |
| 中 | Branded | 份量单位混用 | `GRM/GM/ml/MLT/MG/IU/MC` | 白名单解析 `g/GRM/GM`；`ml/MLT` 不转克；`MG/IU/MC` 标记不可用 |
| 中 | Branded | `package_weight` 自由文本 | `LBR/ONZ/OZA` 等 | 不参与计算，只保留原文 |
| 中 | 全部 | 非质量单位 | `IU/PH/SP_GR/MCG_RE/MG_ATE/UMOL_TE/MG_GAE` | 独立单位展示，不相加、不换克 |
| 低 | Foundation | 80 条非 ISO 日期 | 全部 `sub_sample_food` | 不导入样本；若导入需解析 `M/D/YYYY` |
| 低 | Branded | 1 条空描述 | `776874` | 保留 `fdc_id`；UI 显示“无名称”或排除 |
| 低 | Branded | 10,630 条空品牌分类 | `branded_food_category=''` | 使用兜底分类“未分类”，不猜 |
| 低 | Branded | 3,702 条停售 | `discontinued_date` 非空 | 默认不展示，标记“已停售” |
| 低 | Branded | 4,304 处 `fdc_id` 顺序回退 | 邻接分组重复为 0 | ETL 建唯一键，不能依赖文件有序 |

### 7.1 缺失、零与不可比较的区分

| 状态 | 数据表现 | 本项目表示 |
| --- | --- | --- |
| 缺失 | `food_nutrient` 无该行；或 `amount` 为空 | 数据库无行 / API `null` / UI “—” |
| 明确为零 | `amount = 0` | 保存 `0`，展示 `0`，计入覆盖率 |
| 无效值 | 负值、未知营养 ID、非数值 | 不进入规范值；在质量报告中记录 |
| 不可比较 | 单位不同（`IU` vs `MG`）、`ml` 份量未换算、`package_weight` 无结构 | 不参与求和/排序；单独标注单位或“不可换算” |

---

## 8. 统一结构字段映射

### 8.1 `food` 表映射

| 目标字段 | Foundation | SR Legacy | FNDDS | Branded |
| --- | --- | --- | --- | --- |
| `fdc_id` | `food.fdc_id` | `food.fdc_id` | `food.fdc_id` | `food.fdc_id` |
| `data_type` | 固定 `foundation_food` | 固定 `sr_legacy_food` | 固定 `survey_fndds_food` | 固定 `branded_food` |
| `description_en` | `food.description` 原文 | 同左 | 同左 | 同左 |
| `food_category_id_raw` | `food.food_category_id` | 同左 | `food.food_category_id`（WWEIA 代码） | 空 |
| `category_source` | `fdc` | `fdc` | `wweia` | `branded` |
| `category_code` | `food_category.id` | 同左 | `wweia_food_category` | 无（用文本） |
| `category_en` | `food_category.description` | 同左 | `wweia_food_category_description` | `branded_food.branded_food_category` |
| `category_zh` | 中文映射表 | 同左 | 中文映射表 | 中文映射表 |
| `publication_date` | `food.publication_date` | 同左 | 同左 | 同左 |
| `brand_owner` | 空 | 空 | 空 | `branded_food.brand_owner` |
| `brand_name` | 空 | 空 | 空 | `branded_food.brand_name` |
| `subbrand_name` | 空 | 空 | 空 | `branded_food.subbrand_name` |
| `gtin_upc` | 空 | 空 | 空 | `branded_food.gtin_upc`（按文本保存前导 0） |
| `serving_size` | 空 | 空 | 空 | `branded_food.serving_size` |
| `serving_unit` | 空 | 空 | 空 | `branded_food.serving_size_unit` |
| `household_serving` | 空 | 空 | 空 | `branded_food.household_serving_fulltext` |
| `package_weight_raw` | 空 | 空 | 空 | `branded_food.package_weight`（原文） |
| `ingredients_en` | 空 | 空 | 空 | `branded_food.ingredients` |
| `discontinued_date` | 空 | 空 | 空 | `branded_food.discontinued_date` |
| `source_dataset` | `foundation` | `sr_legacy` | `fndds` | `branded` |
| `source_version` | `2026-04` | `2018-04` | `2021-2023` | `2026-04` |
| `is_default_library` | 1 | 1 | 1 | 0 |
| `search_tokens` | 生成 | 生成 | 生成 | 生成（含品牌英文） |

### 8.2 `food_nutrient` 表映射

| 目标字段 | 规则 |
| --- | --- |
| `fdc_id` | `food_nutrient.fdc_id` |
| `nutrient_id` | Foundation/SR/Branded：原值；FNDDS：`nutrient_nbr` 对应的 `nutrient.id` |
| `amount` | 原值，仅接受有限非负数；负值/空值不进入规范表 |
| `origin_nutrient_id` | 原始 `food_nutrient.nutrient_id` |
| `unit_name` | 关联 `nutrient.unit_name`，冗余存储便于查询 |
| `quality_flag` | 建议新增：`ok` / `negative_value` / `unknown_nutrient` / `duplicate` |

能量规范化单独处理：

```text
对每个 fdc_id：
  若存在 1008 且 amount 有效 → 规范 1008，origin=1008
  否则若存在 2048 且有效   → 规范 1008，origin=2048
  否则若存在 2047 且有效   → 规范 1008，origin=2047
  否则                     → 无能量行（缺失）
```

`1062`（kJ）不写入规范能量行；如需保留，可写入单独的 `energy_kj` 字段或原始表，但不参与 kcal 计算。

### 8.3 `food_portion` 表映射

| 目标字段 | Foundation / SR | FNDDS | Branded |
| --- | --- | --- | --- |
| `id` | `food_portion.id` | 同左 | 无 |
| `fdc_id` | `food_portion.fdc_id` | 同左 | 无 |
| `seq_num` | 原值 | 原值 | 无 |
| `amount` | 原值 | **永远为空，存 NULL** | 无 |
| `measure_unit_id` | 原值（大量 `9999`） | 原值（全 `9999`） | 无 |
| `portion_description` | 原值 | 原值（份量信息在这里） | 无 |
| `modifier` | 原值 | 原值（是代码/文本，不保证可读） | 无 |
| `gram_weight` | 原值 | 原值（`>0` 才可用） | 无 |
| `source_kind` | `measure` | `survey_portion` | `label_serving`（由 `branded_food` 生成展示对象，不入此表） |

### 8.4 `nutrient` 与分类表

| 目标表 | 字段 | 来源 |
| --- | --- | --- |
| `nutrient` | `id` | `nutrient.id` |
| | `nbr` | `nutrient.nutrient_nbr`（可空） |
| | `name_en` | `nutrient.name` |
| | `unit_name` | `nutrient.unit_name` |
| | `rank` | `nutrient.rank` |
| | `name_zh` / `group_zh` / `decimals` | 人工维护的 `data/curation/nutrient_zh.csv` |
| `food_category` | `source, code, name_en, name_zh` | Foundation/SR 用 `food_category.csv`；FNDDS 用 `wweia_food_category.csv`；Branded 用 `branded_food_category` 文本 |

### 8.5 建议新增的质量字段

当前 `PROJECT_SPEC.md` 的 `food_nutrient` 只有 `amount` 与 `origin_nutrient_id`。建议增加：

```sql
quality_flag TEXT NOT NULL DEFAULT 'ok'
  -- ok / negative_value / unknown_nutrient / duplicate / out_of_range
raw_amount   REAL
  -- 原始值；负值或异常时保留，规范 amount 为 NULL
```

这样可以在不篡改原始值的前提下，让规范表只包含可计算值。

---

## 9. 四源合并建议与中文食材库方案

### 9.1 合并原则

1. **一个 `food` 表 + 来源判别字段**，不建立四套独立食品表；但适配器必须独立。
2. **不按英文描述合并**：同名不同 `fdc_id` 保留为独立记录。
3. **默认食材库只含非品牌三源**：13,694 条。
   - Foundation 469：实验分析数据，优先级最高。
   - SR Legacy 7,793：历史完整数据，作为基础食材主力。
   - FNDDS 5,432：调查食品/混合菜品，单独标注，不与原料混淆。
4. **Branded 作为可选层**：默认不进入食材库；用户主动开启“品牌商品”后按分类浏览/搜索。
5. **Branded 版本视图**：同一 GTIN 多版本时，列表默认只显示最新 `publication_date` 的记录；详情可查看历史版本。不得删除旧 `fdc_id`。
6. **停售商品**：保留记录，默认过滤 `discontinued_date` 非空项。
7. **缺失营养**：不参与求和；UI 显示“—”，并给出该营养素的克重覆盖率。
8. **来源展示**：每条食品详情固定展示 `fdc_id`、英文原名、`data_type`、数据集版本、分类来源、中文名状态。

### 9.2 同名与重复的处理

| 场景 | 处理 |
| --- | --- |
| Foundation 内部同名 67 组 | 每条独立；详情显示 `fdc_id` 区分 |
| Foundation 与 SR 同名 99 个 | 不合并；列表可标注“同名，来源不同” |
| SR 与 FNDDS 同名 100 个 | 不合并；FNDDS 标注“调查食品” |
| Branded 同 GTIN 多版本 | 保留全部；默认展示最新版本 |
| Branded 同描述不同 GTIN | 视为不同商品，不合并 |

### 9.3 中文名称映射层

建议目录与文件：

```text
data/curation/
├─ food_name_zh.csv       # fdc_id, name_zh, status, note, source, updated_at
├─ category_zh.csv        # category_source, category_code, name_zh
├─ nutrient_zh.csv        # nutrient_id, name_zh, group_zh, decimals
└─ glossary_rules.csv     # 词条, 译名, 匹配规则, 版本
```

规则：

1. **原始英文名永远保留在 `food.description_en`**，中文只写入附加字段，不覆盖原文。
2. `status` 三级：
   - `verified`：人工核验，正常展示；
   - `glossary`：按可审计的词典规则生成，展示“词典译名”标签；
   - `none`：无中文名，展示英文原名 + “暂无中文名”。
3. 优先人工核验范围：
   - Foundation 469 条全部；
   - SR Legacy 中高频基础食材（蔬菜、水果、肉类、谷物、乳蛋、油脂）；
   - FNDDS 的 172 个 WWEIA 类别名；
   - 477 个营养素名称。
4. **品牌商品名不机翻**：`brand_name`、`brand_owner`、商品描述保留英文；只翻译通用分类和营养素。
5. **配料表不翻译**：`ingredients` 保留英文原文，避免法律/成分歧义。
6. 搜索别名独立存 `food_alias`：中文名、词典译名、英文 token、拼音；`status` 随名称状态。
7. 中文名与别名只写入 `data/curation/*.csv`，这是唯一允许入库的 CSV 类型。

### 9.4 搜索与展示建议

- 默认搜索排序：基础食材优先（Foundation > SR Legacy > FNDDS），Branded 默认排除。
- 英文搜索：对 `description_en` 做 token 化，保留原始大小写展示。
- 中文搜索：使用 bigram 索引；`trigram` 对 2 字中文查询无效（项目已有结论）。
- 同名结果：显示来源徽标（Foundation / SR Legacy / FNDDS / Branded）与 `fdc_id` 后四位，避免用户误选。
- 品牌商品：展示品牌英文名 + 商品英文描述 + 标签份量原文；中文仅用于分类和通用食材词。

---

## 10. 后续 ETL 设计建议

### 10.1 适配器边界

```text
backend/app/etl/
├─ base.py                 # 流式读取、ZIP 打开、批次写入、质量记录
├─ foundation.py           # 仅 data_type=foundation_food；分类走 food_category
├─ sr_legacy.py            # 全量；分类走 food_category
├─ fndds.py                # nutrient_id 按 nutrient_nbr 解析；分类走 WWEIA
├─ branded.py              # 1:1 branded_food；分类走文本；无份量表
├─ nutrient_map.py         # 统一营养键与单位
├─ energy.py               # 1008 → 2048 → 2047
├─ validation.py           # 计数、孤儿、覆盖率、黄金样本
└─ build.py                # 临时库 → 校验 → 原子替换
```

禁止用一个“通用 CSV 导入器”假定四套数据同构。

### 10.2 读取方式

- 用 `zipfile.ZipFile.open()` + `io.TextIOWrapper(..., encoding='utf-8-sig')` 流式读取。
- 全程 `csv.reader`/`DictReader`，逐行处理；不 `read()` 整个文件。
- Branded 的 `food_nutrient.csv` 约 1.5 GB、2,600 万行，必须分批提交（建议 5,000–20,000 行/批）。
- 解压临时文件不落地；如必须落地，放在 `data/build/` 且用后删除。

### 10.3 两阶段构建

**阶段 A：原始暂存**

- `stage_food`、`stage_food_nutrient`、`stage_food_portion`、`stage_branded_food`。
- 保留原始列与原始 `nutrient_id`，不做语义转换。
- 对 Branded 的 4,304 处顺序回退不做假设，按 `fdc_id` 聚合。

**阶段 B：规范化**

- 用 SQL 完成：
  - FNDDS 营养键映射；
  - 能量优先级选择（窗口函数或 `CASE`）；
  - 食品内重复检测（`GROUP BY fdc_id, nutrient_id HAVING COUNT(*)>1`）；
  - 负值/空值/未知键标记；
  - 分类关联；
  - 覆盖率统计。
- 规范化结果写入正式结构表。

### 10.4 校验门禁（必须全部通过才替换正式库）

| 校验项 | 期望 |
| --- | --- |
| 食品计数 | Foundation 469、SR 7,793、FNDDS 5,432、Branded 1,999,950（Branded 可按配置跳过） |
| 孤儿营养记录 | 0 |
| 孤儿份量记录 | 0 |
| 空描述 | Foundation 实际食品 0、SR 0、FNDDS 0、Branded 允许 1 并报告 |
| FNDDS 未映射营养键 | 0 |
| FNDDS 分类不一致 | 0 |
| 规范能量缺失 | Foundation 91、FNDDS 1（Milk, human）、Branded 允许存在并统计 |
| 负值规范行 | 0（负值只留在原始/质量表） |
| 重复主键 | 0 |
| 黄金样本 | 第 11 节 4 条全部一致 |
| 覆盖率 | 与审计基准一致，偏差需书面解释 |

### 10.5 原子替换与版本

1. 写入 `data/build/mealscanvas.tmp.sqlite`。
2. 设置 `PRAGMA journal_mode=OFF`、`synchronous=OFF`（仅构建库）。
3. 构建索引后再校验。
4. 校验通过后关闭连接，原子替换 `data/build/mealcanvas.sqlite`。
5. `meta` 写入 `data_version`、`build_time`、四源计数、SHA-256、审计报告版本。
6. 失败时保留旧库，不覆盖。

### 10.6 性能与内存

- 不要用 `set` 保存 Branded 全部 2,600 万营养行；用 SQLite 临时表与 SQL 聚合。
- `food_nutrient` 先写入无索引的暂存表，构建完成后再建 `(fdc_id, nutrient_id)` 唯一索引。
- 搜索索引最后构建，避免每行更新索引。
- 所有查询分页；搜索 `pageSize ≤ 100`。

---

## 11. 黄金样本（真实数据，不是构造样例）

以下值直接读取自原始 `food_nutrient.csv`，用于 ETL 回归校验。

### 11.1 Foundation `fdc_id=321358` — Hummus, commercial

| 营养 ID | 名称 | 单位 | 值 |
| --- | --- | --- | ---: |
| `1008` | Energy | KCAL | 229.0 |
| `2047` | Energy (Atwater General Factors) | KCAL | 243 |
| `2048` | Energy (Atwater Specific Factors) | KCAL | 229 |
| `1062` | Energy | kJ | 960.0 |
| `1003` | Protein | G | 7.35 |
| `1004` | Total lipid (fat) | G | 17.1 |
| `1005` | Carbohydrate, by difference | G | 14.9 |
| `1079` | Fiber, total dietary | G | 5.4 |
| `1093` | Sodium, Na | MG | 438.0 |

规范能量应为 `229 kcal`，`origin_nutrient_id=1008`。

### 11.2 SR Legacy `fdc_id=167512` — Pillsbury Golden Layer Buttermilk Biscuits

| 营养 ID | 名称 | 单位 | 值 |
| --- | --- | --- | ---: |
| `1008` | Energy | KCAL | 307 |
| `1062` | Energy | kJ | 1,286 |
| `1003` | Protein | G | 5.88 |
| `1004` | Total lipid (fat) | G | 13.24 |
| `1005` | Carbohydrate, by difference | G | 41.18 |
| `1079` | Fiber, total dietary | G | 1.2 |
| `1093` | Sodium, Na | MG | 1,059 |
| `2000` | Sugars, Total | G | 5.88 |

### 11.3 FNDDS `fdc_id=2705384` — Milk, NFS

| 原始 `nutrient_id` | 映射后 ID | 名称 | 单位 | 值 |
| --- | --- | --- | --- | ---: |
| `208` | `1008` | Energy | KCAL | 52 |
| `203` | `1003` | Protein | G | 3.33 |
| `204` | `1004` | Total lipid (fat) | G | 2.14 |
| `205` | `1005` | Carbohydrate, by difference | G | 4.83 |
| `291` | `1079` | Fiber, total dietary | G | 0 |
| `307` | `1093` | Sodium, Na | MG | 39 |
| `269` | `2000` | Total Sugars | G | 4.88 |
| `301` | `1087` | Calcium, Ca | MG | 125 |

### 11.4 Branded `fdc_id=1105904` — WESSON Vegetable Oil 1 GAL

| 营养 ID | 名称 | 单位 | 值 |
| --- | --- | --- | ---: |
| `1008` | Energy | KCAL | 867.0 |
| `1003` | Protein | G | 0.0 |
| `1004` | Total lipid (fat) | G | 93.33 |
| `1005` | Carbohydrate, by difference | G | 0.0 |
| `1079` | Fiber, total dietary | G | 0.0 |
| `1093` | Sodium, Na | MG | 0.0 |
| `2000` | Total Sugars | G | 0.0 |
| `1087` | Calcium, Ca | MG | 0.0 |

该样本的 `serving_size=15.0`、`serving_size_unit=ml`、`household_serving_fulltext=1 Tbsp (15 ml)`。**不得**用 15 ml 直接换算成克来重算 100g 值。

---

## 12. 审计限制与未验证项

1. **Branded `fdc_id` 全局唯一性未完全证明**：只按文件邻接分组检测到食品内重复营养为 0；文件存在 4,304 处 `fdc_id` 顺序回退。ETL 必须建 `(fdc_id, nutrient_id)` 唯一索引，不能依赖排序。
2. **Branded 与其他三源的 `fdc_id` 交集未单独扫描**：本报告只确认 Foundation/SR/FNDDS 两两交集为 0。
3. **`food_attribute.csv` 未分析**：Branded 的 133 MB、Foundation 753 KB、FNDDS 1.6 MB 属性表未参与字段映射。
4. **`not_a_significant_source_of`、`microbe_data`、`preparation_state_code`、`material_code` 未分析**：本阶段不进入统一结构。
5. **`package_weight` 单位统计是主要取值，不是穷举**：自由文本存在更多变体，ETL 不应解析。
6. **英文描述重复是精确匹配**（转小写），未做模糊/词干匹配；实际同名可能更多。
7. **未做营养值合理性全量校验**（如三大营养素合计是否超过 100g、能量与宏量是否自洽）；本阶段只统计空值、负值、未知键与重复。
8. **未验证 USDA 外链 URL 结构**是否仍可用。
9. **官方字段说明来自包内 xlsx 的实际读取**；不同版本说明可能略有差异，ETL 以本报告列名为准。
10. **未解压原始 ZIP，未修改任何原始文件**；`data/build/_audit_*.py` 为只读审计脚本，完成后应删除或移出交付物（见第 13 节）。

---

## 13. 阶段结论与下一步门禁

### 已完成

- 确认四个指定目录全部缺失，并定位实际 ZIP。
- 列出四个 ZIP 的核心文件与大小，确认 Branded 无 `food_portion.csv`。
- 读取全部核心 CSV 的真实表头与样例行。
- 确认四源关联键与 FNDDS 传统编号映射。
- 核实官方“每 100g”口径、能量多口径、份量字段差异。
- 量化重复、缺失、未知单位、不可比较记录。
- 给出字段映射、合并建议、中文映射方案与 ETL 设计。
- 已同步修正 `PROJECT_SPEC.md`：`food.csv` 列数、FNDDS 分类来源、审计异常、`data/reports/` 目录、Branded 默认不入库。

### 未完成（留给下一阶段）

- 未建立 SQLite 数据库。
- 未编写适配器与 ETL。
- 未生成中文映射 CSV。
- 未实现搜索索引与 API。

### 进入 ETL 前需要用户确认

1. 是否接受“默认食材库 = Foundation + SR Legacy + FNDDS，Branded 默认关闭”。
2. 是否接受 FNDDS 标注为“调查食品/混合菜品”，而不是基础食材。
3. 是否接受负值碳水按“不可用/缺失”处理，而不是改为 0。
4. 是否接受 Branded 只展示标签份量、不做 `ml → g` 换算。
5. 是否允许在正式库增加 `quality_flag` / `raw_amount` 两个质量字段。

### 审计脚本说明

本次使用的只读脚本位于 `data/build/`：

- `_audit_nonbranded.py`
- `_audit_details.py`
- `_audit_branded.py`
- `_audit_extra.py`
- `_audit_docs.py`
- `_audit_foundation_aux.py`
- `_audit_categories.py`
- `_audit_golden.py`

它们不属于交付代码，也不会被 API 导入；建议在下一阶段开始前删除，或移入 `data/build/audit_tools/` 并明确标注“仅审计用”。原始数据与报告不受影响。

---

**报告结束。本阶段只完成审计，未修改或覆盖任何原始数据，未生成虚假营养样例。**
