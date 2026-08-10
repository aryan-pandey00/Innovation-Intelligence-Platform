import { useEffect, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { authService, adminService, profileService, fundingService } from '../services/api'
import Loading from '../components/Loading'
import ProfileDetail from '../components/ProfileDetail'
import ToolCards from '../components/ToolCards'
import { StatCard, StatGrid } from '../components/ui'
import { fmtAmount, fmtDeadline, eligUi } from '../components/ui/format'

const ROLE_TITLES = {
  researcher: 'Researcher',
  startup_founder: 'Startup Founder',
  innovation_manager: 'Innovation Manager',
  admin: 'Administrator',
}

// A relevance floor, so a 13% match is not presented as a top recommendation —
// `slice(0, 4)` padded the list regardless of quality. It decides only whether
// *nothing* matched closely; marking individual rows made the card look like it
// was apologising for its own third recommendation.
const RELEVANCE_FLOOR = 25
const TOP_ROWS = 3

function BaseDashboard({ user }) {
  const [profile, setProfile] = useState(null)
  const [recs, setRecs] = useState([])
  const [noProfile, setNoProfile] = useState(false)
  const [ready, setReady] = useState(false)

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

  if (!ready) return <Loading message="Loading your dashboard…" />

  if (noProfile) {
    return (
      <div className="dashboard">
        <div className="hero">
          <h1>Welcome, {user.full_name}</h1>
          <div className="hero-sub">
            <span className="role-badge">{ROLE_TITLES[user.role]}</span>
            {user.organization && <span>{user.organization}</span>}
          </div>
          <div className="hero-accent" />
          <div className="hero-cta">
            <Link to="/portfolio"><button>Set up your portfolio →</button></Link>
          </div>
        </div>
        <div className="card">
          <h2>Get started</h2>
          <p className="muted">
            Create your research profile to unlock personalized funding recommendations,
            research trends, and patent intelligence tailored to your work.
          </p>
        </div>
        <p className="section-label" style={{ marginTop: 26 }}>Explore the platform</p>
        <ToolCards />
      </div>
    )
  }

  const topMatch = recs.length ? Math.round(recs[0].relevance_score) : null
  // Only confirmed eligibility counts here. Previously grants whose country
  // requirement had never been checked were counted as eligible, which inflated
  // this number with opportunities nobody had verified.
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

  // What "100% complete" actually amounts to. A tick beside "Keywords added"
  // says one was added; this says how many there are, and it moves when the
  // portfolio does.
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
          <span className="role-badge">{ROLE_TITLES[user.role]}</span>
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
          note={pubCount > 0 && patCount === 0 ? 'you publish but hold no IP' : undefined}
        />
      </StatGrid>

      <div className="dash-grid">
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
              {/* Three rows, styled identically. The percentage is already the
                  ranking — a second signal on the same row said it twice. */}
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
                      {/* the facts that make a row a decision rather than a name */}
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

          {/* Once every box is ticked the card ran out of things to say. These two
              questions a finished profile still has to answer both read from data
              already on this page, so neither is padding. */}
          <div className="profile-foot">
            <p className="profile-driving">
              Feeding your analysis:{' '}
              {/* Each count is one unbreakable unit. Left to wrap freely the line
                  broke after "1" and left "technology area" stranded below. */}
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
                {/* Its own line: a call to action split across two lines reads as
                    two half-links rather than one thing to click. */}
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

function ManagerDashboard({ user }) {
  const [users, setUsers] = useState([])
  const [selected, setSelected] = useState(null)
  const [profileMsg, setProfileMsg] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    adminService.listUsers()
      .then((res) => setUsers(res.data.filter((u) => u.role === 'researcher' || u.role === 'startup_founder')))
      .catch(() => setError('Failed to load innovation pipeline'))
  }, [])

  const viewProfile = async (u) => {
    setSelected(null); setProfileMsg('Loading profile…')
    try {
      const res = await adminService.getUserProfile(u.id)
      setSelected({ user: u, profile: res.data }); setProfileMsg('')
    } catch (err) {
      if (err.response?.status === 404) { setSelected({ user: u, profile: null }); setProfileMsg('') }
      else setProfileMsg('Could not load profile.')
    }
  }

  const researchers = users.filter((u) => u.role === 'researcher').length
  const founders = users.filter((u) => u.role === 'startup_founder').length

  return (
    <div className="dashboard" style={{ maxWidth: 1200 }}>
      <div className="hero">
        <h1>Innovation Pipeline</h1>
        <div className="hero-sub">
          <span className="role-badge">{ROLE_TITLES[user.role]}</span>
          <span>Monitoring {users.length} innovators</span>
        </div>
        <div className="hero-accent" />
      </div>
      {error && <div className="error">{error}</div>}

      <div className="stat-grid">
        <div className="stat-card"><span className="stat-num">{users.length}</span>Monitored Innovators</div>
        <div className="stat-card"><span className="stat-num">{researchers}</span>Researchers</div>
        <div className="stat-card"><span className="stat-num">{founders}</span>Startup Founders</div>
      </div>

      <div className="dash-grid">
        <div className="card">
          <h2>Monitored Innovators</h2>
          <div className="table-wrap">
            <table className="user-table">
              <thead>
                <tr><th>Name</th><th>Type</th><th>Organisation</th><th>Action</th></tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id}>
                    <td><strong>{u.full_name}</strong><br /><span className="muted" style={{ fontSize: 12 }}>{u.email}</span></td>
                    <td>
                      <span className="role-badge" style={u.role === 'startup_founder' ? { background: 'var(--info-soft)', color: 'var(--info)' } : {}}>
                        {u.role === 'researcher' ? 'Researcher' : 'Founder'}
                      </span>
                    </td>
                    <td>{u.organization || '—'}</td>
                    <td><button className="mini-view" onClick={() => viewProfile(u)}>View Portfolio</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <div>
          {profileMsg && <div className="card"><p className="muted">{profileMsg}</p></div>}
          {selected && (
            <div className="card">
              <h2>{selected.user.full_name}'s Portfolio</h2>
              <p className="muted">{ROLE_TITLES[selected.user.role]} · {selected.user.email}</p>
              {selected.profile ? <ProfileDetail p={selected.profile} />
                : <p className="muted" style={{ marginTop: 16 }}>This user has not created a research profile yet.</p>}
            </div>
          )}
          {!selected && !profileMsg && (
            <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 200 }}>
              <p className="muted">Select an innovator to inspect their research profile.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function AdminDashboard({ user }) {
  const [users, setUsers] = useState([])

  useEffect(() => {
    adminService.listUsers().then((res) => setUsers(res.data)).catch(() => {})
  }, [])

  const count = (role) => users.filter((u) => u.role === role).length

  return (
    <div className="dashboard">
      <div className="hero">
        <h1>Platform Overview</h1>
        <div className="hero-sub">
          <span className="role-badge">{ROLE_TITLES[user.role]}</span>
          <span>{users.length} registered users</span>
        </div>
        <div className="hero-accent" />
        <div className="hero-cta">
          <Link to="/admin"><button>Open Admin Panel →</button></Link>
        </div>
      </div>

      <div className="stat-grid">
        <div className="stat-card"><span className="stat-num">{users.length}</span>Total Users</div>
        <div className="stat-card"><span className="stat-num">{count('researcher')}</span>Researchers</div>
        <div className="stat-card"><span className="stat-num">{count('startup_founder')}</span>Startup Founders</div>
        <div className="stat-card"><span className="stat-num">{count('innovation_manager')}</span>Innovation Managers</div>
      </div>
    </div>
  )
}

export default function Dashboard() {
  const [user, setUser] = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    authService.getMe()
      .then((res) => setUser(res.data))
      .catch(() => { authService.logout(); navigate('/login') })
  }, [navigate])

  if (!user) return <Loading message="Loading your dashboard…" />
  if (user.role === 'innovation_manager') return <ManagerDashboard user={user} />
  if (user.role === 'admin') return <AdminDashboard user={user} />
  return <BaseDashboard user={user} />
}
