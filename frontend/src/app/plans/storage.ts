import type { PlateEntry } from '@/lib/calculator'

export const PLAN_SLOTS = ['A', 'B'] as const
export type PlanSlotId = (typeof PLAN_SLOTS)[number]

/** 一个方案的快照：保存当时的食材与克重，捕获后与当前餐盘完全独立。 */
export interface PlanSnapshot {
  entries: PlateEntry[]
  capturedAt: string
}

export type PlanSnapshots = Partial<Record<PlanSlotId, PlanSnapshot>>

const DB_NAME = 'meal-canvas'
const DB_VERSION = 1
const STORE_NAME = 'plans'

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION)
    request.onupgradeneeded = () => {
      const db = request.result
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME)
      }
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error ?? new Error('打开本地数据库失败'))
  })
}

/** 读取已保存的方案；IndexedDB 不可用时返回空对象，由调用方决定提示方式。 */
export async function readPlanSnapshots(): Promise<PlanSnapshots> {
  if (typeof indexedDB === 'undefined') return {}
  const db = await openDb()
  try {
    return await new Promise<PlanSnapshots>((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readonly')
      const store = tx.objectStore(STORE_NAME)
      const result: PlanSnapshots = {}
      let pending = PLAN_SLOTS.length
      for (const slot of PLAN_SLOTS) {
        const request = store.get(slot)
        request.onsuccess = () => {
          const value = request.result as PlanSnapshot | undefined
          if (value) result[slot] = value
          pending -= 1
          if (pending === 0) resolve(result)
        }
        request.onerror = () => reject(request.error ?? new Error('读取方案失败'))
      }
    })
  } finally {
    db.close()
  }
}

export async function writePlanSnapshot(slot: PlanSlotId, snapshot: PlanSnapshot): Promise<void> {
  if (typeof indexedDB === 'undefined') throw new Error('当前浏览器不支持本地存储')
  const db = await openDb()
  try {
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readwrite')
      tx.objectStore(STORE_NAME).put(snapshot, slot)
      tx.oncomplete = () => resolve()
      tx.onerror = () => reject(tx.error ?? new Error('保存方案失败'))
    })
  } finally {
    db.close()
  }
}

export async function deletePlanSnapshot(slot: PlanSlotId): Promise<void> {
  if (typeof indexedDB === 'undefined') return
  const db = await openDb()
  try {
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readwrite')
      tx.objectStore(STORE_NAME).delete(slot)
      tx.oncomplete = () => resolve()
      tx.onerror = () => reject(tx.error ?? new Error('删除方案失败'))
    })
  } finally {
    db.close()
  }
}
