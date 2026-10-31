import { ScatterChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  MarkPointComponent,
  TooltipComponent,
} from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
// echarts-gl 会通过 side effect 自动安装 Scatter3DChart + Grid3DComponent
import 'echarts-gl'

/**
 * 三维散点图专用 ECharts 实例。
 * 这个文件只在 Scatter3DMap 被 React.lazy 真正加载时才执行，
 * 不会进入首屏主包，也不会影响 ChartShell 使用的二维 echarts 实例。
 *
 * echarts-gl 通过 import 'echarts-gl' 的 side effect 自动向全局
 * echarts 实例注册 Scatter3DChart 和 Grid3DComponent。
 * 这里只需注册 echarts-core 常规组件即可。
 */
echarts.use([
  ScatterChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  MarkPointComponent,
  CanvasRenderer,
])

export { echarts }

export type Chart3DOption = Record<string, unknown>

/** 检测浏览器是否支持 WebGL。echarts-gl 的 scatter3D 依赖 WebGL。 */
export function isWebGLAvailable(): boolean {
  if (typeof window === 'undefined') return false
  try {
    const canvas = document.createElement('canvas')
    const gl =
      canvas.getContext('webgl2') ||
      canvas.getContext('webgl') ||
      canvas.getContext('experimental-webgl')
    return !!gl
  } catch {
    return false
  }
}
