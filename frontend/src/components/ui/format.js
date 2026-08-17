
export function fmtAmount(min, max, currency = 'USD') {
  const one = (n) => {
    const v = Number(n)
    if (!Number.isFinite(v)) return null
    if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(v % 1_000_000 ? 1 : 0)}M`
    if (v >= 1000) return `${Math.round(v / 1000)}K`
    return `${v}`
  }
  if (min == null && max == null) return null
  if (min != null && max != null) {
    const [lo, hi] = [one(min), one(max)]
    return lo === hi ? `${currency} ${lo}` : `${currency} ${lo}–${hi}`
  }
  return `${currency} ${one(min ?? max)}`
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export function fmtDate(iso) {
  if (!iso) return null
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso))
  if (!m) return String(iso)
  const [, y, mm, dd] = m
  const month = MONTHS[Number(mm) - 1]
  if (!month) return String(iso)
  return `${Number(dd)} ${month} ${y}`
}

export function fmtStamp(iso) {
  const day = fmtDate(iso)
  if (!day) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return day
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `${day}, ${hh}:${mm}`
}

export function fmtDeadline(iso, today = new Date()) {
  const shown = fmtDate(iso)
  if (!shown) return null
  const stamp = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`
  return `${String(iso) < stamp ? 'Closed' : 'Closes'} ${shown}`
}

export const ELIG_UI = {
  eligible: { cls: 'elig-ok', label: 'Eligible' },
  unconfirmed: { cls: 'elig-maybe', label: 'Possibly eligible' },
  ineligible: { cls: 'elig-no', label: 'Not eligible' },
}

export const eligUi = (state) => ELIG_UI[state] || ELIG_UI.unconfirmed

export const SOURCE_LABELS = {
  government_grant: 'Government Grant',
  research_council: 'Research Council',
  innovation_fund: 'Innovation Fund',
  startup_accelerator: 'Startup Accelerator',
  venture_program: 'Venture Program',
  international_agency: 'International Agency',
}

export const fmtCount = (n) => (n == null || !Number.isFinite(Number(n))
  ? '—'
  : Number(n).toLocaleString('en-US'))

export const fmtPct = (n, { sign = false } = {}) => {
  if (n == null || !Number.isFinite(Number(n))) return '—'
  const v = Math.round(Number(n))
  return `${sign && v > 0 ? '+' : ''}${v}%`
}
