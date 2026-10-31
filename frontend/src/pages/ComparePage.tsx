import { CalendarPlus, Camera, Trash2 } from 'lucide-react'
import { useMemo, useState } from 'react'

import { usePlate } from '@/app/plate/usePlate'
import { usePlans } from '@/app/plans/usePlans'
import { FoodIcon } from '@/components/FoodIcon'
import { PageHeader } from '@/components/PageHeader'
import { EmptyState } from '@/components/StateViews'
import { zhCN } from '@/i18n/zh-CN'
import {
  computePlateNutrition,
  plateKey,
  type NutrientResult,
  type PlateEntry,
  type PlateIngredient,
} from '@/lib/calculator'
import { formatAmount } from '@/lib/format'
import type { FoodDetail } from '@/lib/types'

import { MetricCompareChart, type MetricCompareRow } from '@/features/compare/MetricCompareChart'
import { usePlateFoodDetails } from '@/features/designer/usePlateFoodDetails'
import { AddPlateToPlanDialog } from '@/features/planner/AddPlateToPlanDialog'

import styles from './ComparePage.module.css'

type SlotId = 'A' | 'B'

function foodName(entry: PlateEntry): string {
  return entry.food.display_name || entry.food.description_en
}

function toIngredients(entries: PlateEntry[], details: Map<string, FoodDetail>): PlateIngredient[] {
  return entries
    .map((entry) => {
      const detail = details.get(plateKey(entry.food))
      if (!detail) return null
      return {
        foodKey: plateKey(entry.food),
        grams: entry.grams,
        summary: detail.summary_per_100g,
      }
    })
    .filter((entry): entry is PlateIngredient => entry !== null)
}

function SlotCard({
  slot,
  snapshot,
  results,
  onCapture,
  onClear,
  onAddToPlan,
  plateEmpty,
}: {
  slot: SlotId
  snapshot: PlateEntry[] | null
  results: NutrientResult[] | null
  onCapture: () => void
  onClear: () => void
  onAddToPlan: () => void
  plateEmpty: boolean
}) {
  const slotName = slot === 'A' ? zhCN.compare.slotA : zhCN.compare.slotB
  return (
    <section className={styles.slot} aria-label={slotName}>
      <header className={styles.slotHeader}>
        <h2 className={styles.slotTitle}>{slotName}</h2>
        <div className={styles.slotActions}>
          <button
            type="button"
            className={styles.captureButton}
            onClick={onCapture}
            disabled={plateEmpty}
            title={plateEmpty ? zhCN.compare.plateEmptyWarn : zhCN.compare.capture(slotName)}
          >
            <Camera size={14} aria-hidden="true" />
            {snapshot ? zhCN.compare.replace : zhCN.compare.capture(slotName)}
          </button>
          {snapshot && snapshot.length > 0 ? (
            <button
              type="button"
              className={styles.captureButton}
              onClick={onAddToPlan}
              title={zhCN.planner.plateToPlanTitle(slotName)}
            >
              <CalendarPlus size={14} aria-hidden="true" />
              {zhCN.planner.plateToPlanAction}
            </button>
          ) : null}
          {snapshot ? (
            <button type="button" className={styles.clearButton} onClick={onClear}>
              <Trash2 size={14} aria-hidden="true" />
              {zhCN.compare.clear}
            </button>
          ) : null}
        </div>
      </header>

      {snapshot === null ? (
        <EmptyState title={zhCN.compare.emptySlot(slotName)} description={zhCN.compare.emptyDesc} />
      ) : snapshot.length === 0 ? (
        <EmptyState title={zhCN.compare.emptySlot(slotName)} description={zhCN.compare.plateEmptyWarn} />
      ) : (
        <>
          <p className={styles.slotMeta}>{zhCN.compare.captured(slotName, snapshot.length)}</p>
          <ul className={styles.ingredientList}>
            {snapshot.map((entry) => (
              <li key={plateKey(entry.food)} className={styles.ingredient}>
                <FoodIcon food={entry.food} size={26} label={zhCN.a11y.foodIcon(foodName(entry))} />
                <span className={styles.ingredientName}>{foodName(entry)}</span>
                <span className={styles.ingredientGrams}>{formatAmount(entry.grams, 0)} g</span>
              </li>
            ))}
          </ul>
          {results ? (
            <dl className={styles.summaryGrid}>
              {results.map((result) => (
                <div key={result.key} className={styles.summaryItem}>
                  <dt>{result.label}</dt>
                  <dd>
                    {result.status === 'complete'
                      ? `${formatAmount(result.total, result.decimals)} ${result.unit}`
                      : result.status === 'partial'
                        ? `${zhCN.designer.knownPrefix}${formatAmount(result.knownValue, result.decimals)} ${result.unit}`
                        : zhCN.common.notAvailable}
                  </dd>
                </div>
              ))}
            </dl>
          ) : null}
        </>
      )}
    </section>
  )
}

/** 方案对比：两套餐盘快照的真实营养差异与食材来源。 */
export function ComparePage() {
  const plate = usePlate()
  const plans = usePlans()
  const slotA = plans.slotA?.entries ?? null
  const slotB = plans.slotB?.entries ?? null
  const [planDialog, setPlanDialog] = useState<{ slot: SlotId; entries: PlateEntry[] } | null>(null)

  const allEntries = useMemo(() => {
    const map = new Map<string, PlateEntry>()
    for (const entry of slotA ?? []) map.set(plateKey(entry.food), entry)
    for (const entry of slotB ?? []) map.set(plateKey(entry.food), entry)
    return [...map.values()]
  }, [slotA, slotB])

  const { details } = usePlateFoodDetails(allEntries)

  const resultsA = useMemo(
    () => (slotA ? computePlateNutrition(toIngredients(slotA, details)) : null),
    [slotA, details],
  )
  const resultsB = useMemo(
    () => (slotB ? computePlateNutrition(toIngredients(slotB, details)) : null),
    [slotB, details],
  )

  const provenance = useMemo(() => {
    if (!slotA || !slotB) return null
    const keysA = new Set(slotA.map((entry) => plateKey(entry.food)))
    const keysB = new Set(slotB.map((entry) => plateKey(entry.food)))
    const shared = slotA.filter((entry) => keysB.has(plateKey(entry.food)))
    const onlyA = slotA.filter((entry) => !keysB.has(plateKey(entry.food)))
    const onlyB = slotB.filter((entry) => !keysA.has(plateKey(entry.food)))
    const gramsChanged = shared.filter((entry) => {
      const other = slotB.find((candidate) => plateKey(candidate.food) === plateKey(entry.food))
      return other !== undefined && other.grams !== entry.grams
    })
    return { shared, onlyA, onlyB, gramsChanged }
  }, [slotA, slotB])

  const capture = (slot: SlotId) => {
    plans.capture(slot, plate.entries)
  }

  const metricRows = useMemo<MetricCompareRow[]>(() => {
    if (!resultsA || !resultsB) return []
    // 完整与部分缺失都取“已知贡献”；只有整项都无数据时才为 null，不画也不按 0 补。
    const valueOf = (result: NutrientResult): number | null => {
      if (result.status === 'all_missing') return null
      return result.status === 'complete' ? (result.total as number) : result.knownValue
    }
    return resultsA.map((resultA, index) => {
      const resultB = resultsB[index]
      const a = valueOf(resultA)
      const b = valueOf(resultB)
      let note: string | null = null
      if (a === null && b === null) note = zhCN.compare.metricNoDataBoth
      else if (a === null) note = zhCN.compare.metricNoDataIn(zhCN.compare.slotA)
      else if (b === null) note = zhCN.compare.metricNoDataIn(zhCN.compare.slotB)
      return {
        key: resultA.key,
        label: resultA.label,
        unit: resultA.unit,
        decimals: resultA.decimals,
        a,
        b,
        aKnown: resultA.totalCount - resultA.missingCount,
        aTotal: resultA.totalCount,
        bKnown: resultB.totalCount - resultB.missingCount,
        bTotal: resultB.totalCount,
        note,
      }
    })
  }, [resultsA, resultsB])

  const metricSummary = useMemo(() => {
    let up = 0
    let down = 0
    let flat = 0
    for (const row of metricRows) {
      if (row.a === null || row.b === null) continue
      const diff = row.b - row.a
      if (diff > 1e-9) up += 1
      else if (diff < -1e-9) down += 1
      else flat += 1
    }
    return { up, down, flat, comparable: up + down + flat }
  }, [metricRows])

  const gramsA = (slotA ?? []).reduce((sum, entry) => sum + entry.grams, 0)
  const gramsB = (slotB ?? []).reduce((sum, entry) => sum + entry.grams, 0)

  const hasBoth = slotA !== null && slotB !== null && slotA.length > 0 && slotB.length > 0

  return (
    <div className={styles.page}>
      <PageHeader title={zhCN.compare.title} subtitle={zhCN.compare.subtitle} />

      <div className={styles.slots}>
        <SlotCard
          slot="A"
          snapshot={slotA}
          results={resultsA}
          onCapture={() => capture('A')}
          onClear={() => plans.clearSlot('A')}
          onAddToPlan={() => {
            if (slotA) setPlanDialog({ slot: 'A', entries: slotA })
          }}
          plateEmpty={plate.entries.length === 0}
        />
        <SlotCard
          slot="B"
          snapshot={slotB}
          results={resultsB}
          onCapture={() => capture('B')}
          onClear={() => plans.clearSlot('B')}
          onAddToPlan={() => {
            if (slotB) setPlanDialog({ slot: 'B', entries: slotB })
          }}
          plateEmpty={plate.entries.length === 0}
        />
      </div>

      <section className={styles.diffCard} aria-label={zhCN.compare.diffTitle}>
        <header className={styles.diffHeader}>
          <h2 className={styles.diffTitle}>{zhCN.compare.diffTitle}</h2>
          <p className={styles.diffDesc}>{zhCN.compare.diffDesc}</p>
        </header>

        {!hasBoth || !resultsA || !resultsB ? (
          <p className={styles.diffEmpty}>{zhCN.compare.diffEmpty}</p>
        ) : (
          <>
            <div className={styles.summaryStrip}>
              <div className={styles.summaryCell}>
                <span className={styles.summaryLabel}>{zhCN.compare.summaryIngredients}</span>
                <strong className={styles.summaryValue}>
                  {slotA.length}
                  <span className={styles.summaryArrow} aria-hidden="true">
                    →
                  </span>
                  {slotB.length}
                </strong>
              </div>
              <div className={styles.summaryCell}>
                <span className={styles.summaryLabel}>{zhCN.compare.summaryShared}</span>
                <strong className={styles.summaryValue}>{provenance?.shared.length ?? 0}</strong>
              </div>
              <div className={styles.summaryCell}>
                <span className={styles.summaryLabel}>{zhCN.compare.summaryGrams}</span>
                <strong className={styles.summaryValue}>
                  {formatAmount(gramsA, 0)}
                  <span className={styles.summaryArrow} aria-hidden="true">
                    →
                  </span>
                  {formatAmount(gramsB, 0)} g
                </strong>
              </div>
              <div className={styles.summaryCell}>
                <span className={styles.summaryLabel}>{zhCN.compare.summaryMetrics}</span>
                <strong className={styles.summaryValue}>
                  {zhCN.compare.metricCount(metricSummary.comparable)}
                </strong>
                <span className={styles.summaryHint}>
                  {zhCN.compare.summaryMetricTrend(
                    metricSummary.up,
                    metricSummary.down,
                    metricSummary.flat,
                  )}
                </span>
              </div>
            </div>

            <MetricCompareChart rows={metricRows} />

            {provenance ? (
              <div className={styles.provenance}>
                <p className={styles.provenanceLine}>
                  {zhCN.compare.sharedNote(provenance.shared.length)}
                </p>
                <p className={styles.provenanceLine}>
                  {zhCN.compare.onlyIn(zhCN.compare.slotA, provenance.onlyA.length)}：
                  {provenance.onlyA.map((entry) => foodName(entry)).join('、') || zhCN.common.notAvailable}
                </p>
                <p className={styles.provenanceLine}>
                  {zhCN.compare.onlyIn(zhCN.compare.slotB, provenance.onlyB.length)}：
                  {provenance.onlyB.map((entry) => foodName(entry)).join('、') || zhCN.common.notAvailable}
                </p>
                {provenance.gramsChanged.map((entry) => {
                  const other = slotB.find(
                    (candidate) => plateKey(candidate.food) === plateKey(entry.food),
                  )
                  if (!other) return null
                  return (
                    <p key={plateKey(entry.food)} className={styles.provenanceLine}>
                      {foodName(entry)}：{zhCN.compare.gramsDiff(formatAmount(entry.grams, 0), formatAmount(other.grams, 0))}
                    </p>
                  )
                })}
              </div>
            ) : null}
          </>
        )}
      </section>

      <p className={styles.snapshotNote}>{zhCN.compare.snapshotNote}</p>

      {planDialog ? (
        <AddPlateToPlanDialog
          entries={planDialog.entries}
          sourceLabel={planDialog.slot === 'A' ? zhCN.compare.slotA : zhCN.compare.slotB}
          onClose={() => setPlanDialog(null)}
        />
      ) : null}
    </div>
  )
}
