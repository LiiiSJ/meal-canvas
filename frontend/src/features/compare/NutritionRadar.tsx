import { ChartShell } from '@/components/ChartShell'
import { zhCN } from '@/i18n/zh-CN'
import { chartToken } from '@/lib/echarts'
import { formatAmount } from '@/lib/format'

import type { MetricCompareRow } from './MetricCompareChart'

interface NutritionRadarProps {
  /** 只传入 A/B 双方都有数据的指标，缺失轴由外层剔除并说明。 */
  rows: MetricCompareRow[]
}

function escapeHtml(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function sideTag(row: MetricCompareRow, side: 'a' | 'b'): string {
  const known = side === 'a' ? row.aKnown : row.bKnown
  const total = side === 'a' ? row.aTotal : row.bTotal
  if (total <= 0 || known >= total) return ''
  return `（${zhCN.compare.coverageTag(side === 'a' ? 'A' : 'B', known, total)}）`
}

/**
 * 方案营养结构雷达图：每根轴按该指标双方较大值独立缩放。
 * 只用于比较形状与相对高低，绝对数值在右侧明细中给出。
 */
export default function NutritionRadar({ rows }: NutritionRadarProps) {
  const inkColor = chartToken('--ink-600', '#6e665c')
  const lineColor = chartToken('--line', '#eadfd2')
  const cardColor = chartToken('--bg-card', '#ffffff')
  const softColor = chartToken('--bg-soft-2', '#fbf3e7')
  const skyColor = chartToken('--sky-300', '#a9cfdd')
  const orangeColor = chartToken('--orange-500', '#f2a65a')

  // 每个轴独立缩放：轴上限 = 双方较大值 × 1.25，因此较大的点不会贴到最外圈。
  const indicators = rows.map((row) => {
    const top = Math.max(row.a as number, row.b as number)
    return { name: row.label, max: top > 0 ? top * 1.25 : 1 }
  })

  const detailOf = (side: 'a' | 'b'): string[] =>
    rows.map((row) => {
      const value = side === 'a' ? row.a : row.b
      return `${row.label}：${formatAmount(value, row.decimals)} ${row.unit}${sideTag(row, side)}`
    })

  const seriesOf = (side: 'a' | 'b') => ({
    name: side === 'a' ? zhCN.compare.slotA : zhCN.compare.slotB,
    value: rows.map((row) => (side === 'a' ? row.a : row.b) as number),
    detail: detailOf(side),
    symbol: 'circle',
    symbolSize: 5,
    lineStyle: {
      width: 2,
      color: side === 'a' ? skyColor : orangeColor,
    },
    itemStyle: { color: side === 'a' ? skyColor : orangeColor },
    areaStyle: { color: side === 'a' ? skyColor : orangeColor, opacity: side === 'a' ? 0.24 : 0.16 },
  })

  const option = {
    tooltip: {
      trigger: 'item',
      backgroundColor: cardColor,
      borderColor: lineColor,
      textStyle: { color: inkColor, fontSize: 12 },
      formatter: (params: unknown) => {
        const data = (params as { data?: { name?: string; detail?: string[] } }).data
        if (!data || !data.detail) return ''
        return [
          `<strong>${escapeHtml(data.name ?? '')}</strong>`,
          ...data.detail.map((text) => escapeHtml(text)),
        ].join('<br/>')
      },
    },
    radar: {
      center: ['50%', '54%'],
      radius: '66%',
      splitNumber: 4,
      axisName: { color: inkColor, fontSize: 12 },
      axisLine: { lineStyle: { color: lineColor } },
      splitLine: { lineStyle: { color: lineColor, type: 'dashed' } },
      splitArea: { areaStyle: { color: [cardColor, softColor] } },
      indicator: indicators,
    },
    series: [
      {
        type: 'radar',
        data: [seriesOf('a'), seriesOf('b')],
      },
    ],
  }

  return (
    <ChartShell option={option} ariaLabel={zhCN.a11y.compareRadarLabel} height={320} />
  )
}
