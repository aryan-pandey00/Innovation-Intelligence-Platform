import { useEffect, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { authService, extractErrorMessage } from '../services/api'
import { useSession } from '../services/session'
import { isOwner, roleLabel } from '../roles'
import { canOpen } from '../components/modules'
import OrganisationCard from '../components/profile/OrganisationCard'
import SecurityQuestionFields from '../components/SecurityQuestionFields'
import { PageHeader, Card } from '../components/ui'
import { IconEye, IconEyeOff } from '../components/ui/icons'

const MAX_NAME = 120
const cleanName = (s) => s.trim().replace(/\s+/g, ' ')

function DisplayName({ owner }) {
  const cached = () => authService.getCachedUser().full_name || ''
  const [saved, setSaved] = useState(cached)
  const [name, setName] = useState(cached)
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const trimmed = cleanName(name)
  const dirty = trimmed !== saved && trimmed.length >= 2

  const save = async (e) => {
    e.preventDefault()
    if (!dirty || busy) return
    setBusy(true); setError(''); setMsg('')
    try {
      const res = await authService.updateMe({ full_name: trimmed })
      authService.setCachedUser({ ...authService.getCachedUser(), ...res.data })
      setSaved(res.data.full_name)
      setName(res.data.full_name)
      setMsg('Name updated')
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not update your name.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="account-row account-name-row" onSubmit={save}>
      <div>
        <strong>Display name</strong>
        <p className="muted" style={{ marginTop: 4 }}>
          {owner
            ? 'Shown to you across the platform and to administrators reviewing your work.'
            : 'Shown to you across the platform, and beside anything you change here.'}
        </p>
        {error && <div className="error" style={{ marginTop: 8, marginBottom: 0 }}>{error}</div>}
        {msg && !error && <p className="save-ok">{msg}</p>}
      </div>
      <div className="account-name-edit">
        <input value={name} maxLength={MAX_NAME} aria-label="Display name"
               placeholder="Your full name"
               onChange={(e) => { setName(e.target.value); setMsg('') }} />
        <button type="submit" className="save-btn" disabled={!dirty || busy}
                title={dirty ? '' : 'No unsaved changes'}>
          {busy ? 'Saving…' : 'Save name'}
        </button>
      </div>
    </form>
  )
}

const MIN_PASSWORD = 8

function ChangePassword() {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [show, setShow] = useState(false)
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()

  const submit = async (e) => {
    e.preventDefault()
    if (busy || !current || next.length < MIN_PASSWORD) return
    setBusy(true); setError(''); setMsg('')
    try {
      await authService.changePassword(current, next)
      setMsg('Password changed. Signing you out…')
      setTimeout(() => {
        authService.logout()
        navigate('/login', { replace: true, state: {
          notice: 'Password changed. Sign in with the new one.',
        } })
      }, 900)
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not change your password.'))
      setBusy(false)
    }
  }

  return (
    <Card title="Password">
      {error && <div className="error">{error}</div>}
      {msg && !error && <p className="save-ok">{msg}</p>}
      <form className="account-row" onSubmit={submit}>
        <div>
          <strong>Change your password</strong>
          <p className="muted" style={{ marginTop: 4, maxWidth: '52ch' }}>
            You will be signed out everywhere, including anywhere still open on
            another device. Cannot remember your current one? Use{' '}
            <strong>Forgot Password</strong> on the sign-in page.
          </p>
        </div>
        <div className="password-change">
          <input type="password" autoComplete="current-password"
                 aria-label="Current password" placeholder="Current password"
                 value={current} onChange={(e) => setCurrent(e.target.value)} />
          <div className="input-affix">
            <input type={show ? 'text' : 'password'} autoComplete="new-password"
                   aria-label="New password" placeholder="New password"
                   minLength={MIN_PASSWORD} maxLength={72}
                   value={next} onChange={(e) => setNext(e.target.value)} />
            <button type="button" className="affix-btn"
                    aria-label={show ? 'Hide password' : 'Show password'}
                    aria-pressed={show} onClick={() => setShow((v) => !v)}>
              {show ? <IconEyeOff size={17} /> : <IconEye size={17} />}
            </button>
          </div>
          <button type="submit" className="save-btn"
                  disabled={busy || !current || next.length < MIN_PASSWORD}
                  title={next.length < MIN_PASSWORD
                    ? `At least ${MIN_PASSWORD} characters` : ''}>
            {busy ? 'Changing…' : 'Change password'}
          </button>
        </div>
      </form>
    </Card>
  )
}

function SecurityQuestions() {
  const [state, setState] = useState(null)
  const [pairs, setPairs] = useState([
    { question: '', answer: '' }, { question: '', answer: '' },
  ])
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    authService.securityQuestions()
      .then((res) => {
        setState(res.data)
        if (res.data.questions.length === 2) {
          setPairs(res.data.questions.map((q) => ({ question: q.question, answer: '' })))
        }
      })
      .catch(() => setError('Could not read your security questions.'))
  }, [])

  const change = (i, field, value) =>
    setPairs(pairs.map((p, j) => (j === i ? { ...p, [field]: value } : p)))

  const ready = pairs.every((p) => p.question.trim().length >= 8 && p.answer.trim())
    && pairs[0].question.trim().toLowerCase() !== pairs[1].question.trim().toLowerCase()

  const save = async (e) => {
    e.preventDefault()
    if (!ready || busy) return
    setBusy(true); setError(''); setMsg('')
    try {
      await authService.setSecurityQuestions(pairs)
      setMsg('Saved. Keep the answers somewhere you will remember.')
      setPairs(pairs.map((p) => ({ ...p, answer: '' })))
      setState({ ...state, configured: true })
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not save your questions.'))
    } finally {
      setBusy(false)
    }
  }

  if (!state) return null

  return (
    <Card title="Security questions">
      {error && <div className="error">{error}</div>}
      {msg && !error && <p className="save-ok">{msg}</p>}
      {!state.configured ? (
        <div className="notice">
          <strong>Your account cannot be recovered yet.</strong> No email is sent, so
          without these an administrator has no way to check it is you.
        </div>
      ) : (
        <p className="sq-status">
          <strong>Set.</strong> An administrator checks these if you are ever locked
          out. Saving again replaces both.
        </p>
      )}
      <form onSubmit={save} className="security-questions">
        <SecurityQuestionFields pairs={pairs} onChange={change}
                                suggestions={state.suggestions || []}
                                idPrefix="sq" />
        <button type="submit" className="save-btn" disabled={!ready || busy}
                title={ready ? '' : 'Two different questions, both answered'}>
          {busy ? 'Saving…' : state.configured ? 'Replace questions' : 'Save questions'}
        </button>
      </form>
    </Card>
  )
}

export default function Profile() {
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const { user, role, verified } = useSession()
  const owner = isOwner(role)
  const deleteBlock = user?.delete_block || ''
  const deleteKnown = typeof user?.deletable === 'boolean' || verified

  const deleteAccount = async () => {
    if (!window.confirm(
      owner
        ? 'This permanently deletes your account, portfolio, publications and '
          + 'patents. This cannot be undone. Continue?'
        : 'This permanently deletes your account, and a staff account cannot be '
          + 'created by signing up — only another administrator can restore it. '
          + 'This cannot be undone. Continue?'
    )) return
    try {
      await authService.deleteMyAccount()
      authService.logout()
      navigate('/')
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not delete your account. Please try again.'))
    }
  }

  return (
    <div className="dashboard">
      <PageHeader trail="Account" title="Profile">
        {owner ? (
          <>
            Your name, organisation and contact details. What you research lives in{' '}
            <Link to="/portfolio" className="inline-link">My Portfolio</Link>.
          </>
        ) : (
          <>Your name, sign-in email and role. This account runs the platform, so it
            has no research portfolio.</>
        )}
      </PageHeader>

      <Card title="Name and sign-in">
        <DisplayName owner={owner} />
        <div className="account-row">
          <div>
            <strong>Email and role</strong>
            <p className="muted" style={{ marginTop: 4 }}>
              Your email is your sign-in identity. Roles are assigned by an administrator.
            </p>
          </div>
          <div className="readonly-pair">
            <span>{user?.email}</span>
            <span className="role-line">
              <span className="role-badge">{roleLabel(role)}</span>
              {user?.is_superuser && (
                <span className="super-tag" title="You can manage other administrators">
                  Super
                </span>
              )}
            </span>
          </div>
        </div>
      </Card>

      <ChangePassword />
      <SecurityQuestions />

      {owner && <OrganisationCard role={role} />}

      <Card title="Delete account" className="account-card">
        {error && <div className="error">{error}</div>}
        <div className="account-row">
          <p className="muted" style={{ maxWidth: '52ch' }}>
            {deleteBlock || (owner
              ? 'Permanently removes your account and everything attached to it — '
                + 'your portfolio, publications and patents. This cannot be undone.'
              : 'Permanently removes your account. This cannot be undone, and staff '
                + 'accounts cannot be re-created by signing up.')}
          </p>
          {deleteBlock
            ? (
              canOpen(role, '/admin')
                ? <Link to="/admin" className="inline-link nowrap">Manage administrators →</Link>
                : <span className="cell-note">Not available for this account</span>
            )
            : (
              <button className="delete-account-btn" onClick={deleteAccount}
                      disabled={!deleteKnown}
                      title={deleteKnown ? '' : 'Checking whether this account can be removed'}>
                {deleteKnown ? 'Delete account' : 'Checking…'}
              </button>
            )}
        </div>
      </Card>
    </div>
  )
}
