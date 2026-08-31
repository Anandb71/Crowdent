import type { RunResult, ScenarioSpec } from './types'

export async function fetchHealth(): Promise<{ ok: boolean; offline: boolean }> {
  const res = await fetch('/api/health')
  if (!res.ok) throw new Error('health check failed')
  return res.json() as Promise<{ ok: boolean; offline: boolean }>
}

export async function fetchScenarios(): Promise<ScenarioSpec[]> {
  const res = await fetch('/api/scenarios')
  if (!res.ok) throw new Error('scenarios unavailable')
  return res.json() as Promise<ScenarioSpec[]>
}

export async function fetchRun(scenarioId: string): Promise<RunResult> {
  try {
    const res = await fetch(`/api/scenarios/${scenarioId}/run`)
    if (res.ok) return (await res.json()) as RunResult
  } catch {
    // fall through to the baked replay — the pitch is offline
  }
  const fallback = await fetch(`/demo/${scenarioId}.json`)
  if (!fallback.ok) {
    throw new Error(`no replay for ${scenarioId}`)
  }
  return (await fallback.json()) as RunResult
}
