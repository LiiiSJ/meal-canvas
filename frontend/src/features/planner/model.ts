/**
 * 每周膳食计划的纯函数模型：本地日期、草稿结构、增删改、复制餐次、保存状态。
 *
 * 关键约定：
 * - 日期一律使用本地日历构造的 `YYYY-MM-DD` 字符串，禁止 `toISOString()`，
 *   避免 UTC 变换把本地日期推前或推后一天。
 * - 一周固定为周一至周日 7 天；主餐次每天各一条，加餐可以有多条。
 * - 计划食品以 `foodKey` + `libraryScope` 标识身份，不同食品库的同号 ID 不会冲突。
 * - 本模块不发起网络请求，不做营养计算（营养复用 lib/calculator）。
 */

import { DEFAULT_PLATE_GRAMS } from '@/lib/calculator'
import { zhCN } from '@/i18n/zh-CN'
import type {
  FoodDetail,
  FoodItem,
  LibraryScope,
  MealType,
  PlannerItem,
  PlannerMeal,
  PlannerMealInput,
  PlannerItemInput,
  PlannerDayInput,
  WeeklyPlanInput,
  WeeklyPlanResponse,
} from '@/lib/types'

export const MAIN_MEAL_TYPES: readonly MealType[] = ['breakfast', 'lunch', 'dinner']

export const MEAL_TYPE_ORDER: Record<MealType, number> = {
  breakfast: 0,
  lunch: 1,
  dinner: 2,
  snack: 9,
}

/** 加餐排序从 30 开始，给主餐次留出空间。 */
export const SNACK_SORT_BASE = 30

// ---------------------------------------------------------------- 本地日期

/** 解析 `YYYY-MM-DD` 为本地日期对象（本地时区，不做 UTC 转换）。 */
export function parseISODateLocal(iso: string): Date {
  const [year, month, day] = iso.split('-').map((part) => Number(part))
  return new Date(year, (month ?? 1) - 1, day ?? 1)
}

/** 把本地日期对象格式化为 `YYYY-MM-DD`。 */
export function toISODateLocal(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

/** 本地今天日期（可注入 now 便于测试）。 */
export function todayISO(now: Date = new Date()): string {
  return toISODateLocal(now)
}

/** 本地日期加减天数。 */
export function addDaysISO(iso: string, days: number): string {
  const date = parseISODateLocal(iso)
  date.setDate(date.getDate() + days)
  return toISODateLocal(date)
}

/** 任意日期所在自然周的周一。 */
export function startOfWeekISO(iso: string): string {
  const date = parseISODateLocal(iso)
  const offset = (date.getDay() + 6) % 7 // 周一=0，周日=6
  return addDaysISO(iso, -offset)
}

/** 周切换：以周一为起点平移若干周。 */
export function shiftWeekISO(weekStart: string, weeks: number): string {
  return addDaysISO(startOfWeekISO(weekStart), weeks * 7)
}

/** 一周 7 天日期（周一至周日）。 */
export function weekDays(weekStart: string): string[] {
  return Array.from({ length: 7 }, (_, index) => addDaysISO(weekStart, index))
}

/** 0=周一 … 6=周日。 */
export function weekdayIndex(iso: string): number {
  return (parseISODateLocal(iso).getDay() + 6) % 7
}

/** 是否为本地意义上的“今天”。 */
export function isToday(iso: string, now: Date = new Date()): boolean {
  return iso === todayISO(now)
}

/** 是否为合法的 `YYYY-MM-DD` 纯日期。 */
export function isValidISODate(iso: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(iso)) return false
  const date = parseISODateLocal(iso)
  return !Number.isNaN(date.getTime()) && toISODateLocal(date) === iso
}

/** 日期展示片段，文案拼装交给 i18n。 */
export function dateParts(iso: string): { month: number; day: number } {
  const date = parseISODateLocal(iso)
  return { month: date.getMonth() + 1, day: date.getDate() }
}

/** 计划日期展示：10 月 26 日（本地日期字符串，不经过时区转换）。 */
export function formatPlanDate(iso: string): string {
  const { month, day } = dateParts(iso)
  return zhCN.planner.dateLabel(month, day)
}

// ---------------------------------------------------------------- 草稿结构

export interface PlannerDraftItem {
  /** 仅前端使用的稳定行标识，不发送给后端。 */
  clientId: string
  foodKey: string
  scope: LibraryScope
  grams: number
  /** 食品名称快照，可为空；展示时优先使用最新详情。 */
  name: string
}

export interface PlannerDraftMeal {
  clientId: string
  mealType: MealType
  name: string
  notes: string
  items: PlannerDraftItem[]
}

export interface PlannerDraftDay {
  date: string
  meals: PlannerDraftMeal[]
}

export interface PlannerDraft {
  weekStart: string
  days: PlannerDraftDay[]
}

/** 选择器返回的食品引用，避免把整个 FoodItem 塞进草稿。 */
export interface PlannerFoodRef {
  foodKey: string
  scope: LibraryScope
  name: string
}

let idCounter = 0

function nextClientId(prefix: string): string {
  idCounter += 1
  return `${prefix}-${idCounter}`
}

function mainMealClientId(date: string, mealType: MealType): string {
  return `${date}:${mealType}`
}

function emptyMainMeal(date: string, mealType: MealType): PlannerDraftMeal {
  return {
    clientId: mainMealClientId(date, mealType),
    mealType,
    name: '',
    notes: '',
    items: [],
  }
}

/** 生成一周的空白草稿：每天默认早餐 / 午餐 / 晚餐三个空餐次。 */
export function createEmptyDraft(weekStart: string): PlannerDraft {
  return {
    weekStart,
    days: weekDays(weekStart).map((date) => ({
      date,
      meals: MAIN_MEAL_TYPES.map((mealType) => emptyMainMeal(date, mealType)),
    })),
  }
}

function itemFromServer(item: PlannerItem): PlannerDraftItem {
  return {
    clientId: `item-${item.item_id}`,
    foodKey: item.food_key,
    scope: item.library_scope,
    grams: item.amount_g,
    name: item.name_snapshot ?? '',
  }
}

function mealFromServer(meal: PlannerMeal): PlannerDraftMeal {
  return {
    clientId: meal.meal_type === 'snack' ? `meal-${meal.meal_id}` : mainMealClientId(meal.meal_date, meal.meal_type),
    mealType: meal.meal_type,
    name: meal.meal_name,
    notes: meal.notes ?? '',
    items: meal.items.map(itemFromServer),
  }
}

/**
 * 把后端响应转成编辑草稿。
 * 缺失的主餐次补成空餐次；多条加餐按 sort_order 依次追加。
 */
export function draftFromResponse(response: WeeklyPlanResponse): PlannerDraft {
  const dates = weekDays(response.week_start)
  const days: PlannerDraftDay[] = dates.map((date) => {
    const source = response.days.find((day) => day.date === date)
    const mainMeals = MAIN_MEAL_TYPES.map((mealType) => {
      const found = source?.meals.find((meal) => meal.meal_type === mealType)
      return found ? mealFromServer(found) : emptyMainMeal(date, mealType)
    })
    const snacks = (source?.meals ?? [])
      .filter((meal) => meal.meal_type === 'snack')
      .slice()
      .sort((a, b) => a.sort_order - b.sort_order || a.meal_id - b.meal_id)
      .map(mealFromServer)
    return { date, meals: [...mainMeals, ...snacks] }
  })
  return { weekStart: response.week_start, days }
}

/**
 * 草稿转周保存请求体。
 * 空餐次（无食品且无备注）不写入，避免保存大量空占位。
 */
export function draftToPayload(draft: PlannerDraft): WeeklyPlanInput {
  const days: PlannerDayInput[] = draft.days
    .map((day) => {
      let snackIndex = 0
      const meals: PlannerMealInput[] = day.meals
        .filter((meal) => meal.items.length > 0 || meal.notes.trim() !== '')
        .map((meal) => {
          const sortOrder =
            meal.mealType === 'snack'
              ? SNACK_SORT_BASE + snackIndex++
              : MEAL_TYPE_ORDER[meal.mealType] * 10
          const items: PlannerItemInput[] = meal.items.map((item, index) => ({
            food_key: item.foodKey,
            library_scope: item.scope,
            amount_g: item.grams,
            sort_order: index,
            name_snapshot: item.name.trim() || null,
          }))
          return {
            meal_type: meal.mealType,
            meal_name: meal.name.trim() || null,
            sort_order: sortOrder,
            notes: meal.notes.trim() || null,
            items,
          }
        })
      return { date: day.date, meals }
    })
    .filter((day) => day.meals.length > 0)
  return { days }
}

/** 草稿是否包含任何已安排内容。 */
export function hasDraftContent(draft: PlannerDraft): boolean {
  return draft.days.some((day) =>
    day.meals.some((meal) => meal.items.length > 0 || meal.notes.trim() !== ''),
  )
}

// ---------------------------------------------------------------- 草稿编辑

function updateDay(
  draft: PlannerDraft,
  date: string,
  updater: (day: PlannerDraftDay) => PlannerDraftDay,
): PlannerDraft {
  let changed = false
  const days = draft.days.map((day) => {
    if (day.date !== date) return day
    const next = updater(day)
    if (next !== day) changed = true
    return next
  })
  return changed ? { ...draft, days } : draft
}

function updateMeal(
  draft: PlannerDraft,
  date: string,
  mealClientId: string,
  updater: (meal: PlannerDraftMeal) => PlannerDraftMeal,
): PlannerDraft {
  return updateDay(draft, date, (day) => {
    let changed = false
    const meals = day.meals.map((meal) => {
      if (meal.clientId !== mealClientId) return meal
      const next = updater(meal)
      if (next !== meal) changed = true
      return next
    })
    return changed ? { ...day, meals } : day
  })
}

/**
 * 向某天某餐次添加食品。
 * 同一餐次内同一食品（food_key + library_scope）只保留一条，重复添加返回原草稿。
 */
export function addFood(
  draft: PlannerDraft,
  date: string,
  mealClientId: string,
  food: PlannerFoodRef,
  grams: number = DEFAULT_PLATE_GRAMS,
): PlannerDraft {
  if (!Number.isFinite(grams) || grams <= 0) return draft
  return updateMeal(draft, date, mealClientId, (meal) => {
    if (meal.items.some((item) => item.foodKey === food.foodKey && item.scope === food.scope)) {
      return meal
    }
    return {
      ...meal,
      items: [
        ...meal.items,
        {
          clientId: nextClientId('item'),
          foodKey: food.foodKey,
          scope: food.scope,
          grams,
          name: food.name,
        },
      ],
    }
  })
}

export interface BatchAddResult {
  draft: PlannerDraft
  /** 实际新增的食品条数。 */
  added: number
  /** 因餐次内重复（或批次内重复、克数无效）而跳过的条数。 */
  skipped: number
}

/**
 * 一次向某天某餐次添加多个食品（例如在选择器里多选后一次确认）。
 * 同一食品（food_key + library_scope）在餐次中只保留一条，重复项跳过并计数。
 */
export function addFoods(
  draft: PlannerDraft,
  date: string,
  mealClientId: string,
  foods: Array<{ ref: PlannerFoodRef; grams: number }>,
): BatchAddResult {
  let next = draft
  let added = 0
  let skipped = 0
  const seen = new Set<string>()
  for (const { ref, grams } of foods) {
    const key = `${ref.scope}:${ref.foodKey}`
    if (seen.has(key)) {
      skipped += 1
      continue
    }
    seen.add(key)
    const updated = addFood(next, date, mealClientId, ref, grams)
    if (updated === next) {
      skipped += 1
      continue
    }
    next = updated
    added += 1
  }
  return { draft: next, added, skipped }
}

/** 修改餐次中某个食品的克数；无效克数返回原草稿。 */
export function setItemGrams(
  draft: PlannerDraft,
  date: string,
  mealClientId: string,
  itemClientId: string,
  grams: number,
): PlannerDraft {
  if (!Number.isFinite(grams) || grams <= 0) return draft
  return updateMeal(draft, date, mealClientId, (meal) => ({
    ...meal,
    items: meal.items.map((item) =>
      item.clientId === itemClientId ? { ...item, grams } : item,
    ),
  }))
}

/** 删除餐次中的某个食品。 */
export function removeItem(
  draft: PlannerDraft,
  date: string,
  mealClientId: string,
  itemClientId: string,
): PlannerDraft {
  return updateMeal(draft, date, mealClientId, (meal) => ({
    ...meal,
    items: meal.items.filter((item) => item.clientId !== itemClientId),
  }))
}

/**
 * 删除餐次。
 * 加餐从当天移除；早餐 / 午餐 / 晚餐是固定槽位，删除等于清空内容并保留空卡片。
 */
export function deleteMeal(
  draft: PlannerDraft,
  date: string,
  mealClientId: string,
): PlannerDraft {
  const day = draft.days.find((item) => item.date === date)
  const meal = day?.meals.find((item) => item.clientId === mealClientId)
  if (!meal) return draft
  if (meal.mealType !== 'snack') {
    return updateMeal(draft, date, mealClientId, (current) => ({
      ...current,
      notes: '',
      name: '',
      items: [],
    }))
  }
  return updateDay(draft, date, (current) => ({
    ...current,
    meals: current.meals.filter((item) => item.clientId !== mealClientId),
  }))
}

/** 向某天追加一个加餐，返回新草稿与新餐次标识。 */
export function addSnack(
  draft: PlannerDraft,
  date: string,
): { draft: PlannerDraft; mealClientId: string } {
  const existing = draft.days.find((day) => day.date === date)
  if (!existing) return { draft, mealClientId: '' }
  const clientId = nextClientId(`snack-${date}`)
  const snack: PlannerDraftMeal = {
    clientId,
    mealType: 'snack',
    name: '',
    notes: '',
    items: [],
  }
  return {
    draft: updateDay(draft, date, (day) => ({ ...day, meals: [...day.meals, snack] })),
    mealClientId: clientId,
  }
}

/** 加餐在当天的序号（从 1 开始）；非加餐返回 0。 */
export function snackOrdinal(day: PlannerDraftDay, mealClientId: string): number {
  let ordinal = 0
  for (const meal of day.meals) {
    if (meal.mealType !== 'snack') continue
    ordinal += 1
    if (meal.clientId === mealClientId) return ordinal
  }
  return 0
}

/**
 * 复制餐次：把某天的早餐/午餐/晚餐/加餐复制到另一天的同类型餐次。
 * - 主餐次：替换目标同类型餐次的食品与备注（目标为空时直接写入）。
 * - 加餐：在目标当天追加一条新的加餐。
 * - 源餐次保持不变；复制后的食品使用新的前端标识，可独立修改。
 */
export function copyMeal(
  draft: PlannerDraft,
  sourceDate: string,
  sourceMealClientId: string,
  targetDate: string,
): PlannerDraft {
  const source = draft.days
    .find((day) => day.date === sourceDate)
    ?.meals.find((meal) => meal.clientId === sourceMealClientId)
  const targetDay = draft.days.find((day) => day.date === targetDate)
  if (!source || !targetDay || source.items.length === 0) return draft

  const clonedItems = source.items.map((item) => ({
    ...item,
    clientId: nextClientId('item'),
  }))

  if (source.mealType === 'snack') {
    const clientId = nextClientId(`snack-${targetDate}`)
    const snack: PlannerDraftMeal = {
      clientId,
      mealType: 'snack',
      name: source.name,
      notes: source.notes,
      items: clonedItems,
    }
    return updateDay(draft, targetDate, (day) => ({ ...day, meals: [...day.meals, snack] }))
  }

  return updateDay(draft, targetDate, (day) => ({
    ...day,
    meals: day.meals.map((meal) =>
      meal.mealType === source.mealType
        ? {
            ...meal,
            name: meal.name.trim() || source.name,
            notes: source.notes,
            items: clonedItems,
          }
        : meal,
    ),
  }))
}

// ---------------------------------------------------------------- 展示辅助

/**
 * 把草稿食品转成 FoodItem，供 FoodIcon / PlateItemControls 复用。
 * 有最新详情时直接使用详情；否则用名称快照构造最小对象。
 */
export function plannerFoodItem(item: PlannerDraftItem, detail?: FoodDetail): FoodItem {
  if (detail) return detail
  const numericId = Number(item.foodKey)
  const fdcId = Number.isFinite(numericId) ? numericId : 0
  const fallbackName = item.name || `FDC ${item.foodKey}`
  return {
    fdc_id: fdcId,
    data_type: 'foundation_food',
    source_dataset: '',
    source_version: '',
    description_en: fallbackName,
    name_zh: item.name || null,
    display_name: fallbackName,
    zh_status: item.name ? 'verified' : 'none',
    zh_review_status: item.name ? 'verified' : 'pending',
    category_code: null,
    category_en: null,
    category_zh: null,
    brand_owner: null,
    brand_name: null,
    gtin_upc: null,
    serving_size: null,
    serving_unit: null,
    household_serving: null,
    publication_date: null,
    is_default_library: item.scope === 'default',
    library_scope: item.scope,
    usage_class: null,
    usage_rule_source: null,
    usage_rule_id: null,
    usage_reason: null,
  }
}

/** 生成稳定的食品条目键：食材库 + 食品标识。 */
export function plannerFoodKey(foodKey: string, scope: LibraryScope): string {
  return `${scope}-${foodKey}`
}

/** 餐次展示名：主餐次用默认中文名，加餐用序号或自定义名称。 */
export function mealDisplayLabel(meal: PlannerDraftMeal, snackNumber: number): string {
  if (meal.mealType === 'snack') {
    return meal.name.trim() || zhCN.planner.snackOrdinal(snackNumber)
  }
  return meal.name.trim() || zhCN.planner.mealType[meal.mealType]
}

/** 计算当天加餐序号集合，供餐次卡片显示“加餐 1 / 加餐 2”。 */
export function snackNumbers(meals: PlannerDraftMeal[]): Map<string, number> {
  const numbers = new Map<string, number>()
  let index = 0
  for (const meal of meals) {
    if (meal.mealType !== 'snack') continue
    index += 1
    numbers.set(meal.clientId, index)
  }
  return numbers
}

// ---------------------------------------------------------------- 保存状态

/** 前端保存状态：尚未保存 / 有未保存修改 / 正在保存 / 保存成功 / 保存失败。 */
export type PlannerSaveStatus = 'clean' | 'dirty' | 'saving' | 'saved' | 'error'

export type PlannerSaveEvent = 'reset' | 'edit' | 'save_start' | 'save_success' | 'save_error'

export function nextSaveStatus(
  current: PlannerSaveStatus,
  event: PlannerSaveEvent,
): PlannerSaveStatus {
  switch (event) {
    case 'reset':
      return 'clean'
    case 'edit':
      return current === 'saving' ? 'saving' : 'dirty'
    case 'save_start':
      return 'saving'
    case 'save_success':
      return 'saved'
    case 'save_error':
      return 'error'
    default:
      return current
  }
}

/** 是否需要在切换周前提示：有未保存修改或上次保存失败。 */
export function hasUnsavedChanges(status: PlannerSaveStatus): boolean {
  return status === 'dirty' || status === 'error'
}
