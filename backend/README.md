# Meal Canvas 后端 API

只读 FastAPI 服务，查询 USDA FoodData Central 经过 ETL 标准化后的食品与营养数据。

> 不提供写入用户数据的接口。用户方案保存在浏览器 IndexedDB，偏好保存在 localStorage。

## 一、启动

```powershell
# 1. 进入项目根目录后激活虚拟环境（已创建）
# 所有命令都用 .venv 内解释器，避免 PowerShell 执行策略拦截

# 2. 启动 API（默认指向 sample 数据库 data/build/sample/meal_canvas.sqlite）
.\.venv\Scripts\python.exe -m uvicorn backend.app.api.main:app --host 127.0.0.1 --port 8000

# 3. 浏览器打开
#    http://127.0.0.1:8000/api/health          ← 健康检查
#    http://127.0.0.1:8000/docs                 ← Swagger UI（可选）
```

## 二、配置数据库路径

默认路径在 `backend/app/api/config.py` 的 `AppSettings` 里，环境变量可覆盖：

| 环境变量 | 含义 | 默认值 |
| --- | --- | --- |
| `MEAL_CANVAS_DB_PATH_API` | 默认食材库 SQLite 路径 | `data/build/sample/meal_canvas.sqlite` |
| `MEAL_CANVAS_BRANDED_DB_PATH_API` | 品牌库 SQLite 路径 | `data/build/sample/meal_canvas_branded.sqlite` |
| `MEAL_CANVAS_HOST` | 监听主机 | `127.0.0.1` |
| `MEAL_CANVAS_PORT` | 监听端口 | `8000` |
| `MEAL_CANVAS_CORS` | 允许的 CORS 来源（逗号分隔） | `http://localhost:5173` |

PowerShell 示例：

```powershell
$env:MEAL_CANVAS_DB = "C:\path\to\meal_canvas.sqlite"
.\.venv\Scripts\python.exe -m uvicorn backend.app.api.main:app --port 8000
```

## 三、接口列表

所有响应体都是中文错误消息，错误结构统一为 `{code, message, detail?}`。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 健康检查：数据库是否可用、食品数量、营养行数 |
| GET | `/api/foods` | 食品列表 + 搜索（中文/英文/别名 + 分类 + 数据源 + 分页 + 排序） |
| GET | `/api/foods/{food_key}` | 单条食品详情（fdc_id 或名称精确匹配） |
| GET | `/api/foods/{food_key}/nutrients` | 该食品的全部营养指标（含缺失状态） |
| GET | `/api/metadata/nutrients` | 营养指标定义表（37 个核心营养；两库共用同一份定义） |
| GET | `/api/metadata/categories` | 食品分类（**同时查询 default 库 + 品牌库**，去重合并后返回） |

### `/api/foods` 参数

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `q` | string | — | 搜索词（FTS5 自动中文单字分词 + LIKE 英文/别名） |
| `category_code` | string | — | 按 FDC/WWEIA category_code 筛选 |
| `data_type` | string | — | `foundation_food` / `sr_legacy_food` / `survey_fndds_food` / `branded_food` |
| `library_scope` | string | — | `default` / `branded` |
| `page` | int | 1 | 页码 |
| `page_size` | int | 20 | 每页数量，后端强制上限 100 |
| `sort` | string | `relevance` | `relevance`（verified 优先）/ `alpha_zh` / `alpha_en` |

### `/api/foods/{food_key}` 可选参数

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `library_scope` | string | — | `default` / `branded`。**不指定时先查 default 库、查不到再查 branded 库**；显式指定时只查对应库 |

### `/api/foods/{food_key}/nutrients` 可选参数

同上，`library_scope` 用来锁定查询的数据库。前端传详情页返回里的 `library_scope` 即可保证一致性。

### `/api/foods/{food_key}/nutrients` 返回字段

- `amount`: 每 100g 数值（`null` 表示**未知**，绝不用 `0` 代替）
- `raw_amount`: 原始 ETL 值
- `quality_flag`: `ok` / `negative`（不可用）/ `missing` / `unit_unknown` / `unmapped_nutrient`
- `is_available`: `quality_flag == 'ok'` **且** `amount` 非 null

## 四、API 快速验证

```powershell
# 健康检查 —— 确认真实数据库存在
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" | ConvertTo-Json

# 中文搜索"鸡蛋"（默认查 default 库）
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/foods?q=%E9%B8%A1%E8%9B%8B" | ConvertTo-Json

# 查询 Foundation Foods 总数
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/foods?data_type=foundation_food&page_size=1" | Select-Object total

# 单条详情（fdc_id=748967 是 Eggs, Grade A, Large，在 default 库）
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/foods/748967" | ConvertTo-Json -Depth 5

# 营养素元数据
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/metadata/nutrients" | Select-Object total

# --- 品牌库 ---
# 列出全部品牌商品（sample 349 条）
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/foods?library_scope=branded&page_size=100" | Select-Object total

# 品牌商品详情 —— fdc_id=1710667（STRAUS FAMILY CREAMERY, 0% FAT FREE MILK）
# 注意：品牌库没有 food_portion / food_alias / quality_event，这三个列表返回空数组 []
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/foods/1710667?library_scope=branded" | ConvertTo-Json -Depth 5

# 品牌商品营养素（同一个库）
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/foods/1710667/nutrients?library_scope=branded" | Select-Object total_nutrients_returned, missing_count
```

## 五、测试

```powershell
# 全部测试（ETL + API，49 个）
$env:PYTHONPATH="."
.\.venv\Scripts\python.exe -m pytest backend\tests -q

# 仅 API 测试
.\.venv\Scripts\python.exe -m pytest backend\tests\test_api.py -v

# 代码风格检查
.\.venv\Scripts\python.exe -m ruff check backend
```

所有 API 测试使用 **真实 sample 数据库** `data/build/sample/meal_canvas.sqlite`，不伪造食品数据。当前 sample 包含：

- 1,285 条食品（Foundation 469 + SR Legacy 315 + Survey FNDDS 501）
- 34,395 行营养数据
- 2,773 行份量

## 五、数据库双库结构

后端同时连接两个独立的 SQLite 文件，它们拥有**相同的 schema**（同一份 `schema.sql`），但表内数据量不同：

| 表 | default（meal_canvas.sqlite） | branded（meal_canvas_branded.sqlite） |
| --- | ---: | ---: |
| food | 1,285 | 349 |
| food_nutrient | 34,395 | 4,430 |
| food_summary | 1,283 | 321 |
| food_fts | 1,285 | 349 |
| food_portion | **2,773** | **0** |
| food_alias | **168** | **0** |
| quality_event | **338** | **0** |
| nutrient | 37 | 37 |

- 默认 API **不指定** `library_scope` 时：**只查 default 库**，不混入品牌商品
- 指定 `library_scope=branded` 时：切到品牌库，独立查询
- 品牌库缺失的表（food_portion / food_alias / quality_event）在该库始终返回空数组——**不伪造份量克重、不猜测别名**
- 详情和营养素接口会**在同一个库内**完成 food 查找 + 后续 portions/aliases/nutrients 查询，不会跨库
- `/api/metadata/categories` **同时查询两个库**，去重合并。当前 sample 返回 229 条分类：fdc 25 + wweia 101 + branded 103（品牌库分类因原始 Branded Foods 没有 category_code，全部 category_code 为 NULL，category_en/zh 为分类名）

## 六、数据库不可用时的行为

- **default 库不存在**：`GET /api/health` 返回 `status="degraded"`、`default_db_exists=false`、`error` 含中文说明；其他接口抛 `DatabaseUnavailableError` → 503
- **branded 库不存在但请求了 `library_scope=branded`**：抛 `DatabaseUnavailableError` → 503，中文错误 `"数据库不存在：..."`，**不会静默回退到 default 库**
- **配置缺失**（`set_db_paths` 未调用）：`default_db_path()` / `branded_db_path()` 直接抛异常

## 七、架构约束（硬性）

- SQLite 连接执行 `PRAGMA query_only=ON`，只允许 SELECT
- ETL 代码（`backend/app/etl/`）与 API 代码（`backend/app/api/`）严格分离；ETL 不得被请求路径导入
- 所有错误消息中文；响应体统一结构；数字格式化集中在 `lib/formatters.py`
- 能量按 `1008 → 2048 → 2047` 取一个值，kcal（1008）和 kJ（1062）不能混淆
- Branded Foods 独立库；默认 API **不混入**品牌商品；禁止为品牌商品伪造份量克重或把不同单位未经可靠转换就换算成克
