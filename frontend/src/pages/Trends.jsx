import { useEffect, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts'
import { trendsService, authService, extractErrorMessage } from '../services/api'
import Loading from '../components/Loading'
import FieldChips from '../components/FieldChips'
import OwnFieldNote from '../components/OwnFieldNote'
import { useSession } from '../services/session'
import { PageHeader, Card, StatCard, StatGrid, RankedList } from '../components/ui'
import {
  CHART_COLORS, axisProps, gridProps, tooltipProps, compactNumber, seriesProps,
  areaGradient, pointLabel,
} from '../components/ui/chartTheme'
import { fmtCount } from '../components/ui/format'
import NextRow from '../components/NextRow'

const share = (n) => (n == null ? '—' : `${n}%`)

export default function Trends() {
  const [query, setQuery] = useState('')
  const [fields, setFields] = useState([])
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [noOwnField, setNoOwnField] = useState(false)
  const navigate = useNavigate()
  const { role } = useSession()

  useEffect(() => {
    trendsService.myDomain()
      .then((res) => { setData(res.data); setQuery(res.data.query); setFields(res.data.profile_fields || []) })
      .catch((err) => {
        if (err.response?.status === 401) { authService.logout(); navigate('/login') }
        else if (err.response?.status === 400) setNoOwnField(true)
        else setError(extractErrorMessage(err, 'Could not load trends'))
      })
      .finally(() => setLoading(false))
  }, [navigate])

  const analyze = async (e, term) => {
    e?.preventDefault()
    const q = (term ?? query).trim()
    if (q.length < 2) return
    setQuery(q); setLoading(true); setError('')
    try {
      const res = await trendsService.analyze(q)
      setData(res.data)
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not load trends'))
    } finally {
      setLoading(false)
    }
  }

  const rising = data?.emerging_topics || []
  const leader = rising[0]
  const win = data?.emerging_window

  return (
    <div className="dashboard">
        <PageHeader trail="Discover" title="Research Trends">
          How much your field publishes, what is rising, and the work everyone cites.
        </PageHeader>

        <form onSubmit={analyze} className="search-row">
          <input placeholder="Explore a research topic, e.g. quantum computing"
                 aria-label="Research topic" maxLength={200}
                 value={query} onChange={(e) => setQuery(e.target.value)} />
          <button type="submit">Analyse</button>
        </form>
        <FieldChips fields={fields} active={data?.query} onPick={(f) => analyze(null, f)}
                    label="Your domains and keywords" />

        {error && <div className="error">{error}</div>}
        {loading && <Loading message="Reading the research landscape…" />}

        {!loading && !data && (
          <Card>
            <OwnFieldNote
              role={role}
              verb="explore"
              detail={noOwnField
                ? 'Search a topic above, or add research domains to your portfolio '
                  + 'and this page will follow your own field automatically.'
                : undefined}
            />
          </Card>
        )}

        {!loading && data && (
          <>
            <StatGrid>
              <StatCard
                value={fmtCount(data.total_works)}
                label="Publications"
                note="OpenAlex"
                hint="Papers with this phrase in the title or abstract. Full-text search
                      returns several times as many, mostly passing mentions."
              />
              <StatCard
                value={data.recent_share != null ? `${data.recent_share}%` : '—'}
                label={`Published since ${data.recent_from_year}`}
                note={data.recent_works != null
                  ? `${fmtCount(data.recent_works)} of ${fmtCount(data.total_works)} papers`
                  : undefined}
                hint="A high share means the field is accelerating — most of what exists
                      was written recently."
              />
              <StatCard
                value={leader ? `+${leader.growth}%` : '—'}
                label="Fastest-rising topic"
                note={leader
                  ? `${leader.topic} · ${share(leader.earlier_share)} → ${share(leader.recent_share)} of publications`
                  : 'no topic is gaining share'}
              />
            </StatGrid>

            <Card title="Publications per year"
                  sub="How much is published on this subject each year">
              <ResponsiveContainer width="100%" height={290}>
                <AreaChart data={data.works_by_year} margin={{ top: 18, right: 12, left: 0, bottom: 0 }}>
                  <defs>{areaGradient('worksFill', CHART_COLORS.research)}</defs>
                  <CartesianGrid {...gridProps} />
                  <XAxis dataKey="year" {...axisProps} />
                  <YAxis tickFormatter={compactNumber} width={52} {...axisProps} />
                  <Tooltip {...tooltipProps}
                           formatter={(v) => [v.toLocaleString('en-US'), 'Publications']} />
                  <Area dataKey="count" fill="url(#worksFill)" fillOpacity={1}
                        {...seriesProps(CHART_COLORS.research)}
                        label={pointLabel({ data: data.works_by_year, dataKey: 'count' })} />
                </AreaChart>
              </ResponsiveContainer>
              <p className="chart-foot">
                The current year is left out — it is still being counted, so it would
                draw as a fall.
              </p>
            </Card>

            <Card title="The biggest topics in this field"
                  sub="Share of publications touching each topic">
              <RankedList items={data.hotspots} labelKey="topic" valueKey="count"
                          shareKey="share" />
              <p className="chart-foot">
                A paper usually carries two topics, so these shares overlap and do not
                add to 100%.
              </p>
            </Card>

            <Card
              title="Topics gaining ground"
              sub={win
                ? `Share of publications since ${win.recent_from}, against ${win.earlier_from}–${String(win.earlier_to).slice(2)}`
                : 'Rising share of publications'}
            >
              {rising.length === 0 ? (
                <p className="empty-note">No topic is measurably gaining share here.</p>
              ) : (
                <>
                  <ol className="ranked">
                    {rising.map((t) => (
                      <li key={t.topic} className="rising-row">
                        <span className="ranked-label" title={t.topic}>{t.topic}</span>
                        <span className="rise-shares">
                          <span className="rise-was">{share(t.earlier_share)}</span>
                          <span className="rise-arrow" aria-hidden="true">→</span>
                          <span className="rise-now">{share(t.recent_share)}</span>
                        </span>
                      </li>
                    ))}
                  </ol>
                  <p className="chart-foot">
                    The two periods do not overlap, so a rise is a real shift, not the
                    recent years counted twice.
                  </p>
                </>
              )}
            </Card>

            <Card title="The most-cited work in this field">
              {data.top_papers.map((p, i) => (
                <div key={i} className="entry" style={{ display: 'block' }}>
                  <a href={p.url} target="_blank" rel="noreferrer" className="opp-title"
                     style={{ fontSize: 14 }}>{p.title}</a>
                  <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
                    {[p.venue, p.year, `${p.cited_by_count.toLocaleString('en-US')} citations`]
                      .filter(Boolean).join(' · ')}
                  </div>
                </div>
              ))}
            </Card>

            <NextRow items={[
              { key: 'technology', title: 'Check where this sits',
                note: 'Early research or already industrial' },
              { key: 'patents', title: 'See who is patenting',
                note: 'The themes running through the filings' },
            ]} />
          </>
        )}
    </div>
  )
}
