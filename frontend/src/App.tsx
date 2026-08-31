import { useEffect, useMemo, useRef, useState } from 'react'
import { fetchRun } from './api'
import { drawPlot } from './plot'
import type { RunResult, Stage } from './types'

const SCENARIOS = [
  { id: 'room_walk', label: 'Room walk' },
  { id: 'tunnel', label: 'Tunnel' },
] as const

const STAGES: { id: Stage; label: string }[] = [
  { id: 'align', label: '1  Alignment' },
  { id: 'odometer', label: '2  Virtual odometer' },
  { id: 'filter', label: '3  Physics filter' },
  { id: 'zupt', label: '4  ZUPT lock' },
  { id: 'map', label: '5  Output 10 Hz' },
]

function fmt(n: number, digits = 2): string {
  return n.toFixed(digits)
}

export default function App() {
  const [scenarioId, setScenarioId] = useState<string>('room_walk')
  const [run, setRun] = useState<RunResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [index, setIndex] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [rate, setRate] = useState(1)
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    let cancelled = false
    setPlaying(false)
    setIndex(0)
    setError(null)
    void fetchRun(scenarioId)
      .then((result) => {
        if (!cancelled) setRun(result)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'load failed')
      })
    return () => {
      cancelled = true
    }
  }, [scenarioId])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !run) return
    drawPlot(canvas, run.frames, index)
  }, [run, index])

  useEffect(() => {
    if (!playing || !run) return
    let frame = 0
    let last = performance.now()
    const step = () => {
      const now = performance.now()
      const dt = ((now - last) / 1000) * rate
      last = now
      setIndex((current) => {
        const t0 = run.frames[current]?.t ?? 0
        let next = current
        while (next < run.frames.length - 1 && run.frames[next].t <= t0 + dt) {
          next += 1
        }
        if (next >= run.frames.length - 1) {
          setPlaying(false)
          return run.frames.length - 1
        }
        return next
      })
      frame = requestAnimationFrame(step)
    }
    frame = requestAnimationFrame(step)
    return () => cancelAnimationFrame(frame)
  }, [playing, run, rate])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.code === 'Space') {
        event.preventDefault()
        setPlaying((value) => !value)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const frame = run?.frames[index]
  const finished = Boolean(run && index >= run.frames.length - 1 && !playing)
  const driftClass = run && run.metrics.requirement_met ? '' : 'fail'

  const activeStages = useMemo(() => {
    const stage = frame?.stage ?? 'idle'
    if (stage === 'idle') return new Set<Stage>()
    if (stage === 'align') return new Set<Stage>(['align'])
    if (stage === 'zupt') return new Set<Stage>(['align', 'odometer', 'filter', 'zupt', 'map'])
    return new Set<Stage>(['align', 'odometer', 'filter', 'map'])
  }, [frame])

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="wordmark">
            Still<span>·</span>Dot
          </div>
          <div className="sub">SIH26168 · ISRO · smartphone dead reckoning</div>
        </div>
        <div className="badges">
          <span className="badge ok">offline</span>
          <span className="badge hot">gnss denied</span>
          <span className="badge">research demo</span>
        </div>
      </header>

      <main className="main">
        <section className="plot-wrap" aria-label="Trajectory plot">
          <canvas ref={canvasRef} data-testid="plot" />
          <div className="plot-caption">
            <span>
              <i className="dot" style={{ background: '#3ecfc1' }} />
              filter
            </span>
            <span>
              <i className="dot" style={{ background: '#8a8478' }} />
              surveyed
            </span>
            <span>
              <i className="dot" style={{ background: '#c45c5c' }} />
              naive ∫∫a
            </span>
          </div>
        </section>

        <aside className="side">
          <p className="pitch">{run?.scenario.pitch_line ?? 'The blue dot should not stop when the roof starts.'}</p>
          <div className="controls">
            {SCENARIOS.map((row) => (
              <button
                key={row.id}
                type="button"
                className={row.id === scenarioId ? 'active' : ''}
                onClick={() => setScenarioId(row.id)}
              >
                {row.label}
              </button>
            ))}
            <button
              type="button"
              className={playing ? 'start' : 'start go'}
              onClick={() => {
                if (!run) return
                if (finished) setIndex(0)
                setPlaying((value) => !value)
              }}
            >
              {playing ? 'HOLD' : 'START'}
            </button>
            <button type="button" onClick={() => setRate((value) => (value === 1 ? 4 : 1))}>
              {rate}×
            </button>
          </div>

          <div className={`lock ${frame?.zupt ? '' : 'off'}`}>
            {frame?.zupt ? 'ZUPT lock · speed is exactly zero' : 'ZUPT open · integrating speed once'}
          </div>

          <div className="drift">
            <div className="drift-label">Drift vs surveyed end</div>
            <div className={`drift-num ${finished && driftClass ? driftClass : ''}`} data-testid="drift">
              {run ? `${fmt(finished ? run.metrics.drift_m : hypot(frame, run), 2)} m` : '—'}
            </div>
            <div className="drift-label" data-testid="drift-pct">
              {run
                ? `${fmt(finished ? run.metrics.drift_pct : 0, 2)} % of ${fmt(run.metrics.distance_m, 1)} m  ·  bar < ${fmt(run.metrics.requirement_pct, 0)} %`
                : 'loading replay'}
            </div>
          </div>

          <div className="metrics">
            <div>
              <span>Naive ∫∫a</span>
              {run ? `${fmt(run.metrics.naive_drift_m, 1)} m` : '—'}
            </div>
            <div>
              <span>Speed</span>
              {frame ? `${fmt(frame.speed, 2)} m/s` : '—'}
            </div>
            <div>
              <span>Heading</span>
              {frame ? `${fmt((frame.heading * 180) / Math.PI, 1)}°` : '—'}
            </div>
            <div>
              <span>Trust</span>
              {frame ? fmt(frame.trust, 2) : '—'}
            </div>
          </div>

          <div className="pipeline" data-testid="pipeline">
            {STAGES.map((stage) => (
              <div key={stage.id} className={`stage ${activeStages.has(stage.id) ? 'on' : ''}`}>
                <span>{stage.label}</span>
                <span>{activeStages.has(stage.id) ? 'live' : 'wait'}</span>
              </div>
            ))}
          </div>

          <div className="honesty">
            <strong>Built and measured.</strong> The network estimates speed and
            uncertainty; the filter estimates position.
            <br />
            {run?.scenario.honesty.map((line) => (
              <span key={line}>
                {line}{' '}
              </span>
            ))}
            {error ? <span> {error}</span> : null}
          </div>
        </aside>
      </main>

      <footer className="footer">
        <div>Not deployment-ready · no vehicle wire · nothing leaves this machine</div>
        <div>Space starts · same engine as the phone fallback</div>
      </footer>
    </div>
  )
}

function hypot(frame: RunResult['frames'][number] | undefined, run: RunResult): number {
  if (!frame) return run.metrics.drift_m
  const dx = frame.x - frame.truth_x
  const dy = frame.y - frame.truth_y
  return Math.hypot(dx, dy)
}
