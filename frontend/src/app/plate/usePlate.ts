import { useContext } from 'react'

import { PlateContext, type PlateContextValue } from '@/app/plate/context'

export function usePlate(): PlateContextValue {
  const context = useContext(PlateContext)
  if (!context) throw new Error('usePlate 必须在 PlateProvider 内使用')
  return context
}
