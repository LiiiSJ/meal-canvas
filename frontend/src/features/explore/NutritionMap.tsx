import { ChartShell } from '@/components/ChartShell'
import { resolveCategoryGroup, type CategoryGroup } from '@/assets/food-icons/mapping'
import { zhCN } from '@/i18n/zh-CN'
import type { CoreNutrientSpec } from '@/lib/calculator'
import { chartToken } from '@/lib/echarts'
import { formatAmount } from '@/lib/format'
import type { FoodItem } from '@/lib/types'

export interface MapPoint {
  food: FoodItem
  x: number
  y: number
}

interface NutritionMapProps {
  points: MapPoint[]
  xSpec: CoreNutrientSpec
  ySpec: CoreNutrientSpec
  selectedId: number | null
  loading?: boolean
  onSelect: (food: FoodItem) => void
}

const GROUP_ORDER: readonly CategoryGroup[] = [
  'grain',
  'protein',
  'dairy',
  'vegetable',
  'fruit',
  'fat',
  'beverage',
  'snack',
  'other',
]

const GROUP_LABEL: Record<CategoryGroup, string> = {
  grain: zhCN.explore.groupGrain,
  protein: zhCN.explore.groupProtein,
  dairy: zhCN.explore.groupDairy,
  vegetable: zhCN.explore.groupVegetable,
  fruit: zhCN.explore.groupFruit,
  fat: zhCN.explore.groupFat,
  beverage: zhCN.explore.groupBeverage,
  snack: zhCN.explore.groupSnack,
  other: zhCN.explore.groupOther,
}

const GROUP_TOKEN: Record<CategoryGroup, [string, string]> = {
  grain: ['--yellow-500', '#e9c46a'],
  protein: ['--berry-500', '#d97b66'],
  dairy: ['--sky-300', '#a9cfdd'],
  vegetable: ['--green-500', '#7fae83'],
  fruit: ['--orange-500', '#f2a65a'],
  fat: ['--yellow-300', '#f6dfa4'],
  beverage: ['--sky-300', '#a9cfdd'],
  snack: ['--orange-300', '#f8c99b'],
  other: ['--ink-400', '#9a9186'],
}

function escapeHtml(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function pointName(point: MapPoint): string {
  const primary = point.food.display_name || point.food.description_en
  return primary === point.food.description_en ? primary : `${primary}（${point.food.description_en}）`
}

/** 食材营养探索散点图：坐标轴含单位，关键点标注，点击选中食品。 */
export default function NutritionMap({ points, xSpec, ySpec, selectedId, loading = false, onSelect }: NutritionMapProps) {
  const grouped = new Map<CategoryGroup, MapPoint[]>()
  for (const point of points) {
    const group = resolveCategoryGroup(point.food)
    const bucket = grouped.get(group) ?? []
    bucket.push(point)
    grouped.set(group, bucket)
  }

  const maxX = points.reduce<MapPoint | null>((best, p) => (best === null || p.x > best.x ? p : best), null)
  const maxY = points.reduce<MapPoint | null>((best, p) => (best === null || p.y > best.y ? p : best), null)

  const axisColor = chartToken('--ink-400', '#9a9186')
  const lineColor = chartToken('--line', '#eadfd2')
  const inkColor = chartToken('--ink-600', '#6e665c')
  const cardColor = chartToken('--bg-card', '#ffffff')
  const markColor = chartToken('--orange-500', '#f2a65a')

  const series = GROUP_ORDER.filter((group) => (grouped.get(group)?.length ?? 0) > 0).map((group) => {
    const [token, fallback] = GROUP_TOKEN[group]
    const groupColor = chartToken(token, fallback)
    const groupPoints = grouped.get(group) ?? []
    const seriesData = groupPoints.map((point) => ({
      name: pointName(point),
      value: [point.x, point.y],
      fdcId: point.food.fdc_id,
      symbolSize: point.food.fdc_id === selectedId ? 16 : 11,
      itemStyle: {
        color: groupColor,
        opacity: selectedId === null || point.food.fdc_id === selectedId ? 0.9 : 0.35,
        borderColor: point.food.fdc_id === selectedId ? markColor : 'transparent',
        borderWidth: point.food.fdc_id === selectedId ? 2 : 0,
      },
    }))

    // 关键点标注挂在包含该点的系列上。
    const markData: { name: string; coord: [number, number] }[] = []
    if (maxX && groupPoints.some((p) => p.food.fdc_id === maxX.food.fdc_id)) {
      markData.push({ name: zhCN.explore.maxPoint(xSpec.label), coord: [maxX.x, maxX.y] })
    }
    if (maxY && maxY.food.fdc_id !== maxX?.food.fdc_id && groupPoints.some((p) => p.food.fdc_id === maxY.food.fdc_id)) {
      markData.push({ name: zhCN.explore.maxPoint(ySpec.label), coord: [maxY.x, maxY.y] })
    }

    return {
      name: GROUP_LABEL[group],
      type: 'scatter',
      emphasis: { scale: 1.4, focus: 'series' },
      // 系列级颜色供图例取用，保证图例与散点同色。
      itemStyle: { color: groupColor },
      data: seriesData,
      markPoint:
        markData.length > 0
          ? {
              symbol: 'pin',
              symbolSize: 40,
              itemStyle: { color: markColor },
              label: { fontSize: 10, color: '#fff' },
              data: markData,
            }
          : undefined,
    }
  })

  const option = {
    color: GROUP_ORDER.map((group) => chartToken(GROUP_TOKEN[group][0], GROUP_TOKEN[group][1])),
    grid: { left: 58, right: 26, top: 42, bottom: 78, containLabel: false },
    tooltip: {
      trigger: 'item',
      backgroundColor: cardColor,
      borderColor: lineColor,
      textStyle: { color: inkColor, fontSize: 12 },
      formatter: (params: unknown) => {
        const payload = params as { data?: { name?: string; value?: [number, number]; fdcId?: number } }
        const data = payload.data
        if (!data || !data.value) return ''
        const [x, y] = data.value
        return [
          `<strong>${escapeHtml(data.name ?? '')}</strong>`,
          `${xSpec.label}：${formatAmount(x, xSpec.decimals)} ${xSpec.unit} / 100g`,
          `${ySpec.label}：${formatAmount(y, ySpec.decimals)} ${ySpec.unit} / 100g`,
        ].join('<br/>')
      },
    },
    legend: {
      type: 'scroll',
      bottom: 6,
      itemWidth: 10,
      itemHeight: 10,
      icon: 'circle',
      textStyle: { color: inkColor, fontSize: 12 },
      pageIconColor: inkColor,
    },
    xAxis: {
      type: 'value',
      min: 0,
      name: zhCN.explore.axis(xSpec.label, xSpec.unit),
      nameLocation: 'middle',
      nameGap: 30,
      nameTextStyle: { color: axisColor, fontSize: 12 },
      axisLine: { lineStyle: { color: lineColor } },
      axisTick: { show: false },
      axisLabel: { color: axisColor, fontSize: 11 },
      splitLine: { lineStyle: { color: lineColor, type: 'dashed' } },
    },
    yAxis: {
      type: 'value',
      min: 0,
      name: zhCN.explore.axis(ySpec.label, ySpec.unit),
      nameLocation: 'middle',
      nameGap: 42,
      nameTextStyle: { color: axisColor, fontSize: 12 },
      axisLine: { lineStyle: { color: lineColor } },
      axisTick: { show: false },
      axisLabel: { color: axisColor, fontSize: 11 },
      splitLine: { lineStyle: { color: lineColor, type: 'dashed' } },
    },
    series,
  }

  return (
    <ChartShell
      option={option}
      ariaLabel={zhCN.a11y.chartLabel}
      height={420}
      loading={loading}
      loadingLabel={zhCN.explore.loadingChart}
      onItemClick={(params) => {
        const payload = params as { data?: { fdcId?: number } }
        const fdcId = payload.data?.fdcId
        if (fdcId === undefined) return
        const point = points.find((candidate) => candidate.food.fdc_id === fdcId)
        if (point) onSelect(point.food)
      }}
    />
  )
}
