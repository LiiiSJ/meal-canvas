import { Database, ExternalLink, FileCheck2, Info, Palette, ShieldAlert } from 'lucide-react'

import { Badge } from '@/components/Badge'
import { ErrorState } from '@/components/StateViews'
import { zhCN } from '@/i18n/zh-CN'
import { formatInteger } from '@/lib/format'
import { useHealth } from '@/lib/queries'
import { PageHeader } from '@/components/PageHeader'

import styles from './AboutPage.module.css'

const DATASETS = [
  zhCN.about.datasetFoundation,
  zhCN.about.datasetSr,
  zhCN.about.datasetFndds,
  zhCN.about.datasetBranded,
]

const RULES = [
  { title: zhCN.about.ruleBaselineTitle, text: zhCN.about.ruleBaseline },
  { title: zhCN.about.ruleMissingTitle, text: zhCN.about.ruleMissing },
  { title: zhCN.about.ruleEnergyTitle, text: zhCN.about.ruleEnergy },
  { title: zhCN.about.ruleZhTitle, text: zhCN.about.ruleZh },
  { title: zhCN.about.ruleBrandTitle, text: zhCN.about.ruleBrand },
]

const LINKS = [
  { label: zhCN.about.linkFdc, href: 'https://fdc.nal.usda.gov/' },
  { label: zhCN.about.linkFoundation, href: 'https://fdc.nal.usda.gov/download-datasets.html' },
  { label: zhCN.about.linkBranded, href: 'https://fdc.nal.usda.gov/food-search?type=Branded' },
]

export function AboutPage() {
  const health = useHealth()

  const statusLabel = health.isPending
    ? zhCN.common.loadingShort
    : health.isError
      ? zhCN.about.liveError
      : health.data?.status === 'ok'
        ? zhCN.about.liveAvailable
        : zhCN.about.liveDegraded

  const foodCount = health.data?.food_count != null ? formatInteger(health.data.food_count) : '—'
  const nutrientRows =
    health.data?.nutrient_row_count != null ? formatInteger(health.data.nutrient_row_count) : '—'
  const brandedState = health.data?.branded_db_exists
    ? zhCN.about.liveAvailable
    : health.data
      ? zhCN.about.liveUnavailable
      : '—'

  return (
    <div className={styles.page}>
      <PageHeader title={zhCN.about.title} subtitle={zhCN.about.subtitle} />

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>{zhCN.about.liveTitle}</h2>
        <div className={styles.metrics}>
          <div className={styles.metric}>
            <span className={styles.metricLabel}>{zhCN.about.liveStatus}</span>
            <span className={styles.metricValue}>{statusLabel}</span>
          </div>
          <div className={styles.metric}>
            <span className={styles.metricLabel}>{zhCN.about.liveFood}</span>
            <span className={styles.metricValue}>{foodCount}</span>
          </div>
          <div className={styles.metric}>
            <span className={styles.metricLabel}>{zhCN.about.liveNutrientRows}</span>
            <span className={styles.metricValue}>{nutrientRows}</span>
          </div>
          <div className={styles.metric}>
            <span className={styles.metricLabel}>{zhCN.about.liveBranded}</span>
            <span className={styles.metricValue}>{brandedState}</span>
          </div>
        </div>

        {health.isError ? (
          <ErrorState
            message={health.error instanceof Error ? health.error.message : zhCN.errors.generic}
            onRetry={() => void health.refetch()}
          />
        ) : null}

        <p className={styles.note}>
          <Info size={15} strokeWidth={1.8} aria-hidden="true" />
          {zhCN.about.liveNote}
        </p>
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>{zhCN.about.datasetsTitle}</h2>
        <p className={styles.sectionDesc}>{zhCN.about.datasetsDesc}</p>
        <div className={styles.datasetGrid}>
          {DATASETS.map((dataset) => (
            <article className={styles.datasetCard} key={dataset.name}>
              <div className={styles.datasetHead}>
                <h3 className={styles.datasetName} lang="en">
                  {dataset.name}
                </h3>
                <span className={styles.datasetCount}>{dataset.count}</span>
              </div>
              <p className={styles.datasetMeta}>{dataset.version}</p>
              <p className={styles.datasetRole}>{dataset.role}</p>
              <p className={styles.datasetNote}>{dataset.note}</p>
            </article>
          ))}
        </div>
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>{zhCN.about.rulesTitle}</h2>
        <div className={styles.ruleGrid}>
          {RULES.map((rule) => (
            <article className={styles.rule} key={rule.title}>
              <h3 className={styles.ruleTitle}>{rule.title}</h3>
              <p className={styles.ruleText}>{rule.text}</p>
            </article>
          ))}
        </div>
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>{zhCN.about.assetsTitle}</h2>
        <div className={styles.ruleGrid}>
          <article className={styles.rule}>
            <h3 className={styles.ruleTitle}>
              <Palette size={16} strokeWidth={1.8} aria-hidden="true" /> {zhCN.about.assetIconsTitle}
            </h3>
            <p className={styles.ruleText}>{zhCN.about.assetIcons}</p>
          </article>
          <article className={styles.rule}>
            <h3 className={styles.ruleTitle}>
              <Badge tone="neutral">Lucide</Badge> {zhCN.about.assetLucideTitle}
            </h3>
            <p className={styles.ruleText}>{zhCN.about.assetLucide}</p>
          </article>
          <article className={styles.rule}>
            <h3 className={styles.ruleTitle}>
              <Database size={16} strokeWidth={1.8} aria-hidden="true" /> {zhCN.about.assetDataTitle}
            </h3>
            <p className={styles.ruleText}>{zhCN.about.assetData}</p>
          </article>
        </div>
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>{zhCN.about.linksTitle}</h2>
        <ul className={styles.linkList}>
          {LINKS.map((link) => (
            <li key={link.href}>
              <a
                className={styles.inlineLink}
                href={link.href}
                target="_blank"
                rel="noopener noreferrer"
              >
                <ExternalLink size={15} strokeWidth={1.8} aria-hidden="true" />
                {link.label}
                <span className={styles.newWindow}>({zhCN.about.newWindow})</span>
              </a>
            </li>
          ))}
        </ul>
      </section>

      <section className={`${styles.card} ${styles.disclaimer}`}>
        <h2 className={styles.cardTitle}>
          <ShieldAlert size={18} strokeWidth={1.8} aria-hidden="true" />
          {zhCN.about.disclaimerTitle}
        </h2>
        <p className={styles.cardText}>{zhCN.about.disclaimer}</p>
        <p className={`${styles.cardText} ${styles.mutedText}`}>
          <FileCheck2 size={13} strokeWidth={1.8} aria-hidden="true" /> {zhCN.about.footerNote}
        </p>
      </section>
    </div>
  )
}
