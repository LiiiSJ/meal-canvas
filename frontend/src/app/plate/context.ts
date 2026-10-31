import { createContext } from 'react'

import type { PlateEntry } from '@/lib/calculator'
import type { FoodItem } from '@/lib/types'

export type AddResult = 'added' | 'duplicate' | 'full'

export interface PlateContextValue {
  entries: PlateEntry[]
  add: (food: FoodItem) => AddResult
  remove: (food: FoodItem) => void
  setGrams: (food: FoodItem, grams: number) => void
  clear: () => void
  has: (food: FoodItem) => boolean
  isFull: boolean
}

export const PlateContext = createContext<PlateContextValue | null>(null)
