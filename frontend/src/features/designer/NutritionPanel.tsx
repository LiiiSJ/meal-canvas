import { AlertTriangle, Info } from 'lucide-react'

import { zhCN } from '@/i18n/zh-CN'
import { formatAmount } from '@/lib/format'
import type { NutrientResult } from '@/lib/calculator'

import styles from './NutritionPanel.module.css'

interface NutritionPanelProps {
  results: NutrientResult[]
  isLoading: boolean
  hasError: boolean
  ingredientCount: number
  /** 有食材正在联网补全缺失营养（不阻塞已知值展示）。 */
  isEnriching?: boolean
}

function statusLabel(result: NutrientResult): string | null {
  if (result.status === 'partial') {
    return zhCN.designer.partialMissing(result.missingCount, result.totalCount)
  }
  if (result.status === 'all_missing') {
    return zhCN.designer.allMissing
  }
  return null
}

export function NutritionPanel({
  results,
  isLoading,
  hasError,
  ingredientCount,
  isEnriching = false,
}: NutritionPanelProps) {
  if (ingredientCount === 0) {
    return (
      <div className={styles.empty}>
        <p className={styles.emptyTitle}>{zhCN.designer.insightEmptyTitle}</p>
        <p className={styles.emptyDesc}>{zhCN.designer.insightEmptyDesc}</p>
      </div>
    )
  }

  return (
    <div className={styles.panel}>
      {isLoading ? (
        <p className={styles.loading}>{zhCN.designer.nutritionLoading}</p>
      ) : null}
      {isEnriching ? (
        <p className={styles.note}>
          <Info size={13} aria-hidden="true" />
          {zhCN.enrich.searching}
        </p>
      ) : null}
      {hasError ? (
        <p className={styles.error}>
          <AlertTriangle size={14} aria-hidden="true" />
          {zhCN.designer.nutritionError}
        </p>
      ) : null}

      <div className={styles.grid}>
        {results.map((result) => {
          const warning = statusLabel(result)
          return (
            <div className={styles.item} key={result.key} data-status={result.status}>
              <span className={styles.label}>{result.label}</span>
              <span className={styles.value}>
                {result.status === 'complete' ? (
                  <>
                    {formatAmount(result.total, result.decimals)}
                    <em>{result.unit}</em>
                  </>
                ) : result.status === 'partial' ? (
                  <>
                    <span className={styles.knownPrefix}>{zhCN.designer.knownPrefix}</span>
                    {formatAmount(result.knownValue, result.decimals)}
                    <em>{result.unit}</em>
                  </>
                ) : (
                  <span className={styles.dash}>{zhCN.common.notAvailable}</span>
                )}
              </span>
              {warning ? (
                <span className={styles.warning} title={warning}>
                  <Info size={11} aria-hidden="true" />
                  {warning}
                </span>
              ) : null}
            </div>
          )
        })}
      </div>

      <p className={styles.note}>
        <Info size={13} aria-hidden="true" />
        {zhCN.designer.nutritionNote}
      </p>
    </div>
  )
}
