import { Plus, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

import { FoodIcon } from '@/components/FoodIcon'
import { zhCN } from '@/i18n/zh-CN'
import { parseGrams } from '@/lib/calculator'
import type { FoodItem } from '@/lib/types'

import { FoodLibrary } from '@/features/food-library/FoodLibrary'

import styles from './FoodPicker.module.css'

export interface PickedFood {
  food: FoodItem
  grams: number
}

interface StagedItem {
  food: FoodItem
  grams: string
}

interface FoodPickerProps {
  mealLabel: string
  onPickAll: (items: PickedFood[]) => void
  onClose: () => void
  isAdded?: (food: FoodItem) => boolean
}

function primaryName(food: FoodItem): string {
  return food.name_zh && food.zh_status !== 'none' ? food.name_zh : food.description_en
}

function sameFood(a: FoodItem, b: FoodItem): boolean {
  return a.fdc_id === b.fdc_id && a.library_scope === b.library_scope
}

/**
 * 餐次食品选择器：直接复用现有 FoodLibrary 的搜索 / 筛选 / 分页。
 * 可以一次暂存多种食品、分别填克数，再一次确认全部加入当前餐次。
 */
export function FoodPicker({ mealLabel, onPickAll, onClose, isAdded }: FoodPickerProps) {
  const [staged, setStaged] = useState<StagedItem[]>([])
  const [error, setError] = useState<string | null>(null)
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

  const stage = (food: FoodItem) => {
    setError(null)
    setStaged((current) =>
      current.some((entry) => sameFood(entry.food, food))
        ? current
        : [...current, { food, grams: '100' }],
    )
  }

  const unstage = (food: FoodItem) => {
    setError(null)
    setStaged((current) => current.filter((entry) => !sameFood(entry.food, food)))
  }

  const setGrams = (food: FoodItem, grams: string) => {
    setStaged((current) =>
      current.map((entry) => (sameFood(entry.food, food) ? { ...entry, grams } : entry)),
    )
  }

  const handleConfirm = () => {
    const items: PickedFood[] = []
    for (const entry of staged) {
      const value = parseGrams(entry.grams)
      if (value === null) {
        setError(zhCN.planner.pickerGramsInvalidFor(primaryName(entry.food)))
        return
      }
      items.push({ food: entry.food, grams: value })
    }
    if (items.length === 0) return
    setError(null)
    onPickAll(items)
    onClose()
  }

  const libraryIsAdded = (food: FoodItem) =>
    (isAdded?.(food) ?? false) || staged.some((entry) => sameFood(entry.food, food))

  return createPortal(
    <div
      className={styles.overlay}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <aside
        className={styles.panel}
        role="dialog"
        aria-modal="true"
        aria-label={zhCN.planner.pickerTitle(mealLabel)}
      >
        <header className={styles.header}>
          <div>
            <h2 className={styles.title}>{zhCN.planner.pickerTitle(mealLabel)}</h2>
            <p className={styles.hint}>{zhCN.planner.pickerHint}</p>
          </div>
          <button
            type="button"
            className={styles.closeButton}
            onClick={onClose}
            aria-label={zhCN.common.close}
            ref={closeRef}
          >
            <X size={18} aria-hidden="true" />
          </button>
        </header>

        <div className={styles.library}>
          <FoodLibrary
            onOpen={stage}
            onAddFood={stage}
            addLabel={zhCN.planner.pickerAddLabel}
            isAdded={libraryIsAdded}
          />
        </div>

        <footer className={styles.footer}>
          <div className={styles.stagedArea}>
            {staged.length === 0 ? (
              <p className={styles.footerHint}>{zhCN.planner.pickerStagedEmpty}</p>
            ) : (
              <ul className={styles.stagedList} aria-label={zhCN.planner.pickerSelected}>
                {staged.map((entry) => {
                  const name = primaryName(entry.food)
                  return (
                    <li
                      className={styles.stagedRow}
                      key={`${entry.food.library_scope}-${entry.food.fdc_id}`}
                    >
                      <FoodIcon food={entry.food} size={30} label={zhCN.a11y.foodIcon(name)} />
                      <span className={styles.stagedNames}>
                        <strong>{name}</strong>
                        {name !== entry.food.description_en ? (
                          <small lang="en">{entry.food.description_en}</small>
                        ) : null}
                      </span>
                      <label className={styles.gramsField}>
                        <span className={styles.visuallyHidden}>{zhCN.planner.pickerGrams}</span>
                        <input
                          type="number"
                          inputMode="decimal"
                          min={0}
                          step="1"
                          value={entry.grams}
                          onChange={(event) => setGrams(entry.food, event.target.value)}
                          aria-label={`${name} ${zhCN.planner.pickerGrams}`}
                        />
                        <span>{zhCN.designer.unitGram}</span>
                      </label>
                      <button
                        type="button"
                        className={styles.stagedRemove}
                        onClick={() => unstage(entry.food)}
                        aria-label={zhCN.planner.pickerRemove(name)}
                      >
                        <X size={13} aria-hidden="true" />
                      </button>
                    </li>
                  )
                })}
              </ul>
            )}
          </div>
          <div className={styles.actions}>
            {error ? (
              <p className={styles.error} role="alert">
                {error}
              </p>
            ) : null}
            <button
              type="button"
              className={styles.confirmButton}
              onClick={handleConfirm}
              disabled={staged.length === 0}
            >
              <Plus size={15} aria-hidden="true" />
              {zhCN.planner.pickerConfirmAll(staged.length)}
            </button>
          </div>
        </footer>
      </aside>
    </div>,
    document.body,
  )
}
