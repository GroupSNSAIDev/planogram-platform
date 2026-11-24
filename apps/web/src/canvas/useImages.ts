// Load product pictures once (shared cache) and re-render when they arrive. Used by Konva canvases.
import { useEffect, useState } from 'react'

const cache = new Map<string, HTMLImageElement>()
const pending = new Map<string, Promise<HTMLImageElement>>()

export function loadImage(url: string): Promise<HTMLImageElement> {
  const hit = cache.get(url)
  if (hit) return Promise.resolve(hit)
  let p = pending.get(url)
  if (!p) {
    p = new Promise((resolve, reject) => {
      const img = new window.Image()
      img.onload = () => { cache.set(url, img); pending.delete(url); resolve(img) }
      img.onerror = () => { pending.delete(url); reject(new Error(`image failed: ${url}`)) }
      img.src = url
    })
    pending.set(url, p)
  }
  return p
}

/** Map of url -> loaded image for the given urls; grows as pictures finish loading. */
export function useImages(urls: string[]): Map<string, HTMLImageElement> {
  const [, bump] = useState(0)
  const key = urls.slice().sort().join('|')
  useEffect(() => {
    let alive = true
    for (const u of urls) {
      if (!u || cache.has(u)) continue
      loadImage(u).then(() => { if (alive) bump(n => n + 1) }).catch(() => {})
    }
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])
  return cache
}
