import { BarChart, RadarChart, ScatterChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  MarkPointComponent,
  RadarComponent,
  TooltipComponent,
} from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'

/**
 * 只注册本项目实际使用的图表模块，ECharts 不会进入首屏主包：
 * 探索页、分析页与方案对比页都通过 React.lazy 动态加载图表组件。
 */
echarts.use([
  BarChart,
  RadarChart,
  ScatterChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  MarkPointComponent,
  RadarComponent,
  CanvasRenderer,
])

export { echarts }

export type ChartOption = Record<string, unknown>

/** 从 CSS 设计令牌读取颜色，避免在图表里另写一套硬编码色值。 */
export function chartToken(name: string, fallback: string): string {
  if (typeof window === 'undefined') return fallback
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return value || fallback
}
