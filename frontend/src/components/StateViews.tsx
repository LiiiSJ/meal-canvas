import { AlertCircle, RefreshCw, UtensilsCrossed } from 'lucide-react'
import type { ReactNode } from 'react'

import { zhCN } from '@/i18n/zh-CN'

import styles from './StateViews.module.css'

export function LoadingCards({ count = 6 }: { count?: number }) {
  return (
    <div className={styles.skeletonGrid} aria-busy="true" aria-label={zhCN.a11y.loadingFoods}>
      {Array.from({ length: count }).map((_, index) => (
        <div className={styles.skeletonCard} key={index}>
          <div className={styles.skeletonIcon} />
          <div className={styles.skeletonLines}>
            <div className={styles.skeletonLine} />
            <div className={styles.skeletonLineShort} />
          </div>
        </div>
      ))}
    </div>
  )
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string
  description: string
  action?: ReactNode
}) {
  return (
    <div className={styles.state}>
      <div className={styles.stateIcon} aria-hidden="true">
        <UtensilsCrossed size={30} strokeWidth={1.7} />
      </div>
      <h3 className={styles.stateTitle}>{title}</h3>
      <p className={styles.stateDesc}>{description}</p>
      {action ? <div className={styles.stateAction}>{action}</div> : null}
    </div>
  )
}

export function ErrorState({
  message,
  onRetry,
  hint,
}: {
  message: string
  onRetry?: () => void
  hint?: string
}) {
  return (
    <div className={`${styles.state} ${styles.errorState}`} role="alert">
      <AlertCircle size={32} strokeWidth={1.8} aria-hidden="true" />
      <h3 className={styles.stateTitle}>{zhCN.states.errorTitle}</h3>
      <p className={styles.stateDesc}>{message}</p>
      {hint ? <p className={styles.stateHint}>{hint}</p> : null}
      {onRetry ? (
        <button type="button" className={styles.retryButton} onClick={onRetry}>
          <RefreshCw size={16} aria-hidden="true" />
          {zhCN.common.retry}
        </button>
      ) : null}
    </div>
  )
}
