// Shapes returned by services/api (snake_case, millimetres and grams, as in spec section 7).

export type Rect = [number, number, number, number] // x, y, w, h

export interface Store {
  id: string; code: string; name: string; format: string | null; timezone: string
  width_mm: number; depth_mm: number; layout_version: number
}
export interface Zone { id: string; code: string; kind: string; name: string; rect: Rect }
export interface Landmark { id: string; kind: string; name: string; rect: Rect }

export interface Fixture {
  id: string; code: string; template_code: string; kind: string
  x_mm: number; y_mm: number; rotation_deg: number
  footprint_w_mm: number; footprint_d_mm: number
  temperature: string; faces: string | null; note: string | null
}
export interface Bay {
  id: string; fixture_id: string; side: string; idx: number
  width_mm: number; height_mm: number; depth_mm: number; has_door: boolean
}
export interface Surface {
  id: string; bay_id: string; kind: string; idx: number; height_from_floor_mm: number
  width_mm: number; depth_mm: number; max_load_g: number | null; notch_pitch_mm: number
  grid_cols: number | null; grid_rows: number | null
}
export interface Section {
  id: string; fixture_id: string; side: string; bay_from: number; bay_to: number; code: string
  category_code: string; image_policy: string; assignment_locked: boolean; positions?: number
}
export interface LayoutDoc {
  store: Store; zones: Zone[]; landmarks: Landmark[]
  fixtures: Record<string, Fixture>; bays: Record<string, Bay>
  surfaces: Record<string, Surface>; sections: Record<string, Section>
}
export interface Category { code: string; department: string; name: string; temperature: string }
export interface TemplateDef {
  kind: string; name: string; bay_width: number; bays_per_side: number; sides: string[]
  height: number; depth_per_side?: number; footprint: [number, number]; temperature: string
  notch_pitch?: number; doors?: boolean
  surfaces: { kind: string; h: number; base?: boolean; grid?: number[] }[]
  max_load_g_per_shelf?: number
}
export interface Issue { fixtures: string[]; message: string; gap_mm?: number; landmark?: string }
export interface LayoutChecks {
  overlaps: Issue[]; aisle_warnings: Issue[]; blocked_doors: Issue[]; out_of_bounds: Issue[]
}
export interface LayoutPayload {
  layout: LayoutDoc; templates: Record<string, TemplateDef>; categories: Record<string, Category>; checks: LayoutChecks
}

export interface Eligibility {
  status: 'eligible' | 'estimated' | 'wrong_temperature' | 'blocked'; reason: string | null; badges: string[]
}
export interface Product {
  id: string; sku: string; gtin: string; name: string; brand: string; category_code: string
  width_mm: number; height_mm: number; depth_mm: number; weight_g: number | null
  temperature: string; dims_source: string; dims_verified: boolean; safety_reviewed: boolean
  has_image: boolean; can_stack: boolean; max_stack: number; colour: string; price: number
  eligibility: Eligibility; units_per_day: number; margin_per_day: number
  image: string | null; pack_size: string | null; case_pack: number | null
  liquid: boolean; fragile: boolean; age_restricted: boolean; hazardous: boolean
}
export interface CatalogProduct extends Omit<Product, 'margin_per_day'> {
  category_name: string | null; department: string | null
}
export interface PlanSurface extends Surface {
  bay_idx: number; bay_has_door: boolean; bay_height_mm: number; level: number
  clear_height_mm: number; band: string; usable_depth_mm: number
}
export interface Position {
  id: string; surface_id: string; product_id: string; seq: number; x_mm: number
  facings_wide: number; facings_high: number; facings_deep: number
  placed_by: string; reason: string | null; rule_ids: string[]; locked: boolean; locked_x_mm: number | null
}
export interface Finding {
  rule_id: string; type: string; severity: 'hard' | 'soft' | 'info'; target: string | null
  message: string; data: Record<string, unknown>
}
export interface Evaluation {
  findings: Finding[]; score: number; rule_scores: Record<string, number>
  hard_breaks: number; soft_findings: number
  summary: { positions: number; skus: number; facings: number; units: number; used_mm: number; capacity_mm: number; fill_pct: number }
}
export interface Planogram { id: string; section_id: string; status: string; row_version: number }
export interface PlanogramPayload {
  planogram: Planogram; section: Section; fixture: Fixture; category: Category | null; store: { code: string }
  surfaces: PlanSurface[]; positions: Record<string, Position>; products: Product[]; evaluation: Evaluation
}
export interface AutofillProposal {
  engine_version: string; rule_set: string; params: Record<string, number>
  positions: Position[]; unplaced: { product_id: string; name: string; reason: string }[]
  anchors: string[]; evaluation: Evaluation
  trace: { step: number; title: string; detail: string }[]
  decisions: Record<string, AutofillDecision>
  priority_brands: string[]
}
export interface AutofillDecision {
  rank: number; top_seller: boolean; priority_brand: boolean; heavy: boolean
  units_per_day: number; margin_per_day: number; facings_deep: number
  target_facings: number; packed_facings: number; final_facings: number; trimmed: number
  level: number; band: string; level_scores: Record<string, number>
  why_level: { reason: string; points: number }[]; too_tall_for_levels: number[]
}
export interface RuleInfo {
  id: string; name: string; type: string; severity: string; weight?: number; params?: Record<string, unknown>
  what?: string; measure?: string
}

export type Command = { type: string; [key: string]: unknown }
export interface CommandResult { inverse: Command[] }
