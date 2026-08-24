import { z } from 'zod'

export const zoneSchema = z.object({
  id: z.string(),
  label: z.string(),
  risk_probability: z.number().min(0).max(1),
  density_people_per_m2: z.number().nonnegative(),
  crowd_pressure_index_s2: z.number().nonnegative(),
  readiness: z.enum(['READY', 'DEGRADED', 'UNKNOWN']),
})

export const sensorSchema = z.object({
  id: z.string(),
  kind: z.string(),
  age_s: z.number().nonnegative(),
  state: z.enum(['HEALTHY', 'DEGRADED', 'OFFLINE']),
})

export const forecastPointSchema = z.object({
  minutes: z.number().nonnegative(),
  baseline: z.number().min(0).max(1),
  intervention: z.number().min(0).max(1),
  p10: z.number().min(0).max(1),
  p90: z.number().min(0).max(1),
})

export const recommendationSchema = z.object({
  action: z.string(),
  inflow_people_per_s: z.number().nonnegative(),
  gate_equivalent: z.number().int().nonnegative(),
  expires_in_s: z.number().int().positive(),
  reason_codes: z.array(z.string()),
  assumptions: z.array(z.string()),
  hypothetical: z.literal(true),
})

export const snapshotSchema = z.object({
  schema_version: z.literal(1),
  mode: z.enum(['DEMO_DETERMINISTIC', 'REPLAY_RESEARCH', 'FIELD_RESEARCH']),
  research_only: z.literal(true),
  synthetic: z.boolean(),
  hardware_actuation_available: z.literal(false),
  venue: z.object({
    name: z.string(),
    zones: z.array(zoneSchema).min(1),
  }),
  sensor_health: z.array(sensorSchema),
  forecast: z.array(forecastPointSchema).min(1),
  recommendation: recommendationSchema,
})

export type Zone = z.infer<typeof zoneSchema>
export type Sensor = z.infer<typeof sensorSchema>
export type ForecastPoint = z.infer<typeof forecastPointSchema>
export type Recommendation = z.infer<typeof recommendationSchema>
export type Snapshot = z.infer<typeof snapshotSchema>
export type Readiness = 'READY' | 'DEGRADED' | 'UNKNOWN'
export type Fault = 'none' | 'stale' | 'conflict' | 'clock'
export type InstructionLifecycle =
  | 'draft'
  | 'acknowledged'
  | 'accepted'
  | 'rejected'
  | 'physical_action_confirmed'
