/** Shared value formatting, so no page reinvents an amount or a date. */

/** `USD 150K–1.5M`, or null when there is no amount, so callers can omit the
 *  element rather than render an empty one. */
export function fmtAmount(min, max, currency = 'USD') {
  const one = (n) => {
    const v = Number(n)
    if (!Number.isFinite(v)) return null
    if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(v % 1_000_000 ? 1 : 0)}M`
    if (v >= 1000) return `${Math.round(v / 1000)}K`
    return `${v}`
  }
  if (min == null && max == null) return null
  if (min != null && max != null) return `${currency} ${one(min)}–${one(max)}`
  return `${currency} ${one(min ?? max)}`
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/**
 * `15 Nov 2026` from an ISO date. Parsed by hand: `new Date(iso)` reads a bare
 * `YYYY-MM-DD` as UTC midnight and prints it local, showing the day before for
 * anyone west of Greenwich.
 */
export function fmtDate(iso) {
  if (!iso) return null
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso))
  if (!m) return String(iso)
  const [, y, mm, dd] = m
  const month = MONTHS[Number(mm) - 1]
  if (!month) return String(iso)
  return `${Number(dd)} ${month} ${y}`
}

/** `Closes 15 Nov 2026`, or `Closed 3 Jan 2026` once the date has passed. */
export function fmtDeadline(iso, today = new Date()) {
  const shown = fmtDate(iso)
  if (!shown) return null
  const stamp = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`
  return `${String(iso) < stamp ? 'Closed' : 'Closes'} ${shown}`
}

/**
 * Three states: a country-restricted grant for someone who has not set a country
 * is neither eligible nor ruled out.
 */
export const ELIG_UI = {
  eligible: { cls: 'elig-ok', label: 'Eligible' },
  unconfirmed: { cls: 'elig-maybe', label: 'Possibly eligible' },
  ineligible: { cls: 'elig-no', label: 'Not eligible' },
}

export const eligUi = (state) => ELIG_UI[state] || ELIG_UI.unconfirmed

/** Exact figures with separators: 350,252, not 350.3K. Stat cards state real
 *  counts; `compactNumber` in chartTheme stays for axes. */
export const fmtCount = (n) => (n == null || !Number.isFinite(Number(n))
  ? '—'
  : Number(n).toLocaleString('en-US'))

/** Whole-number signed percentages: year-on-year counts carry no decimal. */
export const fmtPct = (n, { sign = false } = {}) => {
  if (n == null || !Number.isFinite(Number(n))) return '—'
  const v = Math.round(Number(n))
  return `${sign && v > 0 ? '+' : ''}${v}%`
}
