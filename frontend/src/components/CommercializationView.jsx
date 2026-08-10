import { Link } from 'react-router-dom'

/**
 * The commercialization module's output: a recommended pathway and the actions
 * under it.
 *
 * Shared by the Commercialization page and the Innovation Assessment tab, which
 * read the same analysis from two endpoints — the two must never render it
 * differently.
 */

/* Two groups, not five one-off category labels: PRODUCTIZATION, LICENSING,
   TIMING, INDUSTRY PARTNERSHIPS and FUNDING PATHWAY each appeared exactly once,
   so they grouped nothing and an action read no differently from reference. */
const GROUPS = [
  { key: 'now', title: 'Do next', sub: 'Carrying a deadline or a risk' },
  { key: 'context', title: 'Worth knowing', sub: 'Context for the decision' },
]

/* One card, four registers. The backend returns the parts separately (see
   commercialization.recommend) and each gets its own weight here:

     stat     leads, because a figure is what makes the card specific
     facts    at most two, small
     items    a list where the content is a list
     reading  one sentence, why it matters
     action   one imperative, marked. "Worth knowing" cards have none. */
function RecoCard({ reco }) {
  return (
    <article className="reco-card">
      <h4>{reco.title}</h4>

      {reco.stat && (
        <p className="reco-stat">
          <strong>{reco.stat.value}</strong>
          <span>{reco.stat.label}</span>
        </p>
      )}
      {reco.facts?.length > 0 && (
        <p className="reco-facts">{reco.facts.join(' · ')}</p>
      )}

      {reco.items?.length > 0 && (
        <ul className="reco-items">
          {reco.items.map((it) => (
            <li key={it.name}>
              <span className="reco-item-name" title={it.name}>{it.name}</span>
              <span className="reco-item-meta">
                {[it.kind, it.country].filter(Boolean).join(' · ')}
              </span>
              <span className="reco-item-value">{it.value}</span>
            </li>
          ))}
        </ul>
      )}

      {reco.reading && <p className="reco-reading">{reco.reading}</p>}
      {reco.action && <p className="reco-action">{reco.action}</p>}

      {reco.link && (
        <Link to={reco.link.to} className="inline-link reco-link">
          {reco.link.label} →
        </Link>
      )}
    </article>
  )
}

export default function CommercializationView({ pathway, recommendations }) {
  const recs = recommendations || []
  return (
    <>
      {/* Hero treatment matching the dashboard, and it shows the three readings
          that chose this route rather than just asserting it. */}
      <div className="pathway-hero">
        <span className="pathway-eyebrow">Recommended pathway</span>
        <h2>{pathway.title}</h2>
        <p>{pathway.detail}</p>
        {pathway.signals?.length > 0 && (
          <dl className="pathway-signals">
            {pathway.signals.map((sig) => (
              <div key={sig.label}>
                <dt>{sig.label}</dt>
                <dd>{sig.value}</dd>
              </div>
            ))}
          </dl>
        )}
      </div>

      {GROUPS.map((group) => {
        const items = recs.filter((r) => (r.priority || 'context') === group.key)
        if (items.length === 0) return null
        return (
          <section key={group.key} className="reco-group">
            <div className="reco-group-head">
              <h3>{group.title}</h3>
              <span>{group.sub}</span>
            </div>
            {/* one grid per group, so neither leaves an empty cell the way a
                single 2-column grid did with five cards */}
            <div className={`reco-grid cols-${Math.min(items.length, 3)}`}>
              {items.map((r, i) => <RecoCard key={i} reco={r} />)}
            </div>
          </section>
        )
      })}
    </>
  )
}
