import { useEffect, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import {
  ResponsiveContainer, ComposedChart, Area, Line, XAxis, YAxis, Tooltip,
  CartesianGrid, Legend,
} from 'recharts'
import { technologyService, authService, extractErrorMessage } from '../services/api'
import Loading from '../components/Loading'
import FieldChips from '../components/FieldChips'
import NextRow from '../components/NextRow'
import OwnFieldNote from '../components/OwnFieldNote'
import { useSession } from '../services/session'
import { usePipelineFields } from '../hooks'
import { PageHeader, Card, StatCard, StatGrid, InfoHint } from '../components/ui'
import {
  CHART_COLORS, axisProps, gridProps, tooltipProps, seriesProps, areaGradient,
  pointLabel, compactNumber,
} from '../components/ui/chartTheme'
import { fmtCount, fmtPct } from '../components/ui/format'
import { skipMotion, useCountUp } from '../components/ui/motion'

const STAGES = ['Emerging', 'Growing', 'Mature']
const UNPLACED = 'Developing'

const stagePct = (i) => Math.round((i / (STAGES.length - 1)) * 100)

const LEAD_MS = 260

function StageTrack({ stage, index }) {
  const swept = useCountUp(stagePct(index), LEAD_MS)
  const [begun, setBegun] = useState(() => skipMotion())

  useEffect(() => {
    if (skipMotion()) { setBegun(true); return undefined }
    setBegun(false)
    const t = setTimeout(() => setBegun(true), LEAD_MS)
    return () => clearTimeout(t)
  }, [index])

  return (
    <div className="track" role="img"
         aria-label={`Lifecycle stage: ${stage} of ${STAGES.join(', ')}`}>
      <span className="track-line" aria-hidden="true">
        <span className="track-fill" style={{ width: `${swept}%` }} />
      </span>
      {STAGES.map((s, i) => {
        const reached = begun && swept >= stagePct(i)
        return (
          <span key={s} className={`track-point${reached ? ' reached' : ''}`
                                   + `${reached && i === index ? ' here' : ''}`}>
            <span className="track-dot" aria-hidden="true" />
            <span className="track-label">{s}</span>
          </span>
        )
      })}
    </div>
  )
}

const countBasis = (d) => {
  if (d.patent_counts_source === 'epo_ops') {
    return d.patent_query_basis === 'cpc'
      ? 'by classification · EPO worldwide'
      : 'by name · EPO worldwide'
  }
  if (!d.patent_total_exact) return 'approximate — refresh for an exact count'
  return 'full text · Google Patents'
}

const BALANCE = {
  research: { label: 'Research is ahead', tone: 'good' },
  patents: { label: 'Patenting is ahead', tone: 'warn' },
  even: { label: 'Neck and neck', tone: undefined },
}

const VERDICT = {
  concentrated: 'A few holders set the direction, so check their filings first.',
  mixed: 'There is room to enter, but the largest holders are worth designing around.',
  fragmented: 'No one owns this field yet.',
}

const MIX_MIN_SHARE = 4

function foldMix(mix) {
  const small = mix.filter((m) => m.share < MIX_MIN_SHARE)
  if (small.length < 2) return mix
  return [...mix.filter((m) => m.share >= MIX_MIN_SHARE), {
    kind: 'Other',
    share: small.reduce((n, m) => n + m.share, 0),
    detail: small.map((m) => `${m.share}% ${m.kind.toLowerCase()}`).join(', '),
  }]
}

function Ownership({ data }) {
  const own = data.ownership
  if (!own?.organisations) return null
  const mix = foldMix(own.mix || [])

  return (
    <Card title="How ownership is spread">
      <p className="ip-finding">
        <strong>{fmtCount(own.organisations)} organisations</strong> appear in the{' '}
        {fmtCount(own.records)}-patent sample.{' '}
        {own.top_share != null && own.top_holder && (
          <><strong>{own.top_holder}</strong> holds the most across the whole field:{' '}
            <strong>{fmtCount(own.top_count)} patents</strong>, {own.top_share}% of
            it. </>
        )}
        {VERDICT[own.verdict]}
      </p>

      {mix.length > 0 && (
        <>
          <div className="share-strip" role="img"
               aria-label={mix.map((m) => `${m.share}% ${m.kind}`).join(', ')}>
            {mix.map((m, i) => (
              <span key={m.kind} className={`share-seg share-seg-${i}`} style={{ width: `${m.share}%` }} />
            ))}
          </div>
          <ul className="share-legend">
            {mix.map((m, i) => (
              <li key={m.kind}>
                <span className={`share-dot share-seg-${i}`} aria-hidden="true" />
                <strong>{m.share}%</strong> {m.kind}
                {m.detail && <InfoHint>{m.detail}</InfoHint>}
              </li>
            ))}
          </ul>
        </>
      )}

      <p className="chart-foot">
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
  const [noOwnField, setNoOwnField] = useState(false)
  const navigate = useNavigate()
  const { role } = useSession()
  const pipelineFields = usePipelineFields(role)

  useEffect(() => {
    technologyService.myIntelligence()
      .then((res) => { setData(res.data); setQuery(res.data.query); setFields(res.data.profile_fields || []) })
      .catch((err) => {
        if (err.response?.status === 401) { authService.logout(); navigate('/login') }
        else if (err.response?.status === 400) setNoOwnField(true)
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
  const gapYears = (data?.activity_trend || []).filter((t) => t.patents == null).length
  const unplaced = data?.stage === UNPLACED

  return (
    <div className="dashboard">
      <PageHeader trail="Analyse" title="Technology Intelligence">
        Where a technology sits between early research and mature industry —
        measured on both sides.
      </PageHeader>

      <form onSubmit={analyze} className="search-row">
        <input placeholder="Assess a technology, e.g. solid-state battery" maxLength={200}
               aria-label="Technology to assess"
               value={query} onChange={(e) => setQuery(e.target.value)} />
        <button type="submit">Analyse</button>
      </form>
      <FieldChips fields={fields.length ? fields : pipelineFields}
                  active={data?.query} onPick={(f) => analyze(null, f)}
                  label={fields.length ? 'Your technology areas'
                                       : 'Fields your innovators work in'}
                  fallback={fields.length ? data?.fields_are_fallback : false} />

      {error && <div className="error">{error}</div>}
      {loading && <Loading message="Assessing technology maturity…" />}

      {!loading && !data && (
        <Card>
          <OwnFieldNote
            role={role}
            verb="assess"
            detail={noOwnField
              ? 'Assess a technology above, or add a technology area to your '
                + 'portfolio and this page will evaluate your own field automatically.'
              : undefined}
          />
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

          <Card title="Lifecycle stage"
                sub="Read from how fast the research is growing and how large the field already is">
            {unplaced ? (
              <p className="empty-note">
                Not enough patent data to place this technology on the lifecycle.
              </p>
            ) : (
              <StageTrack stage={data.stage} index={activeStage} />
            )}
            <p className="stage-reason">{data.stage_reason}</p>
          </Card>

          <StatGrid>
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
            {data.opportunity_balance && (
              <StatCard
                value={`${data.opportunity_balance.factor}×`}
                label={BALANCE[data.opportunity_balance.lead].label}
                tone={BALANCE[data.opportunity_balance.lead].tone}
                note={`research ${fmtPct(data.research_growth, { sign: true })} `
                      + `vs patents ${fmtPct(data.patent_growth, { sign: true })}, `
                      + 'first half of the series against the second'}
                hint={'How fast the research and the patenting are growing, compared. '
                      + 'Each side splits its own year series in half and measures the '
                      + 'later half against the earlier one, which uses every year on '
                      + 'record — the Patent Landscape instead compares the three '
                      + 'earliest years with the three latest, so its figure for the '
                      + 'same field is a different number rather than a contradiction. '
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
                <Tooltip {...tooltipProps} formatter={(v, name, item) => {
                  const real = item?.payload?.[name === 'Research' ? 'research_count' : 'patent_count']
                  return [real == null ? '—'
                    : `${fmtCount(real)} (${v}% of its peak)`, name]
                }} />
                <Legend iconType="plainline" wrapperStyle={{ fontSize: 13, paddingTop: 8 }} />

                <Area dataKey="research" stroke="none" fill="url(#momentumResearch)"
                      fillOpacity={1} connectNulls isAnimationActive={false}
                      legendType="none" tooltipType="none" activeDot={false} />
                <Area dataKey="patents" stroke="none" fill="url(#momentumPatents)"
                      fillOpacity={1} connectNulls isAnimationActive={false}
                      legendType="none" tooltipType="none" activeDot={false} />

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
                                          color: CHART_COLORS.patents,
                                          lift: 15 })} />
              </ComposedChart>
            </ResponsiveContainer>
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

          <NextRow items={[
            { key: 'innovation', title: 'Score this technology',
              note: 'Your position, weighted' },
            { key: 'patents', title: 'See the technology themes',
              note: 'What is being filed, grouped' },
          ]} />
        </>
      )}
    </div>
  )
}
