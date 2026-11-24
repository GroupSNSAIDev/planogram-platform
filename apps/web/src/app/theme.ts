// Colours from docs/spec/DESIGN.md.
export const DEPT_COLOUR: Record<string, string> = {
  'Fresh': '#BBF7D0',
  'Dairy & chilled': '#BFDBFE',
  'Beverages': '#A5F3FC',
  'Frozen': '#C7D2FE',
  'Staples': '#FDE68A',
  'Packaged food': '#FED7AA',
  'Personal care': '#FBCFE8',
  'Home care': '#DDD6FE',
  'General merchandise': '#E5E7EB',
  'Impulse': '#FCA5A5',
  'Promotions': '#D9F99D',
}
export const CAD = {
  rail: '#334155',
  select: '#4338CA',
  dim: '#64748B',
  warn: '#F59E0B',
  bad: '#DC2626',
  canvas: '#F8FAFC',
  grid: '#E2E8F0',
}
export const NON_MERCH = new Set(['checkout', 'self_checkout', 'service_desk'])

export const mm = (v: number) => `${Math.round(v).toLocaleString('en-IN')} mm`
export const m1 = (v: number) => `${(v / 1000).toFixed(1)} m`
