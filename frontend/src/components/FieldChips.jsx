import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

const VISIBLE = 6

function organise(fields, active) {
  const seen = new Set()
  const unique = []
  for (const f of fields) {
    const key = String(f).trim().toLowerCase()
    if (!key || seen.has(key)) continue
    seen.add(key)
    unique.push(f)
  }

  const broadens = (term) => {
    const t = `${String(term).trim().toLowerCase()} `
    return unique.some((other) => other !== term
      && String(other).trim().toLowerCase().startsWith(t))
  }

  const ordered = [
    ...unique.filter((f) => !broadens(f)),
    ...unique.filter((f) => broadens(f)),
  ]
  const pinned = ordered.filter((f) => f === active)
  const rest = ordered.filter((f) => f !== active)
  const all = [...pinned, ...rest]
  return { shown: all.slice(0, VISIBLE), extra: all.slice(VISIBLE) }
}

export default function FieldChips({ fields, active, onPick, label = 'Your fields', fallback }) {
  const [expanded, setExpanded] = useState(false)
  const { shown, extra } = useMemo(() => organise(fields || [], active), [fields, active])
  if (shown.length === 0) return null

  const visible = expanded ? [...shown, ...extra] : shown

  return (
    <div className="field-chips-wrap">
      <div className="field-chips">
        <span className="fc-label">{label}</span>
        {visible.map((f) => (
          <button
            key={f}
            type="button"
            className={f === active ? 'field-chip active' : 'field-chip'}
            onClick={() => onPick(f)}
          >
            {f}
          </button>
        ))}
        {extra.length > 0 && (
          <button type="button" className="field-chip chip-more"
                  aria-expanded={expanded}
                  onClick={() => setExpanded((v) => !v)}>
            {expanded ? 'Show fewer' : `+${extra.length} more`}
          </button>
        )}
      </div>
      {fallback && (
        <p className="field-help warn">
          Showing research domains: a discipline matches patents less precisely.
          <Link to="/portfolio" className="link-block">Add a technology area →</Link>
        </p>
      )}
    </div>
  )
}
