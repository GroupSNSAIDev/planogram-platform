"""Store execution pack (spec FR-22, 11.6): what store teams need to build the shelves.

  floor_pdf        A3 top view of the store to scale: every fixture with its code, zones, doors, legend, scale bar;
                   then a fixture index (code, type, sections and categories, products placed).
  planogram_pdf    one page per planned section: the elevation to scale with the real product pictures, shelf
                   heights, and a numbered list of what goes where (product, GTIN, facings, units, size).
  execution_xlsx   Summary, Sections, and Placements (one row per shelf position, with picture, quantities,
                   cases to fill and dimensions), filterable by section, bay and shelf.
"""
from __future__ import annotations

import io
import math
from datetime import datetime
from typing import Any

from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from PIL import Image as PILImage
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A3, A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas
from sqlalchemy.orm import Session

from . import models as m_
from . import services as svc
from sqlalchemy import select as _select
from .engines.context import build_context
from .engines.geometry import units
from .imports import MEDIA_DIR

DEPT_COLOUR = {
    "Fresh": "#BBF7D0", "Dairy & chilled": "#BFDBFE", "Beverages": "#A5F3FC", "Frozen": "#C7D2FE", "Staples": "#FDE68A",
    "Packaged food": "#FED7AA", "Personal care": "#FBCFE8", "Home care": "#DDD6FE", "General merchandise": "#E5E7EB",
    "Impulse": "#FCA5A5", "Promotions": "#D9F99D",
}
NON_MERCH = {"checkout", "self_checkout", "service_desk"}
INK, MUTED, INDIGO, LINE = HexColor("#0F172A"), HexColor("#64748B"), HexColor("#4338CA"), HexColor("#CBD5E1")


# ----------------------------------------------------------------------------- data

def snapshot(s: Session, store_code: str, fixture_code: str | None = None, section_id: str | None = None,
             planned_only: bool = True) -> dict[str, Any]:
    store = svc.get_store(s, store_code)
    layout = svc.load_layout(s, store)
    products, stats, cats = svc.load_products(s), svc.load_stats(s, store.id), svc.load_categories(s)
    templates = svc.load_templates(s)
    sections = []
    for sec in sorted(layout["sections"].values(), key=lambda x: _natural(layout["fixtures"][x["fixture_id"]]["code"]) + [x["side"], x["bay_from"]]):
        fx = layout["fixtures"][sec["fixture_id"]]
        if fixture_code and fx["code"] != fixture_code:
            continue
        if section_id and sec["id"] != section_id:
            continue
        ctx = build_context(layout, sec["id"], products, stats, cats)
        if not ctx["surfaces"]:
            continue
        pg = s.scalar(_select(m_.Planogram).where(m_.Planogram.section_id == sec["id"]))
        positions = svc.load_positions(s, pg.id) if pg else {}
        if planned_only and not positions:
            continue
        sections.append({"section": sec, "fixture": fx, "ctx": ctx, "positions": positions, "category": cats.get(sec["category_code"], {}),
                         "planogram": pg})
    return {"store": store, "layout": layout, "products": products, "stats": stats, "categories": cats, "templates": templates,
            "sections": sections}


def _natural(code: str) -> list:
    import re
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", code)]


def _image_path(product: dict[str, Any]) -> str | None:
    if product.get("image"):
        p = MEDIA_DIR / product["image"]
        if p.exists():
            return str(p)
    return None


def _band(h: int) -> str:
    return "top" if h > 1600 else "eye" if h >= 1200 else "waist" if h >= 800 else "knee" if h >= 400 else "floor"


# ----------------------------------------------------------------------------- floor plan PDF

def _section_rects(f: dict[str, Any], sections: list[dict[str, Any]], tpl: dict[str, Any] | None) -> list[tuple[dict, tuple]]:
    """Python port of apps/web/src/features/floor/floorGeometry.ts sectionFloorRects."""
    out = []
    bays = (tpl or {}).get("bays_per_side", 1) or 1
    sides = (tpl or {}).get("sides", [])
    rot = f["rotation_deg"] % 360
    along_x = rot in (0, 180)
    length = f["footprint_w_mm"] if along_x else f["footprint_d_mm"]
    bay_len = length / bays
    faces = (f.get("faces") or "").split("/")
    for sc in sections:
        a0, a1 = (sc["bay_from"] - 1) * bay_len, sc["bay_to"] * bay_len
        if rot in (180, 270):
            a0, a1 = length - a1, length - a0
        if along_x:
            x, y, w, h = f["x_mm"] + a0, f["y_mm"], a1 - a0, f["footprint_d_mm"]
        else:
            x, y, w, h = f["x_mm"], f["y_mm"] + a0, f["footprint_w_mm"], a1 - a0
        if len(sides) == 2:
            d = faces[0] if sc["side"] == "A" else (faces[1] if len(faces) > 1 else "")
            if along_x:
                h /= 2
                y = y + h if d == "S" else y
            else:
                w /= 2
                x = x + w if d == "E" else x
        out.append((sc, (x, y, w, h)))
    return out


def floor_pdf(s: Session, store_code: str) -> bytes:
    snap = snapshot(s, store_code, planned_only=False)
    layout, cats, templates = snap["layout"], snap["categories"], snap["templates"]
    store = layout["store"]
    W, D = store["width_mm"], store["depth_mm"]
    buf = io.BytesIO()
    page = landscape(A3)
    c = Canvas(buf, pagesize=page)
    c.setTitle(f"{store['code']} floor plan")
    pw, ph = page
    m = 28
    head = 54
    legend_h = 40
    avail_w, avail_h = pw - 2 * m, ph - 2 * m - head - legend_h
    k = min(avail_w / W, avail_h / D)
    ox = m + (avail_w - W * k) / 2
    oy = ph - m - head - (avail_h - D * k) / 2  # top of the floor in PDF coordinates
    X = lambda v: ox + v * k  # noqa: E731
    Y = lambda v: oy - v * k  # noqa: E731

    _title(c, pw, ph, m, f"{store['code']} · {store['name']}", f"Floor plan · {W / 1000:g} × {D / 1000:g} m · "
           f"{round(W * D / 1e6 * 10.764):,} sq ft · {len(layout['fixtures'])} fixtures · {len(layout['sections'])} sections")
    # zones
    zc = {"entrance": "#059669", "checkout": "#D97706", "chilled": "#2563EB", "frozen": "#4F46E5", "main_aisle": "#6366F1",
          "centre_store": "#64748B", "perimeter": "#A16207", "promotion": "#65A30D"}
    for z in layout["zones"]:
        x, y, w, h = z["rect"]
        col = HexColor(zc.get(z["kind"], "#64748B"))
        c.setFillColor(col, alpha=0.06 if z["kind"] == "main_aisle" else 0.035)
        c.setStrokeColor(col, alpha=0.6)
        c.setLineWidth(0.4)
        c.setDash(3, 2)
        c.rect(X(x), Y(y + h), w * k, h * k, fill=1, stroke=0 if z["kind"] == "main_aisle" else 1)
        c.setDash()
        if z["kind"] not in ("centre_store", "perimeter"):
            c.setFillColor(col, alpha=0.9)
            c.setFont("Helvetica-Bold", 6.5)
            c.drawString(X(x) + 3, Y(y) - 8, z["name"].upper())
    # floor outline
    c.setFillColor(white, alpha=0)
    c.setStrokeColor(INK)
    c.setLineWidth(2)
    c.rect(X(0), Y(D), W * k, D * k, fill=0, stroke=1)
    # landmarks
    for lm in layout["landmarks"]:
        x, y, w, h = lm["rect"]
        if lm["kind"] == "pillar":
            c.setFillColor(HexColor("#334155"), alpha=1)
            c.rect(X(x), Y(y + h), max(w * k, 1.5), max(h * k, 1.5), fill=1, stroke=0)
        elif lm["kind"] in ("entrance", "exit", "stockroom_door"):
            col = {"entrance": "#059669", "exit": "#DC2626"}.get(lm["kind"], "#64748B")
            c.setFillColor(white, alpha=1)
            c.rect(X(x), Y(y + h) - 1.5, w * k, h * k + 3, fill=1, stroke=0)
            c.setFillColor(HexColor(col), alpha=1)
            c.setFont("Helvetica-Bold", 8)
            label = {"entrance": "ENTRANCE", "exit": "EXIT", "stockroom_door": "STOCKROOM"}[lm["kind"]]
            ty = Y(y + h) - 10 if y > D / 2 else Y(y) + 4
            c.drawCentredString(X(x + w / 2), ty, label)
        elif lm["kind"] == "trolley_bay":
            c.setFillColor(HexColor("#F1F5F9"), alpha=1)
            c.setStrokeColor(HexColor("#94A3B8"))
            c.rect(X(x), Y(y + h), w * k, h * k, fill=1, stroke=1)
    # fixtures
    by_fx: dict[str, list] = {}
    for sc in layout["sections"].values():
        by_fx.setdefault(sc["fixture_id"], []).append(sc)
    counts = {}
    for sec in snap["sections"]:
        counts[sec["fixture"]["id"]] = counts.get(sec["fixture"]["id"], 0) + len(sec["positions"])
    for f in sorted(layout["fixtures"].values(), key=lambda f: f["code"]):
        x, y, w, h = f["x_mm"], f["y_mm"], f["footprint_w_mm"], f["footprint_d_mm"]
        secs = by_fx.get(f["id"], [])
        tpl = templates.get(f["template_code"])
        dept = cats.get(secs[0]["category_code"], {}).get("department") if secs else None
        fill = "#CBD5E1" if f["kind"] in NON_MERCH else DEPT_COLOUR.get(dept or "", "#F1F5F9")
        c.setFillColor(HexColor(fill), alpha=1)
        c.setStrokeColor(HexColor("#475569"))
        c.setLineWidth(0.4)
        c.rect(X(x), Y(y + h), w * k, h * k, fill=1, stroke=1)
        if tpl and (len(tpl.get("sides", [])) == 2 or tpl.get("bays_per_side", 1) > 1):
            for sc, (sx, sy, sw, sh) in _section_rects(f, secs, tpl):
                c.setFillColor(HexColor(DEPT_COLOUR.get(cats.get(sc["category_code"], {}).get("department", ""), "#E2E8F0")), alpha=1)
                c.setStrokeColor(HexColor("#94A3B8"))
                c.setLineWidth(0.25)
                c.rect(X(sx), Y(sy + sh), sw * k, sh * k, fill=1, stroke=1)
            c.setStrokeColor(HexColor("#334155"))
            c.setLineWidth(0.4)
            c.rect(X(x), Y(y + h), w * k, h * k, fill=0, stroke=1)
        # label sized to the fixture
        long_pt, short_pt = max(w, h) * k, min(w, h) * k
        size = min(7.5, short_pt * 0.62, (long_pt - 2) / (0.6 * max(1, len(f["code"]))))
        if size >= 2.4:
            c.setFillColor(INK, alpha=1)
            c.setFont("Helvetica-Bold", size)
            cx, cy = X(x + w / 2), Y(y + h / 2)
            if h > w * 1.4:
                c.saveState()
                c.translate(cx + size * 0.35, cy)
                c.rotate(90)
                c.drawCentredString(0, 0, f["code"])
                c.restoreState()
            else:
                c.drawCentredString(cx, cy - size * 0.35, f["code"])
    # scale bar and legend
    _scale_bar(c, X(0), Y(D) - 22, k)
    lx, ly = m, m + 8
    c.setFont("Helvetica", 7.5)
    for dept, col in DEPT_COLOUR.items():
        c.setFillColor(HexColor(col), alpha=1)
        c.setStrokeColor(HexColor("#94A3B8"))
        c.rect(lx, ly, 9, 7, fill=1, stroke=1)
        c.setFillColor(INK)
        c.drawString(lx + 12, ly + 1, dept)
        lx += 18 + c.stringWidth(dept, "Helvetica", 7.5) + 6
    c.showPage()

    # fixture index
    rows = []
    for f in sorted(layout["fixtures"].values(), key=lambda f: _natural(f["code"])):
        secs = sorted(by_fx.get(f["id"], []), key=lambda s: (s["side"], s["bay_from"]))
        cat_txt = "; ".join(f"{s['side']} {s['bay_from']}-{s['bay_to']} {cats.get(s['category_code'], {}).get('name', s['category_code'])}" for s in secs)
        rows.append([f["code"], (templates.get(f["template_code"]) or {}).get("name", f["kind"]), f"{f['x_mm'] / 1000:.1f}, {f['y_mm'] / 1000:.1f}",
                     f["temperature"], cat_txt or "-", str(counts.get(f["id"], 0) or "")])
    _table_pages(c, page, m, f"{store['code']} · Fixture index", ["Fixture", "Type", "x, y (m)", "Temp.", "Sections and categories", "Placed"],
                 [52, 150, 60, 50, 680, 40], rows)
    c.save()
    return buf.getvalue()


def _title(c: Canvas, pw: float, ph: float, m: float, title: str, sub: str) -> None:
    c.setFillColor(INDIGO)
    c.roundRect(m, ph - m - 22, 22, 22, 4, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(m + 11, ph - m - 14.5, "PL")
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(m + 30, ph - m - 11, title)
    c.setFont("Helvetica", 9)
    c.setFillColor(MUTED)
    c.drawString(m + 30, ph - m - 23, sub)
    c.drawRightString(pw - m, ph - m - 11, f"Generated {datetime.now():%d %b %Y %H:%M}")
    c.drawRightString(pw - m, ph - m - 23, "Planogram platform · POC")


def _scale_bar(c: Canvas, x: float, y: float, k: float) -> None:
    for metres in (1, 2, 5, 10, 20):
        if metres * 1000 * k >= 40:
            break
    length = metres * 1000 * k
    c.setStrokeColor(INK)
    c.setLineWidth(1.2)
    c.line(x, y, x + length, y)
    c.line(x, y - 3, x, y + 3)
    c.line(x + length, y - 3, x + length, y + 3)
    c.setFont("Helvetica", 7)
    c.setFillColor(INK)
    c.drawString(x + length + 4, y - 2.5, f"{metres} m")


def _table_pages(c: Canvas, page: tuple, m: float, title: str, headers: list[str], widths: list[float], rows: list[list[str]],
                 font: float = 7.5) -> None:
    pw, ph = page
    row_h = font + 4.5
    y = 0.0
    first = True
    for i, r in enumerate(rows):
        if first or y < m + row_h:
            if not first:
                c.showPage()
            first = False
            c.setFont("Helvetica-Bold", 13)
            c.setFillColor(INK)
            c.drawString(m, ph - m - 12, title + ("" if i == 0 else " (continued)"))
            y = ph - m - 32
            c.setFillColor(HexColor("#EEF2FF"))
            c.rect(m, y - 3, sum(widths), row_h, fill=1, stroke=0)
            c.setFillColor(INDIGO)
            c.setFont("Helvetica-Bold", font)
            x = m
            for h, w in zip(headers, widths):
                c.drawString(x + 2, y, h)
                x += w
            y -= row_h
        c.setFont("Helvetica", font)
        c.setFillColor(INK)
        x = m
        for v, w in zip(r, widths):
            c.drawString(x + 2, y, _fit(c, str(v), w - 4, font))
            x += w
        c.setStrokeColor(HexColor("#E2E8F0"))
        c.setLineWidth(0.3)
        c.line(m, y - 3, m + sum(widths), y - 3)
        y -= row_h
    c.showPage()


def _fit(c: Canvas, text: str, width: float, size: float, font: str = "Helvetica") -> str:
    text = text.encode("latin-1", "replace").decode("latin-1")
    if c.stringWidth(text, font, size) <= width:
        return text
    while text and c.stringWidth(text + "…", font, size) > width:
        text = text[:-1]
    return text + "…"


# ----------------------------------------------------------------------------- planogram PDF

def planogram_pdf(s: Session, store_code: str, fixture_code: str | None = None, section_id: str | None = None) -> bytes:
    snap = snapshot(s, store_code, fixture_code, section_id)
    store = snap["layout"]["store"]
    buf = io.BytesIO()
    page = landscape(A4)
    c = Canvas(buf, pagesize=page)
    c.setTitle(f"{store['code']} planograms")
    pw, ph = page
    m = 24
    if not snap["sections"]:
        _title(c, pw, ph, m, f"{store['code']} · Planograms", "No planned sections in this selection yet. Run auto-fill or place products first.")
        c.showPage()
        c.save()
        return buf.getvalue()
    # cover with contents
    _title(c, pw, ph, m, f"{store['code']} · {store['name']}", f"Planogram pack · {len(snap['sections'])} sections"
           + (f" · fixture {fixture_code}" if fixture_code else ""))
    c.setFont("Helvetica", 8)
    y = ph - m - 50
    col = 0
    for i, sec in enumerate(snap["sections"], start=1):
        if y < m + 10:
            col += 1
            y = ph - m - 50
            if col > 2:
                c.showPage()
                col, y = 0, ph - m - 30
        x = m + col * 265
        c.setFillColor(INK)
        c.drawString(x, y, f"{i:>3}.  {sec['section']['code']}")
        c.setFillColor(MUTED)
        c.drawString(x + 95, y, _fit(c, f"{sec['category'].get('name', '')} · {len(sec['positions'])} products", 160, 8))
        y -= 11
    c.showPage()
    for i, sec in enumerate(snap["sections"], start=1):
        _section_page(c, page, m, store, sec, snap["products"], snap["stats"], i, len(snap["sections"]))
    c.save()
    return buf.getvalue()


def _section_page(c: Canvas, page, m, store, sec, products, stats, n, total) -> None:
    pw, ph = page
    section, fixture, ctx = sec["section"], sec["fixture"], sec["ctx"]
    positions = sorted(sec["positions"].values(), key=lambda p: (ctx["surface_by_id"].get(p["surface_id"], {}).get("bay_idx", 0),
                                                                -ctx["surface_by_id"].get(p["surface_id"], {}).get("height_from_floor_mm", 0), p["seq"]))
    pg = sec["planogram"]
    _title(c, pw, ph, m, f"{section['code']} · {sec['category'].get('name', section['category_code'])}",
           f"{store['code']} · fixture {fixture['code']} side {section['side']} · bays {section['bay_from']}-{section['bay_to']} · "
           f"{fixture['temperature']} · {len(positions)} products · score {pg.score if pg and pg.score is not None else '-'} · "
           f"page {n} of {total}")
    # elevation
    bays = sorted({sf["bay_idx"] for sf in ctx["surfaces"]})
    bay_w = {b: max(sf["width_mm"] for sf in ctx["surfaces"] if sf["bay_idx"] == b) for b in bays}
    offset, acc = {}, 0
    for b in bays:
        offset[b] = acc
        acc += bay_w[b]
    total_w = acc
    H = max(sf["bay_height_mm"] for sf in ctx["surfaces"]) + 250
    top = ph - m - 40
    elev_h = ph * 0.52
    k = min((pw - 2 * m - 30) / total_w, elev_h / H)
    ox = m + 30 + ((pw - 2 * m - 30) - total_w * k) / 2
    base = top - elev_h + (elev_h - H * k)
    X = lambda v: ox + v * k  # noqa: E731
    Yh = lambda h: base + h * k  # noqa: E731
    # eye band, bays, shelves
    c.setFillColor(HexColor("#EEF2FF"), alpha=0.8)
    c.rect(X(0), Yh(1200), total_w * k, 400 * k, fill=1, stroke=0)
    c.setFont("Helvetica", 6)
    c.setFillColor(MUTED)
    for h in range(0, int(H), 250 if H * k > 150 else 500):
        c.drawRightString(X(0) - 4, Yh(h) - 2, str(h))
    for b in bays:
        c.setStrokeColor(HexColor("#94A3B8"))
        c.setLineWidth(0.6)
        c.setFillColor(white, alpha=0)
        c.rect(X(offset[b]), Yh(0), bay_w[b] * k, (H - 250) * k, fill=0, stroke=1)
        c.setFillColor(INK, alpha=1)
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(X(offset[b] + bay_w[b] / 2), Yh(0) - 9, f"Bay {b}")
    for sf in ctx["surfaces"]:
        c.setFillColor(HexColor("#334155"), alpha=1)
        c.rect(X(offset[sf["bay_idx"]]), Yh(sf["height_from_floor_mm"]) - 1.2, sf["width_mm"] * k, 1.6, fill=1, stroke=0)
        if sf["bay_idx"] == bays[0]:
            c.setFont("Helvetica", 5.5)
            c.setFillColor(MUTED)
            c.drawString(X(0) + 1, Yh(sf["height_from_floor_mm"]) - 6.5, f"S{sf['level']} {sf['height_from_floor_mm']} mm")
    # products with pictures, numbered
    numbers: dict[str, int] = {}
    for idx, p in enumerate(positions, start=1):
        numbers[p["id"]] = idx
        sf = ctx["surface_by_id"].get(p["surface_id"])
        prod = products.get(p["product_id"])
        if not sf or not prod:
            continue
        img = _image_path(prod)
        x0 = offset[sf["bay_idx"]] + p["x_mm"]
        for i in range(p["facings_wide"]):
            for j in range(p["facings_high"]):
                fx, fy = X(x0 + i * prod["width_mm"]), Yh(sf["height_from_floor_mm"] + j * prod["height_mm"])
                fw, fh = prod["width_mm"] * k, prod["height_mm"] * k
                if img:
                    try:
                        c.drawImage(img, fx, fy, fw, fh, preserveAspectRatio=False)
                    except Exception:  # noqa: BLE001
                        img = None
                if not img:
                    c.setFillColor(HexColor(prod.get("colour") or "#CBD5E1"), alpha=0.35)
                    c.rect(fx, fy, fw, fh, fill=1, stroke=0)
                c.setStrokeColor(white, alpha=1)
                c.setLineWidth(0.3)
                c.rect(fx, fy, fw, fh, fill=0, stroke=1)
        # number badge
        bx, by = X(x0) + 1, Yh(sf["height_from_floor_mm"] + prod["height_mm"] * p["facings_high"]) - 7
        c.setFillColor(INDIGO, alpha=0.92)
        c.roundRect(bx, by, 9 + 3 * (idx >= 10), 6.5, 1.5, fill=1, stroke=0)
        c.setFillColor(white, alpha=1)
        c.setFont("Helvetica-Bold", 5)
        c.drawString(bx + 1.5, by + 1.7, str(idx))
    # list
    rows = []
    for p in positions:
        sf = ctx["surface_by_id"].get(p["surface_id"])
        prod = products.get(p["product_id"], {})
        rows.append([str(numbers[p["id"]]), f"B{sf['bay_idx']} S{sf['level']}" if sf else "", str(p["seq"] + 1), prod.get("name", ""),
                     prod.get("brand", ""), prod.get("gtin", ""), f"{p['facings_wide']}x{p['facings_high']}x{p['facings_deep']}",
                     str(units(p)), f"{prod.get('width_mm')}x{prod.get('height_mm')}x{prod.get('depth_mm')}",
                     "LOCK" if p.get("locked") else ""])
    headers = ["#", "Shelf", "Seq", "Product", "Brand", "GTIN", "Facings", "Units", "W x H x D mm", ""]
    widths = [14, 32, 20, 150, 62, 64, 40, 28, 62, 20]
    list_top = top - elev_h - 22
    cols = 2
    fit = ((pw - 2 * m - 14) / cols) / sum(widths)   # two columns side by side across the page
    widths = [w * fit for w in widths]
    col_w = sum(widths)
    per_col = max(1, int((list_top - m) // 9.5))
    i = 0
    while i < len(rows):
        for col in range(cols):
            x = m + col * (col_w + 14)
            y = list_top
            c.setFont("Helvetica-Bold", 6.5)
            c.setFillColor(INDIGO)
            xx = x
            for h, w in zip(headers, widths):
                c.drawString(xx, y, h)
                xx += w
            y -= 9.5
            c.setFont("Helvetica", 6.5)
            for r in rows[i:i + per_col - 1]:
                c.setFillColor(INK)
                xx = x
                for v, w in zip(r, widths):
                    c.drawString(xx, y, _fit(c, v, w - 3, 6.5))
                    xx += w
                y -= 9.5
            i += per_col - 1
            if i >= len(rows):
                break
        if i < len(rows):
            c.showPage()
            list_top = ph - m - 20
            per_col = max(1, int((list_top - m) // 9.5))
            c.setFont("Helvetica-Bold", 10)
            c.setFillColor(INK)
            c.drawString(m, ph - m - 10, f"{section['code']} · list continued")
    c.showPage()


# ----------------------------------------------------------------------------- execution workbook

def execution_xlsx(s: Session, store_code: str, fixture_code: str | None = None, section_id: str | None = None) -> bytes:
    snap = snapshot(s, store_code, fixture_code, section_id)
    store = snap["layout"]["store"]
    products, stats = snap["products"], snap["stats"]
    wb = Workbook()
    head_fill = PatternFill("solid", fgColor="4338CA")
    bold_white = Font(bold=True, color="FFFFFF")

    def header(ws, cols: list[tuple[str, int]]) -> None:
        for i, (h, w) in enumerate(cols, start=1):
            cell = ws.cell(row=1, column=i, value=h)
            cell.fill, cell.font = head_fill, bold_white
            cell.alignment = Alignment(vertical="center", wrap_text=True)
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.row_dimensions[1].height = 30
        ws.freeze_panes = "A2"

    # Summary
    ws = wb.active
    ws.title = "Summary"
    ws["A1"] = f"{store['code']} · {store['name']}"
    ws["A1"].font = Font(bold=True, size=16)
    ws["A2"] = f"Store execution workbook · generated {datetime.now():%d %b %Y %H:%M}" + (f" · fixture {fixture_code}" if fixture_code else "")
    ws["A2"].font = Font(color="64748B")
    total_pos = sum(len(x["positions"]) for x in snap["sections"])
    total_units = sum(units(p) for x in snap["sections"] for p in x["positions"].values())
    info = [("Sections planned", len(snap["sections"])), ("Shelf positions", total_pos), ("Units on shelf", total_units),
            ("Distinct products", len({p["product_id"] for x in snap["sections"] for p in x["positions"].values()}))]
    for i, (k, v) in enumerate(info, start=4):
        ws.cell(row=i, column=1, value=k).font = Font(bold=True)
        ws.cell(row=i, column=2, value=v)
    ws.cell(row=9, column=1, value="How to use").font = Font(bold=True, color="4338CA")
    ws.cell(row=10, column=1, value="Placements lists every shelf position in build order: fixture, side, bay (1 = back of the store), "
                                    "shelf (1 = lowest), then left to right. Facings = packs side by side x stacked x behind each other; "
                                    "Units = packs on the shelf; Cases = cases to open to fill it.")
    ws.cell(row=10, column=1).alignment = Alignment(wrap_text=True, vertical="top")
    ws.merge_cells("A10:H13")
    ws.column_dimensions["A"].width = 24
    ws.column_dimensions["B"].width = 14

    # Sections
    ss = wb.create_sheet("Sections")
    cols = [("Section", 14), ("Fixture", 10), ("Side", 6), ("Bays", 8), ("Category", 26), ("Department", 18), ("Temperature", 11),
            ("Positions", 10), ("Facings", 9), ("Units", 9), ("Shelf used mm", 13), ("Shelf length mm", 14), ("Fill %", 8),
            ("Score", 8), ("Hard breaks", 10)]
    header(ss, cols)
    for r, x in enumerate(snap["sections"], start=2):
        sec, ctx = x["section"], x["ctx"]
        pos = list(x["positions"].values())
        used = sum(products[p["product_id"]]["width_mm"] * p["facings_wide"] for p in pos if p["product_id"] in products)
        cap = sum(sf["width_mm"] for sf in ctx["surfaces"])
        pg = x["planogram"]
        vals = [sec["code"], x["fixture"]["code"], sec["side"], f"{sec['bay_from']}-{sec['bay_to']}", x["category"].get("name"),
                x["category"].get("department"), x["fixture"]["temperature"], len(pos), sum(p["facings_wide"] * p["facings_high"] for p in pos),
                sum(units(p) for p in pos), used, cap, round(100 * min(used, cap) / cap, 1) if cap else 0,
                pg.score if pg else None, pg.hard_breaks if pg else None]
        for col, v in enumerate(vals, start=1):
            ss.cell(row=r, column=col, value=v)
    ss.auto_filter.ref = f"A1:{get_column_letter(len(cols))}{max(2, len(snap['sections']) + 1)}"

    # Placements
    ps = wb.create_sheet("Placements")
    cols = [("Picture", 9), ("Section", 13), ("Category", 20), ("Fixture", 9), ("Side", 5), ("Bay", 5), ("Shelf", 6),
            ("Shelf height mm", 9), ("Band", 7), ("Order (left to right)", 8), ("From left mm", 9), ("SKU", 12), ("GTIN", 15),
            ("Product", 34), ("Brand", 16), ("Pack size", 10), ("Width mm", 8), ("Height mm", 8), ("Depth mm", 8),
            ("Facings wide", 8), ("Facings high", 8), ("Facings deep", 8), ("Units on shelf", 9), ("Case pack", 8), ("Cases to fill", 8),
            ("Sells / day", 8), ("Days of supply", 8), ("Temperature", 10), ("Locked", 7), ("Why it is here", 60)]
    header(ps, cols)
    thumbs: dict[str, bytes] = {}
    r = 2
    for x in snap["sections"]:
        sec, ctx = x["section"], x["ctx"]
        order = sorted(x["positions"].values(), key=lambda p: (ctx["surface_by_id"].get(p["surface_id"], {}).get("bay_idx", 0),
                                                              ctx["surface_by_id"].get(p["surface_id"], {}).get("level", 0), p["seq"]))
        for p in order:
            sf = ctx["surface_by_id"].get(p["surface_id"])
            prod = products.get(p["product_id"])
            if not sf or not prod:
                continue
            u = units(p)
            upd = stats.get(prod["id"], {}).get("units_per_day", 0.0)
            vals = [None, sec["code"], x["category"].get("name"), x["fixture"]["code"], sec["side"], sf["bay_idx"], sf["level"],
                    sf["height_from_floor_mm"], _band(sf["height_from_floor_mm"]), p["seq"] + 1, p["x_mm"], prod["sku"], prod["gtin"],
                    prod["name"], prod["brand"], prod.get("pack_size"), prod["width_mm"], prod["height_mm"], prod["depth_mm"],
                    p["facings_wide"], p["facings_high"], p["facings_deep"], u, prod.get("case_pack") or 1,
                    math.ceil(u / (prod.get("case_pack") or 1)), round(upd, 1), round(u / upd, 1) if upd else None,
                    prod["temperature"], "yes" if p.get("locked") else "", p.get("reason")]
            for col, v in enumerate(vals, start=1):
                ps.cell(row=r, column=col, value=v).alignment = Alignment(vertical="center", wrap_text=col in (14, 30))
            ps.row_dimensions[r].height = 40
            path = _image_path(prod)
            if path:
                data = thumbs.get(path)
                if data is None:
                    im = PILImage.open(path).convert("RGB")
                    im.thumbnail((96, 96))
                    b = io.BytesIO()
                    im.save(b, "JPEG", quality=72)
                    data = thumbs[path] = b.getvalue()
                xi = XLImage(io.BytesIO(data))
                ratio = min(48 / xi.width, 50 / xi.height)
                xi.width, xi.height = int(xi.width * ratio), int(xi.height * ratio)
                ps.add_image(xi, f"A{r}")
            r += 1
    ps.auto_filter.ref = f"A1:{get_column_letter(len(cols))}{max(2, r - 1)}"

    # Products to pick (one row per product: total units across the selection)
    pk = wb.create_sheet("Pick list")
    header(pk, [("SKU", 12), ("GTIN", 15), ("Product", 36), ("Brand", 16), ("Pack size", 10), ("Locations", 9), ("Units", 9),
                ("Case pack", 9), ("Cases", 8), ("Temperature", 11)])
    agg: dict[str, dict[str, Any]] = {}
    for x in snap["sections"]:
        for p in x["positions"].values():
            a = agg.setdefault(p["product_id"], {"units": 0, "locations": 0})
            a["units"] += units(p)
            a["locations"] += 1
    for r2, (pid, a) in enumerate(sorted(agg.items(), key=lambda t: products.get(t[0], {}).get("name", "")), start=2):
        prod = products.get(pid, {})
        cp = prod.get("case_pack") or 1
        for col, v in enumerate([prod.get("sku"), prod.get("gtin"), prod.get("name"), prod.get("brand"), prod.get("pack_size"),
                                 a["locations"], a["units"], cp, math.ceil(a["units"] / cp), prod.get("temperature")], start=1):
            pk.cell(row=r2, column=col, value=v)
    pk.auto_filter.ref = f"A1:J{max(2, len(agg) + 1)}"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


__all__ = ["execution_xlsx", "floor_pdf", "planogram_pdf"]
_ = A3, A4  # page sizes used above
