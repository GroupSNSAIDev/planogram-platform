import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { ShieldAlert, SlidersHorizontal, Sparkles } from 'lucide-react'
import { api } from '../../api/client'
import { PageBar } from '../../app/AppShell'

const STEPS = [
  ['Choose candidates', 'Products of the section’s category that are eligible for this fixture: sizes present, safety flags reviewed, right temperature, picture if the section requires one. Placement-locked products are left exactly where they are.'],
  ['Facings from days of supply', 'facings = ceil(units sold per day × target days ÷ units per facing). Units per facing = how many packs fit front to back on the shelf. Kept between the minimum and maximum facings.'],
  ['Rank by margin', 'Products are ranked by margin per day. The top 30% count as top sellers. The two best-selling brands of the section are the priority brands for the eye-level rule.'],
  ['Pick a shelf level', 'Only shelf levels where the product fits in height are allowed. Each allowed level gets points: priority brand at eye level +3, top seller at eye +2 or waist +1, heavy item low +1.5 (or high −4), next to its own brand +1, minus up to 2.5 for how full the level already is. The best level with room wins.'],
  ['Order and pack', 'Each level is ordered in brand blocks (best-selling brand first, tallest packs first inside a brand) and spread over every bay, flowing around locked products. If a level overflows, low sellers lose facings first; products that still do not fit are listed as not placed, never forced.'],
  ['Share spare space', 'Leftover width on each shelf goes to that shelf’s best sellers, one facing at a time, up to the maximum.'],
  ['Score and explain', 'The proposal is checked with every rule below, scored, and every product gets a one-line reason. Nothing is saved until the planner accepts it.'],
]

export function RulesPage() {
  const q = useQuery({ queryKey: ['rules'], queryFn: api.rules })
  const data = q.data
  return (
    <>
      <PageBar title={<>Rules <span className="ml-2 font-normal text-muted">· {data ? `${data.rule_set.name} (${data.rule_set.id})` : ''}</span></>} />
      <div className="flex-1 overflow-y-auto p-5">
        <div className="grid grid-cols-[1fr_420px] gap-5">
          <div>
            <div className="mb-3 flex items-center gap-2 text-[14px] font-semibold"><ShieldAlert size={16} className="text-bad" />Hard rules · must pass (they block approval)</div>
            {data?.rules.filter(r => r.severity === 'hard').map(r => <RuleCard key={r.id} r={r} />)}
            <div className="mb-3 mt-6 flex items-center gap-2 text-[14px] font-semibold"><SlidersHorizontal size={16} className="text-amber-ink" />Soft rules · weighted into the score</div>
            {data?.rules.filter(r => r.severity === 'soft').map(r => <RuleCard key={r.id} r={r} />)}
            {data && <p className="mt-3 rounded-lg bg-canvas p-3 font-mono text-[12px]">{data.score_formula}</p>}
          </div>
          <div>
            <div className="card sticky top-0 p-4">
              <div className="mb-1 flex items-center gap-2 text-[14px] font-semibold"><Sparkles size={16} className="text-primary" />How auto-fill places products</div>
              <p className="mb-3 text-[12px] text-ink-2">A deterministic heuristic ({data?.autofill.engine_version}): the same section, products and rules always give the same proposal. No machine learning yet; that comes in phase 2 (demand forecasts, space elasticity, optimiser).</p>
              <ol className="space-y-3">
                {STEPS.map(([t, d], i) => (
                  <li key={t} className="flex gap-3">
                    <span className="grid size-6 shrink-0 place-items-center rounded-full bg-primary text-[11px] font-bold text-white">{i + 1}</span>
                    <div><div className="text-[13px] font-medium">{t}</div><div className="text-[12px] text-ink-2">{d}</div></div>
                  </li>
                ))}
              </ol>
              {data && (
                <div className="mt-4 border-t border-line pt-3">
                  <div className="label-up mb-1">Parameters</div>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(data.autofill.params).map(([k, v]) => <span key={k} className="tag bg-slate-100 font-mono text-ink-2">{k} = {String(v)}</span>)}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  )
}

function RuleCard({ r }: { r: { id: string; name: string; type: string; severity: string; weight?: number; params?: Record<string, unknown>; what?: string; measure?: string } }) {
  return (
    <div className={clsx('card mb-2.5 p-3', r.severity === 'hard' ? 'border-l-4 border-l-red-400' : 'border-l-4 border-l-amber-400')}>
      <div className="flex items-center gap-2">
        <span className="font-mono text-[12px] font-semibold">{r.id}</span>
        <span className="text-[13px] font-semibold">{r.name}</span>
        <span className={clsx('chip ml-auto', r.severity === 'hard' ? 'bg-bad-tint text-bad' : 'bg-amber-tint text-amber-ink')}>{r.severity}{r.weight ? ` · weight ${r.weight}` : ''}</span>
      </div>
      <p className="mt-1.5 text-[12.5px] text-ink">{r.what}</p>
      <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[11.5px] text-muted">
        <span>Measured as: {r.measure}</span>
        {r.params && Object.entries(r.params).map(([k, v]) => <span key={k} className="tag bg-slate-100 font-mono">{k}: {Array.isArray(v) ? v.join(', ') : String(v)}</span>)}
      </div>
    </div>
  )
}
