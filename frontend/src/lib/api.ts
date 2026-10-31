import { zhCN } from '@/i18n/zh-CN'
import type {
  CategoriesResponse,
  EnrichedValuesResponse,
  FoodDetail,
  FoodListParams,
  FoodListResponse,
  FoodNutrientsResponse,
  HealthResponse,
  LibraryScope,
  NutrientMetaResponse,
  PlanBatchEntryInput,
  PlanEntryInput,
  WeeklyPlanInput,
  WeeklyPlanResponse,
} from '@/lib/types'

const RAW_BASE = import.meta.env.VITE_API_BASE_URL?.trim() ?? ''
export const API_BASE = RAW_BASE.replace(/\/$/, '')

export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

function buildQuery(params: Record<string, string | number | boolean | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === '') continue
    search.set(key, String(value))
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  return httpRequest<T>('GET', path, signal)
}

async function httpRequest<T>(
  method: 'GET' | 'POST' | 'PUT' | 'DELETE',
  path: string,
  signal?: AbortSignal,
  body?: unknown,
): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      signal,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError(0, 'NETWORK_ERROR', zhCN.errors.network)
  }

  if (!response.ok) {
    let code = `HTTP_${response.status}`
    let message: string = zhCN.errors.generic
    try {
      const body = (await response.json()) as { code?: string; message?: string; detail?: unknown }
      if (typeof body.code === 'string') code = body.code
      if (typeof body.message === 'string' && body.message.trim()) {
        message = body.message
      } else if (body.detail !== undefined) {
        message = zhCN.errors.invalidResponse
      }
    } catch {
      // 响应不是 JSON，保留通用中文提示
    }
    if (response.status === 503 && !message) message = zhCN.errors.databaseUnavailable
    throw new ApiError(response.status, code, message)
  }

  try {
    return (await response.json()) as T
  } catch {
    throw new ApiError(response.status, 'INVALID_JSON', zhCN.errors.invalidResponse)
  }
}

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return request<HealthResponse>('/api/health', signal)
}

export function listFoods(params: FoodListParams, signal?: AbortSignal): Promise<FoodListResponse> {
  const query = buildQuery({
    q: params.q,
    category_code: params.category_code,
    data_type: params.data_type,
    library_scope: params.library_scope,
    usage_scope: params.usage_scope,
    usage_class: params.usage_class,
    page: params.page,
    page_size: params.page_size,
    sort: params.sort,
  })
  return request<FoodListResponse>(`/api/foods${query}`, signal)
}

export function getFood(
  foodKey: string | number,
  scope: LibraryScope,
  signal?: AbortSignal,
): Promise<FoodDetail> {
  const query = buildQuery({ library_scope: scope })
  return request<FoodDetail>(`/api/foods/${encodeURIComponent(String(foodKey))}${query}`, signal)
}

export function getFoodNutrients(
  foodKey: string | number,
  scope: LibraryScope,
  signal?: AbortSignal,
): Promise<FoodNutrientsResponse> {
  const query = buildQuery({ library_scope: scope })
  return request<FoodNutrientsResponse>(
    `/api/foods/${encodeURIComponent(String(foodKey))}/nutrients${query}`,
    signal,
  )
}

export function getCategories(source?: string, signal?: AbortSignal): Promise<CategoriesResponse> {
  const query = buildQuery({ source })
  return request<CategoriesResponse>(`/api/metadata/categories${query}`, signal)
}

export function getNutrientMetadata(signal?: AbortSignal): Promise<NutrientMetaResponse> {
  return request<NutrientMetaResponse>('/api/metadata/nutrients', signal)
}

/** 读取外部补全解析结果；后端按缓存策略决定是否真正联网检索。 */
export function getEnrichedNutrients(
  fdcId: number,
  signal?: AbortSignal,
): Promise<EnrichedValuesResponse> {
  return request<EnrichedValuesResponse>(`/api/enrichment/foods/${fdcId}/resolved`, signal)
}

/** 忽略负缓存，强制重新检索（用户主动触发）。 */
export function refreshEnrichment(
  fdcId: number,
  signal?: AbortSignal,
): Promise<EnrichedValuesResponse> {
  return httpRequest<EnrichedValuesResponse>('POST', `/api/enrichment/foods/${fdcId}/refresh`, signal)
}

// ---------------------------------------------------------------- 每周计划

function plannerWeekPath(weekStart: string): string {
  return `/api/planner/plans/${encodeURIComponent(weekStart)}`
}

export function getWeeklyPlan(
  weekStart: string,
  signal?: AbortSignal,
): Promise<WeeklyPlanResponse> {
  return request<WeeklyPlanResponse>(plannerWeekPath(weekStart), signal)
}

export function saveWeeklyPlan(
  weekStart: string,
  payload: WeeklyPlanInput,
): Promise<WeeklyPlanResponse> {
  return httpRequest<WeeklyPlanResponse>('PUT', plannerWeekPath(weekStart), undefined, payload)
}

export function deleteWeeklyPlan(weekStart: string): Promise<WeeklyPlanResponse> {
  return httpRequest<WeeklyPlanResponse>('DELETE', plannerWeekPath(weekStart))
}

/** 从食品详情/餐盘直接向某天某餐次追加一个食品（餐次不存在时自动创建）。 */
export function addPlanEntry(payload: PlanEntryInput): Promise<WeeklyPlanResponse> {
  return httpRequest<WeeklyPlanResponse>('POST', '/api/planner/entries', undefined, payload)
}

/** 一次向某天某餐次追加多个食品（例如把整盘设计加入计划，餐次不存在时自动创建）。 */
export function addPlanEntriesBatch(payload: PlanBatchEntryInput): Promise<WeeklyPlanResponse> {
  return httpRequest<WeeklyPlanResponse>('POST', '/api/planner/entries/batch', undefined, payload)
}
