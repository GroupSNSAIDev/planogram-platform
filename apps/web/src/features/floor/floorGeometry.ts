// Where each section sits on a fixture's floor footprint.
// Conventions (from seed/make_seed.py): x_mm/y_mm is the top-left of the rotated footprint.
// Bays run along the long axis: rotation 0 left->right, 90 top->bottom, 180 right->left, 270 bottom->top.
// Double-sided fixtures split the depth in two; `faces` "W/E" means side A faces west, side B east.
import type { Fixture, Section, TemplateDef } from '../../api/types'

export type FloorRect = { x: number; y: number; w: number; h: number }

export function sectionFloorRects(f: Fixture, sections: Section[], tpl: TemplateDef | undefined) {
  const out: { section: Section; rect: FloorRect }[] = []
  const bays = tpl?.bays_per_side ?? 1
  const sides = tpl?.sides ?? []
  const rot = ((f.rotation_deg % 360) + 360) % 360
  const alongX = rot === 0 || rot === 180
  const length = alongX ? f.footprint_w_mm : f.footprint_d_mm
  const bayLen = length / Math.max(1, bays)
  const faceParts = (f.faces ?? '').split('/')

  for (const s of sections) {
    // position along the bay axis
    let a0 = (s.bay_from - 1) * bayLen
    let a1 = s.bay_to * bayLen
    if (rot === 180 || rot === 270) [a0, a1] = [length - a1, length - a0]
    let r: FloorRect = alongX
      ? { x: f.x_mm + a0, y: f.y_mm, w: a1 - a0, h: f.footprint_d_mm }
      : { x: f.x_mm, y: f.y_mm + a0, w: f.footprint_w_mm, h: a1 - a0 }
    // which half of the depth, for double-sided fixtures
    if (sides.length === 2) {
      const dir = s.side === 'A' ? faceParts[0] : faceParts[1] ?? ''
      if (alongX) {
        const half = r.h / 2
        r = { ...r, h: half, y: dir === 'S' ? r.y + half : r.y }
      } else {
        const half = r.w / 2
        r = { ...r, w: half, x: dir === 'E' ? r.x + half : r.x }
      }
    }
    out.push({ section: s, rect: r })
  }
  return out
}

/** Edge of the footprint that shoppers face (thick line in the plan), for single-sided fixtures. */
export function frontEdge(f: Fixture): [number, number, number, number] | null {
  const face = f.faces
  if (!face || face.includes('/') || face === 'TOP' || face === 'ALL') return null
  const { x_mm: x, y_mm: y, footprint_w_mm: w, footprint_d_mm: d } = f
  switch (face) {
    case 'N': return [x, y, x + w, y]
    case 'S': return [x, y + d, x + w, y + d]
    case 'W': return [x, y, x, y + d]
    case 'E': return [x + w, y, x + w, y + d]
    default: return null
  }
}

const PREFIX: Record<string, [string, number]> = {
  GONDOLA_DS_12: ['G', 2], END_CAP: ['EC-', 2], WALL_BAY: ['WB-', 2], MULTIDECK_2500: ['MD-', 2],
  GLASS_DOOR_FREEZER_4: ['FZ-', 2], ISLAND_FREEZER_2500: ['IF-', 2], PRODUCE_BIN: ['PB-', 2], PALLET: ['PL-', 2],
  BAKERY_RACK: ['BK-', 2], CHECKOUT_COUNTER: ['CO-', 2], CHECKOUT_RACK: ['CR-', 2], SELF_CHECKOUT: ['SC-', 2],
  SERVICE_DESK: ['CS-', 2],
}

/** Next free fixture code for a template, e.g. G11 or MD-13. */
export function nextFixtureCode(templateCode: string, fixtures: Fixture[]): string {
  const [prefix, digits] = PREFIX[templateCode] ?? ['FX-', 2]
  const re = new RegExp(`^${prefix.replace('-', '\\-')}(\\d+)$`)
  let max = 0
  for (const f of fixtures) {
    const m = re.exec(f.code)
    if (m) max = Math.max(max, Number(m[1]))
  }
  return `${prefix}${String(max + 1).padStart(digits, '0')}`
}
