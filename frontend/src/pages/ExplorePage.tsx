import { ArrowUpRight, Check, CircleDashed, Info, Plus, RotateCcw } from 'lucide-react'
import { lazy, Suspense, useEffect, useMemo, useState } from 'react'

import { usePlate } from '@/app/plate/usePlate'
import { FoodDetailDrawer } from '@/components/FoodDetailDrawer'
import { FoodIcon } from '@/components/FoodIcon'
import { PageHeader } from '@/components/PageHeader'
import { EmptyState, ErrorState } from '@/components/StateViews'
import { zhCN } from '@/i18n/zh-CN'
import { isUsableNutrientValue } from '@/lib/calculator'
import { formatAmount } from '@/lib/format'
import { useCategories, useFoodDetails, useFoodList } from '@/lib/queries'
import type { FoodItem } from '@/lib/types'

import type { MapPoint3D } from '@/features/explore/Scatter3DMap'

import styles from './ExplorePage.module.css'

const Scatter3DMap = lazy(() => import('@/features/explore/Scatter3DMap'))

const PAGE_SIZE = 100
const MAX_LOADED = 300
const SEARCH_DEBOUNCE_MS = 300

const DATA_TYPE_OPTIONS = ['foundation_food', 'sr_legacy_food', 'survey_fndds_food'] as const

/**
 * 可用于坐标轴的营养指标集合。
 * 与 CORE_NUTRIENTS 略有不同：多了 sugar_g（FoodSummary 里有）。
 * 不修改 CORE_NUTRIENTS，避免影响餐盘营养合计。
 */
export type AxisKey =
  | 'energy_kcal'
  | 'protein_g'
  | 'fat_g'
  | 'carb_g'
  | 'fiber_g'
  | 'sugar_g'
  | 'sodium_mg'

export interface AxisSpec {
  key: AxisKey
  label: string
  unit: string
  decimals: number
}

const AXIS_OPTIONS: readonly AxisSpec[] = [
  { key: 'energy_kcal', label: '能量', unit: 'kcal', decimals: 0 },
  { key: 'protein_g', label: '蛋白质', unit: 'g', decimals: 1 },
  { key: 'fat_g', label: '脂肪', unit: 'g', decimals: 1 },
  { key: 'carb_g', label: '碳水化合物', unit: 'g', decimals: 1 },
  { key: 'fiber_g', label: '膳食纤维', unit: 'g', decimals: 1 },
  { key: 'sugar_g', label: '糖', unit: 'g', decimals: 1 },
  { key: 'sodium_mg', label: '钠', unit: 'mg', decimals: 0 },
]

const DEFAULT_X: AxisKey = 'protein_g'
const DEFAULT_Y: AxisKey = 'fat_g'
const DEFAULT_Z: AxisKey = 'carb_g'

function AxisSelect({
  label,
  value,
  onChange,
  exclude,
}: {
  label: string
  value: AxisKey
  onChange: (key: AxisKey) => void
  exclude?: AxisKey[]
}) {
  const excludeSet = new Set(exclude ?? [])
  const available = AXIS_OPTIONS.filter((o) => !excludeSet.has(o.key) || o.key === value)
  return (
    <label className={styles.field}>
      <span className={styles.label}>{label}</span>
      <select
        className={styles.select}
        value={value}
        onChange={(event) => onChange(event.target.value as AxisKey)}
      >
        {available.map((item) => (
          <option key={item.key} value={item.key}>
            {item.label}（{item.unit}）
          </option>
        ))}
      </select>
    </label>
  )
}

function axisSpec(key: AxisKey): AxisSpec {
  return AXIS_OPTIONS.find((o) => o.key === key) ?? AXIS_OPTIONS[0]
}

/** 食材三维营养探索地图。 */
export function ExplorePage() {
  const plate = usePlate()

  const [xKey, setXKey] = useState<AxisKey>(DEFAULT_X)
  const [yKey, setYKey] = useState<AxisKey>(DEFAULT_Y)
  const [zKey, setZKey] = useState<AxisKey>(DEFAULT_Z)

  const [dataType, setDataType] = useState('')
  const [category, setCategory] = useState('')
  const [input, setInput] = useState('')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const [loaded, setLoaded] = useState<FoodItem[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [drawerId, setDrawerId] = useState<number | null>(null)
  const [resetKey, setResetKey] = useState(0)

  const categories = useCategories()

  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(input.trim()), SEARCH_DEBOUNCE_MS)
    return () => window.clearTimeout(timer)
  }, [input])

  useEffect(() => {
    setLoaded([])
    setPage(1)
    setSelectedId(null)
  }, [query, dataType, category])

  const list = useFoodList({
    q: query || undefined,
    category_code: category || undefined,
    data_type: dataType || undefined,
    library_scope: 'default',
    page,
    page_size: PAGE_SIZE,
    sort: 'relevance',
  })

  const total = list.data?.total ?? 0

  useEffect(() => {
    const items = list.data?.items
    if (!items || items.length === 0) return
    setLoaded((current) => {
      const seen = new Set(current.map((food) => food.fdc_id))
      const merged = [...current]
      for (const food of items) {
        if (!seen.has(food.fdc_id) && merged.length < MAX_LOADED) {
          seen.add(food.fdc_id)
          merged.push(food)
        }
      }
      return merged
    })
  }, [list.data])

  const details = useFoodDetails(loaded.map((food) => food.fdc_id), 'default')

  const stats = useMemo(() => {
    const points: MapPoint3D[] = []
    let excluded = 0
    let failed = 0
    let pending = 0

    loaded.forEach((food, index) => {
      const result = details[index]
      if (!result || result.isPending) {
        pending += 1
        return
      }
      if (result.isError) {
        failed += 1
        return
      }
      const summary = result.data?.summary_per_100g
      const x = summary?.[xKey]
      const y = summary?.[yKey]
      const z = summary?.[zKey]
      if (!isUsableNutrientValue(x) || !isUsableNutrientValue(y) || !isUsableNutrientValue(z)) {
        excluded += 1
        return
      }
      points.push({ food, x: x as number, y: y as number, z: z as number })
    })

    return { points, excluded, failed, pending }
  }, [loaded, details, xKey, yKey, zKey])

  const xSpec = axisSpec(xKey)
  const ySpec = axisSpec(yKey)
  const zSpec = axisSpec(zKey)

  const selected = stats.points.find((point) => point.food.fdc_id === selectedId) ?? null
  const canLoadMore = loaded.length < Math.min(total, MAX_LOADED) && !list.isPending

  const categoryOptions = useMemo(() => {
    return (categories.data?.items ?? [])
      .filter((item) => item.category_code)
      .map((item) => ({ value: item.category_code as string, label: item.name_zh }))
  }, [categories.data])

  const handleResetView = () => setResetKey((k) => k + 1)

  return (
    <div className={styles.page}>
      <PageHeader
        title={zhCN.explore.title}
        subtitle={zhCN.explore.subtitle}
        aside={
          <span className={styles.loadedNote}>
            {total > 0 ? zhCN.explore.loadedNote(loaded.length, total) : ''}
          </span>
        }
      />

      <section className={styles.controls} aria-label={zhCN.explore.title}>
        <AxisSelect label={zhCN.explore.xLabel} value={xKey} onChange={setXKey} exclude={[yKey, zKey]} />
        <AxisSelect label={zhCN.explore.yLabel} value={yKey} onChange={setYKey} exclude={[xKey, zKey]} />
        <AxisSelect label={zhCN.explore.zLabel} value={zKey} onChange={setZKey} exclude={[xKey, yKey]} />

        <label className={styles.field}>
          <span className={styles.label}>{zhCN.explore.dataTypeLabel}</span>
          <select
            className={styles.select}
            value={dataType}
            onChange={(event) => setDataType(event.target.value)}
          >
            <option value="">{zhCN.explore.allDataTypes}</option>
            {DATA_TYPE_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {zhCN.dataType[option]?.label ?? option}
              </option>
            ))}
          </select>
        </label>

        <label className={styles.field}>
          <span className={styles.label}>{zhCN.explore.categoryLabel}</span>
          <select
            className={styles.select}
            value={category}
            onChange={(event) => setCategory(event.target.value)}
          >
            <option value="">{zhCN.explore.allCategories}</option>
            {categoryOptions.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </label>

        <label className={`${styles.field} ${styles.searchField}`}>
          <span className={styles.label}>{zhCN.library.searchPlaceholder}</span>
          <input
            className={styles.searchInput}
            type="search"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder={zhCN.explore.searchPlaceholder}
            autoComplete="off"
          />
        </label>
      </section>

      <p className={styles.note}>
        <Info size={14} strokeWidth={1.8} aria-hidden="true" />
        {zhCN.explore.loadMoreHint}
      </p>

      {list.isPending && loaded.length === 0 ? (
        <p className={styles.loadingText}>{zhCN.explore.loadingList}</p>
      ) : null}

      {list.isError ? (
        <ErrorState
          message={list.error instanceof Error ? list.error.message : zhCN.errors.generic}
          onRetry={() => void list.refetch()}
        />
      ) : null}

      {list.data && total === 0 ? (
        <EmptyState title={zhCN.library.emptyTitle} description={zhCN.library.emptyDesc} />
      ) : null}

      {loaded.length > 0 ? (
        <section className={styles.chartCard} aria-label={zhCN.explore.chartTitle3D(xSpec.label, ySpec.label, zSpec.label)}>
          <header className={styles.chartHeader}>
            <div>
              <h2 className={styles.chartTitle}>{zhCN.explore.chartTitle3D(xSpec.label, ySpec.label, zSpec.label)}</h2>
              <p className={styles.chartDesc3D}>{zhCN.explore.chartDesc3D}</p>
            </div>
            <div className={styles.chartStats}>
              <span className={styles.statChip}>{zhCN.explore.pointCount(stats.points.length)}</span>
              {stats.excluded > 0 ? (
                <span className={styles.statChip}>{zhCN.explore.excluded(stats.excluded)}</span>
              ) : null}
              {stats.failed > 0 ? (
                <span className={`${styles.statChip} ${styles.statWarn}`}>
                  {zhCN.explore.failed(stats.failed)}
                </span>
              ) : null}
              {stats.pending > 0 ? (
                <span className={styles.statChip}>{zhCN.explore.loadingPoints(stats.pending)}</span>
              ) : null}
            </div>
          </header>

          <div className={styles.chartActions}>
            <button type="button" className={styles.textButton} onClick={handleResetView}>
              <RotateCcw size={14} aria-hidden="true" />
              {zhCN.explore.resetView}
            </button>
            <span className={styles.hintText}>{zhCN.explore.dragHint}</span>
          </div>

          {stats.points.length === 0 && stats.pending === 0 ? (
            <div className={styles.chartEmpty}>
              <CircleDashed size={28} strokeWidth={1.6} aria-hidden="true" />
              <p>{zhCN.explore.chartEmpty3D}</p>
            </div>
          ) : (
            <Suspense
              fallback={
                <div className={styles.chartEmpty} role="status">
                  <CircleDashed size={28} strokeWidth={1.6} aria-hidden="true" />
                  <p>{zhCN.explore.loadingChart}</p>
                </div>
              }
            >
              <Scatter3DMap
                points={stats.points}
                xSpec={xSpec}
                ySpec={ySpec}
                zSpec={zSpec}
                selectedId={selectedId}
                resetKey={resetKey}
                loading={stats.pending > 0}
                onSelect={(food) => setSelectedId(food.fdc_id)}
              />
            </Suspense>
          )}

          <footer className={styles.chartFooter}>
            {canLoadMore ? (
              <button
                type="button"
                className={styles.loadMoreButton}
                onClick={() => setPage((value) => value + 1)}
              >
                {zhCN.explore.loadMore}
              </button>
            ) : null}
          </footer>

          {selected ? (
            <div className={styles.detailBar}>
              <FoodIcon
                food={selected.food}
                size={40}
                label={zhCN.a11y.foodIcon(selected.food.display_name || selected.food.description_en)}
              />
              <div className={styles.detailInfo}>
                <strong>{selected.food.display_name || selected.food.description_en}</strong>
                <span className={styles.detailValues}>
                  {xSpec.label} {formatAmount(selected.x, xSpec.decimals)} {xSpec.unit} · {ySpec.label}{' '}
                  {formatAmount(selected.y, ySpec.decimals)} {ySpec.unit} · {zSpec.label}{' '}
                  {formatAmount(selected.z, zSpec.decimals)} {zSpec.unit}（{zhCN.common.per100g}）
                </span>
              </div>
              <div className={styles.detailActions}>
                <button
                  type="button"
                  className={styles.textButton}
                  onClick={() => setDrawerId(selected.food.fdc_id)}
                >
                  {zhCN.common.viewDetail}
                  <ArrowUpRight size={14} aria-hidden="true" />
                </button>
                <button
                  type="button"
                  className={styles.addButton}
                  onClick={() => plate.add(selected.food)}
                  disabled={plate.has(selected.food)}
                >
                  {plate.has(selected.food) ? (
                    <Check size={14} aria-hidden="true" />
                  ) : (
                    <Plus size={14} aria-hidden="true" />
                  )}
                  {plate.has(selected.food) ? zhCN.explore.inPlate : zhCN.explore.addToPlate}
                </button>
              </div>
            </div>
          ) : null}
        </section>
      ) : null}

      <FoodDetailDrawer
        foodKey={drawerId}
        scope="default"
        onClose={() => setDrawerId(null)}
      />
    </div>
  )
}
