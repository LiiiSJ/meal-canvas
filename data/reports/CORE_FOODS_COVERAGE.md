# 核心食材覆盖报告

生成时间：2026-10-23 · 范围：sample 数据库（`data/build/sample/meal_canvas.sqlite`）
数据来源：USDA FoodData Central Foundation / SR Legacy / FNDDS 原始 ZIP，**未执行 full 模式，未覆盖正式数据库**。
核验规则：从 `food_zh.csv`（人工核验 249 条）中精确匹配 `fdc_id`，前缀对原始英文 `description` 匹配。单一食材优先，排除混合菜品、品牌食品代用品。

---

## 一、总览

| 数据源 | 食品数 | zh_verified | zh_glossary | zh_none |
| --- | ---: | ---: | ---: | ---: |
| Foundation Foods（全量 469） | 469 | — | — | — |
| SR Legacy（分层抽样 + 强制加入） | 315 | — | — | — |
| FNDDS（分层抽样 + 强制加入） | 501 | — | — | — |
| **合计** | **1285** | **249** | **621** | **415** |

强制加入机制：`backend/app/etl/sample_manifest.py` 中 `SR_FORCED_IDS`（16 条核心食材，含 1 条白米已在分层抽样中命中，净加 15 条），在 SR Legacy 原分层抽样 300 条基础上去重追加，**不破坏原有分层覆盖**。Survey 原有 `SURVEY_FORCED_IDS = (2705383,)` 不变。

---

## 二、逐目标食材覆盖情况

### 目标 1：米饭

Foundation 469 条里只有**干燥生米**，没有煮熟形态；煮熟形态全部在 SR Legacy。两者共同覆盖单一食材场景。

| fdc_id | 英文原名 | 中文名 | 数据源 | 形态 | 核验 | 入库 | 备注 |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 2512381 | Rice, white, long grain, unenriched, raw | 白米（长粒，生） | Foundation | 干燥（未强化） | verified | ✓ | 全量 469 已含 |
| 2512380 | Rice, brown, long grain, unenriched, raw | 糙米（长粒，生） | Foundation | 干燥（未强化） | verified | ✓ | 全量 469 已含 |
| 2710825 | Rice, black, unenriched, raw | 黑米（生） | Foundation | 干燥 | verified | ✓ | 全量 469 已含 |
| 168877 | Rice, white, long-grain, regular, raw, enriched | 白米（长粒，生，强化） | SR Legacy | 干燥（强化） | verified | ✓ | 强制加入 |
| 168878 | Rice, white, long-grain, regular, enriched, cooked | 白米饭（长粒，熟，强化） | SR Legacy | 煮熟（强化） | verified | ✓ | 强制加入 |
| 168875 | Rice, brown, medium-grain, cooked | 糙米饭（中粒，熟） | SR Legacy | 煮熟 | verified | ✓ | 强制加入 |
| 168935 | Rice, white, long-grain, regular, cooked, unenriched, with salt | 白米饭（长粒，熟，未强化，带盐） | SR Legacy | 煮熟（未强化，带盐） | verified | ✓ | 强制加入 |

**未纳入理由**：Foundation 里没有煮熟米饭形态的 `foundation_food` 记录（Foundation 469 条以基础食材形态为主），全部煮熟形态统一来自 SR Legacy。

---

### 目标 2：土豆

Foundation 里只有**生土豆**（带皮/不带皮多个品种），煮熟形态全部在 SR Legacy。红薯单独归类但一并列出。

| fdc_id | 英文原名 | 中文名 | 数据源 | 形态 | 核验 | 入库 | 备注 |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 2346401 | Potatoes, russet, without skin, raw | 褐皮马铃薯（去皮，生） | Foundation | 生（去皮） | verified | ✓ | 全量 469 已含 |
| 2346402 | Potatoes, red, without skin, raw | 红土豆（去皮，生） | Foundation | 生（去皮） | verified | ✓ | 全量 469 已含（本次新增核验） |
| 2346403 | Potatoes, gold, without skin, raw | 金土豆（去皮，生） | Foundation | 生（去皮） | verified | ✓ | 全量 469 已含（本次新增核验） |
| 170028 | Potatoes, white, flesh and skin, raw | 白土豆（带皮带肉，生） | SR Legacy | 生 | verified | ✓ | 强制加入 |
| 170033 | Potatoes, baked, flesh, without salt | 烤土豆（纯肉，无盐） | SR Legacy | 烤熟（纯肉，无盐） | verified | ✓ | 强制加入 |
| 170093 | Potatoes, baked, flesh and skin, without salt | 烤土豆（带皮带肉，无盐） | SR Legacy | 烤熟（带皮带肉，无盐） | verified | ✓ | 强制加入 |
| 170440 | Potatoes, boiled, cooked without skin, flesh, without salt | 煮土豆（去皮纯肉，无盐） | SR Legacy | 煮熟（去皮纯肉，无盐） | verified | ✓ | 强制加入 |
| 168482 | Sweet potato, raw, unprepared | 红薯（生，未加工） | SR Legacy | 生 | verified | ✓ | 强制加入 |
| 168483 | Sweet potato, cooked, baked in skin, flesh, without salt | 烤红薯（纯肉，无盐） | SR Legacy | 烤熟（纯肉，无盐） | verified | ✓ | 强制加入 |
| 168484 | Sweet potato, cooked, boiled, without skin | 煮红薯（去皮纯肉） | SR Legacy | 煮熟（去皮纯肉） | verified | ✓ | 强制加入 |

**未纳入理由**：Foundation 里没有普通白土豆的煮熟形态（烤/煮）记录——Foundation 469 条里的土豆全部是生的、按品种分。煮熟形态统一来自 SR Legacy 的 `sr_legacy_food` 记录（非 brand、非混合品）。

---

### 目标 3：燕麦

Foundation 469 条里同时有**传统压片燕麦**和**钢切燕麦**——干燥形态都在 Foundation。没有用燕麦奶或其他代用品。

| fdc_id | 英文原名 | 中文名 | 数据源 | 形态 | 核验 | 入库 | 备注 |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 2346396 | Oats, whole grain, rolled, old fashioned | 燕麦片（传统压片） | Foundation | 干燥（全谷物） | verified | ✓ | 全量 469 已含 |
| 2346397 | Oats, whole grain, steel cut | 钢切燕麦 | Foundation | 干燥 | verified | ✓ | 全量 469 已含 |

**已排除**：Foundation 2257046 "Oat milk, unsweetened, plain, refrigerated" 是燕麦奶（饮品），不是燕麦本身，**不纳入**。

---

### 目标 4：豆腐

Foundation 469 条里**没有任何豆腐记录**，全部豆腐单一食品在 SR Legacy 的 `sr_legacy_food` 里（非 branded_food）。

| fdc_id | 英文原名 | 中文名 | 数据源 | 形态 | 核验 | 入库 | 备注 |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 172475 | Tofu, raw, firm, prepared with calcium sulfate | 豆腐（硬，生） | SR Legacy | 生（凝固） | verified | ✓ | 强制加入 |
| 172476 | Tofu, raw, regular, prepared with calcium sulfate | 豆腐（常规，生） | SR Legacy | 生（凝固） | verified | ✓ | 强制加入 |
| 172449 | Tofu, soft, prepared with calcium sulfate and magnesium chloride (nigari) | 豆腐（软，凝固） | SR Legacy | 凝固 | verified | ✓ | 强制加入 |
| 172451 | Tofu, fried | 炸豆腐 | SR Legacy | 油炸 | verified | ✓ | 强制加入 |

**已排除**：branded_food 里的 MORI-NU / Vitasoy / Nasoya 等品牌豆腐（独立 branded 库处理，不在默认食材库）；Survey 里的 "Tofu and vegetables including carrots, broccoli..." 混合菜品（混合菜，不是单一豆腐）。

---

### 目标 5：鸡蛋

Foundation 469 条里同时有生/干燥多种形态。

| fdc_id | 英文原名 | 中文名 | 数据源 | 形态 | 核验 | 入库 | 备注 |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 748967 | Eggs, Grade A, Large, egg whole | A级大鸡蛋（全蛋） | Foundation | 生 | verified | ✓ | 全量 469 已含 |
| 323604 | Egg, whole, raw, frozen, pasteurized | 全蛋（生，冷冻巴氏杀菌） | Foundation | 生（冷冻） | — | ✓ | glossary（词典匹配） |
| 747997 | Eggs, Grade A, Large, egg white | A级大鸡蛋（蛋清） | Foundation | 生 | verified | ✓ | 全量 469 已含 |
| 329490 | Egg, whole, dried | 干燥全蛋（全蛋粉） | Foundation | 干燥 | verified | ✓ | 全量 469 已含 |

---

### 目标 6：牛奶

Foundation 469 条里同时有多种脂肪含量的液态奶。

| fdc_id | 英文原名 | 中文名 | 数据源 | 形态 | 核验 | 入库 | 备注 |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 746778 | Milk, reduced fat, fluid, 2% milkfat | 低脂牛奶（2%乳脂） | Foundation | 液态 | verified | ✓ | 全量 469 已含 |
| 746782 | Milk, whole | 全脂牛奶 | Foundation | 液态 | verified | ✓ | 全量 469 已含 |
| 746776 | Milk, nonfat | 脱脂牛奶 | Foundation | 液态 | verified | ✓ | 全量 469 已含 |

---

### 目标 7：鸡胸肉

Foundation 469 条里同时有熟态和生态形态。

| fdc_id | 英文原名 | 中文名 | 数据源 | 形态 | 核验 | 入库 | 备注 |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 331960 | Chicken, broiler or fryers, breast, skinless, boneless, meat only, cooked, braised | 鸡胸肉（去皮去骨，焖煮） | Foundation | 熟 | verified | ✓ | 全量 469 已含 |
| 2646170 | Chicken, breast, boneless, skinless, raw | 鸡胸肉（去皮去骨，生） | Foundation | 生 | verified | ✓ | 全量 469 已含 |

---

### 目标 8：香蕉

Foundation 469 条里同时有熟态和过熟形态。

| fdc_id | 英文原名 | 中文名 | 数据源 | 形态 | 核验 | 入库 | 备注 |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 790991 | Bananas, ripe and slightly ripe, raw | 香蕉（熟） | Foundation | 生 | verified | ✓ | 全量 469 已含 |
| 790774 | Bananas, overripe, raw | 香蕉（过熟） | Foundation | 生 | — | ✓ | glossary（词典匹配） |

---

### 目标 9：苹果

Foundation 469 条里同时有多个品种。

| fdc_id | 英文原名 | 中文名 | 数据源 | 形态 | 核验 | 入库 | 备注 |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1105430 | Apples, red delicious, with skin, raw | 红元帅苹果（带皮，生） | Foundation | 生 | verified | ✓ | 全量 469 已含 |
| 1105547 | Apples, honeycrisp, with skin, raw | 蜜脆苹果（带皮，生） | Foundation | 生 | verified | ✓ | 全量 469 已含 |
| 1105664 | Apples, granny smith, with skin, raw | 青苹果（带皮，生） | Foundation | 生 | verified | ✓ | 全量 469 已含 |

---

### 目标 10：西兰花

Foundation 469 条里只有**生**形态。煮熟形态在 SR Legacy，未强制加入（本次目标是单一食材基础形态覆盖）。

| fdc_id | 英文原名 | 中文名 | 数据源 | 形态 | 核验 | 入库 | 备注 |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 747447 | Broccoli, raw | 西兰花（生） | Foundation | 生 | verified | ✓ | 全量 469 已含 |

---

## 三、核心结论

1. **Foundation 469 条 + SR Legacy 强制加入 15 条 = 核心食材全部覆盖**。用户关心的 10 种目标食材（米饭/土豆/燕麦/豆腐/鸡蛋/牛奶/鸡胸肉/香蕉/苹果/西兰花）均在 sample 数据库中，且每种至少一个形态有 verified 中文名。
2. **生熟形态区分**：米饭、土豆、红薯、鸡胸肉同时有生态和熟态的真实单一食品记录，燕麦只有干燥形态（Foundation 469），西兰花只有生形态（Foundation 469）。煮熟米饭/土豆/红薯全部来自 SR Legacy 的 `sr_legacy_food`，**不加入 foundation_food（Foundation 原始定义没有煮熟食材）**。
3. **豆腐独立来源**：Foundation 469 条里**没有任何豆腐记录**，全部豆腐形态（硬生/常规生/软凝固/油炸）来自 SR Legacy 的 `sr_legacy_food`，**不是 branded_food**。
4. **未纳入**：燕麦奶（Foundation 2257046 是饮品）、品牌豆腐商品（branded 库）、Survey 里的 tofu 混合菜、炸薯条/薯片。这些都不是单一食材或不符合目标范围。

---

## 四、验证状态

| 项目 | 结果 | 说明 |
| --- | --- | --- |
| `pytest backend/tests -q` | 32 passed | 涵盖 manifest 抽样、build 合成、zh_overlay、nutrients、validate 对账 |
| `ruff check backend` | All checks passed | 无 lint 问题 |
| `python -m backend.app.etl.validate` | 32 项全部通过 | 含对账、覆盖率、孤儿/重复、质量事件、黄金能量样本 |
| Foundation energy_collapsed = 416 | 未变 | 450 差额 = 416 + 33 + 1 完全成立，**未被破坏** |
| formal 数据库覆盖 | 未覆盖 | `data/build/meal_canvas.sqlite` 不存在 |
| full 模式 | 未执行 | 本次仅 sample |
| zh_verified 总数 | **249** | 原有 232 + 本次新增 17 条 |
| SR Legacy 强制加入实际命中 | **15 条** | manifest 16 条中 1 条已在分层抽样中 |
