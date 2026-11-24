// Undo/redo over command batches (spec 12.2). Every applied batch returns its inverse from the
// server; undo sends that inverse as a new batch, so history stays linear and auditable.
import { useCallback, useRef, useState } from 'react'
import type { Command } from '../api/types'

interface Entry { forward: Command[]; inverse: Command[] }

export function useHistory(send: (commands: Command[]) => Promise<Command[] | null>) {
  const undoStack = useRef<Entry[]>([])
  const redoStack = useRef<Entry[]>([])
  const [, bump] = useState(0)
  const busy = useRef(false)

  /** Apply a batch; on success it can be undone. Returns false if the server refused it. */
  const run = useCallback(async (commands: Command[]) => {
    const inverse = await send(commands)
    if (!inverse) return false
    undoStack.current.push({ forward: commands, inverse })
    redoStack.current = []
    bump(n => n + 1)
    return true
  }, [send])

  const undo = useCallback(async () => {
    const e = undoStack.current.at(-1)
    if (!e || busy.current) return
    busy.current = true
    const inverse = await send(e.inverse)
    busy.current = false
    if (!inverse) return
    undoStack.current.pop()
    redoStack.current.push({ forward: e.inverse, inverse })
    bump(n => n + 1)
  }, [send])

  const redo = useCallback(async () => {
    const e = redoStack.current.at(-1)
    if (!e || busy.current) return
    busy.current = true
    const inverse = await send(e.inverse)
    busy.current = false
    if (!inverse) return
    redoStack.current.pop()
    undoStack.current.push({ forward: e.inverse, inverse })
    bump(n => n + 1)
  }, [send])

  const clear = useCallback(() => {
    undoStack.current = []
    redoStack.current = []
    bump(n => n + 1)
  }, [])

  return { run, undo, redo, clear, canUndo: undoStack.current.length > 0, canRedo: redoStack.current.length > 0 }
}
