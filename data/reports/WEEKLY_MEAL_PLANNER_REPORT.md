# 每周膳食计划（Weekly Meal Planner）交付报告

| 项目 | 内容 |
| --- | --- |
| 功能 | 每周膳食计划 + 今日餐单 |
| 完成日期 | 2026-10-31 |
| 范围 | 增量功能：新增计划页面、今日餐单页面、独立计划库与计划 API；未改动 USDA 原始数据、ETL、用途分类与食品库 |
| 结论 | 已完成；后端 154 项测试、前端 43 项测试、ruff、typecheck、lint、生产构建全部通过，并在真实浏览器完成三条主流程验收 |

---

## 1. 新增页面与组件

### 页面

| 文件 | 说明 |
| --- | --- |
| `frontend/src/pages/WeeklyPlanPage.tsx` | 「每周计划」主页面：周导航、7 天卡片、每餐增删改、复制餐次、保存状态、未保存切周拦截、今日定位与高亮 |
| `frontend/src/pages/WeeklyPlanPage.module.css` | 页面样式：周工具栏、保存状态 chip、日卡片与今日高亮、餐次网格、周能量条、弹窗与响应式 |
| `frontend/src/pages/TodayMenuPage.tsx` | 「今日餐单」页面：按本地日期定位今天，展示四餐食品与克数、每餐营养合计与修改入口、空状态 |
| `frontend/src/pages/TodayMenuPage.module.css` | 今日餐单样式：摘要条、餐次卡、食品行、全天合计、空状态 |

### 复用与新增组件

| 文件 | 说明 |
| --- | --- |
| `frontend/src/features/planner/MealCard.tsx` | 单个餐次卡片；复用 `PlateItemControls`、`FoodIcon`、`PlannerNutrition`；支持空状态、添加食品、删食品、复制、清空/删除加餐 |
| `frontend/src/features/planner/FoodPicker.tsx` | 添加食品弹窗；`createPortal` 渲染，直接复用现有 `FoodLibrary` 搜索与选择组件；支持一次暂存多种食品、分别填克数后一次确认全部加入 |
| `frontend/src/features/planner/AddPlateToPlanDialog.tsx` | 「整盘加入计划」对话框；选择日期与餐次后把整盘食品按当前克数一次写入计划库，餐盘设计页与方案对比页共用 |
| `frontend/src/features/planner/PlannerNutrition.tsx` | 营养合计展示；复用 `computePlateNutrition`，显示能量、蛋白质、脂肪、碳水化合物、膳食纤维 |
| `frontend/src/features/planner/usePlannerFoodDetails.ts` | 整周食品去重后用 `useQueries` 批量请求 `getFood` 与 `getEnrichedNutrients`，再经 `mergeEnrichment` 合并 |
| `frontend/src/features/planner/AddToPlanForm.tsx` | 食品详情抽屉内的「加入计划」表单：日期（默认今天）、餐次、克数 |
| `frontend/src/features/planner/model.ts` | 纯函数模型：本地日期、周计算、草稿、增删改、复制、保存状态 |

### 接入改动

| 文件 | 改动 |
| --- | --- |
| `frontend/src/app/App.tsx` | 新增 `/weekly`、`/today` 路由 |
| `frontend/src/components/AppShell.tsx` | 主导航新增「每周计划」「今日餐单」入口 |
| `frontend/src/components/FoodDetailDrawer.tsx` | 详情抽屉内加入 `AddToPlanForm`，可从食品详情直接加入某天某餐 |
| `frontend/src/pages/DesignerPage.tsx`、`DesignerPage.module.css` | 餐盘条目新增「加入计划」按钮（详情抽屉表单）；餐盘头部新增「整盘加入计划」按钮，整盘一次加入某天一餐 |
| `frontend/src/pages/ComparePage.tsx` | 方案 A/B 快照卡片新增「整盘加入计划」按钮，与餐盘设计页共用同一对话框 |
| `frontend/src/i18n/zh-CN.ts` | 新增 `planner` 文案块（全部简体中文） |
| `frontend/src/lib/types.ts`、`api.ts`、`queries.ts` | 新增计划类型、请求封装与 TanStack Query hooks |

没有复制第二套食品搜索、食品详情或营养计算实现：搜索复用 `FoodLibrary`，详情复用 `FoodDetailDrawer`，计算复用 `computePlateNutrition`，外部补全复用 `mergeEnrichment`。

---

## 2. 新增数据库表与 API

### 独立计划库

- 路径：`data/build/meal_canvas_planner.sqlite`
- 可通过 `MEAL_CANVAS_PLANNER_DB_PATH` 覆盖（测试使用临时库）。
- 与 `meal_canvas.sqlite`（默认食品库）、`meal_canvas_branded.sqlite`、`meal_canvas_enrichment.sqlite`、`meal_canvas_usage.sqlite` 物理隔离。
- 实现：`backend/app/planner/storage.py`；路由：`backend/app/api/routers/planner.py`。

表结构：

```sql
CREATE TABLE weekly_plan (
    plan_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    week_start TEXT NOT NULL UNIQUE,          -- 周一日期，YYYY-MM-DD
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE meal (
    meal_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id    INTEGER NOT NULL REFERENCES weekly_plan(plan_id) ON DELETE CASCADE,
    meal_date  TEXT NOT NULL,
    meal_type  TEXT NOT NULL,                 -- breakfast / lunch / dinner / snack
    meal_name  TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    notes      TEXT
);

CREATE TABLE meal_item (
    item_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    meal_id       INTEGER NOT NULL REFERENCES meal(meal_id) ON DELETE CASCADE,
    food_key      TEXT NOT NULL,
    library_scope TEXT NOT NULL,              -- default / branded
    amount_g      REAL NOT NULL,
    sort_order    INTEGER NOT NULL DEFAULT 0,
    name_snapshot TEXT
);
```

- `week_start UNIQUE` 保证同一周只有一条计划，不会创建互相冲突的记录。
- 加餐（`snack`）没有唯一约束，同一天可存在多条。
- `meal_item.food_key` + `library_scope` 保留食品身份；`name_snapshot` 保存名称快照，避免原记录变化后完全无法识别。

### API（前缀 `/api/planner`）

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/planner/plans/{week_start}` | 读取整周计划；未保存时返回 `plan_id=null` 与 7 个空日 |
| PUT | `/api/planner/plans/{week_start}` | 整周覆盖保存 |
| DELETE | `/api/planner/plans/{week_start}` | 删除整周计划 |
| POST | `/api/planner/plans/{week_start}/meals` | 新建餐次 |
| PUT | `/api/planner/meals/{meal_id}` | 修改餐次；传 `items` 时整组替换 |
| DELETE | `/api/planner/meals/{meal_id}` | 删除餐次 |
| POST | `/api/planner/meals/{meal_id}/items` | 添加食品 |
| PUT | `/api/planner/meals/{meal_id}/items/{item_id}` | 修改克数 |
| DELETE | `/api/planner/meals/{meal_id}/items/{item_id}` | 删除食品 |
| POST | `/api/planner/entries` | 从食品详情直接加入某天某餐；餐次不存在时自动创建 |
| POST | `/api/planner/entries/batch` | 一次向某天某餐追加多个食品（整盘加入）；餐次不存在时自动创建，单事务写入 |

校验规则：

- `week_start` 必须是周一，否则 400 中文错误。
- 餐次日期必须落在该周 7 天内。
- 早餐/午餐/晚餐每天各最多一条；加餐不限。
- `amount_g` 必须 `> 0` 且 `≤ 10000`。
- 日期一律使用 `YYYY-MM-DD` 纯字符串，后端不做 UTC 转换。

---

## 3. 计划的保存与读取

- 前端以「周草稿」为单位编辑；点「保存本周计划」调用 `PUT /api/planner/plans/{week_start}` 整周覆盖保存，避免每改一个食品就发一次请求。
- 保存成功后：状态变为「已保存」；刷新页面、切换周再返回，均从 `GET` 重新读取。
- 修改已保存计划后状态变为「尚未保存」，再次保存覆盖旧内容。
- 删除食品或餐次后同样标记为未保存，保存时整周覆盖，因此删除结果同步生效。
- 读取时若 `plan_id=null`，页面显示「尚未保存」和空状态；若 `plan_id` 有值，显示「已保存」。
- 切换周前若有未保存修改，弹窗提供「保存并切换」「放弃并切换」「留在本页」三个选项。
- 日期全部由前端本地日期构造（`parseISODateLocal` / `toISODateLocal`），不使用 `toISOString()`，避免 UTC 偏移。

---

## 4. 今日餐单入口

- 导航新增「今日餐单」，路由 `/today`。
- 页面使用本地日期 `todayISO()`，再计算当周周一，读取该周计划，只展示今天。
- 展示今天早餐、午餐、晚餐与全部加餐：食品图标、名称、克数、该餐营养合计、全天合计。
- 每餐提供「修改这一餐」，跳转 `/weekly?date=YYYY-MM-DD&meal=type`，计划页会滚动到当天并高亮该餐。
- 今天没有安排时显示空状态「今天还没有制定餐单」与「去制定今日餐单」按钮。
- 页面底部提供查看完整每周计划的入口。

---

## 5. 如何安排、修改、复制一周餐食

安排：

1. 打开「每周计划」，默认当前周（周一至周日）。
2. 在某天的某餐点「添加食品」，通过复用食材库搜索选择食品；可一次暂存多种食品、分别填写克数，再一次确认全部加入这一餐（重复食品自动跳过并在提示中计数）。
3. 每天可额外添加多个加餐；每个加餐可单独删除。
4. 餐盘设计页点「整盘加入计划」，或方案对比页 A/B 卡片点「整盘加入计划」，选择日期与餐次后整盘按当前克数一次写入计划库。

修改：

- 克数：直接修改该食品克数输入。
- 删除食品：点击删除，底部出现撤销条，可一键撤销。
- 清空/删除餐次：早餐/午餐/晚餐清空后保留餐次卡片；加餐删除后卡片消失，同样提供撤销。
- 复制餐次：选择源餐次与目标日期；主餐替换目标同类型餐次，加餐追加一个新餐次；源餐次不变，复制后各自独立可改。
- 删除整周计划：二次确认后删除。

保存状态四态在页面上明确显示：尚未保存 / 正在保存 / 已保存 / 保存失败，失败时显示中文错误原因。

---

## 6. 营养计算是否复用现有逻辑

完全复用，没有新增第二套计算：

- 每餐与全天合计使用现有 `computePlateNutrition`（`frontend/src/lib/calculator.ts`），以 `summary_per_100g` 按实际克数计算。
- 缺失值保持 `null`，界面显示「—」；不填 0。
- 已核实的外部补全值继续通过现有 `mergeEnrichment` 参与计算，只采纳 `origin === 'external' && status === 'verified_external'`。
- 整周能量概览只做 7 行横条，不新增图表类型；缺失能量显示「—」。

---

## 7. 实际运行的测试及结果

### 后端

```
.\.venv\Scripts\python.exe -m pytest backend\tests -q
→ 160 项全部通过（含 test_planner.py 26 项）

.\.venv\Scripts\python.exe -m ruff check backend
→ All checks passed!
```

`test_planner.py` 覆盖：空周读取、周起始非周一被拒、整周保存与回读、一餐多食品、多加餐、重复主餐被拒、日期越界、周首/周尾边界日期、修改克数、删除食品、删除餐次、整组替换、新建餐次、`/entries` 自动建餐、`food_key` 与 `library_scope` 保留、跨周隔离、跨年周日期、重复保存只保留一条计划、删除整周、非法克数；批量 `/entries/batch` 另覆盖：一次创建单餐次含全部食品、追加到已有餐次、加餐复用当天首条加餐、空列表 422、非法克数 422、非法日期 400。

### 前端

```
npm.cmd --prefix frontend run typecheck  → 通过
npm.cmd --prefix frontend run lint       → 0 errors / 0 warnings
npm.cmd --prefix frontend run test       → 4 个测试文件，45 项通过
                                          其中 planner/model.test.ts 18 项
npm.cmd --prefix frontend run build      → 构建成功（约 21.95s）
```

`planner/model.test.ts` 覆盖：本地日期解析与格式化、周起始计算、跨周/跨年切换、今日判断、草稿与响应互转、添加食品去重、批量添加（多食品一次加入、餐次已有/批次内重复/无效克数跳过计数）、改克数、删食品、删除主餐与加餐、多加餐编号、复制餐次（主餐替换/加餐追加、源不变）、保存状态迁移。

### 真实浏览器验收

使用浏览器自动化在 `http://localhost:5173` 实际操作：

1. 每周计划页：周范围（2026 年 10 月 26 日 – 11 月 1 日）、周一至周日 7 天、每日早餐/午餐/晚餐/加餐卡片、添加食品按钮、保存状态 chip 均可见 → PASS。
2. 周一早餐添加食品 100g 后保存，页面刷新后该食品与克数仍存在，状态显示「已保存」 → PASS。
3. 今日餐单：显示「10 月 31 日 · 周六」与今天标识；当天无计划时显示空状态；点击「去制定今日餐单」跳转 `/weekly?date=2026-10-31` 并定位高亮周六 → PASS。
4. 多选批量添加：早餐选择器中暂存两种食品（各 100g），底部出现「确认添加 2 种食品」；点击后周一早餐卡片显示 2 条食品，保存状态芯片变为「有未保存的修改」→ PASS。
5. 整盘加入计划：餐盘设计页点击「整盘加入计划」，对话框标题「把当前餐盘加入每周计划」，列出「A级大鸡蛋（全蛋）100 g」；选日期 2026-10-31、早餐后点击「加入计划」，显示「已把 1 种食品加入 10 月 31 日 的早餐」与链接「去每周计划查看这一天」（href `/weekly?date=2026-10-31&meal=breakfast`）→ PASS。
   - 首次验证返回 404：运行中的 uvicorn 是代码改动前启动的旧进程，不含新路由；重启后端后 POST `/api/planner/entries/batch` 返回 200 且自动创建周计划，浏览器重验通过。

未覆盖的浏览器场景：跨多个加餐的复制、断网保存失败的界面表现（仅通过代码逻辑与后端错误测试验证）。

---

## 8. 尚未完成的功能

本轮明确未做：

- 自动生成整周菜单、AI 菜谱推荐。
- 购物清单。
- 复杂的饮食目标/热量配额系统。
- 用户注册、登录、多用户隔离与权限（本机单用户，计划库不分用户）。
- 计划导出/导入（JSON/CSV）。
- 跨设备同步。

已知限制：

- 计划中的食品名称会随食品库最新数据刷新；`name_snapshot` 只作为食品记录不可用时的兜底显示。
- 整周保存为覆盖式写入，不保留历史版本。
- 品牌库入口仍按现有约定不在前端展示；计划中仍保留 `library_scope=branded` 的数据模型能力。
