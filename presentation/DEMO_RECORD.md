# Meal Canvas 演示记录（DEMO_RECORD）

记录本次 PPT 制作过程中每一项功能的真实运行测试。所有操作均在 2026-10-31 本机完成。

## 运行环境

| 项 | 值 |
| --- | --- |
| 后端 | `.\.venv\Scripts\python.exe -m uvicorn backend.app.api.main:app --port 8000` |
| 前端 | `npm.cmd --prefix frontend run dev`（http://localhost:5173） |
| 默认食材库 | `data/build/meal_canvas.sqlite`，13,694 食品 / 425,557 营养行（`/api/health` 实时返回） |
| 品牌库 | `data/build/meal_canvas_branded.sqlite`，1,999,950 条 |
| 浏览器自动化 | Playwright（Python）+ 系统 Chrome，视口 1600×900 @2x |
| 演示数据 | 每周计划演示前重置了 `meal_canvas_planner.sqlite`，其余为正式库数据 |

## 功能演示结果

| # | 功能 | 操作步骤 | 路由 | 结果 | 截图 |
| --- | --- | --- | --- | --- | --- |
| 1 | 食材库搜索 | 首页搜索框输入「鸡蛋」 | `/` | 成功，17 条结果，首条为「A级大鸡蛋（全蛋）」 | 01_food_search.png |
| 2 | 食品详情 | 点击首条结果卡片 | `/` | 成功，抽屉显示 FDC ID 748967、Foundation Foods、数据集版本 2026-04 | 02_food_detail.png |
| 2b | 营养列表 | 抽屉内滚动到「核心营养」 | `/` | 成功，能量/蛋白质/矿物质/维生素逐项显示 | 02b_food_detail_nutrients.png |
| 3 | 餐盘设计 | 依次加入 鸡蛋/鸡胸肉/米饭 各 100g | `/` | 成功，本餐营养 444 kcal、蛋白质 47.2 g | 03_meal_plate.png |
| 4 | 调整克数 | 鸡蛋克数改为 200 并失焦 | `/` | 成功，合计实时变为 592 kcal（补拍时验证：克数为失焦提交，首轮截图未触发提交已重拍） | 04_plate_nutrition.png |
| 5 | 营养贡献分析 | 进入营养分析页，选「蛋白质」 | `/analysis` | 成功，鸡胸肉 32.1 g vs 鸡蛋 12.4 g 条形图 | 05_nutrient_contribution.png |
| 6 | 方案对比 | 餐盘存为方案 A（蛋 200g+鸡胸+米饭），改后存方案 B（蛋 100g+鸡胸），打开对比页 | `/compare` | 成功，差异表：能量 592→314 kcal（−47%）、蛋白质 −25%、脂肪 −44% | 06_meal_comparison.png |
| 7 | 食材探索 | 打开食材探索页 | `/explore` | 成功，三维散点 蛋白质×脂肪×碳水，88 个点、排除 12 条缺失 | 07_food_exploration.png |
| 8 | 每周计划·多选添加 | 周六早餐 → 添加食品 → 暂存 鸡蛋+牛奶 →「确认添加 2 种食品」→ 保存本周计划 | `/weekly` | 成功，保存后状态「已保存」 | 08b_weekly_picker.png、08_weekly_plan.png |
| 9 | 今日餐单 | 打开今日餐单 | `/today` | 成功，显示 10 月 31 日（周六）早餐与全天合计 191 kcal | 09_today_meal.png |
| 10 | 外部补全 | 详情抽屉查找「营养补全」区 | `/` | 如实记录：默认库补全未开启（无 FDC API Key），抽屉无补全区，故无此功能界面截图 | （无，PPT 第 14 页如实说明） |
| 11 | 数据来源页 | 打开数据来源页 | `/about` | 成功 | 11_about.png |
| 12 | 持久化验证 | 每周计划页刷新浏览器 | `/weekly` | 成功，刷新后周六早餐（鸡蛋+牛奶）完整读回 | 12_weekly_after_reload.png |

## 质量验证（同一日真实运行）

| 检查 | 命令 | 结果 |
| --- | --- | --- |
| 后端测试 | `.\.venv\Scripts\python.exe -m pytest backend\tests` | 160 passed in 12.58s |
| 后端静态检查 | ruff（此前同一代码基线运行） | All checks passed |
| 前端类型检查 | `npm.cmd --prefix frontend run typecheck` | 通过 |
| 前端 Lint | `npm.cmd --prefix frontend run lint` | 0 错误 0 警告 |
| 前端测试 | `npm.cmd --prefix frontend run test` | 45 passed（4 个测试文件，6.78s） |
| 生产构建 | `npm.cmd --prefix frontend run build` | 成功（25.61s） |

## 过程中发现并处理的问题

1. **「样例库」标签误显示**：截图发现界面左下角始终显示「样例库」，实际连接的是全量正式库。定位为 `AppShell.tsx` 中健康标签无条件渲染，已修复为仅当数据库路径含 sample 时显示，typecheck 通过后重拍全部截图。
2. **克数失焦提交**：首轮截图 04 中输入框已显示 200 但营养合计未变（输入在失焦时才提交），已按真实交互补拍，并确认能量 592 kcal 与方案对比页数字一致。
3. **导航链接重名**：「今日餐单」在导航与页面内各有一个链接，自动化脚本改为精确匹配。
