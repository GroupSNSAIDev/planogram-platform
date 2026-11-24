import { useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { CheckCircle2, LayoutGrid, Lock, Sparkles } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type SectionRow } from '../../api/client'
import { PageBar } from '../../app/AppShell'
import { ExportMenu } from '../../app/ExportMenu'
import { useStoreCode } from '../../app/currentStore'
import { DEPT_COLOUR } from '../../app/theme'
import { toast } from '../../app/toast'

export function SectionPicker() {
  const code = useStoreCode()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['sections', code], queryFn: () => api.storeSections(code) })
  const [filter, setFilter] = useState('')
  const [only, setOnly] = useState<'all' | 'empty' | 'planned'>('all')
  const [busy, setBusy] = useState(false)
  const rows = (q.data ?? []).filter(s =>
    `${s.code} ${s.fixture_code} ${s.category_name} ${s.department}`.toLowerCase().includes(filter.toLowerCase())
    && (only === 'all' || (only === 'empty' ? !s.positions : s.positions > 0)))
  const byDept = useMemo(() => {
    const m = new Map<string, SectionRow[]>()
    for (const s of rows) m.set(s.department ?? 'Other', [...(m.get(s.department ?? 'Other') ?? []), s])
    return [...m.entries()]
  }, [rows])
  const planned = (q.data ?? []).filter(s => s.positions > 0).length

  const fillAll = async (onlyEmpty: boolean) => {
    if (!onlyEmpty && !confirm('Re-run auto-fill on every section? Placement-locked products stay; everything else is replaced.')) return
    setBusy(true)
    try {
      const r = await api.autofillStore(code, null, onlyEmpty)
      toast.ok(`Auto-filled ${r.sections_filled} sections with ${r.positions.toLocaleString('en-IN')} placements${r.sections_skipped ? ` (${r.sections_skipped} already planned, kept)` : ''}`)
      await qc.invalidateQueries()
    } catch (e) { toast.error((e as Error).message) } finally { setBusy(false) }
  }

  return (
    <>
      <PageBar crumbs={<><Link to={`/stores/${code}`} className="hover:text-ink">{code}</Link> / </>}
        title={<>Shelf planner · sections <span className="ml-2 font-normal text-muted">{planned} of {q.data?.length ?? 0} planned</span></>}>
        <ExportMenu store={code} label="Store pack" />
        <button className="btn" disabled={busy} onClick={() => fillAll(false)}><Sparkles size={15} />Re-fill all</button>
        <button className="btn btn-primary" disabled={busy} onClick={() => fillAll(true)}><Sparkles size={15} />{busy ? 'Filling…' : 'Auto-fill empty sections'}</button>
      </PageBar>
      <div className="flex-1 overflow-y-auto p-5">
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <input className="input w-80" placeholder="Find a section, fixture or category…" value={filter} onChange={e => setFilter(e.target.value)} />
          {(['all', 'empty', 'planned'] as const).map(o => (
            <button key={o} className={clsx('btn h-8 capitalize', only === o && 'btn-active')} onClick={() => setOnly(o)}>{o}</button>
          ))}
          <div className="ml-auto h-2 w-64 overflow-hidden rounded-full bg-slate-200">
            <div className="h-2 bg-ok" style={{ width: `${q.data?.length ? (planned / q.data.length) * 100 : 0}%` }} />
          </div>
        </div>
        {byDept.map(([dept, list]) => (
          <div key={dept} className="mb-5">
            <div className="mb-2 flex items-center gap-2 text-[13px] font-semibold">
              <span className="size-3 rounded-sm" style={{ background: DEPT_COLOUR[dept] ?? '#E2E8F0' }} />{dept}
              <span className="font-normal text-muted">· {list.length} sections</span>
            </div>
            <div className="grid grid-cols-[repeat(auto-fill,minmax(230px,1fr))] gap-2.5">
              {list.map(s => (
                <Link key={s.id} to={`/sections/${s.id}/plan`}
                  className="card flex flex-col gap-1 p-3 hover:border-indigo-300 hover:bg-primary-tint/40">
                  <div className="flex items-center gap-2">
                    <LayoutGrid size={14} className="text-muted" />
                    <span className="font-mono text-[12.5px] font-semibold">{s.code}</span>
                    {s.assignment_locked && <Lock size={12} className="text-slate-500" />}
                    {s.positions > 0
                      ? <span className="ml-auto flex items-center gap-1 text-[11px] text-ok"><CheckCircle2 size={12} />{s.positions}</span>
                      : <span className="ml-auto text-[11px] text-muted">empty</span>}
                  </div>
                  <div className="truncate text-[12.5px]">{s.category_name}</div>
                  <div className="flex justify-between font-mono text-[10.5px] text-muted">
                    <span>{s.fixture_code} · side {s.side} · {s.bays} bay{s.bays > 1 ? 's' : ''}</span>
                    {s.score != null && s.positions > 0 && <span className={s.hard_breaks ? 'text-bad' : ''}>score {s.score.toFixed(0)}{s.hard_breaks ? ` · ${s.hard_breaks} hard` : ''}</span>}
                  </div>
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>
    </>
  )
}
