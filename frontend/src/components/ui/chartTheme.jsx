/**
 * One source of truth for chart styling. Values mirror the CSS variables in
 * :root, so charts two pages apart cannot drift into looking like two products.
 */

export const CHART_COLORS = {
  research: '#1e293b',   // --navy
  // Not --accent gold: it measures 2.44:1 on white, under the 3:1 a meaningful
  // graphic needs, and cannot reach it on any light background. Teal is 3.74:1.
  patents: '#0d9488',    // --chart-3
  grid: '#e3e7ee',       // --line
  axis: '#64748b',       // --muted
}

/**
 * A size-ordered set uses ONE hue at decreasing intensity, not a rainbow: five
 * hues imply five categories the reader must track, and there are none.
 */
export const SEQUENCE = ['#1e293b', '#334155', '#4a5b73', '#64748b', '#8494a8', '#a8b4c4']

export const sequenceColor = (i) => SEQUENCE[Math.min(i, SEQUENCE.length - 1)]

/** Shared axis/grid/tooltip props so every chart lines up. */
export const axisProps = {
  tick: { fontSize: 12, fill: CHART_COLORS.axis },
  stroke: CHART_COLORS.grid,
  tickLine: false,
}

export const gridProps = {
  strokeDasharray: '3 3',
  stroke: CHART_COLORS.grid,
  vertical: false,
  strokeOpacity: 0.75,     // the line is the foreground, not the grid
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

/** Compact axis numbers: 350000 -> "350K". Full precision belongs in tooltips. */
export const compactNumber = (n) => {
  const v = Number(n)
  if (!Number.isFinite(v)) return ''
  if (Math.abs(v) >= 1_000_000) return `${Math.round(v / 100_000) / 10}M`
  if (Math.abs(v) >= 1_000) return `${Math.round(v / 100) / 10}K`
  return `${v}`
}

/**
 * Line treatment. Permanent dots make an eleven-year series read as eleven
 * measurements rather than one drawn curve; `activeDot` still marks the hovered one.
 */
export const lineProps = {
  type: 'monotone',
  strokeWidth: 2.5,
  // the white ring separates the marker from the stroke it sits on
  dot: { r: 3.2, strokeWidth: 1.6, stroke: '#fff' },
  activeDot: { r: 5.5, strokeWidth: 2, stroke: '#fff' },
}

/**
 * The same treatment with the dot's fill stated. `<Area>` defaults a dot's fill
 * to the series stroke but `<Line>` defaults it to white, so bare `lineProps` on
 * a Line draws white-on-white. Use this everywhere instead.
 */
export const seriesProps = (color) => ({
  ...lineProps,
  stroke: color,
  dot: { ...lineProps.dot, fill: color },
  activeDot: { ...lineProps.activeDot, fill: color },
})

/**
 * `<defs>` for a fill fading out beneath a line — body for a single-series chart
 * without adding information. Two overlapping fills would muddy both lines.
 */
export function areaGradient(id, color) {
  return (
    <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stopColor={color} stopOpacity={0.18} />
      <stop offset="100%" stopColor={color} stopOpacity={0} />
    </linearGradient>
  )
}

/**
 * Prints the latest reading and the peak beside their points, so the two numbers
 * that matter are on the chart rather than behind a hover. Pass to `<Line
 * label={...}>`; it returns null for every other point.
 */
export function pointLabel({ data, dataKey, format = compactNumber,
                             color = CHART_COLORS.axis }) {
  const values = (data || []).map((d) => Number(d?.[dataKey]))
  const lastIndex = values.reduce((acc, v, i) => (Number.isFinite(v) ? i : acc), -1)
  let peakIndex = -1
  values.forEach((v, i) => {
    if (Number.isFinite(v) && (peakIndex < 0 || v > values[peakIndex])) peakIndex = i
  })

  // Recharts 3 gives position in `viewBox`; the top-level x/y pair survives only
  // because they happen to be valid SVG attributes.
  return function Label({ viewBox, x, y, index, value }) {
    const px = viewBox?.x ?? x
    const py = viewBox?.y ?? y
    const show = index === lastIndex || index === peakIndex
    if (!show || px == null || py == null || !Number.isFinite(Number(value))) return null
    // The final point sits against the right edge, so its label hangs left of it.
    const atEnd = index === lastIndex
    return (
      <text
        x={atEnd ? px - 6 : px}
        y={py - 10}
        textAnchor={atEnd ? 'end' : 'middle'}
        fontSize={11.5}
        fontWeight={600}
        fill={color}
      >
        {/* `index` too, so a series drawn on one scale can label itself with
            another — the momentum chart plots a percentage of each series' own
            peak and labels the count that percentage came from. */}
        {format(value, index)}
      </text>
    )
  }
}
