import { useEffect, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { innovationService, authService, extractErrorMessage } from '../services/api'
import Loading from '../components/Loading'
import FieldChips from '../components/FieldChips'
import { PageHeader, Card, InfoHint } from '../components/ui'
import { fmtCount, fmtPct } from '../components/ui/format'
import { STEP_MS, useCountUp } from '../components/ui/motion'
import NextRow from '../components/NextRow'

const RATING_TONE = { High: 'good', Moderate: 'warn' }

const R = 34
const CIRC = 2 * Math.PI * R

function BigScore({ value, rating }) {
  const shown = useCountUp(value)
  const tone = RATING_TONE[rating] ? ` tone-${RATING_TONE[rating]}` : ''
  return (
    <div className={`big-score${tone}`} role="img" aria-label={`${value} out of 100`}>
      <span aria-hidden="true">{shown}</span>
      <small aria-hidden="true">out of 100</small>
    </div>
  )
}

function Gauge({ value, delay = 0 }) {
  const pct = Math.max(0, Math.min(100, value))
  const shown = useCountUp(pct, delay)
  return (
    <span className="gauge-wrap" role="img" aria-label={`${pct} out of 100`}>
      <svg viewBox="0 0 80 80" className={`gauge${pct < 50 ? ' low' : ''}`} aria-hidden="true">
        <circle className="gauge-track" cx="40" cy="40" r={R} />
        <circle className="gauge-fill" cx="40" cy="40" r={R}
                strokeDasharray={CIRC} strokeDashoffset={CIRC * (1 - shown / 100)} />
      </svg>
      <span className="gauge-val" aria-hidden="true">{shown}</span>
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
      <PageHeader trail="Analyse" title="Innovation Assessment">
        How strong your position is in a technology, and what each factor
        contributes to the score.
      </PageHeader>

      <form onSubmit={analyze} className="search-row">
        <input placeholder="Assess a technology, e.g. solid-state battery" maxLength={200}
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

function NextSteps({ data }) {
  const comm = data.commercialization
  const actions = comm?.recommendations?.length || 0

  return (
    <NextRow items={[
      { key: 'commercialization', title: 'Plan the route to market',
        note: comm?.pathway?.title
          ? `${comm.pathway.title} · ${plural(actions, 'recommended step')}`
          : 'What to do about this score' },
      { key: 'patents', title: 'See who is patenting',
        note: 'The themes running through the filings' },
    ]} />
  )
}

const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`

function Basis({ signals: s, query }) {
  const held = (s.portfolio_publications ?? 0) + (s.portfolio_patents ?? 0)
  const matched = s.own_publications + s.own_patents
  const skipped = held - matched

  if (matched === 0) {
    return held > 0 ? (
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
  const factors = [...data.components].sort((a, b) => b.weight - a.weight || b.score - a.score)
  const strongest = factors.reduce((best, c) => (c.score > best.score ? c : best))
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
        <BigScore value={data.innovation_score} rating={data.rating} />
        <div style={{ flex: 1 }}>
          <span className="rating-pill">{data.rating} potential</span>
          <p className="score-context"><Basis signals={s} query={data.query} /></p>
        </div>
      </div>

      <Card
        title="Where your score comes from"
        sub={`Each factor is scored out of 100, then counts for the share shown beneath it. `
          + `Together they make your ${data.innovation_score}.`}
      >
        <div className="factor-grid">
          {factors.map((c, i) => (
            <div key={c.key} className="factor">
              <Gauge value={c.score} delay={i * STEP_MS} />
              <span className="factor-name">
                {c.label}
                <InfoHint>{c.description}</InfoHint>
              </span>
              <span className="factor-share">{c.weight}% of the score</span>
            </div>
          ))}
        </div>
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
