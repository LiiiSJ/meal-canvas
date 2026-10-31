import { lazy, Suspense, useMemo } from 'react'

import { Badge } from '@/components/Badge'
import { zhCN } from '@/i18n/zh-CN'
import { formatAmount } from '@/lib/format'

import styles from './MetricCompareChart.module.css'

const NutritionRadar = lazy(() => import('./NutritionRadar'))

/** 一行 = 一项营养指标在两套方案中的可比值。 */
export interface MetricCompareRow {
  key: string
  label: string
  unit: string
  decimals: number
  /** 有数据时为合计值（完整或已知部分），完全无数据时为 null。 */
  a: number | null
  b: number | null
  /** 该方案中报告了此项的食材数 / 食材总数。 */
  aKnown: number
  aTotal: number
  bKnown: number
  bTotal: number
  /** 至少一侧完全无数据时的说明。 */
  note: string | null
}

type Tone = 'up' | 'down' | 'none'

/** 少于 3 根轴时雷达图没有形状可比较，改为只显示明细。 */
const MIN_RADAR_AXES = 3

function toneOf(diff: number): Tone {
  if (Math.abs(diff) < 1e-9) return 'none'
  return diff > 0 ? 'up' : 'down'
}

function coverageOf(row: MetricCompareRow): { text: string; low: boolean } {
  const parts: string[] = []
  if (row.aTotal > 0 && row.aKnown < row.aTotal) {
    parts.push(zhCN.compare.coverageTag('A', row.aKnown, row.aTotal))
  }
  if (row.bTotal > 0 && row.bKnown < row.bTotal) {
    parts.push(zhCN.compare.coverageTag('B', row.bKnown, row.bTotal))
  }
  const low =
    (row.aTotal > 0 && row.aKnown / row.aTotal < 0.5) ||
    (row.bTotal > 0 && row.bKnown / row.bTotal < 0.5)
  return { text: parts.join(' · '), low }
}

/**
 * 方案对比主体：雷达图看营养结构，逐项明细给出绝对数值与变化。
 * 部分缺失的指标用“已知部分”参与比较，并标出覆盖率；完全无数据的指标单独说明。
 */
export function MetricCompareChart({ rows }: { rows: MetricCompareRow[] }) {
  const drawable = useMemo(
    () =>
      rows.filter(
        (row): row is MetricCompareRow & { a: number; b: number } => row.a !== null && row.b !== null,
      ),
    [rows],
  )
  const excludedLabels = useMemo(
    () => rows.filter((row) => row.a === null || row.b === null).map((row) => row.label),
    [rows],
  )
  const hasPartial = drawable.some((row) => row.aKnown < row.aTotal || row.bKnown < row.bTotal)
  const showRadar = drawable.length >= MIN_RADAR_AXES

  return (
    <div className={styles.wrap}>
      <div className={styles.hero}>
        <div className={styles.legend}>
          <span className={styles.legendItem}>
            <i className={`${styles.dot} ${styles.dotA}`} aria-hidden="true" />
            {zhCN.compare.legendA}
          </span>
          <span className={styles.legendItem}>
            <i className={`${styles.dot} ${styles.dotB}`} aria-hidden="true" />
            {zhCN.compare.legendB}
          </span>
        </div>
        {showRadar ? (
          <Suspense
            fallback={
              <div className={styles.chartLoading} role="status">
                {zhCN.compare.radarLoading}
              </div>
            }
          >
            <NutritionRadar rows={drawable} />
          </Suspense>
        ) : (
          <p className={styles.chartFallback}>{zhCN.compare.radarTooFew}</p>
        )}
        <p className={styles.hint}>{zhCN.compare.legendHint}</p>
      </div>

      <div className={styles.detail}>
        <div className={styles.detailHead} aria-hidden="true">
          <span>{zhCN.compare.detailMetric}</span>
          <span>{zhCN.compare.detailPair}</span>
          <span className={styles.headDelta}>{zhCN.compare.detailDelta}</span>
        </div>
        <ul className={styles.detailRows}>
          {rows.map((row) => {
            const both = row.a !== null && row.b !== null
            const diff = both ? (row.b as number) - (row.a as number) : 0
            const tone = both ? toneOf(diff) : 'none'
            const pct =
              both && (row.a as number) > 0 ? (diff / (row.a as number)) * 100 : null
            const coverage = coverageOf(row)
            return (
              <li
                key={row.key}
                className={`${styles.detailRow} ${both ? '' : styles.rowMuted}`}
              >
                <span className={styles.detailLabel}>
                  <span className={styles.label}>{row.label}</span>
                  {coverage.text ? (
                    <span
                      className={`${styles.coverage} ${coverage.low ? styles.coverageWarn : ''}`}
                    >
                      {coverage.text}
                    </span>
                  ) : null}
                </span>
                <span className={styles.valuePair}>
                  <span className={styles.val}>
                    <em className={styles.valSide}>A</em>
                    {formatAmount(row.a, row.decimals)}
                    <span className={styles.unit}>{row.unit}</span>
                  </span>
                  <span className={styles.arrow} aria-hidden="true">
                    →
                  </span>
                  <span className={styles.val}>
                    <em className={styles.valSide}>B</em>
                    {formatAmount(row.b, row.decimals)}
                    <span className={styles.unit}>{row.unit}</span>
                  </span>
                </span>
                <span className={styles.deltaCell}>
                  {both ? (
                    <span className={`${styles.delta} ${styles[`delta_${tone}`]}`}>
                      {tone === 'none'
                        ? zhCN.compare.diffNone
                        : `${diff > 0 ? '+' : '−'}${formatAmount(Math.abs(diff), row.decimals)} ${row.unit}`}
                      {pct !== null && tone !== 'none' ? (
                        <span className={styles.deltaPct}>
                          {zhCN.compare.deltaPct(formatAmount(Math.abs(pct), 0))}
                        </span>
                      ) : null}
                    </span>
                  ) : (
                    <Badge tone="orange">{row.note ?? zhCN.compare.metricNoDataBoth}</Badge>
                  )}
                </span>
              </li>
            )
          })}
        </ul>
      </div>

      {hasPartial ? <p className={styles.footNote}>{zhCN.compare.coverageNote}</p> : null}
      {excludedLabels.length > 0 ? (
        <p className={styles.footNote}>{zhCN.compare.axisExcluded(excludedLabels.join('、'))}</p>
      ) : null}
    </div>
  )
}
