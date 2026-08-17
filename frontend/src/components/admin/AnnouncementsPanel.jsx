import { Fragment, useEffect, useState } from 'react'

import {
  adminService, notificationService, extractErrorMessage,
} from '../../services/api'
import { ROLES, ROLE_LABEL } from '../../roles'
import { Card, PageHeader } from '../ui'
import { fmtDate } from '../ui/format'

export default function AnnouncementsPanel() {
  const [form, setForm] = useState({ title: '', body: '', link: '' })
  const [roles, setRoles] = useState([])
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [accounts, setAccounts] = useState(null)
  const [history, setHistory] = useState(null)

  const loadHistory = () => {
    notificationService.announcements()
      .then((res) => setHistory(res.data.announcements))
      .catch(() => setHistory([]))
  }

  useEffect(() => {
    adminService.listUsers()
      .then((res) => setAccounts(res.data))
      .catch(() => setAccounts([]))
    loadHistory()
  }, [])

  const set = (field) => (e) => {
    setForm((cur) => ({ ...cur, [field]: e.target.value }))
    setStatus(''); setError('')
  }

  const toggleRole = (value) => {
    setRoles((cur) => (cur.includes(value)
      ? cur.filter((r) => r !== value) : [...cur, value]))
    setStatus(''); setError('')
  }

  const ready = form.title.trim().length >= 3 && form.body.trim().length >= 3
  const reach = accounts === null ? null
    : (roles.length === 0 ? accounts.length
                          : accounts.filter((u) => roles.includes(u.role)).length)

  const send = async (e) => {
    e.preventDefault()
    if (!ready || busy) return

    const who = reach === null ? 'every matching account'
      : `${reach} account${reach === 1 ? '' : 's'}`
      + (roles.length ? ` (${roles.map((r) => ROLE_LABEL[r] || r).join(', ')})` : '')
    if (!window.confirm(
      `Send "${form.title.trim()}" to ${who}?\n\n`
      + 'It appears in their notifications straight away. You can edit or withdraw '
      + 'it afterwards, but anyone who has already read it has read it.'
    )) return

    setBusy(true); setError(''); setStatus('')
    try {
      const res = await notificationService.broadcast({
        title: form.title.trim(),
        body: form.body.trim(),
        roles,
        link: form.link.trim() || null,
      })
      const n = res.data.sent
      setStatus(n === 0
        ? 'Everyone selected already has this announcement — nothing re-sent.'
        : `Delivered to ${n} account${n === 1 ? '' : 's'}.`)
      setForm({ title: '', body: '', link: '' })
      loadHistory()
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not send the announcement.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="dashboard">
      <PageHeader trail="Act" title="Announcements">
        A message from you to everyone on the platform, or to chosen roles.
      </PageHeader>

    <form onSubmit={send}>
      <Card
        title="Send a platform notification"
        sub="Appears in the recipient's notifications. Nothing is emailed."
      >
        {error && <div className="error">{error}</div>}
        {status && <div className="status">{status}</div>}

        <div className="field">
          <label htmlFor="ann-title">Title</label>
          <input id="ann-title" value={form.title} onChange={set('title')}
                 maxLength={160} placeholder="Scheduled maintenance on Sunday" />
        </div>

        <div className="field">
          <label htmlFor="ann-body">Message</label>
          <textarea id="ann-body" value={form.body} onChange={set('body')}
                    rows={4} maxLength={2000}
                    placeholder="What is happening, and what the reader should do." />
        </div>

        <div className="field">
          <label htmlFor="ann-link">Link (optional)</label>
          <input id="ann-link" value={form.link} onChange={set('link')}
                 placeholder="/funding" />
          <p className="field-help">
            A path inside the platform, such as <code>/funding</code>. Shown as
            “Open →” beneath the message.
          </p>
        </div>

        <div className="field">
          <label>Send to</label>
          {ROLES.map((r) => (
            <label key={r.value} className="checkbox-row">
              <input type="checkbox" checked={roles.includes(r.value)}
                     onChange={() => toggleRole(r.value)} />
              {r.label}
            </label>
          ))}
          <p className="field-help">
            {roles.length === 0
              ? 'No role selected, so this goes to every account.'
              : `Only ${roles.length} of ${ROLES.length} roles will receive it.`}
            {reach !== null && ` Reaches ${reach} account${reach === 1 ? '' : 's'}.`}
            {' '}It arrives at once.
          </p>
        </div>

        <div className="form-actions">
          <button type="submit" className="save-btn" disabled={!ready || busy}
                  title={ready ? '' : 'A title and a message are required'}>
            {busy ? 'Sending…' : 'Send announcement'}
          </button>
        </div>

        <p className="field-help" style={{ marginTop: 14 }}>
          Re-sending is safe: accounts that already have it are skipped, so it tops up
          new joiners.
        </p>
      </Card>

    </form>
      <SentAnnouncements rows={history} onChanged={loadHistory} />
    </div>
  )
}

function SentAnnouncements({ rows, onChanged }) {
  const [editing, setEditing] = useState(null)
  const [draft, setDraft] = useState({ title: '', body: '', link: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  if (rows === null) {
    return <Card title="Sent announcements"><p className="muted">Loading…</p></Card>
  }

  const open = (r) => {
    setEditing(r.key)
    setDraft({ title: r.title, body: r.body, link: r.link || '' })
    setError('')
  }

  const save = async (key) => {
    if (busy) return
    setBusy(true); setError('')
    try {
      await notificationService.editAnnouncement(key, {
        title: draft.title.trim(), body: draft.body.trim(),
        link: draft.link.trim() || null,
      })
      setEditing(null)
      onChanged()
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not update the announcement.'))
    } finally { setBusy(false) }
  }

  const withdraw = async (r) => {
    if (!window.confirm(
      `Withdraw "${r.title}" from ${r.delivered} account`
      + `${r.delivered === 1 ? '' : 's'}?\n\n`
      + 'It disappears from their notifications, read or not. You can send it again after.'
    )) return
    setBusy(true); setError('')
    try {
      await notificationService.withdrawAnnouncement(r.key)
      if (editing === r.key) setEditing(null)
      onChanged()
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not withdraw the announcement.'))
    } finally { setBusy(false) }
  }

  return (
    <Card title={`Sent announcements${rows.length ? ` (${rows.length})` : ''}`}
          sub="Every announcement on the platform, most recent first">
      {error && <div className="error">{error}</div>}
      {rows.length === 0 ? (
        <p className="empty-note">Nothing has been announced yet.</p>
      ) : (
        <>
          <div className="table-wrap">
            <table className="user-table">
              <thead>
                <tr>
                  <th>Sent</th><th>Announcement</th><th>Delivered</th>
                  <th>Read</th><th>Dismissed</th><th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <Fragment key={r.key}>
                    <tr>
                      <td className="cell-note nowrap">{fmtDate(r.sent_at)}</td>
                      <td>
                        <strong>{r.title}</strong>
                        <span className="cell-note row-sub">{r.body}</span>
                      </td>
                      <td className="nowrap">{r.delivered}</td>
                      <td className="nowrap">{r.read}</td>
                      <td className="nowrap">{r.dismissed}</td>
                      <td className="row-actions">
                        <div className="row-actions-inner">
                          <button type="button" className="mini-view"
                                  onClick={() => (editing === r.key
                                    ? setEditing(null) : open(r))}>
                            {editing === r.key ? 'Close' : 'Edit'}
                          </button>
                          <button type="button" className="mini-del" disabled={busy}
                                  onClick={() => withdraw(r)}>Withdraw</button>
                        </div>
                      </td>
                    </tr>
                    {editing === r.key && (
                      <tr className="row-detail">
                        <td colSpan={6}>
                          <div className="field">
                            <label htmlFor={`ed-t-${r.key}`}>Title</label>
                            <input id={`ed-t-${r.key}`} value={draft.title}
                                   maxLength={160}
                                   onChange={(e) => setDraft((d) =>
                                     ({ ...d, title: e.target.value }))} />
                          </div>
                          <div className="field">
                            <label htmlFor={`ed-b-${r.key}`}>Message</label>
                            <textarea id={`ed-b-${r.key}`} rows={4} maxLength={2000}
                                      value={draft.body}
                                      onChange={(e) => setDraft((d) =>
                                        ({ ...d, body: e.target.value }))} />
                          </div>
                          <div className="field">
                            <label htmlFor={`ed-l-${r.key}`}>Link (optional)</label>
                            <input id={`ed-l-${r.key}`} value={draft.link}
                                   placeholder="/funding"
                                   onChange={(e) => setDraft((d) =>
                                     ({ ...d, link: e.target.value }))} />
                          </div>
                          <div className="form-actions">
                            <button type="button" className="save-btn" onClick={() => save(r.key)}
                                    disabled={busy || draft.title.trim().length < 3
                                              || draft.body.trim().length < 3}>
                              {busy ? 'Saving…' : 'Save changes'}
                            </button>
                            <button type="button" className="btn-quiet"
                                    onClick={() => setEditing(null)}>Cancel</button>
                          </div>
                          <p className="field-help">
                            The correction reaches everyone who still has it. Nobody is
                            alerted again, and anyone who dismissed it keeps it
                            dismissed — withdraw and re-send if it must be seen. Who it
                            went to cannot be changed here.
                          </p>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
          <p className="table-foot">
            Delivered counts every account it reached. Only a closed account removes
            its own copy.
          </p>
        </>
      )}
    </Card>
  )
}
