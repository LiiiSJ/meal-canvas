# Meal Canvas 项目介绍 PPT · 制作报告

## 交付物

| 文件 | 说明 |
| --- | --- |
| `presentation/Meal_Canvas_Project_Introduction.pptx` | 正式 PPT，20 页，16:9，每页含演讲者备注 |
| `presentation/assets/screenshots/` | 13 张真实运行截图（3200×1800 PNG） |
| `presentation/Meal_Canvas_Presentation_Script.md` | 逐页中文讲解稿 + 提问预案 |
| `presentation/DEMO_RECORD.md` | 功能演示与质量验证的真实运行记录 |
| `presentation/PPT_PRODUCTION_REPORT.md` | 本报告 |

## 页面结构（20 页）

1. 封面（作者信息留空待填）
2. 项目是什么（五步流程 + 三条设计原则）
3. 背景与痛点（6 条，全部生活场景，无市场规模杜撰数据）
4. 目标用户（4 类，含边界声明）
5. 已实现功能地图（8 模块，以运行代码为准）
6. 食品数据库与搜索 — 截图 01
7. 食品营养详情 — 截图 02b
8. 互动餐盘设计 — 截图 03、04
9. 营养素贡献分析 — 截图 05
10. 方案对比 — 截图 06
11. 食材探索（3D 散点）— 截图 07
12. 每周膳食计划 — 截图 08b、08
13. 今日餐单与持久化 — 截图 09、12
14. 外部营养补全（无界面截图，如实说明原因）
15. 完整使用场景串联（5 张分镜截图）
16. 技术架构（形状绘制架构图）
17. 数据来源与处理（真实记录数表格）
18. 技术难点（问题→方法→效果 ×5）
19. 测试与成果（真实运行数字）
20. 总结与未来展望（含结束页）

## 截图清单（13 张，全部来自真实运行）

01_food_search / 02_food_detail / 02b_food_detail_nutrients / 03_meal_plate / 04_plate_nutrition / 05_nutrient_contribution / 06_meal_comparison / 07_food_exploration / 08_weekly_plan / 08b_weekly_picker / 09_today_meal / 11_about / 12_weekly_after_reload

- 获取方式：Playwright + 系统 Chrome 实际操作 localhost:5173，视口 1600×900、2 倍缩放。
- 数据为全量正式库（13,694 食品），非 sample 样例库。
- 截图中的数字已与多处交叉核对一致（例如 592 kcal 同时出现在餐盘页与方案对比页）。

## 数据来源（PPT 中所有数字的出处）

| 数字 | 出处 |
| --- | --- |
| 13,694 / 425,557 | `/api/health` 实时返回（2026-10-31） |
| 469 / 7,793 / 5,432 / 1,999,950 | 直接查询两个 SQLite 库计数 |
| 249 / 1,073 / 12,372（中文映射） | 默认库 zh_status 分组计数 |
| 7,862 / 599 / 87.2%（外部补全） | `data/reports/FULL_NUTRIENT_ENRICHMENT_REPORT.md`（2026-10-30 快照） |
| 160 / 45 / 0 / 构建成功 | 2026-10-31 本机真实运行 pytest / vitest / eslint / vite build |
| 37 项营养素键 | 补全报告与 API 契约 |

## PPT 生成方式

- python-pptx 1.0.2 脚本生成（脚本在临时目录，未入库）。
- 配色直接取自 `frontend/src/styles/tokens.css`（奶油底 #FFF8EE、绿 #638F68、橙 #F2A65A）。
- 字体统一微软雅黑；截图嵌入文件内部，非外部链接。
- 每页写入演讲者备注（Notes）。
- 视觉检查：经本机 PowerPoint COM 导出全部 20 页 PNG 逐页目检，修正两处后重新生成（第 8 页图注、第 15 页留白）。

## 无法截图 / 未展示的功能（如实声明）

- **默认库外部补全界面**：未配置 USDA FDC API Key，详情抽屉不显示补全区；第 14 页以文字+真实补全数据呈现，未伪造界面。
- **品牌商品库**：按项目约定前端不开放入口，PPT 仅在功能地图和数据页如实说明其存在与规模。
- **食材替换模拟器**：当前实现以「方案对比」承载替换前后的差异分析，独立替换页未实现，PPT 未单列。

## 制作过程中修复的产品问题

1. `AppShell.tsx` 健康标签「样例库」无条件显示 → 改为仅 sample 库显示（typecheck 通过，已重拍截图）。
2. 发现克数输入为失焦提交（首轮截图合计未更新属截图时序问题，非产品缺陷），已在 DEMO_RECORD 记录。

## 仍需人工补充的信息

- 封面与结束页的汇报人姓名、学号（PPT 中为下划线占位）。
- 如需更换演示日期或周计划内容，可重新运行截图流程（演示前重置 `data/build/meal_canvas_planner.sqlite` 即可）。

## 已知限制

- PPT 内字体依赖微软雅黑（Windows/Office 环境正常）；macOS 打开会自动回退，建议演讲前在目标机器打开确认。
- 截图为静态 PNG，3D 探索页的旋转交互需现场演示补充。
