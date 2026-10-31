import { ArrowRight, Bookmark, CalendarPlus, Trash2, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { usePlate } from '@/app/plate/usePlate'
import { usePlans } from '@/app/plans/usePlans'
import { foodIconComponents } from '@/assets/food-icons/icons'
import { Badge } from '@/components/Badge'
import { FoodDetailDrawer } from '@/components/FoodDetailDrawer'
import { FoodIcon } from '@/components/FoodIcon'
import { PageHeader } from '@/components/PageHeader'
import { zhCN } from '@/i18n/zh-CN'
import { computePlateNutrition, plateKey, type PlateIngredient } from '@/lib/calculator'
import type { FoodItem, LibraryScope } from '@/lib/types'

import { NutritionPanel } from '@/features/designer/NutritionPanel'
import { PlateItemControls } from '@/features/designer/PlateItemControls'
import { usePlateFoodDetails } from '@/features/designer/usePlateFoodDetails'
import { FoodLibrary } from '@/features/food-library/FoodLibrary'
import { AddPlateToPlanDialog } from '@/features/planner/AddPlateToPlanDialog'

import styles from './DesignerPage.module.css'

const PlateArt = foodIconComponents.plate

function foodName(food: FoodItem): string {
  return food.display_name || food.description_en
}

function formatCapturedAt(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

/** 餐盘设计工作台：左食材库，中可操作餐盘，右本餐营养。 */
export function DesignerPage() {
  const plate = usePlate()
  const plans = usePlans()
  const [active, setActive] = useState<{ key: number; scope: LibraryScope } | null>(null)
  const [planDialogOpen, setPlanDialogOpen] = useState(false)

  const { details, isLoading, hasError, isEnriching } = usePlateFoodDetails(plate.entries)

  const ingredients = useMemo<PlateIngredient[]>(() => {
    return plate.entries
      .map((entry) => {
        const detail = details.get(plateKey(entry.food))
        if (!detail) return null
        return {
          foodKey: plateKey(entry.food),
          grams: entry.grams,
          summary: detail.summary_per_100g,
        }
      })
      .filter((entry): entry is PlateIngredient => entry !== null)
  }, [plate.entries, details])

  const nutrition = useMemo(() => computePlateNutrition(ingredients), [ingredients])

  const planStatusText = [
    plans.slotA
      ? zhCN.designer.planStatus('A', plans.slotA.entries.length, formatCapturedAt(plans.slotA.capturedAt))
      : null,
    plans.slotB
      ? zhCN.designer.planStatus('B', plans.slotB.entries.length, formatCapturedAt(plans.slotB.capturedAt))
      : null,
  ]
    .filter((line): line is string => line !== null)
    .join('　｜　')

  return (
    <div className={styles.page}>
      <PageHeader
        title={zhCN.designer.title}
        subtitle={zhCN.designer.subtitle}
        aside={<Badge tone="outline">{zhCN.designer.plateCount(plate.entries.length)}</Badge>}
      />

      <div className={styles.workspace}>
        <div className={styles.libraryColumn}>
          <FoodLibrary onOpen={(food) => setActive({ key: food.fdc_id, scope: food.library_scope })} />
        </div>

        <section className={styles.platePanel} aria-label={zhCN.designer.plateTitle}>
          <header className={styles.plateHeader}>
            <h2 className={styles.panelTitle}>{zhCN.designer.plateTitle}</h2>
            <div className={styles.plateActions}>
              {(['A', 'B'] as const).map((slot) => {
                const saved = slot === 'A' ? plans.slotA : plans.slotB
                return (
                  <button
                    key={slot}
                    type="button"
                    className={styles.planButton}
                    onClick={() => plans.capture(slot, plate.entries)}
                    disabled={plate.entries.length === 0}
                    title={
                      plate.entries.length === 0
                        ? zhCN.compare.plateEmptyWarn
                        : (saved ? zhCN.designer.updatePlan(slot) : zhCN.designer.saveToPlan(slot))
                    }
                  >
                    <Bookmark size={14} aria-hidden="true" />
                    {saved ? zhCN.designer.updatePlan(slot) : zhCN.designer.saveToPlan(slot)}
                  </button>
                )
              })}
              <button
                type="button"
                className={styles.planButton}
                onClick={() => setPlanDialogOpen(true)}
                disabled={plate.entries.length === 0}
                title={
                  plate.entries.length === 0
                    ? zhCN.compare.plateEmptyWarn
                    : zhCN.planner.plateToPlanTitle(zhCN.designer.plateTitle)
                }
              >
                <CalendarPlus size={14} aria-hidden="true" />
                {zhCN.planner.plateToPlanAction}
              </button>
              <button
                type="button"
                className={styles.clearButton}
                onClick={plate.clear}
                disabled={plate.entries.length === 0}
              >
                <Trash2 size={14} aria-hidden="true" />
                {zhCN.designer.clearPlate}
              </button>
            </div>
          </header>

          <div className={styles.plateArea}>
            {plate.entries.length === 0 ? (
              <div className={styles.plateEmpty}>
                <PlateArt width={96} height={96} aria-hidden="true" />
                <h3 className={styles.plateEmptyTitle}>{zhCN.designer.plateEmptyTitle}</h3>
                <p className={styles.plateEmptyDesc}>{zhCN.designer.plateEmptyDesc}</p>
              </div>
            ) : (
              <ul className={styles.plateItems}>
                {plate.entries.map((entry) => {
                  const detail = details.get(plateKey(entry.food))
                  const name = foodName(entry.food)
                  return (
                    <li className={styles.plateItem} key={plateKey(entry.food)}>
                      <button
                        type="button"
                        className={styles.plateItemMain}
                        onClick={() =>
                          setActive({ key: entry.food.fdc_id, scope: entry.food.library_scope })
                        }
                        aria-label={zhCN.a11y.foodCard(name)}
                      >
                        <FoodIcon food={entry.food} size={36} label={zhCN.a11y.foodIcon(name)} />
                        <span className={styles.plateItemName}>{name}</span>
                      </button>
                      <button
                        type="button"
                        className={styles.plateItemRemove}
                        onClick={() => plate.remove(entry.food)}
                        aria-label={zhCN.a11y.removeFromPlate(name)}
                      >
                        <X size={13} aria-hidden="true" />
                      </button>
                      <button
                        type="button"
                        className={styles.plateItemPlan}
                        onClick={() =>
                          setActive({ key: entry.food.fdc_id, scope: entry.food.library_scope })
                        }
                        aria-label={`${zhCN.planner.addToPlanFromPlate}：${name}`}
                        title={zhCN.planner.addToPlanFromPlate}
                      >
                        <CalendarPlus size={13} aria-hidden="true" />
                      </button>
                      <PlateItemControls
                        food={entry.food}
                        grams={entry.grams}
                        portions={detail?.portions ?? []}
                        onGramsChange={(grams) => plate.setGrams(entry.food, grams)}
                      />
                    </li>
                  )
                })}
              </ul>
            )}
          </div>

          {planStatusText ? <p className={styles.planStatus}>{planStatusText}</p> : null}
          {plans.ready && !plans.storageAvailable ? (
            <p className={styles.planWarning} role="alert">
              {zhCN.designer.planStorageUnavailable}
            </p>
          ) : null}
          <p className={styles.plateNote}>
            {plate.isFull ? zhCN.designer.plateFullNote : zhCN.designer.plateDraftNote}
          </p>
        </section>

        <aside className={styles.insightColumn} aria-label={zhCN.designer.insightTitle}>
          <section className={styles.insightCard}>
            <header className={styles.insightHeader}>
              <h2 className={styles.panelTitle}>{zhCN.designer.insightTitle}</h2>
            </header>
            <NutritionPanel
              results={nutrition}
              isLoading={isLoading}
              hasError={hasError}
              ingredientCount={plate.entries.length}
              isEnriching={isEnriching}
            />
            {plate.entries.length > 0 ? (
              <Link to="/analysis" className={styles.analysisLink}>
                {zhCN.designer.analysisLink}
                <ArrowRight size={14} aria-hidden="true" />
              </Link>
            ) : null}
          </section>
        </aside>
      </div>

      <FoodDetailDrawer
        foodKey={active?.key ?? null}
        scope={active?.scope ?? 'default'}
        onClose={() => setActive(null)}
      />

      {planDialogOpen ? (
        <AddPlateToPlanDialog
          entries={plate.entries}
          sourceLabel={zhCN.designer.plateTitle}
          onClose={() => setPlanDialogOpen(false)}
        />
      ) : null}
    </div>
  )
}
