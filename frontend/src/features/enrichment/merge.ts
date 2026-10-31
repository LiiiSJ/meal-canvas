/**
 * 外部补全值与 USDA 原始摘要的合并（纯函数，不触碰 query 缓存对象）。
 *
 * 合并规则（与任务书一致）：
 * - 只采纳 origin === 'external' 且 status === 'verified_external' 的值；
 *   候选（candidate_review）与被拒（rejected）值一律不进入计算。
 * - 只填充 summary 中缺失（null/undefined）的键；USDA 已有有效值与真实 0 永不覆盖。
 * - 数值必须是有限非负数；NaN / Infinity / 负数视为不可用。
 * - known_core_count 按填充数递增（7 个 summary 键均为 is_core）。
 */

import type { EnrichedValuesResponse, FoodDetail, FoodSummary } from '@/lib/types'

const SUMMARY_KEYS = [
  'energy_kcal',
  'protein_g',
  'fat_g',
  'carb_g',
  'fiber_g',
  'sugar_g',
  'sodium_mg',
] as const

type SummaryKey = (typeof SUMMARY_KEYS)[number]

/** summary 中缺失的核心键（null / undefined 视为缺失；真实 0 不算缺失）。 */
export function missingSummaryKeys(summary: FoodSummary): string[] {
  return SUMMARY_KEYS.filter((key) => summary[key] === null || summary[key] === undefined)
}

export interface EnrichmentMergeResult {
  /** 合并后的 FoodDetail 副本；没有可采纳的外部值时原样返回。 */
  detail: FoodDetail
  /** 由外部补全填充的 summary 键（用于界面标注来源）。 */
  filledKeys: string[]
}

function isUsableExternalValue(value: number | null): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0
}

/** 把外部补全解析结果合并进 FoodDetail，返回新对象（不修改入参）。 */
export function mergeEnrichment(
  original: FoodDetail,
  response: EnrichedValuesResponse,
): EnrichmentMergeResult {
  const filled: Partial<Record<SummaryKey, number>> = {}

  for (const item of response.values) {
    if (item.origin !== 'external' || item.status !== 'verified_external') continue
    if (!(SUMMARY_KEYS as readonly string[]).includes(item.key)) continue
    const key = item.key as SummaryKey
    const current = original.summary_per_100g[key]
    if (current !== null && current !== undefined) continue
    if (!isUsableExternalValue(item.value)) continue
    filled[key] = item.value
  }

  const filledKeys = SUMMARY_KEYS.filter((key) => key in filled)
  if (filledKeys.length === 0) return { detail: original, filledKeys: [] }

  const summary: FoodSummary = {
    ...original.summary_per_100g,
    ...(filled as Partial<FoodSummary>),
    known_core_count: original.summary_per_100g.known_core_count + filledKeys.length,
  }
  return { detail: { ...original, summary_per_100g: summary }, filledKeys }
}

/** 从解析结果中取某个键的外部值（用于界面展示来源信息）。 */
export function externalValueFor(
  response: EnrichedValuesResponse,
  key: string,
): EnrichedValuesResponse['values'][number] | null {
  const item = response.values.find(
    (v) => v.key === key && v.origin === 'external' && v.status === 'verified_external',
  )
  return item ?? null
}
