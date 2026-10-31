import { useQueries } from '@tanstack/react-query'

import { mergeEnrichment, missingSummaryKeys } from '@/features/enrichment/merge'
import { plannerFoodKey, type PlannerDraftItem } from '@/features/planner/model'
import { getEnrichedNutrients, getFood } from '@/lib/api'
import { queryKeys } from '@/lib/queries'
import type { FoodDetail, LibraryScope } from '@/lib/types'

const FIVE_MINUTES = 5 * 60 * 1000

export interface PlannerFoodRefKey {
  foodKey: string
  scope: LibraryScope
}

function decodeFoodKey(foodKey: string): number | null {
  const numeric = Number(foodKey)
  return Number.isFinite(numeric) ? numeric : null
}

/**
 * 并发展示一周计划中所有食品的最新详情与外部补全值。
 * 与餐盘设计共用同一 food / enrichment 查询缓存，不重复请求。
 */
export function usePlannerFoodDetails(items: PlannerDraftItem[]): {
  details: Map<string, FoodDetail>
  isLoading: boolean
  hasError: boolean
  isEnriching: boolean
} {
  const unique = new Map<string, PlannerFoodRefKey>()
  for (const item of items) {
    unique.set(plannerFoodKey(item.foodKey, item.scope), {
      foodKey: item.foodKey,
      scope: item.scope,
    })
  }
  const refs = [...unique.values()]

  const detailQueries = refs.map((ref) => ({
    queryKey: queryKeys.food(decodeFoodKey(ref.foodKey) ?? ref.foodKey, ref.scope),
    queryFn: ({ signal }: { signal: AbortSignal }) => {
      const numericId = decodeFoodKey(ref.foodKey)
      if (numericId === null) throw new Error(`无法识别的食品标识：${ref.foodKey}`)
      return getFood(numericId, ref.scope, signal)
    },
    staleTime: FIVE_MINUTES,
  }))

  const detailResults = useQueries({ queries: detailQueries })

  const rawDetails = new Map<string, FoodDetail>()
  let isLoading = false
  let hasError = false

  refs.forEach((ref, index) => {
    const result = detailResults[index]
    const key = plannerFoodKey(ref.foodKey, ref.scope)
    if (result?.data) rawDetails.set(key, result.data)
    if (result?.isPending) isLoading = true
    if (result?.isError) hasError = true
  })

  // 第二段：仅对存在缺失核心营养的食品发起补全（共享 queryKey 去重）。
  const enrichQueries = refs.map((ref) => {
    const detail = rawDetails.get(plannerFoodKey(ref.foodKey, ref.scope))
    const hasMissing = detail ? missingSummaryKeys(detail.summary_per_100g).length > 0 : false
    const numericId = decodeFoodKey(ref.foodKey)
    return {
      queryKey: queryKeys.enrichment(numericId ?? 0),
      queryFn: ({ signal }: { signal: AbortSignal }) =>
        getEnrichedNutrients(numericId as number, signal),
      enabled: hasMissing && numericId !== null,
      staleTime: FIVE_MINUTES,
      retry: 1,
    }
  })
  const enrichResults = useQueries({ queries: enrichQueries })

  const details = new Map<string, FoodDetail>()
  let isEnriching = false
  refs.forEach((ref, index) => {
    const key = plannerFoodKey(ref.foodKey, ref.scope)
    const detail = rawDetails.get(key)
    if (!detail) return
    const enrichResult = enrichResults[index]
    if (enrichResult?.fetchStatus === 'fetching') isEnriching = true
    const enrichData = enrichResult?.data
    details.set(key, enrichData ? mergeEnrichment(detail, enrichData).detail : detail)
  })

  return { details, isLoading, hasError, isEnriching }
}
