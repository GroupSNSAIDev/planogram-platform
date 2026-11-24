// Layout document for one store: server state + optimistic local edits + command history.
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useState } from 'react'
import { api } from '../../api/client'
import type { Command, LayoutDoc } from '../../api/types'
import { toast } from '../../app/toast'
import { useHistory } from '../../doc/useHistory'
import { rotateFaces } from '../../geometry/layout'

/** Apply the commands the floor needs instantly (move/rotate); everything else waits for the server. */
function optimistic(doc: LayoutDoc, commands: Command[]): LayoutDoc {
  let fixtures = doc.fixtures
  for (const c of commands) {
    const f = fixtures[c.fixture_id as string]
    if (!f) continue
    if (c.type === 'MoveFixture') {
      fixtures = { ...fixtures, [f.id]: { ...f, x_mm: c.x_mm as number, y_mm: c.y_mm as number } }
    } else if (c.type === 'RotateFixture') {
      const rot = c.rotation_deg as number
      const steps = (((rot - f.rotation_deg) / 90) % 4 + 4) % 4
      const swap = steps % 2 === 1
      fixtures = { ...fixtures, [f.id]: {
        ...f, rotation_deg: rot, x_mm: c.x_mm as number, y_mm: c.y_mm as number,
        footprint_w_mm: swap ? f.footprint_d_mm : f.footprint_w_mm,
        footprint_d_mm: swap ? f.footprint_w_mm : f.footprint_d_mm,
        faces: rotateFaces(f.faces, steps),
      } }
    } else if (c.type === 'RemoveFixture') {
      fixtures = { ...fixtures }
      delete fixtures[f.id]
    }
  }
  return fixtures === doc.fixtures ? doc : { ...doc, fixtures }
}

export function useLayout(storeCode: string) {
  const qc = useQueryClient()
  const query = useQuery({ queryKey: ['layout', storeCode], queryFn: () => api.layout(storeCode) })
  const [doc, setDoc] = useState<LayoutDoc | null>(null)
  const [saving, setSaving] = useState(false)
  const [savedAt, setSavedAt] = useState<Date | null>(null)

  useEffect(() => { if (query.data) setDoc(query.data.layout) }, [query.data])

  const send = useCallback(async (commands: Command[]) => {
    setDoc(d => (d ? optimistic(d, commands) : d))
    setSaving(true)
    try {
      const res = await api.layoutCommands(storeCode, commands)
      await qc.invalidateQueries({ queryKey: ['layout', storeCode] })
      setSavedAt(new Date())
      return res.inverse
    } catch (e) {
      toast.error((e as Error).message)
      // roll back the optimistic edit to whatever the server has
      const fresh = await qc.fetchQuery({ queryKey: ['layout', storeCode], queryFn: () => api.layout(storeCode), staleTime: 0 })
      setDoc(fresh.layout)
      return null
    } finally {
      setSaving(false)
    }
  }, [qc, storeCode])

  const history = useHistory(send)
  return { query, doc, setDoc, history, saving, savedAt, templates: query.data?.templates, categories: query.data?.categories }
}
