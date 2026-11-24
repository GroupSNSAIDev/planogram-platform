import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Download, ExternalLink, Map as MapIcon, Plus, Trash2, Upload } from 'lucide-react'
import { useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../../api/client'
import { PageBar } from '../../app/AppShell'
import { rememberStore } from '../../app/currentStore'
import { toast } from '../../app/toast'

export function StoresPage() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const q = useQuery({ queryKey: ['stores'], queryFn: api.stores })
  const [form, setForm] = useState({ code: '', name: '', width_m: 90, depth_m: 62, layout: 'generated' })
  const [busy, setBusy] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const [importCode, setImportCode] = useState('')

  const create = async () => {
    setBusy(true)
    try {
      const r = await api.createStore(form)
      toast.ok(`Created ${r.code}: ${r.fixtures} fixtures, ${r.sections} sections`)
      await qc.invalidateQueries({ queryKey: ['stores'] })
      rememberStore(r.code)
      navigate(`/stores/${r.code}/floor`)
    } catch (e) { toast.error((e as Error).message) } finally { setBusy(false) }
  }
  const importDesign = async () => {
    const f = fileRef.current?.files?.[0]
    if (!f) { toast.error('Choose a design file (.planogram.json)'); return }
    setBusy(true)
    try {
      const r = await api.importDesign(f, importCode || null)
      toast.ok(`Imported ${r.code}: ${r.fixtures} fixtures, ${r.sections} sections, ${r.positions} placed products`)
      await qc.invalidateQueries({ queryKey: ['stores'] })
      navigate(`/stores/${r.code}`)
    } catch (e) { toast.error((e as Error).message) } finally { setBusy(false) }
  }
  const remove = async (code: string) => {
    if (!confirm(`Delete store ${code} with all its fixtures and planograms?`)) return
    try { await api.deleteStore(code); toast.ok(`Deleted ${code}`); qc.invalidateQueries({ queryKey: ['stores'] }) } catch (e) { toast.error((e as Error).message) }
  }
  const sqft = (w: number, d: number) => Math.round(w * d * 10.764).toLocaleString('en-IN')

  return (
    <>
      <PageBar title={<>Stores <span className="ml-2 font-normal text-muted">· {q.data?.length ?? 0}</span></>} />
      <div className="flex-1 overflow-y-auto p-5">
        <div className="mb-5 grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-4">
          {(q.data ?? []).map(s => (
            <div key={s.code} className="card p-4">
              <div className="flex items-start justify-between">
                <div>
                  <div className="font-mono text-[15px] font-bold">{s.code}</div>
                  <div className="text-[13px] text-ink-2">{s.name}</div>
                </div>
                <button className="btn btn-icon btn-ghost text-muted" title="Delete store" onClick={() => remove(s.code)}><Trash2 size={15} /></button>
              </div>
              <div className="mt-3 grid grid-cols-3 gap-2 text-center">
                <Stat label="Floor" value={`${s.width_mm / 1000}×${s.depth_mm / 1000} m`} />
                <Stat label="Fixtures" value={String(s.fixtures)} />
                <Stat label="Sections" value={String(s.sections)} />
              </div>
              <div className="mt-1 text-center text-[11px] text-muted">{sqft(s.width_mm / 1000, s.depth_mm / 1000)} sq ft</div>
              <div className="mt-3 flex flex-wrap gap-2">
                <Link className="btn btn-primary" to={`/stores/${s.code}`} onClick={() => rememberStore(s.code)}>Open</Link>
                <Link className="btn" to={`/stores/${s.code}/floor`} onClick={() => rememberStore(s.code)}><MapIcon size={14} />Floor</Link>
                <button className="btn" onClick={() => window.open(`/design/${s.code}`, '_blank')}><ExternalLink size={14} />Designer</button>
                <a className="btn" href={`/api/stores/${s.code}/layout/export`}><Download size={14} />Design file</a>
              </div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-5">
          <div className="card p-4">
            <div className="text-[14px] font-semibold">Create a store</div>
            <p className="mt-1 text-[12px] text-ink-2">Any size up to 300 × 300 m. <b>Generated</b> lays out a complete hypermarket for that floor:
              a racetrack main aisle around gondola blocks, dairy and frozen on the back wall, staples and home care on the side walls,
              fresh and promotions at the entrance, and a checkout bank with impulse racks. <b>Empty</b> gives you a blank floor to draw.</p>
            <div className="mt-3 grid grid-cols-2 gap-3">
              <label><div className="label-up mb-1">Code</div><input className="input w-full font-mono" value={form.code} placeholder="SMS-003" onChange={e => setForm({ ...form, code: e.target.value.toUpperCase() })} /></label>
              <label><div className="label-up mb-1">Name</div><input className="input w-full" value={form.name} placeholder="Mega Mart Whitefield" onChange={e => setForm({ ...form, name: e.target.value })} /></label>
              <label><div className="label-up mb-1">Width (m)</div><input type="number" className="input w-full font-mono" value={form.width_m} min={5} max={300} onChange={e => setForm({ ...form, width_m: Number(e.target.value) })} /></label>
              <label><div className="label-up mb-1">Depth (m)</div><input type="number" className="input w-full font-mono" value={form.depth_m} min={5} max={300} onChange={e => setForm({ ...form, depth_m: Number(e.target.value) })} /></label>
            </div>
            <div className="mt-3 flex items-center gap-4 text-[12.5px]">
              <label className="flex items-center gap-1.5"><input type="radio" checked={form.layout === 'generated'} onChange={() => setForm({ ...form, layout: 'generated' })} />Generated hypermarket layout</label>
              <label className="flex items-center gap-1.5"><input type="radio" checked={form.layout === 'empty'} onChange={() => setForm({ ...form, layout: 'empty' })} />Empty floor</label>
            </div>
            <div className="mt-2 text-[12px] text-muted">{sqft(form.width_m, form.depth_m)} sq ft{form.layout === 'generated' && (form.width_m < 30 || form.depth_m < 25) ? ' · generated layouts need at least 30 × 25 m' : ''}</div>
            <button className="btn btn-primary mt-3" disabled={busy || !form.code || !form.name} onClick={create}><Plus size={15} />Create store</button>
          </div>
          <div className="card p-4">
            <div className="text-[14px] font-semibold">Import a design file</div>
            <p className="mt-1 text-[12px] text-ink-2">A design file (<span className="font-mono">.planogram.json</span>) holds a whole store: floor, zones, fixtures,
              shelf heights, sections and every placed product. Export one from any store, keep it, and import it later as a new store.</p>
            <div className="mt-3 flex flex-wrap items-end gap-3">
              <label className="text-[12px]"><div className="label-up mb-1">Design file</div><input ref={fileRef} type="file" accept=".json" className="text-[12px]" /></label>
              <label><div className="label-up mb-1">New store code (optional)</div><input className="input w-40 font-mono" value={importCode} placeholder="from file" onChange={e => setImportCode(e.target.value.toUpperCase())} /></label>
              <button className="btn btn-primary" disabled={busy} onClick={importDesign}><Upload size={15} />Import</button>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return <div className="rounded-md bg-canvas px-2 py-1.5"><div className="text-[10px] uppercase tracking-wider text-muted">{label}</div><div className="font-mono text-[13px] font-semibold">{value}</div></div>
}
