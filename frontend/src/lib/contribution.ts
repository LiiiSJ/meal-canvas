/**
 * 营养来源贡献计算。
 *
 * 与 calculator.ts 同一套规则：实际贡献 = 每 100 克值 × 克重 ÷ 100；
 * null / 非有限数 / 负数视为缺失，不按 0 处理；真实 0 保留。
 */

import { isUsableNutrientValue, type CoreNutrientKey, type PlateEntry } from '@/lib/calculator'
import type { FoodSummary } from '@/lib/types'

export interface ContributionItem {
  entry: PlateEntry
  /** 该食材对所选营养指标的实际贡献量（单位与指标一致）。 */
  value: number
}

export interface ContributionResult {
  key: CoreNutrientKey
  /** 有有效数据的食材贡献，按贡献量从大到小排序。 */
  items: ContributionItem[]
  /** 缺少该营养数据的食材，不参与排序与占比。 */
  missing: PlateEntry[]
  /** 已知贡献之和；存在缺失时不应被宣称为完整总量。 */
  knownTotal: number
}

export function computeContributions(
  entries: PlateEntry[],
  summaries: Map<string, FoodSummary>,
  keyOf: (entry: PlateEntry) => string,
  key: CoreNutrientKey,
): ContributionResult {
  const items: ContributionItem[] = []
  const missing: PlateEntry[] = []
  let knownTotal = 0

  for (const entry of entries) {
    const summary = summaries.get(keyOf(entry))
    const value = summary?.[key]
    if (!isUsableNutrientValue(value)) {
      missing.push(entry)
      continue
    }
    const contribution = ((value as number) * entry.grams) / 100
    items.push({ entry, value: contribution })
    knownTotal += contribution
  }

  items.sort((a, b) => b.value - a.value)
  return { key, items, missing, knownTotal }
}
