export type LibraryScope = 'default' | 'branded'

export type DataType =
  | 'foundation_food'
  | 'sr_legacy_food'
  | 'survey_fndds_food'
  | 'branded_food'

export type SortOption = 'relevance' | 'alpha_zh' | 'alpha_en'

/** 产品用途分类，独立于 USDA data_type 与中文映射状态。 */
export type UsageClass =
  | 'basic_ingredient'
  | 'processed_ingredient'
  | 'prepared_dish'
  | 'ready_to_eat'
  | 'unknown'

/** 默认搜索范围：ingredients 只含基础与加工食材；all 含全部用途类别。 */
export type UsageScope = 'ingredients' | 'all'

export interface FoodItem {
  fdc_id: number
  data_type: DataType | string
  source_dataset: string
  source_version: string
  description_en: string
  name_zh: string | null
  display_name: string
  zh_status: 'verified' | 'glossary' | 'none' | string
  zh_review_status: 'verified' | 'pending' | string
  category_code: string | null
  category_en: string | null
  category_zh: string | null
  brand_owner: string | null
  brand_name: string | null
  gtin_upc: string | null
  serving_size: number | null
  serving_unit: string | null
  household_serving: string | null
  publication_date: string | null
  is_default_library: boolean
  library_scope: LibraryScope
  usage_class: UsageClass | string | null
  usage_rule_source: string | null
  usage_rule_id: string | null
  usage_reason: string | null
}

export interface FoodPortion {
  fdc_id: number
  amount: number | null
  modifier: string | null
  portion_description: string | null
  gram_weight: number | null
  unit_name: string | null
  quality_flag: string
}

export interface FoodAlias {
  alias: string
  alias_type: string
  status: string
  review_status: string
}

export interface FoodSummary {
  energy_kcal: number | null
  protein_g: number | null
  fat_g: number | null
  carb_g: number | null
  fiber_g: number | null
  sugar_g: number | null
  sodium_mg: number | null
  known_core_count: number
  baseline: string
}

export interface QualityEvent {
  event_type: string
  nutrient_id: number | null
  raw_amount: number | null
  detail: string | null
}

export interface FoodDetail extends FoodItem {
  portions: FoodPortion[]
  aliases: FoodAlias[]
  summary_per_100g: FoodSummary
  quality_events: QualityEvent[]
}

export interface NutrientItem {
  nutrient_id: number
  origin_nutrient_id: number | null
  name_en: string
  name_zh: string
  unit_en: string
  unit_zh: string
  decimals: number
  is_core: boolean
  baseline: string
  amount: number | null
  raw_amount: number | null
  quality_flag: string
  is_available: boolean
}

export interface FoodNutrientsResponse {
  fdc_id: number
  display_name: string
  baseline: string
  total_nutrients_returned: number
  missing_count: number
  nutrients: NutrientItem[]
}

export interface CategoryItem {
  category_source: string
  category_code: string | null
  name_en: string | null
  name_zh: string
}

export interface CategoriesResponse {
  total: number
  items: CategoryItem[]
}

export interface NutrientMetaItem {
  nutrient_id: number
  nbr: string
  name_en: string
  name_zh: string
  unit_en: string
  unit_zh: string
  group_zh: string
  decimals: number
  is_core: boolean
  baseline: string
}

export interface NutrientMetaResponse {
  total: number
  items: NutrientMetaItem[]
}

export interface HealthResponse {
  status: 'ok' | 'degraded' | 'error' | string
  default_db_exists: boolean
  branded_db_exists: boolean
  default_db_path: string
  branded_db_path: string
  food_count: number | null
  nutrient_row_count: number | null
  error: string | null
}

export interface FoodListParams {
  q?: string
  category_code?: string
  data_type?: string
  library_scope?: LibraryScope
  usage_scope?: UsageScope
  usage_class?: UsageClass
  page?: number
  page_size?: number
  sort?: SortOption
}

export interface FoodListResponse {
  page: number
  page_size: number
  total: number
  usage_scope: UsageScope
  usage_class: UsageClass | null
  items: FoodItem[]
}

/** 补全解析结果中单个营养指标值的来源。 */
export type EnrichOrigin = 'usda' | 'external' | 'none'

/** 补全值的核实状态：usda=原始值；verified_external=已核实外部值；candidate_review=候选待确认。 */
export type EnrichValueStatus =
  | 'usda'
  | 'none'
  | 'verified_external'
  | 'candidate_review'
  | 'rejected'

/** 补全尝试结果：enriched=全部补齐；partial=部分补齐；not_found=未找到可靠来源；error=服务不可用。 */
export type EnrichOutcome =
  | 'no_missing'
  | 'disabled'
  | 'enriched'
  | 'partial'
  | 'not_found'
  | 'error'
  | 'cached'

export interface EnrichedValue {
  key: string
  value: number | null
  origin: EnrichOrigin | string
  status: EnrichValueStatus | string
  usda_value: number | null
  source_name: string | null
  source_url: string | null
  conversion_method: string | null
  original_basis: string | null
  note: string | null
  /** nutrient 元数据（后端按项目键附带，供渲染非核心补全行）。 */
  nutrient_id?: number | null
  name_zh?: string | null
  unit_zh?: string | null
  decimals?: number | null
}

export interface EnrichmentCandidate {
  source_name: string
  external_name_en: string
  match_level: 'exact' | 'similar' | 'partial' | 'none' | string
  source_url: string | null
  nutrient_key: string | null
  note: string | null
}

export interface EnrichmentSourceStatus {
  name: string
  enabled: boolean
  reason: string
}

export interface EnrichmentAttempt {
  attempted: boolean
  outcome: EnrichOutcome | string
  message: string
}

/** GET /api/enrichment/foods/{fdc_id}/resolved 的响应。 */
export interface EnrichedValuesResponse {
  fdc_id: number
  display_name: string
  baseline: string
  values: EnrichedValue[]
  missing_keys: string[]
  enrichment: EnrichmentAttempt
  candidates: EnrichmentCandidate[]
  sources_enabled: EnrichmentSourceStatus[]
}

// ---------------------------------------------------------------- 每周计划

/** 餐次类型：三个主餐次 + 可重复的加餐。 */
export type MealType = 'breakfast' | 'lunch' | 'dinner' | 'snack'

/** 计划中的食品引用：food_key + library_scope 共同标识食品身份。 */
export interface PlannerItem {
  item_id: number
  food_key: string
  library_scope: LibraryScope
  amount_g: number
  sort_order: number
  name_snapshot: string | null
}

export interface PlannerMeal {
  meal_id: number
  meal_date: string
  meal_type: MealType
  meal_name: string
  sort_order: number
  notes: string | null
  items: PlannerItem[]
}

export interface PlannerDay {
  date: string
  meals: PlannerMeal[]
}

/** GET /api/planner/plans/{week_start} 的响应；未保存时 plan_id 为 null。 */
export interface WeeklyPlanResponse {
  week_start: string
  plan_id: number | null
  created_at: string | null
  updated_at: string | null
  days: PlannerDay[]
}

export interface PlannerItemInput {
  food_key: string
  library_scope: LibraryScope
  amount_g: number
  sort_order?: number
  name_snapshot?: string | null
}

export interface PlannerMealInput {
  meal_type: MealType
  meal_name?: string | null
  sort_order?: number
  notes?: string | null
  items?: PlannerItemInput[]
}

export interface PlannerDayInput {
  date: string
  meals: PlannerMealInput[]
}

/** PUT /api/planner/plans/{week_start} 的请求体（整周覆盖保存）。 */
export interface WeeklyPlanInput {
  days: PlannerDayInput[]
}

/** POST /api/planner/entries 的请求体（从食品详情直接加入某天某餐）。 */
export interface PlanEntryInput {
  meal_date: string
  meal_type: MealType
  food_key: string
  library_scope: LibraryScope
  amount_g: number
  name_snapshot?: string | null
}

/** POST /api/planner/entries/batch 的请求体（把多个食品一次加入某天某餐，例如整盘加入）。 */
export interface PlanBatchEntryInput {
  meal_date: string
  meal_type: MealType
  items: PlannerItemInput[]
}
