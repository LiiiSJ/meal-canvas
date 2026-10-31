import { describe, expect, it } from 'vitest'

import {
  addPlateEntry,
  computePlateNutrition,
  formatPortionLabel,
  getUsablePortions,
  parseGrams,
  removePlateEntry,
  type PlateIngredient,
} from '@/lib/calculator'
import type { FoodItem, FoodPortion, FoodSummary } from '@/lib/types'

/** 构造最小可用的 FoodItem 夹具。 */
function makeFood(overrides: Partial<FoodItem> = {}): FoodItem {
  return {
    fdc_id: 1,
    data_type: 'foundation_food',
    source_dataset: 'Foundation',
    source_version: '2026-04',
    description_en: 'Test food',
    name_zh: '测试食材',
    display_name: '测试食材',
    zh_status: 'verified',
    zh_review_status: 'verified',
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
    ...overrides,
  } as FoodItem
}

function makeSummary(overrides: Partial<FoodSummary> = {}): FoodSummary {
  return {
    energy_kcal: 130,
    protein_g: 10,
    fat_g: 5,
    carb_g: 20,
    fiber_g: 3,
    sugar_g: null,
    sodium_mg: 100,
    known_core_count: 6,
    baseline: 'per_100g',
    ...overrides,
  }
}

function makePortion(overrides: Partial<FoodPortion> = {}): FoodPortion {
  return {
    fdc_id: 1,
    amount: 1,
    modifier: 'medium',
    portion_description: '1 个, 中等',
    gram_weight: 150,
    unit_name: null,
    quality_flag: 'ok',
    ...overrides,
  }
}

function ingredient(foodKey: string, grams: number, summary: FoodSummary): PlateIngredient {
  return { foodKey, grams, summary }
}

describe('parseGrams', () => {
  it('接受正整数与小数', () => {
    expect(parseGrams('150')).toBe(150)
    expect(parseGrams('50.5')).toBe(50.5)
    expect(parseGrams('  120  ')).toBe(120)
  })

  it('拒绝空、非数字、负数、零与超限', () => {
    expect(parseGrams('')).toBeNull()
    expect(parseGrams('abc')).toBeNull()
    expect(parseGrams('-5')).toBeNull()
    expect(parseGrams('0')).toBeNull()
    expect(parseGrams('20000')).toBeNull()
  })
})

describe('computePlateNutrition', () => {
  it('空餐盘时所有指标为 all_missing 且 total 为 null', () => {
    const results = computePlateNutrition([])
    for (const result of results) {
      expect(result.status).toBe('all_missing')
      expect(result.total).toBeNull()
      expect(result.knownValue).toBe(0)
    }
  })

  it('添加食品后按每 100 克 × 克重 ÷ 100 计算', () => {
    // 每 100g 含 130 kcal，150g → 195 kcal
    const results = computePlateNutrition([ingredient('f1', 150, makeSummary({ energy_kcal: 130 }))])
    const energy = results.find((r) => r.key === 'energy_kcal')!
    expect(energy.status).toBe('complete')
    expect(energy.total).toBe(195)
  })

  it('修改克重后营养贡献正确改变', () => {
    const at100 = computePlateNutrition([ingredient('f1', 100, makeSummary({ protein_g: 10 }))])
    const at200 = computePlateNutrition([ingredient('f1', 200, makeSummary({ protein_g: 10 }))])
    expect(at100.find((r) => r.key === 'protein_g')!.total).toBe(10)
    expect(at200.find((r) => r.key === 'protein_g')!.total).toBe(20)
  })

  it('小数克数按比例计算', () => {
    // 130 kcal × 50.5 / 100 = 65.65
    const results = computePlateNutrition([ingredient('f1', 50.5, makeSummary({ energy_kcal: 130 }))])
    expect(results.find((r) => r.key === 'energy_kcal')!.total).toBeCloseTo(65.65)
  })

  it('真实零值参与累加（贡献为 0），不被当作缺失', () => {
    const summary = makeSummary({ protein_g: 0 })
    const results = computePlateNutrition([ingredient('f1', 100, summary)])
    const protein = results.find((r) => r.key === 'protein_g')!
    expect(protein.status).toBe('complete')
    expect(protein.total).toBe(0)
    expect(protein.missingCount).toBe(0)
  })

  it('缺失值（null）不计入累加，并计入缺失数', () => {
    const summary = makeSummary({ protein_g: null })
    const results = computePlateNutrition([ingredient('f1', 100, summary)])
    const protein = results.find((r) => r.key === 'protein_g')!
    expect(protein.status).toBe('all_missing')
    expect(protein.total).toBeNull()
    expect(protein.missingCount).toBe(1)
  })

  it('部分食材缺失某营养时标记为 partial，total 为 null 但保留 knownValue', () => {
    const entries = [
      ingredient('f1', 100, makeSummary({ protein_g: 10 })),
      ingredient('f2', 100, makeSummary({ protein_g: null })),
    ]
    const results = computePlateNutrition(entries)
    const protein = results.find((r) => r.key === 'protein_g')!
    expect(protein.status).toBe('partial')
    expect(protein.total).toBeNull()
    expect(protein.knownValue).toBe(10)
    expect(protein.missingCount).toBe(1)
    expect(protein.totalCount).toBe(2)
  })

  it('负数视为不可用，不当作零值参与累加', () => {
    const summary = makeSummary({ protein_g: -3 })
    const results = computePlateNutrition([ingredient('f1', 100, summary)])
    const protein = results.find((r) => r.key === 'protein_g')!
    expect(protein.status).toBe('all_missing')
    expect(protein.knownValue).toBe(0)
  })

  it('删除食材后合计重新计算', () => {
    const entries = [
      ingredient('f1', 100, makeSummary({ energy_kcal: 100 })),
      ingredient('f2', 100, makeSummary({ energy_kcal: 50 })),
    ]
    const before = computePlateNutrition(entries)
    const after = computePlateNutrition(entries.slice(0, 1))
    expect(before.find((r) => r.key === 'energy_kcal')!.total).toBe(150)
    expect(after.find((r) => r.key === 'energy_kcal')!.total).toBe(100)
  })
})

describe('getUsablePortions', () => {
  it('只保留 gram_weight 为正且 quality_flag 为 ok 的份量', () => {
    const portions = [
      makePortion({ gram_weight: 150, quality_flag: 'ok' }),
      makePortion({ gram_weight: 0, quality_flag: 'zero_weight' }),
      makePortion({ gram_weight: null, quality_flag: 'missing' }),
      makePortion({ gram_weight: -10, quality_flag: 'ok' }),
      makePortion({ gram_weight: 200, quality_flag: 'estimated' }),
    ]
    const usable = getUsablePortions(portions)
    expect(usable).toHaveLength(1)
    expect(usable[0].gram_weight).toBe(150)
  })

  it('品牌食品无份量记录时返回空数组，不出现假选项', () => {
    expect(getUsablePortions([])).toHaveLength(0)
  })

  it('可用份量的标签严格使用接口字段', () => {
    const label = formatPortionLabel(makePortion())
    expect(label).toContain('1 个, 中等')
    expect(label).toContain('150 g')
  })
})

describe('plate entry state', () => {
  it('重复添加同一食品时保留已有克重，不新增条目', () => {
    const food = makeFood({ fdc_id: 1 })
    let plate = addPlateEntry([], food, { maxItems: 8, defaultGrams: 100 })
    // 用户修改过克重
    plate = [{ food, grams: 250 }]
    const next = addPlateEntry(plate, food, { maxItems: 8, defaultGrams: 100 })
    expect(next).toHaveLength(1)
    expect(next[0].grams).toBe(250)
  })

  it('超过上限时拒绝新增', () => {
    const plate = Array.from({ length: 8 }, (_, i) => ({
      food: makeFood({ fdc_id: i + 1 }),
      grams: 100,
    }))
    const next = addPlateEntry(plate, makeFood({ fdc_id: 100 }), { maxItems: 8, defaultGrams: 100 })
    expect(next).toHaveLength(8)
  })

  it('移除指定食品后重新计算', () => {
    const food = makeFood({ fdc_id: 1 })
    const plate = [{ food, grams: 100 }]
    expect(removePlateEntry(plate, food)).toHaveLength(0)
  })
})
