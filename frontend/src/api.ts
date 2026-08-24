import { DEMO_SNAPSHOT } from './demo'
import { snapshotSchema, type Snapshot } from './types'

const REQUEST_TIMEOUT_MS = 1500

export async function loadSnapshot(signal?: AbortSignal): Promise<Snapshot> {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
  const abort = () => controller.abort()
  signal?.addEventListener('abort', abort, { once: true })
  try {
    const response = await fetch('/api/v1/demo/snapshot', {
      signal: controller.signal,
      headers: { Accept: 'application/json' },
      credentials: 'same-origin',
    })
    if (!response.ok) {
      throw new Error(`snapshot request failed: ${response.status}`)
    }
    return snapshotSchema.parse(await response.json())
  } catch {
    // The bundled deterministic fixture keeps the console demonstrable while
    // the local API is not running. FIELD mode never uses this fallback.
    return DEMO_SNAPSHOT
  } finally {
    window.clearTimeout(timer)
    signal?.removeEventListener('abort', abort)
  }
}
