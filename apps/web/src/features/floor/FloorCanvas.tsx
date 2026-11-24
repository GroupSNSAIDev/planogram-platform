import type Konva from 'konva'
import type { KonvaEventObject } from 'konva/lib/Node'
import { memo, useEffect, useMemo, useRef, useState } from 'react'
import { Circle, Group, Layer, Line, Rect, Stage, Text } from 'react-konva'
import type { Category, Fixture, Landmark, LayoutDoc, Section, TemplateDef, Zone } from '../../api/types'
import { CAD, DEPT_COLOUR, NON_MERCH } from '../../app/theme'
import { useElementSize } from '../../canvas/useElementSize'
import { frontEdge, sectionFloorRects } from './floorGeometry'

export interface Layers { zones: boolean; sections: boolean; labels: boolean; grid: boolean }
export type Tool = 'select' | 'zone' | 'pillar' | 'door'
export type Box = { x: number; y: number; w: number; h: number }

interface Props {
  doc: LayoutDoc
  templates: Record<string, TemplateDef>
  categories: Record<string, Category>
  selectedIds?: Set<string>
  selectedZone?: string | null
  bad?: Set<string>
  warn?: Set<string>
  layers?: Layers
  editable?: boolean
  snapMm?: number
  tool?: Tool
  showRulers?: boolean
  showMinimap?: boolean
  onSelect?: (id: string | null, additive?: boolean) => void
  onSelectMany?: (ids: string[]) => void
  onSelectZone?: (id: string | null) => void
  onDragMove?: (id: string, x: number, y: number) => void
  onDragEnd?: (id: string, x: number, y: number) => void
  onZoneMove?: (zone: Zone, x: number, y: number) => void
  onDrawRect?: (tool: Tool, box: Box) => void
  onDropTemplate?: (templateCode: string, x: number, y: number) => void
  onCursor?: (x: number, y: number) => void
  onZoom?: (pct: number) => void
  zoomRequest?: { factor: number; n: number }
  focusRequest?: { id: string; n: number }
  highlight?: string | null
}

const ZONE_COLOUR: Record<string, string> = {
  entrance: '#059669', checkout: '#D97706', chilled: '#2563EB', frozen: '#4F46E5',
  main_aisle: '#6366F1', centre_store: '#64748B', perimeter: '#A16207', promotion: '#65A30D', back_of_house: '#475569',
}
const DEFAULT_LAYERS: Layers = { zones: true, sections: true, labels: true, grid: true }
const RULER = 22

export function FloorCanvas(props: Props) {
  const { doc, templates, categories, layers = DEFAULT_LAYERS, editable = false, snapMm = 50, tool = 'select' } = props
  const [wrapRef, size] = useElementSize<HTMLDivElement>()
  const stageRef = useRef<Konva.Stage>(null)
  const rul = props.showRulers ? RULER : 0
  const pad = 40
  const W = doc.store.width_mm, D = doc.store.depth_mm
  const fitScale = size.width && size.height ? Math.min((size.width - rul - 2 * pad) / W, (size.height - rul - 2 * pad) / D) : 0.02
  const [view, setView] = useState<{ scale: number; x: number; y: number } | null>(null)
  const scale = view?.scale ?? fitScale
  const pos = view ? { x: view.x, y: view.y } : { x: rul + (size.width - rul - W * fitScale) / 2, y: rul + (size.height - rul - D * fitScale) / 2 }
  const [hover, setHover] = useState<{ id: string; x: number; y: number } | null>(null)
  const [box, setBox] = useState<Box | null>(null)
  const boxStart = useRef<{ x: number; y: number; tool: Tool | 'box' } | null>(null)

  const { onZoom } = props
  useEffect(() => { onZoom?.(Math.round((scale / fitScale) * 100)) }, [scale, fitScale, onZoom])

  const minScale = fitScale * 0.4, maxScale = Math.max(fitScale * 40, 0.25)
  const zoomN = props.zoomRequest?.n
  useEffect(() => {
    if (!props.zoomRequest || !size.width) return
    const { factor } = props.zoomRequest
    if (factor === 0) { setView(null); return }
    setView(v => {
      const s0 = v?.scale ?? fitScale
      const p0 = v ? { x: v.x, y: v.y } : pos
      const s1 = Math.max(minScale, Math.min(maxScale, s0 * factor))
      const cx = size.width / 2, cy = size.height / 2
      return { scale: s1, x: cx - ((cx - p0.x) / s0) * s1, y: cy - ((cy - p0.y) / s0) * s1 }
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [zoomN])

  // search: centre and zoom on a fixture
  const focusN = props.focusRequest?.n
  useEffect(() => {
    const f = props.focusRequest && doc.fixtures[props.focusRequest.id]
    if (!f || !size.width) return
    const s1 = Math.max(scale, Math.min(maxScale, Math.min(size.width / (f.footprint_w_mm * 6), size.height / (f.footprint_d_mm * 3))))
    centreOn(f.x_mm + f.footprint_w_mm / 2, f.y_mm + f.footprint_d_mm / 2, s1)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusN])

  function centreOn(xMm: number, yMm: number, s1 = scale) {
    setView({ scale: s1, x: rul + (size.width - rul) / 2 - xMm * s1, y: rul + (size.height - rul) / 2 - yMm * s1 })
  }

  const onWheel = (e: KonvaEventObject<WheelEvent>) => {
    e.evt.preventDefault()
    const p = stageRef.current?.getPointerPosition()
    if (!p) return
    if (e.evt.shiftKey) { setView({ scale, x: pos.x - e.evt.deltaY, y: pos.y }); return }
    const factor = e.evt.deltaY < 0 ? 1.15 : 1 / 1.15
    const s1 = Math.max(minScale, Math.min(maxScale, scale * factor))
    setView({ scale: s1, x: p.x - ((p.x - pos.x) / scale) * s1, y: p.y - ((p.y - pos.y) / scale) * s1 })
  }

  const toMm = (px: { x: number; y: number }) => ({ x: (px.x - pos.x) / scale, y: (px.y - pos.y) / scale })
  const snap = (v: number) => Math.round(v / snapMm) * snapMm

  const sectionsByFixture = useMemo(() => {
    const m = new Map<string, Section[]>()
    for (const s of Object.values(doc.sections)) {
      const list = m.get(s.fixture_id) ?? []
      list.push(s)
      m.set(s.fixture_id, list)
    }
    return m
  }, [doc.sections])
  const fixtures = useMemo(() => Object.values(doc.fixtures).sort((a, b) => a.code.localeCompare(b.code)), [doc.fixtures])
  const px = 1 / scale
  const drawing = tool !== 'select'

  const startBox = (e: KonvaEventObject<MouseEvent>) => {
    const onEmpty = e.target === stageRef.current || e.target.name() === 'floor' || e.target.name() === 'zone'
    if (!onEmpty) return
    if (!(drawing || (e.evt.shiftKey && editable))) return
    const p = stageRef.current?.getPointerPosition()
    if (!p) return
    const m = toMm(p)
    if (tool === 'pillar' || tool === 'door') {
      props.onDrawRect?.(tool, tool === 'pillar' ? { x: snap(m.x - 300), y: snap(m.y - 300), w: 600, h: 600 } : { x: snap(m.x - 1000), y: snap(m.y), w: 2000, h: 200 })
      return
    }
    stageRef.current?.draggable(false)
    boxStart.current = { x: snap(m.x), y: snap(m.y), tool: drawing ? tool : 'box' }
    setBox({ x: snap(m.x), y: snap(m.y), w: 0, h: 0 })
  }
  const moveBox = () => {
    const p = stageRef.current?.getPointerPosition()
    if (!p) return
    const m = toMm(p)
    props.onCursor?.(m.x, m.y)
    if (!boxStart.current) return
    const s0 = boxStart.current
    const x2 = snap(m.x), y2 = snap(m.y)
    setBox({ x: Math.min(s0.x, x2), y: Math.min(s0.y, y2), w: Math.abs(x2 - s0.x), h: Math.abs(y2 - s0.y) })
  }
  const endBox = () => {
    const s0 = boxStart.current
    boxStart.current = null
    stageRef.current?.draggable(true)
    if (!s0 || !box) { setBox(null); return }
    if (box.w > 200 && box.h > 200) {
      if (s0.tool === 'box') {
        const ids = fixtures.filter(f => f.x_mm < box.x + box.w && f.x_mm + f.footprint_w_mm > box.x && f.y_mm < box.y + box.h && f.y_mm + f.footprint_d_mm > box.y).map(f => f.id)
        props.onSelectMany?.(ids)
      } else props.onDrawRect?.(s0.tool, box)
    }
    setBox(null)
  }

  const hovered = hover ? doc.fixtures[hover.id] : null

  return (
    <div
      ref={wrapRef}
      className="relative h-full w-full overflow-hidden"
      style={{ background: '#EEF1F6', cursor: drawing ? 'crosshair' : undefined }}
      onDragOver={e => { if (props.onDropTemplate) e.preventDefault() }}
      onDrop={e => {
        const code = e.dataTransfer.getData('text/x-template')
        if (!code || !props.onDropTemplate || !stageRef.current) return
        e.preventDefault()
        stageRef.current.setPointersPositions(e.nativeEvent)
        const p = stageRef.current.getPointerPosition()
        if (p) { const m = toMm(p); props.onDropTemplate(code, m.x, m.y) }
      }}
      onMouseLeave={() => setHover(null)}
    >
      {size.width > 0 && (
        <Stage
          ref={stageRef}
          width={size.width}
          height={size.height}
          draggable={!drawing}
          x={0}
          y={0}
          onDragEnd={e => {
            if (e.target !== stageRef.current) return
            setView({ scale, x: pos.x + e.target.x(), y: pos.y + e.target.y() })
            e.target.position({ x: 0, y: 0 })
          }}
          onWheel={onWheel}
          onMouseDown={startBox}
          onMouseMove={moveBox}
          onMouseUp={endBox}
          onClick={e => {
            if (e.target === stageRef.current || e.target.name() === 'floor') { props.onSelect?.(null); props.onSelectZone?.(null) }
          }}
        >
          <Layer x={pos.x} y={pos.y} scaleX={scale} scaleY={scale}>
            <Rect x={-200 * px} y={-200 * px} width={W + 400 * px} height={D + 400 * px} fill="#EEF1F6" listening={false} />
            <Rect name="floor" x={0} y={0} width={W} height={D} fill="#ffffff" shadowColor="#0F172A" shadowBlur={18} shadowOpacity={0.12} />
            {layers.grid && <Grid w={W} d={D} px={px} />}
            {layers.zones && doc.zones.map(z => (
              <ZoneShape key={z.id} z={z} px={px} selected={props.selectedZone === z.id} labels={layers.labels}
                editable={editable && !drawing} snap={snap}
                onSelect={() => props.onSelectZone?.(z.id)} onMove={(x, y) => props.onZoneMove?.(z, x, y)} />
            ))}
            <Rect x={0} y={0} width={W} height={D} stroke={CAD.rail} strokeWidth={Math.max(80, 3 * px)} listening={false} />
            {doc.landmarks.map(lm => <LandmarkShape key={lm.id} lm={lm} px={px} D={D} />)}
          </Layer>
          <Layer x={pos.x} y={pos.y} scaleX={scale} scaleY={scale}>
            {fixtures.map(f => (
              <FixtureShape
                key={f.id}
                f={f}
                tpl={templates[f.template_code]}
                sections={sectionsByFixture.get(f.id) ?? []}
                categories={categories}
                selected={props.selectedIds?.has(f.id) ?? false}
                highlighted={props.highlight === f.id || hover?.id === f.id}
                bad={props.bad?.has(f.id) ?? false}
                warn={props.warn?.has(f.id) ?? false}
                showSections={layers.sections}
                showLabels={layers.labels}
                px={px}
                editable={editable && !drawing}
                snapMm={snapMm}
                onSelect={props.onSelect}
                onDragMove={props.onDragMove}
                onDragEnd={props.onDragEnd}
                onHover={(id, on) => {
                  const p = stageRef.current?.getPointerPosition()
                  setHover(on && p ? { id, x: p.x, y: p.y } : null)
                }}
              />
            ))}
            {box && <Rect x={box.x} y={box.y} width={box.w} height={box.h} fill={tool === 'zone' ? '#6366F1' : '#4338CA'} opacity={0.12}
              stroke="#4338CA" strokeWidth={1.5 * px} dash={[6 * px, 4 * px]} listening={false} />}
          </Layer>
        </Stage>
      )}
      {props.showRulers && size.width > 0 && <Rulers W={W} D={D} scale={scale} pos={pos} size={size} />}
      {props.showMinimap && size.width > 0 && (
        <Minimap doc={doc} fixtures={fixtures} categories={categories} sectionsByFixture={sectionsByFixture}
          view={{ scale, ...pos }} size={size} onJump={(x, y) => centreOn(x, y)} />
      )}
      {hovered && hover && !boxStart.current && (
        <HoverCard f={hovered} tpl={templates[hovered.template_code]} sections={sectionsByFixture.get(hovered.id) ?? []}
          categories={categories} x={hover.x} y={hover.y} maxW={size.width} />
      )}
    </div>
  )
}

// ----------------------------------------------------------------------------- pieces

const Grid = memo(function Grid({ w, d, px }: { w: number; d: number; px: number }) {
  const step = px > 120 ? 10000 : px > 30 ? 5000 : 1000
  const lines = []
  for (let x = step; x < w; x += step) lines.push(<Line key={`x${x}`} points={[x, 0, x, d]} stroke={x % 5000 === 0 ? '#E2E8F0' : '#F1F5F9'} strokeWidth={px} />)
  for (let y = step; y < d; y += step) lines.push(<Line key={`y${y}`} points={[0, y, w, y]} stroke={y % 5000 === 0 ? '#E2E8F0' : '#F1F5F9'} strokeWidth={px} />)
  return <Group listening={false}>{lines}</Group>
})

function ZoneShape({ z, px, selected, labels, editable, snap, onSelect, onMove }: {
  z: Zone; px: number; selected: boolean; labels: boolean; editable: boolean; snap: (v: number) => number
  onSelect: () => void; onMove: (x: number, y: number) => void
}) {
  const [x, y, w, h] = z.rect
  const c = ZONE_COLOUR[z.kind] ?? '#64748B'
  const aisle = z.kind === 'main_aisle'
  return (
    <Group x={x} y={y} draggable={editable && selected}
      onDragEnd={e => { e.cancelBubble = true; onMove(snap(e.target.x()), snap(e.target.y())) }}
      onDragStart={e => { e.cancelBubble = true }}>
      <Rect name="zone" width={w} height={h} fill={c} opacity={selected ? 0.14 : aisle ? 0.06 : 0.035}
        stroke={selected ? '#4338CA' : aisle ? undefined : c} strokeWidth={(selected ? 2 : 1) * px} dash={selected ? undefined : [6 * px, 4 * px]}
        onClick={e => { if (!e.evt.shiftKey) { e.cancelBubble = true; onSelect() } }} />
      {labels && !['centre_store', 'perimeter'].includes(z.kind) && (
        <Text x={10 * px} y={8 * px} text={z.name.toUpperCase()} fontSize={10.5 * px} fontStyle="bold" letterSpacing={0.6 * px}
          fill={c} opacity={0.9} listening={false} />
      )}
    </Group>
  )
}

function LandmarkShape({ lm, px, D }: { lm: Landmark; px: number; D: number }) {
  const [x, y, w, h] = lm.rect
  if (lm.kind === 'pillar') return (
    <Group listening={false}>
      <Rect x={x} y={y} width={w} height={h} fill="#334155" />
      <Line points={[x, y, x + w, y + h]} stroke="#64748B" strokeWidth={px} />
    </Group>
  )
  if (lm.kind === 'trolley_bay') return (
    <Group listening={false}>
      <Rect x={x} y={y} width={w} height={h} fill="#F1F5F9" stroke="#94A3B8" strokeWidth={px} dash={[4 * px, 3 * px]} />
      <Text x={x} y={y + h / 2 - 6 * px} width={w} align="center" text="TROLLEYS" fontSize={9 * px} fontStyle="bold" fill="#64748B" />
    </Group>
  )
  const door = { entrance: ['▲ ENTRANCE', '#059669'], exit: ['EXIT ▼', '#DC2626'], stockroom_door: ['STOCKROOM', '#64748B'] }[lm.kind] ?? [lm.name.toUpperCase(), '#64748B']
  const front = y > D / 2
  return (
    <Group listening={false}>
      <Rect x={x} y={y - 120} width={w} height={h + 240} fill="#ffffff" />
      <Rect x={x} y={front ? D - 80 : 0} width={w} height={80} fill={door[1]} opacity={0.85} />
      <Text x={x - 6000} y={front ? D + 8 * px : -20 * px} width={w + 12000} align="center" wrap="none"
        text={door[0]} fontSize={11 * px} fontStyle="bold" fill={door[1]} />
    </Group>
  )
}

interface ShapeProps {
  f: Fixture; tpl?: TemplateDef; sections: Section[]; categories: Record<string, Category>
  selected: boolean; highlighted: boolean; bad: boolean; warn: boolean; showSections: boolean; showLabels: boolean
  px: number; editable: boolean; snapMm: number
  onSelect?: (id: string | null, additive?: boolean) => void
  onDragMove?: (id: string, x: number, y: number) => void
  onDragEnd?: (id: string, x: number, y: number) => void
  onHover: (id: string, on: boolean) => void
}

const KIND_STROKE: Record<string, string> = { multideck: '#2563EB', door_freezer: '#4F46E5', chest_freezer: '#4F46E5' }

const FixtureShape = memo(function FixtureShape(p: ShapeProps) {
  const { f, tpl, sections, categories, px } = p
  const w = f.footprint_w_mm, d = f.footprint_d_mm
  const deptOf = (s: Section) => categories[s.category_code]?.department ?? ''
  const nonMerch = NON_MERCH.has(f.kind)
  const fill = nonMerch ? '#CBD5E1' : sections[0] ? DEPT_COLOUR[deptOf(sections[0])] ?? '#E2E8F0' : '#F1F5F9'
  const kindStroke = KIND_STROKE[f.kind]
  const stroke = p.bad ? CAD.bad : p.warn ? CAD.warn : p.selected ? CAD.select : p.highlighted ? '#6366F1' : kindStroke ?? '#475569'
  const strokeWidth = (p.bad || p.warn || p.selected ? 2.5 : p.highlighted ? 2 : kindStroke ? 1.4 : 1) * px
  const multi = p.showSections && sections.length > 0 && (tpl?.sides.length === 2 || (tpl?.bays_per_side ?? 1) > 1)
  const rects = multi ? sectionFloorRects({ ...f, x_mm: 0, y_mm: 0 }, sections, tpl) : []
  const edge = frontEdge({ ...f, x_mm: 0, y_mm: 0 })
  const tall = d > w * 1.4
  const snap = (v: number) => Math.round(v / p.snapMm) * p.snapMm
  const radius = f.kind === 'produce_bin' ? Math.min(w, d) * 0.18 : f.kind === 'chest_freezer' ? Math.min(w, d) * 0.12 : 0
  // label: constant 10-11 px on screen; only if the fixture is big enough on screen to hold it
  const screenLong = Math.max(w, d) / px, screenShort = Math.min(w, d) / px
  const showLabel = p.showLabels && screenShort > 8 && screenLong > f.code.length * 6.5 + 4
  const fontPx = Math.min(11, Math.max(8, screenShort * 0.6))

  return (
    <Group
      x={f.x_mm}
      y={f.y_mm}
      draggable={p.editable}
      onClick={e => { e.cancelBubble = true; p.onSelect?.(f.id, e.evt.shiftKey || e.evt.ctrlKey || e.evt.metaKey) }}
      onTap={() => p.onSelect?.(f.id)}
      onDragStart={e => { e.cancelBubble = true; if (!p.selected) p.onSelect?.(f.id) }}
      onDragMove={e => {
        e.cancelBubble = true
        const x = snap(e.target.x()), y = snap(e.target.y())
        e.target.position({ x, y })
        p.onDragMove?.(f.id, x, y)
      }}
      onDragEnd={e => { e.cancelBubble = true; p.onDragEnd?.(f.id, snap(e.target.x()), snap(e.target.y())) }}
      onMouseEnter={e => { const c = e.target.getStage()?.container(); if (c) c.style.cursor = p.editable ? 'move' : 'pointer'; p.onHover(f.id, true) }}
      onMouseLeave={e => { const c = e.target.getStage()?.container(); if (c) c.style.cursor = 'default'; p.onHover(f.id, false) }}
    >
      <Rect width={w} height={d} fill={multi ? '#ffffff' : fill} cornerRadius={radius} />
      {rects.map(({ section, rect }) => (
        <Rect key={section.id} x={rect.x} y={rect.y} width={rect.w} height={rect.h}
          fill={DEPT_COLOUR[deptOf(section)] ?? '#E2E8F0'} stroke="#94A3B8" strokeWidth={0.6 * px} />
      ))}
      {/* kind details */}
      {f.kind === 'gondola' && <Line points={w < d ? [w / 2, 0, w / 2, d] : [0, d / 2, w, d / 2]} stroke="#334155" strokeWidth={1.4 * px} />}
      {f.kind === 'door_freezer' && [1, 2, 3].map(i => (
        <Line key={i} points={w > d ? [(w / 4) * i, 0, (w / 4) * i, d] : [0, (d / 4) * i, w, (d / 4) * i]} stroke="#4F46E5" strokeWidth={0.8 * px} />
      ))}
      {f.kind === 'chest_freezer' && <Rect x={Math.min(w, d) * 0.12} y={Math.min(w, d) * 0.12} width={w - Math.min(w, d) * 0.24} height={d - Math.min(w, d) * 0.24}
        stroke="#6366F1" strokeWidth={0.8 * px} dash={[5 * px, 3 * px]} cornerRadius={radius / 2} />}
      {f.kind === 'pallet' && [0.25, 0.5, 0.75].map(t => <Line key={t} points={[w * t, 0, w * t, d]} stroke="#A16207" strokeWidth={0.7 * px} opacity={0.6} />)}
      {f.kind === 'checkout' && <Rect x={w * 0.3} y={d * 0.05} width={w * 0.4} height={d * 0.7} fill="#94A3B8" />}
      {f.kind === 'self_checkout' && <Circle x={w / 2} y={d / 2} radius={Math.min(w, d) * 0.22} fill="#64748B" />}
      {f.kind === 'multideck' && edge && <Line points={edge} stroke="#60A5FA" strokeWidth={4 * px} opacity={0.9} />}
      {edge && f.kind !== 'multideck' && <Line points={edge} stroke="#0F172A" strokeWidth={2.2 * px} opacity={0.55} />}
      <Rect width={w} height={d} stroke={stroke} strokeWidth={strokeWidth} cornerRadius={radius}
        shadowColor={p.selected ? CAD.select : undefined} shadowBlur={p.selected ? 10 : 0} shadowOpacity={0.45} />
      {showLabel && (
        tall
          ? <Text text={f.code} x={w / 2 + (fontPx / 2) * px} y={d / 2} rotation={-90} width={d} offsetX={d / 2}
              align="center" fontSize={fontPx * px} fontStyle="bold" fill="#0F172A" listening={false} />
          : <Text text={f.code} x={0} y={d / 2 - (fontPx / 2) * px} width={w} align="center"
              fontSize={fontPx * px} fontStyle="bold" fill="#0F172A" listening={false} />
      )}
    </Group>
  )
})

function HoverCard({ f, tpl, sections, categories, x, y, maxW }: {
  f: Fixture; tpl?: TemplateDef; sections: Section[]; categories: Record<string, Category>; x: number; y: number; maxW: number
}) {
  const left = x + 280 > maxW ? x - 270 : x + 16
  return (
    <div className="pointer-events-none absolute z-20 w-[255px] rounded-lg border border-line bg-white p-2.5 shadow-xl" style={{ left, top: y + 14 }}>
      <div className="flex items-center gap-2">
        <span className="font-mono text-[13px] font-bold">{f.code}</span>
        <span className="truncate text-[12px] text-ink-2">{tpl?.name ?? f.kind}</span>
      </div>
      <div className="mt-0.5 font-mono text-[10.5px] text-muted">
        {f.footprint_w_mm.toLocaleString('en-IN')} × {f.footprint_d_mm.toLocaleString('en-IN')} mm · {f.rotation_deg}° · {f.temperature}
      </div>
      {sections.length > 0 && (
        <div className="mt-1.5 space-y-0.5">
          {sections.slice(0, 6).sort((a, b) => a.side.localeCompare(b.side) || a.bay_from - b.bay_from).map(s => {
            const c = categories[s.category_code]
            return (
              <div key={s.id} className="flex items-center gap-1.5 text-[11.5px]">
                <span className="size-2.5 shrink-0 rounded-sm" style={{ background: DEPT_COLOUR[c?.department ?? ''] }} />
                <span className="flex-1 truncate">{c?.name ?? s.category_code}</span>
                <span className="font-mono text-[10px] text-muted">{s.side} {s.bay_from}–{s.bay_to}{s.positions ? ` · ${s.positions}` : ''}</span>
              </div>
            )
          })}
        </div>
      )}
      {f.note && <div className="mt-1 text-[11px] text-muted">{f.note}</div>}
    </div>
  )
}

function Rulers({ W, D, scale, pos, size }: { W: number; D: number; scale: number; pos: { x: number; y: number }; size: { width: number; height: number } }) {
  const target = 70 / scale // mm per ~70 px
  const step = [1000, 2000, 5000, 10000, 20000, 50000].find(s => s >= target) ?? 100000
  const xs: number[] = [], ys: number[] = []
  for (let v = 0; v <= W; v += step) xs.push(v)
  for (let v = 0; v <= D; v += step) ys.push(v)
  return (
    <>
      <div className="absolute left-0 right-0 top-0 z-10 border-b border-line bg-white/95" style={{ height: RULER }}>
        {xs.map(v => {
          const sx = pos.x + v * scale
          if (sx < RULER || sx > size.width) return null
          return <div key={v} className="absolute bottom-0 border-l border-slate-400 pl-1 font-mono text-[9.5px] leading-none text-muted" style={{ left: sx, height: 12 }}>{v / 1000}m</div>
        })}
      </div>
      <div className="absolute bottom-0 left-0 top-0 z-10 border-r border-line bg-white/95" style={{ width: RULER }}>
        {ys.map(v => {
          const sy = pos.y + v * scale
          if (sy < RULER || sy > size.height) return null
          return <div key={v} className="absolute right-0 border-t border-slate-400 pr-0.5 pt-0.5 text-right font-mono text-[9px] leading-none text-muted" style={{ top: sy, width: RULER }}>{v / 1000}</div>
        })}
      </div>
      <div className="absolute left-0 top-0 z-10 border-b border-r border-line bg-white" style={{ width: RULER, height: RULER }} />
    </>
  )
}

function Minimap({ doc, fixtures, categories, sectionsByFixture, view, size, onJump }: {
  doc: LayoutDoc; fixtures: Fixture[]; categories: Record<string, Category>; sectionsByFixture: Map<string, Section[]>
  view: { scale: number; x: number; y: number }; size: { width: number; height: number }; onJump: (x: number, y: number) => void
}) {
  const W = doc.store.width_mm, D = doc.store.depth_mm
  const mw = 200, mh = Math.round(mw * D / W)
  const vx = (RULER - view.x) / view.scale, vy = (RULER - view.y) / view.scale
  const vw = (size.width - RULER) / view.scale, vh = (size.height - RULER) / view.scale
  return (
    <div className="absolute bottom-3 right-3 z-10 rounded-lg border border-line bg-white/95 p-1.5 shadow-lg">
      <div className="mb-1 flex justify-between px-0.5 text-[9.5px] font-semibold uppercase tracking-wider text-muted"><span>Overview</span><span>{W / 1000} × {D / 1000} m</span></div>
      <svg width={mw} height={mh} viewBox={`0 0 ${W} ${D}`} className="cursor-pointer"
        onClick={e => {
          const r = (e.currentTarget as SVGSVGElement).getBoundingClientRect()
          onJump(((e.clientX - r.left) / mw) * W, ((e.clientY - r.top) / mh) * D)
        }}>
        <rect width={W} height={D} fill="#fff" stroke="#334155" strokeWidth={W / 150} />
        {fixtures.map(f => {
          const s = sectionsByFixture.get(f.id)?.[0]
          const fill = NON_MERCH.has(f.kind) ? '#CBD5E1' : s ? DEPT_COLOUR[categories[s.category_code]?.department ?? ''] ?? '#CBD5E1' : '#E2E8F0'
          return <rect key={f.id} x={f.x_mm} y={f.y_mm} width={f.footprint_w_mm} height={f.footprint_d_mm} fill={fill} stroke="#64748B" strokeWidth={W / 900} />
        })}
        <rect x={vx} y={vy} width={vw} height={vh} fill="#4338CA" fillOpacity={0.08} stroke="#4338CA" strokeWidth={W / 220} />
      </svg>
    </div>
  )
}
