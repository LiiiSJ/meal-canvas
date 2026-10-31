import {
  BarChart3,
  CalendarDays,
  ChartScatter,
  ClipboardList,
  Columns2,
  CookingPot,
  Database,
  UtensilsCrossed,
} from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'

import { usePlate } from '@/app/plate/usePlate'
import { zhCN } from '@/i18n/zh-CN'
import { useHealth } from '@/lib/queries'

import styles from './AppShell.module.css'

function HealthChip() {
  const health = useHealth()

  let tone = 'pending'
  let label: string = zhCN.shell.statusChecking
  if (health.isError) {
    tone = 'offline'
    label = zhCN.shell.statusOffline
  } else if (health.data) {
    if (health.data.status === 'ok') {
      tone = 'ok'
      label = zhCN.shell.statusOk
    } else {
      tone = 'degraded'
      label = zhCN.shell.statusDegraded
    }
  }

  const isSampleDb = health.data?.default_db_path?.toLowerCase().includes('sample') ?? false

  return (
    <div className={styles.health} title={isSampleDb ? zhCN.shell.sampleDbHint : undefined}>
      <span className={`${styles.healthDot} ${styles[`dot_${tone}`]}`} aria-hidden="true" />
      <span className={styles.healthText}>{label}</span>
      {isSampleDb ? <span className={styles.healthTag}>{zhCN.shell.sampleDb}</span> : null}
    </div>
  )
}

export function AppShell() {
  const plate = usePlate()

  const mainNav = [
    { to: '/', label: zhCN.nav.designer, icon: CookingPot, end: true, badge: plate.entries.length },
    { to: '/weekly', label: zhCN.nav.weekly, icon: CalendarDays, end: false, badge: 0 },
    { to: '/today', label: zhCN.nav.today, icon: ClipboardList, end: false, badge: 0 },
    { to: '/analysis', label: zhCN.nav.analysis, icon: BarChart3, end: false, badge: 0 },
    { to: '/explore', label: zhCN.nav.explore, icon: ChartScatter, end: false, badge: 0 },
    { to: '/compare', label: zhCN.nav.compare, icon: Columns2, end: false, badge: 0 },
  ]

  const renderLink = (item: (typeof mainNav)[number], classActive: string, classItem: string) => {
    const Icon = item.icon
    return (
      <NavLink
        key={item.to}
        to={item.to}
        end={item.end}
        className={({ isActive }) => `${classItem} ${isActive ? classActive : ''}`}
      >
        <Icon size={19} strokeWidth={1.8} aria-hidden="true" />
        <span className={styles.navLabel}>{item.label}</span>
        {item.badge > 0 ? <span className={styles.navBadge}>{item.badge}</span> : null}
      </NavLink>
    )
  }

  return (
    <div className={styles.app}>
      <a className={styles.skipLink} href="#main-content">
        {zhCN.a11y.skipToContent}
      </a>

      <aside className={styles.sidebar}>
        <div className={styles.brand}>
          <span className={styles.brandMark} aria-hidden="true">
            <UtensilsCrossed size={22} strokeWidth={1.8} />
          </span>
          <span className={styles.brandText}>
            <strong>{zhCN.appName}</strong>
            <small lang="en">{zhCN.appNameEn}</small>
          </span>
        </div>
        <p className={styles.tagline}>{zhCN.tagline}</p>

        <nav className={styles.nav} aria-label={zhCN.a11y.mainNav}>
          {mainNav.map((item) => renderLink(item, styles.navActive, styles.navItem))}
        </nav>

        <div className={styles.sidebarFooter}>
          <nav aria-label={zhCN.nav.secondary}>
            <NavLink
              to="/about"
              className={({ isActive }) =>
                `${styles.secondaryItem} ${isActive ? styles.secondaryActive : ''}`
              }
            >
              <Database size={16} strokeWidth={1.8} aria-hidden="true" />
              <span>{zhCN.nav.about}</span>
            </NavLink>
          </nav>
          <HealthChip />
        </div>
      </aside>

      <header className={styles.mobileHeader}>
        <span className={styles.brandMark} aria-hidden="true">
          <UtensilsCrossed size={18} strokeWidth={1.8} />
        </span>
        <strong>{zhCN.appName}</strong>
        <HealthChip />
      </header>

      <main className={styles.main} id="main-content">
        <Outlet />
      </main>

      <nav className={styles.mobileNav} aria-label={zhCN.a11y.mainNav}>
        {mainNav.map((item) => renderLink(item, styles.mobileNavActive, styles.mobileNavItem))}
      </nav>
    </div>
  )
}
