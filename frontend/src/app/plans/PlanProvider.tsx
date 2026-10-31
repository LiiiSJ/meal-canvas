import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'

import type { PlateEntry } from '@/lib/calculator'

import { PlanContext, type PlanContextValue } from './context'
import {
  deletePlanSnapshot,
  readPlanSnapshots,
  writePlanSnapshot,
  type PlanSlotId,
  type PlanSnapshot,
} from './storage'

type Slots = Record<PlanSlotId, PlanSnapshot | null>

const EMPTY_SLOTS: Slots = { A: null, B: null }

/** 方案快照与当前餐盘解耦：保存一次即独立持有，清空餐盘不会影响已保存的方案。 */
export function PlanProvider({ children }: { children: ReactNode }) {
  const [slots, setSlots] = useState<Slots>(EMPTY_SLOTS)
  const [ready, setReady] = useState(false)
  const [storageAvailable, setStorageAvailable] = useState(true)

  useEffect(() => {
    let cancelled = false
    readPlanSnapshots()
      .then((saved) => {
        if (cancelled) return
        setSlots({ A: saved.A ?? null, B: saved.B ?? null })
      })
      .catch(() => {
        if (cancelled) return
        setStorageAvailable(false)
      })
      .finally(() => {
        if (!cancelled) setReady(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const capture = useCallback((slot: PlanSlotId, entries: PlateEntry[]): boolean => {
    if (entries.length === 0) return false
    const snapshot: PlanSnapshot = {
      entries: entries.map((entry) => ({ ...entry, food: { ...entry.food } })),
      capturedAt: new Date().toISOString(),
    }
    setSlots((current) => ({ ...current, [slot]: snapshot }))
    writePlanSnapshot(slot, snapshot).catch(() => setStorageAvailable(false))
    return true
  }, [])

  const clearSlot = useCallback((slot: PlanSlotId) => {
    setSlots((current) => ({ ...current, [slot]: null }))
    deletePlanSnapshot(slot).catch(() => setStorageAvailable(false))
  }, [])

  const value = useMemo<PlanContextValue>(
    () => ({
      slotA: slots.A,
      slotB: slots.B,
      ready,
      storageAvailable,
      capture,
      clearSlot,
    }),
    [slots, ready, storageAvailable, capture, clearSlot],
  )

  return <PlanContext.Provider value={value}>{children}</PlanContext.Provider>
}
