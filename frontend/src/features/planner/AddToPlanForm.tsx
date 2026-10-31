import { useState } from 'react'

import { zhCN } from '@/i18n/zh-CN'
import { parseGrams } from '@/lib/calculator'
import { useAddPlanEntry } from '@/lib/queries'
import type { LibraryScope, MealType } from '@/lib/types'

import { formatPlanDate, todayISO } from '@/features/planner/model'

import styles from './AddToPlanForm.module.css'

interface AddToPlanFormProps {
  foodKey: string
  scope: LibraryScope
  name: string
}

const MEAL_TYPES: readonly MealType[] = ['breakfast', 'lunch', 'dinner', 'snack']

/** 日期展示：10 月 26 日（本地日期字符串，不经过时区转换）。 */

/**
 * 把当前食品加入某天某餐次并立即写入计划库。
 * 食品详情抽屉与餐盘设计页共用这一个表单，不重复实现选择写入口。
 */
export function AddToPlanForm({ foodKey, scope, name }: AddToPlanFormProps) {
  const [date, setDate] = useState(todayISO())
  const [mealType, setMealType] = useState<MealType>('breakfast')
  const [grams, setGrams] = useState('100')
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const addEntry = useAddPlanEntry()

  const submit = () => {
    const amount = parseGrams(grams)
    if (amount === null) {
      setError(zhCN.planner.pickerInvalid)
      setMessage(null)
      return
    }
    if (!date) {
      setError(zhCN.planner.pickerInvalid)
      setMessage(null)
      return
    }
    setError(null)
    addEntry.mutate(
      {
        meal_date: date,
        meal_type: mealType,
        food_key: foodKey,
        library_scope: scope,
        amount_g: amount,
        name_snapshot: name || null,
      },
      {
        onSuccess: () => {
          setMessage(
            zhCN.planner.addToPlanSuccess(
              formatPlanDate(date),
              zhCN.planner.mealType[mealType],
            ),
          )
        },
        onError: (mutationError) => {
          setMessage(null)
          setError(
            mutationError instanceof Error
              ? mutationError.message
              : zhCN.planner.addToPlanFailed,
          )
        },
      },
    )
  }

  return (
    <div className={styles.form}>
      <p className={styles.hint}>{zhCN.planner.addToPlanHint}</p>
      <div className={styles.fields}>
        <label className={styles.field}>
          <span>{zhCN.planner.addToPlanDate}</span>
          <input
            type="date"
            value={date}
            onChange={(event) => {
              setDate(event.target.value)
              setMessage(null)
            }}
          />
        </label>
        <label className={styles.field}>
          <span>{zhCN.planner.addToPlanMeal}</span>
          <select
            value={mealType}
            onChange={(event) => {
              setMealType(event.target.value as MealType)
              setMessage(null)
            }}
          >
            {MEAL_TYPES.map((type) => (
              <option key={type} value={type}>
                {zhCN.planner.mealType[type]}
              </option>
            ))}
          </select>
        </label>
        <label className={styles.field}>
          <span>{zhCN.planner.addToPlanGrams}</span>
          <input
            type="number"
            inputMode="decimal"
            min={0}
            step="1"
            value={grams}
            onChange={(event) => {
              setGrams(event.target.value)
              setMessage(null)
            }}
          />
        </label>
        <button
          type="button"
          className={styles.submit}
          onClick={submit}
          disabled={addEntry.isPending}
        >
          {addEntry.isPending ? zhCN.planner.saving : zhCN.planner.addToPlanSubmit}
        </button>
      </div>
      {message ? <p className={styles.success}>{message}</p> : null}
      {error ? <p className={styles.error}>{error}</p> : null}
    </div>
  )
}
