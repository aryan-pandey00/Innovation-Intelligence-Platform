import { useEffect, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts'
import { patentsService, authService, extractErrorMessage } from '../services/api'
import Loading from '../components/Loading'
import EmptyState from '../components/EmptyState'
import FieldChips from '../components/FieldChips'
import { PageHeader, Card, StatCard, StatGrid, RankedList, InfoHint } from '../components/ui'
import {
  CHART_COLORS, axisProps, gridProps, tooltipProps, compactNumber,
  seriesProps, areaGradient, pointLabel,
} from '../components/ui/chartTheme'
import { fmtCount, fmtDate, fmtPct } from '../components/ui/format'
import { byKey } from '../components/modules'

/** Years averaged at each end of the series. */
const WINDOW = 3

/**
 * Change between the first three years of the series and the last three.
 *
 * Endpoint to endpoint is arithmetically correct and also the most flattering of
 * nine available framings — 2015→2025 reads +201% where 2016→2025 reads +257%, a
 * 150-point spread from moving one endpoint. Averaging three years at each end
 * makes the figure independent of where the series happens to start and stop.
 */
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
  const navigate = useNavigate()

  useEffect(() => {
    patentsService.myLandscape()
      .then((res) => { setData(res.data); setQuery(res.data.query); setFields(res.data.profile_fields || []) })
      .catch((err) => {
        if (err.response?.status === 401) { authService.logout(); navigate('/login') }
        // Anything else has to be shown. Without this the page fell through to its
        // "search above" empty card, so a rate-limited data source looked exactly
        // like an empty profile.
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

  // Headline figures worth showing, drawn from the real year counts. Meaningless
  // on a sampled series, so they are only offered when the counts are complete.
  const series = (!data || data.filings_sampled) ? [] : (data.filings_by_year || [])
  const peak = series.length
    ? series.reduce((best, row) => (row.count > best.count ? row : best))
    : null
  const growth = averageGrowth(series)
  // Records with a readable English title: the only ones that can be grouped,
  // and the denominator the shares are of. The heading said `sample_size` while
  // the note below said `of_records` — 1,100 against 1,073 on electric vehicle.
  const grouped = data?.clusters?.[0]?.of_records ?? data?.sample_size ?? 0
  // A leaderboard only exists once the rows carry patents held rather than
  // appearances in our sample. `basis` is set once, in _top_assignees.
  const lead = data?.top_assignees?.[0]
  const holders = lead?.basis === 'corpus'
  const tested = lead?.holders_tested ?? 0
  const resolved = lead?.holders_resolved ?? 0
  const Patents = byKey.patents.Icon
  const Technology = byKey.technology.Icon
  const Trends = byKey.trends.Icon

  return (
    <div className="dashboard">
      <PageHeader trail="Analyse" title="Patent Landscape">
        Who is patenting in a technology, how activity has moved, and the themes
        running through it.
      </PageHeader>

      <form onSubmit={analyze} className="search-row">
        <input placeholder="Map a technology, e.g. lithium battery"
               aria-label="Technology to map"
               value={query} onChange={(e) => setQuery(e.target.value)} />
        <button type="submit">Analyse</button>
      </form>
      <FieldChips fields={fields} active={data?.query} onPick={(f) => analyze(null, f)}
                  label="Your technology areas" fallback={data?.fields_are_fallback} />

      {error && <div className="error">{error}</div>}
      {loading && <Loading message="Mapping the patent landscape…" />}

      {!loading && !data && (
        <Card>
          <p className="empty-note">
            Search a technology above, or add a technology area to your portfolio to map
            your own field automatically.
          </p>
        </Card>
      )}

      {!loading && data && (
        <>
          <StatGrid>
            <StatCard
              value={fmtCount(data.corpus_total ?? data.sample_size)}
              label={data.corpus_total == null ? 'Patents analysed' : 'Matching patents'}
              // "440 read in full for themes" did not say what the two numbers
              // were to each other. This one names the relationship.
              note={data.sample_size > 0
                ? `themes below read from ${fmtCount(data.sample_size)} of them`
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
            {/* No tone: this figure was green because it happened to be positive,
                which spends a colour the app reserves for good-or-bad on something
                that is neither. */}
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
                {/* Six tracks, span-2 cards: five themes lay out 3 + 2 with the second
                    row widened to fill it. Three equal columns left the sixth
                    cell empty, which read as a hole in the set. */}
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
                        {/* Share of the records grouped, which is a real proportion.
                            This used to be size / the largest cluster, so the leading
                            card read 100% by construction. */}
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
                {/* Why the percentages add up is what a reader needs here; the method
                    belongs in the ⓘ. This line used to carry three facts and
                    repeat a number the heading above already gives. */}
                <p className="chart-foot">
                  Each patent joins one theme, so the shares add up to 100%.
                  <InfoHint>
                    Themes come from the classification codes these patents share,
                    and the code beside each one is its subclass in the international
                    patent classification.
                    {grouped < data.sample_size && (() => {
                      // Real on 15 of 23 seeded topics — clean energy groups 393 of
                      // the 440 it reads — and one of them skips exactly one record.
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
                  {/* Patents are teal wherever they are charted, research navy. In the
                      research colour this was indistinguishable from the Trends
                      chart, and it contradicted the momentum chart where the two
                      sit side by side and teach the reader which is which. */}
                  <defs>{areaGradient('filingsFill', CHART_COLORS.patents)}</defs>
                  <CartesianGrid {...gridProps} />
                  <XAxis dataKey="year" {...axisProps} />
                  <YAxis width={46} allowDecimals={false} tickFormatter={compactNumber} {...axisProps} />
                  <Tooltip {...tooltipProps} formatter={(v) => [v.toLocaleString('en-US'), 'Patents']} />
                  {/* fillOpacity 1 — the gradient already fades 18% to 0, and Recharts
                      would otherwise multiply it by its 0.6 default. */}
                  <Area dataKey="count" fill="url(#filingsFill)" fillOpacity={1}
                        {...seriesProps(CHART_COLORS.patents)}
                        label={pointLabel({ data: data.filings_by_year, dataKey: 'count',
                                            color: CHART_COLORS.patents })} />
                </AreaChart>
              </ResponsiveContainer>
            )}
            {/* Split out of the subtitle rather than cut: a sampled series really
                does have gaps, and a reader has to know a missing year means
                "unknown" and not "none". */}
            {data.filings_sampled && data.filings_by_year.length > 0 && (
              <p className="chart-foot">
                Years the sample does not reach are left out, not shown as zero.
              </p>
            )}
          </Card>

          {/* The one place in the app that names patent holders. Technology
              Intelligence used to render this same array, so both pages printed
              the same eight rows and neither was the leaderboard. */}
          <Card
            title={holders ? 'Top patent holders' : 'Organisations filing here'}
            sub={holders
              ? `Patents held across all ${fmtCount(data.corpus_total)} in this field.`
              : `Most frequent applicants across the ${data.sample_size} patents read in full.`}
          >
            {data.top_assignees.length === 0 ? (
              <p className="empty-note">No applicant names available for this query.</p>
            ) : (
              // Bars encode a real spread once the counts are real — 8,877 against
              // 3,676 against 2,959. On sample appearances they only ever drew
              // 6,6,5,5,5,5,4,4 as 100/100/83/83/83/83/67/67, so they stayed off.
              <RankedList items={data.top_assignees} labelKey="assignee"
                          valueKey={holders ? 'corpus_count' : 'count'}
                          shareKey={holders ? 'corpus_share' : undefined}
                          bars={holders || data.top_assignees[0]?.decisive === true} />
            )}
            {/* The caveat sits under the list it applies to, instead of doubling
                the subtitle's length above it. */}
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
                  {/* Clamped to two lines with the whole title on hover: Chinese
                      filings run past 200 characters, and ten of those made this
                      panel a wall of text. */}
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

          <div className="next-row">
            <Link to="/technology" className="next-card">
              <Technology size={18} />
              <span><strong>Check where this sits</strong>Early research or already industrial</span>
            </Link>
            <Link to="/trends" className="next-card">
              <Trends size={18} />
              <span><strong>See the research side</strong>What is published and what is rising</span>
            </Link>
          </div>
        </>
      )}
    </div>
  )
}
