# Meal Canvas 项目开发规则

本文件是本项目的硬性约束。任何实现、重构、脚本或界面改动都必须遵守。与临时偏好冲突时，以本文件为准。

---

## 1. 项目与范围

- 项目根目录：`c:\Users\Markli\Desktop\营养餐盘项目\1`。
- 规格的唯一事实来源：`PROJECT_SPEC.md`；阶段与验收：`DEVELOPMENT_PLAN.md`。
- 技术栈固定：React + TypeScript + Vite / Apache ECharts / dnd-kit / Lucide React / Python + FastAPI / SQLite。
- 不引入未经确认的替代框架（Next.js、Vue、Django、PostgreSQL、Tailwind 组件库等）。
- 不做用户账号、云端同步、支付、社交功能。
- 不一次性实现所有功能；严格按当前阶段范围交付。
- 原始数据通过 `MEAL_CANVAS_DATA_DIR` 指定；路径失效必须失败并输出中文错误，不得复制 ZIP 或假装文件存在。

---

## 2. 数据完整性（最高优先级）

### 必须

- 保留原始 `fdc_id`、英文 `description`、`data_type`、数据集名称与版本。
- 四个数据源全部纳入：Foundation、SR Legacy、FNDDS 进入默认食材库；Branded 写入独立库 `data/build/meal_canvas_branded.sqlite`，后端保留但前端界面不提供品牌库入口。
- 默认食材库列表**不得**因 `zh_status='none'` 排除食品：中文映射状态只是展示信息，不是食品准入条件。无中文名时以英文原名回退展示并标注“暂无中文名”，仍可搜索、加入餐盘与参与计算。
- 食品用途使用独立分类层 `basic_ingredient` / `processed_ingredient` / `prepared_dish` / `ready_to_eat` / `unknown`，由 `data/curation/usage_categories.csv`、`usage_rules.csv`、`usage_overrides.csv` 判定并生成独立用途库；**不得把 USDA `data_type` 或 `zh_status` 当作用途分类**，不得凭猜测把用途不明的记录标记为基础食材。
- 默认搜索只返回基础食材与加工食材；成品菜、即食成品与 `unknown` 只能通过 `usage_scope=all` 或 `usage_class` 显式查看，用途过滤必须在后端 SQL 完成并与搜索、总数、分页共用条件。
- FNDDS 记录必须标记为“膳食调查食品 / 组合食品”，不得与基础食材混为一类。
- 使用 `data/curation/` 作为中文映射层；**绝不修改 USDA 原始 CSV 与原始字段**。
- 将“营养值缺失”表示为：数据库无行、API `null`、界面“—”。
- 所有餐盘计算返回该营养素的**克重覆盖率**与缺失食材清单。
- 能量按 `1008 → 2048 → 2047` 顺序取**一个**值，记录 `origin_nutrient_id`；`1062` kJ 不得并入 kcal。
- 每个数据集使用独立适配器；禁止假定字段语义一致。
- 营养行必须保留 `raw_amount` 与 `quality_flag`；不可用值写 `amount=NULL`，原值不得丢失。
- ETL 必须显式指定 `--mode sample` 或 `--mode full --confirm-full`，无 mode 时拒绝执行。
- sample 只输出到 `data/build/sample/`，与正式库物理隔离；full 先写临时数据库，校验通过后原子替换正式库。
- 每次数据库重建生成校验报告，包含导入计数、缺失率、冲突数、黄金样本对照、中文映射分布、Foundation 469/395/74 差异。

### 禁止

- 禁止把缺失值、空字符串、空单元格写成 `0`。
- 禁止把 `1008`、`2047`、`2048` 三种能量相加。
- 禁止对营养值做插值、猜测、按同类平均值填充。
- 禁止把 Foundation `food.csv` 的 `sub_sample_food`、`market_acquisition`、`sample_food`、`agricultural_acquisition` 当作食品导入。
- 禁止按 FDC 营养 ID 直接解析 FNDDS 的 `food_nutrient.nutrient_id`（它是传统编号，如 `301`、`208`），必须经 `nutrient.nutrient_nbr → nutrient.id` 映射。
- 禁止用 Branded 的 `food.food_category_id` 做分类（该字段为空）。
- 禁止删除 Branded 数据源，或把品牌商品混入默认食材库。
- 禁止为 Branded 伪造 `food_portion` 克重；禁止在无可靠密度数据时把 `ml/MLT` 自动换算为克。
- 禁止直接删除重复 GTIN 的历史记录；按 `publication_date` 保留版本。
- 禁止让 sample 库写入正式库路径，禁止覆盖任何已存在的正式数据库。
- 禁止把原始 CSV、SQLite、ZIP 提交进 Git（`data/curation/*.csv` 除外）。
- 禁止在文档中编造数据行数、覆盖率或测试结果；数字必须来自实际扫描。

### 已核验基准（改动前必须重新核验）

| 数据集 | 真实食品数 | 关键事实 |
| --- | ---: | --- |
| Foundation | 469 | `food.csv` 共 87,990 行，其余为样本/采购；`foundation_food.csv` 仅 395 行，差 74 条，不得作白名单；能量并集覆盖 378 |
| SR Legacy | 7,793 | 核心营养覆盖完整 |
| FNDDS | 5,432 | 2021-01-01 至 2023-12-31；`nutrient_id` 用传统编号 |
| Branded | 1,999,950 | 无 `food_portion.csv`；`food_category_id` 为空；独立品牌库，默认不查询 |

---

## 3. 中文与文案

- 所有用户可见文字用简体中文，包括：导航、按钮、占位符、错误、空状态、加载、图表标题、图例、tooltip、帮助、导出说明。
- 文案集中在 `frontend/src/i18n/zh-CN.ts`；禁止在组件中散落长句。
- 允许保留英文的范围：USDA 原始食品名、品牌名、FDC ID、GTIN/UPC、单位（kcal/g/mg/µg）。
- 中文名三级状态必须在界面可区分：
  - `verified`：人工核验，中文名作为主名显示。
  - `glossary`：词典规则译名，中文名作为主名显示，并标注“词典译名 / 待核验”标签，英文原名作为次名。
  - `none`：暂无中文名，以英文原名在默认食材库展示并标注“暂无中文名”，不因缺少中文名排除（数据保留，可通过 fdc_id 查询）。
- `zh_status` 之外必须维护 `review_status`（`verified` / `pending`）：`glossary` 与 `none` 默认 `pending`，界面显示“待核验”；人工核验后才升级。
- 中文化是数据处理阶段的任务：营养名称、单位、分类与常见食材中文名必须在 ETL 阶段建立，不得留到 UI 阶段集中补。
- 待核验清单生成到 `data/build/zh_pending.csv`，不得当作正式映射提交。
- 禁止机翻品牌商品名；禁止编造中文别名。
- 错误文案必须说明“发生了什么 + 用户能做什么”。
- 禁止医疗化措辞：“治愈”“疗效”“必须吃”“最佳方案”等。

---

## 4. 视觉与图标

- 风格：温暖奶油色、柔和绿色、浅橙色；扁平、圆润、精致，不做幼稚儿童风，不做拥挤数据大屏。
- 禁止使用真实食物照片；禁止用 AI 生成写实食物图。
- 食材图标唯一来源：`frontend/src/assets/food-icons/` + `FoodIcon` 组件。
- 同一食材在食材库、餐盘、替换、对比、方案卡片中必须使用同一图标和主色。
- 未匹配食品使用分类兜底图标，禁止各页面自行绘制。
- 颜色只能取自 `styles/` 中的 CSS 令牌；禁止散落硬编码颜色。
- 默认视图最多 4 个核心数字 + 1 个主视觉 + 1 条提示；复杂图表需用户主动展开。
- 不使用普通柱状图/饼图作为主要视觉亮点；不使用 3D 图表。
- 动画 160–240ms，必须尊重 `prefers-reduced-motion`。

---

## 5. 架构边界

- 前端只能通过本地 `/api/*` 获取食品数据；禁止把 USDA 数据打包进 bundle。
- 食品类 SQLite（默认食材库、品牌库、用途库、外部补全库）只读，不提供写入接口；唯一可写库是独立的每周计划库 `data/build/meal_canvas_planner.sqlite`，只允许 `/api/planner` 读写计划数据，禁止写入任何食品、补全或用途数据。
- 用户方案与偏好只存浏览器：IndexedDB（方案）、localStorage（偏好）；每周膳食计划存后端独立计划库，不做账号与多用户体系。
- 方案必须保存营养快照与 `dataVersion`；数据版本变化时提示，不静默换数。
- 计算契约以前后端一致为准：分母只含已知值，覆盖率单独返回。
- 图表按需懒加载，不得进入首屏主 chunk。
- ETL 与 API 代码分离：`backend/app/etl/` 不得被请求路径导入。

---

## 6. 编码约定

### 后端

- Python 3.13，类型注解；模块化路由；Pydantic v2 模型。
- 数据访问用标准库 `sqlite3` + 参数化 SQL，禁止拼接用户输入。
- 所有查询必须有上限与分页；搜索 `pageSize ≤ 100`。
- 错误统一结构 `{code, message, detail?}`，`message` 为中文。
- ETL 使用生成器/分批提交，禁止一次性读取整个大 CSV。
- 连接设置 `PRAGMA query_only=ON`（API 侧）。

### 前端

- TypeScript 严格模式；禁止 `any` 滥用。
- 组件按 `pages / features / components` 分层；业务逻辑放 `features` 或 `lib`。
- 所有异步请求用 TanStack Query，统一 loading/error/empty。
- 拖拽必须有键盘与按钮替代路径。
- 数字格式化集中在 `lib/format.ts`；禁止各页面自行决定小数位。
- 图表统一通过 `ChartShell` 封装，禁止每个页面重复初始化 ECharts。

---

## 7. 工作流程纪律

1. **先检查再修改**：改任何文件前先读取；不得未检查就覆盖。
2. **先说明计划**：非平凡任务先给出步骤，再动手。
3. **小步交付**：一次只完成一个可验证增量。
4. **实际验证**：运行构建、测试或接口请求，并记录真实输出。
5. **禁止虚假成功**：没运行就说没运行；失败就报告失败与原因。
6. **阻塞要说明**：缺数据、缺依赖、端口冲突、网络不可用，必须明确报告并给出替代方案。
7. **同步文档**：规格、API、数据口径变化必须同阶段更新 `PROJECT_SPEC.md` 或 `DEVELOPMENT_PLAN.md`。
8. **不扩大范围**：不顺手重构无关代码，不添加未被要求的“优化”。

### Windows 环境固定命令

```powershell
# Python：直接调用 venv 内解释器，避免 PowerShell 执行策略拦截
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe -m pytest backend\tests -q
.\.venv\Scripts\python.exe -m uvicorn backend.app.api.main:app --port 8000

# Node：必须用 npm.cmd，不能直接 npm
npm.cmd --prefix frontend install
npm.cmd --prefix frontend run dev
```

---

## 8. 提交与文件管理

- 原始数据：工作区外 `..\数据集`，只读。
- 生成物：`data/build/`、`node_modules/`、`dist/`、日志、缓存，一律不入库。
- 允许入库的 CSV：仅 `data/curation/*.csv`。
- 不主动创建额外文档（`*.md`）；需要时先确认。
- 不初始化 Git 或提交，除非用户明确要求。

---

## 9. 每阶段完成检查表

- [ ] 已实际运行该阶段命令，并保存真实输出
- [ ] 数据计数与基准一致，或有书面解释
- [ ] Foundation 469 / 395 / 74 差异已在报告中列出
- [ ] 缺失值全程保持未知，没有出现 0 替代
- [ ] `raw_amount` 与 `quality_flag` 已写入，异常值未进入计算
- [ ] 品牌商品仅在独立库中，未混入默认食材库
- [ ] sample 输出在 `data/build/sample/`，正式库未被覆盖
- [ ] 新增界面全中文（允许项除外）
- [ ] 食材图标复用了统一注册表
- [ ] 键盘可完成主路径
- [ ] 加载/空/错误状态齐全
- [ ] 没有把原始数据或数据库写入版本库
- [ ] `PROJECT_SPEC.md` / `DEVELOPMENT_PLAN.md` 已同步
- [ ] 阶段报告明确写出“已完成 / 未完成 / 已知限制”
