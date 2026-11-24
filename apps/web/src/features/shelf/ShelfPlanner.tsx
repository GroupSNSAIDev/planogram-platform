import { useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import {
  AlertTriangle, Check, CheckCircle2, ChevronLeft, ChevronRight, Eraser, ImageOff, Info, Lock, LockOpen, Maximize, Minus, Plus, Redo2,
  ShieldCheck, Sparkles, Trash2, Undo2, X,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, mediaUrl } from '../../api/client'
import type { AutofillDecision, AutofillProposal, Command, Evaluation, Finding, PlanogramPayload, Position, Product } from '../../api/types'
import { PageBar } from '../../app/AppShell'
import { ExportMenu } from '../../app/ExportMenu'
import { rememberStore } from '../../app/currentStore'
import { mm } from '../../app/theme'
import { toast } from '../../app/toast'
import { useKeys } from '../../canvas/useKeys'
import { useHistory } from '../../doc/useHistory'
import { ShelfCanvas } from './ShelfCanvas'
import { buildModel, daysOfSupply } from './shelfModel'

export function ShelfPlanner() {
  const { ref: code = 'G03-A-01' } = useParams()
  const qc = useQueryClient()
  const query = useQuery({ queryKey: ['planogram', code], queryFn: () => api.sectionPlanogram(code) })
  const data = query.data
  const [positions, setPositions] = useState<Record<string, Position>>({})
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [highlight, setHighlight] = useState<string | null>(null)
  const [proposal, setProposal] = useState<AutofillProposal | null>(null)
  const [running, setRunning] = useState(false)
  const [dragProduct, setDragProduct] = useState<Product | null>(null)
  const [showEye, setShowEye] = useState(true)
  const [showMm, setShowMm] = useState(true)
  const [zoomPct, setZoomPct] = useState(100)
  const [zoomReq, setZoomReq] = useState({ factor: 1, n: 0 })
  const [cursor, setCursor] = useState({ x: 0, h: 0 })
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (data) { setPositions(data.positions); setEvaluation(data.evaluation); setProposal(null); setSelected(null); rememberStore(data.store.code) }
  }, [data])

  const pgId = data?.planogram.id
  const send = useCallback(async (commands: Command[]) => {
    if (!pgId) return null
    setSaving(true)
    try {
      const res = await api.planogramCommands(pgId, commands)
      setPositions(res.positions)
      setEvaluation(res.evaluation)
      qc.invalidateQueries({ queryKey: ['layout'] })
      return res.inverse
    } catch (e) {
      toast.error((e as Error).message)
      return null
    } finally {
      setSaving(false)
    }
  }, [pgId, qc])
  const history = useHistory(send)

  const products = useMemo(() => Object.fromEntries((data?.products ?? []).map(p => [p.id, p])), [data])
  const model = useMemo(() => (data ? buildModel(data.surfaces) : null), [data])
  const shown = proposal ? Object.fromEntries(proposal.positions.map(p => [p.id, p])) : positions
  const shownEval = proposal ? proposal.evaluation : evaluation
  const severity = useMemo(() => {
    const m: Record<string, 'hard' | 'soft'> = {}
    for (const f of shownEval?.findings ?? []) {
      if (!f.target || f.severity === 'info') continue
      if (f.severity === 'hard' || !m[f.target]) m[f.target] = f.severity
    }
    return m
  }, [shownEval])
  const sel = selected ? shown[selected] : null

  const runAutofill = async () => {
    if (!pgId) return
    setRunning(true)
    try {
      const p = await api.autofill(pgId)
      setProposal(p)
      setSelected(null)
    } catch (e) {
      toast.error((e as Error).message)
    } finally {
      setRunning(false)
    }
  }
  const accept = async () => {
    if (!proposal) return
    const ok = await history.run([{ type: 'ReplacePositions', positions: proposal.positions, keep_locked: true }])
    if (ok) { toast.ok(`Auto-fill applied: ${proposal.positions.length} positions, score ${proposal.evaluation.score}`); setProposal(null) }
  }
  const setFacings = (p: Position, d: { wide?: number; high?: number; deep?: number }) =>
    history.run([{ type: 'SetFacings', position_id: p.id, wide: d.wide ?? p.facings_wide, high: d.high ?? p.facings_high, deep: d.deep ?? p.facings_deep }])

  useKeys(e => {
    const mod = e.ctrlKey || e.metaKey
    if (mod && e.key.toLowerCase() === 'z' && !e.shiftKey) { e.preventDefault(); if (!proposal) history.undo(); return }
    if (mod && (e.key.toLowerCase() === 'y' || (e.key.toLowerCase() === 'z' && e.shiftKey))) { e.preventDefault(); if (!proposal) history.redo(); return }
    if (e.key === 'Escape') { setSelected(null); setHighlight(null) }
    if (!sel || proposal) return
    if (e.key === '+' || e.key === '=') setFacings(sel, { wide: sel.facings_wide + 1 })
    if (e.key === '-' && sel.facings_wide > 1) setFacings(sel, { wide: sel.facings_wide - 1 })
    if (e.key === 'l' || e.key === 'L') history.run([{ type: sel.locked ? 'Unlock' : 'Lock', position_id: sel.id }])
    if ((e.key === 'Delete' || e.key === 'Backspace') && !sel.locked) history.run([{ type: 'RemovePosition', position_id: sel.id }]).then(ok => ok && setSelected(null))
  })

  if (query.isError) return <div className="p-6 text-bad">Could not load section {code}: {(query.error as Error).message}</div>
  if (!data || !model || !shownEval) return <div className="p-6 text-muted">Loading shelf planner…</div>

  const hard = shownEval.hard_breaks
  const soft = shownEval.soft_findings
  const onShelf = (pid: string) => Object.values(positions).filter(p => p.product_id === pid).length

  return (
    <>
      <PageBar
        crumbs={<><Link to={`/stores/${data.store.code}`} className="hover:text-ink">{data.store.code}</Link> / <Link className="hover:text-ink" to={`/stores/${data.store.code}/fixtures/${data.fixture.code}`}>{data.fixture.code}</Link> / </>}
        title={<SectionSwitcher storeCode={data.store.code} current={data.section.id} label={`${data.section.code} · ${data.category?.name ?? data.section.category_code}`} />}>
        <span className="chip bg-slate-100 text-ink-2">Draft</span>
        <span className="text-[12px] text-muted">{saving ? 'Saving…' : 'Saved'}</span>
        <div className="mx-1 h-6 w-px bg-line" />
        <span className={clsx('chip font-mono', shownEval.score >= 85 ? 'bg-ok-tint text-ok' : shownEval.score >= 60 ? 'bg-amber-tint text-amber-ink' : 'bg-slate-100 text-ink-2')}>
          Score {shownEval.score.toFixed(1)}
        </span>
        <span className={clsx('chip font-mono', hard ? 'bg-bad-tint text-bad' : 'bg-ok-tint text-ok')}>{hard} hard</span>
        <span className={clsx('chip font-mono', soft ? 'bg-amber-tint text-amber-ink' : 'bg-ok-tint text-ok')}>{soft} soft</span>
        <div className="mx-1 h-6 w-px bg-line" />
        <button className="btn btn-primary" disabled={running || !!proposal} onClick={runAutofill}><Sparkles size={15} />{running ? 'Running…' : 'Auto-fill'}</button>
        <button className="btn" disabled={!!proposal} onClick={async () => { if (pgId) { setEvaluation(await api.validate(pgId)); toast.info('Validated with rule set breakfast-v5') } }}><ShieldCheck size={15} />Validate</button>
        <ExportMenu store={data.store.code} section={data.section.id} />
      </PageBar>

      {/* toolbar */}
      <div className="flex h-11 shrink-0 items-center gap-1 border-b border-line bg-white px-3">
        <button className="btn btn-icon btn-ghost" title="Undo (Ctrl+Z)" disabled={!history.canUndo || !!proposal} onClick={history.undo}><Undo2 size={16} /></button>
        <button className="btn btn-icon btn-ghost" title="Redo (Ctrl+Y)" disabled={!history.canRedo || !!proposal} onClick={history.redo}><Redo2 size={16} /></button>
        <div className="mx-2 h-6 w-px bg-line" />
        <span className="text-[12px] text-muted">Facings</span>
        <button className="btn btn-icon btn-ghost" disabled={!sel || !!proposal || sel.locked || sel.facings_wide <= 1} onClick={() => sel && setFacings(sel, { wide: sel.facings_wide - 1 })}><Minus size={15} /></button>
        <span className="w-6 text-center font-mono">{sel ? sel.facings_wide : '–'}</span>
        <button className="btn btn-icon btn-ghost" disabled={!sel || !!proposal || sel.locked} onClick={() => sel && setFacings(sel, { wide: sel.facings_wide + 1 })}><Plus size={15} /></button>
        <button className="btn btn-ghost" disabled={!sel || !!proposal} onClick={() => sel && history.run([{ type: sel.locked ? 'Unlock' : 'Lock', position_id: sel.id }])}>
          {sel?.locked ? <><LockOpen size={15} />Unlock</> : <><Lock size={15} />Placement lock</>}
        </button>
        <button className="btn btn-ghost" disabled={!sel || !!proposal || sel?.locked} onClick={() => sel && history.run([{ type: 'RemovePosition', position_id: sel.id }]).then(ok => ok && setSelected(null))}><Trash2 size={15} />Remove</button>
        <button className="btn btn-ghost" disabled={!!proposal || !Object.keys(positions).length}
          onClick={() => { if (confirm('Remove every product that is not placement-locked?')) history.run([{ type: 'ReplacePositions', positions: [], keep_locked: true }]) }}>
          <Eraser size={15} />Clear unlocked
        </button>
        <div className="mx-2 h-6 w-px bg-line" />
        <button className="btn btn-icon btn-ghost" onClick={() => setZoomReq(z => ({ factor: 1 / 1.25, n: z.n + 1 }))}><Minus size={15} /></button>
        <span className="w-12 text-center font-mono text-[12px]">{zoomPct}%</span>
        <button className="btn btn-icon btn-ghost" onClick={() => setZoomReq(z => ({ factor: 1.25, n: z.n + 1 }))}><Plus size={15} /></button>
        <button className="btn btn-ghost h-8 px-2 text-[12px]" title="Whole section" onClick={() => setZoomReq(z => ({ factor: 0, n: z.n + 1 }))}><Maximize size={14} />Fit</button>
        <button className="btn btn-ghost h-8 px-2 text-[12px]" title="True scale for the height" onClick={() => setZoomReq(z => ({ factor: -1, n: z.n + 1 }))}>1:1 height</button>
        <div className="ml-auto flex items-center gap-3 text-[12px]">
          <label className="flex items-center gap-1.5"><input type="checkbox" checked={showEye} onChange={e => setShowEye(e.target.checked)} />Eye-level band</label>
          <label className="flex items-center gap-1.5"><input type="checkbox" checked={showMm} onChange={e => setShowMm(e.target.checked)} />Show mm</label>
        </div>
      </div>

      <div className="flex min-h-0 flex-1">
        <ProductPanel data={data} onShelf={onShelf} highlight={highlight} setHighlight={setHighlight} setDragProduct={setDragProduct} disabled={!!proposal} />
        <div className="relative min-w-0 flex-1">
          <ShelfCanvas
            model={model}
            positions={shown}
            products={products}
            fixtureTemp={data.fixture.temperature}
            severity={severity}
            selectedId={selected}
            highlightProduct={highlight}
            showEye={showEye}
            showMm={showMm}
            readOnly={!!proposal}
            dragProduct={dragProduct}
            zoomRequest={zoomReq}
            onZoom={setZoomPct}
            onSelect={setSelected}
            onCursor={(x, h) => setCursor({ x, h })}
            onMove={(id, surfaceId, seq) => history.run([{ type: 'MovePosition', position_id: id, surface_id: surfaceId, seq }])}
            onDropProduct={(prod, surfaceId, seq) => {
              setDragProduct(null)
              const id = crypto.randomUUID()
              history.run([{ type: 'AddPosition', position_id: id, surface_id: surfaceId, product_id: prod.id, seq, facings_wide: 1 }])
                .then(ok => ok && setSelected(id))
            }}
          />
          {proposal && <ProposalBanner proposal={proposal} before={evaluation} onAccept={accept} onReject={() => setProposal(null)} />}
          {Object.keys(positions).length === 0 && !proposal && (
            <div className="pointer-events-none absolute inset-x-0 top-24 mx-auto w-[420px] rounded-xl border border-line bg-white/95 p-5 text-center shadow-lg">
              <div className="text-[14px] font-semibold">This section is empty</div>
              <div className="mt-1 text-[13px] text-ink-2">Run <b>Auto-fill</b> to place products by the rules, or drag products from the left panel onto a shelf.</div>
            </div>
          )}
        </div>
        <aside className="flex w-[340px] shrink-0 flex-col overflow-y-auto border-l border-line bg-white">
          {proposal ? <ProposalPanel proposal={proposal} products={products} selected={sel} />
            : <PositionInspector pos={sel} products={products} model={model} setFacings={setFacings}
                run={history.run} />}
          <FindingsPanel evaluation={shownEval} onPick={id => {
            if (shown[id]) setSelected(id)
            else if (products[id]) setHighlight(id)
          }} />
        </aside>
      </div>

      <footer className="flex h-7 shrink-0 items-center gap-5 bg-ink px-4 font-mono text-[11px] text-slate-300">
        <span>Fixture {data.fixture.code} · side {data.section.side} · bays {data.section.bay_from}–{data.section.bay_to}</span>
        <span>Rule set breakfast-v5</span>
        <span>Cursor x {mm(Math.max(0, cursor.x))} · h {mm(Math.max(0, cursor.h))}</span>
        <span className="ml-auto">{shownEval.summary.skus} SKUs · {shownEval.summary.facings} facings · {shownEval.summary.units} units</span>
        <span>Fill {shownEval.summary.fill_pct}%</span>
        <span className={hard ? 'text-red-300' : 'text-emerald-300'}>Hard breaks {hard}</span>
      </footer>
    </>
  )
}

// ----------------------------------------------------------------------------- product panel

function SectionSwitcher({ storeCode, current, label }: { storeCode: string; current: string; label: string }) {
  const navigate = useNavigate()
  const q = useQuery({ queryKey: ['sections', storeCode], queryFn: () => api.storeSections(storeCode) })
  const list = q.data ?? []
  const i = list.findIndex(s => s.id === current)
  const go = (id?: string) => id && navigate(`/sections/${id}/plan`)
  return (
    <span className="flex items-center gap-1">
      <button className="btn btn-icon btn-ghost h-7 w-7" disabled={i <= 0} title="Previous section" onClick={() => go(list[i - 1]?.id)}><ChevronLeft size={15} /></button>
      <select className="input h-8 max-w-[360px] font-semibold" value={current} onChange={e => go(e.target.value)}>
        {i < 0 && <option value={current}>{label}</option>}
        {list.map(s => <option key={s.id} value={s.id}>{s.code} · {s.category_name}{s.positions ? ` (${s.positions})` : ''}</option>)}
      </select>
      <button className="btn btn-icon btn-ghost h-7 w-7" disabled={i < 0 || i >= list.length - 1} title="Next section" onClick={() => go(list[i + 1]?.id)}><ChevronRight size={15} /></button>
      <Link to={`/stores/${storeCode}/plan`} className="ml-1 text-[12px] font-normal text-primary">All sections</Link>
    </span>
  )
}

function ProductPanel({ data, onShelf, highlight, setHighlight, setDragProduct, disabled }: {
  data: PlanogramPayload; onShelf: (id: string) => number; highlight: string | null
  setHighlight: (id: string | null) => void; setDragProduct: (p: Product | null) => void; disabled: boolean
}) {
  const [q, setQ] = useState('')
  const [eligibleOnly, setEligibleOnly] = useState(true)
  const [categoryOnly, setCategoryOnly] = useState(true)
  const list = data.products.filter(p =>
    (!categoryOnly || p.category_code === data.section.category_code)
    && (!eligibleOnly || p.eligibility.status === 'eligible' || p.eligibility.status === 'estimated')
    && (`${p.name} ${p.brand} ${p.gtin} ${p.sku}`.toLowerCase().includes(q.toLowerCase())))
  const total = data.products.filter(p => p.category_code === data.section.category_code).length

  return (
    <aside className="flex w-[290px] shrink-0 flex-col border-r border-line bg-white">
      <div className="space-y-2 border-b border-line p-3">
        <div className="flex items-center justify-between">
          <span className="text-[13px] font-semibold">Products <span className="font-normal text-muted">({list.length}{categoryOnly ? ` of ${total}` : ''})</span></span>
        </div>
        <input className="input w-full" placeholder="Search name, brand, GTIN…" value={q} onChange={e => setQ(e.target.value)} />
        <div className="flex flex-wrap gap-x-3 gap-y-1 text-[12px]">
          <label className="flex items-center gap-1.5"><input type="checkbox" checked={eligibleOnly} onChange={e => setEligibleOnly(e.target.checked)} />Eligible only</label>
          <label className="flex items-center gap-1.5"><input type="checkbox" checked={categoryOnly} onChange={e => setCategoryOnly(e.target.checked)} />{data.category?.name ?? 'This category'} only</label>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-2">
        {list.map(p => {
          const blocked = p.eligibility.status === 'blocked'
          const count = onShelf(p.id)
          return (
            <div key={p.id}
              draggable={!blocked && !disabled}
              onDragStart={e => { e.dataTransfer.setData('text/x-product', p.id); e.dataTransfer.effectAllowed = 'copy'; setDragProduct(p) }}
              onDragEnd={() => setDragProduct(null)}
              onClick={() => setHighlight(highlight === p.id ? null : p.id)}
              title={blocked ? `Cannot be placed: ${p.eligibility.reason}` : 'Drag onto a shelf'}
              className={clsx('mb-1.5 flex gap-2.5 rounded-lg border p-2',
                blocked ? 'cursor-not-allowed border-red-100 bg-bad-tint/40' : 'cursor-grab hover:border-indigo-300 active:cursor-grabbing',
                highlight === p.id ? 'border-primary bg-primary-tint' : 'border-line')}>
              <PackSwatch p={p} />
              <div className="min-w-0 flex-1">
                <div className="truncate text-[12.5px] font-medium">{p.name}</div>
                <div className="font-mono text-[11px] text-muted">{p.brand} · {p.width_mm}×{p.height_mm}×{p.depth_mm}</div>
                <div className="mt-1 flex flex-wrap gap-1">
                  <EligibilityTag p={p} />
                  {count > 0 && <span className="tag bg-primary-tint text-primary">on shelf ×{count}</span>}
                </div>
              </div>
            </div>
          )
        })}
        {list.length === 0 && <div className="p-4 text-center text-[12px] text-muted">No products match.</div>}
      </div>
      <div className="border-t border-line px-3 py-2 text-[11px] text-muted">Drag to a shelf · click to highlight · + / − facings · L lock · Del remove</div>
    </aside>
  )
}

function PackSwatch({ p }: { p: Product }) {
  if (p.image) return <img src={mediaUrl(p.image)} alt="" loading="lazy" className="h-12 w-10 shrink-0 rounded border border-line bg-white object-contain" />
  if (!p.has_image) return <div className="grid h-12 w-10 shrink-0 place-items-center rounded border border-dashed border-slate-300 bg-slate-50 text-slate-400"><ImageOff size={14} /></div>
  return (
    <div className="flex h-12 w-10 shrink-0 flex-col items-center justify-center rounded text-[7px] font-bold leading-tight text-white" style={{ background: p.colour }}>
      <span>{p.brand.toUpperCase()}</span>
    </div>
  )
}

function EligibilityTag({ p }: { p: Product }) {
  const e = p.eligibility
  return (
    <>
      {e.status === 'eligible' && <span className="tag bg-ok-tint text-ok">Eligible</span>}
      {e.status === 'estimated' && <span className="tag bg-amber-tint text-amber-ink">Size estimated · drafts only</span>}
      {e.status === 'wrong_temperature' && <span className="tag bg-bad-tint text-bad">{e.reason}</span>}
      {e.status === 'blocked' && <span className="tag bg-bad-tint text-bad"><AlertTriangle size={10} />Blocked · {e.reason}</span>}
      {e.badges.includes('no_image') && <span className="tag bg-slate-100 text-muted">No image · placeholder</span>}
    </>
  )
}

// ----------------------------------------------------------------------------- inspector

function PositionInspector({ pos, products, model, setFacings, run }: {
  pos: Position | null; products: Record<string, Product>; model: ReturnType<typeof buildModel>
  setFacings: (p: Position, d: { wide?: number; high?: number; deep?: number }) => void; run: (c: Command[]) => Promise<boolean>
}) {
  if (!pos) {
    return (
      <div className="border-b border-line p-4 text-[13px] text-muted">
        <div className="mb-1 font-semibold text-ink">Nothing selected</div>
        Click a product on the shelf to see its facings, placement and why it is there.
      </div>
    )
  }
  const prod = products[pos.product_id]
  const su = model.surfaceById[pos.surface_id]
  const units = pos.facings_wide * pos.facings_high * pos.facings_deep
  const dos = daysOfSupply(units, prod.units_per_day)
  return (
    <div className="border-b border-line">
      <div className="flex gap-3 border-b border-line p-4">
        <PackSwatch p={prod} />
        <div className="min-w-0">
          <div className="text-[14px] font-semibold">{prod.name}</div>
          <div className="font-mono text-[11px] text-muted">GTIN {prod.gtin} · {prod.sku}</div>
          <div className="mt-1 flex flex-wrap gap-1"><EligibilityTag p={prod} /></div>
        </div>
      </div>
      <div className="space-y-4 p-4">
        <section>
          <div className="mb-2 flex items-center justify-between">
            <span className="label-up">Facings</span>
            <span className="font-mono text-[12px] text-primary">{pos.facings_wide} × {pos.facings_high} × {pos.facings_deep}</span>
          </div>
          <div className="grid grid-cols-3 gap-2">
            {(['wide', 'high', 'deep'] as const).map(k => {
              const v = k === 'wide' ? pos.facings_wide : k === 'high' ? pos.facings_high : pos.facings_deep
              return (
                <div key={k} className="rounded-lg border border-line p-1.5 text-center">
                  <div className="text-[11px] capitalize text-muted">{k}</div>
                  <div className="mt-1 flex items-center justify-between">
                    <button className="btn btn-icon h-6 w-6 btn-ghost" disabled={pos.locked || v <= 1} onClick={() => setFacings(pos, { [k]: v - 1 })}><Minus size={12} /></button>
                    <span className="font-mono text-[13px]">{v}</span>
                    <button className="btn btn-icon h-6 w-6 btn-ghost" disabled={pos.locked} onClick={() => setFacings(pos, { [k]: v + 1 })}><Plus size={12} /></button>
                  </div>
                </div>
              )
            })}
          </div>
          <div className="mt-2 flex justify-between text-[12px]">
            <span>Units on shelf <b className="font-mono">{units}</b></span>
            <span>Days of supply <b className={clsx('font-mono', dos < 5 ? 'text-amber-ink' : 'text-ok')}>{dos.toFixed(1)}</b></span>
          </div>
          <div className="mt-1 text-[11px] text-muted">Sells {prod.units_per_day.toFixed(1)} units/day · margin ₹{prod.margin_per_day.toFixed(0)}/day</div>
        </section>
        <section>
          <div className="label-up mb-2">Placement</div>
          <dl className="grid grid-cols-[110px_1fr] gap-y-1.5 text-[12px]">
            <dt className="text-muted">Shelf</dt><dd>Bay {su?.bay_idx} · Shelf {su?.level} · <span className="font-mono">{mm(su?.height_from_floor_mm ?? 0)}</span> · <span className="capitalize">{su?.band}</span></dd>
            <dt className="text-muted">Order</dt><dd className="font-mono">seq {pos.seq + 1} · x {mm(pos.x_mm)}</dd>
            <dt className="text-muted">Width used</dt><dd className="font-mono">{mm(prod.width_mm * pos.facings_wide)}</dd>
            <dt className="text-muted">Orientation</dt><dd>Front (GS1 default)</dd>
            <dt className="text-muted">Placed by</dt><dd className="font-mono">{pos.placed_by}</dd>
          </dl>
        </section>
        <section>
          <div className="label-up mb-2">Lock</div>
          <div className="flex gap-2">
            <button className={clsx('btn flex-1 justify-center', !pos.locked && 'btn-active')} onClick={() => pos.locked && run([{ type: 'Unlock', position_id: pos.id }])}>None</button>
            <button className={clsx('btn flex-1 justify-center', pos.locked && 'btn-active')} onClick={() => !pos.locked && run([{ type: 'Lock', position_id: pos.id }])}><Lock size={13} />Placement lock</button>
          </div>
          {pos.locked && <div className="mt-2 text-[11px] text-ink-2">Keeps shelf, order, facings and left edge at {mm(pos.locked_x_mm ?? 0)}. Auto-fill and edits flow around it; nothing can push it.</div>}
        </section>
        {pos.reason && (
          <section className="rounded-lg border border-indigo-100 bg-primary-tint/50 p-3">
            <div className="label-up mb-1 flex items-center gap-1 !text-primary"><Info size={12} />Why it is here</div>
            <div className="text-[12px] text-ink">{pos.reason}</div>
            <div className="mt-2 flex flex-wrap gap-1">{pos.rule_ids.map(r => <span key={r} className="tag bg-white text-primary">{r}</span>)}</div>
          </section>
        )}
      </div>
    </div>
  )
}

// ----------------------------------------------------------------------------- findings and proposal

function FindingsPanel({ evaluation, onPick }: { evaluation: Evaluation; onPick: (id: string) => void }) {
  const groups: [string, Finding[]][] = [
    ['hard', evaluation.findings.filter(f => f.severity === 'hard')],
    ['soft', evaluation.findings.filter(f => f.severity === 'soft')],
    ['info', evaluation.findings.filter(f => f.severity === 'info')],
  ]
  return (
    <div className="p-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="label-up">Findings</span>
        <span className="font-mono text-[11px] text-muted">score {evaluation.score.toFixed(1)} · fill {evaluation.summary.fill_pct}%</span>
      </div>
      {evaluation.findings.length === 0 && (
        <div className="flex items-center gap-2 rounded-lg bg-ok-tint p-3 text-[12px] text-ok"><CheckCircle2 size={14} />No findings.</div>
      )}
      {groups.map(([sev, list]) => list.map((f, i) => (
        <button key={`${sev}${i}`} onClick={() => f.target && onPick(f.target)}
          className={clsx('mb-1.5 flex w-full items-start gap-2 rounded-lg border p-2 text-left',
            sev === 'hard' ? 'border-red-200 bg-bad-tint' : sev === 'soft' ? 'border-amber-200 bg-amber-tint/60' : 'border-line bg-canvas')}>
          {sev === 'hard' ? <AlertTriangle size={14} className="mt-0.5 shrink-0 text-bad" /> : sev === 'soft' ? <AlertTriangle size={14} className="mt-0.5 shrink-0 text-amber-ink" /> : <Info size={14} className="mt-0.5 shrink-0 text-muted" />}
          <span className="text-[12px]"><b className="font-mono">{f.rule_id}</b> · {f.message}</span>
        </button>
      )))}
      <div className="mt-3 rounded-lg border border-line p-2.5">
        <div className="label-up mb-1.5">Soft rule scores</div>
        {Object.entries(evaluation.rule_scores).map(([r, v]) => (
          <div key={r} className="mb-1 flex items-center gap-2 text-[11px]">
            <span className="w-10 font-mono">{r}</span>
            <div className="h-1.5 flex-1 rounded bg-slate-100"><div className={clsx('h-1.5 rounded', v >= 0.85 ? 'bg-ok' : v >= 0.6 ? 'bg-amber' : 'bg-bad')} style={{ width: `${v * 100}%` }} /></div>
            <span className="w-9 text-right font-mono">{Math.round(v * 100)}%</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function ProposalBanner({ proposal, before, onAccept, onReject }: {
  proposal: AutofillProposal; before: Evaluation | null; onAccept: () => void; onReject: () => void
}) {
  const ev = proposal.evaluation
  return (
    <div className="absolute inset-x-4 bottom-12 z-10 flex items-center gap-4 rounded-xl border border-indigo-200 bg-white px-4 py-3 shadow-lg">
      <div className="grid size-9 place-items-center rounded-lg bg-primary text-white"><Sparkles size={18} /></div>
      <div className="flex-1">
        <div className="text-[13px] font-semibold">Auto-fill proposal · {proposal.engine_version} · rules {proposal.rule_set}</div>
        <div className="text-[12px] text-ink-2">
          {ev.summary.positions} products placed · {proposal.unplaced.length} not placed · {ev.summary.facings} facings · fill {ev.summary.fill_pct}% ·
          score <b>{before ? before.score.toFixed(1) : '–'} → {ev.score.toFixed(1)}</b> · {ev.hard_breaks} hard breaks
          {proposal.anchors.length > 0 && <> · {proposal.anchors.length} locked kept in place</>}
        </div>
      </div>
      <button className="btn" onClick={onReject}><X size={14} />Reject</button>
      <button className="btn btn-primary" onClick={onAccept}><Check size={14} />Accept</button>
    </div>
  )
}

function DecisionView({ d }: { d: AutofillDecision }) {
  const levels = Object.entries(d.level_scores).sort((a, b) => Number(b[0]) - Number(a[0]))
  const max = Math.max(...levels.map(([, v]) => Math.abs(v)), 1)
  return (
    <div className="mt-3 space-y-2 border-t border-indigo-100 pt-2 text-[11.5px]">
      <div className="grid grid-cols-2 gap-x-2 gap-y-0.5">
        <span className="text-muted">Rank by margin</span><span className="font-mono">#{d.rank}{d.top_seller ? ' · top seller' : ''}</span>
        <span className="text-muted">Sells</span><span className="font-mono">{d.units_per_day.toFixed(1)}/day · ₹{d.margin_per_day.toFixed(0)} margin</span>
        <span className="text-muted">Facings</span><span className="font-mono">target {d.target_facings} → packed {d.packed_facings} → final {d.final_facings}</span>
        <span className="text-muted">Deep</span><span className="font-mono">{d.facings_deep} per facing</span>
      </div>
      <div>
        <div className="font-medium">Why shelf {d.level} ({d.band}):</div>
        {d.why_level.length === 0 && <div className="text-muted">no preference: emptiest level that fits</div>}
        {d.why_level.map((w, i) => (
          <div key={i} className="flex justify-between"><span>{w.reason}</span><span className={clsx('font-mono', w.points >= 0 ? 'text-ok' : 'text-bad')}>{w.points > 0 ? '+' : ''}{w.points}</span></div>
        ))}
      </div>
      <div>
        <div className="font-medium">Score of each shelf level it fits:</div>
        {levels.map(([lv, v]) => (
          <div key={lv} className="flex items-center gap-2">
            <span className="w-12 font-mono">Shelf {lv}</span>
            <div className="h-1.5 flex-1 rounded bg-white"><div className={clsx('h-1.5 rounded', Number(lv) === d.level ? 'bg-primary' : 'bg-slate-300')} style={{ width: `${(Math.max(0, v + max) / (2 * max)) * 100}%` }} /></div>
            <span className="w-10 text-right font-mono">{v.toFixed(1)}</span>
          </div>
        ))}
        {d.too_tall_for_levels.length > 0 && <div className="text-muted">Too tall for shelf {d.too_tall_for_levels.join(', ')}</div>}
      </div>
    </div>
  )
}

function ProposalPanel({ proposal, products, selected }: { proposal: AutofillProposal; products: Record<string, Product>; selected: Position | null }) {
  return (
    <div className="border-b border-line p-4">
      <div className="label-up mb-2">Proposal preview</div>
      <p className="text-[12px] text-ink-2">Nothing is saved until you accept. Click a product on the shelf to see why it was placed there.</p>
      {selected && (
        <div className="mt-3 rounded-lg border border-indigo-100 bg-primary-tint/50 p-3">
          <div className="text-[12px] font-semibold">{products[selected.product_id]?.name}</div>
          <div className="mt-1 text-[12px]">{selected.reason ?? 'Placement-locked: kept exactly where it was.'}</div>
          <div className="mt-2 flex flex-wrap gap-1">{selected.rule_ids.map(r => <span key={r} className="tag bg-white text-primary">{r}</span>)}</div>
          {proposal.decisions[selected.product_id] && <DecisionView d={proposal.decisions[selected.product_id]} />}
        </div>
      )}
      <details className="mt-3 rounded-lg border border-line" open={!selected}>
        <summary className="cursor-pointer px-3 py-2 text-[12px] font-semibold">How auto-fill decided ({proposal.trace.length} steps)</summary>
        <ol className="space-y-2 px-3 pb-3">
          {proposal.trace.map(t => (
            <li key={t.step} className="flex gap-2">
              <span className="grid size-5 shrink-0 place-items-center rounded-full bg-primary text-[10px] font-bold text-white">{t.step}</span>
              <div><div className="text-[12px] font-medium">{t.title}</div><div className="text-[11.5px] text-ink-2">{t.detail}</div></div>
            </li>
          ))}
        </ol>
        <div className="px-3 pb-3 text-[11px]"><Link className="text-primary" to="/rules">See every rule →</Link></div>
      </details>
      {proposal.unplaced.length > 0 && (
        <div className="mt-3">
          <div className="label-up mb-1.5">Not placed ({proposal.unplaced.length})</div>
          {proposal.unplaced.map(u => (
            <div key={u.product_id} className="mb-1.5 rounded-lg border border-amber-200 bg-amber-tint/60 p-2 text-[12px]">
              <div className="font-medium">{u.name}</div>
              <div className="text-ink-2">{u.reason}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
