import type { Snapshot } from './types'

export const DEMO_SNAPSHOT: Snapshot = {
  schema_version: 1,
  mode: 'DEMO_DETERMINISTIC',
  research_only: true,
  synthetic: true,
  hardware_actuation_available: false,
  venue: {
    name: 'Synthetic Transit Concourse',
    zones: [
      {
        id: 'platform',
        label: 'Platform',
        risk_probability: 0.72,
        density_people_per_m2: 3.8,
        crowd_pressure_index_s2: 0.017,
        readiness: 'READY',
      },
      {
        id: 'footbridge',
        label: 'Footbridge',
        risk_probability: 0.48,
        density_people_per_m2: 2.9,
        crowd_pressure_index_s2: 0.011,
        readiness: 'READY',
      },
      {
        id: 'forecourt',
        label: 'Forecourt',
        risk_probability: 0.19,
        density_people_per_m2: 1.4,
        crowd_pressure_index_s2: 0.004,
        readiness: 'READY',
      },
    ],
  },
  sensor_health: [
    { id: 'camera-north', kind: 'CCTV', age_s: 0.4, state: 'HEALTHY' },
    { id: 'gate-counter-a', kind: 'COUNTER', age_s: 0.1, state: 'HEALTHY' },
    { id: 'schedule-feed', kind: 'SCHEDULE', age_s: 2, state: 'HEALTHY' },
    { id: 'passive-count-west', kind: 'AGGREGATE', age_s: 4.2, state: 'DEGRADED' },
  ],
  forecast: [
    { minutes: 0, baseline: 0.22, intervention: 0.22, p10: 0.11, p90: 0.32 },
    { minutes: 5, baseline: 0.31, intervention: 0.27, p10: 0.2, p90: 0.41 },
    { minutes: 10, baseline: 0.44, intervention: 0.31, p10: 0.33, p90: 0.54 },
    { minutes: 15, baseline: 0.58, intervention: 0.34, p10: 0.47, p90: 0.68 },
    { minutes: 30, baseline: 0.72, intervention: 0.29, p10: 0.61, p90: 0.82 },
    { minutes: 45, baseline: 0.84, intervention: 0.2, p10: 0.73, p90: 0.94 },
    { minutes: 60, baseline: 0.9, intervention: 0.14, p10: 0.79, p90: 1 },
  ],
  recommendation: {
    action: 'METER_INFLOW',
    inflow_people_per_s: 1.8,
    gate_equivalent: 2,
    expires_in_s: 300,
    reason_codes: ['PLATFORM_FORECAST_RISING', 'ADJACENT_ZONE_CAPACITY_OK'],
    assumptions: [
      'Synthetic arrival schedule remains unchanged',
      'Gate A discharge capacity is 1.2 people/(m·s)',
    ],
    hypothetical: true,
  },
}
