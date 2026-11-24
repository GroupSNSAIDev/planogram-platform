import { ChevronDown, Download, FileSpreadsheet, FileText, Map as MapIcon } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

/** Store execution pack downloads, scoped to the whole store, one fixture or one section. */
export function ExportMenu({ store, fixture, section, label = 'Download' }: { store: string; fixture?: string; section?: string; label?: string }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const close = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    window.addEventListener('mousedown', close)
    return () => window.removeEventListener('mousedown', close)
  }, [])
  const q = section ? `?section=${encodeURIComponent(section)}` : fixture ? `?fixture=${encodeURIComponent(fixture)}` : ''
  const scope = section ? 'this section' : fixture ? `fixture ${fixture}` : 'the whole store'
  const items = [
    { href: `/api/stores/${store}/exports/floor.pdf`, icon: <MapIcon size={15} />, title: 'Floor plan (PDF)', sub: 'Top view of the store with every fixture code, legend and fixture index' },
    { href: `/api/stores/${store}/exports/planograms.pdf${q}`, icon: <FileText size={15} />, title: 'Planograms (PDF)', sub: `One page per section with product pictures and the shelf list · ${scope}` },
    { href: `/api/stores/${store}/exports/execution.xlsx${q}`, icon: <FileSpreadsheet size={15} />, title: 'Execution sheet (Excel)', sub: `Every shelf position: product, picture, facings, units, cases, size · ${scope}` },
    { href: `/api/stores/${store}/layout/export`, icon: <Download size={15} />, title: 'Design file (.json)', sub: 'The whole store design, to import again later' },
  ]
  return (
    <div ref={ref} className="relative">
      <button className="btn" onClick={() => setOpen(o => !o)}><Download size={15} />{label}<ChevronDown size={13} /></button>
      {open && (
        <div className="absolute right-0 top-9 z-30 w-[340px] rounded-xl border border-line bg-white p-1.5 shadow-xl">
          {items.map(it => (
            <a key={it.title} href={it.href} onClick={() => setOpen(false)} className="flex gap-3 rounded-lg px-2.5 py-2 hover:bg-canvas">
              <span className="mt-0.5 text-primary">{it.icon}</span>
              <span><span className="block text-[13px] font-medium">{it.title}</span><span className="block text-[11.5px] text-muted">{it.sub}</span></span>
            </a>
          ))}
          <div className="px-2.5 pb-1 pt-1.5 text-[11px] text-muted">Large stores take a few seconds to build.</div>
        </div>
      )}
    </div>
  )
}
