import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

/** How many chips stay in the front row before the rest fold behind a toggle. */
const VISIBLE = 6

/**
 * Order the terms so the front row carries the most specific ones, and say how
 * many are held back.
 *
 * A term that only broadens one already listed is demoted rather than dropped:
 * `renewable` beside `renewable energy` is still analysable, it just does not
 * earn a front-row slot over the more specific version of itself.
 */
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
  // Whatever is being analysed has to be on screen, or the page shows a result
  // with no chip marked as its source.
  const pinned = ordered.filter((f) => f === active)
  const rest = ordered.filter((f) => f !== active)
  const all = [...pinned, ...rest]
  return { shown: all.slice(0, VISIBLE), extra: all.slice(VISIBLE) }
}

/**
 * The profile terms this page can analyse.
 *
 * Each page passes only the fields that answer its own question. Showing all of
 * them everywhere is what let `fusion` reach a patent search, where it matched
 * image fusion and sensor fusion instead.
 */
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
