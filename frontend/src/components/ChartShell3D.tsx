import { useEffect, useRef } from 'react'

import { chartToken } from '@/lib/echarts'
import { echarts, isWebGLAvailable, type Chart3DOption } from '@/lib/echarts3d'

import styles from './ChartShell.module.css'

interface ChartShell3DProps {
  option: Chart3DOption
  ariaLabel: string
  height?: number
  loading?: boolean
  loadingLabel?: string
  onItemClick?: (params: unknown) => void
  /** WebGL 不可用时的中文提示。 */
  webglFallbackLabel?: string
}

/**
 * 三维散点图专用 ECharts 封装。
 * - renderer 用 'canvas'，echarts-gl 内部会自动检测 grid3D 并启用 WebGL
 * - 保留与 ChartShell 相同的 ResizeObserver 自动 resize 和 dispose 生命周期
 * - 在组件挂载时检测 WebGL 支持，不支持时显示提示而非初始化空图表
 * - option 变化时调用 setOption(option, true) 替换（避免轴/系列残留）
 */
export function ChartShell3D({
  option,
  ariaLabel,
  height = 520,
  loading = false,
  loadingLabel,
  onItemClick,
  webglFallbackLabel = '当前浏览器不支持 WebGL，无法显示三维视图。请使用最新版 Chrome、Edge 或 Firefox 查看。',
}: ChartShell3DProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<ReturnType<typeof echarts.init> | null>(null)
  const webglOk = useRef<boolean | null>(null)

  useEffect(() => {
    const node = containerRef.current
    if (!node) return

    const supported = isWebGLAvailable()
    webglOk.current = supported
    if (!supported) return

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

  const notSupported = webglOk.current === false

  return (
    <div className={styles.shell}>
      {notSupported ? (
        <div
          className={styles.chart}
          style={{ height }}
          role="alert"
          aria-label={ariaLabel}
        >
          <p style={{ color: chartToken('--ink-600', '#6e665c'), margin: 'auto', textAlign: 'center', padding: 24 }}>
            {webglFallbackLabel}
          </p>
        </div>
      ) : (
        <div ref={containerRef} className={styles.chart} style={{ height }} role="img" aria-label={ariaLabel} />
      )}
      {loading && !notSupported ? (
        <div className={styles.loading} role="status">
          {loadingLabel}
        </div>
      ) : null}
    </div>
  )
}
