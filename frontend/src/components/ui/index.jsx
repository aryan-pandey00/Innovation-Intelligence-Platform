import { useId, useState } from 'react'

export function PageHeader({ trail, title, children }) {
  return (
    <header className="page-head">
      {trail && <div className="crumb">{trail}</div>}
      <h1>{title}</h1>
      {children && <p className="page-sub">{children}</p>}
    </header>
  )
}

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

export function RankedList({ items, valueKey = 'count', labelKey = 'topic',
                             shareKey, bars = true, format }) {
  const max = Math.max(1, ...items.map((i) => Number(i[valueKey]) || 0))
  const text = (v) => (format ? format(v) : v.toLocaleString('en-US'))
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
