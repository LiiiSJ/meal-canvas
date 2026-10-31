import { useQuery, useQueries, useMutation, useQueryClient } from '@tanstack/react-query'

import {
  addPlanEntriesBatch,
  addPlanEntry,
  deleteWeeklyPlan,
  getCategories,
  getEnrichedNutrients,
  getFood,
  getFoodNutrients,
  getHealth,
  getWeeklyPlan,
  listFoods,
  refreshEnrichment,
  saveWeeklyPlan,
} from '@/lib/api'
import type {
  FoodListParams,
  LibraryScope,
  PlanBatchEntryInput,
  PlanEntryInput,
  WeeklyPlanInput,
} from '@/lib/types'

const FIVE_MINUTES = 5 * 60 * 1000

export const queryKeys = {
  health: ['health'] as const,
  foods: (params: FoodListParams) => ['foods', params] as const,
  food: (foodKey: string | number, scope: LibraryScope) => ['food', foodKey, scope] as const,
  nutrients: (foodKey: string | number, scope: LibraryScope) =>
    ['food-nutrients', foodKey, scope] as const,
  categories: ['categories'] as const,
  enrichment: (fdcId: string | number) => ['enrichment', fdcId] as const,
  weeklyPlanPrefix: ['weekly-plan'] as const,
  weeklyPlan: (weekStart: string) => ['weekly-plan', weekStart] as const,
}

export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: ({ signal }) => getHealth(signal),
    staleTime: 60 * 1000,
    retry: 1,
  })
}

export function useFoodList(params: FoodListParams, enabled = true) {
  return useQuery({
    queryKey: queryKeys.foods(params),
    queryFn: ({ signal }) => listFoods(params, signal),
    enabled,
    staleTime: FIVE_MINUTES,
    placeholderData: (previous) => previous,
  })
}

export function useFoodDetail(foodKey: string | number | null, scope: LibraryScope) {
  return useQuery({
    queryKey: queryKeys.food(foodKey ?? 'none', scope),
    queryFn: ({ signal }) => getFood(foodKey!, scope, signal),
    enabled: foodKey !== null,
    staleTime: FIVE_MINUTES,
  })
}

export function useFoodNutrients(foodKey: string | number | null, scope: LibraryScope) {
  return useQuery({
    queryKey: queryKeys.nutrients(foodKey ?? 'none', scope),
    queryFn: ({ signal }) => getFoodNutrients(foodKey!, scope, signal),
    enabled: foodKey !== null,
    staleTime: FIVE_MINUTES,
  })
}

export function useCategories() {
  return useQuery({
    queryKey: queryKeys.categories,
    queryFn: ({ signal }) => getCategories(undefined, signal),
    staleTime: 10 * 60 * 1000,
  })
}

/** 并发读取一组食品详情（探索页绘图用）。 */
export function useFoodDetails(foodKeys: number[], scope: LibraryScope) {
  return useQueries({
    queries: foodKeys.map((foodKey) => ({
      queryKey: queryKeys.food(foodKey, scope),
      queryFn: ({ signal }: { signal: AbortSignal }) => getFood(foodKey, scope, signal),
      staleTime: FIVE_MINUTES,
    })),
  })
}

/**
 * 读取外部补全解析结果（缺失检测与联网检索都在后端完成）。
 * 与餐盘补全共用同一 queryKey，天然去重：同一食品多组件请求只发一次。
 */
export function useEnrichedNutrients(fdcId: number | null, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.enrichment(fdcId ?? 0),
    queryFn: ({ signal }) => getEnrichedNutrients(fdcId!, signal),
    enabled: enabled && fdcId !== null,
    staleTime: FIVE_MINUTES,
    retry: 1,
  })
}

/** 用户主动触发：忽略负缓存重新检索，成功后直接写入缓存。 */
export function useEnrichmentRefresh(fdcId: number | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => refreshEnrichment(fdcId!),
    onSuccess: (data) => {
      if (fdcId !== null) queryClient.setQueryData(queryKeys.enrichment(fdcId), data)
    },
  })
}

// ---------------------------------------------------------------- 每周计划

/** 读取指定周（周一日期）的完整计划；未保存时后端返回空周。 */
export function useWeeklyPlan(weekStart: string) {
  return useQuery({
    queryKey: queryKeys.weeklyPlan(weekStart),
    queryFn: ({ signal }) => getWeeklyPlan(weekStart, signal),
    staleTime: FIVE_MINUTES,
    placeholderData: (previous) => previous,
  })
}

/** 整周覆盖保存；成功后把响应直接写入对应周缓存。 */
export function useSaveWeeklyPlan() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (vars: { weekStart: string; payload: WeeklyPlanInput }) =>
      saveWeeklyPlan(vars.weekStart, vars.payload),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.weeklyPlan(data.week_start), data)
      void queryClient.invalidateQueries({ queryKey: queryKeys.weeklyPlanPrefix })
    },
  })
}

/** 从食品详情/餐盘直接加入某天某餐次；成功后刷新对应周（周前缀失效）。 */
export function useAddPlanEntry() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: PlanEntryInput) => addPlanEntry(payload),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.weeklyPlan(data.week_start), data)
      void queryClient.invalidateQueries({ queryKey: queryKeys.weeklyPlanPrefix })
    },
  })
}

/** 一次把多个食品加入某天某餐次（例如整盘加入计划）；成功后刷新对应周。 */
export function useAddPlanEntriesBatch() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: PlanBatchEntryInput) => addPlanEntriesBatch(payload),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.weeklyPlan(data.week_start), data)
      void queryClient.invalidateQueries({ queryKey: queryKeys.weeklyPlanPrefix })
    },
  })
}

/** 删除整周计划（用户明确操作，需二次确认）。 */
export function useDeleteWeeklyPlan() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (weekStart: string) => deleteWeeklyPlan(weekStart),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.weeklyPlan(data.week_start), data)
      void queryClient.invalidateQueries({ queryKey: queryKeys.weeklyPlanPrefix })
    },
  })
}
