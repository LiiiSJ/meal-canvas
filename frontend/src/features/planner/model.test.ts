import { describe, expect, it } from 'vitest'

import { computePlateNutrition } from '@/lib/calculator'
import type { WeeklyPlanResponse } from '@/lib/types'

import {
  addFood,
  addFoods,
  addSnack,
  copyMeal,
  createEmptyDraft,
  draftFromResponse,
  draftToPayload,
  hasDraftContent,
  hasUnsavedChanges,
  isToday,
  nextSaveStatus,
  plannerFoodItem,
  removeItem,
  setItemGrams,
  shiftWeekISO,
  snackOrdinal,
  startOfWeekISO,
  todayISO,
  weekDays,
  weekdayIndex,
  deleteMeal,
  type PlannerSaveStatus,
} from '@/features/planner/model'

const WEEK_START = '2026-10-26' // 周一
const SATURDAY = '2026-10-31'
const SUNDAY = '2026-11-01'

function emptyResponse(weekStart = WEEK_START): WeeklyPlanResponse {
  return {
    week_start: weekStart,
    plan_id: null,
    created_at: null,
    updated_at: null,
    days: weekDays(weekStart).map((date) => ({ date, meals: [] })),
  }
}

describe('本地日期与周计算', () => {
  it('使用本地日历生成 YYYY-MM-DD，不受 UTC 时区影响', () => {
    expect(todayISO(new Date(2026, 9, 31, 23, 30))).toBe('2026-10-31')
    expect(todayISO(new Date(2026, 0, 1, 0, 30))).toBe('2026-01-01')
  })

  it('任意日期都能定位到所在周的周一', () => {
    expect(startOfWeekISO(WEEK_START)).toBe(WEEK_START)
    expect(startOfWeekISO(SATURDAY)).toBe(WEEK_START)
    expect(startOfWeekISO(SUNDAY)).toBe(WEEK_START)
    expect(weekdayIndex(SATURDAY)).toBe(5)
  })

  it('周切换以周一为起点平移 7 天', () => {
    expect(shiftWeekISO(WEEK_START, 1)).toBe('2026-11-02')
    expect(shiftWeekISO(WEEK_START, -1)).toBe('2026-10-19')
    expect(weekDays(WEEK_START)).toEqual([
      '2026-10-26',
      '2026-10-27',
      '2026-10-28',
      '2026-10-29',
      '2026-10-30',
      '2026-10-31',
      '2026-11-01',
    ])
  })

  it('识别本地今天', () => {
    expect(isToday(SATURDAY, new Date(2026, 9, 31, 8, 0))).toBe(true)
    expect(isToday(SUNDAY, new Date(2026, 9, 31, 8, 0))).toBe(false)
  })
})

describe('草稿结构', () => {
  it('空周默认包含 7 天，每天 3 个空主餐次', () => {
    const draft = createEmptyDraft(WEEK_START)
    expect(draft.days).toHaveLength(7)
    expect(draft.days[0].meals.map((meal) => meal.mealType)).toEqual([
      'breakfast',
      'lunch',
      'dinner',
    ])
    expect(hasDraftContent(draft)).toBe(false)
  })

  it('从后端响应恢复主餐次与多条加餐，并保持顺序', () => {
    const response: WeeklyPlanResponse = {
      ...emptyResponse(),
      plan_id: 7,
      days: weekDays(WEEK_START).map((date) => ({
        date,
        meals:
          date === SATURDAY
            ? [
                {
                  meal_id: 31,
                  meal_date: date,
                  meal_type: 'breakfast',
                  meal_name: '早餐',
                  sort_order: 0,
                  notes: null,
                  items: [
                    {
                      item_id: 101,
                      food_key: '748967',
                      library_scope: 'default',
                      amount_g: 50,
                      sort_order: 0,
                      name_snapshot: '鸡蛋',
                    },
                  ],
                },
                {
                  meal_id: 32,
                  meal_date: date,
                  meal_type: 'snack',
                  meal_name: '加餐',
                  sort_order: 30,
                  notes: null,
                  items: [],
                },
                {
                  meal_id: 33,
                  meal_date: date,
                  meal_type: 'snack',
                  meal_name: '下午茶',
                  sort_order: 31,
                  notes: '坚果',
                  items: [],
                },
              ]
            : [],
      })),
    }
    const draft = draftFromResponse(response)
    const saturday = draft.days.find((day) => day.date === SATURDAY)!
    expect(saturday.meals.map((meal) => meal.mealType)).toEqual([
      'breakfast',
      'lunch',
      'dinner',
      'snack',
      'snack',
    ])
    expect(saturday.meals[0].items[0].grams).toBe(50)
    expect(saturday.meals[0].items[0].name).toBe('鸡蛋')
    expect(snackOrdinal(saturday, saturday.meals[4].clientId)).toBe(2)
  })
})

describe('餐次编辑', () => {
    it('添加食品、修改克数、删除食品', () => {
      let draft = createEmptyDraft(WEEK_START)
      const mealId = draft.days[0].meals[0].clientId
      const date = draft.days[0].date

      draft = addFood(draft, date, mealId, { foodKey: '748967', scope: 'default', name: '鸡蛋' }, 50)
      expect(draft.days[0].meals[0].items).toHaveLength(1)

      const itemId = draft.days[0].meals[0].items[0].clientId
      draft = setItemGrams(draft, date, mealId, itemId, 120)
      expect(draft.days[0].meals[0].items[0].grams).toBe(120)

      draft = removeItem(draft, date, mealId, itemId)
      expect(draft.days[0].meals[0].items).toHaveLength(0)
    })

    it('同一餐次重复添加同一食品不会产生重复条目', () => {
      let draft = createEmptyDraft(WEEK_START)
      const mealId = draft.days[0].meals[0].clientId
      const date = draft.days[0].date
      const food = { foodKey: '748967', scope: 'default' as const, name: '鸡蛋' }
      draft = addFood(draft, date, mealId, food)
      draft = addFood(draft, date, mealId, food)
      expect(draft.days[0].meals[0].items).toHaveLength(1)
    })

    it('允许同一天存在多个加餐，删除加餐只移除该条', () => {
      let draft = createEmptyDraft(WEEK_START)
      const date = draft.days[0].date
      const first = addSnack(draft, date)
      draft = first.draft
      const second = addSnack(draft, date)
      draft = second.draft
      expect(draft.days[0].meals.filter((meal) => meal.mealType === 'snack')).toHaveLength(2)

      draft = deleteMeal(draft, date, first.mealClientId)
      expect(draft.days[0].meals.filter((meal) => meal.mealType === 'snack')).toHaveLength(1)
      expect(draft.days[0].meals.find((meal) => meal.clientId === second.mealClientId)).toBeDefined()
    })

    it('删除主餐次等于清空内容，卡片保留', () => {
      let draft = createEmptyDraft(WEEK_START)
      const date = draft.days[0].date
      const mealId = draft.days[0].meals[2].clientId
      draft = addFood(draft, date, mealId, { foodKey: '1', scope: 'default', name: '米饭' })
      draft = deleteMeal(draft, date, mealId)
      expect(draft.days[0].meals).toHaveLength(3)
      expect(draft.days[0].meals[2].items).toHaveLength(0)
    })

    it('批量添加：一次把多种食品加入同一餐次', () => {
      const draft = createEmptyDraft(WEEK_START)
      const date = draft.days[0].date
      const mealId = draft.days[0].meals[0].clientId

      const result = addFoods(draft, date, mealId, [
        { ref: { foodKey: '1', scope: 'default', name: '全麦面包' }, grams: 100 },
        { ref: { foodKey: '2', scope: 'default', name: '鸡蛋' }, grams: 50 },
        { ref: { foodKey: '3', scope: 'default', name: '牛奶' }, grams: 200 },
      ])

      expect(result.added).toBe(3)
      expect(result.skipped).toBe(0)
      const meal = result.draft.days[0].meals[0]
      expect(meal.items.map((item) => item.foodKey)).toEqual(['1', '2', '3'])
      expect(meal.items.map((item) => item.grams)).toEqual([100, 50, 200])
    })

    it('批量添加：餐次已有、批次内重复与无效克数都跳过并计数', () => {
      let draft = createEmptyDraft(WEEK_START)
      const date = draft.days[0].date
      const mealId = draft.days[0].meals[0].clientId
      draft = addFood(draft, date, mealId, { foodKey: '1', scope: 'default', name: '全麦面包' }, 80)

      const result = addFoods(draft, date, mealId, [
        { ref: { foodKey: '1', scope: 'default', name: '全麦面包' }, grams: 100 }, // 餐次已有
        { ref: { foodKey: '2', scope: 'default', name: '鸡蛋' }, grams: 50 },
        { ref: { foodKey: '2', scope: 'default', name: '鸡蛋' }, grams: 60 }, // 批次内重复
        { ref: { foodKey: '3', scope: 'default', name: '牛奶' }, grams: 0 }, // 无效克数
      ])

      expect(result.added).toBe(1)
      expect(result.skipped).toBe(3)
      const meal = result.draft.days[0].meals[0]
      expect(meal.items.map((item) => item.foodKey)).toEqual(['1', '2'])
      expect(meal.items[0].grams).toBe(80) // 原有克数不被批量操作覆盖
    })
})

describe('复制餐次', () => {
  it('复制早餐到另一天，源餐次不变且副本可独立修改', () => {
    let draft = createEmptyDraft(WEEK_START)
    const sourceDate = WEEK_START
    const targetDate = '2026-10-28'
    const breakfast = draft.days[0].meals[0].clientId
    draft = addFood(draft, sourceDate, breakfast, { foodKey: '1', scope: 'default', name: '全麦面包' }, 100)
    draft = addFood(draft, sourceDate, breakfast, { foodKey: '2', scope: 'default', name: '牛奶' }, 200)

    draft = copyMeal(draft, sourceDate, breakfast, targetDate)

    const targetBreakfast = draft.days.find((day) => day.date === targetDate)!.meals[0]
    expect(targetBreakfast.items.map((item) => item.grams)).toEqual([100, 200])
    const sourceBreakfast = draft.days[0].meals[0]
    expect(sourceBreakfast.items).toHaveLength(2)

    const targetItemId = targetBreakfast.items[0].clientId
    draft = setItemGrams(draft, targetDate, targetBreakfast.clientId, targetItemId, 60)
    expect(
      draft.days
        .find((day) => day.date === targetDate)!
        .meals[0].items[0].grams,
    ).toBe(60)
    expect(draft.days[0].meals[0].items[0].grams).toBe(100)
  })

  it('复制加餐会追加一条新加餐，不替换已有加餐', () => {
    let draft = createEmptyDraft(WEEK_START)
    const date = WEEK_START
    const snack = addSnack(draft, date)
    draft = snack.draft
    draft = addFood(draft, date, snack.mealClientId, { foodKey: '3', scope: 'default', name: '酸奶' }, 150)
    draft = copyMeal(draft, date, snack.mealClientId, '2026-10-30')
    const targetDay = draft.days.find((day) => day.date === '2026-10-30')!
    expect(targetDay.meals.filter((meal) => meal.mealType === 'snack')).toHaveLength(1)
    expect(draft.days[0].meals.filter((meal) => meal.mealType === 'snack')).toHaveLength(1)
  })
})

describe('保存请求体', () => {
  it('跳过空餐次与空日期，并为加餐生成递增排序', () => {
    let draft = createEmptyDraft(WEEK_START)
    const date = SATURDAY
    const day = draft.days.find((item) => item.date === date)!
    draft = addFood(draft, date, day.meals[0].clientId, { foodKey: '1', scope: 'default', name: '面包' }, 80)
    const snackA = addSnack(draft, date)
    draft = snackA.draft
    const snackB = addSnack(draft, date)
    draft = snackB.draft
    draft = addFood(draft, date, snackA.mealClientId, { foodKey: '2', scope: 'default', name: '苹果' }, 100)
    draft = addFood(draft, date, snackB.mealClientId, { foodKey: '3', scope: 'default', name: '坚果' }, 20)

    const payload = draftToPayload(draft)
    expect(payload.days).toHaveLength(1)
    const meals = payload.days[0].meals
    expect(meals.map((meal) => meal.meal_type)).toEqual(['breakfast', 'snack', 'snack'])
    expect(meals[0].sort_order).toBe(0)
    expect(meals[1].sort_order).toBe(30)
    expect(meals[2].sort_order).toBe(31)
    expect(meals[1].items?.[0]).toMatchObject({
      food_key: '2',
      library_scope: 'default',
      amount_g: 100,
      sort_order: 0,
    })
  })
})

describe('保存状态与营养合计', () => {
  it('保存状态在编辑、保存、失败之间正确流转', () => {
    let status: PlannerSaveStatus = 'clean'
    status = nextSaveStatus(status, 'edit')
    expect(status).toBe('dirty')
    status = nextSaveStatus(status, 'save_start')
    expect(status).toBe('saving')
    status = nextSaveStatus(status, 'save_success')
    expect(status).toBe('saved')
    status = nextSaveStatus(status, 'edit')
    expect(status).toBe('dirty')
    status = nextSaveStatus(status, 'save_start')
    status = nextSaveStatus(status, 'save_error')
    expect(status).toBe('error')
    expect(hasUnsavedChanges('dirty')).toBe(true)
    expect(hasUnsavedChanges('error')).toBe(true)
    expect(hasUnsavedChanges('saved')).toBe(false)
    expect(hasUnsavedChanges('saving')).toBe(false)
  })

  it('修改克数会改变该餐营养合计', () => {
    let draft = createEmptyDraft(WEEK_START)
    const date = draft.days[0].date
    const mealId = draft.days[0].meals[0].clientId
    draft = addFood(draft, date, mealId, { foodKey: '748967', scope: 'default', name: '鸡蛋' }, 50)
    const itemId = draft.days[0].meals[0].items[0].clientId
    const summary = {
      energy_kcal: 143,
      protein_g: 12.6,
      fat_g: 9.5,
      carb_g: 0.7,
      fiber_g: 0,
      sugar_g: 0.4,
      sodium_mg: 142,
      known_core_count: 7,
      baseline: 'per_100g',
    }
    const before = computePlateNutrition([
      { foodKey: '748967', grams: draft.days[0].meals[0].items[0].grams, summary },
    ])
    expect(before[0].total).toBeCloseTo(71.5)

    draft = setItemGrams(draft, date, mealId, itemId, 100)
    const after = computePlateNutrition([
      { foodKey: '748967', grams: draft.days[0].meals[0].items[0].grams, summary },
    ])
    expect(after[0].total).toBeCloseTo(143)
  })

  it('名称缺失时构造的展示食品仍有可读名称', () => {
    const item = plannerFoodItem({
      clientId: 'item-1',
      foodKey: '748967',
      scope: 'default',
      grams: 100,
      name: '',
    })
    expect(item.fdc_id).toBe(748967)
    expect(item.display_name).toBe('FDC 748967')
  })
})
