import { Check, Plus } from 'lucide-react'
import { useState } from 'react'

import { usePlate } from '@/app/plate/usePlate'
import { Badge, type BadgeTone } from '@/components/Badge'
import { FoodIcon } from '@/components/FoodIcon'
import { zhCN } from '@/i18n/zh-CN'
import type { FoodItem } from '@/lib/types'

import styles from './FoodLibraryCard.module.css'

interface FoodLibraryCardProps {
  food: FoodItem
  onOpen: (food: FoodItem) => void
  /** 自定义「加入」动作（例如加入某餐次）；不传时加入餐盘。 */
  onAddFood?: (food: FoodItem) => void
  addLabel?: string
  /** 自定义动作下的已加入状态。 */
  isAdded?: boolean
}

function usageTone(usageClass: string): BadgeTone {
  switch (usageClass) {
    case 'processed_ingredient':
      return 'sky'
    case 'prepared_dish':
      return 'berry'
    case 'ready_to_eat':
      return 'neutral'
    default:
      return 'outline'
  }
}

/**
 * 食材库卡片：第一眼是插画与中文名，类别一行小字，右下一个添加操作。
 * FDC ID、数据集版本等技术字段不在这里出现，保留在详情抽屉。
 */
export function FoodLibraryCard({ food, onOpen, onAddFood, addLabel, isAdded }: FoodLibraryCardProps) {
  const plate = usePlate()
  const [hint, setHint] = useState<string | null>(null)

  // 已核验 / 词典译名均以中文名为主名；完全无中文名（none）才显示英文原名。
  // display_name 后端只在 verified 时给中文名，glossary 的中文名需要从 name_zh 取。
  const hasVerifiedZh = food.zh_status === 'verified' && food.name_zh
  const hasGlossaryZh = food.zh_status === 'glossary' && food.name_zh
  const primary = hasVerifiedZh || hasGlossaryZh ? food.name_zh! : food.description_en
  const showEnglish = primary !== food.description_en
  const category = food.category_zh ?? food.category_en ?? zhCN.library.categoryUnknown
  const added = isAdded ?? plate.has(food)
  // 基础食材是默认列表的常态，不额外占位；只有加工、成品、即食与未知才显示用途徽标。
  const usageClass = food.usage_class ?? null
  const showUsageBadge = usageClass !== null && usageClass !== 'basic_ingredient'
  const usageLabel = usageClass ? (zhCN.usageClass[usageClass]?.short ?? usageClass) : ''

  const handleAdd = () => {
    if (onAddFood) {
      onAddFood(food)
      setHint(null)
      return
    }
    const result = plate.add(food)
    if (result === 'duplicate') setHint(zhCN.library.duplicateHint)
    else if (result === 'full') setHint(zhCN.library.fullHint)
    else setHint(null)
  }

  return (
    <article className={styles.card}>
      <button
        type="button"
        className={styles.main}
        onClick={() => onOpen(food)}
        aria-label={zhCN.a11y.foodCard(primary)}
      >
        <span className={styles.iconBox}>
          <FoodIcon food={food} size={44} label={zhCN.a11y.foodIcon(primary)} />
        </span>
        <span className={styles.names}>
          <span className={styles.primary} lang={primary === food.name_zh ? 'zh-CN' : 'en'}>
            {primary}
          </span>
          {showEnglish ? (
            <span className={styles.secondary} lang="en">
              {food.description_en}
            </span>
          ) : null}
          <span className={styles.category}>{category}</span>
        </span>
      </button>

      <div className={styles.footer}>
        <span className={styles.badges}>
          {showUsageBadge && usageClass ? (
            <Badge tone={usageTone(usageClass)} title={food.usage_reason ?? undefined}>
              {usageLabel}
            </Badge>
          ) : null}
          {food.zh_status === 'glossary' ? (
            <Badge tone="orange">{zhCN.zhStatus.glossary}</Badge>
          ) : null}
          {food.zh_status === 'none' ? <Badge tone="neutral">{zhCN.zhStatus.none}</Badge> : null}
          {hint ? <span className={styles.hint}>{hint}</span> : null}
        </span>
        <button
          type="button"
          className={`${styles.addButton} ${added ? styles.addedButton : ''}`}
          onClick={handleAdd}
          aria-label={
            onAddFood
              ? zhCN.a11y.addToPlate(primary)
              : added
                ? zhCN.library.addedHint
                : zhCN.a11y.addToPlate(primary)
          }
        >
          {added && !onAddFood ? (
            <Check size={15} aria-hidden="true" />
          ) : (
            <Plus size={15} aria-hidden="true" />
          )}
          {addLabel ?? (added && !onAddFood ? zhCN.common.added : zhCN.common.addToPlate)}
        </button>
      </div>
    </article>
  )
}
