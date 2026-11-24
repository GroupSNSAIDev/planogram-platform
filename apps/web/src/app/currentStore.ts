// The store the planner is working on: taken from the URL when present, remembered for the navigation.
import { useEffect } from 'react'
import { useParams } from 'react-router-dom'

const KEY = 'planogram.store'

export function rememberStore(code: string) {
  try { localStorage.setItem(KEY, code) } catch { /* private mode */ }
}

export function currentStore(): string {
  try { return localStorage.getItem(KEY) || 'SMS-001' } catch { return 'SMS-001' }
}

/** Store code from the route (and remember it), or the last one used. */
export function useStoreCode(): string {
  const { code } = useParams()
  useEffect(() => { if (code) rememberStore(code) }, [code])
  return code ?? currentStore()
}
