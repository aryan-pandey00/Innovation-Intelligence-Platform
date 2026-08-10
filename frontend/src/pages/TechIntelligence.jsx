import { useEffect, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import {
  ResponsiveContainer, ComposedChart, Area, Line, XAxis, YAxis, Tooltip,
  CartesianGrid, Legend,
} from 'recharts'
import { technologyService, authService, extractErrorMessage } from '../services/api'
import Loading from '../components/Loading'
import FieldChips from '../components/FieldChips'
import { PageHeader, Card, StatCard, StatGrid, InfoHint } from '../components/ui'
import {
  CHART_COLORS, axisProps, gridProps, tooltipProps, seriesProps, areaGradient,
  pointLabel, compactNumber,
} from '../components/ui/chartTheme'
import { fmtCount, fmtPct } from '../components/ui/format'
import { byKey } from '../components/modules'

const STAGES = ['Emerging', 'Growing', 'Mature']
// The backend also returns "Developing" when patent data is missing, which is
// not a point on the lifecycle — it means the lifecycle could not be placed.
const UNPLACED = 'Developing'

// What the patent number actually counts differs by source, so say so rather
// than showing two incomparable figures under one label.
const countBasis = (d) => {
  if (d.patent_counts_source === 'epo_ops') {
    // "title or abstract" names our query, not the reader's answer. The precise
    // wording lives in this card's ⓘ, which is where method belongs.
    return d.patent_query_basis === 'cpc'
      ? 'by classification · EPO worldwide'
      : 'by name · EPO worldwide'
  }
  if (!d.patent_total_exact) return 'approximate — refresh for an exact count'
  return 'full text · Google Patents'
}

/* The 0-100 opportunity score is not shown: it is a balance centred on 50, and a
   number out of 100 reads as a mark, so an evenly-growing field looked like a
   failure at 46. The multiplier it stood in for needs no scale. */
const BALANCE = {
  research: { label: 'Research is ahead', tone: 'good' },
  patents: { label: 'Patenting is ahead', tone: 'warn' },
  even: { label: 'Neck and neck', tone: undefined },
}

// Each says what the band means for the reader, and each has to stand on its own:
// the name list these used to point at ("the filings below", "the names below")
// lives on the patent landscape now.
const VERDICT = {
  concentrated: 'A few holders set the direction, so check their filings first.',
  mixed: 'There is room to enter, but the largest holders are worth designing around.',
  fragmented: 'No one owns this field yet.',
}

/* Segments under this are a sliver nobody can see, yet they still claimed a full
   legend entry. Folded into one "Other" that names what is in it. */
const MIX_MIN_SHARE = 4

function foldMix(mix) {
  const small = mix.filter((m) => m.share < MIX_MIN_SHARE)
  // Folding a single item just renames it — "Organisation 1%" would become
  // "Other 1%", which says less for the same width. Only worth doing when it
  // actually merges something.
  if (small.length < 2) return mix
  return [...mix.filter((m) => m.share >= MIX_MIN_SHARE), {
    kind: 'Other',
    share: small.reduce((n, m) => n + m.share, 0),
    detail: small.map((m) => `${m.share}% ${m.kind.toLowerCase()}`).join(', '),
  }]
}

/* How the field is held, not who holds it. The name list here rendered the same
   array as Patent Landscape, so both pages showed identical rows. This card keeps
   only what that one cannot say: how many, how concentrated, what kind. */
function Ownership({ data }) {
  const own = data.ownership
  if (!own?.organisations) return null
  const mix = foldMix(own.mix || [])

  return (
    <Card title="How ownership is spread">
      <p className="ip-finding">
        <strong>{fmtCount(own.organisations)} organisations</strong> across the{' '}
        {fmtCount(own.records)} patents read.{' '}
        {/* The count leads, the share supports it: quoting only the share made the
            reader multiply two numbers to reach the claim. The share stays because
            it is what makes the verdict follow — under 2% for the largest holder is
            a wide-open field. Only ever a share of the corpus; from the sample it
            fell as 1/sample-size and measured our own sampling. */}
        {own.top_share != null && own.top_holder && (
          <><strong>{own.top_holder}</strong> holds the most:{' '}
            <strong>{fmtCount(own.top_count)} patents</strong>, {own.top_share}% of
            the field. </>
        )}
        {VERDICT[own.verdict]}
      </p>

      {mix.length > 0 && (
        <>
          {/* A proportion strip, not a chart: no axes, and it shows a
              part-to-whole relationship a list cannot. */}
          <div className="ip-strip" role="img"
               aria-label={mix.map((m) => `${m.share}% ${m.kind}`).join(', ')}>
            {mix.map((m, i) => (
              <span key={m.kind} className={`ip-seg ip-seg-${i}`} style={{ width: `${m.share}%` }} />
            ))}
          </div>
          <ul className="ip-legend">
            {mix.map((m, i) => (
              <li key={m.kind}>
                <span className={`ip-dot ip-seg-${i}`} aria-hidden="true" />
                <strong>{m.share}%</strong> {m.kind}
                {m.detail && <InfoHint>{m.detail}</InfoHint>}
              </li>
            ))}
          </ul>
        </>
      )}

      <p className="chart-foot">
        {/* Says what the percentages are rather than what they are not, and does
            not repeat the organisation count from the sentence above it. */}
        Each organisation counts once, whether it holds one patent or thousands.
        <InfoHint>
          {`So this shows what kind of players are in the field, not how much of it `
           + `they own. Taken from the ${fmtCount(own.records)} patents read in full.`}
        </InfoHint>
        <Link to="/patents" className="inline-link link-block">
          See the top holders by name →
        </Link>
      </p>
    </Card>
  )
}

export default function TechIntelligence() {
  const [query, setQuery] = useState('')
  const [fields, setFields] = useState([])
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    technologyService.myIntelligence()
      .then((res) => { setData(res.data); setQuery(res.data.query); setFields(res.data.profile_fields || []) })
      .catch((err) => {
        if (err.response?.status === 401) { authService.logout(); navigate('/login') }
        // Anything else has to be shown. Without this the page fell through to its
        // "search above" empty card, so a rate-limited data source looked exactly
        // like an empty profile.
        else setError(extractErrorMessage(err, 'Could not load technology intelligence'))
      })
      .finally(() => setLoading(false))
  }, [navigate])

  const analyze = async (e, term) => {
    e?.preventDefault()
    const q = (term ?? query).trim()
    if (q.length < 2) return
    setQuery(q); setLoading(true); setError('')
    try {
      const res = await technologyService.intelligence(q)
      setData(res.data)
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not load technology intelligence'))
    } finally {
      setLoading(false)
    }
  }

  const activeStage = data ? STAGES.indexOf(data.stage) : -1
  // Only worth explaining the joined line when there is actually a join to explain.
  const gapYears = (data?.activity_trend || []).filter((t) => t.patents == null).length
  const unplaced = data?.stage === UNPLACED
  const Innovation = byKey.innovation.Icon
  const Patents = byKey.patents.Icon

  return (
    <div className="dashboard">
      <PageHeader trail="Analyse" title="Technology Intelligence">
        Where a technology sits between early research and mature industry —
        measured on both sides.
      </PageHeader>

      <form onSubmit={analyze} className="search-row">
        <input placeholder="Assess a technology, e.g. solid-state battery"
               aria-label="Technology to assess"
               value={query} onChange={(e) => setQuery(e.target.value)} />
        <button type="submit">Analyse</button>
      </form>
      <FieldChips fields={fields} active={data?.query} onPick={(f) => analyze(null, f)}
                  label="Your technology areas" fallback={data?.fields_are_fallback} />

      {error && <div className="error">{error}</div>}
      {loading && <Loading message="Assessing technology maturity…" />}

      {!loading && !data && (
        <Card>
          <p className="empty-note">
            Assess a technology above, or add technology areas to your portfolio to
            evaluate your field automatically.
          </p>
        </Card>
      )}

      {!loading && data && (
        <>
          {!data.patents_available && (
            <div className="notice">
              Patent data is unavailable right now, so the lifecycle is placed from
              research signals alone.
            </div>
          )}
          {data.patent_count_low_confidence && (
            <div className="notice">
              Only {fmtCount(data.patent_total)} patents name “{data.query}” in their title or
              abstract. Patents describe mechanisms rather than research fields, so read the
              patent figures below as a floor rather than a measurement.
            </div>
          )}

          {/* A single track with the position filled, not three boxes with one
              selected: the heading is the label and the track carries the value,
              the same split the stat cards use, so the stage word appears once. */}
          {/* Says what the stage is actually read from. It claimed "research output
              and patent activity together", but patents only decide whether the
              question can be answered at all — see tech_intelligence._stage. */}
          <Card title="Lifecycle stage"
                sub="Read from how fast the research is growing and how large the field already is">
            {unplaced ? (
              <p className="empty-note">
                Not enough patent data to place this technology on the lifecycle.
              </p>
            ) : (
              <div className="track" role="img"
                   aria-label={`Lifecycle stage: ${data.stage} of ${STAGES.join(', ')}`}>
                <span className="track-line" aria-hidden="true">
                  <span className="track-fill"
                        style={{ width: `${(activeStage / (STAGES.length - 1)) * 100}%` }} />
                </span>
                {STAGES.map((s, i) => (
                  <span key={s} className={`track-point${i <= activeStage ? ' reached' : ''}${i === activeStage ? ' here' : ''}`}>
                    <span className="track-dot" aria-hidden="true" />
                    <span className="track-label">{s}</span>
                  </span>
                ))}
              </div>
            )}
            <p className="stage-reason">{data.stage_reason}</p>
          </Card>

          <StatGrid>
            {/* Method lives in the ⓘ; the note says where the number came from. */}
            <StatCard
              value={fmtCount(data.research_total)}
              label="Research papers"
              note="OpenAlex"
              hint="Papers whose title or abstract names this technology."
            />
            <StatCard
              value={data.patents_available ? fmtCount(data.patent_total) : '—'}
              label="Patents"
              note={data.patents_available ? countBasis(data) : undefined}
              hint={'Research and patent totals count different things. Patents are '
                    + 'matched by classification where a mapping exists, otherwise by '
                    + 'title or abstract — the note says which.'}
            />
            {/* Papers per patent used to fill this slot when the score could not
                be computed. It divided two counts measured different ways, so it
                is gone rather than replaced — two cards is honest. */}
            {data.opportunity_balance && (
              <StatCard
                // "1.3x" cannot be misread as a mark; "36" always was.
                value={`${data.opportunity_balance.factor}×`}
                label={BALANCE[data.opportunity_balance.lead].label}
                tone={BALANCE[data.opportunity_balance.lead].tone}
                note={`research ${fmtPct(data.research_growth, { sign: true })} `
                      + `vs patents ${fmtPct(data.patent_growth, { sign: true })}`}
                hint={'How fast the research and the patenting are growing, compared. '
                      + 'When research is ahead, more of the science is still unpatented '
                      + 'and there is room to file. When patenting is ahead, others are '
                      + 'claiming the ground first. A rough guide: we find papers by name '
                      + 'and patents mostly by their official subject code, so the two are '
                      + 'not counted in quite the same way.'}
              />
            )}
          </StatGrid>

          <Card
            title="Activity momentum"
            sub="Research and patent activity over time, each scaled to its own busiest year"
          >
            <ResponsiveContainer width="100%" height={290}>
              <ComposedChart data={data.activity_trend} margin={{ top: 18, right: 14, left: 0, bottom: 0 }}>
                <defs>
                  {areaGradient('momentumResearch', CHART_COLORS.research)}
                  {areaGradient('momentumPatents', CHART_COLORS.patents)}
                </defs>
                <CartesianGrid {...gridProps} />
                <XAxis dataKey="year" {...axisProps} />
                <YAxis width={38} domain={[0, 100]} {...axisProps} />
                {/* The axis is a percentage of each series' own peak, so "54" on
                    its own says nothing. The tooltip and the labels give what was
                    actually counted that year. */}
                <Tooltip {...tooltipProps} formatter={(v, name, item) => {
                  const real = item?.payload?.[name === 'Research' ? 'research_count' : 'patent_count']
                  return [real == null ? '—'
                    : `${fmtCount(real)} (${v}% of its peak)`, name]
                }} />
                <Legend iconType="plainline" wrapperStyle={{ fontSize: 13, paddingTop: 8 }} />

                {/* Two bare strokes left the lower two-thirds of the card empty. At
                    this opacity the overlap reads as a deeper band, not mud. Legend
                    and tooltip come from the lines, not from these. */}
                <Area dataKey="research" stroke="none" fill="url(#momentumResearch)"
                      fillOpacity={1} connectNulls isAnimationActive={false}
                      legendType="none" tooltipType="none" activeDot={false} />
                <Area dataKey="patents" stroke="none" fill="url(#momentumPatents)"
                      fillOpacity={1} connectNulls isAnimationActive={false}
                      legendType="none" tooltipType="none" activeDot={false} />

                {/* The line runs continuously, and because a dot is only drawn where a
                    value exists, a stretch without dots IS the marker for an
                    unmeasured span — no invented point, no broken stroke. */}
                {/* Labelled with the real count, not the plotted percentage: "100"
                    told the reader nothing they could take away. Compact here,
                    full precision in the tooltip, as everywhere else. */}
                <Line dataKey="research" name="Research"
                      connectNulls {...seriesProps(CHART_COLORS.research)}
                      label={pointLabel({ data: data.activity_trend, dataKey: 'research',
                                          format: (v, i) => compactNumber(
                                            data.activity_trend[i]?.research_count ?? v),
                                          color: CHART_COLORS.research })} />
                <Line dataKey="patents" name="Patents"
                      connectNulls {...seriesProps(CHART_COLORS.patents)}
                      label={pointLabel({ data: data.activity_trend, dataKey: 'patents',
                                          format: (v, i) => compactNumber(
                                            data.activity_trend[i]?.patent_count ?? v),
                                          color: CHART_COLORS.patents })} />
              </ComposedChart>
            </ResponsiveContainer>
            {/* Provenance only. What went was restating the card's own subtitle and
                explaining gaps most terms do not have; the filing-lag reasoning
                sits behind the ⓘ. */}
            {(data.patents_available || gapYears > 0) && (
              <p className="chart-foot">
                {data.patent_history_reliable ? (
                  <>Complete EPO counts, not a sample.
                    <InfoHint>
                      Counted by publication year, so the latest year is not dragged
                      down by the wait between filing a patent and its publication.
                    </InfoHint>
                  </>
                ) : data.patents_available && (
                  <>Patents come from a {fmtCount(data.patent_sample_size)}-record
                    sample, so the shape is real but the totals are not.</>
                )}
                {gapYears > 0 && (
                  <> {gapYears} year{gapYears === 1 ? ' has' : 's have'} no patent
                    data; the line simply joins across {gapYears === 1 ? 'it' : 'them'}.</>
                )}
              </p>
            )}
          </Card>

          <Ownership data={data} />

          {/* The page used to end on the assignee panel with nowhere to go. */}
          <div className="next-row">
            <Link to="/innovation" className="next-card">
              <Innovation size={18} />
              <span><strong>Score this technology</strong>Your position, weighted</span>
            </Link>
            <Link to="/patents" className="next-card">
              <Patents size={18} />
              <span><strong>See the technology themes</strong>What is being filed, grouped</span>
            </Link>
          </div>
        </>
      )}
    </div>
  )
}
