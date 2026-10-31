import { useContext } from 'react'

import { PlanContext, type PlanContextValue } from './context'

export function usePlans(): PlanContextValue {
  const value = useContext(PlanContext)
  if (!value) throw new Error('usePlans 必须在 PlanProvider 内使用')
  return value
}
