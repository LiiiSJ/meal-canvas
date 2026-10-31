import { ChartShell } from '@/components/ChartShell'
import { zhCN } from '@/i18n/zh-CN'
import type { ContributionItem } from '@/lib/contribution'
import { chartToken } from '@/lib/echarts'
import { formatAmount } from '@/lib/format'
import type { CoreNutrientSpec } from '@/lib/calculator'

interface ContributionChartProps {
  items: ContributionItem[]
  knownTotal: number
  spec: CoreNutrientSpec
  selectedKey: string | null
  keyOf: (item: ContributionItem) => string
  onSelect: (key: string) => void
}

function escapeHtml(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

/** 营养来源贡献条形图：横条越长贡献越大，点击与餐盘食材联动。 */
export default function ContributionChart({
  items,
  knownTotal,
  spec,
  selectedKey,
  keyOf,
  onSelect,
}: ContributionChartProps) {
  const inkColor = chartToken('--ink-600', '#6e665c')
  const axisColor = chartToken('--ink-400', '#9a9186')
  const lineColor = chartToken('--line', '#eadfd2')
  const cardColor = chartToken('--bg-card', '#ffffff')
  const green = chartToken('--green-500', '#7fae83')
  const orange = chartToken('--orange-500', '#f2a65a')

  // 横条图第一项在最上面。
  const ordered = [...items].reverse()

  const option = {
    grid: { left: 8, right: 44, top: 10, bottom: 26, containLabel: true },
    tooltip: {
      trigger: 'item',
      backgroundColor: cardColor,
      borderColor: lineColor,
      textStyle: { color: inkColor, fontSize: 12 },
      formatter: (params: unknown) => {
        const payload = params as { data?: { name?: string; value?: number; share?: number } }
        const data = payload.data
        if (!data || data.value === undefined) return ''
        const lines = [
          `<strong>${escapeHtml(data.name ?? '')}</strong>`,
          `${spec.label}：${formatAmount(data.value, spec.decimals)} ${spec.unit}`,
        ]
        if (knownTotal > 0 && data.share !== undefined) {
          lines.push(zhCN.analysis.shareOfKnown(formatAmount(data.share * 100, 1)))
        }
        return lines.join('<br/>')
      },
    },
    xAxis: {
      type: 'value',
      min: 0,
      name: spec.unit,
      nameLocation: 'end',
      nameTextStyle: { color: axisColor, fontSize: 11 },
      axisLine: { lineStyle: { color: lineColor } },
      axisTick: { show: false },
      axisLabel: { color: axisColor, fontSize: 11 },
      splitLine: { lineStyle: { color: lineColor, type: 'dashed' } },
    },
    yAxis: {
      type: 'category',
      data: ordered.map((item) => item.entry.food.display_name || item.entry.food.description_en),
      axisLine: { lineStyle: { color: lineColor } },
      axisTick: { show: false },
      axisLabel: {
        color: inkColor,
        fontSize: 12,
        width: 110,
        overflow: 'truncate',
      },
    },
    series: [
      {
        type: 'bar',
        barMaxWidth: 22,
        itemStyle: {
          borderRadius: [0, 11, 11, 0],
        },
        data: ordered.map((item) => {
          const key = keyOf(item)
          const selected = key === selectedKey
          return {
            name: item.entry.food.display_name || item.entry.food.description_en,
            value: Math.round(item.value * 1000) / 1000,
            share: knownTotal > 0 ? item.value / knownTotal : undefined,
            itemStyle: {
              color: selected ? orange : green,
              opacity: selectedKey === null || selected ? 1 : 0.45,
            },
          }
        }),
      },
    ],
  }

  return (
    <ChartShell
      option={option}
      ariaLabel={zhCN.a11y.contributionChartLabel}
      height={Math.max(220, ordered.length * 46 + 60)}
      onItemClick={(params) => {
        const index = (params as { dataIndex?: number }).dataIndex
        if (index === undefined || index < 0) return
        const item = ordered[index]
        if (item) onSelect(keyOf(item))
      }}
    />
  )
}
