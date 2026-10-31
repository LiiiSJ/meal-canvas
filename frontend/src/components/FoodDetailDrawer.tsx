import { Check, ExternalLink, Plus, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

import { usePlate } from '@/app/plate/usePlate'
import { externalValueFor, mergeEnrichment, missingSummaryKeys } from '@/features/enrichment/merge'
import { AddToPlanForm } from '@/features/planner/AddToPlanForm'
import { Badge } from '@/components/Badge'
import { FoodIcon } from '@/components/FoodIcon'
import { ErrorState } from '@/components/StateViews'
import { zhCN } from '@/i18n/zh-CN'
import { formatAmount, formatDate } from '@/lib/format'
import { useEnrichedNutrients, useEnrichmentRefresh, useFoodDetail, useFoodNutrients } from '@/lib/queries'
import type { EnrichedValue, EnrichedValuesResponse, FoodDetail, LibraryScope, NutrientItem } from '@/lib/types'

import styles from './FoodDetailDrawer.module.css'

interface FoodDetailDrawerProps {
  foodKey: number | null
  scope: LibraryScope
  onClose: () => void
}

const CATEGORY_SOURCE_LABEL: Record<string, string> = {
  fdc: zhCN.drawer.categorySourceFdc,
  wweia: zhCN.drawer.categorySourceWweia,
  branded: zhCN.drawer.categorySourceBranded,
}

function qualityLabel(flag: string): string {
  return zhCN.qualityFlag[flag] ?? flag
}

/** 已核实外部补全值的徽章；有来源链接时可点击跳转。 */
function ExternalBadge({
  sourceName,
  sourceUrl,
}: {
  sourceName: string | null
  sourceUrl: string | null
}) {
  const tooltip = `${zhCN.enrich.externalNote}${sourceName ? ` ${zhCN.enrich.sourceLabel}：${sourceName}` : ''}`
  if (sourceUrl) {
    return (
      <a
        className={styles.enrichBadge}
        href={sourceUrl}
        target="_blank"
        rel="noopener noreferrer"
        title={tooltip}
      >
        {zhCN.enrich.badge}
      </a>
    )
  }
  return (
    <span className={styles.enrichBadge} title={tooltip}>
      {zhCN.enrich.badge}
    </span>
  )
}

function NutrientRow({ item, external }: { item: NutrientItem; external?: EnrichedValue | null }) {
  // USDA 无可用值时，已核实的外部补全值补位展示（带徽章与来源）；USDA 原值永不被覆盖。
  const filledByExternal = !item.is_available && external != null && external.value !== null
  const unavailable = !item.is_available && !filledByExternal
  return (
    <li className={`${styles.nutrientRow} ${unavailable ? styles.unavailable : ''}`}>
      <span className={styles.nutrientName}>
        <span>{item.name_zh}</span>
        <small lang="en">{item.name_en}</small>
      </span>
      <span className={styles.nutrientValue}>
        {filledByExternal
          ? formatAmount(external.value, external.decimals ?? item.decimals)
          : formatAmount(item.amount, item.decimals)}
        <em>{filledByExternal ? (external.unit_zh ?? item.unit_zh) : item.unit_zh}</em>
      </span>
      <span className={styles.nutrientStatus}>
        {filledByExternal ? (
          <ExternalBadge sourceName={external.source_name} sourceUrl={external.source_url} />
        ) : unavailable ? (
          <span className={styles.missingBadge}>{qualityLabel(item.quality_flag)}</span>
        ) : null}
      </span>
    </li>
  )
}

/** USDA 无对应营养行、仅由已核实外部来源提供的营养素（按 nutrient 元数据渲染）。 */
function ExternalNutrientRow({ value }: { value: EnrichedValue }) {
  return (
    <li className={styles.nutrientRow}>
      <span className={styles.nutrientName}>
        <span>{value.name_zh ?? value.key}</span>
      </span>
      <span className={styles.nutrientValue}>
        {formatAmount(value.value, value.decimals ?? 2)}
        <em>{value.unit_zh ?? ''}</em>
      </span>
      <span className={styles.nutrientStatus}>
        <ExternalBadge sourceName={value.source_name} sourceUrl={value.source_url} />
      </span>
    </li>
  )
}

function SummaryTile({
  label,
  value,
  unit,
  decimals,
  external,
}: {
  label: string
  value: number | null
  unit: string
  decimals: number
  /** 该值由外部来源补全时展示来源信息（USDA 原始值不显示）。 */
  external?: { sourceName: string | null; sourceUrl: string | null }
}) {
  const tooltip = external
    ? `${zhCN.enrich.externalNote}${external.sourceName ? ` ${zhCN.enrich.sourceLabel}：${external.sourceName}` : ''}`
    : undefined
  return (
    <div className={styles.summaryTile}>
      <span className={styles.summaryLabel}>{label}</span>
      <span className={styles.summaryValue}>
        {formatAmount(value, decimals)}
        <em>{unit}</em>
      </span>
      {external ? (
        <span className={styles.enrichBadge} title={tooltip}>
          {zhCN.enrich.badge}
        </span>
      ) : null}
    </div>
  )
}

/** 补全状态块：检索中 / 结果说明 / 候选参考来源 / 重新检索。 */
function EnrichmentBlock({ fdcId, missingCount }: { fdcId: number; missingCount: number }) {
  const enrich = useEnrichedNutrients(fdcId, missingCount > 0)
  const refresh = useEnrichmentRefresh(fdcId)

  if (missingCount === 0 && !enrich.data) return null

  if (enrich.isPending && missingCount > 0) {
    return <p className={styles.enrichStatus}>{zhCN.enrich.searching}</p>
  }
  if (enrich.isError) {
    return (
      <p className={styles.enrichStatus}>
        <span>
          {enrich.error instanceof Error ? enrich.error.message : zhCN.errors.network}
        </span>
        <button type="button" className={styles.textButton} onClick={() => void enrich.refetch()}>
          {zhCN.enrich.failedRetry}
        </button>
      </p>
    )
  }
  if (!enrich.data) return null

  const data: EnrichedValuesResponse = enrich.data
  const attempt = data.enrichment
  return (
    <div className={styles.enrichBlock}>
      <p className={styles.enrichStatus}>
        <span>{attempt.outcome === 'disabled' ? zhCN.enrich.disabledNote : attempt.message}</span>
        {attempt.outcome !== 'enriched' && attempt.outcome !== 'cached' && attempt.outcome !== 'no_missing' ? (
          <button
            type="button"
            className={styles.textButton}
            onClick={() => refresh.mutate()}
            disabled={refresh.isPending}
          >
            {refresh.isPending ? zhCN.enrich.refreshing : zhCN.enrich.refresh}
          </button>
        ) : null}
      </p>
      {data.candidates.length > 0 ? (
        <details className={styles.enrichCandidates}>
          <summary>
            {zhCN.enrich.candidatesTitle}（{data.candidates.length}）
          </summary>
          <p className={styles.enrichCandidatesHint}>{zhCN.enrich.candidatesHint}</p>
          <ul>
            {data.candidates.map((candidate, index) => (
              <li key={`${candidate.source_name}-${candidate.external_name_en}-${index}`}>
                <span lang="en">{candidate.external_name_en}</span>
                <span>
                  {candidate.source_name}
                  {candidate.match_level ? ` · ${candidate.match_level}` : ''}
                </span>
                {candidate.note ? <span className={styles.enrichNote}>{candidate.note}</span> : null}
                {candidate.source_url ? (
                  <a href={candidate.source_url} target="_blank" rel="noopener noreferrer">
                    {zhCN.enrich.viewSource}
                  </a>
                ) : null}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  )
}

function DetailBody({ food }: { food: FoodDetail }) {
  const [showAll, setShowAll] = useState(false)
  const detail = food
  const missing = missingSummaryKeys(food.summary_per_100g)
  const enrich = useEnrichedNutrients(food.fdc_id, missing.length > 0)
  // 展示用合并：只采纳已核实的外部值，USDA 原值与真实 0 不覆盖。
  const merged = enrich.data ? mergeEnrichment(food, enrich.data) : { detail: food, filledKeys: [] }
  const summary = merged.detail.summary_per_100g

  const externalFor = (key: string) => {
    if (!enrich.data || !merged.filledKeys.includes(key)) return undefined
    const item = externalValueFor(enrich.data, key)
    return item ? { sourceName: item.source_name, sourceUrl: item.source_url } : undefined
  }

  return (
    <>
      <div className={styles.zhNote}>
        <Badge
          tone={
            detail.zh_status === 'verified'
              ? 'green'
              : detail.zh_status === 'glossary'
                ? 'orange'
                : 'neutral'
          }
        >
          {zhCN.zhStatus[detail.zh_status as keyof typeof zhCN.zhStatus] ?? detail.zh_status}
        </Badge>
        {detail.zh_review_status === 'pending' ? (
          <Badge tone="outline">{zhCN.zhStatus.pending}</Badge>
        ) : null}
        <span>{zhCN.drawer.sourceNote}</span>
      </div>

      <section className={styles.section}>
        <h3 className={styles.sectionTitle}>{zhCN.drawer.basicInfo}</h3>
        <dl className={styles.infoGrid}>
          <div>
            <dt>{zhCN.library.fdcId}</dt>
            <dd className={styles.mono}>{detail.fdc_id}</dd>
          </div>
          <div>
            <dt>{zhCN.drawer.dataType}</dt>
            <dd>{zhCN.dataType[detail.data_type]?.label ?? detail.data_type}</dd>
          </div>
          <div>
            <dt>{zhCN.drawer.usageClass}</dt>
            <dd>
              {detail.usage_class
                ? (zhCN.usageClass[detail.usage_class]?.label ?? detail.usage_class)
                : zhCN.drawer.usageUnknown}
              {detail.usage_reason ? <small>{detail.usage_reason}</small> : null}
            </dd>
          </div>
          <div>
            <dt>{zhCN.drawer.dataset}</dt>
            <dd>{detail.source_dataset}</dd>
          </div>
          <div>
            <dt>{zhCN.drawer.version}</dt>
            <dd>{detail.source_version}</dd>
          </div>
          <div>
            <dt>{zhCN.drawer.category}</dt>
            <dd>
              {detail.category_zh ?? detail.category_en ?? zhCN.library.categoryUnknown}
              {detail.category_en && detail.category_zh ? (
                <small lang="en">{detail.category_en}</small>
              ) : null}
            </dd>
          </div>
          <div>
            <dt>{zhCN.drawer.categorySource}</dt>
            <dd>
              {CATEGORY_SOURCE_LABEL[
                detail.library_scope === 'branded'
                  ? 'branded'
                  : detail.data_type === 'survey_fndds_food'
                    ? 'wweia'
                    : 'fdc'
              ] ?? '—'}
            </dd>
          </div>
          <div>
            <dt>{zhCN.drawer.publicationDate}</dt>
            <dd>{formatDate(detail.publication_date)}</dd>
          </div>
          <div>
            <dt>{zhCN.drawer.knownCore}</dt>
            <dd>{zhCN.drawer.knownCoreCount(summary.known_core_count)}</dd>
          </div>
        </dl>

        {detail.library_scope === 'branded' ? (
          <dl className={styles.infoGrid}>
            <div>
              <dt>{zhCN.drawer.brandOwner}</dt>
              <dd>{detail.brand_owner ?? '—'}</dd>
            </div>
            <div>
              <dt>{zhCN.drawer.brandName}</dt>
              <dd>{detail.brand_name ?? '—'}</dd>
            </div>
            <div>
              <dt>{zhCN.drawer.gtin}</dt>
              <dd className={styles.mono}>{detail.gtin_upc ?? '—'}</dd>
            </div>
            <div>
              <dt>{zhCN.drawer.labelServing}</dt>
              <dd>
                {detail.serving_size !== null
                  ? `${formatAmount(detail.serving_size, 2)} ${detail.serving_unit ?? ''}`.trim()
                  : '—'}
              </dd>
            </div>
            <div>
              <dt>{zhCN.drawer.householdServing}</dt>
              <dd>{detail.household_serving ?? '—'}</dd>
            </div>
          </dl>
        ) : null}
      </section>

      <section className={styles.section}>
        <h3 className={styles.sectionTitle}>
          {zhCN.drawer.coreNutrients}
          {summary.protein_g === null || summary.energy_kcal === null ? (
            <span className={styles.sectionHint}>{zhCN.drawer.summaryMissing}</span>
          ) : null}
        </h3>
        <div className={styles.summaryGrid}>
          <SummaryTile
            label={zhCN.drawer.summaryEnergy}
            value={summary.energy_kcal}
            unit={zhCN.drawer.unitKcal}
            decimals={0}
            external={externalFor('energy_kcal')}
          />
          <SummaryTile
            label={zhCN.drawer.summaryProtein}
            value={summary.protein_g}
            unit={zhCN.drawer.unitGram}
            decimals={1}
            external={externalFor('protein_g')}
          />
          <SummaryTile
            label={zhCN.drawer.summaryFat}
            value={summary.fat_g}
            unit={zhCN.drawer.unitGram}
            decimals={1}
            external={externalFor('fat_g')}
          />
          <SummaryTile
            label={zhCN.drawer.summaryCarb}
            value={summary.carb_g}
            unit={zhCN.drawer.unitGram}
            decimals={1}
            external={externalFor('carb_g')}
          />
          <SummaryTile
            label={zhCN.drawer.summaryFiber}
            value={summary.fiber_g}
            unit={zhCN.drawer.unitGram}
            decimals={1}
            external={externalFor('fiber_g')}
          />
          <SummaryTile
            label={zhCN.drawer.summarySodium}
            value={summary.sodium_mg}
            unit={zhCN.drawer.unitMg}
            decimals={0}
            external={externalFor('sodium_mg')}
          />
        </div>
        <EnrichmentBlock fdcId={food.fdc_id} missingCount={missing.length} />
      </section>

      <NutrientSection detail={detail} showAll={showAll} onToggle={() => setShowAll((value) => !value)} />
    </>
  )
}

function NutrientSection({
  detail,
  showAll,
  onToggle,
}: {
  detail: FoodDetail
  showAll: boolean
  onToggle: () => void
}) {
  const nutrients = useFoodNutrients(detail.fdc_id, detail.library_scope)
  const core = nutrients.data?.nutrients.filter((item) => item.is_core) ?? []
  const others = nutrients.data?.nutrients.filter((item) => !item.is_core) ?? []
  const missingCount = nutrients.data?.missing_count ?? 0
  // 营养素粒度触发：存在缺失营养素（不止核心 7 项）即尝试外部补全；与摘要区共用同一查询缓存。
  const enrich = useEnrichedNutrients(detail.fdc_id, missingCount > 0)

  // 已核实外部值按 nutrient_id 索引；候选与被拒值不进入展示与计算。
  const externalByNutrientId = new Map<number, EnrichedValue>()
  for (const value of enrich.data?.values ?? []) {
    if (value.origin !== 'external' || value.status !== 'verified_external') continue
    if (value.value === null || value.nutrient_id == null) continue
    externalByNutrientId.set(value.nutrient_id, value)
  }
  const listedIds = new Set(nutrients.data?.nutrients.map((item) => item.nutrient_id) ?? [])
  const extraExternal = [...externalByNutrientId.values()].filter(
    (value) => !listedIds.has(value.nutrient_id as number),
  )
  const hasRows = (nutrients.data?.nutrients.length ?? 0) > 0 || extraExternal.length > 0
  const showExtra = showAll || (nutrients.data?.nutrients.length ?? 0) === 0

  return (
    <section className={styles.section}>
      <h3 className={styles.sectionTitle}>{zhCN.drawer.allNutrients}</h3>
      {nutrients.isPending ? <p className={styles.muted}>{zhCN.common.loading}</p> : null}
      {nutrients.isError ? (
        <ErrorState
          message={nutrients.error instanceof Error ? nutrients.error.message : zhCN.errors.generic}
          onRetry={() => void nutrients.refetch()}
        />
      ) : null}
      {nutrients.data ? (
        <>
          {!hasRows ? (
            <p className={styles.muted}>{zhCN.drawer.noNutrients}</p>
          ) : (
            <>
              <ul className={styles.nutrientList}>
                {core.map((item) => (
                  <NutrientRow
                    item={item}
                    key={item.nutrient_id}
                    external={externalByNutrientId.get(item.nutrient_id)}
                  />
                ))}
                {showAll
                  ? others.map((item) => (
                      <NutrientRow
                        item={item}
                        key={item.nutrient_id}
                        external={externalByNutrientId.get(item.nutrient_id)}
                      />
                    ))
                  : null}
                {showExtra
                  ? extraExternal.map((value) => (
                      <ExternalNutrientRow value={value} key={`external-${value.nutrient_id ?? value.key}`} />
                    ))
                  : null}
              </ul>
              <div className={styles.nutrientFooter}>
                <span className={styles.muted}>
                  {zhCN.drawer.nutrientCount(nutrients.data.total_nutrients_returned)}
                  {missingCount > 0 ? ` · ${zhCN.drawer.missingNote(missingCount)}` : null}
                  {extraExternal.length > 0 ? ` · ${zhCN.drawer.externalFilled(extraExternal.length)}` : null}
                </span>
                {others.length > 0 || extraExternal.length > 0 ? (
                  <button type="button" className={styles.textButton} onClick={onToggle}>
                    {showAll ? zhCN.drawer.collapseAll : zhCN.drawer.expandAll}
                  </button>
                ) : null}
              </div>
            </>
          )}
        </>
      ) : null}
    </section>
  )
}

function FooterSections({ detail }: { detail: FoodDetail }) {
  return (
    <>
      <section className={styles.section}>
        <h3 className={styles.sectionTitle}>{zhCN.drawer.portions}</h3>
        {detail.portions.length === 0 ? (
          <p className={styles.muted}>
            {zhCN.drawer.noPortions}
            {detail.library_scope === 'branded' ? ` ${zhCN.drawer.brandedServingNote}` : null}
          </p>
        ) : (
          <ul className={styles.portionList}>
            {detail.portions.map((portion, index) => (
              <li key={`${portion.modifier ?? 'portion'}-${index}`} className={styles.portionRow}>
                <span>
                  {portion.portion_description ?? portion.modifier ?? '—'}
                  {portion.amount !== null ? ` · ${formatAmount(portion.amount, 2)}` : null}
                </span>
                <span className={styles.portionGram}>
                  {portion.gram_weight !== null ? `${formatAmount(portion.gram_weight, 1)} g` : '—'}
                  {portion.quality_flag !== 'ok' ? (
                    <span className={styles.missingBadge}>{qualityLabel(portion.quality_flag)}</span>
                  ) : null}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className={styles.section}>
        <h3 className={styles.sectionTitle}>{zhCN.drawer.aliases}</h3>
        {detail.aliases.length === 0 ? (
          <p className={styles.muted}>{zhCN.drawer.noAliases}</p>
        ) : (
          <div className={styles.chips}>
            {detail.aliases.map((alias) => (
              <Badge
                tone={alias.status === 'verified' ? 'green' : 'neutral'}
                key={`${alias.alias_type}-${alias.alias}`}
                title={alias.review_status === 'pending' ? zhCN.zhStatus.pending : alias.status}
              >
                {alias.alias}
              </Badge>
            ))}
          </div>
        )}
      </section>

      <section className={styles.section}>
        <h3 className={styles.sectionTitle}>{zhCN.drawer.qualityEvents}</h3>
        {detail.quality_events.length === 0 ? (
          <p className={styles.muted}>{zhCN.drawer.noQualityEvents}</p>
        ) : (
          <ul className={styles.eventList}>
            {detail.quality_events.map((event, index) => (
              <li key={`${event.event_type}-${index}`}>
                <span className={styles.eventType}>{qualityLabel(event.event_type)}</span>
                <span className={styles.muted}>
                  {event.nutrient_id !== null ? `营养 ID ${event.nutrient_id}` : null}
                  {event.raw_amount !== null ? ` · 原始值 ${formatAmount(event.raw_amount, 4)}` : null}
                  {event.detail ? ` · ${event.detail}` : null}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className={styles.section}>
        <h3 className={styles.sectionTitle}>{zhCN.drawer.fdcRecord}</h3>
        <a
          className={styles.fdcLink}
          href={`https://fdc.nal.usda.gov/fdc-app.html#/food-details/${detail.fdc_id}/nutrients`}
          target="_blank"
          rel="noopener noreferrer"
        >
          {zhCN.drawer.openFdc}
          <ExternalLink size={15} aria-hidden="true" />
        </a>
      </section>
    </>
  )
}

function DrawerAddButton({ food }: { food: FoodDetail }) {
  const plate = usePlate()
  const added = plate.has(food)
  return (
    <button
      type="button"
      className={`${styles.addButton} ${added ? styles.addButtonAdded : ''}`}
      onClick={() => plate.add(food)}
      disabled={added}
    >
      {added ? <Check size={15} aria-hidden="true" /> : <Plus size={15} aria-hidden="true" />}
      {added ? zhCN.drawer.added : zhCN.drawer.addToPlate}
    </button>
  )
}

export function FoodDetailDrawer({ foodKey, scope, onClose }: FoodDetailDrawerProps) {
  const detail = useFoodDetail(foodKey, scope)
  const closeRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (foodKey === null) return
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    closeRef.current?.focus()

    const handleKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKey)

    return () => {
      document.removeEventListener('keydown', handleKey)
      document.body.style.overflow = previousOverflow
      previousFocus?.focus()
    }
  }, [foodKey, onClose])

  if (foodKey === null) return null

  const food = detail.data
  // 已核验与词典译名都以中文名作为标题，英文原名作为副标题。
  const title = food
    ? food.name_zh && food.zh_status !== 'none'
      ? food.name_zh
      : food.description_en
    : zhCN.drawer.title

  return createPortal(
    <div
      className={styles.overlay}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <aside
        className={styles.panel}
        role="dialog"
        aria-modal="true"
        aria-label={`${zhCN.drawer.title}：${title}`}
      >
        <header className={styles.header}>
          <div className={styles.heading}>
            {food ? (
              <span className={styles.headIcon}>
                <FoodIcon
                  food={food}
                  size={52}
                  label={zhCN.a11y.foodIcon(food.name_zh ?? food.description_en)}
                />
              </span>
            ) : null}
            <div>
              <h2 className={styles.title}>{title}</h2>
              {food && title !== food.description_en ? (
                <p className={styles.subtitle} lang="en">
                  {food.description_en}
                </p>
              ) : null}
              {food?.zh_status === 'glossary' ? (
                <p className={styles.subtitle} lang="zh-CN">
                  {zhCN.zhStatus.glossary}（{zhCN.zhStatus.pending}）
                </p>
              ) : null}
            </div>
          </div>
          <button
            type="button"
            className={styles.closeButton}
            onClick={onClose}
            aria-label={zhCN.drawer.closeAria}
            ref={closeRef}
          >
            <X size={20} aria-hidden="true" />
          </button>
        </header>

        {food ? (
          <div className={styles.drawerActions}>
            <DrawerAddButton food={food} />
          </div>
        ) : null}

        <div className={styles.body}>
          {detail.isPending ? <p className={styles.muted}>{zhCN.drawer.loadingDetail}</p> : null}
          {detail.isError ? (
            <ErrorState
              message={detail.error instanceof Error ? detail.error.message : zhCN.errors.generic}
              onRetry={() => void detail.refetch()}
            />
          ) : null}
          {food ? (
            <section className={styles.section}>
              <h3 className={styles.sectionTitle}>{zhCN.planner.addToPlanTitle}</h3>
              <AddToPlanForm
                foodKey={String(food.fdc_id)}
                scope={food.library_scope}
                name={
                  food.name_zh && food.zh_status !== 'none' ? food.name_zh : food.description_en
                }
              />
            </section>
          ) : null}
          {food ? <DetailBody food={food} key={food.fdc_id} /> : null}
          {food ? <FooterSections detail={food} /> : null}
        </div>
      </aside>
    </div>,
    document.body,
  )
}
