export type Stage = 'idle' | 'align' | 'odometer' | 'filter' | 'zupt' | 'map'

export type VehicleClass = 'pedestrian' | 'vehicle'

export type Frame = {
  t: number
  x: number
  y: number
  heading: number
  speed: number
  truth_x: number
  truth_y: number
  naive_x: number
  naive_y: number
  zupt: boolean
  nhc: boolean
  odo_speed: number
  gnss_denied: boolean
  alignment_yaw_deg: number
  trust: number
  stage: Stage
}

export type ScenarioSpec = {
  id: string
  title: string
  pitch_line: string
  vehicle_class: VehicleClass
  requirement_pct: number
  requirement_note: string
  honesty: string[]
}

export type RunMetrics = {
  distance_m: number
  duration_s: number
  drift_m: number
  drift_pct: number
  naive_drift_m: number
  naive_drift_pct: number
  requirement_pct: number
  requirement_met: boolean
  final_speed: number
  zupt_locked: boolean
  sample_hz: number
  output_hz: number
}

export type RunResult = {
  scenario: ScenarioSpec
  metrics: RunMetrics
  frames: Frame[]
  start: [number, number]
  end_truth: [number, number]
  end_estimate: [number, number]
}
