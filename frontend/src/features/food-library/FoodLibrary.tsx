import { Search } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import { EmptyState, ErrorState, LoadingCards } from '@/components/StateViews'
import { FoodLibraryCard } from '@/features/food-library/FoodLibraryCard'
import { zhCN } from '@/i18n/zh-CN'
import { useCategories, useFoodList } from '@/lib/queries'
import type { FoodItem, SortOption, UsageClass } from '@/lib/types'

import styles from './FoodLibrary.module.css'

const PAGE_SIZE = 12
const SEARCH_DEBOUNCE_MS = 250

const DATA_TYPE_OPTIONS = ['foundation_food', 'sr_legacy_food', 'survey_fndds_food'] as const

const USAGE_CLASSES = [
  'basic_ingredient',
  'processed_ingredient',
  'prepared_dish',
  'ready_to_eat',
  'unknown',
] as const satisfies readonly UsageClass[]

/** 用途下拉：'' 表示默认范围（基础+加工），'all' 表示全部用途，其余为精确用途类别。 */
type UsageFilterValue = '' | 'all' | UsageClass

interface FoodLibraryProps {
  onOpen: (food: FoodItem) => void
  /** 传入后卡片「加入」按钮改为自定义动作（例如加入计划餐次），默认加入餐盘。 */
  onAddFood?: (food: FoodItem) => void
  addLabel?: string
  /** 自定义动作下的已加入判断（例如该食品已在本餐次）。 */
  isAdded?: (food: FoodItem) => boolean
}

/** 左侧食材库：搜索、筛选、浏览、加入餐盘。仅使用默认基础食材库。 */
export function FoodLibrary({ onOpen, onAddFood, addLabel, isAdded }: FoodLibraryProps) {
  const [input, setInput] = useState('')
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('')
  const [dataType, setDataType] = useState('')
  const [usage, setUsage] = useState<UsageFilterValue>('')
  const [sort, setSort] = useState<SortOption>('relevance')
  const [page, setPage] = useState(1)

  const categories = useCategories()

  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(input.trim()), SEARCH_DEBOUNCE_MS)
    return () => window.clearTimeout(timer)
  }, [input])

  useEffect(() => {
    setPage(1)
  }, [query, category, dataType, usage, sort])

  const usageParams =
    usage === 'all'
      ? { usage_scope: 'all' as const }
      : usage === ''
        ? { usage_scope: 'ingredients' as const }
        : { usage_class: usage }

  const list = useFoodList({
    q: query || undefined,
    category_code: category || undefined,
    data_type: dataType || undefined,
    library_scope: 'default',
    ...usageParams,
    page,
    page_size: PAGE_SIZE,
    sort,
  })

  const groupedCategories = useMemo(() => {
    const groups = new Map<string, { value: string; label: string }[]>()
    for (const item of categories.data?.items ?? []) {
      if (!item.category_code) continue
      const source = item.category_source
      const bucket = groups.get(source) ?? []
      bucket.push({ value: item.category_code, label: item.name_zh })
      groups.set(source, bucket)
    }
    return groups
  }, [categories.data])

  const total = list.data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  useEffect(() => {
    if (list.data && page > totalPages) setPage(totalPages)
  }, [list.data, page, totalPages])

  const resetFilters = () => {
    setInput('')
    setQuery('')
    setCategory('')
    setDataType('')
    setUsage('')
    setSort('relevance')
    setPage(1)
  }

  const showRefetching = list.isFetching && !list.isPending
  const usageHint =
    usage === ''
      ? zhCN.library.usageHintDefault
      : usage === 'all'
        ? zhCN.library.usageHintAll
        : zhCN.library.usageHintClass(zhCN.usageClass[usage]?.label ?? usage)

  return (
    <section className={styles.panel} aria-label={zhCN.library.title}>
      <div className={styles.toolbar}>
        <label className={styles.search}>
          <Search size={16} strokeWidth={1.8} aria-hidden="true" className={styles.searchIcon} />
          <span className="visuallyHidden">{zhCN.library.searchPlaceholder}</span>
          <input
            className={styles.searchInput}
            type="search"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder={zhCN.library.searchPlaceholder}
            autoComplete="off"
          />
        </label>

        <div className={styles.filters}>
          <label className={styles.field}>
            <span className={styles.label}>{zhCN.library.categoryLabel}</span>
            <select
              className={styles.select}
              value={category}
              onChange={(event) => setCategory(event.target.value)}
            >
              <option value="">{zhCN.library.allCategories}</option>
              {[...groupedCategories.entries()].map(([source, items]) => (
                <optgroup
                  key={source}
                  label={
                    source === 'wweia'
                      ? zhCN.drawer.categorySourceWweia
                      : zhCN.drawer.categorySourceFdc
                  }
                >
                  {items.map((item) => (
                    <option key={`${source}-${item.value}`} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </label>

          <label className={styles.field}>
            <span className={styles.label}>{zhCN.library.dataTypeLabel}</span>
            <select
              className={styles.select}
              value={dataType}
              onChange={(event) => setDataType(event.target.value)}
            >
              <option value="">{zhCN.library.allDataTypes}</option>
              {DATA_TYPE_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {zhCN.dataType[option]?.label ?? option}
                </option>
              ))}
            </select>
          </label>

          <label className={styles.field}>
            <span className={styles.label}>{zhCN.library.usageLabel}</span>
            <select
              className={styles.select}
              value={usage}
              onChange={(event) => setUsage(event.target.value as UsageFilterValue)}
            >
              <option value="">{zhCN.library.usageScopeIngredients}</option>
              <option value="all">{zhCN.library.usageScopeAll}</option>
              <optgroup label={zhCN.library.usageScopeClassGroup}>
                {USAGE_CLASSES.map((option) => (
                  <option key={option} value={option}>
                    {zhCN.usageClass[option]?.label ?? option}
                  </option>
                ))}
              </optgroup>
            </select>
          </label>

          <label className={styles.field}>
            <span className={styles.label}>{zhCN.library.sortLabel}</span>
            <select
              className={styles.select}
              value={sort}
              onChange={(event) => setSort(event.target.value as SortOption)}
            >
              <option value="relevance">{zhCN.library.sortRelevance}</option>
              <option value="alpha_zh">{zhCN.library.sortAlphaZh}</option>
              <option value="alpha_en">{zhCN.library.sortAlphaEn}</option>
            </select>
          </label>
        </div>

        <div className={styles.resultBar} aria-live="polite">
          <span>{total > 0 ? zhCN.library.resultsLabel(total) : ''}</span>
          {showRefetching ? <span className={styles.searching}>{zhCN.library.searching}</span> : null}
        </div>
        <p className={styles.usageHint}>{usageHint}</p>
      </div>

      <div className={styles.results}>
        {list.isPending ? <LoadingCards count={6} /> : null}

        {list.isError ? (
          <ErrorState
            message={list.error instanceof Error ? list.error.message : zhCN.errors.generic}
            onRetry={() => void list.refetch()}
          />
        ) : null}

        {list.data && list.data.items.length === 0 ? (
          <EmptyState
            title={zhCN.library.emptyTitle}
            description={zhCN.library.emptyDesc}
            action={
              <button type="button" className={styles.resetButton} onClick={resetFilters}>
                {zhCN.library.resetFilters}
              </button>
            }
          />
        ) : null}

        {list.data?.items.map((food) => (
          <FoodLibraryCard
            key={`${food.library_scope}-${food.fdc_id}`}
            food={food}
            onOpen={onOpen}
            onAddFood={onAddFood}
            addLabel={addLabel}
            isAdded={isAdded ? isAdded(food) : undefined}
          />
        ))}
      </div>

      {list.data && total > 0 ? (
        <nav className={styles.pagination} aria-label={zhCN.library.title}>
          <button
            type="button"
            className={styles.pageButton}
            onClick={() => setPage((value) => Math.max(1, value - 1))}
            disabled={page <= 1}
          >
            {zhCN.common.prevPage}
          </button>
          <span className={styles.pageInfo}>
            {zhCN.common.pageOf(Math.min(page, totalPages), totalPages)}
          </span>
          <button
            type="button"
            className={styles.pageButton}
            onClick={() => setPage((value) => Math.min(totalPages, value + 1))}
            disabled={page >= totalPages}
          >
            {zhCN.common.nextPage}
          </button>
        </nav>
      ) : null}
    </section>
  )
}
