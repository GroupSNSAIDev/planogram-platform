import { create } from 'zustand'

export interface Toast { id: number; kind: 'error' | 'info' | 'ok'; text: string }

interface ToastState {
  toasts: Toast[]
  push: (kind: Toast['kind'], text: string) => void
  dismiss: (id: number) => void
}

let next = 1
export const useToasts = create<ToastState>(set => ({
  toasts: [],
  push: (kind, text) => {
    const id = next++
    set(s => ({ toasts: [...s.toasts, { id, kind, text }] }))
    setTimeout(() => set(s => ({ toasts: s.toasts.filter(t => t.id !== id) })), kind === 'error' ? 6000 : 3000)
  },
  dismiss: id => set(s => ({ toasts: s.toasts.filter(t => t.id !== id) })),
}))

export const toast = {
  error: (text: string) => useToasts.getState().push('error', text),
  info: (text: string) => useToasts.getState().push('info', text),
  ok: (text: string) => useToasts.getState().push('ok', text),
}
