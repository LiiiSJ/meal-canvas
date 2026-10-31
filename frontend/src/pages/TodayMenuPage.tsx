import { CalendarDays, ClipboardList, Pencil } from 'lucide-react'
import { Link } from 'react-router-dom'

import { FoodIcon } from '@/components/FoodIcon'
import { PageHeader } from '@/components/PageHeader'
import { EmptyState, ErrorState, LoadingCards } from '@/components/StateViews'
import { zhCN } from '@/i18n/zh-CN'
import { computePlateNutrition, type PlateIngredient, type NutrientResult } from '@/lib/calculator'
import { formatAmount } from '@/lib/format'
import { useWeeklyPlan } from '@/lib/queries'
import type { FoodDetail } from '@/lib/types'

import { PlannerNutrition } from '@/features/planner/PlannerNutrition'
import {
  draftFromResponse,
  formatPlanDate,
  mealDisplayLabel,
  parseISODateLocal,
  plannerFoodItem,
  plannerFoodKey,
  snackNumbers,
  startOfWeekISO,
  todayISO,
  weekdayIndex,
  weekDays,
  type PlannerDraftDay,
  type PlannerDraftItem,
} from '@/features/planner/model'
import { usePlannerFoodDetails } from '@/features/planner/usePlannerFoodDetails'

import styles from './TodayMenuPage.module.css'

function itemName(item: PlannerDraftItem, detail?: FoodDetail): string {
  if (detail) {
    return detail.name_zh && detail.zh_status !== 'none' ? detail.name_zh : detail.description_en
  }
  return item.name || zhCN.planner.foodFallback(item.foodKey)
}

function mealIngredients(
  day: PlannerDraftDay,
  details: Map<string, FoodDetail>,
): PlateIngredient[] {
  return day.meals.flatMap((meal) =>
    meal.items.flatMap((item) => {
      const detail = details.get(plannerFoodKey(item.foodKey, item.scope))
      if (!detail) return []
      return [
        {
          foodKey: plannerFoodKey(item.foodKey, item.scope),
          grams: item.grams,
          summary: detail.summary_per_100g,
        },
      ]
    }),
  )
}

function dayItemCount(day: PlannerDraftDay): number {
  return day.meals.reduce((total, meal) => total + meal.items.length, 0)
}

/** 今日餐单：按本地日期定位今天，展示四餐食品与克数，并可进入每周计划修改。 */
export function TodayMenuPage() {
  const today = todayISO()
  const weekStart = startOfWeekISO(today)
  const plan = useWeeklyPlan(weekStart)

  const draft =
    plan.data && plan.data.week_start === weekStart ? draftFromResponse(plan.data) : null
  const day = draft?.days.find((item) => item.date === today)
  const allItems = day?.meals.flatMap((meal) => meal.items) ?? []
  const { details, isLoading, hasError, isEnriching } = usePlannerFoodDetails(allItems)

  const year = parseISODateLocal(today).getFullYear()
  const weekday = zhCN.planner.weekdayNames[weekdayIndex(today)]
  const todayLabel = `${formatPlanDate(today)} · ${weekday}`

  if (plan.isError) {
    return (
      <div className={styles.page}>
        <PageHeader title={zhCN.planner.todayTitle} subtitle={zhCN.planner.todaySubtitle} />
        <ErrorState
          message={zhCN.planner.loadError}
          hint={plan.error instanceof Error ? plan.error.message : undefined}
          onRetry={() => void plan.refetch()}
        />
      </div>
    )
  }

  if (!draft || !day) {
    return (
      <div className={styles.page}>
        <PageHeader title={zhCN.planner.todayTitle} subtitle={zhCN.planner.todaySubtitle} />
        <p className={styles.loadingText}>{zhCN.common.loading}</p>
        <LoadingCards count={4} />
      </div>
    )
  }

  const itemCount = dayItemCount(day)
  const totals = computePlateNutrition(mealIngredients(day, details))
  const snacks = snackNumbers(day.meals)

  const mealResults = (mealItems: PlannerDraftItem[]): NutrientResult[] =>
    computePlateNutrition(
      mealItems.flatMap((item) => {
        const detail = details.get(plannerFoodKey(item.foodKey, item.scope))
        if (!detail) return []
        return [
          {
            foodKey: plannerFoodKey(item.foodKey, item.scope),
            grams: item.grams,
            summary: detail.summary_per_100g,
          },
        ]
      }),
    )

  return (
    <div className={styles.page}>
      <PageHeader
        title={zhCN.planner.todayTitle}
        subtitle={zhCN.planner.todaySubtitle}
        aside={
          <Link to={`/weekly?week=${weekStart}`} className={styles.headerLink}>
            <CalendarDays size={15} aria-hidden="true" />
            {zhCN.planner.weeklyAction}
          </Link>
        }
      />

      <section className={styles.summaryBar} aria-label={zhCN.planner.todayTitle}>
        <div className={styles.todayInfo}>
          <span className={styles.todayBadge}>{zhCN.planner.todayBadge}</span>
          <div>
            <strong>{todayLabel}</strong>
            <span className={styles.weekRange}>
              {zhCN.planner.weekRange(
                year,
                formatPlanDate(weekStart),
                formatPlanDate(weekDays(weekStart)[6]),
              )}
            </span>
          </div>
        </div>
        <ClipboardList size={20} aria-hidden="true" className={styles.summaryIcon} />
      </section>

      {itemCount === 0 ? (
        <EmptyState
          title={zhCN.planner.todayEmptyTitle}
          description={zhCN.planner.todayEmptyDesc}
          action={
            <Link to={`/weekly?date=${today}`} className={styles.emptyAction}>
              {zhCN.planner.todayEmptyAction}
            </Link>
          }
        />
      ) : (
        <>
          <div className={styles.mealList}>
            {day.meals.map((meal) => {
              const results = mealResults(meal.items)
              const label = mealDisplayLabel(meal, snacks.get(meal.clientId) ?? 0)
              return (
                <article
                  key={meal.clientId}
                  className={styles.mealCard}
                  data-meal-type={meal.mealType}
                  aria-label={label}
                >
                  <header className={styles.mealHeader}>
                    <h2 className={styles.mealTitle}>{label}</h2>
                    <span className={styles.mealCount}>
                      {meal.items.length > 0 ? zhCN.common.totalItems(meal.items.length) : null}
                    </span>
                    <Link
                      to={`/weekly?date=${today}&meal=${meal.mealType}`}
                      className={styles.editLink}
                      aria-label={`${zhCN.planner.editTodayMeal}：${label}`}
                    >
                      <Pencil size={13} aria-hidden="true" />
                      {zhCN.planner.editTodayMeal}
                    </Link>
                  </header>

                  {meal.items.length === 0 ? (
                    <p className={styles.emptyMeal}>{zhCN.planner.emptyMeal}</p>
                  ) : (
                    <>
                      <ul className={styles.items}>
                        {meal.items.map((item) => {
                          const detail = details.get(plannerFoodKey(item.foodKey, item.scope))
                          const food = plannerFoodItem(item, detail)
                          const name = itemName(item, detail)
                          return (
                            <li className={styles.item} key={item.clientId}>
                              <FoodIcon food={food} size={32} label={zhCN.a11y.foodIcon(name)} />
                              <span className={styles.itemName}>{name}</span>
                              <span className={styles.itemGrams}>
                                {formatAmount(item.grams, 0)}
                                <em>{zhCN.designer.unitGram}</em>
                              </span>
                            </li>
                          )
                        })}
                      </ul>
                      <PlannerNutrition
                        results={results}
                        itemCount={meal.items.length}
                        isLoading={isLoading}
                        hasError={hasError}
                        isEnriching={isEnriching}
                      />
                    </>
                  )}
                </article>
              )
            })}
          </div>

          <section className={styles.dayTotal} aria-label={zhCN.planner.dayTotal}>
            <header className={styles.dayTotalHeader}>
              <h2>{zhCN.planner.dayTotal}</h2>
              <span>{zhCN.common.totalItems(itemCount)}</span>
            </header>
            <PlannerNutrition
              results={totals}
              itemCount={itemCount}
              isLoading={isLoading}
              hasError={hasError}
              isEnriching={isEnriching}
            />
          </section>
        </>
      )}

      <Link to={`/weekly?week=${weekStart}`} className={styles.backLink}>
        {zhCN.planner.weeklyAction}
      </Link>
    </div>
  )
}
