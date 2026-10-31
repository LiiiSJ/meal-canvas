import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  Plus,
  Save,
  Trash2,
  Undo2,
  X,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { FoodDetailDrawer } from '@/components/FoodDetailDrawer'
import { PageHeader } from '@/components/PageHeader'
import { ErrorState, LoadingCards } from '@/components/StateViews'
import { zhCN } from '@/i18n/zh-CN'
import { computePlateNutrition, type PlateIngredient } from '@/lib/calculator'
import { formatAmount } from '@/lib/format'
import { useDeleteWeeklyPlan, useSaveWeeklyPlan, useWeeklyPlan } from '@/lib/queries'
import type { FoodDetail, FoodItem, LibraryScope, MealType } from '@/lib/types'

import { FoodPicker, type PickedFood } from '@/features/planner/FoodPicker'
import { MealCard } from '@/features/planner/MealCard'
import { PlannerNutrition } from '@/features/planner/PlannerNutrition'
import {
  addFoods,
  addSnack,
  copyMeal,
  createEmptyDraft,
  deleteMeal,
  draftFromResponse,
  draftToPayload,
  formatPlanDate,
  hasDraftContent,
  hasUnsavedChanges,
  isToday,
  isValidISODate,
  mealDisplayLabel,
  nextSaveStatus,
  parseISODateLocal,
  plannerFoodKey,
  removeItem,
  setItemGrams,
  shiftWeekISO,
  snackNumbers,
  snackOrdinal,
  startOfWeekISO,
  todayISO,
  weekdayIndex,
  weekDays,
  type PlannerDraft,
  type PlannerDraftDay,
  type PlannerDraftItem,
  type PlannerDraftMeal,
  type PlannerSaveStatus,
} from '@/features/planner/model'
import { usePlannerFoodDetails } from '@/features/planner/usePlannerFoodDetails'

import styles from './WeeklyPlanPage.module.css'

interface PickerTarget {
  date: string
  mealClientId: string
  label: string
}

interface CopySource {
  date: string
  mealClientId: string
  label: string
}

interface UndoState {
  message: string
  previous: PlannerDraft
}

const MEAL_FOCUS_TYPES: readonly MealType[] = ['breakfast', 'lunch', 'dinner', 'snack']

function primaryName(food: FoodItem): string {
  return food.name_zh && food.zh_status !== 'none' ? food.name_zh : food.description_en
}

function detailName(detail: FoodDetail): string {
  return detail.name_zh && detail.zh_status !== 'none' ? detail.name_zh : detail.description_en
}

function itemDisplayName(item: PlannerDraftItem, detail?: FoodDetail): string {
  if (detail) return detailName(detail)
  return item.name || zhCN.planner.foodFallback(item.foodKey)
}

function dayItemCount(day: PlannerDraftDay): number {
  return day.meals.reduce((total, meal) => total + meal.items.length, 0)
}

/** 计划页：周工具栏、每天四餐、食品增删改、复制餐次、保存四态与今日定位。 */
export function WeeklyPlanPage() {
  const [params, setParams] = useSearchParams()
  const weekParam = params.get('week')
  const dateParam = params.get('date')
  const focusMealRaw = params.get('meal')

  const today = todayISO()

  const weekStart = useMemo(() => {
    if (weekParam && isValidISODate(weekParam)) return startOfWeekISO(weekParam)
    if (dateParam && isValidISODate(dateParam)) return startOfWeekISO(dateParam)
    return startOfWeekISO(today)
  }, [weekParam, dateParam, today])

  const focusDate =
    dateParam && isValidISODate(dateParam) && weekDays(weekStart).includes(dateParam)
      ? dateParam
      : null
  const focusMeal =
    focusMealRaw && (MEAL_FOCUS_TYPES as readonly string[]).includes(focusMealRaw)
      ? (focusMealRaw as MealType)
      : null

  const plan = useWeeklyPlan(weekStart)
  const savePlan = useSaveWeeklyPlan()
  const deletePlan = useDeleteWeeklyPlan()

  const [draft, setDraft] = useState<PlannerDraft | null>(null)
  const [status, setStatus] = useState<PlannerSaveStatus>('clean')
  const [saveError, setSaveError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [undoState, setUndoState] = useState<UndoState | null>(null)
  const [picker, setPicker] = useState<PickerTarget | null>(null)
  const [copySource, setCopySource] = useState<CopySource | null>(null)
  const [copyTarget, setCopyTarget] = useState<string | null>(null)
  const [pendingSwitch, setPendingSwitch] = useState<string | null>(null)
  const [activeDetail, setActiveDetail] = useState<{ key: number; scope: LibraryScope } | null>(null)

  const loadedWeekRef = useRef<string | null>(null)
  const scrolledRef = useRef<string | null>(null)

  // 只在整周响应与当前周一致且周发生变化时初始化草稿，避免保存/后台刷新重置编辑内容。
  useEffect(() => {
    if (!plan.data || plan.data.week_start !== weekStart) return
    if (loadedWeekRef.current === weekStart) return
    loadedWeekRef.current = weekStart
    setDraft(draftFromResponse(plan.data))
    setStatus(plan.data.plan_id !== null ? 'saved' : 'clean')
    setSaveError(null)
    setUndoState(null)
    setPicker(null)
    setCopySource(null)
  }, [plan.data, weekStart])

  useEffect(() => {
    if (!notice) return
    const timer = window.setTimeout(() => setNotice(null), 4000)
    return () => window.clearTimeout(timer)
  }, [notice])

  const allItems = draft?.days.flatMap((day) => day.meals.flatMap((meal) => meal.items)) ?? []
  const { details, isLoading, hasError, isEnriching } = usePlannerFoodDetails(allItems)

  // 今日餐单带 ?date=&meal= 跳转过来时，滚动到对应餐次一次即可。
  useEffect(() => {
    if (!focusDate || !draft || draft.weekStart !== weekStart) return
    const key = `${weekStart}:${focusDate}:${focusMeal ?? ''}`
    if (scrolledRef.current === key) return
    scrolledRef.current = key
    const target = document.getElementById(`plan-day-${focusDate}`)
    if (!target) return
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    window.setTimeout(() => {
      target.scrollIntoView({ block: 'center', behavior: reduced ? 'auto' : 'smooth' })
    }, 60)
  }, [focusDate, focusMeal, draft, weekStart])

  if (plan.isError) {
    return (
      <div className={styles.page}>
        <PageHeader title={zhCN.planner.weeklyTitle} subtitle={zhCN.planner.weeklySubtitle} />
        <ErrorState
          message={zhCN.planner.loadError}
          hint={plan.error instanceof Error ? plan.error.message : undefined}
          onRetry={() => void plan.refetch()}
        />
      </div>
    )
  }

  if (!draft || draft.weekStart !== weekStart || plan.data?.week_start !== weekStart) {
    return (
      <div className={styles.page}>
        <PageHeader title={zhCN.planner.weeklyTitle} subtitle={zhCN.planner.weeklySubtitle} />
        <p className={styles.loadingText}>{zhCN.common.loading}</p>
        <LoadingCards count={4} />
      </div>
    )
  }

  const navigateWeek = (nextWeek: string) => {
    const next = new URLSearchParams()
    next.set('week', nextWeek)
    setParams(next, { replace: true })
  }

  const requestWeek = (nextWeek: string) => {
    if (hasUnsavedChanges(status)) {
      setPendingSwitch(nextWeek)
      return
    }
    navigateWeek(nextWeek)
  }

  const applyDraft = (next: PlannerDraft, undoMessage?: string) => {
    if (next === draft) return
    setUndoState(undoMessage ? { message: undoMessage, previous: draft } : null)
    setDraft(next)
    setStatus((current) => nextSaveStatus(current, 'edit'))
  }

  const handleSave = async (): Promise<boolean> => {
    setStatus('saving')
    setSaveError(null)
    try {
      const response = await savePlan.mutateAsync({
        weekStart,
        payload: draftToPayload(draft),
      })
      loadedWeekRef.current = response.week_start
      setStatus('saved')
      setNotice(zhCN.planner.saveSuccess)
      setUndoState(null)
      return true
    } catch (error) {
      setStatus('error')
      setSaveError(error instanceof Error ? error.message : zhCN.planner.saveFailed)
      return false
    }
  }

  const handleDeletePlan = async () => {
    if (!window.confirm(zhCN.planner.deletePlanConfirm)) return
    try {
      await deletePlan.mutateAsync(weekStart)
      const empty = createEmptyDraft(weekStart)
      loadedWeekRef.current = weekStart
      setDraft(empty)
      setStatus('clean')
      setSaveError(null)
      setUndoState(null)
      setNotice(zhCN.planner.deletePlanDone)
    } catch (error) {
      setNotice(error instanceof Error ? error.message : zhCN.planner.saveFailed)
    }
  }

  const handleUndo = () => {
    if (!undoState) return
    setDraft(undoState.previous)
    setStatus((current) => nextSaveStatus(current, 'edit'))
    setUndoState(null)
  }

  const handleSaveAndSwitch = async () => {
    if (!pendingSwitch) return
    const saved = await handleSave()
    if (saved) {
      setPendingSwitch(null)
      navigateWeek(pendingSwitch)
    }
  }

  const snackNumberFor = (day: PlannerDraftDay, meal: PlannerDraftMeal): number =>
    snackNumbers(day.meals).get(meal.clientId) ?? snackOrdinal(day, meal.clientId)

  const openPicker = (day: PlannerDraftDay, meal: PlannerDraftMeal) => {
    setPicker({
      date: day.date,
      mealClientId: meal.clientId,
      label: mealDisplayLabel(meal, snackNumberFor(day, meal)),
    })
  }

  const handlePickFoods = (items: PickedFood[]) => {
    if (!picker) return
    const result = addFoods(
      draft,
      picker.date,
      picker.mealClientId,
      items.map(({ food, grams }) => ({
        ref: {
          foodKey: String(food.fdc_id),
          scope: food.library_scope,
          name: primaryName(food),
        },
        grams,
      })),
    )
    if (result.added > 0) {
      applyDraft(result.draft)
    }
    setNotice(zhCN.planner.pickerAddedNotice(result.added, result.skipped))
    setPicker(null)
  }

  const handleSetGrams = (
    date: string,
    mealClientId: string,
    itemClientId: string,
    grams: number,
  ) => {
    applyDraft(setItemGrams(draft, date, mealClientId, itemClientId, grams))
  }

  const handleRemoveItem = (day: PlannerDraftDay, meal: PlannerDraftMeal, item: PlannerDraftItem) => {
    const detail = details.get(plannerFoodKey(item.foodKey, item.scope))
    const next = removeItem(draft, day.date, meal.clientId, item.clientId)
    applyDraft(next, zhCN.planner.undoRemoved(itemDisplayName(item, detail)))
  }

  const handleDeleteMeal = (day: PlannerDraftDay, meal: PlannerDraftMeal) => {
    const label = mealDisplayLabel(meal, snackNumberFor(day, meal))
    const next = deleteMeal(draft, day.date, meal.clientId)
    const message =
      meal.mealType === 'snack' ? zhCN.planner.undoSnackDeleted : zhCN.planner.undoCleared(label)
    applyDraft(next, message)
  }

  const handleAddSnack = (day: PlannerDraftDay) => {
    const result = addSnack(draft, day.date)
    if (result.draft === draft) return
    setDraft(result.draft)
    setStatus((current) => nextSaveStatus(current, 'edit'))
    setUndoState(null)
    const nextDay = result.draft.days.find((item) => item.date === day.date)
    const ordinal = nextDay ? snackNumbers(nextDay.meals).get(result.mealClientId) ?? 1 : 1
    setPicker({
      date: day.date,
      mealClientId: result.mealClientId,
      label: zhCN.planner.snackOrdinal(ordinal),
    })
  }

  const handleCopy = (day: PlannerDraftDay, meal: PlannerDraftMeal) => {
    const others = weekDays(weekStart).filter((date) => date !== day.date)
    setCopySource({
      date: day.date,
      mealClientId: meal.clientId,
      label: mealDisplayLabel(meal, snackNumberFor(day, meal)),
    })
    setCopyTarget(others[0] ?? null)
  }

  const confirmCopy = () => {
    if (!copySource || !copyTarget) return
    const next = copyMeal(draft, copySource.date, copySource.mealClientId, copyTarget)
    if (next === draft) {
      setCopySource(null)
      return
    }
    applyDraft(next)
    setNotice(
      zhCN.planner.copySuccess(formatPlanDate(copyTarget), copySource.label),
    )
    setCopySource(null)
    setCopyTarget(null)
  }

  const dayIngredients = (day: PlannerDraftDay): PlateIngredient[] =>
    day.meals.flatMap((meal) =>
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

  const energyOverview = draft.days.map((day) => {
    const results = computePlateNutrition(dayIngredients(day))
    const energy = results.find((result) => result.key === 'energy_kcal')
    return {
      date: day.date,
      itemCount: dayItemCount(day),
      energy,
    }
  })
  const maxEnergy = Math.max(
    0,
    ...energyOverview
      .filter((entry) => entry.energy && entry.energy.status !== 'all_missing')
      .map((entry) => entry.energy?.knownValue ?? 0),
  )

  const currentWeek = weekStart === startOfWeekISO(today)
  const pickerMeal = picker
    ? draft.days
        .find((day) => day.date === picker.date)
        ?.meals.find((meal) => meal.clientId === picker.mealClientId)
    : undefined
  const copyTargets = copySource
    ? weekDays(weekStart).filter((date) => date !== copySource.date)
    : []
  const copySourceMealType = copySource
    ? draft.days
        .find((day) => day.date === copySource.date)
        ?.meals.find((meal) => meal.clientId === copySource.mealClientId)?.mealType
    : undefined
  const copyWillReplace =
    copyTarget && copySourceMealType
      ? (draft.days.find((day) => day.date === copyTarget)?.meals ?? []).some(
          (meal) => meal.mealType === copySourceMealType && meal.items.length > 0,
        )
      : false

  const statusText: Record<PlannerSaveStatus, string> = {
    clean: zhCN.planner.statusClean,
    dirty: zhCN.planner.dirty,
    saving: zhCN.planner.saving,
    saved: zhCN.planner.saveSuccess,
    error: zhCN.planner.saveFailed,
  }

  return (
    <div className={styles.page}>
      <PageHeader
        title={zhCN.planner.weeklyTitle}
        subtitle={zhCN.planner.weeklySubtitle}
        aside={
          <Link to={`/today?date=${today}`} className={styles.headerLink}>
            <ClipboardList size={15} aria-hidden="true" />
            {zhCN.planner.todayAction}
          </Link>
        }
      />

      <section className={styles.toolbar} aria-label={zhCN.planner.weeklyTitle}>
        <div className={styles.weekNav}>
          <button
            type="button"
            className={styles.navButton}
            onClick={() => requestWeek(shiftWeekISO(weekStart, -1))}
            aria-label={zhCN.planner.prevWeek}
            title={zhCN.planner.prevWeek}
          >
            <ChevronLeft size={17} aria-hidden="true" />
          </button>
          <div className={styles.weekLabel}>
            <strong>
              {zhCN.planner.weekRange(
                parseISODateLocal(weekStart).getFullYear(),
                formatPlanDate(weekStart),
                formatPlanDate(weekDays(weekStart)[6]),
              )}
            </strong>
            <span className={styles.weekHint}>
              <CalendarDays size={13} aria-hidden="true" />
              {currentWeek ? zhCN.planner.currentWeek : zhCN.planner.backToThisWeek}
            </span>
          </div>
          <button
            type="button"
            className={styles.navButton}
            onClick={() => requestWeek(shiftWeekISO(weekStart, 1))}
            aria-label={zhCN.planner.nextWeek}
            title={zhCN.planner.nextWeek}
          >
            <ChevronRight size={17} aria-hidden="true" />
          </button>
          <button
            type="button"
            className={styles.thisWeekButton}
            onClick={() => requestWeek(startOfWeekISO(today))}
            disabled={currentWeek}
          >
            {zhCN.planner.backToThisWeek}
          </button>
        </div>

        <div className={styles.saveArea}>
          <span className={styles.statusChip} data-status={status} role="status">
            {statusText[status]}
          </span>
          <button
            type="button"
            className={styles.saveButton}
            onClick={() => void handleSave()}
            disabled={status === 'saving'}
          >
            <Save size={15} aria-hidden="true" />
            {status === 'saving' ? zhCN.planner.saving : zhCN.planner.save}
          </button>
          <button
            type="button"
            className={styles.deleteButton}
            onClick={() => void handleDeletePlan()}
            disabled={deletePlan.isPending || !hasDraftContent(draft)}
            title={zhCN.planner.deletePlan}
          >
            <Trash2 size={15} aria-hidden="true" />
            {zhCN.planner.deletePlan}
          </button>
        </div>
      </section>

      {saveError ? (
        <p className={styles.saveError} role="alert">
          {zhCN.planner.saveErrorDetail(saveError)}
        </p>
      ) : null}

      {undoState || notice ? (
        <div className={styles.noticeBar} role="status">
          <span>{undoState ? undoState.message : notice}</span>
          {undoState ? (
            <button type="button" className={styles.noticeAction} onClick={handleUndo}>
              <Undo2 size={13} aria-hidden="true" />
              {zhCN.planner.undo}
            </button>
          ) : null}
          <button
            type="button"
            className={styles.noticeClose}
            onClick={() => {
              setUndoState(null)
              setNotice(null)
            }}
            aria-label={zhCN.common.close}
          >
            <X size={13} aria-hidden="true" />
          </button>
        </div>
      ) : null}

      {!hasDraftContent(draft) ? (
        <p className={styles.emptyPlanNote}>{zhCN.planner.emptyPlan}</p>
      ) : null}

      <div className={styles.dayList}>
        {draft.days.map((day) => {
          const emptyDay = !day.meals.some((meal) => meal.items.length > 0)
          const isTodayDay = isToday(day.date)
          const ingredients = dayIngredients(day)
          const totals = computePlateNutrition(ingredients)
          const count = dayItemCount(day)
          return (
            <section
              key={day.date}
              id={`plan-day-${day.date}`}
              className={`${styles.dayCard} ${isTodayDay ? styles.todayCard : ''}`}
              aria-label={`${zhCN.planner.weekdayNames[weekdayIndex(day.date)]} ${formatPlanDate(day.date)}`}
            >
              <header className={styles.dayHeader}>
                <div className={styles.dayTitle}>
                  <strong>{zhCN.planner.weekdayNames[weekdayIndex(day.date)]}</strong>
                  <span>{formatPlanDate(day.date)}</span>
                  {isTodayDay ? (
                    <span className={styles.todayBadge}>{zhCN.planner.todayBadge}</span>
                  ) : null}
                </div>
                <div className={styles.dayActions}>
                  {emptyDay ? <span className={styles.emptyDayText}>{zhCN.planner.emptyDay}</span> : null}
                  <button type="button" className={styles.addSnackButton} onClick={() => handleAddSnack(day)}>
                    <Plus size={13} aria-hidden="true" />
                    {zhCN.planner.addSnack}
                  </button>
                </div>
              </header>

              <div className={styles.mealGrid}>
                {day.meals.map((meal) => {
                  const highlighted =
                    !focusDate || focusDate === day.date
                      ? focusMeal === meal.mealType
                      : false
                  return (
                    <MealCard
                      key={`${day.date}-${meal.clientId}`}
                      meal={meal}
                      snackNumber={snackNumbers(day.meals).get(meal.clientId) ?? 0}
                      details={details}
                      isLoading={isLoading}
                      hasError={hasError}
                      isEnriching={isEnriching}
                      highlighted={highlighted}
                      onAddFood={() => openPicker(day, meal)}
                      onSetGrams={(itemClientId, grams) =>
                        handleSetGrams(day.date, meal.clientId, itemClientId, grams)
                      }
                      onRemoveItem={(item) => handleRemoveItem(day, meal, item)}
                      onDeleteMeal={() => handleDeleteMeal(day, meal)}
                      onCopyMeal={() => handleCopy(day, meal)}
                      onOpenDetail={(foodKey, scope) => {
                        const numeric = Number(foodKey)
                        if (Number.isFinite(numeric)) setActiveDetail({ key: numeric, scope })
                      }}
                    />
                  )
                })}
              </div>

              {count > 0 ? (
                <div className={styles.dayTotal}>
                  <h3 className={styles.dayTotalTitle}>
                    {zhCN.planner.dayTotal}
                    <span>{zhCN.common.totalItems(count)}</span>
                  </h3>
                  <PlannerNutrition
                    results={totals}
                    itemCount={count}
                    isLoading={isLoading}
                    hasError={hasError}
                    isEnriching={isEnriching}
                  />
                </div>
              ) : null}
            </section>
          )
        })}
      </div>

      <section className={styles.energySection} aria-label={zhCN.planner.weekEnergy}>
        <h2 className={styles.sectionTitle}>{zhCN.planner.weekEnergy}</h2>
        <p className={styles.sectionHint}>{zhCN.planner.weekEnergyHint}</p>
        <ul className={styles.energyList}>
          {energyOverview.map((entry) => {
            const energy = entry.energy
            const hasValue = energy && energy.status !== 'all_missing'
            const percent = hasValue && maxEnergy > 0 ? Math.max(4, (energy.knownValue / maxEnergy) * 100) : 0
            const weekday = zhCN.planner.weekdayNames[weekdayIndex(entry.date)]
            const dateLabel = formatPlanDate(entry.date)
            const display = hasValue ? formatAmount(energy.knownValue, 0) : zhCN.common.notAvailable
            return (
              <li key={entry.date} className={styles.energyRow}>
                <span className={styles.energyDate}>
                  {weekday}
                  <small>{dateLabel}</small>
                </span>
                <span
                  className={styles.energyTrack}
                  role="img"
                  aria-label={`${weekday} ${dateLabel}：${
                    hasValue ? `${display} ${zhCN.planner.kcal}` : zhCN.common.notAvailable
                  }`}
                >
                  <span
                    className={styles.energyFill}
                    style={{ width: `${percent}%` }}
                    data-empty={hasValue ? undefined : 'true'}
                  />
                </span>
                <span className={styles.energyValue}>
                  {hasValue && energy.status === 'partial' ? (
                    <small>{zhCN.designer.knownPrefix}</small>
                  ) : null}
                  {display}
                  {hasValue ? <em>{zhCN.planner.kcal}</em> : null}
                </span>
              </li>
            )
          })}
        </ul>
        <p className={styles.energyNote}>{zhCN.planner.weekEnergyHint}</p>
      </section>

      {picker ? (
        <FoodPicker
          mealLabel={picker.label}
          onPickAll={handlePickFoods}
          onClose={() => setPicker(null)}
          isAdded={(food) =>
            pickerMeal?.items.some(
              (item) =>
                item.foodKey === String(food.fdc_id) && item.scope === food.library_scope,
            ) ?? false
          }
        />
      ) : null}

      {copySource ? (
        <div
          className={styles.dialogOverlay}
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              setCopySource(null)
              setCopyTarget(null)
            }
          }}
        >
          <section
            className={styles.dialog}
            role="dialog"
            aria-modal="true"
            aria-label={zhCN.planner.copyTitle(copySource.label)}
          >
            <header className={styles.dialogHeader}>
              <h2>{zhCN.planner.copyTitle(copySource.label)}</h2>
              <button
                type="button"
                className={styles.dialogClose}
                onClick={() => {
                  setCopySource(null)
                  setCopyTarget(null)
                }}
                aria-label={zhCN.common.close}
              >
                <X size={16} aria-hidden="true" />
              </button>
            </header>
            <p className={styles.dialogHint}>{zhCN.planner.copyHint}</p>
            <div className={styles.dialogField}>
              <span>{zhCN.planner.copySource}</span>
              <strong>
                {formatPlanDate(copySource.date)} · {copySource.label}
              </strong>
            </div>
            <div className={styles.dialogField}>
              <span>{zhCN.planner.copyTarget}</span>
              <ul className={styles.targetList}>
                {copyTargets.map((date) => (
                  <li key={date}>
                    <button
                      type="button"
                      className={`${styles.targetButton} ${copyTarget === date ? styles.targetActive : ''}`}
                      onClick={() => setCopyTarget(date)}
                    >
                      <span>{zhCN.planner.weekdayNames[weekdayIndex(date)]}</span>
                      <small>{formatPlanDate(date)}</small>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
            {copyWillReplace ? (
              <p className={styles.dialogWarn}>{zhCN.planner.copyReplaceWarn}</p>
            ) : null}
            <footer className={styles.dialogFooter}>
              <button
                type="button"
                className={styles.dialogCancel}
                onClick={() => {
                  setCopySource(null)
                  setCopyTarget(null)
                }}
              >
                {zhCN.common.cancel}
              </button>
              <button
                type="button"
                className={styles.dialogConfirm}
                onClick={confirmCopy}
                disabled={!copyTarget}
              >
                {zhCN.planner.copyConfirm}
              </button>
            </footer>
          </section>
        </div>
      ) : null}

      {pendingSwitch ? (
        <div className={styles.dialogOverlay}>
          <section
            className={styles.dialog}
            role="dialog"
            aria-modal="true"
            aria-label={zhCN.planner.unsavedTitle}
          >
            <header className={styles.dialogHeader}>
              <h2>{zhCN.planner.unsavedTitle}</h2>
            </header>
            <p className={styles.dialogHint}>{zhCN.planner.unsavedDesc}</p>
            <footer className={styles.dialogFooter}>
              <button
                type="button"
                className={styles.dialogCancel}
                onClick={() => setPendingSwitch(null)}
              >
                {zhCN.planner.unsavedStay}
              </button>
              <button
                type="button"
                className={styles.dialogCancel}
                onClick={() => {
                  navigateWeek(pendingSwitch)
                  setPendingSwitch(null)
                }}
              >
                {zhCN.planner.unsavedDiscard}
              </button>
              <button
                type="button"
                className={styles.dialogConfirm}
                onClick={() => void handleSaveAndSwitch()}
                disabled={status === 'saving'}
              >
                {status === 'saving' ? zhCN.planner.saving : zhCN.planner.unsavedSaveAndGo}
              </button>
            </footer>
          </section>
        </div>
      ) : null}

      <FoodDetailDrawer
        foodKey={activeDetail?.key ?? null}
        scope={activeDetail?.scope ?? 'default'}
        onClose={() => setActiveDetail(null)}
      />
    </div>
  )
}
