import { useEffect, useMemo, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  CircleStop,
  Clock3,
  Gauge,
  Pause,
  Play,
  RadioTower,
  ShieldAlert,
  Users,
} from 'lucide-react'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { loadSnapshot } from './api'
import './App.css'
import { DEMO_SNAPSHOT } from './demo'
import type {
  Fault,
  InstructionLifecycle,
  Readiness,
  Snapshot,
  Zone,
} from './types'

function App() {
  const [snapshot, setSnapshot] = useState<Snapshot>(DEMO_SNAPSHOT)
  const [selectedZoneId, setSelectedZoneId] = useState('platform')
  const [fault, setFault] = useState<Fault>('none')
  const [playing, setPlaying] = useState(true)
  const [playbackMinute, setPlaybackMinute] = useState(15)
  const [lifecycle, setLifecycle] = useState<InstructionLifecycle>('draft')
  const [now, setNow] = useState(() => new Date())

  useEffect(() => {
    const controller = new AbortController()
    void loadSnapshot(controller.signal).then(setSnapshot)
    return () => controller.abort()
  }, [])

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000)
    return () => window.clearInterval(timer)
  }, [])

  const selectedZone =
    snapshot.venue.zones.find((zone) => zone.id === selectedZoneId) ??
    snapshot.venue.zones[0]
  const readiness = readinessForFault(fault)
  const faultReason = reasonForFault(fault)
  const recommendationVisible = readiness === 'READY'
  const finalBaseline = snapshot.forecast.at(-1)?.baseline ?? 0
  const finalIntervention = snapshot.forecast.at(-1)?.intervention ?? 0

  return (
    <div className="console-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">
            C
          </div>
          <div>
            <strong>Crowdent</strong>
            <span>Forecast command console</span>
          </div>
        </div>
        <div className="topbar-status" aria-label="Runtime status">
          <span className="mode-badge">DEMO · SYNTHETIC</span>
          <span className="offline-badge">
            <RadioTower size={14} aria-hidden="true" />
            Offline runtime
          </span>
          <StatusPill readiness={readiness} />
          <time dateTime={now.toISOString()} className="clock">
            <Clock3 size={14} aria-hidden="true" />
            {now.toLocaleTimeString([], { hour12: false })}
          </time>
        </div>
      </header>

      <div className="research-banner" role="note">
        <ShieldAlert size={16} aria-hidden="true" />
        <strong>RESEARCH ONLY — NOT DEPLOYMENT CERTIFIED</strong>
        <span>Human advisory only. No hardware actuation is available.</span>
      </div>

      <section className="control-strip" aria-label="Demo controls">
        <button
          className="icon-button"
          type="button"
          aria-label={playing ? 'Pause demo playback' : 'Resume demo playback'}
          onClick={() => setPlaying((value) => !value)}
        >
          {playing ? <Pause size={16} /> : <Play size={16} />}
        </button>
        <label className="timeline-control">
          <span>Scenario time</span>
          <input
            aria-label="Scenario minute"
            type="range"
            min="0"
            max="60"
            step="5"
            value={playbackMinute}
            onChange={(event) => setPlaybackMinute(Number(event.target.value))}
          />
          <output>{playbackMinute} min</output>
        </label>
        <label className="fault-control">
          <span>Failure injection</span>
          <select
            aria-label="Failure injection"
            value={fault}
            onChange={(event) => {
              setFault(event.target.value as Fault)
              setLifecycle('draft')
            }}
          >
            <option value="none">None — nominal inputs</option>
            <option value="stale">Stale camera</option>
            <option value="conflict">Conflicting counters</option>
            <option value="clock">Clock synchronization failure</option>
          </select>
        </label>
        <div className="data-age">
          <span>Last fused state</span>
          <strong>{readiness === 'READY' ? '0.4 s ago' : 'WITHHELD'}</strong>
        </div>
      </section>

      {readiness !== 'READY' && (
        <div className="suppression-alert" role="alert" aria-live="assertive">
          <AlertTriangle size={20} aria-hidden="true" />
          <div>
            <strong>{readiness}: recommendation suppressed</strong>
            <span>{faultReason}</span>
          </div>
          <span className="suppression-rule">Countdown removed · advice withheld</span>
        </div>
      )}

      <main className="dashboard">
        <section className="panel venue-panel" aria-labelledby="venue-title">
          <PanelHeader
            icon={<Users size={17} />}
            title="Venue state"
            id="venue-title"
            meta={snapshot.venue.name}
          />
          <VenueMap
            zones={snapshot.venue.zones}
            selectedZoneId={selectedZone.id}
            readiness={readiness}
          />
          <div className="map-legend" aria-label="Risk probability legend">
            <span>Lower risk</span>
            <div aria-hidden="true">
              <i className="risk-low" />
              <i className="risk-watch" />
              <i className="risk-high" />
            </div>
            <span>Higher risk</span>
          </div>
          <div className="selected-metrics">
            <Metric
              label={`${selectedZone.label} density`}
              value={readiness === 'UNKNOWN' ? '—' : selectedZone.density_people_per_m2.toFixed(1)}
              unit="people/m²"
            />
            <Metric
              label="Mean speed"
              value={readiness === 'UNKNOWN' ? '—' : '0.42'}
              unit="m/s"
            />
            <Metric
              label="Pressure index"
              value={
                readiness === 'UNKNOWN'
                  ? '—'
                  : selectedZone.crowd_pressure_index_s2.toFixed(3)
              }
              unit="s⁻²"
            />
          </div>
        </section>

        <section className="panel zones-panel" aria-labelledby="zones-title">
          <PanelHeader
            icon={<Gauge size={17} />}
            title="Ranked zones"
            id="zones-title"
            meta="Probability × urgency"
          />
          <ol className="zone-list">
            {[...snapshot.venue.zones]
              .sort((a, b) => b.risk_probability - a.risk_probability)
              .map((zone, index) => (
                <li key={zone.id}>
                  <button
                    type="button"
                    className={zone.id === selectedZone.id ? 'zone-row selected' : 'zone-row'}
                    onClick={() => setSelectedZoneId(zone.id)}
                  >
                    <span className="zone-rank">{String(index + 1).padStart(2, '0')}</span>
                    <span className="zone-name">
                      <strong>{zone.label}</strong>
                      <small>{zone.density_people_per_m2.toFixed(1)} people/m²</small>
                    </span>
                    <span className="risk-number">
                      {readiness === 'UNKNOWN'
                        ? '—'
                        : `${Math.round(zone.risk_probability * 100)}%`}
                    </span>
                  </button>
                </li>
              ))}
          </ol>
          <div className="countdown-block">
            <span>Estimated time to policy threshold</span>
            <strong>{recommendationVisible ? '13:00' : '--:--'}</strong>
            <small>
              {recommendationVisible
                ? 'Range 10–17 minutes'
                : 'Unavailable while inputs are not ready'}
            </small>
          </div>
        </section>

        <section className="panel sensors-panel" aria-labelledby="sensors-title">
          <PanelHeader
            icon={<Activity size={17} />}
            title="Sensor health"
            id="sensors-title"
            meta={`${snapshot.sensor_health.length} sources`}
          />
          <ul className="sensor-list">
            {snapshot.sensor_health.map((sensor) => {
              const injected =
                fault === 'stale' && sensor.kind === 'CCTV'
                  ? 'OFFLINE'
                  : fault === 'conflict' && sensor.kind === 'COUNTER'
                    ? 'DEGRADED'
                    : sensor.state
              return (
                <li key={sensor.id}>
                  <span className={`sensor-dot ${injected.toLowerCase()}`} aria-hidden="true" />
                  <span>
                    <strong>{sensor.id}</strong>
                    <small>{sensor.kind}</small>
                  </span>
                  <span>{injected === 'OFFLINE' ? 'STALE' : `${sensor.age_s.toFixed(1)} s`}</span>
                </li>
              )
            })}
          </ul>
          <p className="privacy-note">
            Passive counts are aggregated at ingest. Raw device identifiers are rejected.
          </p>
        </section>

        <section className="panel forecast-panel" aria-labelledby="forecast-title">
          <PanelHeader
            icon={<Activity size={17} />}
            title="Probability forecast"
            id="forecast-title"
            meta={`${selectedZone.label} · 60 min horizon`}
          />
          <div className="chart-wrap" aria-label="Risk probability forecast chart">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={snapshot.forecast} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
                <CartesianGrid stroke="#26313b" strokeDasharray="3 3" />
                <XAxis
                  dataKey="minutes"
                  stroke="#82909d"
                  tickFormatter={(value) => `${value}m`}
                />
                <YAxis
                  domain={[0, 1]}
                  stroke="#82909d"
                  tickFormatter={(value) => `${Math.round(value * 100)}%`}
                />
                <Tooltip
                  formatter={(value) => `${Math.round(Number(value) * 100)}%`}
                  labelFormatter={(value) => `+${value} minutes`}
                  contentStyle={{ background: '#111820', border: '1px solid #35434f' }}
                />
                <Legend />
                <Line
                  name="No action"
                  type="monotone"
                  dataKey="baseline"
                  stroke="#f06b5f"
                  strokeWidth={2.5}
                  dot={false}
                  isAnimationActive={false}
                />
                <Line
                  name="Meter inflow"
                  type="monotone"
                  dataKey="intervention"
                  stroke="#53d4b0"
                  strokeWidth={2.5}
                  dot={false}
                  isAnimationActive={false}
                />
                <Line
                  name="p10"
                  type="monotone"
                  dataKey="p10"
                  stroke="#82909d"
                  strokeDasharray="3 5"
                  dot={false}
                  isAnimationActive={false}
                />
                <Line
                  name="p90"
                  type="monotone"
                  dataKey="p90"
                  stroke="#82909d"
                  strokeDasharray="3 5"
                  dot={false}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="chart-caption">
            Bands are ensemble quantiles, not guarantees. Counterfactuals are hypothetical.
          </p>
        </section>

        <section className="panel comparison-panel" aria-labelledby="comparison-title">
          <PanelHeader
            icon={<CircleStop size={17} />}
            title="Intervention comparison"
            id="comparison-title"
            meta="Common initial ensemble"
          />
          <div className="comparison-grid">
            <ScenarioCard
              label="No action"
              probability={finalBaseline}
              kind="baseline"
              detail="Scheduled inflow continues at 4.1 people/s"
            />
            <ScenarioCard
              label="Meter north entry"
              probability={finalIntervention}
              kind="intervention"
              detail="Limit inflow to 1.8 people/s at two gate equivalents"
            />
          </div>
          <dl className="assumption-list">
            <div>
              <dt>Model version</dt>
              <dd>demo-forecast-v1</dd>
            </div>
            <div>
              <dt>Constraints</dt>
              <dd>No violations detected in synthetic venue</dd>
            </div>
            <div>
              <dt>Causal status</dt>
              <dd>Hypothetical simulation, not a causal claim</dd>
            </div>
          </dl>
        </section>

        <section className="panel recommendation-panel" aria-labelledby="recommendation-title">
          <PanelHeader
            icon={<ShieldAlert size={17} />}
            title="Human advisory"
            id="recommendation-title"
            meta={recommendationVisible ? lifecycleLabel(lifecycle) : 'SUPPRESSED'}
          />
          {recommendationVisible ? (
            <div className="recommendation-content">
              <div className="instruction">
                <span>Recommended research action</span>
                <strong>Meter north entry to 1.8 people/s</strong>
                <p>
                  Staff equivalent: hold two admission lanes. Confirm local egress and
                  exterior queue conditions before any physical action.
                </p>
              </div>
              <ul className="reason-codes" aria-label="Recommendation reasons">
                {snapshot.recommendation.reason_codes.map((reason) => (
                  <li key={reason}>{reason.replaceAll('_', ' ')}</li>
                ))}
              </ul>
              <InstructionActions lifecycle={lifecycle} onChange={setLifecycle} />
              <p className="lifecycle-status" role="status" aria-live="polite">
                Lifecycle: <strong>{lifecycleLabel(lifecycle)}</strong>. A software
                approval never actuates a gate.
              </p>
            </div>
          ) : (
            <div className="withheld-card">
              <AlertTriangle size={28} aria-hidden="true" />
              <strong>No recommendation available</strong>
              <p>{faultReason}</p>
              <span>Restore sustained healthy inputs before reevaluation.</span>
            </div>
          )}
        </section>
      </main>

      <footer>
        <span>Run demo-v1 · Seed 404 · CPU inference</span>
        <span>Raw video retention disabled · No cloud telemetry</span>
      </footer>
    </div>
  )
}

function PanelHeader({
  icon,
  title,
  id,
  meta,
}: {
  icon: React.ReactNode
  title: string
  id: string
  meta: string
}) {
  return (
    <div className="panel-header">
      <h2 id={id}>
        {icon}
        {title}
      </h2>
      <span>{meta}</span>
    </div>
  )
}

function StatusPill({ readiness }: { readiness: Readiness }) {
  return (
    <span className={`status-pill ${readiness.toLowerCase()}`}>
      {readiness === 'READY' ? (
        <CheckCircle2 size={14} aria-hidden="true" />
      ) : (
        <AlertTriangle size={14} aria-hidden="true" />
      )}
      {readiness}
    </span>
  )
}

function VenueMap({
  zones,
  selectedZoneId,
  readiness,
}: {
  zones: Zone[]
  selectedZoneId: string
  readiness: Readiness
}) {
  const riskById = useMemo(
    () => Object.fromEntries(zones.map((zone) => [zone.id, zone.risk_probability])),
    [zones],
  )
  return (
    <svg
      className="venue-map"
      viewBox="0 0 640 330"
      role="img"
      aria-label="Synthetic venue density map with platform, footbridge and forecourt zones"
    >
      <defs>
        <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
          <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#24313a" strokeWidth="1" />
        </pattern>
      </defs>
      <rect x="1" y="1" width="638" height="328" fill="url(#grid)" stroke="#35434f" />
      <ZoneShape
        id="platform"
        label="PLATFORM"
        path="M36 58 H390 V178 H36 Z"
        labelX={52}
        labelY={82}
        risk={riskById.platform}
        selected={selectedZoneId === 'platform'}
        readiness={readiness}
      />
      <ZoneShape
        id="footbridge"
        label="FOOTBRIDGE"
        path="M390 94 H604 V146 H390 Z"
        labelX={408}
        labelY={124}
        risk={riskById.footbridge}
        selected={selectedZoneId === 'footbridge'}
        readiness={readiness}
      />
      <ZoneShape
        id="forecourt"
        label="FORECOURT"
        path="M126 216 H528 V298 H126 Z"
        labelX={146}
        labelY={242}
        risk={riskById.forecourt}
        selected={selectedZoneId === 'forecourt'}
        readiness={readiness}
      />
      {Array.from({ length: 12 }, (_, index) => (
        <g key={index} transform={`translate(${70 + index * 25} ${112 + (index % 3) * 12})`}>
          <circle r="3" fill="#d8e0e5" opacity="0.78" />
          <path d="M-8 0 H8 M4 -4 L8 0 L4 4" stroke="#8fe0cc" strokeWidth="1.3" />
        </g>
      ))}
      <text x="35" y="315" className="map-coordinate">
        SITE-LOCAL GRID · 1 m CELLS · SYNTHETIC
      </text>
    </svg>
  )
}

function ZoneShape({
  label,
  path,
  labelX,
  labelY,
  risk,
  selected,
  readiness,
}: {
  id: string
  label: string
  path: string
  labelX: number
  labelY: number
  risk: number
  selected: boolean
  readiness: Readiness
}) {
  const category =
    readiness === 'UNKNOWN'
      ? 'unknown'
      : risk >= 0.65
        ? 'high'
        : risk >= 0.35
          ? 'watch'
          : 'low'
  return (
    <g className={`map-zone ${category} ${selected ? 'selected' : ''}`}>
      <path d={path} />
      <text x={labelX} y={labelY}>
        {label}
      </text>
    </g>
  )
}

function Metric({ label, value, unit }: { label: string; value: string; unit: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{unit}</small>
    </div>
  )
}

function ScenarioCard({
  label,
  probability,
  kind,
  detail,
}: {
  label: string
  probability: number
  kind: 'baseline' | 'intervention'
  detail: string
}) {
  return (
    <article className={`scenario-card ${kind}`}>
      <div>
        <span>{label}</span>
        <strong>{Math.round(probability * 100)}%</strong>
      </div>
      <div className="probability-track" aria-label={`${label}: ${Math.round(probability * 100)}%`}>
        <i style={{ width: `${probability * 100}%` }} />
      </div>
      <p>{detail}</p>
      <small>Probability of site-specific threshold exceedance at +60 min</small>
    </article>
  )
}

function InstructionActions({
  lifecycle,
  onChange,
}: {
  lifecycle: InstructionLifecycle
  onChange: (value: InstructionLifecycle) => void
}) {
  if (lifecycle === 'draft') {
    return (
      <div className="action-row">
        <button type="button" className="primary-action" onClick={() => onChange('acknowledged')}>
          Acknowledge review
        </button>
        <button type="button" className="danger-action" onClick={() => onChange('rejected')}>
          Reject
        </button>
      </div>
    )
  }
  if (lifecycle === 'acknowledged') {
    return (
      <div className="action-row">
        <button type="button" className="primary-action" onClick={() => onChange('accepted')}>
          Supervisor accepts advisory
        </button>
        <button type="button" className="danger-action" onClick={() => onChange('rejected')}>
          Reject
        </button>
      </div>
    )
  }
  if (lifecycle === 'accepted') {
    return (
      <div className="action-row">
        <button
          type="button"
          className="primary-action"
          onClick={() => onChange('physical_action_confirmed')}
        >
          Record human-reported physical action
        </button>
      </div>
    )
  }
  return null
}

function readinessForFault(fault: Fault): Readiness {
  if (fault === 'clock') return 'UNKNOWN'
  if (fault === 'stale' || fault === 'conflict') return 'DEGRADED'
  return 'READY'
}

function reasonForFault(fault: Fault): string {
  if (fault === 'stale') return 'Camera north exceeded its freshness limit.'
  if (fault === 'conflict') return 'Gate counters disagree beyond the configured tolerance.'
  if (fault === 'clock') return 'Clock error prevents safe event-time alignment.'
  return 'All deterministic demo inputs are within configured limits.'
}

function lifecycleLabel(lifecycle: InstructionLifecycle): string {
  return lifecycle.replaceAll('_', ' ').toUpperCase()
}

export default App
