import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, test, vi } from 'vitest'
import App from './App'
import type { RunResult } from './types'

const fixture: RunResult = {
  scenario: {
    id: 'room_walk',
    title: 'Room walk · 50 m L-path',
    pitch_line: 'GPS is off. Airplane mode. Watch the track.',
    vehicle_class: 'pedestrian',
    requirement_pct: 10,
    requirement_note: 'under 5 m over 50 m',
    honesty: ['Synthetic surveyed path, not a live GNSS log.'],
  },
  metrics: {
    distance_m: 50,
    duration_s: 4,
    drift_m: 2.4,
    drift_pct: 4.8,
    naive_drift_m: 11,
    naive_drift_pct: 22,
    requirement_pct: 10,
    requirement_met: true,
    final_speed: 0,
    zupt_locked: true,
    sample_hz: 100,
    output_hz: 10,
  },
  frames: [
    {
      t: 0,
      x: 0,
      y: 0,
      heading: 0,
      speed: 0,
      truth_x: 0,
      truth_y: 0,
      naive_x: 0,
      naive_y: 0,
      zupt: true,
      nhc: true,
      odo_speed: 0,
      gnss_denied: true,
      alignment_yaw_deg: 0,
      trust: 1,
      stage: 'zupt',
    },
    {
      t: 1,
      x: 1.2,
      y: 0.1,
      heading: 0.02,
      speed: 1.3,
      truth_x: 1.3,
      truth_y: 0,
      naive_x: 1.8,
      naive_y: 0.4,
      zupt: false,
      nhc: true,
      odo_speed: 1.3,
      gnss_denied: true,
      alignment_yaw_deg: 0,
      trust: 0.8,
      stage: 'filter',
    },
  ],
  start: [0, 0],
  end_truth: [1.3, 0],
  end_estimate: [1.2, 0.1],
}

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo) => {
      const url = String(input)
      if (url.includes('/api/scenarios/room_walk/run') || url.includes('/demo/room_walk.json')) {
        return new Response(JSON.stringify(fixture), { status: 200 })
      }
      if (url.includes('/api/scenarios/tunnel/run') || url.includes('/demo/tunnel.json')) {
        return new Response(
          JSON.stringify({
            ...fixture,
            scenario: { ...fixture.scenario, id: 'tunnel', pitch_line: 'One kilometre of denied rail.' },
          }),
          { status: 200 },
        )
      }
      return new Response('missing', { status: 404 })
    }),
  )
  HTMLCanvasElement.prototype.getContext = vi.fn(() => {
    return {
      setTransform: vi.fn(),
      fillRect: vi.fn(),
      strokeRect: vi.fn(),
      beginPath: vi.fn(),
      moveTo: vi.fn(),
      lineTo: vi.fn(),
      stroke: vi.fn(),
      fill: vi.fn(),
      arc: vi.fn(),
      save: vi.fn(),
      restore: vi.fn(),
      translate: vi.fn(),
      rotate: vi.fn(),
      closePath: vi.fn(),
      setLineDash: vi.fn(),
    } as unknown as CanvasRenderingContext2D
  })
})

test('console shows the offline pitch chrome', async () => {
  render(<App />)
  expect(screen.getByText(/Still/)).toBeInTheDocument()
  expect(screen.getByText(/offline/i)).toBeInTheDocument()
  expect(screen.getByText(/gnss denied/i)).toBeInTheDocument()
  expect(await screen.findByText(/GPS is off/)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'START' })).toBeInTheDocument()
  expect(screen.getByText(/network estimates speed/i)).toBeInTheDocument()
})

test('start toggles to hold and scenario switch reloads', async () => {
  const user = userEvent.setup()
  render(<App />)
  await screen.findByText(/GPS is off/)
  await user.click(screen.getByRole('button', { name: 'START' }))
  expect(screen.getByRole('button', { name: 'HOLD' })).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Tunnel' }))
  expect(await screen.findByText(/denied rail/)).toBeInTheDocument()
})
