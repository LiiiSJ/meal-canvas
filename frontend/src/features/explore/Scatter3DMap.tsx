import { ChartShell3D } from '@/components/ChartShell3D'
import { resolveCategoryGroup, type CategoryGroup } from '@/assets/food-icons/mapping'
import { zhCN } from '@/i18n/zh-CN'
import { chartToken } from '@/lib/echarts'
import { formatAmount } from '@/lib/format'
import type { FoodItem } from '@/lib/types'

/** 坐标轴规格：label/unit/decimals，与 CoreNutrientSpec 结构相同但 key 更自由。 */
export interface AxisSpec3D {
  key: string
  label: string
  unit: string
  decimals: number
}

export interface MapPoint3D {
  food: FoodItem
  x: number
  y: number
  z: number
}

interface Scatter3DMapProps {
  points: MapPoint3D[]
  xSpec: AxisSpec3D
  ySpec: AxisSpec3D
  zSpec: AxisSpec3D
  selectedId: number | null
  /** 视角重置计数器：每次 +1 强制 remount 图表回到默认视角。 */
  resetKey: number
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
  grain: ['--yellow-500', '#c99a3a'],
  protein: ['--berry-500', '#a84c3c'],
  dairy: ['--sky-400', '#6a99ad'],
  vegetable: ['--green-500', '#4e7d4c'],
  fruit: ['--orange-500', '#c4742a'],
  fat: ['--yellow-400', '#caa850'],
  beverage: ['--sky-400', '#6a99ad'],
  snack: ['--orange-400', '#c89456'],
  other: ['--ink-500', '#7a6f63'],
}

const DEFAULT_VIEW = { alpha: 20, beta: 40, distance: 180, panX: 0, panY: 0 }

function escapeHtml(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function pointName(point: MapPoint3D): string {
  const primary = point.food.display_name || point.food.description_en
  return primary === point.food.description_en ? primary : `${primary}（${point.food.description_en}）`
}

/** 食材营养探索三维散点图：真实 x/y/z 坐标，支持旋转/缩放/悬停/点击。 */
export default function Scatter3DMap({
  points,
  xSpec,
  ySpec,
  zSpec,
  selectedId,
  resetKey,
  loading = false,
  onSelect,
}: Scatter3DMapProps) {
  const axisColor = chartToken('--ink-400', '#9a9186')
  const lineColor = chartToken('--line', '#eadfd2')
  const inkColor = chartToken('--ink-600', '#6e665c')
  const cardColor = chartToken('--bg-card', '#ffffff')
  const markColor = chartToken('--orange-500', '#f2a65a')

  const grouped = new Map<CategoryGroup, MapPoint3D[]>()
  for (const p of points) {
    const g = resolveCategoryGroup(p.food)
    const bucket = grouped.get(g) ?? []
    bucket.push(p)
    grouped.set(g, bucket)
  }

  const series = GROUP_ORDER.filter((g) => (grouped.get(g)?.length ?? 0) > 0).map((g) => {
    const [token, fallback] = GROUP_TOKEN[g]
    const groupColor = chartToken(token, fallback)
    const pts = grouped.get(g) ?? []
    const seriesData = pts.map((p) => ({
      name: pointName(p),
      value: [p.x, p.y, p.z] as [number, number, number],
      fdcId: p.food.fdc_id,
      categoryLabel: p.food.category_zh ?? GROUP_LABEL[g],
      symbolSize: p.food.fdc_id === selectedId ? 18 : 10,
      itemStyle: {
        color: groupColor,
        opacity: selectedId === null || p.food.fdc_id === selectedId ? 0.85 : 0.3,
        borderColor: p.food.fdc_id === selectedId ? markColor : 'transparent',
        borderWidth: p.food.fdc_id === selectedId ? 2 : 0,
      },
    }))

    return {
      name: GROUP_LABEL[g],
      type: 'scatter3D' as const,
      emphasis: { focus: 'series' as const },
      // 系列级颜色供图例取用；否则图例会退回 ECharts 默认调色板，与散点颜色不符。
      itemStyle: { color: groupColor },
      data: seriesData,
    }
  })

  const legendData = GROUP_ORDER.filter((g) => (grouped.get(g)?.length ?? 0) > 0).map((g) => GROUP_LABEL[g])

  const option = {
    color: GROUP_ORDER.map((g) => chartToken(GROUP_TOKEN[g][0], GROUP_TOKEN[g][1])),
    tooltip: {
      trigger: 'item' as const,
      backgroundColor: cardColor,
      borderColor: lineColor,
      textStyle: { color: inkColor, fontSize: 12 },
      formatter: (params: unknown) => {
        const p = params as {
          data?: { name?: string; value?: [number, number, number]; categoryLabel?: string }
        }
        const d = p.data
        if (!d || !d.value) return ''
        const [x, y, z] = d.value
        return [
          `<strong>${escapeHtml(d.name ?? '')}</strong>`,
          `<span style="color:${axisColor}">${escapeHtml(d.categoryLabel ?? '')}</span>`,
          `${xSpec.label}：${formatAmount(x, xSpec.decimals)} ${xSpec.unit}`,
          `${ySpec.label}：${formatAmount(y, ySpec.decimals)} ${ySpec.unit}`,
          `${zSpec.label}：${formatAmount(z, zSpec.decimals)} ${zSpec.unit}`,
        ].join('<br/>')
      },
    },
    legend: {
      type: 'scroll' as const,
      top: 8,
      right: 12,
      itemWidth: 10,
      itemHeight: 10,
      icon: 'circle',
      textStyle: { color: inkColor, fontSize: 11 },
      pageIconColor: inkColor,
      data: legendData,
    },
    xAxis3D: {
      type: 'value' as const,
      min: 0,
      name: `${xSpec.label}（${xSpec.unit}/100g）`,
      nameTextStyle: { color: axisColor, fontSize: 12 },
      axisLine: { lineStyle: { color: lineColor } },
      axisLabel: { color: axisColor, fontSize: 11 },
    },
    yAxis3D: {
      type: 'value' as const,
      min: 0,
      name: `${ySpec.label}（${ySpec.unit}/100g）`,
      nameTextStyle: { color: axisColor, fontSize: 12 },
      axisLine: { lineStyle: { color: lineColor } },
      axisLabel: { color: axisColor, fontSize: 11 },
    },
    zAxis3D: {
      type: 'value' as const,
      min: 0,
      name: `${zSpec.label}（${zSpec.unit}/100g）`,
      nameTextStyle: { color: axisColor, fontSize: 12 },
      axisLine: { lineStyle: { color: lineColor } },
      axisLabel: { color: axisColor, fontSize: 11 },
    },
    grid3D: {
      boxWidth: 100,
      boxDepth: 100,
      boxHeight: 70,
      environment: 'none',
      light: {
        main: { intensity: 1.2, shadow: false },
        ambient: { intensity: 0.6 },
      },
      viewControl: {
        type: 'perspective' as const,
        alpha: DEFAULT_VIEW.alpha,
        beta: DEFAULT_VIEW.beta,
        distance: DEFAULT_VIEW.distance,
        panX: DEFAULT_VIEW.panX,
        panY: DEFAULT_VIEW.panY,
        autoRotate: false,
        projection: 'perspective' as const,
      },
      axisLine: { lineStyle: { color: lineColor } },
      splitLine: { lineStyle: { color: lineColor, type: 'dashed' as const } },
    },
    series,
  }

  return (
    <ChartShell3D
      key={resetKey}
      option={option}
      ariaLabel={zhCN.a11y.chartLabel}
      height={520}
      loading={loading}
      loadingLabel={zhCN.explore.loadingChart}
      onItemClick={(params) => {
        const p = params as { data?: { fdcId?: number } }
        const fdcId = p.data?.fdcId
        if (fdcId === undefined) return
        const point = points.find((c) => c.food.fdc_id === fdcId)
        if (point) onSelect(point.food)
      }}
    />
  )
}
