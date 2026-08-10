/** Shared page primitives, so headers, cards and stat tiles are styled once. */
import { useId, useState } from 'react'

/** Page title, optional breadcrumb trail and a one-line description. */
export function PageHeader({ trail, title, children }) {
  return (
    <header className="page-head">
      {trail && <div className="crumb">{trail}</div>}
      <h1>{title}</h1>
      {children && <p className="page-sub">{children}</p>}
    </header>
  )
}

/** A titled section. `aside` sits opposite the title for links or actions. */
export function Card({ title, sub, aside, className = '', children }) {
  return (
    <section className={`card ${className}`.trim()}>
      {(title || aside) && (
        <div className="card-head">
          <div>
            {title && <h2>{title}</h2>}
            {sub && <p className="card-sub">{sub}</p>}
          </div>
          {aside}
        </div>
      )}
      {children}
    </section>
  )
}

/** A headline number. `note` qualifies it: what was counted, or how much of a
 *  corpus was sampled. */
export function StatCard({ value, label, note, tone, hint }) {
  return (
    <div className="stat-card">
      <span className={`stat-num${tone ? ` tone-${tone}` : ''}`}>{value}</span>
      <span className="stat-label">
        {label}
        {hint && <InfoHint>{hint}</InfoHint>}
      </span>
      {note && <span className="stat-note">{note}</span>}
    </div>
  )
}

export function StatGrid({ children }) {
  return <div className="stat-grid">{children}</div>
}

/**
 * A small ⓘ revealing a qualifier on hover or focus. Accuracy caveats have to
 * stay — they stop a sampled ranking being read as fact — but not inline.
 */
export function InfoHint({ children, label = 'More about this figure' }) {
  const [open, setOpen] = useState(false)
  const id = useId()
  return (
    <span className="hint-wrap">
      <button
        type="button"
        className="hint-btn"
        aria-label={label}
        aria-describedby={open ? id : undefined}
        aria-expanded={open}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onClick={(e) => { e.preventDefault(); setOpen((v) => !v) }}
      >
        i
      </button>
      {open && <span role="tooltip" id={id} className="hint-bubble">{children}</span>}
    </span>
  )
}

/**
 * Ranked list with an inline magnitude bar, for the 5-10 item rankings a bar
 * chart oversells.
 *
 * `bars={false}` where values are near-identical: 6,6,5,5,5,5,4,4 draws as
 * 100/100/83/83/83/83/67/67, encoding nothing while implying precision.
 * `shareKey` gives each bar an absolute meaning rather than one relative to the
 * leading row.
 */
export function RankedList({ items, valueKey = 'count', labelKey = 'topic',
                             shareKey, bars = true, format }) {
  const max = Math.max(1, ...items.map((i) => Number(i[valueKey]) || 0))
  const text = (v) => (format ? format(v) : v.toLocaleString('en-US'))
  /* Every <li> is its own grid, so an `auto` value column is sized by that row's
     own number and slides the fixed-width bar sideways — up to 25px of drift on
     a list running 12,405 down to 97. One width for the whole list instead. */
  const valueWidth = Math.max(1, ...items.map(
    (i) => text(Number(i[valueKey]) || 0).length))
  return (
    <ol className="ranked" style={{ '--value-w': `${valueWidth}ch` }}>
      {items.map((item, i) => {
        const value = Number(item[valueKey]) || 0
        const share = shareKey ? item[shareKey] : null
        const cols = [bars && 'has-bar', share != null && 'has-share']
          .filter(Boolean).join(' ')
        return (
          <li key={item[labelKey] ?? i} className={cols}>
            <span className="ranked-rank">{i + 1}</span>
            <span className="ranked-label" title={item[labelKey]}>{item[labelKey]}</span>
            {bars && (
              <span className="ranked-bar" aria-hidden="true">
                <span style={{ width: `${(value / max) * 100}%` }} />
              </span>
            )}
            <span className="ranked-value">{text(value)}</span>
            {/* A holder of 23 patents in a 502,434-patent field rounds to 0.0%,
                which reads as "holds none" rather than "holds very few". */}
            {share != null && (
              <span className="ranked-share">
                {share === 0 && value > 0 ? '<0.01%' : `${share}%`}
              </span>
            )}
          </li>
        )
      })}
    </ol>
  )
}

export function EmptyNote({ children }) {
  return <p className="empty-note">{children}</p>
}
