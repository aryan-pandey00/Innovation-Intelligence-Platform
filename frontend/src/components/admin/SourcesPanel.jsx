import { useEffect, useState } from 'react'

import { adminService } from '../../services/api'
import Loading from '../Loading'
import { Card, InfoHint, StatCard, StatGrid } from '../ui'
import { fmtCount } from '../ui/format'

const readable = (slug) => slug.replace(/-/g, ' ')

export default function SourcesPanel() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [showAll, setShowAll] = useState(false)

  useEffect(() => {
    adminService.dataHealth()
      .then((res) => setData(res.data))
      .catch(() => setError('Could not read the data caches.'))
  }, [])

  if (error) return <div className="error">{error}</div>
  if (!data) return <Loading message="Reading the data caches…" />

  const { cached, sources, gaps, topics } = data
  const missingKey = sources.filter((s) => s.needs_key && !s.configured)
  const wanted = new Set(gaps.map((g) => g.slug))
  const exceptions = topics.filter((t) => wanted.has(t.slug) || !t.has_series)
  const rows = showAll ? topics : exceptions

  return (
    <>
      <p className="ip-finding">
        {cached.unseeded_but_named > 0 ? (
          <>
            <strong>{cached.unseeded_but_named} of the {cached.named_by_a_portfolio}{' '}
              technology areas</strong> named across the platform's portfolios have
            no cached patent data, so Patent Landscape and Technology Intelligence
            are empty for those users.
          </>
        ) : (
          <>
            All <strong>{cached.named_by_a_portfolio} technology areas</strong> named
            across the platform's portfolios have cached patent data behind them.
          </>
        )}
        {missingKey.length > 0 && (
          <> {missingKey.map((s) => s.name).join(', ')} {missingKey.length === 1
            ? 'has no credentials configured' : 'have no credentials configured'},
            so those topics cannot be re-seeded.</>
        )}
      </p>

      <StatGrid>
        <StatCard value={cached.with_corpus} label="Topics with a real corpus"
                  note="real per-year counts behind them" />
        <StatCard value={cached.fallback_only} label="Fallback data only"
                  tone={cached.fallback_only ? 'warn' : undefined}
                  note="no seeded sample, so no year series" />
        <StatCard value={cached.low_confidence} label="Field size is a floor"
                  note="phrase-matched, so the real total is higher" />
        <StatCard value={cached.unseeded_but_named} label="Named but unseeded"
                  tone={cached.unseeded_but_named ? 'warn' : undefined}
                  note={`of ${cached.named_by_a_portfolio} fields in use`} />
      </StatGrid>
      <p className="chart-foot">
        {cached.total} topics cached.
        {cached.series_without_sample > 0 && (
          ` ${cached.series_without_sample} count toward both of the first two figures:`
          + ' their field size is known but there is no sample to read inside it.'
        )}
      </p>

      <Card title="External sources"
            sub="What each one feeds, and whether it is configured">
        <ul className="metric-rows">
          {sources.map((s) => (
            <li key={s.key}>
              <span className="metric-label">{s.name}</span>
              <span className="metric-value">
                <span className={`state-pill ${s.needs_key
                  ? (s.configured ? 'state-ok' : 'state-off') : 'state-ok'}`}>
                  {s.needs_key ? (s.configured ? 'Configured' : 'No credentials')
                               : 'No key needed'}
                </span>
              </span>
              <span className="metric-note">{s.used_by} · {s.detail}</span>
            </li>
          ))}
        </ul>
        <p className="chart-foot">
          Configuration only. Whether a source is answering right now is not shown:
          finding out would mean calling it, and these pages are database-only
          precisely so a rate-limited source cannot take the dashboard down.
        </p>
      </Card>

      {gaps.length > 0 && (
        <Card title="Fields with nothing to analyse"
              sub="Named by a portfolio, but with no cached patent data">
          <ul className="metric-rows">
            {gaps.map((g) => (
              <li key={g.slug}>
                <span className="metric-label">{readable(g.slug)}</span>
                <span className="metric-value">
                  {g.portfolios} portfolio{g.portfolios === 1 ? '' : 's'}
                </span>
              </li>
            ))}
          </ul>
          <p className="chart-foot">
            Seed a topic with <code>python -m scripts.seed_patent_series</code>.
            Each takes minutes, because the patent office paces searches to a few
            per minute.
          </p>
        </Card>
      )}

      <Card
        title={`Cached patent topics (${topics.length})`}
        sub={showAll
          ? 'Every cached topic, alphabetically'
          : `${exceptions.length} worth a look — named by a portfolio, or without a real corpus`}
        aside={(
          <button className="mini-view" aria-expanded={showAll}
                  onClick={() => setShowAll((v) => !v)}>
            {showAll ? 'Show exceptions' : `Show all ${topics.length}`}
          </button>
        )}
      >
        <div className="table-wrap">
          <table className="user-table">
            <thead>
              <tr>
                <th>Topic</th>
                <th>
                  Field size
                  <InfoHint>
                    Patents in the field, from the patent office's own count. Blank
                    where only fallback data exists, which cannot give a total.
                  </InfoHint>
                </th>
                <th>Years</th>
                <th>Matched by</th>
                <th>Holders</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((t) => (
                <tr key={t.slug}>
                  <td>
                    {readable(t.slug)}
                    {wanted.has(t.slug) && <span className="super-tag">In use</span>}
                  </td>
                  <td>
                    {t.corpus_total != null ? fmtCount(t.corpus_total)
                      : <span className="cell-note">no corpus</span>}
                    {t.low_confidence && <span className="cell-note"> · a floor</span>}
                  </td>
                  <td>{t.years || <span className="cell-note">—</span>}</td>
                  <td className="cell-note">{t.query_basis || 'fallback'}</td>
                  <td className="cell-note">
                    {t.holder_basis === 'corpus' ? 'real counts'
                      : t.holder_basis === 'sample' ? 'sample only' : '—'}
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr><td colSpan={5} className="cell-note">
                  Every cached topic has a real corpus behind it.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
        <p className="table-foot">
          Patent dates are publication dates, not filing dates. A derived cache
          written by an older analysis version rebuilds itself on the next request.
        </p>
      </Card>
    </>
  )
}
