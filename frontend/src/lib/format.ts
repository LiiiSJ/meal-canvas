/** 数字格式化集中在这里，页面不自行决定小数位。 */

const formatterCache = new Map<number, Intl.NumberFormat>()

function getFormatter(decimals: number): Intl.NumberFormat {
  const cached = formatterCache.get(decimals)
  if (cached) return cached
  const formatter = new Intl.NumberFormat('zh-CN', {
    maximumFractionDigits: decimals,
    minimumFractionDigits: 0,
  })
  formatterCache.set(decimals, formatter)
  return formatter
}

/** 缺失返回“—”，0 正常显示为 0。 */
export function formatAmount(value: number | null | undefined, decimals = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—'
  return getFormatter(Math.max(0, Math.min(decimals, 4))).format(value)
}

export function formatInteger(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—'
  return getFormatter(0).format(value)
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  return value
}
