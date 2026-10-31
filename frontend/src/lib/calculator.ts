/**
 * 餐盘营养本地计算器。
 *
 * 数据来源：后端 /api/foods/{key} 返回的 summary_per_100g（已按质量规则聚合）。
 * 计算基准：每 100 克可食部。实际贡献 = 每 100 克值 × 克重 ÷ 100。
 *
 * 关键约定（与项目规则一致）：
 * - summary 中 amount === null 表示该营养素数据库无行，计入“缺失”，不参与累加。
 * - amount === 0 是真实零值，参与累加（贡献为 0）。
 * - 负数或非有限数视为异常，不计入累加并视为缺失。
 * - 合计只等于“已知贡献之和”；当存在缺失食材时，不把已知部分宣称为完整总量，
 *   而是标记为 partial，同时返回 knownValue 供界面展示“已知贡献”。
 */

import type { FoodItem, FoodPortion, FoodSummary } from '@/lib/types'

export const CORE_NUTRIENT_KEYS = [
  'energy_kcal',
  'protein_g',
  'fat_g',
  'carb_g',
  'fiber_g',
  'sodium_mg',
] as const

export type CoreNutrientKey = (typeof CORE_NUTRIENT_KEYS)[number]

export interface CoreNutrientSpec {
  key: CoreNutrientKey
  label: string
  unit: string
  decimals: number
}

/** 核心营养指标的展示规格：名称、单位、小数位。 */
export const CORE_NUTRIENTS: readonly CoreNutrientSpec[] = [
  { key: 'energy_kcal', label: '能量', unit: 'kcal', decimals: 0 },
  { key: 'protein_g', label: '蛋白质', unit: 'g', decimals: 1 },
  { key: 'fat_g', label: '脂肪', unit: 'g', decimals: 1 },
  { key: 'carb_g', label: '碳水化合物', unit: 'g', decimals: 1 },
  { key: 'fiber_g', label: '膳食纤维', unit: 'g', decimals: 1 },
  { key: 'sodium_mg', label: '钠', unit: 'mg', decimals: 0 },
]

/** 单个餐盘食材在计算时所需的最小信息。 */
export interface PlateIngredient {
  /** 稳定标识，用于调试与追溯，不参与计算。 */
  foodKey: string
  /** 当前克重，必须为正数。 */
  grams: number
  /** 后端返回的每 100 克核心营养摘要。 */
  summary: FoodSummary
}

/** 餐盘条目（组件层使用）。 */
export interface PlateEntry {
  food: FoodItem
  grams: number
}

/** 生成餐盘条目的稳定键：食材库 + FDC ID。 */
export function plateKey(food: FoodItem): string {
  return `${food.library_scope}-${food.fdc_id}`
}

/**
 * 添加食材到餐盘。
 * 重复添加同一食品时保留已有条目及其克重，不覆盖、不新增。
 * 超过上限时拒绝新增。
 */
export function addPlateEntry(
  current: PlateEntry[],
  food: FoodItem,
  options: { maxItems: number; defaultGrams: number },
): PlateEntry[] {
  if (current.some((entry) => plateKey(entry.food) === plateKey(food))) return current
  if (current.length >= options.maxItems) return current
  return [...current, { food, grams: options.defaultGrams }]
}

/** 从餐盘移除指定食品。 */
export function removePlateEntry(current: PlateEntry[], food: FoodItem): PlateEntry[] {
  return current.filter((entry) => plateKey(entry.food) !== plateKey(food))
}

export type NutritionStatus = 'complete' | 'partial' | 'all_missing'

export interface NutrientResult {
  key: CoreNutrientKey
  label: string
  unit: string
  decimals: number
  /**
   * 完整总量：仅当所有食材都有该营养数据时为已知贡献之和；
   * 存在缺失时为 null，避免把已知部分宣称为完整总量。
   */
  total: number | null
  /** 已知贡献之和（无论是否有缺失），用于界面显示“已知部分”。 */
  knownValue: number
  status: NutritionStatus
  missingCount: number
  totalCount: number
}

/** 单食材最大克重上限，用于拒绝明显不合理的输入。 */
export const MAX_GRAMS_PER_INGREDIENT = 10000

/** 餐盘最多暂存的食材种类。 */
export const MAX_PLATE_ITEMS = 8

/** 新食材加入餐盘时的默认克重。 */
export const DEFAULT_PLATE_GRAMS = 100

/**
 * 解析克重输入。
 * 返回 null 表示输入无效（空、非数字、非正数、超出上限）。
 */
export function parseGrams(raw: string): number | null {
  const trimmed = String(raw ?? '').trim()
  if (trimmed === '') return null
  const value = Number(trimmed)
  if (!Number.isFinite(value)) return null
  if (value <= 0) return null
  if (value > MAX_GRAMS_PER_INGREDIENT) return null
  return value
}

/**
 * 判断一个营养值是否可用于合计。
 * null / 非有限数 / 负数 → 不可用（视为缺失）。
 * 0 是真实零值，返回 true。
 */
export function isUsableNutrientValue(value: number | null | undefined): boolean {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0
}

/**
 * 计算一餐的核心营养合计。
 * 对每个核心营养指标分别统计：哪些食材有值、哪些缺失。
 */
export function computePlateNutrition(entries: PlateIngredient[]): NutrientResult[] {
  return CORE_NUTRIENTS.map((spec) => {
    let knownValue = 0
    let missingCount = 0

    for (const entry of entries) {
      const value = entry.summary[spec.key]
      if (!isUsableNutrientValue(value)) {
        missingCount += 1
        continue
      }
      knownValue += (value as number) * entry.grams / 100
    }

    const totalCount = entries.length
    let status: NutritionStatus
    if (totalCount === 0) {
      status = 'all_missing'
    } else if (missingCount === 0) {
      status = 'complete'
    } else if (missingCount >= totalCount) {
      status = 'all_missing'
    } else {
      status = 'partial'
    }

    return {
      key: spec.key,
      label: spec.label,
      unit: spec.unit,
      decimals: spec.decimals,
      total: status === 'complete' ? knownValue : null,
      knownValue,
      status,
      missingCount,
      totalCount,
    }
  })
}

/**
 * 从后端返回的 portions[] 中筛选出“可用于自动填充克数”的份量。
 * 条件：gram_weight 为正数、且 quality_flag === 'ok'。
 * 品牌食品通常没有 food_portion，这里会返回空数组，界面据此显示“手动输入克数”。
 */
export function getUsablePortions(portions: FoodPortion[]): FoodPortion[] {
  return portions.filter(
    (portion) =>
      portion.gram_weight !== null &&
      typeof portion.gram_weight === 'number' &&
      Number.isFinite(portion.gram_weight) &&
      portion.gram_weight > 0 &&
      portion.quality_flag === 'ok',
  )
}

/**
 * 生成份量下拉项的显示文本，严格使用接口真实字段。
 * 例如：“1 个, 中等 = 150 g” 或 “杯, 切碎 = 100 g”。
 */
export function formatPortionLabel(portion: FoodPortion): string {
  const desc = portion.portion_description ?? portion.modifier ?? '份量'
  const amountPart =
    portion.amount !== null && Number.isFinite(portion.amount) ? ` ${portion.amount}` : ''
  const unitPart = portion.unit_name ? ` ${portion.unit_name}` : ''
  return `${desc}${amountPart}${unitPart} = ${portion.gram_weight} g`
}
