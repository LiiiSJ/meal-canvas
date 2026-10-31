import { useEffect, useRef } from 'react'

import { chartToken, echarts, type ChartOption } from '@/lib/echarts'

import styles from './ChartShell.module.css'

interface ChartShellProps {
  option: ChartOption
  ariaLabel: string
  height?: number
  loading?: boolean
  loadingLabel?: string
  /** 图表点击事件，例如点击贡献条形或散点。 */
  onItemClick?: (params: unknown) => void
}

/**
 * 所有 ECharts 图表统一经过这里初始化，避免页面各自处理 resize 与销毁。
 */
export function ChartShell({ option, ariaLabel, height = 340, loading = false, loadingLabel, onItemClick }: ChartShellProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<ReturnType<typeof echarts.init> | null>(null)

  useEffect(() => {
    const node = containerRef.current
    if (!node) return
    const chart = echarts.init(node, undefined, { renderer: 'canvas' })
    chartRef.current = chart
    const observer = new ResizeObserver(() => chart.resize())
    observer.observe(node)
    return () => {
      observer.disconnect()
      chart.dispose()
      chartRef.current = null
    }
  }, [])

  useEffect(() => {
    const chart = chartRef.current
    if (!chart) return
    chart.setOption(
      {
        textStyle: {
          fontFamily: chartToken('--font-sans', 'sans-serif'),
          color: chartToken('--ink-600', '#6e665c'),
        },
        ...option,
      },
      true,
    )
  }, [option])

  useEffect(() => {
    const chart = chartRef.current
    if (!chart || !onItemClick) return
    chart.off('click')
    chart.on('click', onItemClick)
    return () => {
      chart.off('click')
    }
  }, [onItemClick])

  return (
    <div className={styles.shell}>
      <div ref={containerRef} className={styles.chart} style={{ height }} role="img" aria-label={ariaLabel} />
      {loading ? (
        <div className={styles.loading} role="status">
          {loadingLabel}
        </div>
      ) : null}
    </div>
  )
}
