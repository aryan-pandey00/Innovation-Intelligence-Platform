import { useEffect, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { fundingService, authService, extractErrorMessage } from '../services/api'
import Loading from '../components/Loading'
import EmptyState from '../components/EmptyState'
import { PageHeader } from '../components/ui'
import { useSession } from '../services/session'
import { isOwner } from '../roles'
import { ELIG_UI, SOURCE_LABELS, fmtAmount, fmtDeadline } from '../components/ui/format'

function OpportunityCard({ opp, score, eligibility, matched, reasons }) {
  const amount = fmtAmount(opp.amount_min, opp.amount_max, opp.currency)
  const elig = ELIG_UI[eligibility] || ELIG_UI.unconfirmed
  return (
    <div className="opp-card">
      <div className="opp-head">
        <div>
          <a href={opp.url} target="_blank" rel="noreferrer" className="opp-title">{opp.title}</a>
          {opp.live && <span className="live-badge">● {opp.source_label}</span>}
          {opp.awarded && <span className="awarded-tag">Past award</span>}
          <div className="muted">{opp.agency}</div>
        </div>
        {score != null && (
          <div className={`score-pill ${eligibility === 'ineligible' ? 'score-ineligible' : ''}`}>
            {Math.round(score)}% match
          </div>
        )}
      </div>

      <p className="opp-desc">{opp.description}</p>

      <div className="opp-tags">
        <span className="src-tag">{SOURCE_LABELS[opp.source_type] || opp.source_type}</span>
        {amount && <span className="meta-tag">{amount}</span>}
        {opp.deadline && <span className="meta-tag">{fmtDeadline(opp.deadline)}</span>}
        {opp.countries?.length > 0 && <span className="meta-tag">{opp.countries.join(', ')}</span>}
      </div>

      {matched?.length > 0 && (
        <div className="matched">Matches your profile: {matched.map((m) => (
          <span key={m} className="match-chip">{m}</span>
        ))}</div>
      )}

      {reasons?.length > 0 && (
        <div className={`elig-note ${elig.cls}`}>
          <strong>{elig.label}</strong> — {reasons.join(' · ')}
          {eligibility === 'unconfirmed' && (
            <> · <Link to="/profile">add your country</Link></>
          )}
        </div>
      )}
    </div>
  )
}

export default function Funding() {
  const [tab, setTab] = useState('recommended')
  const [recs, setRecs] = useState([])
  const [all, setAll] = useState([])
  const [live, setLive] = useState([])
  const [liveLoading, setLiveLoading] = useState(true)
  const [eligibleOnly, setEligibleOnly] = useState(false)
  const [sourceFilter, setSourceFilter] = useState('')
  const [query, setQuery] = useState('')
  const [searchResults, setSearchResults] = useState(null)
  const [error, setError] = useState('')
  const [noProfile, setNoProfile] = useState(false)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()
  const { role } = useSession()
  const owner = isOwner(role)

  useEffect(() => {
    fundingService.recommendations({ limit: 50, include_live: true })
      .then((res) => setRecs(res.data))
      .catch((err) => {
        if (err.response?.status === 401) { authService.logout(); navigate('/login') }
        else if (err.response?.status === 400) { setNoProfile(true); setTab('browse') }
        else setError(extractErrorMessage(err))
      })
      .finally(() => setLoading(false))

    fundingService.list().then((res) => setAll(res.data)).catch(() => {})
    loadLive('')
  }, [navigate])

  const loadLive = (q) => {
    setLiveLoading(true)
    fundingService.live(q)
      .then((res) => setLive(res.data))
      .catch(() => setLive([]))
      .finally(() => setLiveLoading(false))
  }

  const runSearch = async (e) => {
    e.preventDefault()
    if (query.trim().length < 2) { setSearchResults(null); loadLive(''); return }
    try {
      const res = await fundingService.search(query.trim())
      setSearchResults(res.data)
    } catch (err) { setError(extractErrorMessage(err)) }
    loadLive(query.trim())
  }

  const shownRecs = eligibleOnly
    ? recs.filter((r) => r.eligibility !== 'ineligible')
    : recs
  const bySource = (o) => !sourceFilter || o.source_type === sourceFilter
  const curatedList = (searchResults ?? all).filter(bySource)
  const liveList = live.filter(bySource)
  const browseList = [...curatedList, ...liveList]

  if (loading) return <Loading message="Matching opportunities, including live funding sources…" />

  return (
    <div className="dashboard">
      <PageHeader trail="Discover" title="Funding Discovery">
        {owner
          ? 'Grants ranked against your portfolio, with eligibility checked against '
            + 'your role and country.'
          : 'The whole funding catalogue, plus live listings — searchable by title, '
            + 'agency or keyword.'}
      </PageHeader>
        {error && <div className="error">{error}</div>}

        {owner && (
          <div className="tabs">
            <button className={tab === 'recommended' ? 'tab active' : 'tab'}
                    onClick={() => setTab('recommended')} disabled={noProfile}
                    title={noProfile ? 'Build your portfolio to get recommendations' : ''}>
              Recommended for you
            </button>
            <button className={tab === 'browse' ? 'tab active' : 'tab'}
                    onClick={() => setTab('browse')}>
              Browse & search all
            </button>
          </div>
        )}

        {owner && tab === 'recommended' && (
          <>
            {noProfile ? (
              <div className="card">
                <p>Create your research profile to get personalized funding recommendations.</p>
                <Link to="/portfolio"><button style={{ marginTop: 12, width: 'auto', padding: '10px 18px' }}>
                  Go to my portfolio</button></Link>
              </div>
            ) : (
              <>
                <label className="checkbox-row">
                  <input type="checkbox" checked={eligibleOnly}
                         onChange={(e) => setEligibleOnly(e.target.checked)} />
                  Hide opportunities I'm not eligible for
                </label>
                <p className="muted" style={{ marginBottom: 12 }}>
                  Ranked against your portfolio — showing {shownRecs.length} of {recs.length}
                </p>
                {shownRecs.length === 0
                  ? <EmptyState>No matching opportunities. Try adding more research domains or keywords to your profile.</EmptyState>
                  : shownRecs.map((r) => (
                      <OpportunityCard key={r.opportunity.id} opp={r.opportunity}
                        score={r.relevance_score} eligibility={r.eligibility}
                        matched={r.matched_terms} reasons={r.reasons} />
                    ))}
              </>
            )}
          </>
        )}

        {/* Staff have no other tab, so the catalogue is their whole page. */}
        {(!owner || tab === 'browse') && (
          <>
            <form onSubmit={runSearch} className="search-row">
              <input placeholder="Search grants by title, agency or keyword..." maxLength={200}
                     value={query} onChange={(e) => setQuery(e.target.value)} />
              <button type="submit">Search</button>
              {searchResults && (
                <button type="button" className="close-results-btn"
                        onClick={() => { setSearchResults(null); setQuery('') }}>Clear</button>
              )}
            </form>

            <select value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)}
                    style={{ maxWidth: 280, marginBottom: 16 }}>
              <option value="">All funding types</option>
              {Object.entries(SOURCE_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>

            <p className="muted" style={{ marginBottom: 12 }}>
              {curatedList.length} curated
              {liveLoading ? ' · loading live sources…' : ` · ${liveList.length} live`}
            </p>
            {browseList.length === 0
              ? <EmptyState>No opportunities found.</EmptyState>
              : browseList.map((o) => <OpportunityCard key={o.id} opp={o} />)}
          </>
        )}
    </div>
  )
}
