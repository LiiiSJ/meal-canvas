import { createContext } from 'react'

import type { PlateEntry } from '@/lib/calculator'

import type { PlanSlotId, PlanSnapshot } from './storage'

export interface PlanContextValue {
  slotA: PlanSnapshot | null
  slotB: PlanSnapshot | null
  /** 是否已从本地存储完成首次读取。 */
  ready: boolean
  /** 本地存储是否可用；不可用时方案只保留在当前会话。 */
  storageAvailable: boolean
  /** 把当前餐盘内容复制成快照存入方案；餐盘为空时返回 false。 */
  capture: (slot: PlanSlotId, entries: PlateEntry[]) => boolean
  clearSlot: (slot: PlanSlotId) => void
}

export const PlanContext = createContext<PlanContextValue | null>(null)
