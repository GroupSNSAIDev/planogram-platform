import type {
  AutofillProposal, CatalogProduct, RuleInfo, Category, Command, Evaluation, LayoutChecks, LayoutPayload, PlanogramPayload, Position, Store,
} from './types'

export class ApiError extends Error {
  status: number
  index: number | null
  constructor(status: number, message: string, index: number | null = null) {
    super(message)
    this.status = status
    this.index = index
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`
    let index: number | null = null
    try {
      const data = await res.json()
      const d = data.detail
      if (typeof d === 'string') message = d
      else if (d?.message) { message = d.message; index = d.index ?? null }
      else if (Array.isArray(d)) message = d.map((e: { msg: string }) => e.msg).join('; ')
    } catch { /* not JSON */ }
    throw new ApiError(res.status, message, index)
  }
  return res.json() as Promise<T>
}

export const api = {
  stores: () => request<(Store & { fixtures: number; sections: number })[]>('GET', '/stores'),
  layout: (code: string) => request<LayoutPayload>('GET', `/stores/${code}/layout`),
  layoutCommands: (code: string, commands: Command[]) =>
    request<{ layout_version: number; inverse: Command[]; checks: LayoutChecks }>('POST', `/stores/${code}/layout/commands`, { commands }),
  templates: () => request<{ code: string; kind: string; name: string; version: number; used_by: number; defaults: LayoutPayload['templates'][string] }[]>('GET', '/fixture-templates'),
  categories: () => request<Category[]>('GET', '/categories'),
  sectionPlanogram: (code: string) => request<PlanogramPayload>('GET', `/sections/${code}/planogram`),
  planogramCommands: (id: string, commands: Command[]) =>
    request<{ row_version: number; positions: Record<string, Position>; evaluation: Evaluation; inverse: Command[] }>(
      'POST', `/planograms/${id}/commands`, { commands }),
  autofill: (id: string) => request<AutofillProposal>('POST', `/planograms/${id}/autofill`),
  validate: (id: string) => request<Evaluation>('POST', `/planograms/${id}/validate`),
  resetDemo: () => request<Record<string, number>>('POST', '/demo/reset'),
  products: () => request<CatalogProduct[]>('GET', '/products'),
  rules: () => request<{ rule_set: { id: string; name: string }; rules: RuleInfo[]; score_formula: string;
    autofill: { engine_version: string; params: Record<string, number> } }>('GET', '/rules'),
  uploadImport: async (file: File, zip: File | null): Promise<ImportReport> => {
    const fd = new FormData()
    fd.append('file', file)
    if (zip) fd.append('images', zip)
    const res = await fetch('/api/imports', { method: 'POST', body: fd })
    if (!res.ok) {
      const d = await res.json().catch(() => ({}))
      throw new ApiError(res.status, d?.detail?.message ?? res.statusText)
    }
    return res.json()
  },
  publishImport: (id: string) => request<Record<string, number>>('POST', `/imports/${id}/publish`),
  storeSections: (code: string) => request<SectionRow[]>('GET', `/stores/${code}/sections`),
  autofillStore: (code: string, fixtureCode: string | null, onlyEmpty: boolean) =>
    request<{ sections_filled: number; sections_skipped: number; positions: number }>('POST', `/stores/${code}/autofill`,
      { fixture_code: fixtureCode, only_empty: onlyEmpty }),
  createStore: (body: { code: string; name: string; width_m: number; depth_m: number; layout: string }) =>
    request<{ code: string; fixtures: number; sections: number }>('POST', '/stores', body),
  deleteStore: (code: string) => request<{ deleted: string }>('DELETE', `/stores/${code}`),
  importDesign: async (file: File, code: string | null) => {
    const fd = new FormData()
    fd.append('file', file)
    if (code) fd.append('code', code)
    const res = await fetch('/api/stores/import', { method: 'POST', body: fd })
    const d = await res.json().catch(() => ({}))
    if (!res.ok) throw new ApiError(res.status, d?.detail?.message ?? res.statusText)
    return d as { code: string; fixtures: number; sections: number; positions: number }
  },
}

export interface SectionRow {
  id: string; code: string; fixture_id: string; fixture_code: string; fixture_kind: string; side: string
  bay_from: number; bay_to: number; bays: number; category_code: string; category_name: string | null
  department: string | null; positions: number; score: number | null; hard_breaks: number | null; assignment_locked: boolean
}

export const mediaUrl = (path: string | null | undefined) => (path ? `/api/media/${path}` : '')

export interface ImportReport {
  id: string; filename: string; status: string
  counts: Record<string, number>
  rows: { row: number; data: Record<string, unknown>; issues: { code: string; severity: string; message: string }[]
    image: string | null; image_source: string | null; quality: number; action: string }[]
}
