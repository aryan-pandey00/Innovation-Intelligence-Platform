import { useEffect, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { commercializationService, authService, extractErrorMessage } from '../services/api'
import Loading from '../components/Loading'
import FieldChips from '../components/FieldChips'
import CommercializationView from '../components/CommercializationView'
import NextRow from '../components/NextRow'
import { PageHeader, Card } from '../components/ui'

export default function Commercialization() {
  const [query, setQuery] = useState('')
  const [fields, setFields] = useState([])
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    commercializationService.mine()
      .then((res) => {
        setData(res.data); setQuery(res.data.query); setFields(res.data.profile_fields || [])
      })
      .catch((err) => {
        if (err.response?.status === 401) { authService.logout(); navigate('/login') }
        else setError(extractErrorMessage(err, 'Could not load commercialization recommendations'))
      })
      .finally(() => setLoading(false))
  }, [navigate])

  const analyze = async (e, term) => {
    e?.preventDefault()
    const q = (term ?? query).trim()
    if (q.length < 2) return
    setQuery(q); setLoading(true); setError('')
    try {
      const res = await commercializationService.forQuery(q)
      setData(res.data)
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not load commercialization recommendations'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="dashboard">
      <PageHeader trail="Act" title="Commercialization">
        The route from a technology to a product, a licence or a company — and
        what to do first.
      </PageHeader>

      <form onSubmit={analyze} className="search-row">
        <input placeholder="Plan a technology, e.g. solid-state battery" maxLength={200}
               aria-label="Technology to plan"
               value={query} onChange={(e) => setQuery(e.target.value)} />
        <button type="submit">Analyse</button>
      </form>
      <FieldChips fields={fields} active={data?.query} onPick={(f) => analyze(null, f)}
                  label="Your technology areas" fallback={data?.fields_are_fallback} />

      {error && <div className="error">{error}</div>}
      {loading && <Loading message="Working out the route to market…" />}

      {!loading && !data && (
        <Card>
          <p className="empty-note">
            Search a technology above, or add a technology area to your portfolio to
            plan your own field automatically.
          </p>
          <Link to="/portfolio" className="btn-quiet" style={{ marginTop: 12 }}>
            Go to my portfolio
          </Link>
        </Card>
      )}

      {!loading && data && (
        <>
          <CommercializationView pathway={data.pathway}
                                 recommendations={data.recommendations} />

          <NextRow
            exclude={(data.recommendations || []).map((r) => r.link?.to)}
            items={[
              { key: 'innovation', title: 'Where this comes from',
                note: `Innovation score ${data.innovation_score} · ${data.stage}` },
              { key: 'funding', title: 'Fund the next stage',
                note: 'Grants matched to your profile' },
              { key: 'reports', title: 'Save this as a report',
                note: 'This route to market, as a PDF or a spreadsheet' },
            ]}
          />
        </>
      )}
    </div>
  )
}
