import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  adminService, profileService, fundingService, innovationService,
  extractErrorMessage,
} from '../services/api'
import { useSession } from '../services/session'
import { isOwner, roleLabel } from '../roles'
import Loading from '../components/Loading'
import ToolCards from '../components/ToolCards'
import { StatCard, StatGrid, RankedList } from '../components/ui'
import { fmtAmount, fmtDeadline, fmtCount, fmtPct, eligUi } from '../components/ui/format'

const RELEVANCE_FLOOR = 25
const TOP_ROWS = 3

const OWNER_VIEW = {
  researcher: {
    lead: 'trends',
    getStarted: 'Create your research profile to unlock personalised funding '
      + 'recommendations, research trends and patent intelligence tailored to your work.',
    noIpNote: 'you publish but hold no IP',
  },
  startup_founder: {
    lead: 'market',
    getStarted: 'Create your profile to unlock funding opportunities, patent '
      + 'intelligence and a route to market for your technology.',
    noIpNote: 'nothing filed to protect it',
  },
}
const viewFor = (role) => OWNER_VIEW[role] || OWNER_VIEW.researcher

function InsightCard({ to, value, label, note }) {
  return (
    <Link to={to} className="insight-card">
      <span className="insight-value">{value}</span>
      <span className="insight-label">{label}</span>
      <span className="insight-note">{note}</span>
    </Link>
  )
}

function TechnologyInsights({ state, data, note, view }) {
  const thirdLabel = view.lead === 'market' ? 'Recommended next steps' : 'Research momentum'

  if (state === 'loading') {
    return (
      <div className="insight-row" aria-busy="true">
        {['Innovation score', 'Patents in this field', thirdLabel].map((l) => (
          <div key={l} className="insight-card is-waiting">
            <span className="insight-value">—</span>
            <span className="insight-label">{l}</span>
            <span className="insight-note">Reading your technology…</span>
          </div>
        ))}
      </div>
    )
  }

  if (state === 'unavailable') {
    return (
      <div className="card">
        <p className="empty-note">{note || 'Innovation analysis is unavailable right now.'}</p>
        <Link to="/portfolio" className="inline-link link-block">Open your portfolio →</Link>
      </div>
    )
  }

  const s = data.signals || {}
  const steps = (data.commercialization?.recommendations || [])
    .filter((r) => r.priority === 'now').length
  const growth = s.patent_history_reliable && s.patent_growth != null
    ? `${fmtPct(s.patent_growth, { sign: true })} over the decade` : null
  const busiest = s.busiest_year ? `busiest ${s.busiest_year}` : null

  return (
    <div className="insight-row">
      <InsightCard
        to="/innovation"
        value={data.innovation_score}
        label="Innovation score"
        note={`${data.rating} potential · ${data.query}`}
      />
      <InsightCard
        to="/patents"
        value={fmtCount(s.patent_total)}
        label="Patents in this field"
        note={[growth, busiest].filter(Boolean).join(' · ') || 'filing history not measurable'}
      />
      {view.lead === 'market' ? (
        <InsightCard
          to="/commercialization"
          value={steps}
          label={`Recommended next step${steps === 1 ? '' : 's'}`}
          note={data.commercialization?.pathway?.title || 'route to market'}
        />
      ) : (
        <InsightCard
          to="/trends"
          value={s.research_growth == null ? '—' : fmtPct(s.research_growth, { sign: true })}
          label="Research momentum"
          note={s.research_growth == null
            ? 'publication growth not measurable'
            : 'publication growth in this field'}
        />
      )}
    </div>
  )
}

function BaseDashboard({ user }) {
  const [profile, setProfile] = useState(null)
  const [recs, setRecs] = useState([])
  const [noProfile, setNoProfile] = useState(false)
  const [ready, setReady] = useState(false)
  const [insight, setInsight] = useState(null)
  const [insightState, setInsightState] = useState('loading')
  const [insightNote, setInsightNote] = useState('')
  const view = viewFor(user.role)

  useEffect(() => {
    Promise.allSettled([
      profileService.get(),
      fundingService.recommendations({ limit: 50 }),
    ]).then(([p, r]) => {
      if (p.status === 'fulfilled') setProfile(p.value.data)
      else setNoProfile(true)
      if (r.status === 'fulfilled') setRecs(r.value.data)
      setReady(true)
    })
  }, [])

  useEffect(() => {
    innovationService.myAssessment()
      .then((res) => { setInsight(res.data); setInsightState('ready') })
      .catch((err) => {
        setInsightState('unavailable')
        setInsightNote(err.response?.status === 400
          ? extractErrorMessage(err, '')
          : 'Innovation analysis is unavailable right now.')
      })
  }, [])

  if (!ready) return <Loading message="Loading your dashboard…" />

  if (noProfile) {
    return (
      <div className="dashboard">
        <div className="hero">
          <h1>Welcome, {user.full_name}</h1>
          <div className="hero-sub">
            <span className="role-badge">{roleLabel(user.role)}</span>
            {user.organization && <span>{user.organization}</span>}
          </div>
          <div className="hero-accent" />
          <p className="hero-lead">{view.getStarted}</p>
          <div className="hero-cta">
            <Link to="/portfolio"><button>Set up your portfolio →</button></Link>
          </div>
        </div>
        <p className="section-label" style={{ marginTop: 26 }}>Explore the platform</p>
        <ToolCards />
      </div>
    )
  }

  const topMatch = recs.length ? Math.round(recs[0].relevance_score) : null
  const eligibleCount = recs.filter((r) => r.eligibility === 'eligible').length
  const unconfirmedCount = recs.filter((r) => r.eligibility === 'unconfirmed').length
  const pubCount = profile?.publications?.length || 0
  const patCount = profile?.patents?.length || 0

  const topRecs = recs.slice(0, TOP_ROWS)
  const weakOnly = recs.length > 0 && recs[0]?.relevance_score < RELEVANCE_FLOOR

  const checks = [
    { label: 'Research domains added', done: (profile?.research_domains?.length || 0) > 0 },
    { label: 'Keywords added', done: (profile?.keywords?.length || 0) > 0 },
    { label: 'Technology areas added', done: (profile?.technology_areas?.length || 0) > 0 },
    { label: 'Publication imported', done: pubCount > 0 },
    { label: 'Patent imported', done: patCount > 0 },
  ]
  const completeness = Math.round((checks.filter((c) => c.done).length / checks.length) * 100)

  const termCounts = [
    [profile?.research_domains?.length || 0, 'domain', 'domains'],
    [profile?.keywords?.length || 0, 'keyword', 'keywords'],
    [profile?.technology_areas?.length || 0, 'technology area', 'technology areas'],
  ].map(([n, one, many]) => `${n} ${n === 1 ? one : many}`)

  return (
    <div className="dashboard">
      <div className="hero">
        <h1>Welcome back, {user.full_name}</h1>
        <div className="hero-sub">
          <span className="role-badge">{roleLabel(user.role)}</span>
          {profile?.organization && <span>{profile.organization}</span>}
          {profile?.country && <span>· {profile.country}</span>}
        </div>
        <div className="hero-accent" />
      </div>

      <StatGrid>
        <StatCard
          value={topMatch == null ? '—' : `${topMatch}%`}
          label="Best funding match"
          note={recs[0]?.opportunity?.agency}
        />
        <StatCard
          value={eligibleCount}
          label="Eligible grants"
          note={unconfirmedCount > 0
            ? `${unconfirmedCount} more once your country is set`
            : undefined}
        />
        <StatCard value={pubCount} label="Publications" />
        <StatCard
          value={patCount}
          label="Patents"
          note={pubCount > 0 && patCount === 0 ? view.noIpNote : undefined}
        />
      </StatGrid>

      <p className="section-label">Your technology at a glance</p>
      <TechnologyInsights state={insightState} data={insight} note={insightNote} view={view} />

      <div className="dash-grid" style={{ marginTop: 22 }}>
        <div className="card">
          <div className="card-head">
            <h2>Top funding matches</h2>
            <Link to="/funding" className="inline-link">View all →</Link>
          </div>
          <p className="card-sub">Ranked against your research profile</p>
          {topRecs.length === 0 ? (
            <p className="empty-note">
              No matches yet — add domains or keywords to your portfolio.
            </p>
          ) : (
            <>
              {topRecs.map((r) => {
                const opp = r.opportunity
                const facts = [
                  fmtAmount(opp.amount_min, opp.amount_max, opp.currency),
                  fmtDeadline(opp.deadline),
                  eligUi(r.eligibility).label,
                ].filter(Boolean)
                return (
                  <div key={opp.id} className="match-row">
                    <div style={{ minWidth: 0 }}>
                      <div className="m-title">{opp.title}</div>
                      <div className="m-agency">{opp.agency}</div>
                      <div className="match-meta">{facts.join(' · ')}</div>
                    </div>
                    <div className="match-score">
                      <span className="score-pill">{Math.round(r.relevance_score)}%</span>
                    </div>
                  </div>
                )
              })}
              {weakOnly && (
                <p className="empty-note">
                  Nothing matched closely. Adding domains and keywords sharpens the ranking.
                </p>
              )}
            </>
          )}
        </div>

        <div className="card">
          <div className="card-head">
            <h2>Profile strength</h2>
            <Link to="/portfolio" className="inline-link">Edit →</Link>
          </div>
          <p className="muted">{completeness}% complete</p>
          <div className="meter"><div className="meter-fill" style={{ width: `${completeness}%` }} /></div>
          <ul className="check-list">
            {checks.map((c) => (
              <li key={c.label}>
                <span className={c.done ? 'done' : 'todo'}>{c.done ? '✓' : '○'}</span>
                <span className={c.done ? '' : 'muted'}>{c.label}</span>
              </li>
            ))}
          </ul>

          <div className="profile-foot">
            <p className="profile-driving">
              Feeding your analysis:{' '}
              {termCounts.map((text, i) => (
                <span key={text}>
                  {i > 0 && <span className="term-sep"> · </span>}
                  <span className="term-count">{text}</span>
                </span>
              ))}
            </p>
            {!profile?.country && unconfirmedCount > 0 ? (
              <p className="profile-gap">
                No country set, so {unconfirmedCount} grants stay unconfirmed.
                <Link to="/profile" className="inline-link link-block">
                  Add it in your profile →
                </Link>
              </p>
            ) : (
              <p className="profile-gap">
                Rankings refresh from these terms every time you open a tool.
              </p>
            )}
          </div>
        </div>
      </div>

      <p className="section-label" style={{ marginTop: 26 }}>Explore the platform</p>
      <ToolCards />
    </div>
  )
}

function PipelineAnalytics({ stats }) {
  if (!stats) return null
  const { technologies, funding, innovators, portfolios_with_focus: listed } = stats
  const spread = technologies.length > 1
    && technologies[0].users > technologies[technologies.length - 1].users
  const tie = technologies[0]?.users

  return (
    <div className="dash-grid" style={{ marginTop: 20 }}>
      <div className="card">
        <div className="card-head">
          <h2>Technology focus</h2>
          <Link to="/technology" className="inline-link">Analyse a field →</Link>
        </div>
        <p className="card-sub">
          {listed === 0
            ? 'No portfolio names a technology area yet'
            : `Named by ${listed} of the ${innovators} monitored innovators`}
        </p>
        {technologies.length === 0 ? (
          <p className="empty-note">
            Nothing to analyse yet — a technology area is what the patent and
            innovation tools run on.
          </p>
        ) : (
          <>
            <RankedList items={technologies} labelKey="name" valueKey="users"
                        bars={spread} />
            {!spread && technologies.length > 1 && (
              <p className="chart-foot">
                All {technologies.length} are named by {tie} portfolio
                {tie === 1 ? '' : 's'} each, so the order is not a ranking.
              </p>
            )}
          </>
        )}
      </div>

      <div className="card">
        <div className="card-head">
          <h2>Funding available</h2>
          <Link to="/funding" className="inline-link">Browse →</Link>
        </div>
        <ul className="metric-rows">
          <li>
            <span className="metric-label">Open opportunities</span>
            <span className="metric-value">{funding.opportunities}</span>
          </li>
          <li>
            <span className="metric-label">Funding agencies</span>
            <span className="metric-value">{funding.agencies}</span>
          </li>
          <li>
            <span className="metric-label">Total on offer</span>
            <span className="metric-value">
              {fmtAmount(null, funding.total_available, 'USD')}
            </span>
            <span className="metric-note">
              across {funding.priced} awards that state a ceiling
            </span>
          </li>
        </ul>
        <p className="chart-foot">
          {funding.closed > 0 && `${funding.closed} closed grant${funding.closed === 1
            ? ' is' : 's are'} left out — past their deadline, so open to nobody. `}
          {funding.top_agencies.length > 0
            ? `Most active: ${funding.top_agencies.map((a) => `${a.name} (${a.count})`).join(', ')}.`
            : `Spread across ${funding.agencies} funders, so no single agency dominates.`}
        </p>
      </div>
    </div>
  )
}

function focusCell(entry) {
  if (!entry) return <span className="muted">No portfolio</span>
  if (entry.focus.length === 0) return <span className="muted">No technology area</span>
  const [first, ...rest] = entry.focus
  return (
    <span className="focus-cell" title={entry.focus.join(', ')}>
      {first}
      {rest.length > 0 && <span className="muted"> +{rest.length}</span>}
    </span>
  )
}

function matchCell(entry) {
  const best = entry?.best_match
  if (!entry) return <span className="cell-note">—</span>
  if (!best) return <span className="cell-note">nothing matched</span>
  const tone = eligUi(best.eligibility)
  return (
    <span className="match-cell" title={`${best.title} · ${tone.label}`}>
      <span className="score-pill">{Math.round(best.score)}%</span>
      <span className="muted">{best.agency}</span>
    </span>
  )
}

function ManagerDashboard({ user }) {
  const [users, setUsers] = useState([])
  const [error, setError] = useState('')
  const [stats, setStats] = useState(null)

  useEffect(() => {
    adminService.listUsers()
      .then((res) => setUsers(res.data.filter((u) => isOwner(u.role))))
      .catch(() => setError('Failed to load innovation pipeline'))
    adminService.pipelineStats().then((res) => setStats(res.data))
      .catch(() => setError('Could not load pipeline analytics.'))
  }, [])

  const researchers = users.filter((u) => u.role === 'researcher').length
  const founders = users.filter((u) => u.role === 'startup_founder').length
  const roster = new Map((stats?.roster || []).map((r) => [r.user_id, r]))
  const ranked = [...users].sort((a, b) => {
    const sa = roster.get(a.id)?.best_match?.score ?? -1
    const sb = roster.get(b.id)?.best_match?.score ?? -1
    if (sb !== sa) return sb - sa
    return (roster.has(b.id) ? 1 : 0) - (roster.has(a.id) ? 1 : 0)
  })

  return (
    <div className="dashboard">
      <div className="hero">
        <h1>Innovation Pipeline</h1>
        <div className="hero-sub">
          <span className="role-badge">{roleLabel(user.role)}</span>
        </div>
        <div className="hero-accent" />
      </div>
      {error && <div className="error">{error}</div>}

      <StatGrid>
        <StatCard
          value={users.length}
          label="Monitored innovators"
          note={`${researchers} researcher${researchers === 1 ? '' : 's'} · `
                + `${founders} founder${founders === 1 ? '' : 's'}`}
        />
        <StatCard value={stats ? stats.with_profile : '—'} label="With a portfolio" />
        <StatCard
          value={stats ? stats.portfolios_with_focus : '—'}
          label="Ready to analyse"
          note="a technology area is set"
        />
      </StatGrid>

      <PipelineAnalytics stats={stats} />

      <div className="card" style={{ marginTop: 20 }}>
        <div className="card-head">
          <h2>Monitored Innovators</h2>
        </div>
        <p className="card-sub">
          Every researcher and founder on the platform, strongest funding match first
          {stats?.attention?.no_portfolio ? ` · ${stats.attention.no_portfolio} not set up yet` : ''}
        </p>
        <div className="table-wrap">
          <table className="user-table">
            <thead>
              <tr><th>Name</th><th>Type</th><th>Focus</th><th>Best match</th><th>Detail</th></tr>
            </thead>
            <tbody>
              {ranked.map((u) => (
                <tr key={u.id}>
                  <td>
                    <Link to={`/innovator/${u.id}`} className="row-name">
                      {u.full_name}
                    </Link>
                    <span className="cell-note row-sub">{u.email}</span>
                  </td>
                  <td>
                    <span className="role-badge" style={u.role === 'startup_founder' ? { background: 'var(--info-soft)', color: 'var(--info)' } : {}}>
                      {u.role === 'researcher' ? 'Researcher' : 'Founder'}
                    </span>
                  </td>
                  <td>{focusCell(roster.get(u.id))}</td>
                  <td>{matchCell(roster.get(u.id))}</td>
                  <td className="row-actions">
                    <Link to={`/innovator/${u.id}`} className="mini-view">Open →</Link>
                  </td>
                </tr>
              ))}
              {ranked.length === 0 && (
                <tr><td colSpan={5} className="cell-note">
                  No researcher or founder has registered yet.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function RecommendationMonitor({ stats, health }) {
  if (!stats) return null
  return (
    <>
      <div className="dash-grid dash-grid-even">
        <UserReach stats={stats} />
        <FundingInventory stats={stats} />
      </div>
      <SourceHealth health={health} />
    </>
  )
}

function SourceHealth({ health }) {
  if (health === null) {
    return (
      <div className="card">
        <div className="card-head"><h2>Data &amp; sources</h2></div>
        <p className="muted">Loading…</p>
      </div>
    )
  }
  if (health.unavailable) {
    return (
      <div className="card">
        <div className="card-head"><h2>Data &amp; sources</h2></div>
        <p className="empty-note">
          The cache could not be read, so what is stored is unknown. The two cards
          beside this one are unaffected — they come from the database.
        </p>
        <Link to="/admin/sources" className="inline-link link-block">Sources →</Link>
      </div>
    )
  }
  const { cached, sources, gaps } = health
  const missingKey = (sources || []).filter((s) => s.needs_key && !s.configured)
  const named = cached.named_by_a_portfolio
  const uncached = cached.unseeded_but_named

  return (
    <div className="card">
      <div className="card-head">
        <h2>Data &amp; sources</h2>
        <Link to="/admin/sources" className="inline-link">Sources →</Link>
      </div>
      <p className="ip-finding">
        {uncached > 0
          ? <><strong>{uncached} of {named} technology areas</strong> named by a
              portfolio have nothing cached behind them.</>
          : <><strong>All {named} technology areas</strong> named by a portfolio have
              data cached behind them.</>}
      </p>
      <dl className="fact-list">
        <div><dt>Topics cached</dt><dd>{cached.total}</dd></div>
        <div><dt>With a measured field size</dt><dd>{cached.with_corpus}</dd></div>
        <div><dt>Sources connected</dt><dd>{sources?.length ?? '—'}</dd></div>
      </dl>

      {gaps?.length > 0 && (
        <p className="chart-foot">
          <strong>Named but not cached:</strong>{' '}
          {gaps.slice(0, 4).join(', ')}
          {gaps.length > 4 && ` and ${gaps.length - 4} more`}.
        </p>
      )}

      <p className="chart-foot">
        {missingKey.length > 0
          ? `${missingKey.map((s) => s.name).join(' and ')} has no key set, so anything `
            + 'that needs it falls back to a coarser source.'
          : 'Every source that needs a key has one.'}
        {uncached > 0 && ' An uncached field is why its analysis page can come back '
          + 'empty — it fills the first time anyone opens it.'}
      </p>
    </div>
  )
}

function UserReach({ stats }) {
  const { population, accounts, matching } = stats
  const segments = [
    ['Can act on a match', matching.strong],
    ['Weak matches only', matching.weak_only],
    ['Nothing matched', matching.none],
    ['No portfolio', population.without_profile],
  ].filter(([, n]) => n > 0)
  const covered = segments.reduce((n, [, count]) => n + count, 0)
  const complete = covered === population.total && population.total > 0

  return (
    <div className="card">
      <div className="card-head">
        <h2>Recommendation reach</h2>
        <Link to="/admin" className="inline-link">Accounts →</Link>
      </div>
      <p className="ip-finding">
        <strong>{matching.strong} of {population.total} {population.label}</strong>{' '}
        {matching.strong === 1 ? 'has' : 'have'} a funding match worth acting on, at{' '}
        {matching.threshold}% relevance or better.{' '}
        {population.without_profile > 0 && (
          <><strong>{population.without_profile}</strong>{' '}
            {population.without_profile === 1 ? 'has' : 'have'} not built a portfolio, so
            there is nothing to score them against.</>
        )}
      </p>

      {segments.length > 0 && (
        <>
          {complete && (
            <div className="share-strip" role="img"
                 aria-label={segments.map(([k, n]) => `${n} ${k}`).join(', ')}>
              {segments.map(([kind, n], i) => (
                <span key={kind} className={`share-seg share-seg-${i}`}
                      style={{ width: `${(n / population.total) * 100}%` }} />
              ))}
            </div>
          )}
          <ul className="share-legend">
            {segments.map(([kind, n], i) => (
              <li key={kind}>
                <span className={`share-dot share-seg-${i}`} aria-hidden="true" />
                <strong>{n}</strong> {kind}
              </li>
            ))}
          </ul>
          {!complete && (
            <p className="chart-foot">
              These {covered} do not account for all {population.total}{' '}
              {population.label}, so they are listed rather than shown as a split.
            </p>
          )}
        </>
      )}

      <p className="chart-foot">
        {matching.median_best_match != null
          ? (matching.median_population === 1
              ? `The one owner with a match scores ${matching.median_best_match}%. `
              : `Median best match among the ${matching.median_population} who matched `
                + `at all: ${matching.median_best_match}%. `)
          : 'Nobody with a portfolio has matched a grant yet. '}
        {population.with_technology_area} of the {population.with_profile} with a
        portfolio {population.with_technology_area === 1 ? 'has' : 'have'} set a
        technology area, which is what the patent and innovation modules run on.
        The other {accounts.staff} accounts are staff, who own no portfolio by design.
      </p>
    </div>
  )
}

function FundingInventory({ stats }) {
  const { matching, opportunities, eligibility, population } = stats
  return (
    <div className="card">
      <div className="card-head">
        <h2>Funding inventory</h2>
        <Link to="/admin/funding" className="inline-link">Catalogue →</Link>
      </div>
      <p className="ip-finding">
        <strong>{opportunities.unreachable} of {opportunities.total} grants</strong>{' '}
        reach nobody on the platform at {matching.threshold}% or better.
      </p>
      <ul className="metric-rows">
        <li>
          <span className="metric-label">Matched to someone</span>
          <span className="metric-value">{opportunities.reachable}</span>
        </li>
        <li>
          <span className="metric-label">Reaching nobody</span>
          <span className="metric-value">{opportunities.unreachable}</span>
        </li>
      </ul>

      {eligibility.length > 0 && (
        <>
          <h3 className="metric-group">Strong matches, by eligibility</h3>
          <ul className="metric-rows">
            {eligibility.map((e) => (
              <li key={e.status}>
                <span className="metric-label">{e.status}</span>
                <span className="metric-value">{e.count}</span>
              </li>
            ))}
          </ul>
        </>
      )}

      <p className="chart-foot">
        A grant goes unreached when nobody scores against it. There are{' '}
        {population.with_profile} portfolios to score, so the catalogue is ahead of
        the audience rather than mismatched to it.
        {eligibility.length > 0 && ' A match is one owner against one grant, so the '
          + 'eligibility figures count pairs rather than grants.'}
      </p>
    </div>
  )
}

function AdminDashboard({ user }) {
  const [stats, setStats] = useState(null)
  const [health, setHealth] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    adminService.dataHealth().then((res) => setHealth(res.data))
      .catch(() => setHealth({ cached: {}, sources: [], gaps: [], unavailable: true }))
  }, [])

  useEffect(() => {
    adminService.recommendationStats().then((res) => setStats(res.data))
      .catch(() => setError('Platform analytics are unavailable right now.'))
  }, [])

  return (
    <div className="dashboard">
      <div className="hero">
        <h1>Platform Overview</h1>
        <div className="hero-sub">
          <span className="role-badge">{roleLabel(user.role)}</span>
          {user.is_superuser && <span className="super-tag">Super</span>}
        </div>
        <div className="hero-accent" />
        <div className="hero-cta">
          <Link to="/admin"><button>Open Admin Panel →</button></Link>
        </div>
      </div>

      <StatGrid>
        <StatCard value={stats ? stats.accounts.total : '—'} label="Accounts" />
        <StatCard value={stats ? stats.accounts.owners : '—'}
                  label="Portfolio owners"
                  note="who the recommendation engine is for" />
        <StatCard value={stats ? stats.accounts.staff : '—'} label="Staff"
                  note="own no portfolio by design" />
      </StatGrid>

      {error && <div className="error">{error}</div>}
      <RecommendationMonitor stats={stats} health={health} />
    </div>
  )
}

export default function Dashboard() {
  const { user, role, verified } = useSession()

  if (!user?.email && !verified) return <Loading message="Loading your dashboard…" />
  if (role === 'innovation_manager') return <ManagerDashboard user={user} />
  if (role === 'admin') return <AdminDashboard user={user} />
  return <BaseDashboard user={user} />
}
