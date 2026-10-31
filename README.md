# Meal Canvas —— 营养餐盘设计师

一款本机运行的营养餐盘设计与膳食规划工具：**选择食品 → 调整克数 → 查看营养 → 分析比较 → 制定每周计划**。

所有营养数据来自 **USDA FoodData Central**，缺失值如实显示为「—」，不使用 0 或猜测值填充。

![Tech](https://img.shields.io/badge/React-19-61dafb) ![Tech](https://img.shields.io/badge/TypeScript-5-3178c6) ![Tech](https://img.shields.io/badge/FastAPI-0.115-009688) ![Tech](https://img.shields.io/badge/SQLite-3-003b57)

---

## 一、功能概览

| 模块 | 说明 |
| --- | --- |
| 食品库与搜索 | 13,694 种真实食品，支持中文名 / 英文名 / 别名搜索，按分类、数据集、用途筛选 |
| 食品营养详情 | 每种食品 37 项营养素，按每 100 克展示，保留 FDC ID、数据集版本等来源信息 |
| 互动餐盘设计 | 添加食材、按克或常用份量调整重量，本餐营养实时合计 |
| 营养素贡献分析 | 任选营养素，条形图展示每种食材的贡献量，并可联动高亮餐盘中的食材 |
| 方案对比 | 餐盘存为方案 A / B 快照，雷达图 + 逐项差异（能量、蛋白质、脂肪等） |
| 食材营养探索 | 三维散点图，坐标轴可切换营养素，颜色区分食品分类 |
| 每周膳食计划 | 周一至周日 × 早餐/午餐/晚餐/加餐，支持一餐多选添加、复制餐次、整盘加入计划 |
| 今日餐单 | 按本地日期读取当天安排，直接回答「今天吃什么」 |
| 外部营养补全 | 检测缺失字段，按 GTIN 到 Open Food Facts 精确匹配，只写入独立补全库 |

> 品牌商品库（1,999,950 条）已在后端独立建库，按项目约定**前端不提供入口**。

---

## 二、技术栈

| 层 | 选型 |
| --- | --- |
| 前端 | React 19 · TypeScript（严格模式）· Vite · TanStack Query · Apache ECharts / ECharts-GL · dnd-kit · Lucide React |
| 后端 | Python 3.13 · FastAPI · Pydantic v2 · 标准库 `sqlite3`（参数化 SQL、WAL） |
| 存储 | SQLite：默认食材库、品牌库、外部补全库、每周计划库（仅计划库可写） |
| 数据处理 | 独立 ETL 模块 `backend/app/etl/`，每个数据集独立适配器，sample / full 模式物理隔离 |

---

## 三、目录结构

```
1/
├── backend/            # FastAPI 服务与 ETL
│   ├── app/api/        # 路由：foods / metadata / enrichment / planner / health
│   ├── app/etl/        # USDA 四数据集解析与建库
│   ├── app/enrichment/ # 外部营养补全
│   ├── app/planner/    # 每周膳食计划存储
│   └── tests/          # pytest（160 项）
├── frontend/           # React 前端
│   └── src/
│       ├── pages/      # 设计 / 分析 / 对比 / 探索 / 周计划 / 今日 / 数据来源
│       ├── features/   # food-library / designer / planner / compare / explore …
│       ├── components/ # AppShell、FoodIcon、ChartShell、FoodDetailDrawer …
│       └── i18n/       # 全部中文文案集中管理
├── data/
│   ├── curation/       # 人工维护的中文映射与用途分类 CSV（入库）
│   ├── reports/        # 建库与补全报告
│   └── build/          # 生成的 SQLite（不入库）
├── presentation/       # 项目答辩 PPT、截图与讲解稿
├── PROJECT_SPEC.md     # 产品与技术规格（唯一事实来源）
└── DEVELOPMENT_PLAN.md # 阶段计划与验收
```

---

## 四、快速开始

### 1. 环境要求

- Windows 10/11（其他系统亦可，命令按对应 shell 调整）
- Python 3.13
- Node.js 20+

```powershell
# 在项目根目录创建虚拟环境
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
npm.cmd --prefix frontend install
```

### 2. 准备原始数据（必需）

本仓库**不包含** USDA 原始数据（ZIP 与 CSV 体积过大且不允许入库）。请自行从
[USDA FoodData Central](https://fdc.nal.usda.gov/download-datasets.html) 下载以下四个数据集的 CSV 包：

- Foundation Foods
- SR Legacy
- FNDDS / Survey Foods
- Branded Foods

将它们放在一个目录中，程序通过环境变量 `MEAL_CANVAS_DATA_DIR` 定位（默认回退到项目外的 `..\数据集`）：

```powershell
$env:MEAL_CANVAS_DATA_DIR = "D:\usda\fooddata"
```

> 路径失效时 ETL 会直接以中文错误中止，不会静默跳过。

### 3. 构建数据库

ETL **必须显式指定模式**，缺失则拒绝执行：

```powershell
# 样例库：只取少量记录，输出到 data/build/sample/（与正式库物理隔离）
.\.venv\Scripts\python.exe -m backend.app.etl.build --mode sample --library default

# 正式库：全量导入，必须额外确认，且不会覆盖已存在的正式库
.\.venv\Scripts\python.exe -m backend.app.etl.build --mode full --library default --confirm-full

# 品牌库单独构建（前端不展示）
.\.venv\Scripts\python.exe -m backend.app.etl.build --mode full --library branded --confirm-full
```

构建完成后会生成校验报告（导入计数、缺失率、冲突数、中文映射分布等）。

### 4. 启动后端

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.api.main:app --host 127.0.0.1 --port 8000
```

- 健康检查：<http://127.0.0.1:8000/api/health>（返回当前数据库路径与食品总数）
- 接口文档：<http://127.0.0.1:8000/docs>

### 5. 启动前端

```powershell
npm.cmd --prefix frontend run dev
```

浏览器打开 <http://localhost:5173>。开发服务器会把 `/api/*` 代理到 `127.0.0.1:8000`。

---

## 五、常用命令

| 用途 | 命令 |
| --- | --- |
| 后端测试 | `.\.venv\Scripts\python.exe -m pytest backend\tests -q` |
| 后端静态检查 | `.\.venv\Scripts\python.exe -m ruff check backend` |
| 前端类型检查 | `npm.cmd --prefix frontend run typecheck` |
| 前端 Lint | `npm.cmd --prefix frontend run lint` |
| 前端单元测试 | `npm.cmd --prefix frontend run test` |
| 前端生产构建 | `npm.cmd --prefix frontend run build` |

---

## 六、环境变量

| 变量 | 作用 | 默认值 |
| --- | --- | --- |
| `MEAL_CANVAS_DATA_DIR` | USDA 原始数据目录 | `..\数据集` |
| `MEAL_CANVAS_DB_PATH` | 默认食材库路径 | `data/build/meal_canvas.sqlite` |
| `MEAL_CANVAS_BRANDED_DB_PATH` | 品牌库路径 | `data/build/meal_canvas_branded.sqlite` |
| `MEAL_CANVAS_SAMPLE_DIR` | 样例库输出目录 | `data/build/sample` |
| `MEAL_CANVAS_PLANNER_DB_PATH` | 每周计划库路径（唯一可写库） | `data/build/meal_canvas_planner.sqlite` |
| `MEAL_CANVAS_HOST` / `MEAL_CANVAS_PORT` | 服务监听地址 | `127.0.0.1` / `8000` |
| `MEAL_CANVAS_CORS` | 允许的跨域来源（逗号分隔） | `http://localhost:5173` |
| `VITE_API_BASE_URL` | 前端 API 基地址（留空走同源代理） | 空 |

---

## 七、数据说明

| 数据集 | 记录数 | 在项目中的角色 |
| --- | ---: | --- |
| Foundation Foods | 469 | 实验分析级基础食材，营养最完整 |
| SR Legacy | 7,793 | 经典通用食材 |
| FNDDS（膳食调查食品） | 5,432 | 组合食品，单独标记，不与基础食材混类 |
| Branded（品牌商品） | 1,999,950 | 独立品牌库，前端不开放 |

默认食材库合计 **13,694 种食品 / 425,557 条营养行**。

数据完整性约定：

- 「营养值缺失」= 数据库无行 + API `null` + 界面「—」，**禁止写 0**
- 不做插值、不按同类均值填充、不修改 USDA 原始 CSV
- 中文名在独立的 `data/curation/` 映射层维护，三级状态（已核验 / 词典译名 / 暂无中文名）在界面可区分
- 餐盘计算返回每种营养素的**克重覆盖率**与缺失食材清单

---

## 八、测试与构建状态

| 检查 | 结果 |
| --- | --- |
| 后端 pytest | 160 passed |
| 前端 vitest | 45 passed |
| TypeScript `tsc -b` | 通过 |
| ESLint | 0 错误 0 警告 |
| 生产构建 | `vite build` 成功 |

---

## 九、已知限制

- 默认食材库的**联网营养补全尚未开启**（需配置 USDA FDC API Key），此时详情页不显示补全区。
- 品牌库补全为长期后台任务（Open Food Facts 限速约 2.5 秒/条），可断点续跑。
- 中文名覆盖率为 1,322 / 13,694，其余以英文原名展示并标注「暂无中文名」。
- 本工具只做营养信息展示与膳食记录，不提供疾病诊断、疗效或减重/增肌承诺。

---

## 十、更多文档

- [`PROJECT_SPEC.md`](PROJECT_SPEC.md) —— 产品与技术规格（唯一事实来源）
- [`DEVELOPMENT_PLAN.md`](DEVELOPMENT_PLAN.md) —— 阶段计划与验收标准
- [`data/reports/`](data/reports/) —— 建库审计、营养完整性、补全与周计划报告
- [`presentation/`](presentation/) —— 项目介绍 PPT、真实运行截图与答辩讲解稿
