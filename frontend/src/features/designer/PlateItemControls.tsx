import { Minus, Plus } from 'lucide-react'
import { useEffect, useState } from 'react'

import { zhCN } from '@/i18n/zh-CN'
import { formatAmount } from '@/lib/format'
import {
  formatPortionLabel,
  getUsablePortions,
  parseGrams,
} from '@/lib/calculator'
import type { FoodPortion, FoodItem } from '@/lib/types'

import styles from './PlateItemControls.module.css'

interface PlateItemControlsProps {
  food: FoodItem
  grams: number
  portions: FoodPortion[]
  onGramsChange: (grams: number) => void
}

const STEP = 10

export function PlateItemControls({ food, grams, portions, onGramsChange }: PlateItemControlsProps) {
  const usablePortions = getUsablePortions(portions)
  const [draft, setDraft] = useState(String(grams))
  const [error, setError] = useState<string | null>(null)

  // 外部 grams 变化（例如份量选择）时同步输入框，避免每次按键被覆盖。
  useEffect(() => {
    setDraft(String(grams))
  }, [grams])

  const commitDraft = () => {
    const value = parseGrams(draft)
    if (value === null) {
      setError(zhCN.designer.gramsInvalid)
      // 回退到上一个有效值，不清空。
      setDraft(String(grams))
      return
    }
    setError(null)
    if (value !== grams) onGramsChange(value)
  }

  const stepGrams = (delta: number) => {
    const next = Math.max(1, Math.round((grams + delta) / STEP) * STEP)
    if (next !== grams) onGramsChange(next)
  }

  const handlePortion = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const index = Number(event.target.value)
    const portion = usablePortions[index]
    if (portion && portion.gram_weight !== null) {
      onGramsChange(portion.gram_weight)
    }
    event.target.value = ''
  }

  return (
    <div className={styles.controls}>
      <div className={styles.gramsRow}>
        <button
          type="button"
          className={styles.stepButton}
          onClick={() => stepGrams(-STEP)}
          aria-label={zhCN.a11y.decreaseGrams(food.display_name || food.description_en)}
        >
          <Minus size={14} aria-hidden="true" />
        </button>

        <label className={styles.gramsLabel}>
          <span className={styles.gramsHint}>{zhCN.designer.gramsLabel}</span>
          <input
            type="number"
            inputMode="decimal"
            min={0}
            step="1"
            className={styles.gramsInput}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onBlur={commitDraft}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault()
                commitDraft()
                ;(event.target as HTMLInputElement).blur()
              }
            }}
            aria-invalid={error !== null}
            aria-describedby={error ? `grams-error-${food.fdc_id}` : undefined}
          />
          <span className={styles.gramsUnit}>{zhCN.designer.unitGram}</span>
        </label>

        <button
          type="button"
          className={styles.stepButton}
          onClick={() => stepGrams(STEP)}
          aria-label={zhCN.a11y.increaseGrams(food.display_name || food.description_en)}
        >
          <Plus size={14} aria-hidden="true" />
        </button>
      </div>

      {error ? (
        <p className={styles.error} id={`grams-error-${food.fdc_id}`}>
          {error}
        </p>
      ) : null}

      {usablePortions.length > 0 ? (
        <label className={styles.portionLabel}>
          <span className={styles.portionHint}>{zhCN.designer.portionLabel}</span>
          <select
            className={styles.portionSelect}
            value=""
            onChange={handlePortion}
            aria-label={zhCN.a11y.portionSelect(food.display_name || food.description_en)}
          >
            <option value="">{zhCN.designer.portionPlaceholder}</option>
            {usablePortions.map((portion, index) => (
              <option key={`${portion.modifier ?? 'p'}-${index}`} value={index}>
                {formatPortionLabel(portion)}
              </option>
            ))}
          </select>
        </label>
      ) : (
        <p className={styles.noPortion}>
          {food.library_scope === 'branded'
            ? zhCN.designer.brandedNoPortion
            : zhCN.designer.noPortionHint}
        </p>
      )}

      <p className={styles.contributionHint}>
        {zhCN.designer.contributionHint(formatAmount(grams, 0))}
      </p>
    </div>
  )
}
