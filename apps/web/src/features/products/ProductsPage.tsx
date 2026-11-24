import { useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { AlertTriangle, CheckCircle2, Download, FileSpreadsheet, ImageOff, Upload, X } from 'lucide-react'
import { useMemo, useRef, useState } from 'react'
import { api, mediaUrl, type ImportReport } from '../../api/client'
import { PageBar } from '../../app/AppShell'
import { DEPT_COLOUR } from '../../app/theme'
import { toast } from '../../app/toast'

export function ProductsPage() {
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['products'], queryFn: api.products })
  const [filter, setFilter] = useState('')
  const [dept, setDept] = useState<string | null>(null)
  const [report, setReport] = useState<ImportReport | null>(null)
  const [uploading, setUploading] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const zipRef = useRef<HTMLInputElement>(null)

  const products = q.data ?? []
  const depts = useMemo(() => [...new Set(products.map(p => p.department ?? ''))].sort(), [products])
  const list = products.filter(p => (!dept || p.department === dept)
    && `${p.name} ${p.brand} ${p.gtin} ${p.sku} ${p.category_name}`.toLowerCase().includes(filter.toLowerCase()))
  const withImages = products.filter(p => p.has_image).length

  const upload = async () => {
    const f = fileRef.current?.files?.[0]
    if (!f) { toast.error('Choose the product workbook (.xlsx) first'); return }
    setUploading(true)
    try {
      setReport(await api.uploadImport(f, zipRef.current?.files?.[0] ?? null))
    } catch (e) {
      toast.error((e as Error).message)
    } finally {
      setUploading(false)
    }
  }
  const publish = async () => {
    if (!report) return
    try {
      const c = await api.publishImport(report.id)
      toast.ok(`Published ${c.published} products`)
      setReport(null)
      if (fileRef.current) fileRef.current.value = ''
      await qc.invalidateQueries()
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  return (
    <>
      <PageBar title={<>Products & imports <span className="ml-2 font-normal text-muted">· {products.length} products · {withImages} with pictures</span></>}>
        <a className="btn" href="/api/catalog/template.xlsx"><FileSpreadsheet size={15} />Blank template</a>
        <a className="btn" href="/api/catalog/export.xlsx"><Download size={15} />Download catalogue (.xlsx)</a>
      </PageBar>
      <div className="flex-1 overflow-y-auto p-5">
        {/* import */}
        <div className="card mb-5 p-4">
          <div className="flex flex-wrap items-end gap-4">
            <div className="min-w-[280px] flex-1">
              <div className="text-[14px] font-semibold">Import products from a workbook</div>
              <p className="mt-1 text-[12px] text-ink-2">
                Stores and suppliers fill in the template: one row per product with sizes, safety flags and a front picture
                (inserted over the Image cell, as files in a ZIP, or as web addresses). Upload it here, check the report, then publish.
                Rows with errors are not imported; re-importing only changes what changed.
              </p>
            </div>
            <label className="text-[12px]"><div className="label-up mb-1">Workbook (.xlsx)</div>
              <input ref={fileRef} type="file" accept=".xlsx,.xlsm" className="text-[12px]" /></label>
            <label className="text-[12px]"><div className="label-up mb-1">Pictures ZIP (optional)</div>
              <input ref={zipRef} type="file" accept=".zip" className="text-[12px]" /></label>
            <button className="btn btn-primary" disabled={uploading} onClick={upload}><Upload size={15} />{uploading ? 'Checking…' : 'Upload and check'}</button>
          </div>
          {report && <ImportReportView report={report} onPublish={publish} onClose={() => setReport(null)} />}
        </div>

        {/* library */}
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <input className="input w-72" placeholder="Search name, brand, GTIN, SKU…" value={filter} onChange={e => setFilter(e.target.value)} />
          <button className={clsx('btn h-8', !dept && 'btn-active')} onClick={() => setDept(null)}>All</button>
          {depts.map(d => (
            <button key={d} className={clsx('btn h-8', dept === d && 'btn-active')} onClick={() => setDept(d)}>
              <span className="size-2.5 rounded-sm" style={{ background: DEPT_COLOUR[d] ?? '#E2E8F0' }} />{d}
            </button>
          ))}
        </div>
        <div className="grid grid-cols-[repeat(auto-fill,minmax(190px,1fr))] gap-3">
          {list.map(p => (
            <div key={p.id} className="card overflow-hidden">
              <div className="grid h-40 place-items-center bg-white p-2">
                {p.image ? <img src={mediaUrl(p.image)} alt={p.name} loading="lazy" className="max-h-36 max-w-full object-contain" />
                  : <div className="grid h-32 w-24 place-items-center rounded border border-dashed border-slate-300 text-slate-400"><ImageOff size={18} /></div>}
              </div>
              <div className="border-t border-line p-2.5">
                <div className="line-clamp-2 text-[12.5px] font-medium leading-snug">{p.name}</div>
                <div className="mt-0.5 text-[11px] text-muted">{p.brand} · {p.pack_size ?? ''}</div>
                <div className="mt-1 font-mono text-[10.5px] text-muted">{p.width_mm}×{p.height_mm}×{p.depth_mm} mm · {p.gtin}</div>
                <div className="mt-1.5 flex flex-wrap gap-1">
                  <span className="tag" style={{ background: DEPT_COLOUR[p.department ?? ''] ?? '#F1F5F9' }}>{p.category_name}</span>
                  {p.eligibility.status === 'blocked' && <span className="tag bg-bad-tint text-bad">Blocked</span>}
                  {p.eligibility.status === 'estimated' && <span className="tag bg-amber-tint text-amber-ink">Size estimated</span>}
                </div>
              </div>
            </div>
          ))}
        </div>
        <p className="mt-6 text-[11px] text-muted">
          Demo catalogue: product data and pictures from Open Food Facts (ODbL / CC BY-SA), used for the demo tenant only.
          Pack sizes are estimated from the declared quantity and picture shape.
        </p>
      </div>
    </>
  )
}

function ImportReportView({ report, onPublish, onClose }: { report: ImportReport; onPublish: () => void; onClose: () => void }) {
  const c = report.counts
  const [onlyIssues, setOnlyIssues] = useState(true)
  const rows = report.rows.filter(r => !onlyIssues || r.issues.length)
  return (
    <div className="mt-4 rounded-lg border border-line">
      <div className="flex flex-wrap items-center gap-3 border-b border-line px-3 py-2">
        <span className="font-semibold">{report.filename}</span>
        <span className="chip bg-slate-100 text-ink-2">{c.rows} rows</span>
        <span className="chip bg-ok-tint text-ok">{c.ok} ok · {c.new} new · {c.changed} changed</span>
        <span className={clsx('chip', c.errors ? 'bg-bad-tint text-bad' : 'bg-ok-tint text-ok')}>{c.errors} with errors</span>
        <span className="chip bg-amber-tint text-amber-ink">{c.warnings} with warnings</span>
        <span className="chip bg-primary-tint text-primary">{c.images} pictures</span>
        <label className="ml-auto flex items-center gap-1.5 text-[12px]"><input type="checkbox" checked={onlyIssues} onChange={e => setOnlyIssues(e.target.checked)} />Only rows with issues</label>
        <button className="btn" onClick={onClose}><X size={14} />Discard</button>
        <button className="btn btn-primary" disabled={!c.ok || report.status === 'published'} onClick={onPublish}><CheckCircle2 size={15} />Publish {c.ok} products</button>
      </div>
      <div className="max-h-[360px] overflow-y-auto">
        <table className="w-full text-[12px]">
          <thead className="sticky top-0 bg-canvas text-left text-[11px] uppercase tracking-wider text-muted">
            <tr><th className="px-3 py-1.5">Row</th><th>Picture</th><th>SKU</th><th>Product</th><th>Result</th><th>Quality</th><th>Issues</th></tr>
          </thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.row} className="border-t border-line align-top">
                <td className="px-3 py-1.5 font-mono">{r.row}</td>
                <td className="py-1">{r.image ? <img src={mediaUrl(r.image)} className="h-10 w-10 object-contain" /> : <span className="text-muted">—</span>}</td>
                <td className="font-mono">{String(r.data.sku ?? '')}</td>
                <td className="max-w-[260px] truncate">{String(r.data.name ?? '')}</td>
                <td><span className={clsx('tag', r.action === 'error' ? 'bg-bad-tint text-bad' : r.action === 'new' ? 'bg-ok-tint text-ok' : 'bg-slate-100 text-ink-2')}>{r.action}</span></td>
                <td className="font-mono">{r.quality}</td>
                <td className="py-1">{r.issues.map((i, k) => (
                  <div key={k} className={i.severity === 'error' ? 'text-bad' : 'text-amber-ink'}><AlertTriangle size={11} className="mr-1 inline" /><b className="font-mono">{i.code}</b> {i.message}</div>
                ))}</td>
              </tr>
            ))}
            {rows.length === 0 && <tr><td colSpan={7} className="px-3 py-4 text-center text-ok">No issues in any row.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  )
}
