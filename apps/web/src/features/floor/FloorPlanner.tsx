import clsx from 'clsx'
import {
  AlertTriangle, AlignHorizontalJustifyStart, AlignHorizontalSpaceAround, AlignVerticalJustifyStart, AlignVerticalSpaceAround,
  ArrowLeft, CheckCircle2, Columns3, DoorOpen, ExternalLink, Layers as LayersIcon, Map as MapIcon, Maximize, Minus,
  MousePointer2, Plus, Redo2, RotateCcw, RotateCw, Ruler, Search, Square, SquareDashed, Trash2, Undo2,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import type { Command, Fixture, LayoutChecks, LayoutDoc, TemplateDef, Zone } from '../../api/types'
import { PageBar } from '../../app/AppShell'
import { ExportMenu } from '../../app/ExportMenu'
import { useStoreCode } from '../../app/currentStore'
import { DEPT_COLOUR, m1, mm, NON_MERCH } from '../../app/theme'
import { toast } from '../../app/toast'
import { useKeys } from '../../canvas/useKeys'
import { checkLayout, flaggedIds, rotatedPose } from '../../geometry/layout'
import { type Box, FloorCanvas, type Layers, type Tool } from './FloorCanvas'
import { nextFixtureCode } from './floorGeometry'
import { useLayout } from './useLayout'

export function FloorPlanner({ fullscreen = false }: { fullscreen?: boolean }) {
  const code = useStoreCode()
  const navigate = useNavigate()
  const { query, doc, history, saving, savedAt, templates, categories } = useLayout(code)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [zoneSel, setZoneSel] = useState<string | null>(null)
  const [drag, setDrag] = useState<{ id: string; x: number; y: number } | null>(null)
  const [layers, setLayers] = useState<Layers>({ zones: true, sections: true, labels: true, grid: true })
  const [snap, setSnap] = useState(50)
  const [tool, setTool] = useState<Tool>('select')
  const [cursor, setCursor] = useState({ x: 0, y: 0 })
  const [zoomPct, setZoomPct] = useState(100)
  const [zoomReq, setZoomReq] = useState<{ factor: number; n: number }>({ factor: 1, n: 0 })
  const [focusReq, setFocusReq] = useState<{ id: string; n: number } | undefined>()
  const [showIssues, setShowIssues] = useState(false)
  const [showRulers, setShowRulers] = useState(true)
  const [showMinimap, setShowMinimap] = useState(true)
  const [search, setSearch] = useState('')

  // live preview while dragging: every selected fixture moves with the one under the mouse
  const liveDoc = useMemo<LayoutDoc | null>(() => {
    if (!doc || !drag) return doc
    const lead = doc.fixtures[drag.id]
    if (!lead) return doc
    const dx = drag.x - lead.x_mm, dy = drag.y - lead.y_mm
    const ids = selected.has(drag.id) ? selected : new Set([drag.id])
    const fixtures = { ...doc.fixtures }
    for (const id of ids) { const f = fixtures[id]; if (f) fixtures[id] = { ...f, x_mm: f.x_mm + dx, y_mm: f.y_mm + dy } }
    return { ...doc, fixtures }
  }, [doc, drag, selected])
  const checks: LayoutChecks | null = useMemo(() => (liveDoc ? checkLayout(liveDoc) : null), [liveDoc])
  const flagged = useMemo(() => (checks ? flaggedIds(checks) : { bad: new Set<string>(), warn: new Set<string>() }), [checks])

  const selList = doc ? [...selected].map(id => doc.fixtures[id]).filter(Boolean) : []
  const sel = selList.length === 1 ? selList[0] : null
  const zone = zoneSel && doc ? doc.zones.find(z => z.id === zoneSel) ?? null : null

  const run = (cmds: Command[]) => (cmds.length ? history.run(cmds) : Promise.resolve(true))
  const moveMany = (fs: Fixture[], dx: number, dy: number) =>
    run(fs.filter(() => dx || dy).map(f => ({ type: 'MoveFixture', fixture_id: f.id, x_mm: Math.round(f.x_mm + dx), y_mm: Math.round(f.y_mm + dy) })))
  const rotate = (f: Fixture, delta: number) => {
    const rot = (((f.rotation_deg + delta) % 360) + 360) % 360
    const pose = rotatedPose(f, rot)
    run([{ type: 'RotateFixture', fixture_id: f.id, rotation_deg: rot, x_mm: pose.x_mm, y_mm: pose.y_mm }])
  }
  const removeMany = (fs: Fixture[]) => run(fs.map(f => ({ type: 'RemoveFixture', fixture_id: f.id }))).then(ok => ok && setSelected(new Set()))
  const place = (templateCode: string, x: number, y: number) => {
    if (!doc || !templates) return
    const [w, d] = templates[templateCode].footprint
    const s = (v: number) => Math.round(v / snap) * snap
    const id = crypto.randomUUID()
    const codeNew = nextFixtureCode(templateCode, Object.values(doc.fixtures))
    run([{ type: 'PlaceFixture', fixture_id: id, template_code: templateCode, code: codeNew, x_mm: s(x - w / 2), y_mm: s(y - d / 2), rotation_deg: 0 }])
      .then(ok => ok && setSelected(new Set([id])))
  }
  const drawn = (t: Tool, b: Box) => {
    const id = crypto.randomUUID()
    if (t === 'zone') {
      run([{ type: 'AddZone', zone: { id, code: `Z-${(doc?.zones.length ?? 0) + 1}`, kind: 'promotion', name: 'New zone', rect: [b.x, b.y, b.w, b.h] } }])
        .then(ok => { if (ok) { setZoneSel(id); setTool('select') } })
    } else {
      run([{ type: 'AddLandmark', landmark: { id, kind: t === 'pillar' ? 'pillar' : 'entrance', name: t === 'pillar' ? 'Pillar' : 'Door', rect: [b.x, b.y, b.w, b.h] } }])
    }
  }
  const align = (how: 'left' | 'top' | 'dist-x' | 'dist-y') => {
    if (selList.length < 2) return
    if (how === 'left') { const x = Math.min(...selList.map(f => f.x_mm)); run(selList.map(f => ({ type: 'MoveFixture', fixture_id: f.id, x_mm: x, y_mm: f.y_mm }))) }
    if (how === 'top') { const y = Math.min(...selList.map(f => f.y_mm)); run(selList.map(f => ({ type: 'MoveFixture', fixture_id: f.id, x_mm: f.x_mm, y_mm: y }))) }
    if (how === 'dist-x' || how === 'dist-y') {
      const ax = how === 'dist-x' ? 'x_mm' : 'y_mm'
      const sorted = [...selList].sort((a, b) => a[ax] - b[ax])
      const first = sorted[0][ax], last = sorted.at(-1)![ax]
      const step = (last - first) / (sorted.length - 1)
      run(sorted.map((f, i) => ({ type: 'MoveFixture', fixture_id: f.id, x_mm: ax === 'x_mm' ? Math.round(first + i * step) : f.x_mm, y_mm: ax === 'y_mm' ? Math.round(first + i * step) : f.y_mm })))
    }
  }
  const find = () => {
    if (!doc || !search.trim()) return
    const q = search.trim().toLowerCase()
    const all = Object.values(doc.fixtures)
    const f = all.find(x => x.code.toLowerCase() === q) ?? all.find(x => x.code.toLowerCase().startsWith(q))
      ?? all.find(x => Object.values(doc.sections).some(s => s.fixture_id === x.id && (categories?.[s.category_code]?.name ?? '').toLowerCase().includes(q)))
    if (!f) { toast.info(`No fixture matches “${search}”`); return }
    setSelected(new Set([f.id]))
    setFocusReq(r => ({ id: f.id, n: (r?.n ?? 0) + 1 }))
  }

  useKeys(e => {
    const mod = e.ctrlKey || e.metaKey
    if (mod && e.key.toLowerCase() === 'z' && !e.shiftKey) { e.preventDefault(); history.undo(); return }
    if (mod && (e.key.toLowerCase() === 'y' || (e.key.toLowerCase() === 'z' && e.shiftKey))) { e.preventDefault(); history.redo(); return }
    if (mod && e.key.toLowerCase() === 'a' && doc) { e.preventDefault(); setSelected(new Set(Object.keys(doc.fixtures))); return }
    if (e.key === 'Escape') { setSelected(new Set()); setZoneSel(null); setTool('select'); return }
    if (e.key === 'v' || e.key === 'V') setTool('select')
    if (e.key === 'z' || e.key === 'Z') setTool('zone')
    if (zone && (e.key === 'Delete' || e.key === 'Backspace')) { run([{ type: 'RemoveZone', id: zone.id }]).then(ok => ok && setZoneSel(null)); return }
    if (!selList.length) return
    const step = e.shiftKey ? 500 : snap
    const nudge: Record<string, [number, number]> = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }
    if (nudge[e.key]) { e.preventDefault(); moveMany(selList, nudge[e.key][0], nudge[e.key][1]); return }
    if ((e.key === 'r' || e.key === 'R') && sel) rotate(sel, e.shiftKey ? -90 : 90)
    if (e.key === 'Delete' || e.key === 'Backspace') removeMany(selList)
  })

  if (query.isError) return <div className="p-6 text-bad">Could not load the layout: {(query.error as Error).message}</div>
  if (!doc || !templates || !categories || !checks) return <div className="p-6 text-muted">Loading floor plan…</div>

  const counts = { overlaps: checks.overlaps.length + checks.out_of_bounds.length, aisles: checks.aisle_warnings.length, doors: checks.blocked_doors.length }
  const areaSqft = Math.round((doc.store.width_mm * doc.store.depth_mm) / 1e6 * 10.764)

  const header = (
    <>
      <CheckChip ok={counts.overlaps === 0} bad label="Overlaps" n={counts.overlaps} onClick={() => setShowIssues(v => !v)} />
      <CheckChip ok={counts.aisles === 0} label="Aisle warnings" n={counts.aisles} onClick={() => setShowIssues(v => !v)} />
      <CheckChip ok={counts.doors === 0} bad label="Blocked doors" n={counts.doors} icon={<DoorOpen size={13} />} onClick={() => setShowIssues(v => !v)} />
      <div className="mx-1 h-6 w-px bg-line" />
      <ExportMenu store={code} />
      {!fullscreen && <button className="btn" onClick={() => window.open(`/design/${code}`, '_blank')}><ExternalLink size={15} />Open in new tab</button>}
    </>
  )

  return (
    <div className={clsx('flex min-h-0 flex-1 flex-col', fullscreen && 'h-full')}>
      {fullscreen ? (
        <header className="flex h-12 shrink-0 items-center gap-3 border-b border-line bg-white px-4">
          <Link to={`/stores/${code}`} className="btn btn-ghost"><ArrowLeft size={15} />App</Link>
          <div className="grid size-7 place-items-center rounded-md bg-primary text-[11px] font-bold text-white">PL</div>
          <div className="text-[14px] font-semibold">Floor designer · {doc.store.code} · {doc.store.name}</div>
          <span className="chip bg-slate-100 font-mono text-ink-2">{doc.store.width_mm / 1000} × {doc.store.depth_mm / 1000} m · {areaSqft.toLocaleString('en-IN')} sq ft</span>
          <span className="text-[12px] text-muted">{saving ? 'Saving…' : savedAt ? `Saved ${savedAt.toLocaleTimeString()}` : 'All changes saved'}</span>
          <div className="ml-auto flex items-center gap-2">{header}</div>
        </header>
      ) : (
        <PageBar crumbs={<><Link to={`/stores/${code}`} className="hover:text-ink">{code}</Link> / </>} title="Floor planner">
          <span className="text-[12px] text-muted">{saving ? 'Saving…' : savedAt ? `Saved ${savedAt.toLocaleTimeString()}` : 'All changes saved'}</span>
          <div className="mx-1 h-6 w-px bg-line" />
          {header}
        </PageBar>
      )}

      {/* toolbar */}
      <div className="flex h-11 shrink-0 items-center gap-1 border-b border-line bg-white px-3">
        <ToolBtn on={tool === 'select'} onClick={() => setTool('select')} title="Select and move (V). Shift+drag on empty floor to box-select."><MousePointer2 size={15} />Select</ToolBtn>
        <ToolBtn on={tool === 'zone'} onClick={() => setTool('zone')} title="Draw a zone (Z): drag a rectangle"><SquareDashed size={15} />Zone</ToolBtn>
        <ToolBtn on={tool === 'pillar'} onClick={() => setTool('pillar')} title="Click to place a pillar"><Square size={15} />Pillar</ToolBtn>
        <ToolBtn on={tool === 'door'} onClick={() => setTool('door')} title="Click to place a door"><DoorOpen size={15} />Door</ToolBtn>
        <div className="mx-1.5 h-6 w-px bg-line" />
        <button className="btn btn-icon btn-ghost" title="Undo (Ctrl+Z)" disabled={!history.canUndo} onClick={history.undo}><Undo2 size={16} /></button>
        <button className="btn btn-icon btn-ghost" title="Redo (Ctrl+Y)" disabled={!history.canRedo} onClick={history.redo}><Redo2 size={16} /></button>
        <button className="btn btn-icon btn-ghost" disabled={!sel} onClick={() => sel && rotate(sel, -90)} title="Rotate left (Shift+R)"><RotateCcw size={15} /></button>
        <button className="btn btn-icon btn-ghost" disabled={!sel} onClick={() => sel && rotate(sel, 90)} title="Rotate right (R)"><RotateCw size={15} /></button>
        <button className="btn btn-icon btn-ghost" disabled={!selList.length} onClick={() => removeMany(selList)} title="Delete (Del)"><Trash2 size={15} /></button>
        <div className="mx-1.5 h-6 w-px bg-line" />
        <button className="btn btn-icon btn-ghost" disabled={selList.length < 2} onClick={() => align('left')} title="Align left edges"><AlignHorizontalJustifyStart size={15} /></button>
        <button className="btn btn-icon btn-ghost" disabled={selList.length < 2} onClick={() => align('top')} title="Align top edges"><AlignVerticalJustifyStart size={15} /></button>
        <button className="btn btn-icon btn-ghost" disabled={selList.length < 3} onClick={() => align('dist-x')} title="Distribute horizontally"><AlignHorizontalSpaceAround size={15} /></button>
        <button className="btn btn-icon btn-ghost" disabled={selList.length < 3} onClick={() => align('dist-y')} title="Distribute vertically"><AlignVerticalSpaceAround size={15} /></button>
        <div className="mx-1.5 h-6 w-px bg-line" />
        <select className="input h-7 py-0 text-[12px]" value={snap} onChange={e => setSnap(Number(e.target.value))} title="Snap">
          {[10, 50, 100, 250, 500, 1000].map(v => <option key={v} value={v}>Snap {v} mm</option>)}
        </select>
        <button className="btn btn-icon btn-ghost" onClick={() => setZoomReq(z => ({ factor: 1 / 1.3, n: z.n + 1 }))}><Minus size={15} /></button>
        <span className="w-12 text-center font-mono text-[12px]">{zoomPct}%</span>
        <button className="btn btn-icon btn-ghost" onClick={() => setZoomReq(z => ({ factor: 1.3, n: z.n + 1 }))}><Plus size={15} /></button>
        <button className="btn btn-icon btn-ghost" title="Fit the whole floor" onClick={() => setZoomReq(z => ({ factor: 0, n: z.n + 1 }))}><Maximize size={15} /></button>
        <form className="ml-2 flex items-center" onSubmit={e => { e.preventDefault(); find() }}>
          <div className="relative">
            <Search size={13} className="absolute left-2 top-2.5 text-muted" />
            <input className="input h-8 w-48 pl-7 text-[12px]" placeholder="Find fixture or category…" value={search} onChange={e => setSearch(e.target.value)} />
          </div>
        </form>
        <div className="ml-auto flex items-center gap-1">
          <LayersIcon size={14} className="text-muted" />
          {(Object.keys(layers) as (keyof Layers)[]).map(k => (
            <button key={k} className={clsx('btn h-7 px-2 text-[12px] capitalize', layers[k] && 'btn-active')} onClick={() => setLayers(l => ({ ...l, [k]: !l[k] }))}>{k}</button>
          ))}
          <button className={clsx('btn h-7 px-2 text-[12px]', showRulers && 'btn-active')} onClick={() => setShowRulers(v => !v)} title="Rulers"><Ruler size={13} /></button>
          <button className={clsx('btn h-7 px-2 text-[12px]', showMinimap && 'btn-active')} onClick={() => setShowMinimap(v => !v)} title="Overview map"><MapIcon size={13} /></button>
        </div>
      </div>

      <div className="flex min-h-0 flex-1">
        <LibraryPanel templates={templates} />
        <div className="relative min-w-0 flex-1">
          <FloorCanvas
            doc={liveDoc ?? doc}
            templates={templates}
            categories={categories}
            selectedIds={selected}
            selectedZone={zoneSel}
            bad={flagged.bad}
            warn={flagged.warn}
            layers={layers}
            editable
            snapMm={snap}
            tool={tool}
            showRulers={showRulers}
            showMinimap={showMinimap}
            onSelect={(id, additive) => {
              setZoneSel(null)
              if (!id) { setSelected(new Set()); return }
              setSelected(s => {
                if (!additive) return new Set([id])
                const n = new Set(s)
                if (n.has(id)) n.delete(id); else n.add(id)
                return n
              })
            }}
            onSelectMany={ids => { setZoneSel(null); setSelected(new Set(ids)) }}
            onSelectZone={id => { setZoneSel(id); if (id) setSelected(new Set()) }}
            onDragMove={(id, x, y) => setDrag({ id, x, y })}
            onDragEnd={(id, x, y) => {
              setDrag(null)
              const lead = doc.fixtures[id]
              if (!lead) return
              const group = selected.has(id) ? selList : [lead]
              moveMany(group, x - lead.x_mm, y - lead.y_mm)
            }}
            onZoneMove={(z, x, y) => run([{ type: 'UpdateZone', id: z.id, rect: [x, y, z.rect[2], z.rect[3]] }])}
            onDrawRect={drawn}
            onDropTemplate={place}
            onCursor={(x, y) => setCursor({ x, y })}
            onZoom={setZoomPct}
            zoomRequest={zoomReq}
            focusRequest={focusReq}
          />
          {showIssues && <IssueList checks={checks} doc={doc} onPick={id => { setSelected(new Set([id])); setFocusReq(r => ({ id, n: (r?.n ?? 0) + 1 })); setShowIssues(false) }} onClose={() => setShowIssues(false)} />}
          <Legend />
        </div>
        <aside className="w-[300px] shrink-0 overflow-y-auto border-l border-line bg-white">
          {zone ? <ZoneInspector key={zone.id + zone.rect.join()} zone={zone} run={run} onClose={() => setZoneSel(null)} />
            : selList.length > 1 ? <MultiInspector list={selList} categories={categories} onRemove={() => removeMany(selList)} align={align} />
              : sel ? <Inspector f={sel} doc={doc} templates={templates} categories={categories} checks={checks}
                  onMove={(f, x, y) => moveMany([f], x - f.x_mm, y - f.y_mm)} onRotate={rotate} onRemove={f => removeMany([f])}
                  onRename={(f, c) => run([{ type: 'RenameFixture', fixture_id: f.id, code: c }])}
                  onOpen={f => navigate(`/stores/${code}/fixtures/${encodeURIComponent(f.code)}`)} />
                : <StorePanel doc={doc} run={run} />}
        </aside>
      </div>

      <footer className="flex h-7 shrink-0 items-center gap-5 bg-ink px-4 font-mono text-[11px] text-slate-300">
        <span>x {mm(Math.max(0, cursor.x))} · y {mm(Math.max(0, cursor.y))}</span>
        <span>Tool {tool}</span>
        <span>{selList.length ? `${selList.length} selected${sel ? ` · ${sel.code}` : ''}` : 'Nothing selected'}</span>
        <span className="ml-auto">{Object.keys(doc.fixtures).length} fixtures · {Object.keys(doc.sections).length} sections · {doc.store.width_mm / 1000} × {doc.store.depth_mm / 1000} m</span>
        <span className={counts.overlaps ? 'text-red-300' : 'text-emerald-300'}>Collisions {counts.overlaps}</span>
      </footer>
    </div>
  )
}

function ToolBtn({ on, onClick, title, children }: { on: boolean; onClick: () => void; title: string; children: React.ReactNode }) {
  return <button className={clsx('btn h-8 px-2.5', on ? 'btn-active' : 'btn-ghost')} onClick={onClick} title={title}>{children}</button>
}

function CheckChip({ ok, label, n, bad, icon, onClick }: { ok: boolean; label: string; n: number; bad?: boolean; icon?: React.ReactNode; onClick: () => void }) {
  return (
    <button onClick={onClick} className={clsx('chip border font-mono',
      ok ? 'border-emerald-200 bg-ok-tint text-ok' : bad ? 'border-red-200 bg-bad-tint text-bad' : 'border-amber-200 bg-amber-tint text-amber-ink')}>
      {ok ? <CheckCircle2 size={13} /> : icon ?? <AlertTriangle size={13} />}{label} {n}
    </button>
  )
}

const LIB_GROUPS: { title: string; codes: string[] }[] = [
  { title: 'Gondolas & wall bays', codes: ['GONDOLA_DS_12', 'END_CAP', 'WALL_BAY'] },
  { title: 'Chillers & freezers', codes: ['MULTIDECK_2500', 'GLASS_DOOR_FREEZER_4', 'ISLAND_FREEZER_2500'] },
  { title: 'Fresh & promotional', codes: ['PRODUCE_BIN', 'PALLET', 'BAKERY_RACK'] },
  { title: 'Front end & checkout', codes: ['CHECKOUT_COUNTER', 'CHECKOUT_RACK', 'SELF_CHECKOUT', 'SERVICE_DESK'] },
]

function LibraryPanel({ templates }: { templates: Record<string, TemplateDef> }) {
  const [filter, setFilter] = useState('')
  return (
    <aside className="flex w-[240px] shrink-0 flex-col border-r border-line bg-white">
      <div className="border-b border-line p-3">
        <div className="mb-2 text-[13px] font-semibold">Fixture library</div>
        <input className="input w-full" placeholder="Filter fixtures…" value={filter} onChange={e => setFilter(e.target.value)} />
      </div>
      <div className="flex-1 overflow-y-auto p-3">
        {LIB_GROUPS.map(g => {
          const items = g.codes.filter(c => templates[c] && templates[c].name.toLowerCase().includes(filter.toLowerCase()))
          if (!items.length) return null
          return (
            <div key={g.title} className="mb-4">
              <div className="label-up mb-2">{g.title}</div>
              {items.map(c => {
                const t = templates[c]
                return (
                  <div key={c} draggable onDragStart={e => { e.dataTransfer.setData('text/x-template', c); e.dataTransfer.effectAllowed = 'copy' }}
                    className="mb-2 flex cursor-grab items-center gap-2.5 rounded-lg border border-line p-2 hover:border-indigo-300 hover:bg-primary-tint active:cursor-grabbing">
                    <TemplateIcon t={t} />
                    <div className="min-w-0">
                      <div className="truncate text-[12.5px] font-medium">{t.name}</div>
                      <div className="font-mono text-[10.5px] text-muted">{t.footprint[0].toLocaleString('en-IN')} × {t.footprint[1].toLocaleString('en-IN')} · {t.temperature}</div>
                    </div>
                  </div>
                )
              })}
            </div>
          )
        })}
      </div>
      <div className="border-t border-line px-3 py-2 text-[11px] text-muted">Drag onto the floor · R rotate · Del delete · arrows nudge · Shift+click multi-select</div>
    </aside>
  )
}

function TemplateIcon({ t }: { t: TemplateDef }) {
  const [w, d] = t.footprint
  const s = 34 / Math.max(w, d)
  const colour = t.temperature === 'frozen' ? '#C7D2FE' : t.temperature === 'chilled' ? '#BFDBFE' : t.surfaces.length ? '#FDE68A' : '#CBD5E1'
  return (
    <svg width={38} height={38} viewBox="0 0 38 38" className="shrink-0 rounded bg-canvas">
      <rect x={19 - (w * s) / 2} y={19 - (d * s) / 2} width={Math.max(3, w * s)} height={Math.max(3, d * s)} fill={colour} stroke="#475569" strokeWidth={1}
        rx={t.kind === 'produce_bin' ? 4 : 0} />
      {t.sides.length === 2 && <line x1={19 - (w * s) / 2} x2={19 + (w * s) / 2} y1={19} y2={19} stroke="#334155" />}
    </svg>
  )
}

function Inspector({ f, doc, templates, categories, checks, onMove, onRotate, onRemove, onRename, onOpen }: {
  f: Fixture; doc: LayoutDoc; templates: Record<string, TemplateDef>; categories: Record<string, { department: string; name: string }>
  checks: LayoutChecks
  onMove: (f: Fixture, x: number, y: number) => void; onRotate: (f: Fixture, d: number) => void
  onRemove: (f: Fixture) => void; onRename: (f: Fixture, code: string) => void; onOpen: (f: Fixture) => void
}) {
  const tpl = templates[f.template_code]
  const sections = Object.values(doc.sections).filter(s => s.fixture_id === f.id).sort((a, b) => a.side.localeCompare(b.side) || a.bay_from - b.bay_from)
  const zone = zoneOf(f, doc)
  const entrance = doc.landmarks.find(l => l.kind === 'entrance')
  const dist = (r: number[] | undefined) => r ? Math.hypot(f.x_mm + f.footprint_w_mm / 2 - (r[0] + r[2] / 2), f.y_mm + f.footprint_d_mm / 2 - (r[1] + r[3] / 2)) : 0
  const checkouts = Object.values(doc.fixtures).filter(x => x.kind === 'checkout')
  const toCheckout = checkouts.length ? Math.min(...checkouts.map(c => dist([c.x_mm, c.y_mm, c.footprint_w_mm, c.footprint_d_mm]))) : 0
  const issues = [...checks.overlaps, ...checks.aisle_warnings, ...checks.blocked_doors, ...checks.out_of_bounds].filter(i => i.fixtures.includes(f.id))
  const linear = tpl ? tpl.bay_width * tpl.bays_per_side * tpl.sides.filter(s => s !== 'TOP').length : 0
  const placed = sections.reduce((a, s) => a + (s.positions ?? 0), 0)

  return (
    <div>
      <div className="border-b border-line p-4">
        <div className="flex items-center gap-2">
          <span className="size-2 rounded-full bg-primary" />
          <TextField value={f.code} onCommit={v => onRename(f, v)} className="w-28 font-mono text-[14px] font-semibold" />
        </div>
        <div className="mt-1 text-[12.5px] text-ink-2">{tpl?.name ?? f.kind}</div>
        <div className="font-mono text-[11px] text-muted">Template {f.template_code} v1{f.note ? ` · ${f.note}` : ''}</div>
      </div>
      <div className="space-y-4 p-4">
        {!NON_MERCH.has(f.kind) && (
          <button className="btn btn-primary w-full justify-center" onClick={() => onOpen(f)}><Columns3 size={15} />Open fixture, sections & products</button>
        )}
        <section>
          <div className="label-up mb-2">Position</div>
          <div className="grid grid-cols-3 gap-2">
            <NumField label="X (mm)" value={f.x_mm} onCommit={v => onMove(f, v, f.y_mm)} />
            <NumField label="Y (mm)" value={f.y_mm} onCommit={v => onMove(f, f.x_mm, v)} />
            <div>
              <div className="mb-1 text-[11px] text-muted">Rotation</div>
              <div className="flex">
                <button className="btn btn-icon h-8 rounded-r-none" onClick={() => onRotate(f, -90)}><RotateCcw size={14} /></button>
                <span className="grid h-8 flex-1 place-items-center border-y border-line font-mono text-[12px]">{f.rotation_deg}°</span>
                <button className="btn btn-icon h-8 rounded-l-none" onClick={() => onRotate(f, 90)}><RotateCw size={14} /></button>
              </div>
            </div>
          </div>
          <dl className="mt-3 grid grid-cols-2 gap-y-2 text-[12px]">
            <dt className="text-muted">Footprint</dt><dd className="font-mono">{f.footprint_w_mm.toLocaleString('en-IN')} × {f.footprint_d_mm.toLocaleString('en-IN')} mm</dd>
            <dt className="text-muted">Faces</dt><dd className="font-mono">{f.faces ?? '—'}</dd>
            <dt className="text-muted">Zone</dt><dd>{zone ?? '—'}</dd>
            <dt className="text-muted">Temperature</dt><dd className="capitalize">{f.temperature}</dd>
            <dt className="text-muted">Linear shelf</dt><dd className="font-mono">{linear ? m1(linear) : '—'}</dd>
            <dt className="text-muted">Products placed</dt><dd className="font-mono">{placed}</dd>
            <dt className="text-muted">To entrance</dt><dd className="font-mono">{m1(dist(entrance?.rect))}</dd>
            <dt className="text-muted">To checkouts</dt><dd className="font-mono">{m1(toCheckout)}</dd>
          </dl>
        </section>
        {issues.length > 0 && (
          <section className="rounded-lg border border-red-200 bg-bad-tint p-3">
            <div className="label-up mb-1 !text-bad">Layout checks</div>
            {issues.map((i, k) => <div key={k} className="text-[12px] text-bad">{i.message}</div>)}
          </section>
        )}
        {!NON_MERCH.has(f.kind) && (
          <section>
            <div className="mb-2 flex items-center justify-between">
              <span className="label-up">Sections</span>
              <span className="tag bg-primary-tint text-primary">{sections.length}</span>
            </div>
            {sections.length === 0 && <div className="text-[12px] text-muted">No sections yet. Open the fixture to assign categories to bays.</div>}
            {sections.map(s => {
              const cat = categories[s.category_code]
              return (
                <div key={s.id} className="mb-1.5 flex items-center gap-2 rounded-md border border-line px-2 py-1.5">
                  <span className="size-2.5 rounded-sm" style={{ background: DEPT_COLOUR[cat?.department ?? ''] ?? '#E2E8F0' }} />
                  <span className="flex-1 truncate text-[12px]">{cat?.name ?? s.category_code} <span className="text-muted">· {s.side} {s.bay_from}–{s.bay_to}</span></span>
                  <span className="font-mono text-[10.5px] text-muted">{s.positions ? `${s.positions} SKU` : ''}</span>
                  {tpl?.surfaces.some(x => x.kind === 'shelf') && (
                    <Link to={`/sections/${s.id}/plan`} title="Open shelf planner" className="text-primary"><ExternalLink size={13} /></Link>
                  )}
                </div>
              )
            })}
          </section>
        )}
        <button className="btn w-full justify-center text-bad" onClick={() => onRemove(f)}><Trash2 size={14} />Delete fixture</button>
      </div>
    </div>
  )
}

function MultiInspector({ list, categories, onRemove, align }: {
  list: Fixture[]; categories: Record<string, { department: string; name: string }>
  onRemove: () => void; align: (how: 'left' | 'top' | 'dist-x' | 'dist-y') => void
}) {
  void categories
  const kinds = list.reduce<Record<string, number>>((a, f) => ({ ...a, [f.kind]: (a[f.kind] ?? 0) + 1 }), {})
  return (
    <div className="space-y-4 p-4">
      <div className="text-[14px] font-semibold">{list.length} fixtures selected</div>
      <div className="flex flex-wrap gap-1">{Object.entries(kinds).map(([k, n]) => <span key={k} className="tag bg-slate-100 text-ink-2">{n} × {k.replace('_', ' ')}</span>)}</div>
      <div className="font-mono text-[11px] text-muted">{list.map(f => f.code).slice(0, 30).join(', ')}{list.length > 30 ? '…' : ''}</div>
      <div className="grid grid-cols-2 gap-2">
        <button className="btn justify-center" onClick={() => align('left')}><AlignHorizontalJustifyStart size={14} />Align left</button>
        <button className="btn justify-center" onClick={() => align('top')}><AlignVerticalJustifyStart size={14} />Align top</button>
        <button className="btn justify-center" disabled={list.length < 3} onClick={() => align('dist-x')}><AlignHorizontalSpaceAround size={14} />Spread across</button>
        <button className="btn justify-center" disabled={list.length < 3} onClick={() => align('dist-y')}><AlignVerticalSpaceAround size={14} />Spread down</button>
      </div>
      <p className="text-[11px] text-muted">Drag any selected fixture to move the group. Arrow keys nudge them all (Shift = 500 mm).</p>
      <button className="btn w-full justify-center text-bad" onClick={onRemove}><Trash2 size={14} />Delete {list.length} fixtures</button>
    </div>
  )
}

const ZONE_KINDS = ['entrance', 'main_aisle', 'checkout', 'chilled', 'frozen', 'centre_store', 'perimeter', 'promotion', 'back_of_house']

function ZoneInspector({ zone, run, onClose }: { zone: Zone; run: (c: Command[]) => Promise<boolean>; onClose: () => void }) {
  const [x, y, w, h] = zone.rect
  const upd = (patch: Record<string, unknown>) => run([{ type: 'UpdateZone', id: zone.id, ...patch }])
  return (
    <div className="space-y-4 p-4">
      <div className="flex items-center justify-between">
        <span className="text-[14px] font-semibold">Zone</span>
        <button className="btn btn-ghost h-7 px-2 text-[12px]" onClick={onClose}>Close</button>
      </div>
      <label className="block"><div className="label-up mb-1">Name</div><TextField value={zone.name} onCommit={v => upd({ name: v })} className="w-full" /></label>
      <label className="block"><div className="label-up mb-1">Kind</div>
        <select className="input w-full" value={zone.kind} onChange={e => upd({ kind: e.target.value })}>
          {ZONE_KINDS.map(k => <option key={k} value={k}>{k.replace('_', ' ')}</option>)}
        </select>
      </label>
      <div className="grid grid-cols-2 gap-2">
        <NumField label="X (mm)" value={x} onCommit={v => upd({ rect: [v, y, w, h] })} />
        <NumField label="Y (mm)" value={y} onCommit={v => upd({ rect: [x, v, w, h] })} />
        <NumField label="Width (mm)" value={w} onCommit={v => upd({ rect: [x, y, v, h] })} />
        <NumField label="Depth (mm)" value={h} onCommit={v => upd({ rect: [x, y, w, v] })} />
      </div>
      <p className="text-[11px] text-muted">Drag the selected zone on the floor to move it. Zones decide which fixtures count as fresh, checkout, chilled and so on.</p>
      <button className="btn w-full justify-center text-bad" onClick={() => run([{ type: 'RemoveZone', id: zone.id }]).then(ok => ok && onClose())}><Trash2 size={14} />Delete zone</button>
    </div>
  )
}

function StorePanel({ doc, run }: { doc: LayoutDoc; run: (c: Command[]) => Promise<boolean> }) {
  const [w, setW] = useState(doc.store.width_mm / 1000)
  const [d, setD] = useState(doc.store.depth_mm / 1000)
  const kinds = Object.values(doc.fixtures).reduce<Record<string, number>>((a, f) => ({ ...a, [f.kind]: (a[f.kind] ?? 0) + 1 }), {})
  return (
    <div className="space-y-4 p-4">
      <div className="text-[14px] font-semibold">Store</div>
      <label className="block"><div className="label-up mb-1">Name</div><TextField value={doc.store.name} onCommit={v => run([{ type: 'RenameStore', name: v }])} className="w-full" /></label>
      <div>
        <div className="label-up mb-1">Floor size (metres)</div>
        <div className="flex items-center gap-2">
          <input type="number" className="input w-20 font-mono" value={w} min={5} max={300} onChange={e => setW(Number(e.target.value))} />
          <span className="text-muted">×</span>
          <input type="number" className="input w-20 font-mono" value={d} min={5} max={300} onChange={e => setD(Number(e.target.value))} />
          <button className="btn" disabled={w * 1000 === doc.store.width_mm && d * 1000 === doc.store.depth_mm}
            onClick={() => run([{ type: 'ResizeFloor', width_mm: Math.round(w * 1000), depth_mm: Math.round(d * 1000) }])}>Apply</button>
        </div>
        <div className="mt-1 text-[11px] text-muted">{Math.round(w * d * 10.764).toLocaleString('en-IN')} sq ft · up to 300 × 300 m</div>
      </div>
      <div>
        <div className="label-up mb-1">Fixtures</div>
        <div className="flex flex-wrap gap-1">{Object.entries(kinds).sort((a, b) => b[1] - a[1]).map(([k, n]) => <span key={k} className="tag bg-slate-100 text-ink-2">{n} {k.replace('_', ' ')}</span>)}</div>
      </div>
      <div className="rounded-lg bg-canvas p-3 text-[12px] text-ink-2">
        <div className="mb-1 font-semibold text-ink">Tips</div>
        Drag fixtures from the library. Click one to edit it; Shift+click or Shift+drag on empty floor to select several.
        Use <b>Zone</b>, <b>Pillar</b> and <b>Door</b> to draw the shell. Hover any fixture to see its sections.
      </div>
    </div>
  )
}

function NumField({ label, value, onCommit }: { label: string; value: number; onCommit: (v: number) => void }) {
  const [text, setText] = useState<string | null>(null)
  return (
    <label>
      <div className="mb-1 text-[11px] text-muted">{label}</div>
      <input className="input w-full font-mono text-[12px]" value={text ?? String(value)}
        onChange={e => setText(e.target.value)}
        onBlur={() => { if (text !== null && Number.isFinite(Number(text)) && Number(text) !== value) onCommit(Math.round(Number(text))); setText(null) }}
        onKeyDown={e => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur(); if (e.key === 'Escape') setText(null) }} />
    </label>
  )
}

function TextField({ value, onCommit, className }: { value: string; onCommit: (v: string) => void; className?: string }) {
  const [text, setText] = useState<string | null>(null)
  return (
    <input className={clsx('input', className)} value={text ?? value} onChange={e => setText(e.target.value)}
      onBlur={() => { if (text !== null && text.trim() && text !== value) onCommit(text.trim()); setText(null) }}
      onKeyDown={e => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur(); if (e.key === 'Escape') setText(null) }} />
  )
}

function zoneOf(f: Fixture, doc: LayoutDoc): string | null {
  let best: { name: string; area: number; aisle: boolean } | null = null
  for (const z of doc.zones) {
    const [x, y, w, h] = z.rect
    const ow = Math.min(f.x_mm + f.footprint_w_mm, x + w) - Math.max(f.x_mm, x)
    const oh = Math.min(f.y_mm + f.footprint_d_mm, y + h) - Math.max(f.y_mm, y)
    if (ow <= 0 || oh <= 0) continue
    const cand = { name: z.name, area: ow * oh, aisle: z.kind === 'main_aisle' }
    if (!best || (best.aisle && !cand.aisle) || (best.aisle === cand.aisle && cand.area > best.area)) best = cand
  }
  return best?.name ?? null
}

function IssueList({ checks, doc, onPick, onClose }: { checks: LayoutChecks; doc: LayoutDoc; onPick: (id: string) => void; onClose: () => void }) {
  const rows = [
    ...checks.overlaps.map(i => ({ ...i, kind: 'Overlap', bad: true })),
    ...checks.out_of_bounds.map(i => ({ ...i, kind: 'Outside floor', bad: true })),
    ...checks.blocked_doors.map(i => ({ ...i, kind: 'Blocked door', bad: true })),
    ...checks.aisle_warnings.map(i => ({ ...i, kind: 'Aisle', bad: false })),
  ]
  return (
    <div className="absolute right-3 top-8 z-20 w-[360px] rounded-xl border border-line bg-white shadow-lg">
      <div className="flex items-center justify-between border-b border-line px-3 py-2">
        <span className="text-[13px] font-semibold">Layout checks</span>
        <button className="btn btn-ghost h-6 px-2 text-[12px]" onClick={onClose}>Close</button>
      </div>
      <div className="max-h-[320px] overflow-y-auto p-2">
        {rows.length === 0 && <div className="p-3 text-[13px] text-ok">No overlaps, narrow aisles or blocked doors.</div>}
        {rows.map((r, k) => (
          <button key={k} className="flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left hover:bg-canvas" onClick={() => onPick(r.fixtures[0])}>
            <span className={clsx('tag mt-0.5', r.bad ? 'bg-bad-tint text-bad' : 'bg-amber-tint text-amber-ink')}>{r.kind}</span>
            <span className="text-[12px]">{r.message}</span>
          </button>
        ))}
        <div className="px-2 pt-1 text-[11px] text-muted">{Object.keys(doc.fixtures).length} fixtures checked</div>
      </div>
    </div>
  )
}

function Legend() {
  return (
    <div className="pointer-events-none absolute bottom-3 left-8 z-10 flex max-w-[60%] flex-wrap gap-x-3 gap-y-1 rounded-lg border border-line bg-white/95 px-3 py-2 shadow">
      {Object.entries(DEPT_COLOUR).map(([d, c]) => (
        <span key={d} className="flex items-center gap-1.5 text-[11px] text-ink-2"><span className="size-2.5 rounded-sm border border-slate-300" style={{ background: c }} />{d}</span>
      ))}
      <span className="flex items-center gap-1.5 text-[11px] text-ink-2"><span className="h-0.5 w-3 bg-blue-400" />chilled front</span>
      <span className="flex items-center gap-1.5 text-[11px] text-ink-2"><span className="size-2.5 rounded-sm border-2 border-indigo-500" />frozen</span>
    </div>
  )
}
