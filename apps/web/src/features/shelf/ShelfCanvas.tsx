import type Konva from 'konva'
import type { KonvaEventObject } from 'konva/lib/Node'
import { memo, useEffect, useRef, useState } from 'react'
import { Arc, Group, Image as KImage, Layer, Line, Rect, Stage, Text } from 'react-konva'
import { mediaUrl } from '../../api/client'
import { useImages } from '../../canvas/useImages'
import type { Position, Product } from '../../api/types'
import { useElementSize } from '../../canvas/useElementSize'
import { type DropPreview, previewDrop, type SectionModel, tint } from './shelfModel'

const HEADROOM = 320    // mm drawn above the fixture top
const RAIL = 15         // shelf thickness, mm
const PAD = { left: 56, top: 16, right: 24, bottom: 40 }

export interface ShelfCanvasProps {
  model: SectionModel
  positions: Record<string, Position>
  products: Record<string, Product>
  fixtureTemp: string
  severity: Record<string, 'hard' | 'soft'>
  selectedId: string | null
  highlightProduct: string | null
  showEye: boolean
  showMm: boolean
  readOnly: boolean
  dragProduct: Product | null          // product being dragged in from the panel
  zoomRequest: { factor: number; n: number }
  onZoom: (pct: number) => void
  onSelect: (id: string | null) => void
  onMove: (id: string, surfaceId: string, seq: number) => void
  onDropProduct: (product: Product, surfaceId: string, seq: number) => void
  onCursor: (x: number, h: number) => void
}

export function ShelfCanvas(p: ShelfCanvasProps) {
  const { model } = p
  const [wrapRef, size] = useElementSize<HTMLDivElement>()
  const stageRef = useRef<Konva.Stage>(null)
  const Htop = model.maxHeight + HEADROOM
  const fitH = size.height ? (size.height - PAD.top - PAD.bottom) / Htop : 0.3
  const fitAll = size.width ? Math.min(fitH, (size.width - PAD.left - PAD.right) / model.totalWidth) : 0.1
  const [view, setView] = useState<{ s: number; x: number; y: number } | null>(null)
  const s = view?.s ?? fitH
  const ox = view?.x ?? PAD.left
  const oy = view?.y ?? PAD.top
  const [preview, setPreview] = useState<DropPreview | null>(null)
  const [dragging, setDragging] = useState<string | null>(null)
  const images = useImages([...new Set(Object.values(p.positions).map(q => mediaUrl(p.products[q.product_id]?.image)).filter(Boolean))])

  const { onZoom } = p
  useEffect(() => { onZoom(Math.round(s / fitH * 100)) }, [s, fitH, onZoom])
  const zoomN = p.zoomRequest.n
  useEffect(() => {
    if (!zoomN) return
    const f = p.zoomRequest.factor
    if (f === 0) { setView({ s: fitAll, x: PAD.left, y: PAD.top + ((size.height - PAD.top - PAD.bottom) - Htop * fitAll) / 2 }); return }
    if (f === -1) { setView(null); return }
    setView(v => ({ s: (v?.s ?? fitH) * f, x: v?.x ?? PAD.left, y: v?.y ?? PAD.top }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [zoomN])

  const toMm = (pt: { x: number; y: number }) => ({ x: (pt.x - ox) / s, h: Htop - (pt.y - oy) / s })
  const pointerMm = () => {
    const pt = stageRef.current?.getPointerPosition()
    return pt ? toMm(pt) : null
  }

  const onWheel = (e: KonvaEventObject<WheelEvent>) => {
    e.evt.preventDefault()
    const pt = stageRef.current?.getPointerPosition()
    if (!pt) return
    if (!e.evt.ctrlKey && Math.abs(e.evt.deltaX) + Math.abs(e.evt.deltaY) > 0 && !e.evt.altKey && e.evt.shiftKey) {
      setView({ s, x: ox - e.evt.deltaY, y: oy })
      return
    }
    const f = e.evt.deltaY < 0 ? 1.1 : 1 / 1.1
    const s1 = Math.max(fitAll * 0.6, Math.min(fitH * 4, s * f))
    setView({ s: s1, x: pt.x - ((pt.x - ox) / s) * s1, y: pt.y - ((pt.y - oy) / s) * s1 })
  }

  const yOf = (h: number) => Htop - h
  const px = 1 / s
  const font = (pxSize: number) => pxSize * px

  return (
    <div
      ref={wrapRef}
      className="relative h-full w-full overflow-hidden bg-canvas"
      onDragOver={e => {
        if (!p.dragProduct || p.readOnly || !stageRef.current) return
        e.preventDefault()
        stageRef.current.setPointersPositions(e.nativeEvent)
        const m = pointerMm()
        if (m) setPreview(previewDrop(model, p.positions, p.products, p.fixtureTemp, m.x, m.h, p.dragProduct))
      }}
      onDragLeave={() => setPreview(null)}
      onDrop={e => {
        e.preventDefault()
        if (preview && p.dragProduct) p.onDropProduct(p.dragProduct, preview.surface.id, preview.seq)
        setPreview(null)
      }}
    >
      {size.width > 0 && (
        <Stage
          ref={stageRef}
          width={size.width}
          height={size.height}
          draggable
          x={0}
          y={0}
          onDragEnd={e => {
            if (e.target !== stageRef.current) return
            setView({ s, x: ox + e.target.x(), y: oy + e.target.y() })
            e.target.position({ x: 0, y: 0 })
          }}
          onWheel={onWheel}
          onMouseMove={() => { const m = pointerMm(); if (m) p.onCursor(m.x, m.h) }}
          onClick={e => { if (e.target === stageRef.current || e.target.name() === 'bg') p.onSelect(null) }}
        >
          <Layer x={ox} y={oy} scaleX={s} scaleY={s}>
            <Rect name="bg" x={-PAD.left * px} y={0} width={model.totalWidth + (PAD.left + PAD.right) * px} height={Htop} fill="#F8FAFC" />
            {/* height ruler */}
            {p.showMm && Array.from({ length: Math.floor(Htop / 250) + 1 }, (_, i) => i * 250).map(h => (
              <Group key={h} listening={false}>
                <Line points={[-8 * px, yOf(h), 0, yOf(h)]} stroke="#94A3B8" strokeWidth={px} />
                <Text x={-48 * px} y={yOf(h) - 5 * px} width={38 * px} align="right" text={String(h)} fontSize={font(9.5)} fill="#64748B" fontFamily="JetBrains Mono" />
              </Group>
            ))}
            {/* bays: back panel and uprights */}
            {model.bays.map(b => (
              <Group key={b.idx} listening={false}>
                <Rect x={b.x0} y={yOf(b.height)} width={b.width} height={b.height} fill="#FFFFFF" stroke="#CBD5E1" strokeWidth={px} />
                <Rect x={b.x0 - 6 * px / 2} y={yOf(b.height)} width={6 * px} height={b.height} fill="#94A3B8" />
                <Text x={b.x0} y={Htop + 10 * px} width={b.width} align="center" text={`Bay ${b.idx} · ${b.width.toLocaleString('en-IN')} mm`}
                  fontSize={font(11)} fill="#475569" fontFamily="JetBrains Mono" />
              </Group>
            ))}
            <Rect x={model.totalWidth - 3 * px} y={yOf(model.maxHeight)} width={6 * px} height={model.maxHeight} fill="#94A3B8" listening={false} />
            {p.showEye && (
              <Group listening={false}>
                <Rect x={0} y={yOf(1600)} width={model.totalWidth} height={400} fill="#EEF2FF" opacity={0.55} />
                <Text x={model.totalWidth - 4 * px} y={yOf(1600) + 3 * px} text="EYE-LEVEL BAND 1,200–1,600 mm" align="right"
                  width={model.totalWidth} offsetX={model.totalWidth} fontSize={font(10)} fontStyle="600" fill="#4338CA" />
              </Group>
            )}
            {/* shelves */}
            {model.surfaces.map(su => {
              const x0 = model.bayOffset[su.bay_idx]
              const target = preview?.surface.id === su.id
              return (
                <Group key={su.id} listening={false}>
                  {target && (
                    <Rect x={x0} y={yOf(su.height_from_floor_mm + su.clear_height_mm)} width={su.width_mm} height={su.clear_height_mm}
                      fill={preview.ok ? '#059669' : '#DC2626'} opacity={0.1} />
                  )}
                  <Rect x={x0} y={yOf(su.height_from_floor_mm)} width={su.width_mm} height={RAIL}
                    fill={target ? (preview.ok ? '#059669' : '#DC2626') : '#334155'} />
                  {p.showMm && su.bay_idx === model.bays[0].idx && (
                    <Text x={x0 + 4 * px} y={yOf(su.height_from_floor_mm) + RAIL + 2 * px}
                      text={`Shelf ${su.level} · ${su.height_from_floor_mm.toLocaleString('en-IN')} mm`} fontSize={font(9)} fill="#64748B" fontFamily="JetBrains Mono" />
                  )}
                </Group>
              )
            })}
            {/* products */}
            {Object.values(p.positions).map(pos => {
              const su = model.surfaceById[pos.surface_id]
              const prod = p.products[pos.product_id]
              if (!su || !prod) return null
              return (
                <PositionShape
                  key={pos.id}
                  pos={pos}
                  prod={prod}
                  img={prod.image ? images.get(mediaUrl(prod.image)) : undefined}
                  x={model.bayOffset[su.bay_idx] + pos.x_mm}
                  y={yOf(su.height_from_floor_mm)}
                  px={px}
                  selected={p.selectedId === pos.id}
                  dim={!!p.highlightProduct && p.highlightProduct !== pos.product_id}
                  severity={p.severity[pos.id]}
                  draggable={!p.readOnly && !pos.locked}
                  ghost={dragging === pos.id}
                  onSelect={p.onSelect}
                  onDragStart={() => { setDragging(pos.id); p.onSelect(pos.id) }}
                  onDragMove={() => {
                    const m = pointerMm()
                    if (m) setPreview(previewDrop(model, p.positions, p.products, p.fixtureTemp, m.x, m.h, prod, pos))
                  }}
                  onDragEnd={node => {
                    node.position({ x: model.bayOffset[su.bay_idx] + pos.x_mm, y: yOf(su.height_from_floor_mm) })
                    setDragging(null)
                    const target = preview
                    setPreview(null)
                    if (target && (target.surface.id !== pos.surface_id || target.seq !== pos.seq)) p.onMove(pos.id, target.surface.id, target.seq)
                  }}
                />
              )
            })}
            {/* insertion marker and fit message while dragging */}
            {preview && (
              <Group listening={false}>
                <Rect x={model.bayOffset[preview.surface.bay_idx] + preview.insertX - 2 * px} y={yOf(preview.surface.height_from_floor_mm + preview.surface.clear_height_mm)}
                  width={4 * px} height={preview.surface.clear_height_mm} fill={preview.ok ? '#059669' : '#DC2626'} />
                <Rect x={model.bayOffset[preview.surface.bay_idx]} y={yOf(preview.surface.height_from_floor_mm + preview.surface.clear_height_mm) - 22 * px}
                  width={Math.max(preview.surface.width_mm, 260 * px)} height={20 * px} fill={preview.ok ? '#059669' : '#DC2626'} cornerRadius={4 * px} />
                <Text x={model.bayOffset[preview.surface.bay_idx] + 6 * px} y={yOf(preview.surface.height_from_floor_mm + preview.surface.clear_height_mm) - 17 * px}
                  text={preview.ok ? `Fits · Bay ${preview.surface.bay_idx} · Shelf ${preview.surface.level}` : preview.issues[0].message}
                  fontSize={font(11)} fill="#fff" fontStyle="600" />
              </Group>
            )}
          </Layer>
        </Stage>
      )}
    </div>
  )
}

interface PosProps {
  pos: Position; prod: Product; img?: HTMLImageElement; x: number; y: number; px: number
  selected: boolean; dim: boolean; severity?: 'hard' | 'soft'; draggable: boolean; ghost: boolean
  onSelect: (id: string) => void; onDragStart: () => void; onDragMove: () => void; onDragEnd: (node: Konva.Node) => void
}

const PositionShape = memo(function PositionShape(p: PosProps) {
  const { pos, prod, px } = p
  const fw = pos.facings_wide, fh = pos.facings_high
  const W = prod.width_mm, H = prod.height_mm
  const placeholder = !prod.has_image
  const img = p.img
  const colour = prod.colour || '#94A3B8'
  const stroke = p.selected ? '#4338CA' : p.severity === 'hard' ? '#DC2626' : p.severity === 'soft' ? '#F59E0B' : null
  const label = W / px > 34
  const facings = []
  for (let i = 0; i < fw; i++) {
    for (let j = 0; j < fh; j++) {
      facings.push(
        <Group key={`${i}-${j}`} x={i * W} y={-(j + 1) * H}>
          {img ? (
            <>
              <Rect width={W} height={H} fill="#ffffff" />
              <KImage image={img} x={0.6 * px} y={0.6 * px} width={W - 1.2 * px} height={H - 1.2 * px} />
              <Rect width={W} height={H} stroke="rgba(15,23,42,0.18)" strokeWidth={px} />
            </>
          ) : (<>
          <Rect width={W} height={H} fill={placeholder ? '#F1F5F9' : tint(colour, 0.15)} stroke={placeholder ? '#94A3B8' : '#ffffff'}
            strokeWidth={placeholder ? px : 1.2 * px} dash={placeholder ? [4 * px, 3 * px] : undefined} />
          {!placeholder && <Rect x={W * 0.12} y={H * 0.12} width={W * 0.76} height={H * 0.34} fill={tint(colour, 0.75)} cornerRadius={3 * px} />}
          {label && (
            <Text x={2 * px} y={placeholder ? H * 0.3 : H * 0.16} width={W - 4 * px} align="center" wrap="word"
              text={placeholder ? prod.name : prod.brand.toUpperCase()} fontSize={Math.min(10, (W / px) / 7) * px}
              fontStyle={placeholder ? 'normal' : 'bold'} fill={placeholder ? '#64748B' : '#0F172A'} />
          )}
          {label && !placeholder && (
            <Text x={2 * px} y={H * 0.56} width={W - 4 * px} align="center" text={shortName(prod)} fontSize={Math.min(9, (W / px) / 8) * px}
              fill="#ffffff" fontStyle="600" wrap="word" />
          )}
          </>)}
        </Group>,
      )
    }
  }
  return (
    <Group
      x={p.x}
      y={p.y}
      opacity={p.ghost ? 0.5 : p.dim ? 0.3 : 1}
      draggable={p.draggable}
      onClick={e => { e.cancelBubble = true; p.onSelect(pos.id) }}
      onTap={() => p.onSelect(pos.id)}
      onDragStart={e => { e.cancelBubble = true; p.onDragStart() }}
      onDragMove={e => { e.cancelBubble = true; p.onDragMove() }}
      onDragEnd={e => { e.cancelBubble = true; p.onDragEnd(e.target) }}
      onMouseEnter={e => { const c = e.target.getStage()?.container(); if (c) c.style.cursor = p.draggable ? 'grab' : 'pointer' }}
      onMouseLeave={e => { const c = e.target.getStage()?.container(); if (c) c.style.cursor = 'default' }}
    >
      {facings}
      {stroke && <Rect y={-fh * H} width={fw * W} height={fh * H} stroke={stroke} strokeWidth={(p.selected ? 2.5 : 2) * px} />}
      {p.selected && (
        <Group y={-fh * H - 13 * px}>
          <Rect width={Math.min(fw * W, 62 * px)} height={12 * px} fill={p.selected ? '#4338CA' : '#334155'} cornerRadius={2 * px} opacity={0.9} />
          <Text x={3 * px} y={2 * px} text={`${fw}×${fh}×${pos.facings_deep}`} fontSize={8.5 * px} fill="#fff" fontFamily="JetBrains Mono" />
        </Group>
      )}
      {pos.locked && (
        <Group x={fw * W - 14 * px} y={-fh * H + 3 * px}>
          <Rect width={11 * px} height={13 * px} fill="#ffffff" cornerRadius={2 * px} opacity={0.9} />
          <Arc x={5.5 * px} y={6 * px} innerRadius={2 * px} outerRadius={3.3 * px} angle={180} rotation={180} fill="#334155" />
          <Rect x={1.8 * px} y={6 * px} width={7.4 * px} height={5.5 * px} fill="#334155" cornerRadius={1 * px} />
        </Group>
      )}
    </Group>
  )
})

const shortName = (p: Product) => p.name.replace(p.brand, '').replace('(sample)', '').trim()
