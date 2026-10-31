import type { ReactNode } from 'react'

import styles from './PageHeader.module.css'

interface PageHeaderProps {
  title: string
  subtitle: string
  aside?: ReactNode
}

export function PageHeader({ title, subtitle, aside }: PageHeaderProps) {
  return (
    <header className={styles.header}>
      <div>
        <h1 className={styles.title}>{title}</h1>
        <p className={styles.subtitle}>{subtitle}</p>
      </div>
      {aside ? <div className={styles.aside}>{aside}</div> : null}
    </header>
  )
}
