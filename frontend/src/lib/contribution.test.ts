import { describe, expect, it } from 'vitest'

import { computeContributions } from '@/lib/contribution'
import type { FoodItem, FoodSummary } from '@/lib/types'

function makeFood(fdcId: number, name: string): FoodItem {
  return {
    fdc_id: fdcId,
    data_type: 'sr_legacy_food',
    source_dataset: 'SR Legacy',
    source_version: '2018-04',
    description_en: name,
    name_zh: null,
    display_name: name,
    zh_status: 'none',
    zh_review_status: 'pending',
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
    is_default_library: true,
    library_scope: 'default',
    usage_class: 'basic_ingredient',
    usage_rule_source: null,
    usage_rule_id: null,
    usage_reason: null,
  }
}

function makeSummary(protein: number | null): FoodSummary {
  return {
    energy_kcal: null,
    protein_g: protein,
    fat_g: null,
    carb_g: null,
    fiber_g: null,
    sugar_g: null,
    sodium_mg: null,
    known_core_count: 0,
    baseline: 'per_100g',
  }
}

const keyOf = (entry: { food: FoodItem }) => `${entry.food.library_scope}-${entry.food.fdc_id}`

describe('computeContributions', () => {
  it('按每 100 克值 × 克重 ÷ 100 计算并从大到小排序', () => {
    const a = makeFood(1, 'A')
    const b = makeFood(2, 'B')
    const entries = [
      { food: a, grams: 100 },
      { food: b, grams: 200 },
    ]
    const summaries = new Map([
      [keyOf({ food: a }), makeSummary(10)],
      [keyOf({ food: b }), makeSummary(20)],
    ])
    const result = computeContributions(entries, summaries, keyOf, 'protein_g')
    expect(result.items.map((item) => item.entry.food.fdc_id)).toEqual([2, 1])
    expect(result.items[0].value).toBeCloseTo(40)
    expect(result.items[1].value).toBeCloseTo(10)
    expect(result.knownTotal).toBeCloseTo(50)
    expect(result.missing).toHaveLength(0)
  })

  it('缺失值不计入贡献并列入 missing，不当作 0', () => {
    const a = makeFood(1, 'A')
    const b = makeFood(2, 'B')
    const entries = [
      { food: a, grams: 100 },
      { food: b, grams: 100 },
    ]
    const summaries = new Map([
      [keyOf({ food: a }), makeSummary(null)],
      [keyOf({ food: b }), makeSummary(5)],
    ])
    const result = computeContributions(entries, summaries, keyOf, 'protein_g')
    expect(result.items).toHaveLength(1)
    expect(result.missing.map((entry) => entry.food.fdc_id)).toEqual([1])
    expect(result.knownTotal).toBeCloseTo(5)
  })

  it('真实 0 值保留为贡献 0，负值视为缺失', () => {
    const a = makeFood(1, 'A')
    const b = makeFood(2, 'B')
    const entries = [
      { food: a, grams: 100 },
      { food: b, grams: 100 },
    ]
    const summaries = new Map([
      [keyOf({ food: a }), makeSummary(0)],
      [keyOf({ food: b }), makeSummary(-3)],
    ])
    const result = computeContributions(entries, summaries, keyOf, 'protein_g')
    expect(result.items).toHaveLength(1)
    expect(result.items[0].value).toBe(0)
    expect(result.missing.map((entry) => entry.food.fdc_id)).toEqual([2])
  })
})
