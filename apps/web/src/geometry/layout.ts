// Floor checks: TypeScript mirror of services/api/planogram/engines/layout_checks.py.
// Used for live feedback while dragging; the server result is authoritative after each save.
import type { Fixture, Landmark, LayoutChecks, LayoutDoc } from '../api/types'
import { SETTINGS } from './geometry'

type R = [number, number, number, number]
const DOORS = new Set(['entrance', 'exit', 'stockroom_door'])

export const fixtureRect = (f: Pick<Fixture, 'x_mm' | 'y_mm' | 'footprint_w_mm' | 'footprint_d_mm'>): R =>
  [f.x_mm, f.y_mm, f.x_mm + f.footprint_w_mm, f.y_mm + f.footprint_d_mm]
const lmRect = (lm: Landmark): R => [lm.rect[0], lm.rect[1], lm.rect[0] + lm.rect[2], lm.rect[1] + lm.rect[3]]

function overlapArea(a: R, b: R): number {
  const w = Math.min(a[2], b[2]) - Math.max(a[0], b[0])
  const h = Math.min(a[3], b[3]) - Math.max(a[1], b[1])
  return w > 0 && h > 0 ? w * h : 0
}

const faces = (f: Fixture) => new Set((f.faces ?? '').split('/').filter(x => 'NESW'.includes(x) && x.length === 1))

function aisleGap(fa: Fixture, a: R, fb: Fixture, b: R): number | null {
  const xo = Math.min(a[2], b[2]) - Math.max(a[0], b[0])
  const yo = Math.min(a[3], b[3]) - Math.max(a[1], b[1])
  if (xo > 0 && yo <= 0) {
    const [upper, lower] = a[1] < b[1] ? [fa, fb] : [fb, fa]
    if (faces(upper).has('S') || faces(lower).has('N')) return -yo
  } else if (yo > 0 && xo <= 0) {
    const [left, right] = a[0] < b[0] ? [fa, fb] : [fb, fa]
    if (faces(left).has('E') || faces(right).has('W')) return -xo
  }
  return null
}

function doorKeepout(lm: Landmark, fw: number, fd: number): R {
  const [x1, y1, x2, y2] = lmRect(lm)
  const k = SETTINGS.door_keepout_mm
  if (y2 >= fd) return [x1, fd - k, x2, fd]
  if (y1 <= 0) return [x1, 0, x2, k]
  if (x1 <= 0) return [0, y1, k, y2]
  return [fw - k, y1, fw, y2]
}

export function checkLayout(doc: Pick<LayoutDoc, 'store' | 'fixtures' | 'landmarks'>, onlyIds?: Set<string>): LayoutChecks {
  const { width_mm: fw, depth_mm: fd } = doc.store
  const fixtures = Object.values(doc.fixtures).sort((a, b) => a.code.localeCompare(b.code))
  const out: LayoutChecks = { overlaps: [], aisle_warnings: [], blocked_doors: [], out_of_bounds: [] }
  fixtures.forEach((a, i) => {
    const ra = fixtureRect(a)
    const mine = !onlyIds || onlyIds.has(a.id)
    if (mine && (ra[0] < 0 || ra[1] < 0 || ra[2] > fw || ra[3] > fd)) {
      out.out_of_bounds.push({ fixtures: [a.id], message: `${a.code} is outside the floor` })
    }
    for (const b of fixtures.slice(i + 1)) {
      if (onlyIds && !onlyIds.has(a.id) && !onlyIds.has(b.id)) continue
      const rb = fixtureRect(b)
      if (overlapArea(ra, rb)) {
        out.overlaps.push({ fixtures: [a.id, b.id], message: `${a.code} overlaps ${b.code}` })
        continue
      }
      const gap = aisleGap(a, ra, b, rb)
      if (gap !== null && gap > 0 && gap < SETTINGS.min_aisle_mm) {
        out.aisle_warnings.push({ fixtures: [a.id, b.id], gap_mm: gap,
          message: `aisle between ${a.code} and ${b.code} is ${gap.toLocaleString('en-IN')} mm (min ${SETTINGS.min_aisle_mm} mm)` })
      }
    }
    if (!mine) return
    for (const lm of doc.landmarks) {
      if (lm.kind === 'pillar' && overlapArea(ra, lmRect(lm))) {
        out.overlaps.push({ fixtures: [a.id], landmark: lm.name, message: `${a.code} overlaps ${lm.name}` })
      } else if (DOORS.has(lm.kind) && overlapArea(ra, doorKeepout(lm, fw, fd))) {
        out.blocked_doors.push({ fixtures: [a.id], landmark: lm.name, message: `${a.code} blocks ${lm.name}` })
      }
    }
  })
  return out
}

export function flaggedIds(checks: LayoutChecks): { bad: Set<string>; warn: Set<string> } {
  const bad = new Set<string>()
  const warn = new Set<string>()
  for (const i of [...checks.overlaps, ...checks.blocked_doors, ...checks.out_of_bounds]) i.fixtures.forEach(id => bad.add(id))
  for (const i of checks.aisle_warnings) i.fixtures.forEach(id => warn.add(id))
  return { bad, warn }
}

/** Footprint after a quarter-turn rotation about the centre, snapped to whole millimetres. */
export function rotatedPose(f: Fixture, rotationDeg: number) {
  const steps = (((rotationDeg - f.rotation_deg) / 90) % 4 + 4) % 4
  const swap = steps % 2 === 1
  const w = swap ? f.footprint_d_mm : f.footprint_w_mm
  const d = swap ? f.footprint_w_mm : f.footprint_d_mm
  const cx = f.x_mm + f.footprint_w_mm / 2
  const cy = f.y_mm + f.footprint_d_mm / 2
  return { x_mm: Math.round(cx - w / 2), y_mm: Math.round(cy - d / 2), footprint_w_mm: w, footprint_d_mm: d, steps }
}

const COMPASS = ['N', 'E', 'S', 'W']
export function rotateFaces(faces: string | null, steps: number): string | null {
  if (!faces || faces === 'TOP' || faces === 'ALL') return faces
  return faces.split('/').map(p => (COMPASS.includes(p) ? COMPASS[(COMPASS.indexOf(p) + steps) % 4] : p)).join('/')
}
