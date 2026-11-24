import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { Snowflake, Sun, Thermometer } from 'lucide-react'
import { useState } from 'react'
import { api } from '../../api/client'
import type { TemplateDef } from '../../api/types'
import { PageBar } from '../../app/AppShell'

const GROUPS: Record<string, string[]> = {
  'Gondolas & wall': ['gondola', 'end_cap', 'wall_bay'],
  'Refrigeration & frozen': ['multideck', 'door_freezer', 'chest_freezer'],
  'Fresh & specialty': ['produce_bin', 'pallet', 'bakery_rack'],
  'Front end & checkout': ['checkout', 'checkout_rack', 'self_checkout', 'service_desk'],
}

export function FixtureLibrary() {
  const q = useQuery({ queryKey: ['templates'], queryFn: api.templates })
  const [group, setGroup] = useState<string | null>(null)
  const [filter, setFilter] = useState('')
  const items = (q.data ?? []).filter(t =>
    (!group || GROUPS[group].includes(t.kind)) && t.name.toLowerCase().includes(filter.toLowerCase()))

  return (
    <>
      <PageBar title={<>Fixture library <span className="ml-2 font-normal text-muted">· {q.data?.length ?? 0} templates</span></>}>
        <button className="btn" disabled title="Template editor is planned for phase P4">+ New template</button>
      </PageBar>
      <div className="flex-1 overflow-y-auto p-5">
        <p className="mb-4 max-w-3xl text-[13px] text-ink-2">
          Standard fixtures with true sizes, shelf positions and behaviour. Every fixture on a floor is placed from one of these
          templates, and its bays and shelves are generated from it (spec section 8).
        </p>
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <input className="input w-64" placeholder="Filter templates…" value={filter} onChange={e => setFilter(e.target.value)} />
          <button className={clsx('btn h-8', !group && 'btn-active')} onClick={() => setGroup(null)}>All ({q.data?.length ?? 0})</button>
          {Object.keys(GROUPS).map(g => (
            <button key={g} className={clsx('btn h-8', group === g && 'btn-active')} onClick={() => setGroup(g)}>
              {g} ({(q.data ?? []).filter(t => GROUPS[g].includes(t.kind)).length})
            </button>
          ))}
        </div>
        <div className="grid grid-cols-[repeat(auto-fill,minmax(250px,1fr))] gap-4">
          {items.map(t => <TemplateCard key={t.code} code={t.code} t={t.defaults} usedBy={t.used_by} />)}
        </div>
      </div>
    </>
  )
}

function TemplateCard({ code, t, usedBy }: { code: string; t: TemplateDef; usedBy: number }) {
  const temp = t.temperature
  const shelves = t.surfaces.filter(s => s.kind === 'shelf').length
  const kinds = [...new Set(t.surfaces.map(s => s.kind))].join(', ') || 'none (landmark)'
  return (
    <div className="card flex flex-col overflow-hidden">
      <div className="flex items-start justify-between gap-2 p-3">
        <div>
          <div className="text-[14px] font-semibold">{t.name}</div>
          <div className="font-mono text-[11px] text-muted">{code} · v1</div>
        </div>
        <span className={clsx('chip', temp === 'frozen' ? 'bg-primary-tint text-primary' : temp === 'chilled' ? 'bg-teal-tint text-teal' : 'bg-slate-100 text-ink-2')}>
          {temp === 'frozen' ? <Snowflake size={12} /> : temp === 'chilled' ? <Thermometer size={12} /> : <Sun size={12} />}{temp}
        </span>
      </div>
      <div className="mx-3 rounded-md bg-primary-tint/60 p-2">
        <div className="mb-1 text-[10px] uppercase tracking-wider text-muted">Elevation · front view</div>
        <MiniElevation t={t} />
      </div>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1.5 p-3 text-[12px]">
        <dt className="text-muted">Footprint</dt><dd className="font-mono">{t.footprint[0].toLocaleString('en-IN')} × {t.footprint[1].toLocaleString('en-IN')}</dd>
        <dt className="text-muted">Height</dt><dd className="font-mono">{t.height.toLocaleString('en-IN')} mm</dd>
        <dt className="text-muted">Bays</dt><dd className="font-mono">{t.bays_per_side} × {t.bay_width.toLocaleString('en-IN')} mm{t.sides.length === 2 ? ' · 2 sides' : ''}</dd>
        <dt className="text-muted">Surfaces</dt><dd>{shelves ? `${shelves} shelves` : kinds}</dd>
        {t.notch_pitch ? <><dt className="text-muted">Notch pitch</dt><dd className="font-mono">{t.notch_pitch} mm</dd></> : null}
        {t.max_load_g_per_shelf ? <><dt className="text-muted">Shelf load</dt><dd className="font-mono">{t.max_load_g_per_shelf / 1000} kg</dd></> : null}
      </dl>
      <div className="mt-auto flex items-center justify-between border-t border-line px-3 py-2 text-[12px]">
        <span className="flex items-center gap-1.5 text-ink-2"><span className={clsx('size-2 rounded-full', usedBy ? 'bg-ok' : 'bg-slate-300')} />Used by {usedBy} fixture{usedBy === 1 ? '' : 's'}</span>
      </div>
    </div>
  )
}

/** Simple front elevation drawn from the template: bays and shelf heights to scale. */
function MiniElevation({ t }: { t: TemplateDef }) {
  const bays = Math.max(1, Math.min(t.bays_per_side, 6))
  const W = t.bay_width * bays
  const H = Math.max(t.height, 400)
  const vw = 220, vh = 90
  const s = Math.min(vw / W, vh / H)
  const ox = (vw - W * s) / 2, oy = vh - H * s
  const shelves = t.surfaces.filter(x => x.kind === 'shelf' || x.kind === 'peg')
  return (
    <svg viewBox={`0 0 ${vw} ${vh + 4}`} className="h-[94px] w-full">
      <rect x={ox} y={oy} width={W * s} height={H * s} fill="#fff" stroke="#334155" strokeWidth={1} />
      {Array.from({ length: bays - 1 }, (_, i) => (
        <line key={i} x1={ox + t.bay_width * (i + 1) * s} x2={ox + t.bay_width * (i + 1) * s} y1={oy} y2={vh} stroke="#94A3B8" strokeWidth={0.8} />
      ))}
      {shelves.map((x, i) => (
        <line key={i} x1={ox + 1} x2={ox + W * s - 1} y1={vh - x.h * s} y2={vh - x.h * s}
          stroke={x.kind === 'peg' ? '#6366F1' : '#334155'} strokeWidth={x.kind === 'peg' ? 1 : 1.6} strokeDasharray={x.kind === 'peg' ? '2 2' : undefined} />
      ))}
      {t.surfaces.some(x => x.kind === 'chest') && <rect x={ox + 4} y={oy + 6} width={W * s - 8} height={H * s - 10} fill="#C7D2FE" opacity={0.6} />}
      {t.surfaces.some(x => x.kind === 'bin') && <polygon points={`${ox},${oy + 8} ${ox + W * s},${oy + 8} ${ox + W * s - 8},${vh} ${ox + 8},${vh}`} fill="#BBF7D0" opacity={0.7} />}
      {t.surfaces.some(x => x.kind === 'stack') && Array.from({ length: 5 }, (_, i) => (
        <rect key={i} x={ox + 6} y={vh - 14 - i * (H * s - 16) / 5} width={W * s - 12} height={(H * s - 20) / 5 - 2} fill="#FDE68A" stroke="#D97706" strokeWidth={0.5} />
      ))}
      {t.doors && Array.from({ length: bays }, (_, i) => (
        <rect key={i} x={ox + t.bay_width * i * s + 2} y={oy + 2} width={t.bay_width * s - 4} height={H * s - 4} fill="#BFDBFE" opacity={0.35} stroke="#3B82F6" strokeWidth={0.6} />
      ))}
      {t.bays_per_side > bays && <text x={vw - 4} y={10} textAnchor="end" fontSize={9} fill="#64748B">+{t.bays_per_side - bays} bays</text>}
    </svg>
  )
}
