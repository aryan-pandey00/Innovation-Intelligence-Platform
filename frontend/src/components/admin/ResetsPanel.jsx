import { useCallback, useEffect, useState } from 'react'

import { adminService, extractErrorMessage } from '../../services/api'
import { resetsChanged } from '../../hooks'
import Loading from '../Loading'
import { Card, PageHeader } from '../ui'
import { fmtStamp } from '../ui/format'
import { roleLabel } from '../../roles'

const STATE_LABEL = {
  waiting: 'Waiting',
  approved: 'Approved',
  completed: 'Reset done',
  cancelled: 'Declined',
  expired: 'Approval expired',
}

// Hostile input: free text an unauthenticated stranger wrote to get into an account.
// Rendered as text and labelled unverified, wherever it appears.
function Appeal({ message }) {
  if (!message) return null
  return (
    <>
      <p className="appeal-lead">They wrote:</p>
      <blockquote className="appeal-note">{message}</blockquote>
      <p className="appeal-warn">Unverified — typed by whoever made this request.</p>
    </>
  )
}

function Answers({ row }) {
  if (!row.had_questions) {
    return (
      <div className="notice answers-none">
        <strong>No security questions were set on this account.</strong> There is
        nothing to check against, so approving rests entirely on your own knowledge
        of this person.
        <Appeal message={row.appeal_message} />
      </div>
    )
  }
  // The appeal route refuses this now, so only rows written before that reach here.
  if (!row.answered_at) {
    return (
      <div className="notice answers-none">
        <strong>This account has security questions, and they were not answered.</strong>{' '}
        The request skipped the check rather than failing it, so there is no evidence
        here either way.
        <Appeal message={row.appeal_message} />
      </div>
    )
  }
  return (
    <>
      <ol className="answer-list">
        {row.answers.map((a, i) => (
          <li key={a.question || i}>
            <span className="answer-q">{a.question}</span>
            <span className="answer-given">
              “{a.typed || '—'}”
              <span className={`answer-verdict ${a.matched ? 'ok' : 'bad'}`}>
                {a.matched ? 'matched' : 'no match'}
              </span>
            </span>
          </li>
        ))}
      </ol>
      <Appeal message={row.appeal_message} />
    </>
  )
}

export default function ResetsPanel() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState(null)

  const load = useCallback(() => {
    adminService.passwordResets()
      .then((res) => setData(res.data))
      .catch(() => setError('Could not read the reset queue.'))
  }, [])

  useEffect(load, [load])

  const act = async (id, fn) => {
    setBusyId(id); setError('')
    try {
      await fn(id)
      load()
      resetsChanged()
    } catch (err) {
      setError(extractErrorMessage(err, 'That did not work.'))
    } finally {
      setBusyId(null)
    }
  }

  const approve = (row) => {
    const unverified = row.appeal_message
      ? ' You have only what they typed about themselves, which nobody has verified.'
      : ''
    const score = !row.had_questions
      ? 'This account never set security questions, so there is nothing to check '
        + 'against.' + unverified
        + ' Approving rests entirely on your own knowledge of this person.'
      : row.answered_at
        ? `They answered ${row.answers_matched} of 2 security questions correctly.`
        : 'This account HAS security questions and this request did not answer them '
          + 'at all.' + unverified
          + ' Nothing has been checked. Approving rests entirely on your own '
          + 'knowledge of this person.'
    if (!window.confirm(
      `Approve the reset for ${row.full_name} (${row.email})?\n\n${score}\n\n`
      + 'This lets whoever made the request set a new password. Only approve if '
      + 'you are satisfied it is really them.')) return
    act(row.id, adminService.approveReset)
  }

  const decline = (row) => {
    if (!window.confirm(
      `Decline the request from ${row.email}? They are told, and can ask again.`)) return
    act(row.id, adminService.cancelReset)
  }

  const withdraw = (row) => {
    if (!window.confirm(
      `Withdraw the approval for ${row.email}?\n\nThey can no longer set a new `
      + 'password, and are told the request was refused.')) return
    act(row.id, adminService.cancelReset)
  }

  if (error && !data) return <div className="error">{error}</div>
  if (!data) return <Loading message="Reading the reset queue…" />

  const { waiting, approved, recent } = data

  return (
    <div className="dashboard">
      <PageHeader trail="Act" title="Password Resets">
        People who cannot sign in, and the one decision that lets them back.
      </PageHeader>

      {error && <div className="error">{error}</div>}

      <Card
        title={waiting.length
          ? `${waiting.length} waiting to be let back in`
          : 'Nobody is locked out'}
        sub={waiting.length
          ? `Approving lets them set a new password on the page they kept open, `
            + `within ${data.ttl_minutes} minutes. Nothing is emailed.`
          : null}>
        {waiting.length === 0 ? (
          <p className="cell-note">
            Requests appear here when somebody uses <em>Forgot Password</em> on the
            sign-in page. Oldest first.
          </p>
        ) : (
          <div className="reset-queue">
            {waiting.map((r) => (
              <div className="reset-request" key={r.id}>
                <div className="reset-who">
                  <strong>{r.full_name}</strong>
                  <span className="cell-note">{r.email} · {roleLabel(r.role)}</span>
                  <span className="cell-note">Asked {fmtStamp(r.requested_at)}</span>
                </div>
                <Answers row={r} />
                <p className="field-help">
                  {r.answered_at && r.had_questions
                    && 'These answers are evidence, not proof. '}
                  Approve only if you are satisfied this is really them.
                </p>
                <div className="reset-actions">
                  <button type="button" className="save-btn"
                          disabled={busyId === r.id}
                          onClick={() => approve(r)}>
                    {busyId === r.id ? '…' : 'Approve'}
                  </button>
                  <button type="button" className="mini-del"
                          disabled={busyId === r.id}
                          onClick={() => decline(r)}>
                    Decline
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {approved.length > 0 && (
        <Card
          title={`${approved.length} approved, not yet used`}
          sub={`They have ${data.ttl_minutes} minutes from approval to set a new `
            + 'password. Withdraw if you approved the wrong person.'}>
          <div className="reset-queue">
            {approved.map((r) => (
              <div className="reset-request" key={r.id}>
                <div className="reset-who">
                  <strong>{r.full_name}</strong>
                  <span className="cell-note">{r.email} · {roleLabel(r.role)}</span>
                  <span className="cell-note">
                    Approved {fmtStamp(r.approved_at)}
                    {r.approved_by && ` by ${r.approved_by}`}
                  </span>
                </div>
                <div className="reset-actions">
                  <button type="button" className="mini-del"
                          disabled={busyId === r.id}
                          onClick={() => withdraw(r)}>
                    Withdraw approval
                  </button>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      <Card title="Recently handled">
        {recent.length === 0 ? (
          <p className="cell-note">Nothing has been reset or declined yet.</p>
        ) : (
          <table className="user-table">
            <thead>
              <tr>
                <th>Who</th><th>Email</th><th>Asked</th><th>Outcome</th>
                <th>Decided by</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((r) => (
                <tr key={r.id}>
                  <td><strong>{r.full_name}</strong></td>
                  <td className="cell-note">{r.email}</td>
                  <td className="nowrap">{fmtStamp(r.requested_at)}</td>
                  <td>
                    {STATE_LABEL[r.state]}
                    <span className="cell-note stacked">{r.basis}</span>
                  </td>
                  <td>{r.approved_by || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p className="field-help">
          The most recent 20. Nothing is deleted — every decision is kept in{' '}
          <em>Recent changes</em> on the Accounts tab.
        </p>
      </Card>
    </div>
  )
}
