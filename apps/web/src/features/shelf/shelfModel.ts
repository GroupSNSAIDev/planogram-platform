// Section elevation model for the shelf planner: where bays sit, which shelf a point is over,
// and live fit checks for a drop (same TS geometry as the golden cases).
import type { PlanSurface, Position, Product } from '../../api/types'
import { checkSurface, maxFacingsDeep, type FitIssue } from '../../geometry/geometry'

export interface SectionModel {
  bays: { idx: number; x0: number; width: number; height: number }[]
  totalWidth: number
  maxHeight: number
  surfaces: PlanSurface[]
  surfaceById: Record<string, PlanSurface>
  bayOffset: Record<number, number>
}

export function buildModel(surfaces: PlanSurface[]): SectionModel {
  const bayIdx = [...new Set(surfaces.map(s => s.bay_idx))].sort((a, b) => a - b)
  const bays: SectionModel['bays'] = []
  const bayOffset: Record<number, number> = {}
  let x = 0
  for (const idx of bayIdx) {
    const own = surfaces.filter(s => s.bay_idx === idx)
    const width = Math.max(...own.map(s => s.width_mm))
    bays.push({ idx, x0: x, width, height: own[0].bay_height_mm })
    bayOffset[idx] = x
    x += width
  }
  return {
    bays, totalWidth: x, maxHeight: Math.max(...bays.map(b => b.height), 0), surfaces,
    surfaceById: Object.fromEntries(surfaces.map(s => [s.id, s])), bayOffset,
  }
}

/** Shelf under a point (x across the section, h height from floor): the highest shelf at or below h. */
export function surfaceAt(model: SectionModel, x: number, h: number): PlanSurface | null {
  const bay = model.bays.find(b => x >= b.x0 && x < b.x0 + b.width) ?? (x < 0 ? model.bays[0] : model.bays.at(-1))
  if (!bay) return null
  const own = model.surfaces.filter(s => s.bay_idx === bay.idx).sort((a, b) => a.height_from_floor_mm - b.height_from_floor_mm)
  let best = own[0] ?? null
  for (const s of own) if (s.height_from_floor_mm <= h) best = s
  return best
}

export function onSurface(positions: Record<string, Position>, surfaceId: string, exclude?: string) {
  return Object.values(positions).filter(p => p.surface_id === surfaceId && p.id !== exclude).sort((a, b) => a.seq - b.seq)
}

/** Index to insert at, from the pointer's x within the shelf. */
export function insertionSeq(row: Position[], products: Record<string, Product>, xInShelf: number): number {
  let i = 0
  for (const p of row) {
    const w = products[p.product_id].width_mm * p.facings_wide
    if (xInShelf > p.x_mm + w / 2) i += 1
  }
  return i
}

export interface DropPreview {
  surface: PlanSurface; seq: number; ok: boolean; issues: FitIssue[]; insertX: number
}

/** Would this product (or moved position) fit if dropped here? */
export function previewDrop(
  model: SectionModel, positions: Record<string, Position>, products: Record<string, Product>,
  fixtureTemp: string, xMm: number, hMm: number, product: Product, moving?: Position,
): DropPreview | null {
  const surface = surfaceAt(model, xMm, hMm)
  if (!surface) return null
  const row = onSurface(positions, surface.id, moving?.id)
  const xIn = xMm - model.bayOffset[surface.bay_idx]
  const seq = insertionSeq(row, products, xIn)
  const cand: Position = moving
    ? { ...moving, surface_id: surface.id }
    : { id: '__new', surface_id: surface.id, product_id: product.id, seq, x_mm: 0, facings_wide: 1, facings_high: 1,
        facings_deep: maxFacingsDeep(product.depth_mm, surface.usable_depth_mm), placed_by: 'planner', reason: null,
        rule_ids: [], locked: false, locked_x_mm: null }
  const list = [...row]
  list.splice(seq, 0, cand)
  const fit = checkSurface(surface, surface.clear_height_mm, surface.bay_has_door, fixtureTemp,
    list.map((p, i) => ({ ...p, seq: i })), products)
  const relevant = fit.issues.filter(i => i.target === cand.id || i.target === surface.id || i.code === 'ANCHOR')
  return { surface, seq, ok: relevant.length === 0, issues: relevant, insertX: fit.x_mm[cand.id] ?? 0 }
}

export const daysOfSupply = (units: number, perDay: number) => units / Math.max(perDay, 0.01)

/** Lighter tint of a hex colour for the facing fill. */
export function tint(hex: string, amount = 0.55): string {
  const n = parseInt(hex.slice(1), 16)
  const r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255
  const mix = (c: number) => Math.round(c + (255 - c) * amount)
  return `rgb(${mix(r)},${mix(g)},${mix(b)})`
}
