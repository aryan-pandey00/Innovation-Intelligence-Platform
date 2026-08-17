import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts'
import { patentsService, authService, extractErrorMessage } from '../services/api'
import Loading from '../components/Loading'
import EmptyState from '../components/EmptyState'
import FieldChips from '../components/FieldChips'
import NextRow from '../components/NextRow'
import OwnFieldNote from '../components/OwnFieldNote'
import { useSession } from '../services/session'
import { usePipelineFields } from '../hooks'
import { PageHeader, Card, StatCard, StatGrid, RankedList, InfoHint } from '../components/ui'
import {
  CHART_COLORS, axisProps, gridProps, tooltipProps, compactNumber,
  seriesProps, areaGradient, pointLabel,
} from '../components/ui/chartTheme'
import { fmtCount, fmtDate, fmtPct } from '../components/ui/format'
import { byKey } from '../components/modules'

const WINDOW = 3

function averageGrowth(series) {
  if (series.length < WINDOW * 2) return null
  const mean = (rows) => rows.reduce((sum, r) => sum + r.count, 0) / rows.length
  const from = series.slice(0, WINDOW)
  const to = series.slice(-WINDOW)
  const early = mean(from)
  const late = mean(to)
  if (!early) return null
  const span = (rows) => `${rows[0].year}–${String(rows[rows.length - 1].year).slice(2)}`
  return {
    pct: Math.round(((late - early) / early) * 100),
    note: `${span(from)} avg ${fmtCount(Math.round(early))} → ${span(to)} avg ${fmtCount(Math.round(late))}`,
  }
}

export default function PatentLandscape() {
  const [query, setQuery] = useState('')
  const [fields, setFields] = useState([])
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [noOwnField, setNoOwnField] = useState(false)
  const navigate = useNavigate()
  const { role } = useSession()
  const pipelineFields = usePipelineFields(role)

  useEffect(() => {
    patentsService.myLandscape()
      .then((res) => { setData(res.data); setQuery(res.data.query); setFields(res.data.profile_fields || []) })
      .catch((err) => {
        if (err.response?.status === 401) { authService.logout(); navigate('/login') }
        else if (err.response?.status === 400) setNoOwnField(true)
        else setError(extractErrorMessage(err, 'Could not load patent landscape'))
      })
      .finally(() => setLoading(false))
  }, [navigate])

  const analyze = async (e, term) => {
    e?.preventDefault()
    const q = (term ?? query).trim()
    if (q.length < 2) return
    setQuery(q); setLoading(true); setError('')
    try {
      const res = await patentsService.landscape(q)
      setData(res.data)
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not load patent landscape'))
    } finally {
      setLoading(false)
    }
  }

  const series = (!data || data.filings_sampled) ? [] : (data.filings_by_year || [])
  const peak = series.length
    ? series.reduce((best, row) => (row.count > best.count ? row : best))
    : null
  const growth = averageGrowth(series)
  const grouped = data?.clusters?.[0]?.of_records ?? data?.sample_size ?? 0
  const lead = data?.top_assignees?.[0]
  const holders = lead?.basis === 'corpus'
  const tested = lead?.holders_tested ?? 0
  const resolved = lead?.holders_resolved ?? 0
  const Patents = byKey.patents.Icon

  return (
    <div className="dashboard">
      <PageHeader trail="Analyse" title="Patent Landscape">
        Who is patenting in a technology, how activity has moved, and the themes
        running through it.
      </PageHeader>

      <form onSubmit={analyze} className="search-row">
        <input placeholder="Map a technology, e.g. lithium battery" maxLength={200}
               aria-label="Technology to map"
               value={query} onChange={(e) => setQuery(e.target.value)} />
        <button type="submit">Analyse</button>
      </form>
      <FieldChips fields={fields.length ? fields : pipelineFields}
                  active={data?.query} onPick={(f) => analyze(null, f)}
                  label={fields.length ? 'Your technology areas'
                                       : 'Fields your innovators work in'}
                  fallback={fields.length ? data?.fields_are_fallback : false} />

      {error && <div className="error">{error}</div>}
      {loading && <Loading message="Mapping the patent landscape…" />}

      {!loading && !data && (
        <Card>
          <OwnFieldNote
            role={role}
            verb="map"
            detail={noOwnField
              ? 'Search a technology above to map it, or add a technology area to '
                + 'your portfolio and this page will map your own field automatically.'
              : undefined}
          />
        </Card>
      )}

      {!loading && data && (
        <>
          <StatGrid>
            <StatCard
              value={fmtCount(data.corpus_total ?? data.sample_size)}
              label={data.corpus_total == null ? 'Patents analysed' : 'Matching patents'}
              note={grouped > 0
                ? `themes below read from ${fmtCount(grouped)} of them`
                : 'counts only — no sample available'}
              hint={data.sample_balanced
                ? `The count covers every matching patent. Reading them all is not
                   possible — the source serves 100 records per request — so
                   ${fmtCount(data.sample_size)} were downloaded evenly across the years
                   to group themes and name organisations.`
                : `Counts cover every match; themes come from a
                   ${fmtCount(data.sample_size)}-patent sample.`}
            />
            <StatCard
              value={peak ? peak.year : '—'}
              label="Busiest year"
              note={peak ? `${fmtCount(peak.count)} patents published` : 'needs complete year counts'}
            />
            <StatCard
              value={growth ? fmtPct(growth.pct, { sign: true }) : '—'}
              label={series.length ? `Change over ${series.length} years` : 'Change over time'}
              note={growth ? growth.note : 'needs complete year counts'}
              hint="Three years averaged at each end, so the figure does not swing on
                    whichever single year the counts start on."
            />
          </StatGrid>

          <Card
            title={<><Patents size={17} /> Innovation Map</>}
            className="cluster-block"
            sub={`${fmtCount(grouped)} patents grouped by shared classification`
                 + `${data.sample_balanced ? ', sampled evenly across years' : ''}.`}
          >
            {data.clusters.length === 0 ? (
              <p className="empty-note">Not enough data to group themes for this query.</p>
            ) : (
              <>
                <div className="cluster-grid">
                  {data.clusters.map((c) => (
                    <article key={c.label} className="cluster-card">
                      <header className="cluster-head">
                        <div>
                          <strong>{c.label}</strong>
                          {c.code && <span className="cluster-code">{c.code}</span>}
                          {c.terms?.length > 0 && (
                            <span className="cluster-terms">{c.terms.join(' · ')}</span>
                          )}
                        </div>
                        <span className="cluster-size">
                          {c.share != null ? `${c.share}%` : c.size}
                          <small>{fmtCount(c.size)} patents</small>
                        </span>
                      </header>
                      <ul className="cluster-samples">
                        {c.samples.map((s, j) => <li key={j} title={s}>{s}</li>)}
                      </ul>
                    </article>
                  ))}
                </div>
                <p className="chart-foot">
                  Each patent joins one theme, so the shares add up to 100%.
                  <InfoHint>
                    Themes come from the classification codes these patents share,
                    and the code beside each one is its subclass in the international
                    patent classification.
                    {grouped < data.sample_size && (() => {
                      const skipped = data.sample_size - grouped
                      return ` ${fmtCount(skipped)} of the ${fmtCount(data.sample_size)} `
                        + `patents read ${skipped === 1 ? 'has' : 'have'} no readable `
                        + `English title, so ${skipped === 1 ? 'it' : 'they'} cannot `
                        + 'be grouped.'
                    })()}
                  </InfoHint>
                </p>
              </>
            )}
          </Card>

          <Card
            title="Patent filing trend"
            sub={data.filings_sampled
              ? `Filed per year within the ${data.sample_size} analysed patents — shape, not volume.`
              : `Published per year across all ${fmtCount(data.corpus_total)} EPO matches — not a sample.`}
          >
            {data.filings_by_year.length === 0 ? (
              <p className="empty-note">No dated patents available for this query.</p>
            ) : (
              <ResponsiveContainer width="100%" height={290}>
                <AreaChart data={data.filings_by_year} margin={{ top: 18, right: 12, left: 0, bottom: 0 }}>
                  <defs>{areaGradient('filingsFill', CHART_COLORS.patents)}</defs>
                  <CartesianGrid {...gridProps} />
                  <XAxis dataKey="year" {...axisProps} />
                  <YAxis width={46} allowDecimals={false} tickFormatter={compactNumber} {...axisProps} />
                  <Tooltip {...tooltipProps} formatter={(v) => [v.toLocaleString('en-US'), 'Patents']} />
                  <Area dataKey="count" fill="url(#filingsFill)" fillOpacity={1}
                        {...seriesProps(CHART_COLORS.patents)}
                        label={pointLabel({ data: data.filings_by_year, dataKey: 'count',
                                            color: CHART_COLORS.patents })} />
                </AreaChart>
              </ResponsiveContainer>
            )}
            {data.filings_sampled && data.filings_by_year.length > 0 && (
              <p className="chart-foot">
                Years the sample does not reach are left out, not shown as zero.
              </p>
            )}
          </Card>

          <Card
            title={holders ? 'Top patent holders' : 'Organisations filing here'}
            sub={holders
              ? `Patents held across all ${fmtCount(data.corpus_total)} in this field.`
              : `Most frequent applicants across the ${data.sample_size} patents read in full.`}
          >
            {data.top_assignees.length === 0 ? (
              <p className="empty-note">No applicant names available for this query.</p>
            ) : (
              <RankedList items={data.top_assignees} labelKey="assignee"
                          valueKey={holders ? 'corpus_count' : 'count'}
                          shareKey={holders ? 'corpus_share' : undefined}
                          bars={holders || data.top_assignees[0]?.decisive === true} />
            )}
            {holders ? (
              <p className="chart-foot">
                Ranked by patents held, not by how often each appears in our sample.
                <InfoHint>
                  {`Candidates come from the ${fmtCount(data.sample_size)} patents read `
                   + `in full; the ${fmtCount(tested)} that appear most often were then `
                   + 'counted across the whole field.'
                   + (resolved < tested
                     ? ` ${fmtCount(tested - resolved)} could not be matched to a field `
                       + 'total and are left out.' : '')
                   + ' An organisation that files too rarely to reach the sample can be '
                   + 'missing from this list.'}
                </InfoHint>
              </p>
            ) : data.top_assignees.length > 0 && !data.top_assignees[0]?.decisive && (
              <p className="chart-foot">
                The counts sit close together, so read this as who is present, not a ranking.
              </p>
            )}
          </Card>

          <Card
            title="Recent patents"
            sub={data.sample_date_kind === 'publication'
              ? 'The five most recently published, one per family'
              : 'The five most recently filed, one per family'}
          >
            {data.top_patents.length === 0 ? (
              <EmptyState>No patents found for this query.</EmptyState>
            ) : (
              data.top_patents.map((p, i) => (
                <div key={i} className="patent-row">
                  <a href={p.url} target="_blank" rel="noreferrer"
                     className="patent-title" title={p.title}>{p.title}</a>
                  <div className="patent-meta">
                    {[p.patent_number, p.assignee,
                      (p.publication_date || p.filing_date) &&
                        `${p.publication_date ? 'published' : 'filed'} `
                        + fmtDate(p.publication_date || p.filing_date)]
                      .filter(Boolean).join(' · ')}
                  </div>
                </div>
              ))
            )}
          </Card>

          <NextRow items={[
            { key: 'technology', title: 'Check where this sits',
              note: 'Early research or already industrial' },
            { key: 'trends', title: 'See the research side',
              note: 'What is published and what is rising' },
          ]} />
        </>
      )}
    </div>
  )
}
