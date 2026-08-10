import { useEffect, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { innovationService, authService, extractErrorMessage } from '../services/api'
import Loading from '../components/Loading'
import FieldChips from '../components/FieldChips'
import { PageHeader, Card, InfoHint } from '../components/ui'
import { fmtCount, fmtPct } from '../components/ui/format'
import { byKey } from '../components/modules'

const RATING_TONE = { High: 'good', Moderate: 'warn' }

/* A ring, drawn once, used five times. The whole circle is 100 and the arc is
   the score, so the reader never has to ask which scale a shape belongs to. The
   number sits in the middle, so colour never carries meaning on its own. */
const R = 34
const CIRC = 2 * Math.PI * R

function Gauge({ value }) {
  const pct = Math.max(0, Math.min(100, value))
  return (
    <span className="gauge-wrap">
      <svg viewBox="0 0 80 80" className={`gauge${pct < 50 ? ' low' : ''}`} aria-hidden="true">
        <circle className="gauge-track" cx="40" cy="40" r={R} />
        <circle className="gauge-fill" cx="40" cy="40" r={R}
                strokeDasharray={CIRC} strokeDashoffset={CIRC * (1 - pct / 100)} />
      </svg>
      <span className="gauge-val">{value}</span>
    </span>
  )
}

export default function Innovation() {
  const [query, setQuery] = useState('')
  const [fields, setFields] = useState([])
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    innovationService.myAssessment()
      .then((res) => {
        setData(res.data); setQuery(res.data.query); setFields(res.data.profile_fields || [])
      })
      .catch((err) => {
        if (err.response?.status === 401) { authService.logout(); navigate('/login') }
        // Anything else has to be shown. Without this the page fell through to its
        // "search above" empty card, so a rate-limited data source looked exactly
        // like an empty profile.
        else setError(extractErrorMessage(err, 'Could not load the innovation assessment'))
      })
      .finally(() => setLoading(false))
  }, [navigate])

  const analyze = async (e, term) => {
    e?.preventDefault()
    const q = (term ?? query).trim()
    if (q.length < 2) return
    setQuery(q); setLoading(true); setError('')
    try {
      const res = await innovationService.assessment(q)
      setData(res.data)
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not load the innovation assessment'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="dashboard">
      {/* The trail names the sidebar section this page sits in. It read
          "Intelligence", which is not a section that exists. */}
      <PageHeader trail="Analyse" title="Innovation Assessment">
        How strong your position is in a technology, and what each factor
        contributes to the score.
      </PageHeader>

      <form onSubmit={analyze} className="search-row">
        <input placeholder="Assess a technology, e.g. solid-state battery"
               aria-label="Technology to assess"
               value={query} onChange={(e) => setQuery(e.target.value)} />
        <button type="submit">Analyse</button>
      </form>
      <FieldChips fields={fields} active={data?.query} onPick={(f) => analyze(null, f)}
                  label="Your technology areas" fallback={data?.fields_are_fallback} />

      {error && <div className="error">{error}</div>}
      {loading && <Loading message="Scoring innovation potential…" />}

      {!loading && !data && (
        <Card>
          <p className="empty-note">
            Search a technology above, or add a technology area to your portfolio to score
            your own field automatically.
          </p>
          <Link to="/portfolio" className="btn-quiet" style={{ marginTop: 12 }}>
            Go to my portfolio
          </Link>
        </Card>
      )}

      {!loading && data && (
        <>
          <Assessment data={data} />
          <NextSteps data={data} />
        </>
      )}
    </div>
  )
}

/* This page scores a technology; acting on the score is its own module, with its
   own page. It was a second tab here, which put the same content in two places
   once that page existed — and the two could sit on different technologies with
   nothing on screen saying so.

   The link names the pathway rather than the module, because "Industry
   Partnership · 4 actions" is a reason to click and "Commercialization" is not.
   `data.commercialization` stays in this payload for exactly that: it is derived
   from figures already computed, so the label costs nothing. */
function NextSteps({ data }) {
  const comm = data.commercialization
  const actions = comm?.recommendations?.length || 0
  const Commercialization = byKey.commercialization.Icon
  const Patents = byKey.patents.Icon

  return (
    <div className="next-row">
      <Link to="/commercialization" className="next-card">
        <Commercialization size={18} />
        <span>
          <strong>Plan the route to market</strong>
          {comm?.pathway?.title
            ? `${comm.pathway.title} · ${plural(actions, 'recommended step')}`
            : 'What to do about this score'}
        </span>
      </Link>
      <Link to="/patents" className="next-card">
        <Patents size={18} />
        <span><strong>See who is patenting</strong>The themes running through the filings</span>
      </Link>
    </div>
  )
}

const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`

/* What the score was actually measured on.
   Three states, not two: an empty portfolio and a full one holding nothing about
   this technology are different situations, and collapsing them told a user with
   three energy papers to add work they had already added. */
function Basis({ signals: s, query }) {
  const held = (s.portfolio_publications ?? 0) + (s.portfolio_patents ?? 0)
  const matched = s.own_publications + s.own_patents
  const skipped = held - matched

  if (matched === 0) {
    return held > 0 ? (
      // "is not about this technology" would be a claim the matching cannot
      // support — it compares words, so it can miss a paper that never names the
      // technology it is about. Say what was actually checked.
      <>Measured for <strong>{query}</strong>. Nothing in your{' '}
        <Link to="/portfolio">portfolio</Link> mentions this technology, so this scores
        the field rather than your position in it.</>
    ) : (
      <>Measured for <strong>{query}</strong>. Add publications and patents to your{' '}
        <Link to="/portfolio">portfolio</Link> and this becomes specific to you.</>
    )
  }

  const parts = []
  if (s.own_publications > 0) parts.push(plural(s.own_publications, 'publication'))
  if (s.own_patents > 0) parts.push(plural(s.own_patents, 'patent'))
  return (
    <>Measured for <strong>{query}</strong>, including {parts.join(' and ')} from your
      portfolio.
      {skipped > 0 && <> The other {plural(skipped, 'item')} there{' '}
        {skipped === 1 ? "doesn’t" : "don’t"} mention it, so{' '}
        {skipped === 1 ? 'it is' : 'they are'} not counted.</>}
    </>
  )
}

function Assessment({ data }) {
  const s = data.signals
  // Heaviest factor first, so the order is visible from the shares on the card and
  // the layout is the same on every visit rather than reshuffling with the data.
  const factors = [...data.components].sort((a, b) => b.weight - a.weight || b.score - a.score)
  const strongest = factors.reduce((best, c) => (c.score > best.score ? c : best))
  // Where the score has the most to gain: the weight not yet earned. A weak factor
  // on a small weight is not worth naming; a weak factor on a big one is.
  const unearned = (c) => c.weight * (100 - c.score)
  const gap = factors.reduce((worst, c) => (unearned(c) > unearned(worst) ? c : worst))

  return (
    <>
      {!s.patents_available && (
        <div className="notice">
          Patent data is unavailable right now, so the patent components fall back to
          research signals alone.
        </div>
      )}

      <div className="card score-hero">
        <div className={`big-score${RATING_TONE[data.rating] ? ` tone-${RATING_TONE[data.rating]}` : ''}`}>
          {data.innovation_score}
          <small>out of 100</small>
        </div>
        <div style={{ flex: 1 }}>
          <span className="rating-pill">{data.rating} potential</span>
          <p className="score-context"><Basis signals={s} query={data.query} /></p>
        </div>
      </div>

      {/* One number per factor, one scale, one sentence of method.
          A reader needs two things: how am I doing on each factor, and how much
          does each one matter. That is a score and a share. The ring makes the
          score unambiguous (the circle is the 100) and the share sits under it as
          text rather than as a second length to compare. Contribution, points and
          headroom are all derivable from those two, so none of them is printed. */}
      <Card
        title="Where your score comes from"
        sub={`Each factor is scored out of 100, then counts for the share shown beneath it. `
          + `Together they make your ${data.innovation_score}.`}
      >
        <div className="factor-grid">
          {factors.map((c) => (
            <div key={c.key} className="factor">
              <Gauge value={c.score} />
              <span className="factor-name">
                {c.label}
                <InfoHint>{c.description}</InfoHint>
              </span>
              <span className="factor-share">{c.weight}% of the score</span>
            </div>
          ))}
        </div>
        {/* The conclusion the five rings add up to, in words. This is the half of
            "explainable" that a chart cannot do: which factor to act on. */}
        <p className="factor-takeaway">
          {strongest.key === gap.key ? (
            <><strong>{strongest.label}</strong> is your strongest factor, and because it
              carries the most weight it is still where the total has the most to gain.</>
          ) : (
            <><strong>{strongest.label}</strong> is your strongest factor. Raising{' '}
              <strong>{gap.label}</strong> would move the total most.</>
          )}
        </p>
      </Card>

      {/* The two totals count every year on record while the two growth figures
          compare an 11-year window, so "10,432 papers" sits beside "+41%" that
          describes 5,070 of them. Both are right; unlabelled they read as one. */}
      <Card title="The measurements behind it"
            sub="Totals cover every year on record. The growth figures compare the last
                 eleven complete years.">
        <dl className="fact-list">
          <div><dt>Research papers</dt><dd>{fmtCount(s.research_total)}</dd></div>
          <div><dt>Research growth</dt><dd>{fmtPct(s.research_growth, { sign: true })}</dd></div>
          <div><dt>Patents</dt><dd>{fmtCount(s.patent_total)}</dd></div>
          <div>
            <dt>Patent growth</dt>
            <dd>
              {s.patent_history_reliable
                ? fmtPct(s.patent_growth, { sign: true })
                : 'not measurable yet'}
            </dd>
          </div>
          <div><dt>Busiest patent year</dt><dd>{s.busiest_year || '—'}</dd></div>
          <div><dt>Lifecycle stage</dt><dd>{s.stage}</dd></div>
        </dl>
      </Card>
    </>
  )
}
