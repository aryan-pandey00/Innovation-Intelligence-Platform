import { useState } from 'react'
import { datasetService, extractErrorMessage } from '../../services/api'
import { fmtDate } from '../ui/format'

export default function DatasetSearch({ kind, onImport }) {
  const [q, setQ] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [importedKeys, setImportedKeys] = useState(new Set())
  const [showResults, setShowResults] = useState(false)
  const source = kind === 'publication' ? 'OpenAlex' : 'Google Patents'
  const noun = kind === 'publication' ? 'publications' : 'patents'

  const search = async (e) => {
    e.preventDefault()
    if (q.trim().length < 2) return
    setLoading(true); setError(''); setResults([]); setShowResults(false)
    try {
      const call = kind === 'publication'
        ? datasetService.searchPublications : datasetService.searchPatents
      const res = await call(q.trim())
      setResults(res.data.results)
      setShowResults(true)
      if (res.data.results.length === 0) setError('No results found.')
    } catch (err) {
      setError(extractErrorMessage(err, `Could not reach ${source}.`))
      setShowResults(true)
    } finally {
      setLoading(false)
    }
  }

  const handleImport = async (rec, key) => {
    await onImport(rec)
    setImportedKeys((prev) => new Set(prev).add(key))
  }

  const closeResults = () => {
    setResults([]); setError(''); setShowResults(false); setImportedKeys(new Set())
  }

  return (
    <div className="dataset-search">
      <form className="search-bar" onSubmit={search}>
        <input value={q} onChange={(e) => setQ(e.target.value)}
               aria-label={`Search for your ${noun} to import`}
               placeholder={`Search by title or author to import your ${noun}`} />
        <button type="submit" disabled={loading}>{loading ? 'Searching…' : 'Search'}</button>
      </form>

      {showResults && (
        <div className="search-results-panel">
          <div className="search-results-header">
            <span className="results-count">
              {results.length > 0
                ? `${results.length} result${results.length !== 1 ? 's' : ''}`
                : 'No results'}
            </span>
            <button type="button" className="close-results-btn" onClick={closeResults}>
              Close
            </button>
          </div>

          {error && <p className="empty-note">{error}</p>}

          <div className="results-scroll">
            {results.map((r, i) => {
              const key = (kind === 'publication' ? r.doi : r.patent_number) || `${i}-${r.title}`
              const imported = importedKeys.has(key)
              return (
                <div key={key} className="result">
                  <div>
                    <strong>{r.title}</strong>
                    <div className="muted">
                      {kind === 'publication'
                        ? [(r.authors || []).slice(0, 3).join(', '), r.venue, r.year,
                           r.citation_count ? `${r.citation_count} citations` : null]
                            .filter(Boolean).join(' · ')
                        : [r.patent_number, r.assignee,
                           r.filing_date ? `filed ${fmtDate(r.filing_date)}` : null]
                            .filter(Boolean).join(' · ')}
                    </div>
                  </div>
                  <button type="button" className="mini-import" disabled={imported}
                          onClick={() => handleImport(r, key)}>
                    {imported ? '✓ Added' : 'Add'}
                  </button>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
