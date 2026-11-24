import { useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import {
  BarChart3, Boxes, Building2, CheckCircle2, ClipboardCheck, Grid3x3, Home, LayoutGrid, Map as MapIcon, Package, RotateCcw,
  Scale, Store as StoreIcon, X,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useStoreCode } from './currentStore'
import { toast, useToasts } from './toast'

interface NavItem { to?: string; label: string; icon: ReactNode; phase2?: boolean }
const nav = (STORE: string): { group: string; items: NavItem[] }[] => [
  { group: 'Plan', items: [
    { to: '/stores', label: 'Stores', icon: <Building2 size={18} /> },
    { to: `/stores/${STORE}`, label: 'Store overview', icon: <StoreIcon size={18} /> },
    { to: `/stores/${STORE}/floor`, label: 'Floor planner', icon: <MapIcon size={18} /> },
    { to: '/fixtures/templates', label: 'Fixture library', icon: <Boxes size={18} /> },
    { to: `/stores/${STORE}/fixtures/G03`, label: 'Fixtures & sections', icon: <Grid3x3 size={18} /> },
    { to: `/stores/${STORE}/plan`, label: 'Shelf planner', icon: <LayoutGrid size={18} /> },
    { to: '/products', label: 'Products & imports', icon: <Package size={18} /> },
    { to: '/rules', label: 'Rules & auto-fill', icon: <Scale size={18} /> },
  ] },
  { group: 'Phase 2', items: [
    { label: 'Approvals', icon: <CheckCircle2 size={18} />, phase2: true },
    { label: 'Execution', icon: <ClipboardCheck size={18} />, phase2: true },
    { label: 'Reports', icon: <BarChart3 size={18} />, phase2: true },
  ] },
]

export function AppShell() {
  const STORE = useStoreCode()
  const NAV = nav(STORE)
  const qc = useQueryClient()
  const navigate = useNavigate()
  const reset = async () => {
    if (!confirm('Reload the sample store SMS-001? All edits and planograms are discarded.')) return
    try {
      await api.resetDemo()
      await qc.invalidateQueries()
      toast.ok('Demo data reloaded')
      navigate('/stores')
    } catch (e) {
      toast.error(String((e as Error).message))
    }
  }
  return (
    <div className="flex h-full">
      <aside className="flex w-[220px] shrink-0 flex-col bg-nav text-slate-300">
        <div className="flex h-12 items-center gap-2 px-4 text-white">
          <div className="grid size-7 place-items-center rounded-md bg-primary text-[11px] font-bold">PL</div>
          <span className="font-semibold">Planogram</span>
          <span className="ml-auto rounded bg-white/10 px-1.5 text-[10px] text-slate-300">POC</span>
        </div>
        <div className="mx-3 mb-1 rounded-md bg-white/5 px-3 py-1.5 text-[11px] text-slate-400">Store <span className="font-mono font-semibold text-white">{STORE}</span></div>
        <nav className="flex-1 overflow-y-auto px-2 py-2">
          <NavLink to="/" end className={({ isActive }) => navCls(isActive)}><Home size={18} />Home</NavLink>
          {NAV.map(g => (
            <div key={g.group} className="mt-4">
              <div className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">{g.group}</div>
              {g.items.map(it => it.to ? (
                <NavLink key={it.label} to={it.to} end={it.label === 'Store overview' || it.label === 'Stores'} className={({ isActive }) => navCls(isActive)}>
                  {it.icon}{it.label}
                </NavLink>
              ) : (
                <div key={it.label} title="Planned for phase 2" className="flex h-9 cursor-not-allowed items-center gap-3 rounded-md px-3 text-slate-500">
                  {it.icon}{it.label}
                </div>
              ))}
            </div>
          ))}
        </nav>
        <div className="border-t border-white/10 p-3">
          <button className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-xs text-slate-400 hover:bg-white/5 hover:text-white" onClick={reset}>
            <RotateCcw size={14} /> Reset demo data
          </button>
          <div className="mt-2 px-2 text-[11px] text-slate-500">Demo tenant · sample data</div>
        </div>
      </aside>
      <main className="flex min-w-0 flex-1 flex-col">
        <Outlet />
      </main>
      <Toasts />
    </div>
  )
}

const navCls = (active: boolean) => clsx(
  'flex h-9 items-center gap-3 rounded-md px-3 text-[13px]',
  active ? 'bg-primary text-white' : 'hover:bg-white/5 hover:text-white')

function Toasts() {
  const { toasts, dismiss } = useToasts()
  return (
    <div className="fixed bottom-10 right-4 z-50 flex w-[380px] flex-col gap-2">
      {toasts.map(t => (
        <div key={t.id} className={clsx('flex items-start gap-2 rounded-lg border bg-white px-3 py-2 shadow-lg',
          t.kind === 'error' ? 'border-red-200' : t.kind === 'ok' ? 'border-emerald-200' : 'border-line')}>
          <span className={clsx('mt-1 size-2 shrink-0 rounded-full', t.kind === 'error' ? 'bg-bad' : t.kind === 'ok' ? 'bg-ok' : 'bg-primary')} />
          <span className="flex-1 text-[13px]">{t.text}</span>
          <button className="text-muted hover:text-ink" onClick={() => dismiss(t.id)}><X size={14} /></button>
        </div>
      ))}
    </div>
  )
}

/** Page header used by every screen: breadcrumb, title and actions. */
export function PageBar({ crumbs, title, children }: { crumbs?: ReactNode; title: ReactNode; children?: ReactNode }) {
  return (
    <header className="flex h-12 shrink-0 items-center gap-3 border-b border-line bg-white px-4">
      {crumbs && <div className="text-[13px] text-muted">{crumbs}</div>}
      <div className="text-[14px] font-semibold">{title}</div>
      <div className="ml-auto flex items-center gap-2">{children}</div>
    </header>
  )
}
