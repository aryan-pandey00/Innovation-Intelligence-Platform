import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { profileService, authService, extractErrorMessage } from '../../services/api'
import { Card } from '../ui'

const ORG_FIELDS = {
  organization: '', organization_type: '', country: '', website: '', orcid_id: '',
}
const snapshot = (p) => JSON.stringify(Object.keys(ORG_FIELDS).map((k) => p[k] ?? ''))

const IDENTITY = {
  researcher: {
    orgLabel: 'Organisation',
    typeHint: 'University, research council, institute',
    orcid: true,
  },
  startup_founder: {
    orgLabel: 'Company',
    typeHint: 'Startup, spin-out, SME',
    orcid: false,
  },
}

export default function OrganisationCard({ role }) {
  const identity = IDENTITY[role] || IDENTITY.researcher
  const [org, setOrg] = useState(ORG_FIELDS)
  const [saved, setSaved] = useState(() => snapshot(ORG_FIELDS))
  const [exists, setExists] = useState(false)
  const [loadFailed, setLoadFailed] = useState(false)
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

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
        else if (err.response?.status !== 404) {
          setLoadFailed(true)
          setStatus('Could not load your details. Reload before editing.')
        }
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

  return (
    <form onSubmit={save}>
      <Card
        title={identity.orgLabel}
        sub="Country is used to check whether you are eligible for location-restricted funding."
      >
        {status && <div className="status">{status}</div>}
        {loading ? <p className="muted">Loading your details…</p> : (
          <>
            <div className="grid-2">
              <div className="field">
                <label htmlFor="org">{identity.orgLabel}</label>
                <input id="org" value={org.organization || ''} onChange={set('organization')} />
              </div>
              <div className="field">
                <label htmlFor="orgtype">{identity.orgLabel} type</label>
                <input id="orgtype" value={org.organization_type || ''} onChange={set('organization_type')}
                       placeholder={identity.typeHint} />
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
              {identity.orcid && (
                <div className="field">
                  <label htmlFor="orcid">ORCID iD</label>
                  <input id="orcid" value={org.orcid_id || ''} onChange={set('orcid_id')}
                         placeholder="0000-0000-0000-0000" />
                </div>
              )}
            </div>
            <div className="form-actions">
              <button type="submit" className="save-btn" disabled={!dirty || loadFailed}
                      title={loadFailed ? 'Reload before editing'
                                        : (dirty ? '' : 'No unsaved changes')}>
                {exists ? 'Save details' : 'Add details'}
              </button>
            </div>
          </>
        )}
      </Card>
    </form>
  )
}
