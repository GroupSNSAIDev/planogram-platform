import { useQuery } from '@tanstack/react-query'
import { ExternalLink, Map as MapIcon } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useStoreCode } from '../../app/currentStore'
import { api } from '../../api/client'
import { PageBar } from '../../app/AppShell'
import { ExportMenu } from '../../app/ExportMenu'
import { DEPT_COLOUR, NON_MERCH } from '../../app/theme'
import { FloorCanvas } from '../floor/FloorCanvas'

export function StoreOverview() {
  const code = useStoreCode()
  const navigate = useNavigate()
  const q = useQuery({ queryKey: ['layout', code], queryFn: () => api.layout(code) })
  const [hover, setHover] = useState<string | null>(null)

  const stats = useMemo(() => {
    if (!q.data) return null
    const { layout, templates, categories } = q.data
    const fixtures = Object.values(layout.fixtures)
    const sections = Object.values(layout.sections)
    const shelfBays = Object.values(layout.bays).filter(b => b.side !== 'TOP')
    const linear = shelfBays.reduce((a, b) => a + b.width_mm, 0)
    const byDept = new Map<string, number>()
    for (const s of sections) {
      const f = layout.fixtures[s.fixture_id]
      const t = templates[f.template_code]
      if (!t || t.sides[0] === 'TOP') continue
      const dept = categories[s.category_code]?.department ?? 'Other'
      byDept.set(dept, (byDept.get(dept) ?? 0) + (s.bay_to - s.bay_from + 1) * t.bay_width)
    }
    const planned = sections.filter(s => (s.positions ?? 0) > 0)
    return {
      fixtures: fixtures.length, gondolas: fixtures.filter(f => f.kind === 'gondola').length,
      merch: fixtures.filter(f => !NON_MERCH.has(f.kind)).length,
      sections: sections.length, locked: sections.filter(s => s.assignment_locked).length,
      linear, shelfBays: shelfBays.length, planned,
      byDept: [...byDept.entries()].sort((a, b) => b[1] - a[1]),
    }
  }, [q.data])

  if (q.isError) return <div className="p-6 text-bad">{(q.error as Error).message}</div>
  if (!q.data || !stats) return <div className="p-6 text-muted">Loading store…</div>
  const { layout, templates, categories, checks } = q.data
  const issues = checks.overlaps.length + checks.blocked_doors.length + checks.out_of_bounds.length
  const deptTotal = stats.byDept.reduce((a, [, v]) => a + v, 0)
  const sections = Object.values(layout.sections)
    .filter(s => templates[layout.fixtures[s.fixture_id].template_code]?.surfaces.some(x => x.kind === 'shelf'))
    .sort((a, b) => (b.positions ?? 0) - (a.positions ?? 0) || a.code.localeCompare(b.code, undefined, { numeric: true }))

  return (
    <>
      <PageBar crumbs="Stores /" title={`${layout.store.code} · ${layout.store.name}`}>
        <span className="chip bg-amber-tint text-amber-ink">Layout · draft</span>
        <span className="chip bg-slate-100 text-ink-2">{layout.store.timezone}</span>
        <span className="chip bg-teal-tint text-teal">{((layout.store.width_mm * layout.store.depth_mm) / 1e6).toLocaleString('en-IN')} m² · hypermarket</span>
        <ExportMenu store={code} label="Store pack" />
        <Link to={`/stores/${code}/plan`} className="btn">Plan sections</Link>
        <Link to={`/stores/${code}/floor`} className="btn btn-primary"><MapIcon size={15} />Open floor planner</Link>
      </PageBar>
      <div className="flex-1 overflow-y-auto p-5">
        <div className="grid grid-cols-[1fr_340px] gap-5">
          <div className="card flex flex-col p-4">
            <div className="mb-2 flex items-center gap-2">
              <span className="size-2 rounded-full bg-primary" />
              <span className="text-[14px] font-semibold">Floor plan</span>
              <span className="font-mono text-[12px] text-muted">48 × 32 m</span>
              <span className="ml-auto text-[12px] text-muted">{hover ? `Click to open ${layout.fixtures[hover]?.code}` : 'Click a fixture to open its sections'}</span>
            </div>
            <div className="h-[460px] overflow-hidden rounded-lg border border-line">
              <FloorCanvas doc={layout} templates={templates} categories={categories} layers={{ zones: true, sections: true, labels: true, grid: false }}
                highlight={hover}
                onSelect={id => { if (id) { const f = layout.fixtures[id]; if (!NON_MERCH.has(f.kind)) navigate(`/stores/${code}/fixtures/${f.code}`) } }}
                onCursor={() => setHover(null)} />
            </div>
            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1">
              {Object.entries(DEPT_COLOUR).map(([d, c]) => (
                <span key={d} className="flex items-center gap-1.5 text-[11px] text-ink-2"><span className="size-2.5 rounded-sm border border-slate-300" style={{ background: c }} />{d}</span>
              ))}
            </div>
          </div>
          <div className="flex flex-col gap-4">
            <div className="grid grid-cols-2 gap-3">
              <Kpi label="Fixtures" value={stats.fixtures} sub={`${stats.gondolas} gondola runs`} />
              <Kpi label="Sections" value={stats.sections} sub={`${stats.locked} assignment-locked`} />
              <Kpi label="Linear metres" value={Math.round(stats.linear / 1000)} sub={`${stats.shelfBays} shelf bays`} />
              <Kpi label="Planned sections" value={stats.planned.length} sub={issues ? `${issues} layout issues` : 'layout checks clean'} tone={issues ? 'bad' : 'ok'} />
            </div>
            <div className="card p-4">
              <div className="mb-3 text-[14px] font-semibold">Space by department</div>
              <div className="mb-3 flex h-2.5 overflow-hidden rounded-full">
                {stats.byDept.map(([d, v]) => <div key={d} style={{ width: `${(v / deptTotal) * 100}%`, background: DEPT_COLOUR[d] ?? '#CBD5E1' }} />)}
              </div>
              {stats.byDept.map(([d, v]) => (
                <div key={d} className="flex items-center gap-2 py-0.5 text-[12px]">
                  <span className="size-2.5 rounded-sm" style={{ background: DEPT_COLOUR[d] ?? '#CBD5E1' }} />
                  <span className="flex-1">{d}</span>
                  <span className="font-mono">{Math.round(v / 1000)} m</span>
                  <span className="w-10 text-right font-mono text-muted">{Math.round((v / deptTotal) * 100)}%</span>
                </div>
              ))}
            </div>
          </div>
        </div>
        <div className="card mt-5">
          <div className="flex items-center border-b border-line px-4 py-3">
            <span className="text-[14px] font-semibold">Sections</span>
            <span className="ml-2 text-[12px] text-muted">{sections.length} with shelves · open one to plan it</span>
          </div>
          <table className="w-full text-[12.5px]">
            <thead className="bg-canvas text-left text-[11px] uppercase tracking-wider text-muted">
              <tr><th className="px-4 py-2">Section</th><th>Category</th><th>Department</th><th>Fixture · side · bays</th><th>Products placed</th><th>Lock</th><th /></tr>
            </thead>
            <tbody>
              {sections.slice(0, 40).map(s => {
                const cat = categories[s.category_code]
                const f = layout.fixtures[s.fixture_id]
                return (
                  <tr key={s.id} className="border-t border-line hover:bg-canvas" onMouseEnter={() => setHover(f.id)}>
                    <td className="px-4 py-2 font-mono">{s.code}</td>
                    <td>{cat?.name}</td>
                    <td><span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-sm" style={{ background: DEPT_COLOUR[cat?.department ?? ''] }} />{cat?.department}</span></td>
                    <td className="font-mono">{f.code} · {s.side} · {s.bay_from}–{s.bay_to}</td>
                    <td className="font-mono">{s.positions ? <span className="text-ok">{s.positions}</span> : <span className="text-muted">—</span>}</td>
                    <td>{s.assignment_locked ? <span className="tag bg-slate-100 text-slate-700">Locked</span> : ''}</td>
                    <td className="pr-4 text-right"><Link className="inline-flex items-center gap-1 text-primary" to={`/sections/${s.id}/plan`}>Plan <ExternalLink size={12} /></Link></td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          {sections.length > 40 && <div className="border-t border-line px-4 py-2 text-[12px] text-muted">Showing 40 of {sections.length}. Open the floor planner to reach every fixture.</div>}
        </div>
      </div>
    </>
  )
}

function Kpi({ label, value, sub, tone }: { label: string; value: number; sub: string; tone?: 'ok' | 'bad' }) {
  return (
    <div className="card p-3">
      <div className="label-up">{label}</div>
      <div className="mt-1 text-[22px] font-semibold tabular">{value.toLocaleString('en-IN')}</div>
      <div className={tone === 'bad' ? 'text-[12px] text-bad' : tone === 'ok' ? 'text-[12px] text-ok' : 'text-[12px] text-muted'}>{sub}</div>
    </div>
  )
}
