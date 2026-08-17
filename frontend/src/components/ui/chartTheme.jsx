
export const CHART_COLORS = {
  research: '#1e293b',
  patents: '#0d9488',
  grid: '#e3e7ee',
  axis: '#64748b',
}

export const SEQUENCE = ['#1e293b', '#334155', '#4a5b73', '#64748b', '#8494a8', '#a8b4c4']

export const sequenceColor = (i) => SEQUENCE[Math.min(i, SEQUENCE.length - 1)]

export const axisProps = {
  tick: { fontSize: 12, fill: CHART_COLORS.axis },
  stroke: CHART_COLORS.grid,
  tickLine: false,
}

export const gridProps = {
  strokeDasharray: '3 3',
  stroke: CHART_COLORS.grid,
  vertical: false,
  strokeOpacity: 0.75,
}

export const tooltipProps = {
  contentStyle: {
    borderRadius: 8,
    border: `1px solid ${CHART_COLORS.grid}`,
    boxShadow: '0 4px 16px rgba(15,23,42,.08)',
    fontSize: 13,
  },
  labelStyle: { fontWeight: 600, marginBottom: 2 },
}

export const compactNumber = (n) => {
  const v = Number(n)
  if (!Number.isFinite(v)) return ''
  if (Math.abs(v) >= 1_000_000) return `${Math.round(v / 100_000) / 10}M`
  if (Math.abs(v) >= 1_000) return `${Math.round(v / 100) / 10}K`
  return `${v}`
}

export const lineProps = {
  type: 'monotone',
  strokeWidth: 2.5,
  dot: { r: 3.2, strokeWidth: 1.6, stroke: '#fff' },
  activeDot: { r: 5.5, strokeWidth: 2, stroke: '#fff' },
}

export const seriesProps = (color) => ({
  ...lineProps,
  stroke: color,
  dot: { ...lineProps.dot, fill: color },
  activeDot: { ...lineProps.activeDot, fill: color },
})

export function areaGradient(id, color) {
  return (
    <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stopColor={color} stopOpacity={0.18} />
      <stop offset="100%" stopColor={color} stopOpacity={0} />
    </linearGradient>
  )
}

export function pointLabel({ data, dataKey, format = compactNumber,
                             color = CHART_COLORS.axis, lift = 0 }) {
  const values = (data || []).map((d) => Number(d?.[dataKey]))
  const lastIndex = values.reduce((acc, v, i) => (Number.isFinite(v) ? i : acc), -1)
  let peakIndex = -1
  values.forEach((v, i) => {
    if (Number.isFinite(v) && (peakIndex < 0 || v > values[peakIndex])) peakIndex = i
  })

  return function Label({ viewBox, x, y, index, value }) {
    const px = viewBox?.x ?? x
    const py = viewBox?.y ?? y
    const show = index === lastIndex || index === peakIndex
    if (!show || px == null || py == null || !Number.isFinite(Number(value))) return null
    const atEnd = index === lastIndex
    return (
      <text
        x={atEnd ? px - 6 : px}
        y={py - 10 - lift}
        textAnchor={atEnd ? 'end' : 'middle'}
        fontSize={11.5}
        fontWeight={600}
        fill={color}
      >
        {format(value, index)}
      </text>
    )
  }
}
