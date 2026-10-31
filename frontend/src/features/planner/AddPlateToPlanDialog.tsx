import { ArrowRight, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Link } from 'react-router-dom'

import { FoodIcon } from '@/components/FoodIcon'
import { zhCN } from '@/i18n/zh-CN'
import type { PlateEntry } from '@/lib/calculator'
import { formatAmount } from '@/lib/format'
import { useAddPlanEntriesBatch } from '@/lib/queries'
import type { MealType } from '@/lib/types'

import { formatPlanDate, todayISO } from '@/features/planner/model'

import styles from './AddPlateToPlanDialog.module.css'

const MEAL_TYPES: readonly MealType[] = ['breakfast', 'lunch', 'dinner', 'snack']

function entryName(entry: PlateEntry): string {
  return entry.food.display_name || entry.food.description_en
}

interface AddPlateToPlanDialogProps {
  entries: PlateEntry[]
  /** 来源名称，如「当前餐盘」「方案 A」。 */
  sourceLabel: string
  onClose: () => void
}

/**
 * 把一整盘食品按当前克数一次加入某天某餐。
 * 餐盘设计页与方案对比页共用这一个对话框，不重复实现写入口。
 */
export function AddPlateToPlanDialog({ entries, sourceLabel, onClose }: AddPlateToPlanDialogProps) {
  const [date, setDate] = useState(todayISO())
  const [mealType, setMealType] = useState<MealType>('breakfast')
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<{ text: string; link: string } | null>(null)
  const addBatch = useAddPlanEntriesBatch()
  const closeRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    closeRef.current?.focus()

    const handleKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKey)
    return () => {
      document.removeEventListener('keydown', handleKey)
      document.body.style.overflow = previousOverflow
      previousFocus?.focus()
    }
  }, [onClose])

  const submit = () => {
    if (!date || entries.length === 0 || addBatch.isPending) return
    setError(null)
    addBatch.mutate(
      {
        meal_date: date,
        meal_type: mealType,
        items: entries.map((entry) => ({
          food_key: String(entry.food.fdc_id),
          library_scope: entry.food.library_scope,
          amount_g: entry.grams,
          name_snapshot: entryName(entry),
        })),
      },
      {
        onSuccess: () => {
          setSuccess({
            text: zhCN.planner.plateToPlanSuccess(
              formatPlanDate(date),
              zhCN.planner.mealType[mealType],
              entries.length,
            ),
            link: `/weekly?date=${date}&meal=${mealType}`,
          })
        },
        onError: (mutationError) => {
          setError(
            mutationError instanceof Error
              ? mutationError.message
              : zhCN.planner.addToPlanFailed,
          )
        },
      },
    )
  }

  return createPortal(
    <div
      className={styles.overlay}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <section
        className={styles.dialog}
        role="dialog"
        aria-modal="true"
        aria-label={zhCN.planner.plateToPlanTitle(sourceLabel)}
      >
        <header className={styles.header}>
          <div>
            <h2 className={styles.title}>{zhCN.planner.plateToPlanTitle(sourceLabel)}</h2>
            <p className={styles.hint}>{zhCN.planner.plateToPlanHint}</p>
          </div>
          <button
            type="button"
            className={styles.closeButton}
            onClick={onClose}
            aria-label={zhCN.common.close}
            ref={closeRef}
          >
            <X size={16} aria-hidden="true" />
          </button>
        </header>

        <div className={styles.fields}>
          <label className={styles.field}>
            <span>{zhCN.planner.addToPlanDate}</span>
            <input
              type="date"
              value={date}
              onChange={(event) => {
                setDate(event.target.value)
                setSuccess(null)
              }}
            />
          </label>
          <label className={styles.field}>
            <span>{zhCN.planner.addToPlanMeal}</span>
            <select
              value={mealType}
              onChange={(event) => {
                setMealType(event.target.value as MealType)
                setSuccess(null)
              }}
            >
              {MEAL_TYPES.map((type) => (
                <option key={type} value={type}>
                  {zhCN.planner.mealType[type]}
                </option>
              ))}
            </select>
          </label>
        </div>

        <p className={styles.itemsTitle}>{zhCN.planner.plateToPlanItems(entries.length)}</p>
        <ul className={styles.itemList}>
          {entries.map((entry) => (
            <li key={`${entry.food.library_scope}-${entry.food.fdc_id}`} className={styles.item}>
              <FoodIcon
                food={entry.food}
                size={26}
                label={zhCN.a11y.foodIcon(entryName(entry))}
              />
              <span className={styles.itemName}>{entryName(entry)}</span>
              <span className={styles.itemGrams}>{formatAmount(entry.grams, 0)} g</span>
            </li>
          ))}
        </ul>

        {error ? (
          <p className={styles.error} role="alert">
            {error}
          </p>
        ) : null}

        <footer className={styles.footer}>
          {success ? (
            <div className={styles.successArea} role="status">
              <p className={styles.success}>{success.text}</p>
              <Link to={success.link} className={styles.viewLink} onClick={onClose}>
                {zhCN.planner.plateToPlanView}
                <ArrowRight size={13} aria-hidden="true" />
              </Link>
            </div>
          ) : (
            <>
              <button type="button" className={styles.cancelButton} onClick={onClose}>
                {zhCN.common.cancel}
              </button>
              <button
                type="button"
                className={styles.submitButton}
                onClick={submit}
                disabled={addBatch.isPending || entries.length === 0 || !date}
              >
                {addBatch.isPending ? zhCN.planner.saving : zhCN.planner.plateToPlanSubmit}
              </button>
            </>
          )}
        </footer>
      </section>
    </div>,
    document.body,
  )
}
