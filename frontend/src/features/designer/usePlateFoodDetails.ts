import { useQueries } from '@tanstack/react-query'

import { mergeEnrichment, missingSummaryKeys } from '@/features/enrichment/merge'
import { getEnrichedNutrients, getFood } from '@/lib/api'
import { plateKey, type PlateEntry } from '@/lib/calculator'
import { queryKeys } from '@/lib/queries'
import type { FoodDetail } from '@/lib/types'

const FIVE_MINUTES = 5 * 60 * 1000

/**
 * 并发读取餐盘中所有食材的详情（含 summary_per_100g 与 portions）。
 * 复用已有 query 缓存，避免重复请求。
 *
 * 外部补全：详情加载后，对存在缺失核心营养的食材再发起补全查询
 * （后端负责缺失检测、联网检索与缓存；查询失败只影响补全，不影响原数据）。
 * 已核实的外部值合并进 FoodDetail 副本，立即参与餐盘营养计算。
 */
export function usePlateFoodDetails(plate: PlateEntry[]): {
  details: Map<string, FoodDetail>
  isLoading: boolean
  hasError: boolean
  /** 是否有食材正在联网补全缺失营养（不阻塞原数据展示）。 */
  isEnriching: boolean
} {
  const detailQueries = plate.map((entry) => ({
    queryKey: queryKeys.food(entry.food.fdc_id, entry.food.library_scope),
    queryFn: ({ signal }: { signal: AbortSignal }) =>
      getFood(entry.food.fdc_id, entry.food.library_scope, signal),
    staleTime: FIVE_MINUTES,
  }))

  const detailResults = useQueries({ queries: detailQueries })

  const rawDetails = new Map<string, FoodDetail>()
  let isLoading = false
  let hasError = false
  let isEnriching = false

  plate.forEach((entry, index) => {
    const result = detailResults[index]
    const key = plateKey(entry.food)
    if (result?.data) rawDetails.set(key, result.data)
    if (result?.isPending) isLoading = true
    if (result?.isError) hasError = true
  })

  // 第二段：仅对已加载且确实存在缺失指标的食材发起补全（共享 queryKey 去重）。
  const enrichQueries = plate.map((entry) => {
    const detail = rawDetails.get(plateKey(entry.food))
    const hasMissing = detail ? missingSummaryKeys(detail.summary_per_100g).length > 0 : false
    return {
      queryKey: queryKeys.enrichment(entry.food.fdc_id),
      queryFn: ({ signal }: { signal: AbortSignal }) =>
        getEnrichedNutrients(entry.food.fdc_id, signal),
      enabled: hasMissing,
      staleTime: FIVE_MINUTES,
      retry: 1,
    }
  })
  const enrichResults = useQueries({ queries: enrichQueries })

  const details = new Map<string, FoodDetail>()
  plate.forEach((entry, index) => {
    const key = plateKey(entry.food)
    const detail = rawDetails.get(key)
    if (!detail) return
    const enrichResult = enrichResults[index]
    if (enrichResult?.fetchStatus === 'fetching') isEnriching = true
    const enrichData = enrichResult?.data
    // 只采纳 verified_external 的外部值；USDA 原值与真实 0 不被覆盖。
    details.set(key, enrichData ? mergeEnrichment(detail, enrichData).detail : detail)
  })

  return { details, isLoading, hasError, isEnriching }
}
