import { Copy, Plus, Trash2, X } from 'lucide-react'
import { useMemo } from 'react'

import { FoodIcon } from '@/components/FoodIcon'
import { PlateItemControls } from '@/features/designer/PlateItemControls'
import { zhCN } from '@/i18n/zh-CN'
import { computePlateNutrition, type PlateIngredient } from '@/lib/calculator'
import type { FoodDetail, FoodItem, LibraryScope } from '@/lib/types'

import { PlannerNutrition } from './PlannerNutrition'
import {
  mealDisplayLabel,
  plannerFoodItem,
  plannerFoodKey,
  type PlannerDraftItem,
  type PlannerDraftMeal,
} from './model'

import styles from './MealCard.module.css'

interface MealCardProps {
  meal: PlannerDraftMeal
  /** 加餐在当天的序号（1 起）；主餐次为 0。 */
  snackNumber: number
  details: Map<string, FoodDetail>
  isLoading: boolean
  hasError: boolean
  isEnriching: boolean
  highlighted: boolean
  onAddFood: () => void
  onSetGrams: (itemClientId: string, grams: number) => void
  onRemoveItem: (item: PlannerDraftItem) => void
  onDeleteMeal: () => void
  onCopyMeal: () => void
  onOpenDetail: (foodKey: string, scope: LibraryScope) => void
}

function displayName(item: PlannerDraftItem, detail?: FoodDetail): string {
  if (detail) {
    return detail.name_zh && detail.zh_status !== 'none'
      ? detail.name_zh
      : detail.description_en
  }
  return item.name || zhCN.planner.foodFallback(item.foodKey)
}

/** 单餐卡片：食品清单、克数编辑、营养合计、复制与清空/删除。 */
export function MealCard({
  meal,
  snackNumber,
  details,
  isLoading,
  hasError,
  isEnriching,
  highlighted,
  onAddFood,
  onSetGrams,
  onRemoveItem,
  onDeleteMeal,
  onCopyMeal,
  onOpenDetail,
}: MealCardProps) {
  const ingredients = useMemo<PlateIngredient[]>(() => {
    return meal.items.flatMap((item) => {
      const detail = details.get(plannerFoodKey(item.foodKey, item.scope))
      if (!detail) return []
      return [
        {
          foodKey: plannerFoodKey(item.foodKey, item.scope),
          grams: item.grams,
          summary: detail.summary_per_100g,
        },
      ]
    })
  }, [meal.items, details])

  const nutrition = useMemo(() => computePlateNutrition(ingredients), [ingredients])
  const isEmpty = meal.items.length === 0
  const isSnack = meal.mealType === 'snack'
  const label = mealDisplayLabel(meal, snackNumber)

  return (
    <article
      className={`${styles.card} ${highlighted ? styles.highlighted : ''}`}
      data-meal-type={meal.mealType}
      aria-label={label}
    >
      <header className={styles.header}>
        <span className={styles.label}>{label}</span>
        <span className={styles.count}>
          {meal.items.length > 0 ? zhCN.common.totalItems(meal.items.length) : null}
        </span>
        <div className={styles.actions}>
          <button
            type="button"
            className={styles.iconButton}
            onClick={onCopyMeal}
            disabled={isEmpty}
            aria-label={`${zhCN.planner.copyMeal}：${label}`}
            title={isEmpty ? zhCN.planner.copyEmpty : zhCN.planner.copyMeal}
          >
            <Copy size={13} aria-hidden="true" />
          </button>
          <button
            type="button"
            className={`${styles.iconButton} ${styles.dangerButton}`}
            onClick={onDeleteMeal}
            aria-label={isSnack ? zhCN.planner.deleteSnack : zhCN.planner.clearMeal}
            title={isSnack ? zhCN.planner.deleteSnack : zhCN.planner.clearMeal}
          >
            <Trash2 size={13} aria-hidden="true" />
          </button>
        </div>
      </header>

      {isEmpty ? (
        <div className={styles.empty}>
          <p>{zhCN.planner.emptyMeal}</p>
          <button type="button" className={styles.addButton} onClick={onAddFood}>
            <Plus size={14} aria-hidden="true" />
            {zhCN.planner.addFirstFood}
          </button>
        </div>
      ) : (
        <>
          <ul className={styles.items}>
            {meal.items.map((item) => {
              const detail = details.get(plannerFoodKey(item.foodKey, item.scope))
              const food: FoodItem = plannerFoodItem(item, detail)
              const name = displayName(item, detail)
              return (
                <li className={styles.item} key={item.clientId}>
                  <div className={styles.itemHead}>
                    <button
                      type="button"
                      className={styles.itemMain}
                      onClick={() => onOpenDetail(item.foodKey, item.scope)}
                      aria-label={zhCN.a11y.foodCard(name)}
                    >
                      <FoodIcon food={food} size={32} label={zhCN.a11y.foodIcon(name)} />
                      <span className={styles.itemName}>{name}</span>
                    </button>
                    <button
                      type="button"
                      className={styles.removeButton}
                      onClick={() => onRemoveItem(item)}
                      aria-label={zhCN.planner.removeFood(name)}
                    >
                      <X size={12} aria-hidden="true" />
                    </button>
                  </div>
                  <PlateItemControls
                    food={food}
                    grams={item.grams}
                    portions={detail?.portions ?? []}
                    onGramsChange={(grams) => onSetGrams(item.clientId, grams)}
                  />
                </li>
              )
            })}
          </ul>

          <PlannerNutrition
            results={nutrition}
            itemCount={meal.items.length}
            isLoading={isLoading}
            hasError={hasError}
            isEnriching={isEnriching}
          />

          <button type="button" className={styles.addButton} onClick={onAddFood}>
            <Plus size={14} aria-hidden="true" />
            {zhCN.planner.addFood}
          </button>
        </>
      )}
    </article>
  )
}
