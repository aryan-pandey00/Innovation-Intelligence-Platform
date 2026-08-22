import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import {
  adminService, innovationService, reportService, extractErrorMessage,
} from '../services/api'
import { useSession } from '../services/session'
import { canOpen } from '../components/modules'
import { isOwner, roleLabel } from '../roles'
import Loading from '../components/Loading'
import ProfileDetail from '../components/ProfileDetail'
import { Card, InfoHint, PageHeader, StatCard, StatGrid } from '../components/ui'
import { fmtCount, fmtPct } from '../components/ui/format'

export default function Innovator() {
  const { id } = useParams()
  const { role } = useSession()
  const uid = Number(id)

  const [subject, setSubject] = useState(null)
  const [subjectState, setSubjectState] = useState('loading')
  const [entry, setEntry] = useState(null)
  const [profile, setProfile] = useState(null)
  const [profileState, setProfileState] = useState('loading')
  const [assessment, setAssessment] = useState(null)
  const [assessState, setAssessState] = useState('loading')
  const [assessNote, setAssessNote] = useState('')
  const [exportable, setExportable] = useState(false)
  const [saving, setSaving] = useState('')
  const [saved, setSaved] = useState('')
  const [saveError, setSaveError] = useState('')

  useEffect(() => {
    if (!Number.isInteger(uid) || uid < 1) { setSubjectState('missing'); return }

    adminService.listUsers()
      .then((res) => {
        const found = res.data.find((u) => u.id === uid)
        setSubject(found || null)
        setSubjectState(found ? 'ready' : 'missing')
      })
      .catch(() => setSubjectState('error'))

    adminService.pipelineStats()
      .then((res) => setEntry((res.data.roster || []).find((r) => r.user_id === uid) || null))
      .catch(() => setEntry(null))

    adminService.getUserProfile(uid)
      .then((res) => { setProfile(res.data); setProfileState('ready') })
      .catch((err) => setProfileState(err.response?.status === 404 ? 'none' : 'error'))

    innovationService.assessmentFor(uid)
      .then((res) => { setAssessment(res.data); setAssessState('ready') })
      .catch((err) => {
        setAssessNote(extractErrorMessage(err, 'Could not assess this innovator.'))
        setAssessState('unavailable')
      })

    reportService.catalogue()
      .then((res) => setExportable(
        (res.data.reports || []).some((r) => r.kind === 'innovator')))
      .catch(() => setExportable(false))
  }, [uid])

  const download = async (format) => {
    setSaving(format); setSaved(''); setSaveError('')
    try {
      const name = await reportService.download('innovator', format, { subjectId: uid })
      setSaved(`Saved ${name}`)
    } catch (err) {
      let message = 'Could not export this assessment.'
      const body = err.response?.data
      if (body instanceof Blob) {
        try { message = JSON.parse(await body.text()).detail || message } catch {  }
      } else {
        message = extractErrorMessage(err, message)
      }
      setSaveError(message)
    } finally {
      setSaving('')
    }
  }

  const back = role === 'admin'
    ? { to: '/admin', label: 'Accounts' }
    : { to: '/dashboard', label: 'Innovation Pipeline' }

  if (subjectState === 'loading') return <Loading message="Opening this innovator…" />

  if (subjectState !== 'ready') {
    return (
      <div className="dashboard">
        <PageHeader trail={<Link to={back.to}>← {back.label}</Link>} title="Innovator">
          {subjectState === 'missing'
            ? 'No account on the platform has that id. It may have been deleted.'
            : 'Could not read the account list, so this page cannot confirm whose it is.'}
        </PageHeader>
      </div>
    )
  }

  const best = entry?.best_match
  const pubs = profile?.publications?.length ?? null
  const pats = profile?.patents?.length ?? null

  const assessCard = (
    <Assessment state={assessState} data={assessment} note={assessNote}
                name={subject.full_name}
                canAnalyse={canOpen(role, '/technology')} />
  )

  return (
    <div className="dashboard">
      <PageHeader trail={<Link to={back.to}>← {back.label}</Link>}
                  title={subject.full_name}>
        {isOwner(subject.role)
          ? 'Their portfolio, and the field they work in scored with it.'
          : 'A staff account. Staff own no portfolio, so there is nothing to assess.'}
      </PageHeader>
      <div className="subject-line">
        <span className="role-badge">{roleLabel(subject.role)}</span>
        <span>{subject.email}</span>
        {profile?.organization && <span>· {profile.organization}</span>}
        {profile?.country && <span>· {profile.country}</span>}
      </div>

      {exportable && assessState === 'ready' && (
        <div className="subject-actions">
          <button type="button" className="btn-quiet" disabled={!!saving}
                  onClick={() => download('pdf')}>
            {saving === 'pdf' ? 'Preparing…' : 'Download PDF'}
          </button>
          <button type="button" className="btn-quiet" disabled={!!saving}
                  onClick={() => download('xlsx')}>
            {saving === 'xlsx' ? 'Preparing…' : 'Download Excel'}
          </button>
        </div>
      )}
      {saved && <div className="status">{saved}</div>}
      {saveError && <div className="error">{saveError}</div>}

      <StatGrid>
        <StatCard
          value={assessState === 'ready' ? assessment.innovation_score : '—'}
          label="Innovation score"
          note={assessState === 'ready'
            ? `${assessment.rating} potential · ${assessment.query}`
            : 'not scored'}
        />
        <StatCard
          value={best ? `${Math.round(best.score)}%` : '—'}
          label="Best funding match"
          note={best ? best.agency : 'nothing matched'}
          hint="Scored across their whole portfolio, which is the figure the pipeline
                table shows. The Funding Relevance factor below is scored against this
                technology alone, so the two differ by design."
        />
        <StatCard value={pubs ?? '—'} label="Publications" />
        <StatCard value={pats ?? '—'} label="Patents" />
      </StatGrid>

      {assessState === 'ready' ? (
        <>
          {/* Paired with the readings, not the route: both are label-and-value lists of
              similar height, so the two columns finish level instead of one hanging. */}
          <div className="dash-grid dash-grid-even" style={{ marginTop: 20 }}>
            {assessCard}
            <Measurements data={assessment} />
          </div>
          <NextSteps data={assessment} />
        </>
      ) : (
        <div style={{ marginTop: 20 }}>{assessCard}</div>
      )}

      <Card
        className="portfolio-card"
        title="Portfolio"
        sub={profileState === 'ready'
          ? 'The evidence every analysis module runs on for this account'
          : undefined}
      >
        {profileState === 'loading' && <p className="muted">Loading their portfolio…</p>}
        {profileState === 'none' && (
          <p className="empty-note">
            {isOwner(subject.role)
              ? 'This account has not built a portfolio yet, so no analysis module '
                + 'has anything to run on for them.'
              : 'Staff accounts own no research portfolio by design.'}
          </p>
        )}
        {profileState === 'error' && (
          <p className="empty-note">Could not load their portfolio.</p>
        )}
        {profileState === 'ready' && <ProfileDetail p={profile} />}
      </Card>
    </div>
  )
}

function Assessment({ state, data, note, name, canAnalyse }) {
  if (state === 'loading') {
    return (
      <Card title="Innovation assessment">
        <Loading message="Scoring their field…" />
      </Card>
    )
  }
  if (state !== 'ready') {
    return (
      <Card title="Innovation assessment">
        <p className="empty-note">{note}</p>
      </Card>
    )
  }

  const s = data.signals || {}
  const factors = [...(data.components || [])]
    .sort((a, b) => b.weight - a.weight || b.score - a.score)
  // Zero terms are dropped: "0 publications" beside a stat card reading "Publications 2"
  // reads as the page contradicting itself, though both figures are right.
  const own = [(s.own_publications ?? 0) > 0 && plural(s.own_publications, 'publication'),
               (s.own_patents ?? 0) > 0 && plural(s.own_patents, 'patent')].filter(Boolean)

  return (
    <Card
      title="Innovation assessment"
      sub={`Scored on ${data.query}, using their portfolio rather than yours`
        + (data.fields_are_fallback
          ? ' · from their research domains, as no technology area is set' : '')}
      aside={canAnalyse && (
        <Link to={`/technology?q=${encodeURIComponent(data.query)}`} className="inline-link">
          Analyse the field →
        </Link>
      )}
    >
      <div className="score-hero" style={{ marginBottom: 18 }}>
        <div className="big-score">
          {data.innovation_score}<small>out of 100</small>
        </div>
        <div style={{ flex: 1 }}>
          <span className="rating-pill">{data.rating} potential</span>
          <p className="score-context">
            {own.length > 0
              ? `Includes ${own.join(' and ')} of theirs about this technology.`
              : `Nothing in ${name}'s portfolio mentions this technology, so this `
                + 'scores the field rather than their position in it.'}
          </p>
        </div>
      </div>

      <ul className="metric-rows">
        {factors.map((c) => (
          <li key={c.key}>
            <span className="metric-label">
              {c.label}
              <InfoHint>{c.description}</InfoHint>
            </span>
            <span className="metric-value">{c.score}</span>
            <span className="metric-note">{c.weight}% of the total</span>
          </li>
        ))}
      </ul>

    </Card>
  )
}

const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`

function Measurements({ data }) {
  const s = data.signals || {}
  const rows = [
    ['Papers in this field', fmtCount(s.research_total)],
    ['Research growth', s.research_growth == null ? '—'
      : fmtPct(s.research_growth, { sign: true })],
    ['Patents in this field', fmtCount(s.patent_total)],
    ['Filing growth', s.patent_history_reliable && s.patent_growth != null
      ? fmtPct(s.patent_growth, { sign: true }) : 'not measurable'],
    ['Busiest patent year', s.busiest_year || '—'],
    ['Lifecycle stage', s.stage || '—'],
  ]

  return (
    <Card title="The readings behind it"
          sub={`Measured for ${data.query}, not for this account`}>
      <ul className="metric-rows">
        {rows.map(([label, value]) => (
          <li key={label}>
            <span className="metric-label">{label}</span>
            <span className="metric-value">{value}</span>
          </li>
        ))}
      </ul>
      <p className="chart-foot">
        Totals cover every year on record; the growth figures compare the last eleven
        complete years.
      </p>
    </Card>
  )
}

function NextSteps({ data }) {
  const comm = data.commercialization
  const pathway = comm?.pathway
  const now = (comm?.recommendations || []).filter((r) => r.priority === 'now')
  if (!pathway?.title && now.length === 0) return null

  return (
    <Card
      className="route-card"
      title="Route to market"
      sub={pathway?.title
        ? `${pathway.title} · ${plural(now.length, 'step')} outstanding`
        : 'No pathway could be derived from this score'}
    >
      {now.length > 0 && (
        <ul className="check-list">
          {now.map((r) => (
            <li key={r.title}>
              <span className="todo">○</span>
              <span>{r.title}</span>
            </li>
          ))}
        </ul>
      )}
      <p className="chart-foot">
        Derived from the same pass as the score above, for {data.query}. The step
        detail is written to the innovator in their own words, so it is theirs to
        read rather than reprinted here.
      </p>
    </Card>
  )
}
