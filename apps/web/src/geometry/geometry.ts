// Shelf geometry and fit checks: TypeScript mirror of services/api/planogram/engines/geometry.py.
// Both pass packages/contracts/golden/fit_cases.json. Change both together.

export const SETTINGS = {
  gap_mm: 2,
  finger_clearance_mm: 25,
  back_clearance_mm: 10,
  door_clearance_mm: 20,
  shelf_thickness_mm: 15,
  top_shelf_headroom_mm: 250,
  min_aisle_mm: 900,
  door_keepout_mm: 1500,
} as const

const EYE_BANDS: [number, string][] = [[0, 'floor'], [400, 'knee'], [800, 'waist'], [1200, 'eye'], [1601, 'top']]

export function eyeBand(heightMm: number): string {
  let band = 'floor'
  for (const [lower, name] of EYE_BANDS) if (heightMm >= lower) band = name
  return band
}

export function clearHeights(heights: number[], bayHeightMm: number): number[] {
  const order = heights.map((_, i) => i).sort((a, b) => heights[a] - heights[b])
  const out = new Array<number>(heights.length).fill(0)
  order.forEach((i, rank) => {
    const ceiling = rank + 1 < order.length ? heights[order[rank + 1]] : bayHeightMm + SETTINGS.top_shelf_headroom_mm
    out[i] = ceiling - heights[i] - SETTINGS.shelf_thickness_mm
  })
  return out
}

export function usableDepth(surfaceDepthMm: number, hasDoor: boolean): number {
  return surfaceDepthMm - (hasDoor ? SETTINGS.door_clearance_mm : SETTINGS.back_clearance_mm)
}

export function maxFacingsDeep(productDepthMm: number, usableDepthMm: number): number {
  if (productDepthMm <= 0) return 1
  return Math.max(1, Math.floor(usableDepthMm / productDepthMm))
}

export interface FitProduct {
  name: string; width_mm: number; height_mm: number; depth_mm: number; weight_g: number | null
  temperature: string; can_stack: boolean; max_stack: number
}
export interface FitPosition {
  id: string; product_id: string; seq: number; facings_wide: number; facings_high: number; facings_deep: number
  locked?: boolean; locked_x_mm?: number | null
}
export interface FitIssue { code: string; target: string; message: string; data: Record<string, number | string> }
export interface SurfaceResult { x_mm: Record<string, number>; used_width_mm: number; issues: FitIssue[] }

export function checkSurface(
  surface: { id: string; width_mm: number; depth_mm: number; max_load_g: number | null },
  clearHeightMm: number,
  hasDoor: boolean,
  fixtureTemperature: string,
  positions: FitPosition[],
  products: Record<string, FitProduct>,
): SurfaceResult {
  const gap = SETTINGS.gap_mm
  const issues: FitIssue[] = []
  const x: Record<string, number> = {}
  let cursor = 0
  let right = 0
  let load = 0
  const depthAvail = usableDepth(surface.depth_mm, hasDoor)
  const sorted = [...positions].sort((a, b) => a.seq - b.seq || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0))

  for (const p of sorted) {
    const prod = products[p.product_id]
    const width = prod.width_mm * p.facings_wide
    let px = cursor
    if (p.locked && p.locked_x_mm != null) {
      const anchor = p.locked_x_mm
      if (cursor > anchor) {
        issues.push({ code: 'ANCHOR', target: p.id, message: `needs ${cursor - anchor} mm more; ${prod.name} is locked at ${anchor} mm`,
          data: { needed_mm: cursor - anchor, locked_x_mm: anchor } })
      }
      px = anchor
    }
    x[p.id] = px
    cursor = px + width + gap
    right = Math.max(right, px + width)

    const heightNeeded = prod.height_mm * p.facings_high + SETTINGS.finger_clearance_mm
    if (heightNeeded > clearHeightMm) {
      issues.push({ code: 'FIT_H', target: p.id, message: `${prod.name} needs ${heightNeeded} mm height, shelf has ${clearHeightMm} mm`,
        data: { needed_mm: heightNeeded, available_mm: clearHeightMm } })
    }
    const depthNeeded = prod.depth_mm * p.facings_deep
    if (depthNeeded > depthAvail) {
      issues.push({ code: 'FIT_D', target: p.id, message: `${prod.name} needs ${depthNeeded} mm depth, shelf has ${depthAvail} mm`,
        data: { needed_mm: depthNeeded, available_mm: depthAvail } })
    }
    if (p.facings_high > 1 && !(prod.can_stack && p.facings_high <= (prod.max_stack || 1))) {
      issues.push({ code: 'STACK', target: p.id, message: `${prod.name} cannot be stacked ${p.facings_high} high`,
        data: { facings_high: p.facings_high } })
    }
    if (prod.temperature !== fixtureTemperature) {
      issues.push({ code: 'TEMP', target: p.id, message: `${prod.name} is ${prod.temperature}, fixture is ${fixtureTemperature}`,
        data: { product: prod.temperature, fixture: fixtureTemperature } })
    }
    load += (prod.weight_g ?? 0) * p.facings_wide * p.facings_high * p.facings_deep
  }
  if (right > surface.width_mm) {
    issues.push({ code: 'FIT_W', target: surface.id, message: `shelf over-filled by ${right - surface.width_mm} mm`,
      data: { used_mm: right, available_mm: surface.width_mm } })
  }
  if (surface.max_load_g && load > surface.max_load_g) {
    issues.push({ code: 'LOAD', target: surface.id, message: `load ${(load / 1000).toFixed(1)} kg exceeds ${(surface.max_load_g / 1000).toFixed(0)} kg`,
      data: { load_g: load, max_load_g: surface.max_load_g } })
  }
  return { x_mm: x, used_width_mm: right, issues }
}
