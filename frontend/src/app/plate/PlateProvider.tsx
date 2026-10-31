import { useCallback, useMemo, useState, type ReactNode } from 'react'

import { PlateContext, type AddResult, type PlateContextValue } from '@/app/plate/context'
import {
  addPlateEntry,
  DEFAULT_PLATE_GRAMS,
  MAX_PLATE_ITEMS,
  plateKey,
  removePlateEntry,
  type PlateEntry,
} from '@/lib/calculator'
import type { FoodItem } from '@/lib/types'

/**
 * 餐盘是跨页面共享的工作状态：餐盘设计、营养分析、方案对比读写同一份数据。
 * 只保存在内存中，不落盘；方案持久化留到后续阶段（IndexedDB）。
 */
export function PlateProvider({ children }: { children: ReactNode }) {
  const [entries, setEntries] = useState<PlateEntry[]>([])

  const add = useCallback((food: FoodItem): AddResult => {
    let result: AddResult = 'added'
    setEntries((current) => {
      if (current.some((entry) => plateKey(entry.food) === plateKey(food))) {
        result = 'duplicate'
        return current
      }
      if (current.length >= MAX_PLATE_ITEMS) {
        result = 'full'
        return current
      }
      return addPlateEntry(current, food, { maxItems: MAX_PLATE_ITEMS, defaultGrams: DEFAULT_PLATE_GRAMS })
    })
    return result
  }, [])

  const remove = useCallback((food: FoodItem) => {
    setEntries((current) => removePlateEntry(current, food))
  }, [])

  const setGrams = useCallback((food: FoodItem, grams: number) => {
    setEntries((current) =>
      current.map((entry) => (plateKey(entry.food) === plateKey(food) ? { ...entry, grams } : entry)),
    )
  }, [])

  const clear = useCallback(() => setEntries([]), [])

  const value = useMemo<PlateContextValue>(
    () => ({
      entries,
      add,
      remove,
      setGrams,
      clear,
      has: (food: FoodItem) => entries.some((entry) => plateKey(entry.food) === plateKey(food)),
      isFull: entries.length >= MAX_PLATE_ITEMS,
    }),
    [entries, add, remove, setGrams, clear],
  )

  return <PlateContext.Provider value={value}>{children}</PlateContext.Provider>
}
