import { useEffect, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { profileService, authService, extractErrorMessage } from '../services/api'
import Loading from '../components/Loading'
import { PageHeader, Card } from '../components/ui'

const ROLE_LABEL = {
  researcher: 'Researcher',
  startup_founder: 'Startup Founder',
  innovation_manager: 'Innovation Manager',
  admin: 'Administrator',
}

const ORG_FIELDS = {
  organization: '', organization_type: '', country: '', website: '', orcid_id: '',
}
const snapshot = (p) => JSON.stringify(Object.keys(ORG_FIELDS).map((k) => p[k] ?? ''))

const MAX_NAME = 120
const cleanName = (s) => s.trim().replace(/\s+/g, ' ')

function DisplayName() {
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
          Shown to you across the platform and to administrators reviewing your work.
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

export default function Profile() {
  const [org, setOrg] = useState(ORG_FIELDS)
  const [saved, setSaved] = useState(() => snapshot(ORG_FIELDS))
  const [exists, setExists] = useState(false)
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()
  const user = authService.getCachedUser()

  useEffect(() => {
    profileService.get()
      .then((res) => {
        const loaded = { ...ORG_FIELDS, ...res.data }
        setOrg(loaded)
        setSaved(snapshot(loaded))
        setExists(true)
      })
      .catch((err) => {
        if (err.response?.status === 401) { authService.logout(); navigate('/login') }
      })
      .finally(() => setLoading(false))
  }, [navigate])

  const set = (field) => (e) => {
    setOrg((cur) => ({ ...cur, [field]: e.target.value }))
    setStatus('')
  }
  const dirty = snapshot(org) !== saved

  const save = async (e) => {
    e.preventDefault()
    setStatus('Saving…')
    try {
      // Merge with the stored record so saving here cannot wipe the portfolio
      // fields that live on the same row.
      const current = exists ? (await profileService.get()).data : {}
      const call = exists ? profileService.update : profileService.create
      const res = await call({ ...current, ...org })
      const fresh = { ...ORG_FIELDS, ...res.data }
      setOrg(fresh)
      setSaved(snapshot(fresh))
      setExists(true)
      setStatus('Saved')
    } catch (err) {
      setStatus(extractErrorMessage(err, 'Could not save your details.'))
    }
  }

  const deleteAccount = async () => {
    if (!window.confirm(
      'This permanently deletes your account, portfolio, publications and patents. '
      + 'This cannot be undone. Continue?'
    )) return
    try {
      await authService.deleteMyAccount()
      authService.logout()
      navigate('/register')
    } catch {
      setStatus('Could not delete your account. Please try again.')
    }
  }

  if (loading) return <Loading message="Loading your profile…" />

  return (
    <div className="dashboard">
      {/* Not "Settings": there is no theme, no notifications, no preferences. It
          holds personal information, so it is named for that. The pointer to My
          Portfolio is the other half of the split and is mirrored there. */}
      <PageHeader trail="Account" title="Profile">
        Your name, organisation and contact details. What you research lives in{' '}
        <Link to="/portfolio" className="inline-link">My Portfolio</Link>.
      </PageHeader>

      {status && <div className="status">{status}</div>}

      <Card title="Name and sign-in">
        <DisplayName />
        <div className="account-row account-readonly">
          <div>
            <strong>Email and role</strong>
            <p className="muted" style={{ marginTop: 4 }}>
              Your email is your sign-in identity. Roles are assigned by an administrator.
            </p>
          </div>
          <div className="readonly-pair">
            <span>{user.email}</span>
            <span className="role-badge">{ROLE_LABEL[user.role] || user.role}</span>
          </div>
        </div>
      </Card>

      <form onSubmit={save}>
        <Card
          title="Organisation"
          sub="Country is used to check whether you are eligible for location-restricted funding."
        >
          <div className="grid-2">
            <div className="field">
              <label htmlFor="org">Organisation</label>
              <input id="org" value={org.organization || ''} onChange={set('organization')} />
            </div>
            <div className="field">
              <label htmlFor="orgtype">Organisation type</label>
              <input id="orgtype" value={org.organization_type || ''} onChange={set('organization_type')}
                     placeholder="University, company, research council" />
            </div>
            <div className="field">
              <label htmlFor="country">Country</label>
              <input id="country" value={org.country || ''} onChange={set('country')}
                     placeholder="Needed to confirm funding eligibility" />
            </div>
            <div className="field">
              <label htmlFor="website">Website</label>
              <input id="website" value={org.website || ''} onChange={set('website')} />
            </div>
            <div className="field">
              <label htmlFor="orcid">ORCID iD</label>
              <input id="orcid" value={org.orcid_id || ''} onChange={set('orcid_id')}
                     placeholder="0000-0000-0000-0000" />
            </div>
          </div>
          <div className="form-actions">
            <button type="submit" className="save-btn" disabled={!dirty}
                    title={dirty ? '' : 'No unsaved changes'}>
              Save details
            </button>
          </div>
        </Card>
      </form>

      <Card title="Delete account" className="account-card">
        <div className="account-row">
          <p className="muted" style={{ maxWidth: '52ch' }}>
            Permanently removes your account and everything attached to it — your
            portfolio, publications and patents. This cannot be undone.
          </p>
          <button className="delete-account-btn" onClick={deleteAccount}>Delete account</button>
        </div>
      </Card>
    </div>
  )
}
