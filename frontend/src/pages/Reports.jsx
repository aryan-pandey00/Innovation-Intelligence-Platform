import { useEffect, useState } from 'react'

import { adminService, reportService, extractErrorMessage } from '../services/api'
import Loading from '../components/Loading'
import { PageHeader, Card, EmptyNote } from '../components/ui'
import { useSession } from '../services/session'
import { isOwner } from '../roles'

function Facts({ facts }) {
  if (!facts?.length) return null
  return (
    <ul className="metric-rows">
      {facts.map((f) => (
        <li key={f.label}>
          <span className="metric-label">{f.label}</span>
          <span className="metric-value">{f.value}</span>
        </li>
      ))}
    </ul>
  )
}

function Section({ section }) {
  const hasTable = section.columns?.length > 0
  return (
    <div className="report-section">
      <h3>{section.heading}</h3>
      {section.note && <p className="report-note">{section.note}</p>}
      <Facts facts={section.facts} />
      {hasTable && (
        section.rows.length === 0 ? (
          <p className="empty-note">Nothing to report in this section.</p>
        ) : (
          <div className="table-scroll">
            <table className="user-table">
              <thead>
                <tr>{section.columns.map((c) => <th key={c}>{c}</th>)}</tr>
              </thead>
              <tbody>
                {section.rows.map((row, i) => (
                  <tr key={i}>
                    {row.map((cell, j) => <td key={j}>{cell}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}
    </div>
  )
}

export default function Reports() {
  const [catalogue, setCatalogue] = useState([])
  const [kind, setKind] = useState('')
  const [query, setQuery] = useState('')
  const [roster, setRoster] = useState(null)
  const [subjectId, setSubjectId] = useState('')
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [saved, setSaved] = useState('')
  const { role } = useSession()
  const owner = isOwner(role)

  useEffect(() => {
    reportService.catalogue()
      .then((res) => {
        setCatalogue(res.data.reports)
        if (res.data.reports.length) setKind(res.data.reports[0].kind)
      })
      .catch((err) => setError(extractErrorMessage(err, 'Could not load the report list.')))
      .finally(() => setLoading(false))
  }, [])

  const wantsSubject = catalogue.some((r) => r.needs_subject)
  useEffect(() => {
    if (!wantsSubject) return
    Promise.all([adminService.listUsers(), adminService.pipelineStats()])
      .then(([users, stats]) => {
        const focus = new Map((stats.data.roster || []).map((r) => [r.user_id, r.focus]))
        setRoster(users.data
          .filter((u) => isOwner(u.role) && (focus.get(u.id) || []).length > 0)
          .map((u) => ({ id: u.id, name: u.full_name, email: u.email,
                         focus: focus.get(u.id) }))
          .sort((a, b) => (a.name || '').localeCompare(b.name || '')))
      })
      .catch(() => setRoster([]))
  }, [wantsSubject])

  const chosen = catalogue.find((r) => r.kind === kind)
  const needsSubject = !!chosen?.needs_subject
  const blocked = needsSubject && !subjectId

  const pick = (next) => {
    setKind(next)
    setReport(null)
    setError('')
    setSaved('')
  }

  const args = () => ({
    query: query.trim() || undefined,
    subjectId: needsSubject ? Number(subjectId) : undefined,
  })

  const generate = async () => {
    setBusy('preview'); setError(''); setSaved('')
    try {
      const res = await reportService.preview(kind, args())
      setReport(res.data)
    } catch (err) {
      setReport(null)
      setError(extractErrorMessage(err, 'Could not generate that report.'))
    } finally {
      setBusy('')
    }
  }

  const download = async (format) => {
    setBusy(format); setError(''); setSaved('')
    try {
      const name = await reportService.download(kind, format, args())
      setSaved(`Saved ${name}`)
    } catch (err) {
      let message = 'Could not export that report.'
      const body = err.response?.data
      if (body instanceof Blob) {
        try { message = JSON.parse(await body.text()).detail || message } catch {  }
      } else {
        message = extractErrorMessage(err, message)
      }
      setError(message)
    } finally {
      setBusy('')
    }
  }

  if (loading) return <Loading message="Loading reports…" />

  return (
    <div className="dashboard">
      <PageHeader trail="Act" title="Reports">
        Any analysis, written down — on screen, as a spreadsheet, or as a PDF.
      </PageHeader>

      {error && <div className="error">{error}</div>}
      {saved && <div className="status">{saved}</div>}

      {catalogue.length === 0 ? (
        <Card title="No reports for this account">
          <EmptyNote>
            Reports are built from a portfolio or from the platform's own figures,
            and this account has neither.
          </EmptyNote>
        </Card>
      ) : (
        // "Your data" only for an owner: staff reports are an inventory of everyone
        // else, so the phrase would misdescribe them and mislead the reader.
        <Card title="Choose a report"
              sub={owner
                ? 'One at a time, built from your data as it is now.'
                : "One at a time, built from the platform's data as it is now."}>
          <div className="report-picker">
            {catalogue.map((r) => (
              <label key={r.kind}
                     className={r.kind === kind ? 'report-opt sel' : 'report-opt'}>
                <input type="radio" name="report" value={r.kind}
                       checked={r.kind === kind}
                       onChange={() => pick(r.kind)} />
                <span className="report-opt-name">{r.title}</span>
                <span className="report-opt-sub">{r.summary}</span>
              </label>
            ))}
          </div>

          {chosen?.needs_query && (
            <div className="field" style={{ marginTop: 18 }}>
              <label htmlFor="rq">Technology or topic</label>
              {/* Role-aware: staff have no profile to fall back on, so an empty box
                  used to tell them to create one, which they are forbidden to do. */}
              <input id="rq" value={query} onChange={(e) => setQuery(e.target.value)}
                     maxLength={200}
                     placeholder={owner
                       ? 'Leave empty to use your own field'
                       : 'Leave empty to use your innovators’ main field'} />
              <p className="field-help">
                {owner
                  ? 'Empty uses the first field on your profile.'
                  : 'Empty uses the field most of your innovators work in.'}
              </p>
            </div>
          )}

          {/* An account, not a topic — separate server flags, because neither input
              answers the other's question. */}
          {needsSubject && (
            <div className="field" style={{ marginTop: 18 }}>
              <label htmlFor="rs">Innovator</label>
              {roster === null ? (
                <p className="muted">Loading your innovators…</p>
              ) : roster.length === 0 ? (
                <p className="empty-note">
                  No innovator has named a technology area yet, so there is nothing to
                  assess. This report needs one to score against.
                </p>
              ) : (
                <>
                  <select id="rs" value={subjectId}
                          onChange={(e) => { setSubjectId(e.target.value); setReport(null) }}>
                    <option value="">Choose an innovator…</option>
                    {roster.map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.name} — {r.focus[0]}
                        {r.focus.length > 1 ? ` +${r.focus.length - 1}` : ''}
                      </option>
                    ))}
                  </select>
                  {/* Shorten the copy, never widen the measure: 96ch caption cap. */}
                  <p className="field-help">
                    Scored with their portfolio, not yours. Only those with a
                    technology area can be assessed.
                  </p>
                </>
              )}
            </div>
          )}

          <div className="form-actions report-actions">
            <button type="button" className="save-btn" onClick={generate}
                    disabled={!!busy || blocked}>
              {busy === 'preview' ? 'Generating…' : 'Generate'}
            </button>
            {/* Quiet, so three gold buttons are not three equal primary actions. */}
            <button type="button" className="btn-quiet"
                    onClick={() => download('pdf')} disabled={!!busy || blocked}>
              {busy === 'pdf' ? 'Preparing…' : 'Download PDF'}
            </button>
            <button type="button" className="btn-quiet"
                    onClick={() => download('xlsx')} disabled={!!busy || blocked}>
              {busy === 'xlsx' ? 'Preparing…' : 'Download Excel'}
            </button>
          </div>
          {blocked && roster?.length > 0 && (
            <p className="field-help" style={{ marginTop: 10 }}>
              Choose an innovator above to generate this one.
            </p>
          )}
          {chosen?.live && (
            <p className="field-help" style={{ marginTop: 10 }}>
              Reads live research and patent sources, so each generate or download
              takes a moment.
            </p>
          )}
        </Card>
      )}

      {report && (
        <Card title={report.title} sub={report.summary}
              aside={<span className="muted">{report.subject}</span>}>
          <ul className="metric-rows report-meta">
            {report.meta.map((m) => (
              <li key={m.label}>
                <span className="metric-label">{m.label}</span>
                <span className="metric-value">{m.value}</span>
              </li>
            ))}
          </ul>
          {report.sections.map((s) => <Section key={s.heading} section={s} />)}
        </Card>
      )}
    </div>
  )
}
