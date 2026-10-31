import {
  categoryIconComponents,
  foodIconComponents,
  type CategoryIconId,
  type FoodIconId,
} from '@/assets/food-icons/icons'
import { resolveFoodIcon, type FoodIconSource } from '@/assets/food-icons/mapping'

interface FoodIconProps {
  food: FoodIconSource
  size?: number
  label?: string
  className?: string
}

/** 食材图标唯一入口：同一食品在卡片、餐盘、详情、探索中都走同一映射。 */
export function FoodIcon({ food, size = 48, label, className }: FoodIconProps) {
  const key = resolveFoodIcon(food)
  const Component =
    key in foodIconComponents
      ? foodIconComponents[key as FoodIconId]
      : categoryIconComponents[key as CategoryIconId]

  const ariaLabel = label ?? food.name_zh ?? food.description_en ?? '未命名食品'

  return (
    <Component
      width={size}
      height={size}
      role="img"
      aria-label={ariaLabel}
      focusable="false"
      className={className}
    />
  )
}
