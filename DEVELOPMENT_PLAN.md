# Meal Canvas · 分阶段开发计划

| 项目 | 内容 |
| --- | --- |
| 版本 | v1.2 |
| 日期 | 2026-10-23 |
| 当前阶段 | **阶段 2：前端骨架 + 食材库（已完成）** |
| 下一阶段 | 阶段 3：动态餐盘 + 计算 + 营养聚光灯 |
| 配套文档 | [PROJECT_SPEC.md](PROJECT_SPEC.md)、[.trae/rules/meal-canvas.md](.trae/rules/meal-canvas.md) |

> 本计划按“可验证的增量”拆分。每个阶段结束必须实际运行构建/测试并报告真实结果；不得因为文档写完就声称功能完成。

---

## 0. 开发原则

1. **数据先行**：先证明四套数据能被正确解析，再做任何界面。数据口径错误会让所有图表失去意义。
2. **每个阶段可独立验收**：有明确产出、验证命令、退出条件；不通过不进入下一阶段。
3. **不一次性生成全部功能**：每阶段只做该阶段范围，复杂图表放到用户主动探索的页面。
4. **诚实优先**：缺失就是未知；没运行的测试不说通过；技术限制直接写进报告。
5. **中文优先**：从第一个页面起就使用简体中文，避免后期集中翻译。
6. **视觉一致**：食材图标只维护一套注册表，任何页面不得自行画新图标。

---

## 1. 环境基线（已核验）

| 项 | 实测结果 | 影响 |
| --- | --- | --- |
| 项目根目录 | `c:\Users\Markli\Desktop\营养餐盘项目\1` | 当前为空，已创建骨架 |
| 原始数据 | `..\数据集` 下四个 ZIP，未解压 | 工作区外；ETL 流式读取 |
| Python | 3.13.9（Anaconda，pip 25.3） | 使用项目内 `.venv` 隔离 |
| Node | v24.21.0 | 满足 Vite 要求 |
| npm | `npm.ps1` 被执行策略阻止 | **必须使用 `npm.cmd`** |
| PowerShell | 配置文件脚本被禁止加载 | 命令仍可执行；不要依赖 profile |
| Git | 2.55.0 | 尚未初始化仓库 |
| SQLite | Python 内置 3.51.0，FTS5 可用 | trigram 对 2 字中文无效，改用 bigram |

已完成的实际核验：

- 读取四个 ZIP 的目录与关键 CSV 表头。
- 统计 `food.csv` 行数与 `data_type` 构成。
- 统计 `food_nutrient.csv` 行数与核心营养覆盖。
- 确认 FNDDS `food_nutrient.nutrient_id` 存的是传统编号（`301`、`208`）。
- 确认 Foundation 真实食品仅 469 条，能量覆盖率 80.6%。
- 确认 Branded 无 `food_portion.csv`，`food_category_id` 为空。
- 确认 Branded 营养值按每 100g 归一（样本 1105904）。
- 测试 FTS5 trigram 对 2 字中文返回空。

这些事实已写入 PROJECT_SPEC 第 3 节，后续不得凭印象改动。

---

## 2. 阶段 0：规格与骨架（已完成）

### 交付物

- `PROJECT_SPEC.md`：完整规格、数据事实、API 契约、功能规格、视觉与验收标准。
- `.trae/rules/meal-canvas.md`：项目级开发规则。
- `.gitignore`：忽略原始数据、数据库、缓存、构建产物，仅放行 `data/curation/*.csv`。
- 目录骨架：`backend/`、`frontend/`、`data/{raw,curation,build}`、`scripts/`、`docs/`。
- `DEVELOPMENT_PLAN.md`：本文件。

### 实际验证

- 使用 `Get-ChildItem` 确认工作区初始为空，未覆盖任何既有文件。
- 使用 Python 流式扫描四个 ZIP（未解压）获得真实计数。
- 使用 `New-Item` 创建目录，并复查目录树。
- 文件写入后需再次检查内容与编码（见本轮收尾验证）。

### 明确未做

- 没有安装前端/后端依赖。
- 没有创建数据库。
- 没有实现任何 API 或页面。
- 没有初始化 Git 仓库。

**退出条件**：文档与骨架齐备，且用户确认规格方向。✅（待用户确认）

---

## 3. 阶段 1：数据管道 MVP（下一步）

### 目标

四个数据源全部纳入数据处理设计：Foundation、SR Legacy、FNDDS 进入默认食材库；Branded 写入独立品牌库，默认不查询。先用真实 CSV 的固定 manifest 子集构建 **sample** 库并完成校验，**full 构建单独门禁，本阶段不执行**。品牌前端功能留到阶段 7。

阶段 1 的完成标准是“口径正确、可追溯、可重复”，而不是“数据全部导入”。

### 任务

1. **后端工程骨架与配置**
   - `backend/requirements.txt`：fastapi、uvicorn、pydantic-settings、pytest、httpx、ruff、pypinyin。
   - `backend/pyproject.toml`：ruff/pytest 配置。
   - `.env.example`：`MEAL_CANVAS_DATA_DIR`、`MEAL_CANVAS_DB_PATH`、`MEAL_CANVAS_BRANDED_DB_PATH`、`MEAL_CANVAS_SAMPLE_DIR`、CORS。
   - `backend/app/core/config.py`：校验数据目录与四个 ZIP 存在；无效时抛出中文错误，列出缺失文件与期望路径。
   - `backend/app/main.py`（仅 health 与异常处理）。

2. **数据库 schema（双库）**
   - 按 PROJECT_SPEC 4.2 建立 `schema.sql`，包含 `library_scope`、`zh_review_status`、`raw_amount`、`quality_flag`。
   - 主库 `meal_canvas.sqlite`：Foundation + SR + FNDDS；品牌库 `meal_canvas_branded.sqlite`：Branded。
   - 每个库先写 `.tmp`，校验通过后原子替换；文件已存在时 full 模式必须要求 `--confirm-full`，sample 模式写入 `data/build/sample/`。

3. **四数据集适配器（全部实现）**
   - `backend/app/etl/base.py`：统一接口 `iter_foods()`、`iter_nutrients()`、`iter_portions()`，流式生成器。
   - `foundation.py`：只接收 `food.csv` 中 `data_type='foundation_food'` 的 469 条；分类走 `food_category`；**禁止**使用 `foundation_food.csv` 作白名单。
   - `sr_legacy.py`：全量 7,793 条；营养 ID 直通。
   - `survey.py`：`nutrient_id` 按 `nutrient.nutrient_nbr` 解释并映射为 FDC ID；分类走 WWEIA；全部标记“膳食调查食品 / 组合食品”。
   - `branded.py`：只取 `data_type='branded_food'`；分类走 `branded_food_category`；份量只读 `serving_size` 等标签字段；写入独立品牌库。
   - 每个适配器必须能独立运行并打印计数，不共享“猜测字段”的代码。

4. **营养规范化与质量字段**
   - `backend/app/etl/nutrients.py`：`nbr → 规范 nutrient_id` 映射；核心营养白名单（约 20 项）。
   - 能量三级回退（1008 → 2048 → 2047），写一条规范值并记录 `origin_nutrient_id`；`1062` kJ 单独隔离，不参与 kcal。
   - 校验 FNDDS 的 `208/301/...` 能映射到 `1008/1087/...`。
   - 每行保留 `raw_amount`；异常写入 `quality_flag`：`negative`（原值保留、规范值 NULL）、`duplicate`、`unmapped_nutrient`、`unit_unknown`、`energy_conflict`。
   - 缺失不写入行，不补 0；负数不改写、不进入计算。

5. **中文映射层（正式数据任务）**
   - `data/curation/nutrient_zh.csv`：全部核心营养 + 常用微量营养，含单位中文与显示小数位。
   - `data/curation/category_zh.csv`：FDC 分类、WWEIA 分类、品牌分类。
   - `data/curation/food_zh.csv`：首批不少于 150 个常见基础食材，含 `status=verified`、`review_status=verified`、别名、拼音、核验日期。
   - `data/curation/glossary_rules.csv`：规则译名候选，生成 `status=glossary`、`review_status=pending`。
   - `backend/app/etl/zh_overlay.py`：把映射叠加到 `food.name_zh`，不改 `description_en`；同时生成 `data/build/zh_pending.csv`。
   - 无法可靠翻译的保持 `none`；品牌专有名称保留英文，仅翻译有可靠依据的通用描述。

6. **sample manifest 与构建模式**
   - `backend/app/etl/sample_manifest.py`：从真实 CSV 选取固定 `fdc_id`，生成 `data/build/sample/manifest.json`；生成后逐条回查原始数据确认存在。
   - 覆盖范围：
     - Foundation 全量 469。
     - SR 按 25 分类分层 300–400 条（每类 ≥5 条）。
     - FNDDS **先统计各 WWEIA 分类的真实食品数**，从 ≥5 条真实食品的分类中选择 ≥100 个分类，每类抽 ≥5 条；预计 500–600 条，实际以真实分布为准；不足 100 类时如实报告，不伪造记录。必须包含 `2705383 Milk, human` 与至少 1 条份量克重为 0 的记录。
     - Branded 按六类边界定向选取并逐项记录 `fdc_id` 与验证结果：同 GTIN 多版本、无营养、停售、`ml/MLT`、非质量单位、空品牌分类；另补足常规样本至约 500 条。
   - `backend/app/etl/build.py` 必须显式接收 `--mode sample` 或 `--mode full --confirm-full`；sample 只写 `data/build/sample/`（主库 `meal_canvas.sqlite`、品牌库 `meal_canvas_branded.sqlite`、manifest、校验报告、`zh_pending.csv`、`DATA_LOCALIZATION_REPORT.md`、`logs/`），并与正式库路径做不同路径校验。
   - 本阶段只执行 sample，不执行 full。

7. **搜索索引**
   - 中文 bigram + 英文 token + 拼音写入 `food.search_tokens`。
   - FTS5 表 + 查询侧同样的 bigram 切分。
   - 排序权重按 PROJECT_SPEC 4.3 实现。

8. **API（只读，主库 + 品牌库）**
   - `/api/health`、`/api/meta/sources`、`/api/meta/nutrients`、`/api/meta/categories`。
   - `/api/foods`（`library=default|branded`、搜索、筛选、分页）、`/api/foods/{fdc_id}`、`/api/foods/batch`。
   - 中文错误消息；主库不存在返回 503；品牌库不存在时品牌查询返回 503 与明确提示。

9. **校验**
   - `backend/app/etl/validate.py` 生成 `data/build/validation_report.md` 与 `validation_report.json`。
   - 必查：Foundation 469/395/74；能量来源分布 135/214/29/91；`fdc_id` 重复 0；`library_scope` 不一致 0；品牌库 `food_portion` 行数 0；负值进入计算 0；`amount=NULL AND quality_flag='ok'` 为 0；中文状态分布与待核验清单一致。
   - 随机 10 个食品与原始 CSV 对照（含 `raw_amount`）。

10. **测试**
   - 用小型合成 CSV 测试适配器语义（尤其 FNDDS 传统编号、Branded 单位、负值质量标记）。
   - 用 sample 库做 5–10 个黄金样本（每 100g 值、能量回退、缺失为 null）。
   - API 测试：搜索 2 字中文、分页、404、主库 503、品牌库 503。

### 建议目录落点

```text
backend/
├─ app/
│  ├─ api/{__init__,meta,foods}.py
│  ├─ core/{config,errors}.py
│  ├─ db/{connection,queries}.py + db/schema.sql
│  ├─ etl/
│  │  ├─ base.py
│  │  ├─ nutrients.py
│  │  ├─ zh_overlay.py
│  │  ├─ sample_manifest.py
│  │  ├─ build.py
│  │  ├─ validate.py
│  │  └─ sources/{foundation,sr_legacy,survey,branded}.py
│  ├─ models/{food,meta}.py
│  ├─ services/nutrition.py
│  └─ main.py
├─ tests/{test_adapters,test_nutrients,test_api,test_golden}.py
├─ requirements.txt
└─ pyproject.toml
```

### 验证命令（本阶段实际执行后再报告）

```powershell
# 创建环境（直接调用 venv 内 python，绕过 PowerShell 执行策略）
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt

# 1) 生成 sample manifest（只记录真实存在的 fdc_id）
.\.venv\Scripts\python.exe -m backend.app.etl.sample_manifest --out data\build\sample\manifest.json

# 2) 构建 sample 主库（Foundation + SR + FNDDS）到隔离目录
.\.venv\Scripts\python.exe -m backend.app.etl.build --mode sample --library default --manifest data\build\sample\manifest.json

# 3) 构建 sample 品牌库
.\.venv\Scripts\python.exe -m backend.app.etl.build --mode sample --library branded --manifest data\build\sample\manifest.json

# 4) 校验 sample
.\.venv\Scripts\python.exe -m backend.app.etl.validate --mode sample --dir data\build\sample

# 5) 测试
.\.venv\Scripts\python.exe -m pytest backend\tests -q

# 6) 启动 API（仅指向 sample 库）
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

**本阶段不执行的命令**：任何 `--mode full`、任何写入 `data/build/meal_canvas.sqlite` 或 `meal_canvas_branded.sqlite` 的构建。full 构建需在 sample 校验通过、用户书面确认后单独进行。

### 退出条件（全部满足）

- sample manifest 中每个 `fdc_id` 都能在原始 CSV 中找到；实际导入数等于 manifest 数。
- Foundation 导入 469 条；校验报告列出 469 / 395 / 74 及 74 条缺失清单。
- Foundation 能量来源分布为 `1008` 135、`2048` 214、`2047` 29、无能量 91。
- FNDDS 核心营养记录数 > 0；`208 → 1008`、`301 → 1087` 至少各命中一次。
- 负值记录保留 `raw_amount` 且 `amount=NULL`；负值进入计算的数量为 0。
- 品牌库中 `food_portion` 行数为 0；`ml/MLT` 未被换算为克；GTIN 多版本记录未被删除。
- 主库 `library_scope` 全部为 `default`，品牌库全部为 `branded`；不一致数为 0。
- 搜索“西兰花”“鸡胸”“broccoli”均返回合理结果；2 字中文不空。
- 任意抽查食品的营养值与 CSV 一致；缺失项 API 返回 `null`。
- sample 构建可重复执行；失败不影响正式库；正式库文件未被创建或覆盖。
- 中文映射：`verified` 食材不少于 150；待核验清单已生成；三类状态数量可查。
- 校验报告与测试全部通过，并把真实输出贴进阶段报告。
- 所有 API 错误消息为中文。

---

## 4. 阶段 2：前端骨架 + 食材库

### 目标

建立统一视觉与中文壳层，完成可用的食材浏览体验。

### 任务

- 初始化 Vite + React + TypeScript；ESLint/Prettier；路径别名。
- 设计令牌、全局样式、布局（导航/工作区/洞察栏）。
- 文案表 `i18n/zh-CN.ts`；日期与数字格式化。
- 食材 SVG 图标系统：首批 20–40 个，按分类/关键词映射；`FoodIcon` 唯一入口。
- 食材库：搜索（250ms 防抖）、数据集/分类筛选、排序、分页、卡片、详情抽屉。
- 状态：骨架屏、空结果、错误重试、品牌未开启说明。
- API 客户端、TanStack Query 配置。
- 组件测试：搜索交互、详情渲染、中文缺失状态。

### 退出条件

- 全界面无英文残留（允许 USDA 原名、品牌名、单位）。
- 同一食材在列表与详情图标一致。
- 2 字中文搜索可用；键盘可完成搜索与打开详情。
- 手机布局可用（至少 390px 宽）。
- 截图与真实运行结果记录在阶段报告。

---

## 5. 阶段 3：动态餐盘 + 计算 + 营养聚光灯

### 目标

完成“操作 → 实时反馈 → 贡献解释”的核心闭环。

### 任务

- 餐盘状态（Zustand）：添加、删除、调克、排序、清空、撤销。
- dnd-kit 拖拽 + 点击添加 + 键盘替代。
- 盘形画布与食材卡片；克数输入/滑杆/快捷份量。
- 前端营养计算模块：缓存每 100g 快照；覆盖率与未知项；与后端同一契约。
- 后端 `/api/plans/calculate` 与前端计算一致性测试（黄金样本）。
- 默认洞察只显示能量/蛋白质/脂肪/碳水 + 覆盖率；展开显示全部。
- 营养聚光灯：贡献河带 + 排序列表 + 缺失项单列。
- 草稿自动保存到 localStorage（刷新不丢）。

### 退出条件

- 调克即时更新（实测 ≤ 50ms，本地样本）。
- 前后端合计误差为 0（同精度输入下）。
- 缺失营养显示“—”且不参与分母；覆盖率正确。
- 聚光灯占比在已知部分合计 100%。
- 不使用饼图/柱状图作为聚光灯主视觉。

---

## 6. 阶段 4：方案管理 + 双餐盘对比

### 目标

方案可保存、可恢复、可比较、可导出；对比能解释差异来源。

> 当前进展：已实现对比槽 A/B 快照（IndexedDB 持久化）与餐盘设计页快捷保存；方案命名、上限 100、导入导出、`dataVersion` 变更提示尚未实现。

### 任务

- IndexedDB 方案 CRUD（上限 100）、重命名、复制、删除确认。
- 方案快照 + `dataVersion`；旧版本提示与“用最新数据重算”。
- JSON 导入/导出、CSV 长表导出。
- 对比槽 A/B；载入方案或复制当前餐盘。
- `/api/plans/compare`：总量、覆盖率、绝对/相对差、Top 3 关键差异、逐食材差异分解。
- 对比页：双盘 + 关键差异卡；差异河/成对斜率下钻；警告（覆盖率、克重差异）。
- 测试：除零、未知、A/B 交换符号、顺序无关。

### 退出条件

- 刷新/重开浏览器方案仍在。
- 导出再导入后数值一致。
- 关键差异均可追溯到食材与克数。
- 无 `NaN`/`Infinity` 出现在任何响应或界面。

---

## 7. 阶段 5：替换模拟器 + 营养目标

### 目标

支持“先预览、后应用”的替换决策，以及目标距离可视化。

### 任务

- 替换候选接口：同分类优先 + 营养相似度回退；返回差值。
- 替换抽屉、幽灵叠加预览、差值胶囊、应用/取消。
- 覆盖率变化提示；数据不完整警告。
- 目标设置（能量、蛋白质、脂肪、碳水、纤维、钠；上下限）。
- 环形距离弧（自定义 SVG），达标/超出/不足三态；覆盖率提示。
- 本地保存目标与偏好。

### 退出条件

- 预览不影响当前方案；应用可撤销。
- 替换前后差异与后端计算一致。
- 目标为空/非法输入有中文校验。
- 不出现“推荐摄入量”类无来源结论。

---

## 8. 阶段 6：探索地图 + 流向图 + 热力矩阵

### 目标

提供用户主动探索的三种深入视图，信息密度受控。

### 任务

- `/api/explore`：按营养轴取样，排除缺失，返回点数与抽样说明。
- 散点图：轴切换、对数、分类色、框选、加入餐盘、缺失排除提示。
- Sankey：食材 → 分类 → 所选营养；Top 8 + 其他；未知说明。
- 热力矩阵：对比 A/B，行营养、列 Top 差异食材 + 合计；发散色阶、斜纹缺失、点击解释。
- 图表主题统一从设计令牌读取；图表懒加载。
- 性能：散点 ≤ 2,000；Sankey 节点 ≤ 20；矩阵默认 8×12。

### 退出条件

- 三个视图均能回答预设问题，且有文字摘要。
- 缺失不被画成 0；图例/提示准确。
- 切换轴/指标不出现请求风暴（取消旧请求或防抖）。
- 首屏不加载图表 chunk。

---

## 9. 阶段 7：品牌数据 + 打磨 + 发布

### 目标

启用品牌商品库（独立库）、补齐数据说明、可访问性、端到端验证，形成可交付版本。

### 任务

- 阶段 1 已实现 `BrandedAdapter` 与 sample 品牌库；本阶段执行 full 品牌库构建（`--mode full --confirm-full --library branded`）。
- 品牌搜索显式开关（`library=branded`）；品牌名保留英文；GTIN 搜索（可选）；无营养商品显示未知，不填 0。
- 数据说明页：四数据集、版本、行数、口径、能量回退、FNDDS 编号、中文三级与核验状态、授权与免责声明。
- 可访问性审计：键盘、焦点、对比度、图表文字摘要、减少动效。
- 响应式复查（390/768/1280/1440）。
- Playwright 冒烟：搜索→添加→调克→聚光灯→保存→对比→导出。
- 性能实测：首屏、搜索 p95、餐盘更新、数据库体积。
- 最终 README（启动步骤、构建命令、已知限制）——仅在用户确认需要时创建。

### 退出条件

- 四个数据集均可查询；品牌默认关闭且说明清楚。
- 数据说明页信息与本文档一致。
- E2E 冒烟通过（真实运行）。
- 无阻塞性可访问性问题。
- 从干净环境按文档可复现启动。

---

## 10. 跨阶段质量门槛

| 门槛 | 要求 |
| --- | --- |
| 数据 | 不伪造、不插值、不把缺失当 0；每个数值可追溯到 FDC ID 与原行 |
| 中文 | 新增界面无未解释英文；错误/空/加载状态完整 |
| 视觉 | 无真实食物照片；图标唯一来源；色彩来自令牌 |
| 交互 | 主路径键盘可达；拖拽有替代操作 |
| 性能 | 遵守 PROJECT_SPEC 11.1 预算；超标必须报告原因 |
| 测试 | 每次阶段结束实际运行并记录命令与输出 |
| 文档 | 规格变更同步更新；阶段报告写“完成/未完成/限制” |

---

## 11. 风险检查点

- **阶段 1 前**：确认 `MEAL_CANVAS_DATA_DIR` 指向四个可读 ZIP；确认 FNDDS 编号映射与能量回退方案，否则停止，不进入前端。
- **阶段 1 中**：若 sample 库构建时间或体积异常，先缩小 manifest 并报告，不擅自删除数据源或降低校验项。
- **阶段 1 sample 通过后**：full 构建必须单独确认；执行前检查正式库是否存在，存在则不得覆盖，需用户明确批准。
- **阶段 2 前**：确认中文映射覆盖足够，避免食材库大面积英文。
- **阶段 3 前**：确认前后端计算契约一致，避免“界面一个数、导出另一个数”。
- **阶段 6 前**：确认图表按需加载，避免首屏被 ECharts 拖慢。
- **阶段 7 前**：确认品牌库构建可回滚，且默认不影响基础食材体验。

---

## 12. 下一轮具体动作（阶段 1 开始）

1. 创建 `backend/requirements.txt`、`pyproject.toml`、`.env.example`，安装依赖到 `.venv`；先验证配置能正确读取四个 ZIP。
2. 实现 `schema.sql`（双库共用）与 `db/connection.py`。
3. 实现四源适配器，先用真实 ZIP 跑通计数：Foundation 469、SR 7,793、FNDDS 5,432、Branded 1,999,950（仅计数，不写正式库）。
4. 解决 FNDDS 传统编号映射、能量回退、`raw_amount` / `quality_flag`，写回归测试。
5. 生成中文映射框架（营养名、分类、单位、≥150 个常见食材核验名）并生成待核验清单。
6. 生成 sample manifest，构建 sample 主库与 sample 品牌库，输出校验报告并抽查 10 个食品。
7. sample 校验通过并经用户确认后，才讨论 full 构建；在此之前不写任何正式数据库。

完成以上步骤并实际验证后，再进入前端阶段。

---

## 13. 当前状态声明

- 本阶段只创建了文档、目录与忽略规则。
- **没有**安装依赖、**没有**创建数据库、**没有**实现 API 或页面。
- 所有数据数字来自实际扫描，但尚未构建完整数据库。
- 下一步需用户确认本实施计划后，才开始编写 ETL 脚本；先跑 sample，不执行 full。
