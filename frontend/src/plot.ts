import type { Frame } from './types'

export type PlotTheme = {
  bg: string
  grid: string
  truth: string
  estimate: string
  naive: string
  ink: string
  saffron: string
}

export const defaultTheme: PlotTheme = {
  bg: '#0b0d10',
  grid: '#1c2128',
  truth: '#8a8478',
  estimate: '#3ecfc1',
  naive: '#c45c5c',
  ink: '#e8e4d9',
  saffron: '#e0a020',
}

type Point = { x: number; y: number }

function bounds(frames: Frame[], upto: number) {
  const pts: Point[] = []
  for (let i = 0; i <= upto; i += 1) {
    const f = frames[i]
    pts.push({ x: f.x, y: f.y }, { x: f.truth_x, y: f.truth_y }, { x: f.naive_x, y: f.naive_y })
  }
  const xs = pts.map((p) => p.x)
  const ys = pts.map((p) => p.y)
  const minX = Math.min(...xs)
  const maxX = Math.max(...xs)
  const minY = Math.min(...ys)
  const maxY = Math.max(...ys)
  const pad = 0.12 * Math.max(maxX - minX, maxY - minY, 8)
  return { minX: minX - pad, maxX: maxX + pad, minY: minY - pad, maxY: maxY + pad }
}

function project(
  p: Point,
  box: ReturnType<typeof bounds>,
  w: number,
  h: number,
): [number, number] {
  const sx = (p.x - box.minX) / (box.maxX - box.minX || 1)
  const sy = (p.y - box.minY) / (box.maxY - box.minY || 1)
  return [24 + sx * (w - 48), h - 24 - sy * (h - 48)]
}

function strokePath(
  ctx: CanvasRenderingContext2D,
  frames: Frame[],
  upto: number,
  pick: (f: Frame) => Point,
  box: ReturnType<typeof bounds>,
  w: number,
  h: number,
  color: string,
  width: number,
  dash: number[] = [],
) {
  ctx.beginPath()
  ctx.strokeStyle = color
  ctx.lineWidth = width
  ctx.setLineDash(dash)
  for (let i = 0; i <= upto; i += 1) {
    const [cx, cy] = project(pick(frames[i]), box, w, h)
    if (i === 0) ctx.moveTo(cx, cy)
    else ctx.lineTo(cx, cy)
  }
  ctx.stroke()
  ctx.setLineDash([])
}

export function drawPlot(
  canvas: HTMLCanvasElement,
  frames: Frame[],
  index: number,
  theme: PlotTheme = defaultTheme,
): void {
  const ctx = canvas.getContext('2d')
  if (!ctx || frames.length === 0) return
  const dpr = window.devicePixelRatio || 1
  const w = canvas.clientWidth
  const h = canvas.clientHeight
  if (canvas.width !== Math.floor(w * dpr) || canvas.height !== Math.floor(h * dpr)) {
    canvas.width = Math.floor(w * dpr)
    canvas.height = Math.floor(h * dpr)
  }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.fillStyle = theme.bg
  ctx.fillRect(0, 0, w, h)

  const upto = Math.max(0, Math.min(index, frames.length - 1))
  const box = bounds(frames, frames.length - 1)

  ctx.strokeStyle = theme.grid
  ctx.lineWidth = 1
  for (let i = 0; i < 8; i += 1) {
    const x = 24 + ((w - 48) * i) / 7
    const y = 24 + ((h - 48) * i) / 7
    ctx.beginPath()
    ctx.moveTo(x, 24)
    ctx.lineTo(x, h - 24)
    ctx.moveTo(24, y)
    ctx.lineTo(w - 24, y)
    ctx.stroke()
  }

  ctx.strokeStyle = theme.ink
  ctx.globalAlpha = 0.35
  ctx.strokeRect(18, 18, w - 36, h - 36)
  ctx.globalAlpha = 1

  strokePath(ctx, frames, upto, (f) => ({ x: f.naive_x, y: f.naive_y }), box, w, h, theme.naive, 1.5, [4, 4])
  strokePath(ctx, frames, frames.length - 1, (f) => ({ x: f.truth_x, y: f.truth_y }), box, w, h, theme.truth, 1.25, [2, 6])
  strokePath(ctx, frames, upto, (f) => ({ x: f.x, y: f.y }), box, w, h, theme.estimate, 2.6)

  const start = project({ x: frames[0].truth_x, y: frames[0].truth_y }, box, w, h)
  const end = project(
    { x: frames[frames.length - 1].truth_x, y: frames[frames.length - 1].truth_y },
    box,
    w,
    h,
  )
  ctx.fillStyle = theme.saffron
  ctx.beginPath()
  ctx.arc(start[0], start[1], 5, 0, Math.PI * 2)
  ctx.fill()
  ctx.strokeStyle = theme.ink
  ctx.strokeRect(end[0] - 5, end[1] - 5, 10, 10)

  const now = frames[upto]
  const [nx, ny] = project({ x: now.x, y: now.y }, box, w, h)
  ctx.save()
  ctx.translate(nx, ny)
  ctx.rotate(-now.heading)
  ctx.fillStyle = theme.estimate
  ctx.beginPath()
  ctx.moveTo(11, 0)
  ctx.lineTo(-7, 6)
  ctx.lineTo(-7, -6)
  ctx.closePath()
  ctx.fill()
  ctx.restore()
}
