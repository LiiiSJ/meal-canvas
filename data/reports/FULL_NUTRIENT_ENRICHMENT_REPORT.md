# Meal Canvas 全库营养数据补全报告（FULL_NUTRIENT_ENRICHMENT_REPORT）

| 项目 | 内容 |
| --- | --- |
| 报告时间 | 2026-10-30 12:56（快照时点） |
| 检查范围 | 默认食材库 13,694 食品 + 独立品牌库 1,999,950 食品，nutrient 元数据表全部 **37 项营养素** |
| 补全来源 | Open Food Facts v2 API（GTIN/UPC 精确匹配，ODbL / CC-BY-SA） |
| 补全库存储 | `data/build/meal_canvas_enrichment.sqlite`（verified 与 candidate 严格分离） |
| 基线报告 | [NUTRIENT_COMPLETENESS_BEFORE.md](NUTRIENT_COMPLETENESS_BEFORE.md) |
| 缺失清单（补全前基线） | [NUTRIENT_MISSING_INVENTORY.csv](NUTRIENT_MISSING_INVENTORY.csv)（默认库 81,131 行）、[NUTRIENT_MISSING_INVENTORY_BRANDED.csv](NUTRIENT_MISSING_INVENTORY_BRANDED.csv)（品牌库 48,863,691 行） |
| 补全增量清单（本次交付） | [NUTRIENT_ENRICHMENT_FILLED.csv](NUTRIENT_ENRICHMENT_FILLED.csv)（7,862 行，快照时点） |

---

## 1. 执行摘要

- **已完成**：全库 37 项营养素完整性扫描与基线报告；本地数据核对（结论：本地 ETL 无丢数）；补全管线扩展至 37 键并全部通过测试；品牌库 OFF 批量补全已启动并持续后台运行，快照时点已补全 **7,862 个营养值、覆盖 599 个品牌食品**，全部经 GTIN 精确匹配（exact），本轮运行成功率 **87.2%**、错误 0；前端详情抽屉与餐盘计算已接入 verified 补全值。
- **未完成（如实说明）**：品牌库共 1,999,950 食品，快照时点已处理 704 个（约 0.035%），受 OFF 合规速率（2.5 秒/条）限制属长期后台任务，进度落盘可断点续跑（命令见 §8）；默认食材库补全因未配置 USDA FDC API Key 暂未执行（配置方法见 §9）。
- **已知限制**：OFF 只覆盖包装食品且营养素字段不如 USDA 完整，37 键中 26 键有补全记录，11 键（如维生素 B1/B2/B6/B12、叶酸、胆碱、IU 口径）OFF 基本不提供；IU↔µg 不做单位换算（口径不同），此类值只进 candidate 不进 verified，本次 candidate 数为 0。

## 2. 两库规模与补全前基线（实际扫描，非估计）

| 库 | 食品数 | 营养素格数（×37） | 缺失格数 | 覆盖率 |
| --- | ---: | ---: | ---: | ---: |
| 默认食材库（Foundation 469 + SR Legacy 7,793 + FNDDS 5,432） | 13,694 | 506,678 | 81,131 | **83.99%** |
| 品牌库（Branded） | 1,999,950 | 73,998,150 | 48,863,691 | **33.97%** |

- 默认库缺失集中在少数低覆盖营养素：维生素D-IU（38.29% 覆盖）、反式脂肪酸（31.32%）、氮（2.74%）、能量-kJ（57.89%）、维生素B5（47.15%）、维生素A-IU（53.72%）、灰分（59.98%）等；核心 7 项（能量/蛋白质/脂肪/碳水/纤维/总糖/钠）覆盖率均在 94%–99.7%。
- 品牌库缺失面更大：镁 3.04%、磷 3.08%、锌 2.55%、铜 1.19%、胆碱 0.06%、维生素E 0.1%、维生素K 0.8%、水分 0.16% 等；USDA 品牌数据本身只申报标签项。
- 品牌库无营养记录的食品 103,700 个，保持"未知"展示，不填 0。

## 3. 本地数据核对结论（第二步）

对原始 USDA ZIP 复核了 nutrient id↔nbr 映射、ETL 导入计数与单位口径：

- **本地修复量：0。** 默认库与品牌库的缺失均为 USDA 源数据真实未报告，非本地 ETL 丢失。
- 能量口径 1008→2048→2047 单值规则、FNDDS 传统编号映射、品牌库无 food_portion 等既有规则经抽查一致。
- 原始 ZIP 未做任何修改（只读）。

## 4. 联网检索与补全结果（第三步，真实数字）

### 4.1 来源与身份匹配

- 使用来源：仅 **Open Food Facts**（USDA FDC API 因无 Key 未启用，见 §9）。
- 身份匹配：全部 598 条来源记录均为 **GTIN/UPC 精确匹配（match_level=exact）**，名称搜索在批量模式下整体关闭（`allow_name_search=False`），无误配风险；GTIN 比较已做去前导零归一。
- 单位与基准：统一换算为每 100g；OFF 字段名自带单位的能量（energy-kcal/energy-kj）直接采纳；无单位标注的微量营养素不假设单位、不进 verified；钠≠食盐（salt 字段不映射）；ml 份量拒绝换算；真实 0 值保留。

### 4.2 补全量（快照时点 2026-10-30 12:56）

| 指标 | 数值 |
| --- | ---: |
| verified 补全值总数 | **7,862**（另有 4 条为快照查询间竞态新增） |
| 覆盖品牌食品数 | **599** |
| 待审核 candidate | 0 |
| 有补全的营养素键 | 26 / 37 |
| 累计尝试食品数 | 704（attempt 记录 751 条） |

补全值按营养素分布（前 15）：能量-kcal 597、脂肪 595、碳水 594、蛋白质 593、能量-kJ 589、钠 583、总糖 550、饱和脂肪 486、纤维 410、胆固醇 402、反式脂肪 388、维生素C 379、铁 379、钙 366、维生素A-RAE 355；另有钾 90、多不饱和脂肪 75、单不饱和脂肪 75、磷 56、锌 55、镁 54、维生素E 49、铜 49、维生素K 48、维生素B3 31、维生素B5 18。

### 4.3 真实成功率与失败分布

| 口径 | enriched | partial | not_found | error | 成功率 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 本轮运行（11:48 重启后，progress 计数） | — | 526 | 77 | **0** | **87.2%**（603 扫描中 526 获得补全） |
| 累计（含试点与被中止的首轮） | 8 | 590 | 104 | 49 | 85.1%（704 食品中 599 获得补全） |

- 49 条 error **全部发生在首轮**（OFF 阵发 429，当时 Retry-After 上限仅 5s）。修复为尊重服务端 Retry-After（上限 60s）并把间隔提至 2.5s 后，本轮 **0 错误**。error 记录 TTL 10 分钟，相关食品已被后续运行自动重试覆盖。
- not_found = GTIN 在 OFF 无记录（品牌库中为正常情形），负缓存 24h 内不重查。

### 4.4 补全前后对比

| 库 | 缺失格数（前） | 本次补全 | 缺失格数（快照时点） | 覆盖率变化 |
| --- | ---: | ---: | ---: | --- |
| 默认食材库 | 81,131 | 0（未启用 FDC，见 §9） | 81,131 | 83.99%（不变） |
| 品牌库 | 48,863,691 | 7,862 | 48,855,829 | 33.97% → 33.98%（+0.01pp） |

品牌库总量 200 万食品，本次为长期后台任务的**首个快照**，已完成数与剩余数如实列出，不做"全部补齐"的虚假宣称。

## 5. 存储与契约

- 补全值仅写入 `data/build/meal_canvas_enrichment.sqlite`（enrich_source / enrich_value / enrich_attempt 三表），`status='verified_external'` 与 `candidate_review` 严格分离；USDA 原值与真实 0 从不覆盖；缺失依旧表示为"无行 / null / —"。
- API `GET /api/foods/{fdc_id}/enrichment/resolved` 固定返回 37 键 values，每项附 `nutrient_id / name_zh / unit_zh / decimals` 中文元数据。
- 补全增量清单 `NUTRIENT_ENRICHMENT_FILLED.csv`（7,862 行）含 fdc_id、nutrient_key、每 100g 值、原始值/单位/基准、换算方式、来源链接、match_level、检索时间，供人工抽查追溯。补全前的 49M 行基线清单为补全前状态，二者配合即"更新后的缺失清单"口径。

## 6. 前端验收（已实际运行）

- 详情抽屉：USDA 缺失行由 verified 外部值补位渲染（外部徽章 + 来源链接 + 中文营养素名/单位）；USDA 完全无记录的营养素作为追加行展示；展开按钮与"外部补全 N 项"计数正确。
- 餐盘计算 / 营养贡献分析：`mergeEnrichment` 仅采纳 `origin=external && status=verified_external` 值合并进 7 个核心键，覆盖率口径不变。
- E2E 实测：品牌食品 fdc 2517880 返回 37 values + 7 条 OFF verified 值带中文元数据与来源链接；默认库 fdc 167512 返回 37 values、14 项 USDA 值元数据正确（energy_kj 独立键）、缺失项保持 none。
- 验证命令真实结果：`npm.cmd --prefix frontend run typecheck` ✓、`eslint` ✓、`vitest` **27 passed** ✓、生产构建 ✓。

## 7. 测试与代码质量（真实结果）

- `.\.venv\Scripts\python.exe -m pytest backend\tests -q` → **134 passed**（含新增 test_enrichment_mapper.py 16 项：37 键一致性、单位换算、IU 不换算、能量单值、serving(ml) 拒绝、真实 0 保留等）。
- `ruff check` → All checks passed（providers/base.py、config.py、openfoodfacts.py、scripts/enrichment_batch.py）。
- PROJECT_SPEC.md §3.9 / §6.6 已同步 37 键口径、批量补全段与响应示例。

## 8. 未完成工作与断点续跑

| 未完成项 | 原因 | 续跑方式 |
| --- | --- | --- |
| 品牌库剩余 ~1,999,246 个食品未处理 | OFF 合规速率 2.5s/条，属长期后台任务；当前 `--max-foods 10000` 仍在后台运行 | 任务结束或中断后执行：`.\.venv\Scripts\python.exe scripts\enrichment_batch.py --library branded --max-foods 0 --batch-size 200 --off-interval 2.5`（自动从 `data/build/enrichment_batch_progress_branded.json` 游标续跑，负缓存自动跳过已处理） |
| 默认食材库 81,131 个缺失格 | 未配置 USDA FDC API Key（用户决策：先只做 OFF 部分） | 配置 Key（见 §9）后：`.\.venv\Scripts\python.exe scripts\enrichment_batch.py --library default --max-foods 0 --batch-size 200` |

## 9. USDA FDC API Key 配置指引

1. 在 https://fdc.nal.usda.gov/api-key-signup 免费申请 API Key。
2. 设置环境变量后重启后端 / 批量脚本：

```powershell
$env:MEAL_CANVAS_FDC_API_KEY = "你的KEY"
.\.venv\Scripts\python.exe -m uvicorn backend.app.api.main:app --port 8000
```

3. FDC 来源启用后，单食品补全与批量脚本会自动优先走 FDC（FDC ID 精确匹配），OFF 作为品牌食品补充。

## 10. 合规与诚实声明

- 所有数字来自实际扫描与运行日志（`data/build/nutrient_stats_before.json`、enrichment SQLite、批量进度 JSON），无编造。
- 未降低自动接受标准换取数量：仅 exact 匹配进 verified；无可确认身份或单位的值一律不进 verified。
- 未填 0、未插值、未合并能量口径、未把盐当钠、未换算 IU。
- OFF 限流要求已遵守（2.5s 间隔、Retry-After 尊重、负缓存去重、有限重试、连续错误退避）。
- 品牌库与默认库物理隔离，未混合；原始 ZIP 只读未动。
