import { describe, expect, it } from 'vitest'

import { mergeEnrichment, missingSummaryKeys } from './merge'
import type { EnrichedValuesResponse, FoodDetail } from '@/lib/types'

function makeDetail(summary: Partial<FoodDetail['summary_per_100g']>): FoodDetail {
  return {
    fdc_id: 1,
    data_type: 'foundation_food',
    source_dataset: 'Foundation Foods',
    source_version: '2024',
    description_en: 'Test food, raw',
    name_zh: '测试食品',
    display_name: '测试食品',
    zh_status: 'verified',
    zh_review_status: 'verified',
    category_code: '11',
    category_en: 'Vegetables',
    category_zh: '蔬菜',
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
    portions: [],
    aliases: [],
    quality_events: [],
    summary_per_100g: {
      energy_kcal: 50,
      protein_g: 2,
      fat_g: null,
      carb_g: 8,
      fiber_g: null,
      sugar_g: null,
      sodium_mg: 0,
      known_core_count: 4,
      baseline: '每 100 克',
      ...summary,
    },
  }
}

function makeResponse(
  values: EnrichedValuesResponse['values'],
): EnrichedValuesResponse {
  return {
    fdc_id: 1,
    display_name: '测试食品',
    baseline: '每 100 克',
    values,
    missing_keys: ['fat_g', 'fiber_g', 'sugar_g'],
    enrichment: { attempted: true, outcome: 'partial', message: '已补全' },
    candidates: [],
    sources_enabled: [],
  }
}

const externalValue = (key: string, value: number | null): EnrichedValuesResponse['values'][number] => ({
  key,
  value,
  origin: 'external',
  status: 'verified_external',
  usda_value: null,
  source_name: 'Open Food Facts',
  source_url: 'https://example.org',
  conversion_method: null,
  original_basis: '每 100 克',
  note: null,
})

describe('missingSummaryKeys', () => {
  it('null 键算缺失，真实 0 不算缺失', () => {
    const summary = makeDetail({}).summary_per_100g
    expect(missingSummaryKeys(summary)).toEqual(['fat_g', 'fiber_g', 'sugar_g'])
  })
})

describe('mergeEnrichment', () => {
  it('只填充缺失键，USDA 已有值与真实 0 不被覆盖', () => {
    const detail = makeDetail({})
    const response = makeResponse([
      externalValue('fat_g', 1.5),
      // protein_g 原值 2 存在，外部值 9 不得覆盖
      externalValue('protein_g', 9),
      // sodium_mg 原值 0 是真实零值，不得覆盖
      externalValue('sodium_mg', 999),
      externalValue('fiber_g', 3),
    ])
    const { detail: merged, filledKeys } = mergeEnrichment(detail, response)
    expect(filledKeys.sort()).toEqual(['fat_g', 'fiber_g'])
    expect(merged.summary_per_100g.fat_g).toBe(1.5)
    expect(merged.summary_per_100g.fiber_g).toBe(3)
    expect(merged.summary_per_100g.protein_g).toBe(2)
    expect(merged.summary_per_100g.sodium_mg).toBe(0)
  })

  it('known_core_count 按填充数递增', () => {
    const detail = makeDetail({})
    const response = makeResponse([externalValue('fat_g', 1.5), externalValue('fiber_g', 3)])
    const { detail: merged } = mergeEnrichment(detail, response)
    expect(merged.summary_per_100g.known_core_count).toBe(6)
  })

  it('candidate_review 与 rejected 值不进入合并', () => {
    const detail = makeDetail({})
    const response = makeResponse([
      { ...externalValue('fiber_g', 3), status: 'candidate_review' },
      { ...externalValue('sugar_g', 4), status: 'rejected' },
    ])
    const { detail: merged, filledKeys } = mergeEnrichment(detail, response)
    expect(filledKeys).toEqual([])
    expect(merged).toBe(detail)
  })

  it('负数与非有限数不进入合并', () => {
    const detail = makeDetail({})
    const response = makeResponse([
      externalValue('fiber_g', -1),
      externalValue('sugar_g', Number.POSITIVE_INFINITY),
    ])
    const { filledKeys } = mergeEnrichment(detail, response)
    expect(filledKeys).toEqual([])
  })

  it('不修改原始对象（query 缓存安全）', () => {
    const detail = makeDetail({})
    const before = { ...detail.summary_per_100g }
    const response = makeResponse([externalValue('fat_g', 1.5)])
    mergeEnrichment(detail, response)
    expect(detail.summary_per_100g).toEqual(before)
  })

  it('未知 key 的外部值被忽略', () => {
    const detail = makeDetail({})
    const response = makeResponse([externalValue('vitamin_c', 10)])
    const { filledKeys } = mergeEnrichment(detail, response)
    expect(filledKeys).toEqual([])
  })
})
