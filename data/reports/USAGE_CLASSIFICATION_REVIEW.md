# Meal Canvas 用途分类边界审计报告（第二轮）

- 审计对象：`data/build/sample/meal_canvas_usage.sqlite`（sample 用途库，分类口径版本 1）
- 对照数据：`data/build/sample/meal_canvas.sqlite`（默认库）与 `data/build/sample/meal_canvas_branded.sqlite`（品牌库）
- 规则来源：`data/curation/usage_categories.csv`（228 条）、`usage_rules.csv`（91 条）、`usage_overrides.csv`（0 条）
- 完整复核清单：[USAGE_CLASSIFICATION_REVIEW.csv](USAGE_CLASSIFICATION_REVIEW.csv)（1,634 行，逐条含当前分类、命中规则、依据与建议）
- 本轮性质：**只读审计**。未修改任何规则 CSV、未重建用途库、未改动 API/数据库结构、未执行全量导入。

> 覆盖范围声明：本报告基于 **sample 用途库的 1,634 条记录**（默认库 1,285 + 品牌库 349），
> 不是全量数据集审计。全量数据约 200 万条，结论仅代表当前 sample 抽样范围，不能外推为全量结论。

---

## 1. 当前五类用途分布

### 1.1 默认库（1,285 条）

| 用途分类 | 数量 | 占比 |
| --- | ---: | ---: |
| basic_ingredient | 600 | 46.69% |
| processed_ingredient | 154 | 11.98% |
| prepared_dish | 260 | 20.23% |
| ready_to_eat | 270 | 21.01% |
| unknown | 1 | 0.08% |

### 1.2 品牌库（349 条，独立统计，不与默认库混合）

| 用途分类 | 数量 | 占比 |
| --- | ---: | ---: |
| basic_ingredient | 51 | 14.61% |
| processed_ingredient | 81 | 23.21% |
| prepared_dish | 54 | 15.47% |
| ready_to_eat | 163 | 46.70% |
| unknown | 0 | 0.00% |

### 1.3 两库合计（1,634 条，仅作总览，分类口径仍以分库为准）

| 用途分类 | 数量 | 占比 |
| --- | ---: | ---: |
| basic_ingredient | 651 | 39.84% |
| processed_ingredient | 235 | 14.38% |
| prepared_dish | 314 | 19.22% |
| ready_to_eat | 433 | 26.50% |
| unknown | 1 | 0.06% |

`unknown` 仅 1 条（默认库饮品粉），说明当前类别映射覆盖率较高，问题不在“判不出来”，而在“判得过头或判得偏”。

---

## 2. 可疑记录总览

本轮共标记 **47 条可疑记录**，占 sample 的 **2.88%**。

| 维度 | 分布 |
| --- | --- |
| 按库 | 默认库 37 条（78.7%）、品牌库 10 条（21.3%） |
| 按复核优先级 | 高 40 条、中 7 条、低 0 条 |
| 按命中来源 | 描述规则 `rule` 32 条、类别映射 `category` 15 条 |
| 按规则阶段 | `before_category` 32 条、`category_mapping` 15 条、`after_category` 0 条 |

按“当前分类 → 建议分类”交叉：

| 当前 → 建议 | 条数 | 主要含义 |
| --- | ---: | --- |
| prepared_dish → processed_ingredient | 20 | 成品菜规则误伤了熟制单一食材/腌腊肉/酱料 |
| ready_to_eat → processed_ingredient | 5 | 饮料规则误伤熟牛排 |
| basic_ingredient → processed_ingredient | 5 | 基础食材里混入了加工/调味形态 |
| processed_ingredient → prepared_dish | 6 | 加工食材里混入了组合菜/调理餐 |
| processed_ingredient → ready_to_eat | 4 | 品牌即食成品被归为加工原料 |
| basic_ingredient → prepared_dish | 6 | 基础食材里混入了带配料的组合食品 |
| unknown → ready_to_eat | 1 | 类别缺失但描述证据充分 |

按当前分类（分库）：

| 当前分类 | 默认库 | 品牌库 |
| --- | ---: | ---: |
| basic_ingredient | 10 | 1 |
| processed_ingredient | 3 | 7 |
| prepared_dish | 18 | 2 |
| ready_to_eat | 5 | 0 |
| unknown | 1 | 0 |

---

## 3. 成因分析：描述规则 vs 类别映射

### 3.1 由描述规则造成（32 条）

**(A) 规则顺序导致高优先级误伤**

- `usage_rules.csv:L41` 的 `salad`（成品菜）排在同优先级的 `usage_rules.csv:L51/L52` 的 `salad dressing`（加工食材）之前。
  由于引擎在“同优先级按文件行序”下取第一条命中，`Salad dressing, ...` 被 L41 先判为 `prepared_dish`。
  - 受影响：171010、171402、173590、2758987（默认库），1428696（品牌库），共 5 条。
  - 这正是规则注释里写着“沙拉酱由更高优先级规则处理”、但实际未实现的地方。
- `usage_rules.csv:L39` 的 `\bfried\b` 排在 `usage_rules.csv:L45` 腌腊/香肠规则之前。
  `pan-fried` 中的 `fried` 命中 L39，导致熟制香肠、培根被判为 `prepared_dish`。
  - 受影响：325658、332864、746780、746781（香肠）、167712（培根）、1326230（品牌萨拉米），共 6 条。

**(B) 正则缺少词边界，发生子串误匹配**

- `L39` 的 `tenders?` 没有 `\b`，`tenderloin`（牛里脊）中的 `tender` 被当作“鸡柳”。
  - 受影响：169548、334897、746758 等牛里脊/牛排记录。
- `L62`（默认库饮料规则）的 `tea` 没有 `\b`，`steak`（牛排）中的 `tea` 被当作“茶”。
  - 受影响：168692、169461、173118、335061、746763，共 5 条熟牛排被判为 `ready_to_eat`。
  这是本轮最严重的单点误判：**熟牛排被当成即饮饮料**。
- `L39` 的 `nuggets?` 命中 `FENNEL SALAMI NUGGETS`（萨拉米肉粒），把加工肉制品当炸鸡块。
- `L40` 的 `stuffed` 同时匹配 `layered`，使 `... CHEDDAR CHEESE LAYERED DIP` 被判组合成品菜（2 条）。

**(C) 单关键词口径过宽**

- `L54` 的 `sauce` 命中 `with barbeque sauce`、`with gravy`，把“已熟制带酱的加工品”直接升级为成品菜：
  `FULLY COOKED PORK BABY BACK RIBS WITH BARBEQUE SAUCE`、`Slow-cooked ... with ... bacon` 等。
- `with-ingredient` 现象集中在 FNDDS 记录：`Chicken breast, grilled with sauce`、`Rice, sweet, cooked with honey`、
  `Potato, baked, ... with vegetables`、`Green plantain with cracklings`。
  这些是“单一主体 + 配料/调味”的膳食调查食品，被类别映射判为基础食材，但描述已接近组合菜。
- `L15/L49` 的干粉混合料规则与 `prepared with ...` 描述冲突：
  `Macaroni and cheese, dry mix, prepared with 2% milk...`、`Rice and vermicelli mix, chicken flavor, prepared with 80% margarine`。
- `L12` 的 `taco seasoning` 命中 `HARD TACO SHELLS WITH TACO SAUCE & SEASONING MIX DINNER KIT`，
  把“晚餐套装”按调味粉处理。

### 3.2 由类别映射造成（15 条）

- **WWEIA 类别粒度不足以区分“生/熟/带配料”**：
  - `wweia:2202 Chicken, whole pieces` → basic，却包含 `grilled with sauce`。
  - `wweia:4002 Rice` → basic，却包含 `cooked with honey`。
  - `wweia:6802 White potatoes, baked or boiled` → basic，却包含 `with vegetables`、`with butter`。
  - `wweia:6418 Other starchy vegetables` → basic，却包含 `Green plantain with cracklings`。
  - `wweia:2802 Beans, peas, legumes` → basic，却包含 `Black beans, from fast food / restaurant`。
- **FDC 类别混合了“干混料”和“成品菜”**：`fdc:22 Meals, Entrees, and Side Dishes` → prepared，
  但 `Rice and vermicelli mix, beef flavor, unprepared`、`Rice mix, white and wild, flavored, unprepared`
  明确是未烹调的干混料，应为 `processed_ingredient`。
- **乳制品类别过宽**：`fdc:1 Dairy and Egg Products` → basic，`Cheese, American, restaurant` 属餐饮加工奶酪。
- **品牌类别名与商品形态不一致**：
  - `Cooked & Prepared` / `Meat/Poultry/Other Animals - Prepared/Processed` → processed，但商品是 `Fully Cooked, Frozen` 即食/复热即食。
  - `Cakes, Cupcakes, Snack Cakes` → processed，但 `COLOR BLAST VANILLA CAKE ... ICING` 是即食甜点。
  - `Crackers & Biscotti` → processed，但 `ORIGINAL HUMMUS WITH HUMMUS CHIPS` 是即食零食组合。
  - `Mexican Dinner Mixes` → processed，但 `HARD TACO SHELLS ... DINNER KIT` 是组合餐套装。

### 3.3 unknown 中的可靠证据（1 条）

- `2710614 Fruit flavored drink, powdered, not reconstituted, diet`，类别 `wweia:9999`（未分类），当前 `unknown`。
  描述已明确是冲调饮品粉，建议 `ready_to_eat`（与现有 `beverage mix` 规则口径一致）。
  这是 sample 中唯一一条 unknown，其余类别均有映射，故“unknown 兜底”本轮不是主要矛盾。

---

## 4. 建议分类与理由（仅建议，未改规则）

| 现状 | 建议 | 理由 | 代表记录 |
| --- | --- | --- | --- |
| prepared_dish | processed_ingredient | 熟制/腌腊单一食材或酱料，不是组合成品菜 | 171010、171402、173590、325658、167712 |
| ready_to_eat | processed_ingredient | 熟牛排被饮料关键词误判；应回到熟制肉类的加工/原料处理 | 168692、169461、173118 |
| basic_ingredient | processed_ingredient | 熟制、带调味或混合拼配，不再是原始基础食材 | 171518、1510019、2709406、2709518、2709667 |
| processed_ingredient | prepared_dish | 带配料/酱汁/套餐组合，已接近成品菜 | 173341、173348、719668、736560 |
| processed_ingredient | ready_to_eat | 品牌即食成品（蛋糕、蘸酱零食、复热即食肉） | 2655557、2428321、2738112 |
| basic_ingredient | prepared_dish | WWEIA 类别为单一食材，但描述含配料/餐饮场景 | 2705969、2708417、2709530、2710139、747429 |
| unknown | ready_to_eat | 描述为冲调饮品粉，证据充分 | 2710614 |

**边界原则（写进复核意见，不改现有规则）**

- 不能因为出现 `cooked / grilled / roasted / fried` 就一律判成品菜：
  `Beef, ... cooked, broiled`、`Fish, flounder, grilled`、`Chicken, ... cooked, roasted` 仍可是餐盘原料。
- 也不能因为它们是单一食材就一律判基础食材：
  当描述同时出现“with 酱汁/配料”“restaurant/fast food”“layered/stuffed”，或主体已被调味成套餐时，应倾向成品菜或即食成品。
- 判断锚点应为：**主体是否仍可独立作为餐盘组成原料**，而不是烹饪动词本身。

---

## 5. 最值得人工复核的 20 条

| # | fdc_id | 库 | 英文名 | 当前 → 建议 | 复核要点 |
| ---: | ---: | --- | --- | --- | --- |
| 1 | 171402 | 默认 | Salad dressing, thousand island, commercial, regular | prepared → processed | L41 `salad` 早于 L51 `salad dressing`，规则顺序误伤 |
| 2 | 171010 | 默认 | Salad dressing, mayonnaise, soybean and safflower oil, with salt | prepared → processed | 同上，沙拉酱不应是成品菜 |
| 3 | 325658 | 默认 | Sausage, Italian, pork, mild, cooked, pan-fried | prepared → processed | L39 `fried` 早于 L45 腌腊香肠 |
| 4 | 167712 | 默认 | Pork, cured, bacon, cooked, broiled, pan-fried or roasted, reduced sodium | prepared → processed | 培根属加工肉制品，不是成品菜 |
| 5 | 173118 | 默认 | Beef, top sirloin, steak, ... cooked, broiled | ready → processed | L62 `tea` 子串命中 `steak`，熟牛排被当饮料 |
| 6 | 169461 | 默认 | Beef, short loin, porterhouse steak, ... cooked, broiled | ready → processed | 同上，饮料规则词边界缺失 |
| 7 | 169548 | 默认 | Beef, tenderloin, steak, ... cooked, broiled | prepared → processed | L39 `tenders?` 命中 `tenderloin` |
| 8 | 334897 | 默认 | Beef, loin, tenderloin roast, ... cooked, roasted | prepared → processed | 同上，牛里脊被当“鸡柳” |
| 9 | 2705969 | 默认 | Chicken breast, grilled with sauce, skin eaten | basic → prepared | 类别 `wweia:2202` 过宽，带酱熟鸡已非基础食材 |
| 10 | 2708417 | 默认 | Rice, sweet, cooked with honey | basic → prepared | 类别 `wweia:4002` 未区分加糖熟制 |
| 11 | 2709530 | 默认 | Potato, baked, peel eaten, with vegetables | basic → prepared | 类别 `wweia:6802` 未区分带配料 |
| 12 | 2710139 | 默认 | Green plantain with cracklings, Puerto Rican style | basic → prepared | 类别 `wweia:6418` 未区分组合菜 |
| 13 | 173341 | 默认 | Macaroni and cheese, dry mix, prepared with 2% milk and 80% stick margarine | processed → prepared | “dry mix, prepared” 的干湿两态边界 |
| 14 | 168949 | 默认 | Rice and vermicelli mix, beef flavor, unprepared | prepared → processed | 类别 `fdc:22` 对未烹调干混料过宽 |
| 15 | 2707474 | 默认 | Swiss steak, with gravy, meatless | processed → prepared | 带肉汁的素肉排，接近成品菜 |
| 16 | 2710614 | 默认 | Fruit flavored drink, powdered, not reconstituted, diet | unknown → ready | 类别缺失但描述充分，是唯一 unknown |
| 17 | 747429 | 默认 | Cheese, American, restaurant | basic → prepared | 乳制品类别过宽，餐饮加工奶酪需复核 |
| 18 | 2655557 | 品牌 | COLOR BLAST VANILLA CAKE, BUTTERCREME ICING AND RAINBOW CONFETTI | processed → ready | 类别 `Cakes...` 未反映即食甜点 |
| 19 | 2428321 | 品牌 | ORIGINAL HUMMUS WITH HUMMUS CHIPS, HUMMUS | processed → ready | 蘸酱 + 薯片属即食零食组合 |
| 20 | 719668 | 品牌 | FULLY COOKED PORK BABY BACK RIBS WITH BARBEQUE SAUCE | processed → ready | 全熟冷冻肋排，L54 `sauce` 口径过宽 |

---

## 6. 分类体系本身是否需要调整

**结论：五类体系本身不需要改。** 本轮问题集中在“规则如何执行”和“类别映射粒度”，不是分类维度设计错误。

需要关注的三点（均为规则/映射层，不改变五类定义）：

1. **规则顺序与词边界**：`salad` vs `salad dressing`、`fried` vs 腌腊香肠、`tenders?`、`tea`、`nuggets?`。
   只需调整规则优先级或用 `\b` 收紧，不需要改表结构。
2. **同一 WWEIA/FDC 类别内部“生/熟/带配料”差异**：类别映射只能给出类别默认值，
   应在 `before_category` 增加“with + 配料/酱汁”“restaurant/fast food”“layered/stuffed”这类组合证据规则，
   而不是把整个类别改类。
3. **品牌库类别名与商品形态不一致**：品牌类别（`Cooked & Prepared`、`Cakes`、`Crackers & Biscotti`）是货架分类，
   不是用途分类，仍需描述规则兜底。

现有可追溯性足够：`food_usage` 已保存 `rule_source / rule_id / reason`，本轮审计无需新增表字段，未改动数据库与 API。

---

## 7. 本轮未做的事

- 未修改 `data/curation/` 任一 CSV，未调整任何优先级或规则。
- 未重建、未覆盖 sample 或正式用途库；未执行全量导入。
- 未修改 USDA 原始数据、中文映射、前端/后端代码。
- 未通过硬编码 fdc_id 隐藏任何食品。

### 附带发现（不在本轮分类范围，未修改）

- `fdc_id=167555`（`Snacks, pretzels, hard, plain, salted`）当前 `name_zh='盐'`、`zh_status='glossary'`；
  `fdc_id=174806`（`Snacks, Pretzels, gluten-free ...`）当前 `name_zh='玉米马铃薯面粉'`。
  两者疑似中文映射短语错配，建议在中文复核流程中处理，本轮不动。
