import { AlertTriangle, CircleDashed } from 'lucide-react'
import { lazy, Suspense, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { usePlate } from '@/app/plate/usePlate'
import { EmptyState } from '@/components/StateViews'
import { FoodIcon } from '@/components/FoodIcon'
import { PageHeader } from '@/components/PageHeader'
import { zhCN } from '@/i18n/zh-CN'
import { CORE_NUTRIENTS, plateKey, type CoreNutrientKey } from '@/lib/calculator'
import { computeContributions } from '@/lib/contribution'
import { formatAmount } from '@/lib/format'
import type { FoodSummary } from '@/lib/types'

import { usePlateFoodDetails } from '@/features/designer/usePlateFoodDetails'

import styles from './AnalysisPage.module.css'

const ContributionChart = lazy(() => import('@/features/analysis/ContributionChart'))

function foodName(entry: { food: { display_name: string; description_en: string } }): string {
  return entry.food.display_name || entry.food.description_en
}

/** 营养分析：选一项营养指标，看每种食材的真实贡献，并与餐盘联动。 */
export function AnalysisPage() {
  const plate = usePlate()
  const [nutrientKey, setNutrientKey] = useState<CoreNutrientKey>('protein_g')
  const [selected, setSelected] = useState<string | null>(null)

  const { details, isLoading, hasError } = usePlateFoodDetails(plate.entries)

  const summaries = useMemo(() => {
    const map = new Map<string, FoodSummary>()
    for (const [key, detail] of details) map.set(key, detail.summary_per_100g)
    return map
  }, [details])

  const spec = CORE_NUTRIENTS.find((item) => item.key === nutrientKey) ?? CORE_NUTRIENTS[0]

  const contribution = useMemo(
    () => computeContributions(plate.entries, summaries, (entry) => plateKey(entry.food), nutrientKey),
    [plate.entries, summaries, nutrientKey],
  )

  if (plate.entries.length === 0) {
    return (
      <div className={styles.page}>
        <PageHeader title={zhCN.analysis.title} subtitle={zhCN.analysis.subtitle} />
        <EmptyState
          title={zhCN.analysis.emptyTitle}
          description={zhCN.analysis.emptyDesc}
          action={
            <Link to="/" className={styles.goButton}>
              {zhCN.analysis.goDesigner}
            </Link>
          }
        />
      </div>
    )
  }

  return (
    <div className={styles.page}>
      <PageHeader title={zhCN.analysis.title} subtitle={zhCN.analysis.subtitle} />

      <div className={styles.controls}>
        <label className={styles.field}>
          <span className={styles.label}>{zhCN.analysis.nutrientLabel}</span>
          <select
            className={styles.select}
            value={nutrientKey}
            onChange={(event) => {
              setNutrientKey(event.target.value as CoreNutrientKey)
              setSelected(null)
            }}
          >
            {CORE_NUTRIENTS.map((item) => (
              <option key={item.key} value={item.key}>
                {item.label}（{item.unit}）
              </option>
            ))}
          </select>
        </label>
        <p className={styles.hint}>{zhCN.analysis.clickHint}</p>
        {isLoading ? <p className={styles.hint}>{zhCN.analysis.loadingDetail}</p> : null}
        {hasError ? (
          <p className={styles.error}>
            <AlertTriangle size={14} aria-hidden="true" />
            {zhCN.analysis.errorNote}
          </p>
        ) : null}
      </div>

      <div className={styles.layout}>
        <section className={styles.chartCard} aria-label={zhCN.analysis.chartTitle(spec.label)}>
          <header className={styles.chartHeader}>
            <h2 className={styles.chartTitle}>{zhCN.analysis.chartTitle(spec.label)}</h2>
            <p className={styles.chartDesc}>{zhCN.analysis.chartDesc(spec.label, spec.unit)}</p>
          </header>

          {contribution.items.length === 0 ? (
            <div className={styles.chartEmpty}>
              <CircleDashed size={28} strokeWidth={1.6} aria-hidden="true" />
              <p>{zhCN.analysis.allZero}</p>
            </div>
          ) : (
            <Suspense
              fallback={
                <div className={styles.chartEmpty} role="status">
                  <CircleDashed size={28} strokeWidth={1.6} aria-hidden="true" />
                  <p>{zhCN.common.loading}</p>
                </div>
              }
            >
              <ContributionChart
                items={contribution.items}
                knownTotal={contribution.knownTotal}
                spec={spec}
                selectedKey={selected}
                keyOf={(item) => plateKey(item.entry.food)}
                onSelect={(key) => setSelected((current) => (current === key ? null : key))}
              />
            </Suspense>
          )}

          {contribution.missing.length > 0 ? (
            <p className={styles.missingNote}>
              {zhCN.analysis.missingNote(contribution.missing.length)}
            </p>
          ) : null}
        </section>

        <aside className={styles.plateCard} aria-label={zhCN.analysis.plateTitle}>
          <h2 className={styles.plateTitle}>{zhCN.analysis.plateTitle}</h2>
          <ul className={styles.plateList}>
            {plate.entries.map((entry) => {
              const key = plateKey(entry.food)
              const item = contribution.items.find((candidate) => plateKey(candidate.entry.food) === key)
              const isMissing = contribution.missing.some((candidate) => plateKey(candidate.food) === key)
              return (
                <li key={key}>
                  <button
                    type="button"
                    className={`${styles.plateItem} ${selected === key ? styles.plateItemActive : ''}`}
                    onClick={() => setSelected((current) => (current === key ? null : key))}
                  >
                    <FoodIcon food={entry.food} size={30} label={zhCN.a11y.foodIcon(foodName(entry))} />
                    <span className={styles.plateItemName}>{foodName(entry)}</span>
                    <span className={styles.plateItemValue}>
                      {item
                        ? `${formatAmount(item.value, spec.decimals)} ${spec.unit}`
                        : isMissing
                          ? zhCN.common.notAvailable
                          : ''}
                    </span>
                  </button>
                </li>
              )
            })}
          </ul>
        </aside>
      </div>
    </div>
  )
}
