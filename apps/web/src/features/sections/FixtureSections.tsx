import { useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { api } from '../../api/client'
import { toast } from '../../app/toast'
import { ExternalLink, Lock, LockOpen, Merge, Plus, Redo2, Scissors, Sparkles, Trash2, Undo2 } from 'lucide-react'
import { useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import type { Bay, Category, Command, Fixture, LayoutDoc, Section, Surface, TemplateDef } from '../../api/types'
import { PageBar } from '../../app/AppShell'
import { DEPT_COLOUR, mm, NON_MERCH } from '../../app/theme'
import { useElementSize } from '../../canvas/useElementSize'
import { useKeys } from '../../canvas/useKeys'
import { clearHeights, eyeBand } from '../../geometry/geometry'
import { useLayout } from '../floor/useLayout'
import { ExportMenu } from '../../app/ExportMenu'
import { useStoreCode } from '../../app/currentStore'

type Sel =
  | { kind: 'section'; id: string }
  | { kind: 'bays'; side: string; from: number; to: number }
  | { kind: 'shelf'; id: string }
  | null

export function FixtureSections() {
  const { fixtureCode = 'G03' } = useParams()
  const code = useStoreCode()
  const navigate = useNavigate()
  const { query, doc, history, templates, categories, saving } = useLayout(code)
  const qc = useQueryClient()
  const [sel, setSel] = useState<Sel>(null)

  useKeys(e => {
    const mod = e.ctrlKey || e.metaKey
    if (mod && e.key.toLowerCase() === 'z') { e.preventDefault(); if (e.shiftKey) history.redo(); else history.undo() }
    if (mod && e.key.toLowerCase() === 'y') { e.preventDefault(); history.redo() }
    if (e.key === 'Escape') setSel(null)
  })

  const fixture = doc ? Object.values(doc.fixtures).find(f => f.code === fixtureCode) : undefined
  const merchFixtures = useMemo(() => doc ? Object.values(doc.fixtures)
    .filter(f => !NON_MERCH.has(f.kind)).sort((a, b) => a.code.localeCompare(b.code, undefined, { numeric: true })) : [], [doc])

  if (query.isError) return <div className="p-6 text-bad">{(query.error as Error).message}</div>
  if (!doc || !templates || !categories) return <div className="p-6 text-muted">Loading…</div>
  if (!fixture) return <div className="p-6">Fixture {fixtureCode} not found. <Link className="text-primary" to={`/stores/${code}/floor`}>Back to floor</Link></div>

  const tpl = templates[fixture.template_code]
  const bays = Object.values(doc.bays).filter(b => b.fixture_id === fixture.id)
  const sections = Object.values(doc.sections).filter(s => s.fixture_id === fixture.id)
  const sides = [...new Set(bays.map(b => b.side))].sort()
  const run = (cmds: Command[]) => history.run(cmds)

  return (
    <>
      <PageBar crumbs={<><Link to={`/stores/${code}`} className="hover:text-ink">{code}</Link> / <Link to={`/stores/${code}/floor`} className="hover:text-ink">Floor</Link> / </>}
        title={<span className="flex items-center gap-2">Fixture & sections
          <select className="input h-8 font-mono" value={fixture.code} onChange={e => { setSel(null); navigate(`/stores/${code}/fixtures/${e.target.value}`) }}>
            {merchFixtures.map(f => <option key={f.id} value={f.code}>{f.code} · {templates[f.template_code]?.name ?? f.kind}</option>)}
          </select></span>}>
        <span className="text-[12px] text-muted">{saving ? 'Saving…' : 'Saved'}</span>
        <button className="btn" onClick={async () => {
          try {
            const r = await api.autofillStore(code, fixture.code, false)
            toast.ok(`Auto-filled ${r.sections_filled} section(s) of ${fixture.code}: ${r.positions} placements`)
            await qc.invalidateQueries()
          } catch (e) { toast.error((e as Error).message) }
        }}><Sparkles size={15} />Auto-fill this fixture</button>
        <ExportMenu store={code} fixture={fixture.code} />
        <button className="btn btn-icon btn-ghost" disabled={!history.canUndo} onClick={history.undo} title="Undo"><Undo2 size={16} /></button>
        <button className="btn btn-icon btn-ghost" disabled={!history.canRedo} onClick={history.redo} title="Redo"><Redo2 size={16} /></button>
      </PageBar>
      <div className="flex min-h-0 flex-1">
        <div className="min-w-0 flex-1 overflow-y-auto p-5">
          <div className="mb-4 flex flex-wrap items-center gap-x-6 gap-y-1 text-[12px] text-ink-2">
            <span><b className="font-mono text-ink">{fixture.code}</b> · {tpl?.name}</span>
            <span>Temperature <b className="capitalize text-ink">{fixture.temperature}</b></span>
            <span>Bays <b className="font-mono text-ink">{tpl?.bays_per_side} × {tpl?.bay_width} mm</b></span>
            <span>Height <b className="font-mono text-ink">{tpl?.height} mm</b></span>
            <span>Depth <b className="font-mono text-ink">{tpl?.depth_per_side} mm</b></span>
            <span>Notch pitch <b className="font-mono text-ink">{tpl?.notch_pitch ?? 25} mm</b></span>
          </div>
          {sides.length === 0 && <div className="card p-6 text-muted">This fixture has no shelves (a landmark such as a checkout).</div>}
          {sides.map(side => (
            <SideElevation
              key={side}
              side={side}
              fixture={fixture}
              tpl={tpl}
              bays={bays.filter(b => b.side === side).sort((a, b) => a.idx - b.idx)}
              surfaces={doc.surfaces}
              sections={sections.filter(s => s.side === side)}
              categories={categories}
              sel={sel}
              setSel={setSel}
              run={run}
            />
          ))}
          <p className="mt-2 text-[12px] text-muted">
            Drag a shelf to move it (snaps to the notch pitch). Click a section to edit it, drag its edge handles to resize.
            Click empty bays (Shift+click to extend) to create a section. Bay 1 is at the back of the store.
          </p>
        </div>
        <Inspector doc={doc} fixture={fixture} tpl={tpl} sections={sections} bays={bays} categories={categories} sel={sel} setSel={setSel} run={run} storeCode={code} />
      </div>
    </>
  )
}

// ----------------------------------------------------------------------------- elevation

interface SideProps {
  side: string; fixture: Fixture; tpl?: TemplateDef; bays: Bay[]; surfaces: LayoutDoc['surfaces']; sections: Section[]
  categories: Record<string, Category>; sel: Sel; setSel: (s: Sel) => void; run: (c: Command[]) => Promise<boolean>
}

function SideElevation({ side, fixture, bays, surfaces, sections, categories, sel, setSel, run }: SideProps) {
  const [ref, size] = useElementSize<HTMLDivElement>()
  const svgRef = useRef<SVGSVGElement>(null)
  const [dragShelf, setDragShelf] = useState<{ id: string; h: number } | null>(null)
  const [dragEdge, setDragEdge] = useState<{ id: string; edge: 'from' | 'to'; bay: number } | null>(null)

  const totalW = bays.reduce((a, b) => a + b.width_mm, 0)
  const H = Math.max(...bays.map(b => b.height_mm), 1)
  const left = 48, top = 34, bandH = 26
  // at least 220 px tall so shelves are easy to drag; wide fixtures scroll sideways
  const s = size.width ? Math.max(Math.min((size.width - left - 16) / totalW, 300 / H), 220 / H) : 0.1
  const svgW = Math.max(size.width, left + totalW * s + 16)
  const bayX = (idx: number) => left + bays.filter(b => b.idx < idx).reduce((a, b) => a + b.width_mm, 0) * s
  const yOf = (h: number) => top + bandH + 8 + (H - h) * s
  const sectionAt = (idx: number) => sections.find(x => x.bay_from <= idx && idx <= x.bay_to)
  const pitch = bays.length ? (Object.values(surfaces).find(x => x.bay_id === bays[0].id)?.notch_pitch_mm ?? 25) : 25

  const svgPoint = (e: React.PointerEvent) => {
    const r = svgRef.current!.getBoundingClientRect()
    return { x: e.clientX - r.left, y: e.clientY - r.top }
  }
  const bayAtX = (x: number) => {
    for (const b of bays) if (x < bayX(b.idx) + b.width_mm * s) return b.idx
    return bays.at(-1)?.idx ?? 1
  }

  const onPointerMove = (e: React.PointerEvent) => {
    if (dragShelf) {
      const p = svgPoint(e)
      const h = Math.round((H - (p.y - top - bandH - 8) / s) / pitch) * pitch
      setDragShelf({ ...dragShelf, h: Math.max(0, Math.min(H, h)) })
    } else if (dragEdge) {
      const p = svgPoint(e)
      const bay = bayAtX(p.x + (dragEdge.edge === 'to' ? -1 : 1))
      setDragEdge({ ...dragEdge, bay })
    }
  }
  const onPointerUp = () => {
    if (dragShelf) {
      const surf = surfaces[dragShelf.id]
      if (surf && surf.height_from_floor_mm !== dragShelf.h) run([{ type: 'UpdateSurface', surface_id: surf.id, height_from_floor_mm: dragShelf.h }])
      setDragShelf(null)
    }
    if (dragEdge) {
      const sec = sections.find(x => x.id === dragEdge.id)
      if (sec) {
        const from = dragEdge.edge === 'from' ? Math.min(dragEdge.bay, sec.bay_to) : sec.bay_from
        const to = dragEdge.edge === 'to' ? Math.max(dragEdge.bay, sec.bay_from) : sec.bay_to
        if (from !== sec.bay_from || to !== sec.bay_to) run([{ type: 'ResizeSection', section_id: sec.id, bay_from: from, bay_to: to }])
      }
      setDragEdge(null)
    }
  }

  const sideLabel = side === 'TOP' ? 'Top view' : `Side ${side}${fixture.faces?.includes('/') ? ` · faces ${dirName(fixture.faces.split('/')[side === 'A' ? 0 : 1])}` : ''}`
  const svgH = top + bandH + 8 + H * s + 26

  return (
    <div className="card mb-5 p-3">
      <div className="mb-1 flex items-center gap-2">
        <span className="text-[13px] font-semibold">{sideLabel}</span>
        <span className="text-[12px] text-muted">{sections.length} section{sections.length === 1 ? '' : 's'} · {bays.length} bay{bays.length === 1 ? '' : 's'}</span>
      </div>
      <div ref={ref} className="w-full overflow-x-auto">
        {size.width > 0 && (
          <svg ref={svgRef} width={svgW} height={svgH} className="select-none touch-none"
            onPointerMove={onPointerMove} onPointerUp={onPointerUp} onPointerLeave={onPointerUp}>
            {/* height ruler */}
            {[0, 500, 1000, 1500, 2000].filter(h => h <= H).map(h => (
              <g key={h}>
                <line x1={left - 6} x2={left} y1={yOf(h)} y2={yOf(h)} stroke="#94A3B8" />
                <text x={left - 9} y={yOf(h) + 3} fontSize={10} textAnchor="end" fill="#64748B" className="font-mono">{h}</text>
              </g>
            ))}
            {/* eye-level band */}
            <rect x={left} y={yOf(Math.min(1600, H))} width={totalW * s} height={(Math.min(1600, H) - 1200) * s} fill="#EEF2FF" opacity={H > 1200 ? 0.9 : 0} />
            {H > 1200 && <text x={left + totalW * s - 4} y={yOf(Math.min(1600, H)) + 11} fontSize={9.5} textAnchor="end" fill="#4338CA">EYE LEVEL 1,200–1,600</text>}
            {/* bays */}
            {bays.map(b => {
              const x = bayX(b.idx), w = b.width_mm * s
              const free = !sectionAt(b.idx)
              const picked = sel?.kind === 'bays' && sel.side === side && sel.from <= b.idx && b.idx <= sel.to
              return (
                <g key={b.id}>
                  <rect x={x} y={yOf(b.height_mm)} width={w} height={b.height_mm * s} fill={picked ? '#E0E7FF' : 'transparent'}
                    stroke="#334155" strokeWidth={1}
                    onClick={e => {
                      if (!free) { const sc = sectionAt(b.idx); if (sc) setSel({ kind: 'section', id: sc.id }); return }
                      if (e.shiftKey && sel?.kind === 'bays' && sel.side === side) setSel({ ...sel, from: Math.min(sel.from, b.idx), to: Math.max(sel.to, b.idx) })
                      else setSel({ kind: 'bays', side, from: b.idx, to: b.idx })
                    }} />
                  <text x={x + w / 2} y={svgH - 8} fontSize={10.5} textAnchor="middle" fill="#64748B" className="font-mono">Bay {b.idx}</text>
                  {b.has_door && <rect x={x + 2} y={yOf(b.height_mm) + 2} width={w - 4} height={b.height_mm * s - 4} fill="none" stroke="#3B82F6" strokeDasharray="3 3" pointerEvents="none" />}
                </g>
              )
            })}
            {/* shelves */}
            {bays.map(b => {
              const own = Object.values(surfaces).filter(x => x.bay_id === b.id && (x.kind === 'shelf' || x.kind === 'peg'))
              return own.map(su => {
                const h = dragShelf?.id === su.id ? dragShelf.h : su.height_from_floor_mm
                const active = sel?.kind === 'shelf' && sel.id === su.id
                return (
                  <g key={su.id} className="cursor-ns-resize"
                    onPointerDown={e => { e.stopPropagation(); (e.target as Element).setPointerCapture?.(e.pointerId); setSel({ kind: 'shelf', id: su.id }); setDragShelf({ id: su.id, h }) }}>
                    <rect x={bayX(b.idx) + 1} y={yOf(h) - 5} width={b.width_mm * s - 2} height={10} fill="transparent" />
                    <line x1={bayX(b.idx) + 1} x2={bayX(b.idx) + b.width_mm * s - 1} y1={yOf(h)} y2={yOf(h)}
                      stroke={active ? '#4338CA' : su.kind === 'peg' ? '#6366F1' : '#334155'} strokeWidth={active ? 4 : 3}
                      strokeDasharray={su.kind === 'peg' ? '4 3' : undefined} />
                    {dragShelf?.id === su.id && (
                      <text x={bayX(b.idx) + 4} y={yOf(h) - 7} fontSize={11} fill="#4338CA" fontWeight={600} className="font-mono">{h} mm</text>
                    )}
                  </g>
                )
              })
            })}
            {/* section band */}
            {sections.map(sc => {
              const from = dragEdge?.id === sc.id && dragEdge.edge === 'from' ? Math.min(dragEdge.bay, sc.bay_to) : sc.bay_from
              const to = dragEdge?.id === sc.id && dragEdge.edge === 'to' ? Math.max(dragEdge.bay, sc.bay_from) : sc.bay_to
              const x0 = bayX(from), x1 = bayX(to) + (bays.find(b => b.idx === to)?.width_mm ?? 0) * s
              const cat = categories[sc.category_code]
              const active = sel?.kind === 'section' && sel.id === sc.id
              const colour = DEPT_COLOUR[cat?.department ?? ''] ?? '#E2E8F0'
              return (
                <g key={sc.id}>
                  <rect x={x0} y={yOf(H) - 6} width={x1 - x0} height={H * s + 6} fill={colour} opacity={0.18} pointerEvents="none" />
                  <g className="cursor-pointer" onClick={() => setSel({ kind: 'section', id: sc.id })}>
                    <rect x={x0 + 1} y={top} width={x1 - x0 - 2} height={bandH} rx={4} fill={colour}
                      stroke={active ? '#4338CA' : '#94A3B8'} strokeWidth={active ? 2 : 1} />
                    <text x={x0 + 8} y={top + 17} fontSize={11.5} fill="#0F172A" fontWeight={600}>
                      {sc.assignment_locked ? '🔒 ' : ''}{cat?.name ?? sc.category_code}
                      <tspan fill="#475569" fontWeight={400} className="font-mono"> · {sc.code}{sc.positions ? ` · ${sc.positions} placed` : ''}</tspan>
                    </text>
                  </g>
                  {active && !sc.assignment_locked && (['from', 'to'] as const).map(edge => (
                    <rect key={edge} x={(edge === 'from' ? x0 : x1) - 5} y={top - 2} width={10} height={bandH + 4} rx={3}
                      fill="#4338CA" className="cursor-ew-resize"
                      onPointerDown={e => { e.stopPropagation(); setDragEdge({ id: sc.id, edge, bay: edge === 'from' ? sc.bay_from : sc.bay_to }) }} />
                  ))}
                </g>
              )
            })}
            {bays.filter(b => !sectionAt(b.idx)).map(b => (
              <g key={b.id} className="cursor-pointer" onClick={e => {
                if (e.shiftKey && sel?.kind === 'bays' && sel.side === side) setSel({ ...sel, from: Math.min(sel.from, b.idx), to: Math.max(sel.to, b.idx) })
                else setSel({ kind: 'bays', side, from: b.idx, to: b.idx })
              }}>
                <rect x={bayX(b.idx) + 1} y={top} width={b.width_mm * s - 2} height={bandH} rx={4} fill="#fff" stroke="#CBD5E1" strokeDasharray="4 3" />
                <text x={bayX(b.idx) + b.width_mm * s / 2} y={top + 17} fontSize={11} textAnchor="middle" fill="#94A3B8">free</text>
              </g>
            ))}
          </svg>
        )}
      </div>
    </div>
  )
}

const dirName = (d?: string) => ({ N: 'north', E: 'east', S: 'south', W: 'west' } as Record<string, string>)[d ?? ''] ?? d ?? ''

// ----------------------------------------------------------------------------- inspector

function Inspector({ doc, fixture, tpl, sections, bays, categories, sel, setSel, run, storeCode }: {
  doc: LayoutDoc; fixture: Fixture; tpl?: TemplateDef; sections: Section[]; bays: Bay[]
  categories: Record<string, Category>; sel: Sel; setSel: (s: Sel) => void; run: (c: Command[]) => Promise<boolean>; storeCode: string
}) {
  const catOptions = useMemo(() => Object.values(categories)
    .filter(c => c.temperature === fixture.temperature)
    .sort((a, b) => a.department.localeCompare(b.department) || a.name.localeCompare(b.name)), [categories, fixture.temperature])

  return (
    <aside className="w-[320px] shrink-0 overflow-y-auto border-l border-line bg-white">
      {!sel && (
        <div className="p-4">
          <div className="label-up mb-2">Sections on {fixture.code}</div>
          {sections.sort((a, b) => a.side.localeCompare(b.side) || a.bay_from - b.bay_from).map(sc => (
            <button key={sc.id} onClick={() => setSel({ kind: 'section', id: sc.id })}
              className="mb-1.5 flex w-full items-center gap-2 rounded-md border border-line px-2 py-1.5 text-left hover:bg-canvas">
              <span className="size-2.5 rounded-sm" style={{ background: DEPT_COLOUR[categories[sc.category_code]?.department ?? ''] }} />
              <span className="flex-1 truncate text-[12px]">{categories[sc.category_code]?.name}</span>
              <span className="font-mono text-[11px] text-muted">{sc.side} {sc.bay_from}–{sc.bay_to}</span>
            </button>
          ))}
          <p className="mt-3 text-[12px] text-muted">Select a section, a shelf or free bays on the elevation.</p>
        </div>
      )}
      {sel?.kind === 'section' && (() => {
        const sc = doc.sections[sel.id]
        if (!sc) return null
        return <SectionPanel key={`${sc.id}-${sc.bay_from}-${sc.bay_to}`} sc={sc} sections={sections} bays={bays} categories={categories} catOptions={catOptions} tpl={tpl} run={run} setSel={setSel} storeCode={storeCode} />
      })()}
      {sel?.kind === 'bays' && <CreatePanel key={`${sel.side}${sel.from}${sel.to}`} fixture={fixture} sel={sel} catOptions={catOptions} run={run} setSel={setSel} sections={sections} />}
      {sel?.kind === 'shelf' && doc.surfaces[sel.id] && <ShelfPanel key={`${sel.id}-${doc.surfaces[sel.id].height_from_floor_mm}`} surface={doc.surfaces[sel.id]} doc={doc} bays={bays} sections={sections} run={run} />}
    </aside>
  )
}

function SectionPanel({ sc, sections, bays, categories, catOptions, tpl, run, setSel }: {
  sc: Section; sections: Section[]; bays: Bay[]; categories: Record<string, Category>; catOptions: Category[]
  tpl?: TemplateDef; run: (c: Command[]) => Promise<boolean>; setSel: (s: Sel) => void; storeCode: string
}) {
  const cat = categories[sc.category_code]
  const sideBays = bays.filter(b => b.side === sc.side).length
  const [from, setFrom] = useState(sc.bay_from)
  const [to, setTo] = useState(sc.bay_to)
  const [splitAt, setSplitAt] = useState(Math.min(sc.bay_to, sc.bay_from + Math.ceil((sc.bay_to - sc.bay_from + 1) / 2)))
  const prev = sections.find(x => x.side === sc.side && x.bay_to + 1 === sc.bay_from)
  const next = sections.find(x => x.side === sc.side && x.bay_from === sc.bay_to + 1)
  const locked = sc.assignment_locked
  const hasShelves = tpl?.surfaces.some(x => x.kind === 'shelf')

  return (
    <div className="p-4">
      <div className="flex items-center gap-2">
        <span className="size-3 rounded-sm" style={{ background: DEPT_COLOUR[cat?.department ?? ''] }} />
        <span className="font-mono text-[14px] font-semibold">{sc.code}</span>
        {locked && <span className="tag bg-slate-100 text-slate-700"><Lock size={11} />Assignment-locked</span>}
      </div>
      <div className="mt-1 text-[12px] text-muted">{cat?.department} · {cat?.name} · side {sc.side} · bays {sc.bay_from}–{sc.bay_to}{sc.positions ? ` · ${sc.positions} products placed` : ''}</div>

      {hasShelves && (
        <Link to={`/sections/${sc.id}/plan`} className="btn btn-primary mt-4 w-full justify-center"><ExternalLink size={14} />Open shelf planner</Link>
      )}

      <div className="mt-5 space-y-4">
        <label className="block">
          <div className="label-up mb-1">Category</div>
          <select className="input w-full" disabled={locked} value={sc.category_code}
            onChange={e => run([{ type: 'AssignSectionCategory', section_id: sc.id, category_code: e.target.value }])}>
            {[...(catOptions.some(c => c.code === sc.category_code) ? [] : [cat].filter(Boolean) as Category[]), ...catOptions].map(c =>
              <option key={c.code} value={c.code}>{c.department} · {c.name}</option>)}
          </select>
        </label>
        <div>
          <div className="label-up mb-1">Bay range</div>
          <div className="flex items-center gap-2">
            <input type="number" className="input w-16 font-mono" min={1} max={sideBays} disabled={locked} value={from} onChange={e => setFrom(Number(e.target.value))} />
            <span className="text-muted">to</span>
            <input type="number" className="input w-16 font-mono" min={1} max={sideBays} disabled={locked} value={to} onChange={e => setTo(Number(e.target.value))} />
            <button className="btn" disabled={locked || (from === sc.bay_from && to === sc.bay_to)}
              onClick={() => run([{ type: 'ResizeSection', section_id: sc.id, bay_from: from, bay_to: to }])}>Resize</button>
          </div>
        </div>
        {sc.bay_to > sc.bay_from && (
          <div>
            <div className="label-up mb-1">Split</div>
            <div className="flex items-center gap-2">
              <span className="text-[12px] text-muted">New section from bay</span>
              <select className="input w-16 font-mono" disabled={locked} value={splitAt} onChange={e => setSplitAt(Number(e.target.value))}>
                {Array.from({ length: sc.bay_to - sc.bay_from }, (_, i) => sc.bay_from + 1 + i).map(b => <option key={b}>{b}</option>)}
              </select>
              <button className="btn" disabled={locked} onClick={async () => {
                const id = crypto.randomUUID()
                if (await run([{ type: 'SplitSection', section_id: sc.id, at_bay: splitAt, new_section_id: id }])) setSel({ kind: 'section', id })
              }}><Scissors size={14} />Split</button>
            </div>
          </div>
        )}
        {(prev || next) && (
          <div>
            <div className="label-up mb-1">Merge</div>
            <div className="flex flex-wrap gap-2">
              {prev && <button className="btn" disabled={locked || prev.assignment_locked} onClick={() => run([{ type: 'MergeSection', section_id: sc.id, other_section_id: prev.id }])}><Merge size={14} />with {prev.code}</button>}
              {next && <button className="btn" disabled={locked || next.assignment_locked} onClick={() => run([{ type: 'MergeSection', section_id: sc.id, other_section_id: next.id }])}><Merge size={14} />with {next.code}</button>}
            </div>
          </div>
        )}
        <label className="block">
          <div className="label-up mb-1">Image policy</div>
          <select className="input w-full" value={sc.image_policy}
            onChange={e => run([{ type: 'SetSectionImagePolicy', section_id: sc.id, image_policy: e.target.value }])}>
            <option value="placeholder_ok">Scaled placeholders allowed</option>
            <option value="required">Front image required</option>
          </select>
        </label>
        <div className="flex flex-col gap-2 border-t border-line pt-4">
          <button className="btn justify-center" onClick={() => run([{ type: 'SetAssignmentLock', section_id: sc.id, locked: !locked }])}>
            {locked ? <><LockOpen size={14} />Unlock assignment</> : <><Lock size={14} />Assignment-lock this space</>}
          </button>
          <p className="text-[11px] text-muted">An assignment lock keeps this space for the category: it cannot be resized, split, merged or reassigned (spec 13.3).</p>
          <button className="btn justify-center text-bad" disabled={locked}
            onClick={async () => { if (await run([{ type: 'RemoveSection', section_id: sc.id }])) setSel(null) }}><Trash2 size={14} />Remove section</button>
        </div>
      </div>
    </div>
  )
}

function CreatePanel({ fixture, sel, catOptions, run, setSel, sections }: {
  fixture: Fixture; sel: Extract<Sel, { kind: 'bays' }>; catOptions: Category[]; run: (c: Command[]) => Promise<boolean>
  setSel: (s: Sel) => void; sections: Section[]
}) {
  const [cat, setCat] = useState(catOptions[0]?.code ?? '')
  const clash = sections.find(s => s.side === sel.side && sel.from <= s.bay_to && s.bay_from <= sel.to)
  return (
    <div className="p-4">
      <div className="text-[14px] font-semibold">New section</div>
      <div className="mt-1 text-[12px] text-muted">{fixture.code} · side {sel.side} · bays {sel.from}–{sel.to} (Shift+click a bay to extend)</div>
      <label className="mt-4 block">
        <div className="label-up mb-1">Category</div>
        <select className="input w-full" value={cat} onChange={e => setCat(e.target.value)}>
          {catOptions.map(c => <option key={c.code} value={c.code}>{c.department} · {c.name}</option>)}
        </select>
      </label>
      {clash && <div className="mt-3 rounded-md bg-amber-tint px-3 py-2 text-[12px] text-amber-ink">Overlaps {clash.code}; the server will refuse it.</div>}
      <button className="btn btn-primary mt-4 w-full justify-center" onClick={async () => {
        const id = crypto.randomUUID()
        if (await run([{ type: 'CreateSection', section_id: id, fixture_id: fixture.id, side: sel.side, bay_from: sel.from, bay_to: sel.to, category_code: cat }])) setSel({ kind: 'section', id })
      }}><Plus size={14} />Create section</button>
    </div>
  )
}

function ShelfPanel({ surface, doc, bays, sections, run }: {
  surface: Surface; doc: LayoutDoc; bays: Bay[]; sections: Section[]; run: (c: Command[]) => Promise<boolean>
}) {
  const bay = doc.bays[surface.bay_id]
  const own = Object.values(doc.surfaces).filter(x => x.bay_id === bay.id && x.kind === 'shelf').sort((a, b) => a.height_from_floor_mm - b.height_from_floor_mm)
  const clears = clearHeights(own.map(x => x.height_from_floor_mm), bay.height_mm)
  const level = own.findIndex(x => x.id === surface.id)
  const [h, setH] = useState(surface.height_from_floor_mm)
  const section = sections.find(s => s.side === bay.side && s.bay_from <= bay.idx && bay.idx <= s.bay_to)
  const sameLevel = (scope: 'section' | 'side') => bays
    .filter(b => b.side === bay.side && (scope === 'side' || (section && section.bay_from <= b.idx && b.idx <= section.bay_to)))
    .map(b => Object.values(doc.surfaces).find(x => x.bay_id === b.id && x.idx === surface.idx))
    .filter((x): x is Surface => !!x && x.height_from_floor_mm !== h)
  const apply = (targets: Surface[]) => run(targets.map(t => ({ type: 'UpdateSurface', surface_id: t.id, height_from_floor_mm: h })))

  return (
    <div className="p-4">
      <div className="text-[14px] font-semibold">Shelf {level + 1} · bay {bay.idx} · side {bay.side}</div>
      <dl className="mt-3 grid grid-cols-2 gap-y-2 text-[12px]">
        <dt className="text-muted">Height from floor</dt><dd className="font-mono">{mm(surface.height_from_floor_mm)}</dd>
        <dt className="text-muted">Clear height above</dt><dd className="font-mono">{level >= 0 ? mm(clears[level]) : '—'}</dd>
        <dt className="text-muted">Band</dt><dd className="capitalize">{eyeBand(surface.height_from_floor_mm)}</dd>
        <dt className="text-muted">Width × depth</dt><dd className="font-mono">{surface.width_mm} × {surface.depth_mm} mm</dd>
        <dt className="text-muted">Max load</dt><dd className="font-mono">{surface.max_load_g ? `${surface.max_load_g / 1000} kg` : '—'}</dd>
        <dt className="text-muted">Notch pitch</dt><dd className="font-mono">{surface.notch_pitch_mm} mm</dd>
      </dl>
      <label className="mt-4 block">
        <div className="label-up mb-1">New height (mm)</div>
        <div className="flex gap-2">
          <input type="number" step={surface.notch_pitch_mm} className="input w-28 font-mono" value={h} onChange={e => setH(Number(e.target.value))} />
          <button className="btn" disabled={h === surface.height_from_floor_mm} onClick={() => run([{ type: 'UpdateSurface', surface_id: surface.id, height_from_floor_mm: h }])}>This bay</button>
        </div>
      </label>
      <div className="mt-2 flex flex-col gap-2">
        {section && <button className="btn justify-center" disabled={!sameLevel('section').length} onClick={() => apply(sameLevel('section'))}>Apply to all bays of {section.code}</button>}
        <button className="btn justify-center" disabled={!sameLevel('side').length} onClick={() => apply(sameLevel('side'))}>Apply to all bays on side {bay.side}</button>
      </div>
      <p className={clsx('mt-3 text-[11px] text-muted')}>Heights snap to the {surface.notch_pitch_mm} mm notch pitch and must keep 50 mm from the shelves above and below.
        Products that no longer fit show up as hard breaks in the shelf planner.</p>
    </div>
  )
}
