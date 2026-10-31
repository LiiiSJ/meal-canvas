import { Info } from 'lucide-react'

import { zhCN } from '@/i18n/zh-CN'
import { formatAmount } from '@/lib/format'
import type { NutrientResult } from '@/lib/calculator'

import styles from './PlannerNutrition.module.css'

const SHOWN_KEYS = ['energy_kcal', 'protein_g', 'fat_g', 'carb_g', 'fiber_g'] as const

interface PlannerNutritionProps {
  results: NutrientResult[]
  itemCount: number
  isLoading: boolean
  hasError: boolean
  isEnriching?: boolean
}

/**
 * 计划餐次的营养合计展示。
 * 计算完全复用 lib/calculator 的 computePlateNutrition：只累加已知值，缺失显示“—”。
 */
export function PlannerNutrition({
  results,
  itemCount,
  isLoading,
  hasError,
  isEnriching = false,
}: PlannerNutritionProps) {
  if (itemCount === 0) return null

  const shown = results.filter((result) =>
    (SHOWN_KEYS as readonly string[]).includes(result.key),
  )

  return (
    <div className={styles.nutrition}>
      <div className={styles.metrics}>
        {shown.map((result) => {
          const partial = result.status === 'partial'
          return (
            <span className={styles.metric} key={result.key} data-status={result.status}>
              <span className={styles.label}>{result.label}</span>
              <span className={styles.value}>
                {result.status === 'all_missing' ? (
                  zhCN.common.notAvailable
                ) : (
                  <>
                    {partial ? <small>{zhCN.designer.knownPrefix}</small> : null}
                    {formatAmount(partial ? result.knownValue : result.total, result.decimals)}
                    <em>{result.unit}</em>
                  </>
                )}
              </span>
            </span>
          )
        })}
      </div>
      {isLoading ? <p className={styles.note}>{zhCN.designer.nutritionLoading}</p> : null}
      {isEnriching ? (
        <p className={styles.note}>
          <Info size={12} aria-hidden="true" />
          {zhCN.enrich.searching}
        </p>
      ) : null}
      {hasError ? (
        <p className={styles.error}>{zhCN.designer.nutritionError}</p>
      ) : null}
      <p className={styles.note}>
        <Info size={12} aria-hidden="true" />
        {zhCN.designer.nutritionNote}
      </p>
    </div>
  )
}
