import { useEffect, useMemo, useRef, useState } from 'react'

import { adminService, fundingService, extractErrorMessage } from '../../services/api'
import { Card, InfoHint, StatCard, StatGrid } from '../ui'
import { fmtAmount, fmtDeadline, SOURCE_LABELS } from '../ui/format'
import GrantForm from './GrantForm'

const today = () => new Date().toISOString().slice(0, 10)

const FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'unreached', label: 'Reaching nobody' },
  { key: 'closed', label: 'Closed' },
]

export default function CataloguePanel() {
  const [grants, setGrants] = useState([])
  const [reach, setReach] = useState(null)
  const [sampled, setSampled] = useState(null)
  const [filter, setFilter] = useState('all')
  const [query, setQuery] = useState('')
  const [editing, setEditing] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [formError, setFormError] = useState('')
  const formRef = useRef(null)

  const load = () => {
    fundingService.list()
      .then((res) => setGrants(res.data))
      .catch(() => setError('Could not load the catalogue.'))
    adminService.recommendationStats()
      .then((res) => {
        setReach(new Map((res.data.reach || []).map((r) => [r.id, r.owners])))
        setSampled(res.data.profiles_sampled ?? null)
      })
      .catch(() => setReach(null))
  }

  useEffect(load, [])

  const reveal = () => requestAnimationFrame(() => {
    formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })

  const startEdit = (grant) => { setFormError(''); setEditing(grant); reveal() }

  const save = async (data) => {
    setBusy(true); setFormError('')
    try {
      if (editing?.id) await adminService.updateOpportunity(editing.id, data)
      else await adminService.createOpportunity(data)
      setEditing(null)
      load()
    } catch (err) {
      setFormError(extractErrorMessage(err, 'Could not save that grant.'))
    } finally {
      setBusy(false)
    }
  }

  const remove = async (grant) => {
    if (!window.confirm(
      `Remove "${grant.title}" (${grant.agency}) from the catalogue permanently? `
      + 'This cannot be undone.'
    )) return
    try {
      await adminService.deleteOpportunity(grant.id)
      if (editing?.id === grant.id) setEditing(null)
      load()
    } catch (err) {
      alert(extractErrorMessage(err, 'Could not remove that grant.'))
    }
  }

  const closed = (g) => g.deadline && g.deadline < today()
  const unreached = (g) => reach != null && (reach.get(g.id) ?? 0) === 0

  const counts = {
    all: grants.length,
    unreached: reach == null ? null : grants.filter(unreached).length,
    closed: grants.filter(closed).length,
  }

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase()
    return grants
      .filter((g) => (filter === 'all')
        || (filter === 'unreached' && unreached(g))
        || (filter === 'closed' && closed(g)))
      .filter((g) => !q || (g.title || '').toLowerCase().includes(q)
        || (g.agency || '').toLowerCase().includes(q))
      .sort((a, b) => {
        const rank = (g) => (closed(g) ? 2 : (g.deadline ? 0 : 1))
        return rank(a) - rank(b)
          || (a.deadline || '9999').localeCompare(b.deadline || '9999')
      })
  }, [grants, filter, query, reach])   // eslint-disable-line react-hooks/exhaustive-deps

  const agencies = new Set(grants.map((g) => g.agency).filter(Boolean)).size

  return (
    <>
      {error && <div className="error">{error}</div>}

      <StatGrid>
        <StatCard value={grants.length} label="Grants in the catalogue"
                  note={`from ${agencies} funders`} />
        <StatCard value={counts.unreached ?? '—'} label="Reaching nobody"
                  tone={counts.unreached ? 'warn' : undefined}
                  note={reach == null ? 'reach could not be measured'
                                      : 'nobody scores against them'} />
        <StatCard value={counts.closed} label="Past their deadline"
                  note="ineligible for everyone" />
      </StatGrid>

      {editing && (
        <div ref={formRef}>
          <GrantForm value={editing.id ? editing : null} onSave={save} busy={busy}
                     error={formError} onCancel={() => setEditing(null)} />
        </div>
      )}

      <Card
        title="Funding catalogue"
        sub="Closing soonest first, then undated, with closed grants last"
        aside={(
          <input className="table-search" type="search"
                 placeholder="Search title or agency" aria-label="Search grants"
                 value={query} onChange={(e) => setQuery(e.target.value)} />
        )}
      >
        <div className="field-chips">
          {FILTERS.map((f) => (
            <button key={f.key} type="button"
                    className={filter === f.key ? 'field-chip active' : 'field-chip'}
                    onClick={() => setFilter(f.key)}>
              {f.label}{counts[f.key] != null ? ` (${counts[f.key]})` : ''}
            </button>
          ))}
          <button type="button" className="field-chip chip-more"
                  onClick={() => startEdit({})}>+ Add a grant</button>
        </div>

        <div className="table-wrap">
          <table className="user-table">
            <thead>
              <tr>
                <th>Grant</th><th>Type</th><th>Amount</th><th>Deadline</th>
                <th>
                  Reach
                  <InfoHint>
                    {'How many portfolios score at or above the match threshold '
                     + 'against this grant. A zero is often the size of the audience '
                     + 'rather than a fault in the grant.'}
                  </InfoHint>
                </th>
                <th colSpan={2} className="th-actions">Actions</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((g) => (
                <tr key={g.id} className={editing?.id === g.id ? 'row-editing' : ''}>
                  <td className="cat-grant">
                    <strong>{g.title}</strong><br />
                    <span className="muted" style={{ fontSize: 12 }}>{g.agency}</span>
                  </td>
                  <td className="cell-type nowrap">
                    {SOURCE_LABELS[g.source_type] || g.source_type}
                  </td>
                  <td className="nowrap">
                    {fmtAmount(g.amount_min, g.amount_max, g.currency)
                      || <span className="cell-note">Not stated</span>}
                  </td>
                  <td className="nowrap">
                    {g.deadline ? fmtDeadline(g.deadline)
                                : <span className="cell-note">No deadline</span>}
                  </td>
                  <td>
                    {reach == null ? <span className="cell-note">—</span>
                      : closed(g) ? <span className="cell-note">closed</span>
                        : (reach.get(g.id) || <span className="cell-note">nobody</span>)}
                  </td>
                  <td>
                    <button className="mini-view" onClick={() => startEdit(g)}>Edit</button>
                  </td>
                  <td>
                    <button className="mini-del" onClick={() => remove(g)}>Remove</button>
                  </td>
                </tr>
              ))}
              {shown.length === 0 && (
                <tr><td colSpan={7} className="cell-note">
                  No grant matches that filter.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>

        <p className="table-foot">
          {reach == null
            ? 'Reach could not be measured, so that column is blank rather than zero.'
            : `Reach is measured against the portfolios on the platform${
              sampled ? `, sampled at the most recent ${sampled}` : ''}.`}
        </p>
      </Card>
    </>
  )
}
