import { useEffect, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { profileService, authService, extractErrorMessage } from '../services/api'
import Loading from '../components/Loading'
import { PageHeader, Card } from '../components/ui'
import TagInput from '../components/profile/TagInput'
import PublicationsSection from '../components/profile/PublicationsSection'
import PatentsSection from '../components/profile/PatentsSection'

const EMPTY = {
  headline: '', bio: '', research_domains: [], keywords: [], technology_areas: [],
}

const FIELDS = Object.keys(EMPTY)
const snapshot = (p) => JSON.stringify(FIELDS.map((k) => p[k] ?? EMPTY[k]))

export default function Portfolio() {
  const [profile, setProfile] = useState(EMPTY)
  const [saved, setSaved] = useState(() => snapshot(EMPTY))
  const [exists, setExists] = useState(false)
  const [pubs, setPubs] = useState([])
  const [patents, setPatents] = useState([])
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    profileService.get()
      .then((res) => {
        const loaded = { ...EMPTY, ...res.data }
        setProfile(loaded)
        setSaved(snapshot(loaded))
        setExists(true)
        setPubs(res.data.publications || [])
        setPatents(res.data.patents || [])
      })
      .catch((err) => {
        if (err.response?.status === 401) { authService.logout(); navigate('/login') }
      })
      .finally(() => setLoading(false))
  }, [navigate])

  const patch = (changes) => {
    setProfile((cur) => ({ ...cur, ...changes }))
    setStatus('')
  }
  const set = (field) => (e) => patch({ [field]: e.target.value })
  const dirty = snapshot(profile) !== saved

  const save = async (e) => {
    e.preventDefault()
    setStatus('Saving…')
    try {
      const current = exists ? (await profileService.get()).data : {}
      const call = exists ? profileService.update : profileService.create
      const res = await call({ ...current, ...profile })
      const fresh = { ...EMPTY, ...res.data }
      setProfile(fresh)
      setSaved(snapshot(fresh))
      setExists(true)
      setStatus('Saved')
    } catch (err) {
      setStatus(extractErrorMessage(err, 'Could not save your portfolio.'))
    }
  }

  if (loading) return <Loading message="Loading your portfolio…" />

  return (
    <div className="dashboard">
      <PageHeader trail="Workspace" title="My Portfolio">
        What you work on, and what you’ve produced.
      </PageHeader>

      {status && <div className="status">{status}</div>}

      <form onSubmit={save}>
        <Card
          title="About you"
          sub={<>Your name, organisation and country live in{' '}
            <Link to="/profile" className="inline-link">Profile</Link>.</>}
        >
          <div className="field">
            <label htmlFor="headline">Headline</label>
            <input id="headline" value={profile.headline || ''} onChange={set('headline')}
                   placeholder="e.g. Professor of Materials Science" />
          </div>
          <div className="field">
            <label htmlFor="bio">Short bio</label>
            <textarea id="bio" rows={3} value={profile.bio || ''} onChange={set('bio')}
                      placeholder="A line or two on what you research and what you're working towards." />
          </div>
        </Card>

        <Card title="Your focus">
          <TagInput
            label="Research domains"
            routing={['trends', 'funding']}
            hint="Broad fields, like renewable energy or materials science."
            tags={profile.research_domains}
            elsewhere={[{ label: 'Keywords', terms: profile.keywords },
                        { label: 'Technology areas', terms: profile.technology_areas }]}
            onChange={(v) => patch({ research_domains: v })}
            placeholder="Add a discipline and press Enter"
          />
          <TagInput
            label="Keywords"
            routing={['trends', 'funding']}
            hint="Specific subjects, like fusion or photovoltaics."
            tags={profile.keywords}
            elsewhere={[{ label: 'Research domains', terms: profile.research_domains },
                        { label: 'Technology areas', terms: profile.technology_areas }]}
            onChange={(v) => patch({ keywords: v })}
            placeholder="Add a topic and press Enter"
          />
          <TagInput
            label="Technology areas"
            routing={['patents', 'technology', 'innovation']}
            hint="Patent records are indexed by technology, not discipline: “energy storage” works, “physics” does not."
            tags={profile.technology_areas}
            elsewhere={[{ label: 'Research domains', terms: profile.research_domains },
                        { label: 'Keywords', terms: profile.keywords }]}
            onChange={(v) => patch({ technology_areas: v })}
            placeholder="Add a technology and press Enter"
          />
          {profile.technology_areas.length === 0 && (
            <p className="field-help warn">
              Without one, patent analysis falls back to your domains — a weaker match.
            </p>
          )}
          <div className="form-actions">
            <button type="submit" className="save-btn" disabled={!dirty}
                    title={dirty ? '' : 'No unsaved changes'}>
              {exists ? 'Save changes' : 'Create portfolio'}
            </button>
          </div>
        </Card>
      </form>

      {exists ? (
        <>
          <PublicationsSection items={pubs} setItems={setPubs} />
          <PatentsSection items={patents} setItems={setPatents} />
        </>
      ) : (
        <Card>
          <p className="empty-note">
            Save your portfolio first, then you can add publications and patents.
          </p>
        </Card>
      )}
    </div>
  )
}
