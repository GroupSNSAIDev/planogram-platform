"""Product workbook imports: stage and validate an upload, then publish the good rows (spec 9, FR-01/02/05).

Nothing bad blocks good rows: rows with errors stay in the report and are not published.
Pictures are stored under media/products/<SKU>.jpg (512 px, JPEG) and served at /api/media/...
"""
from __future__ import annotations

import io
import os
import shutil
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m
from .catalog_excel import ImportRow, build_workbook, parse_workbook, quality_score

MEDIA_DIR = Path(os.environ.get("PLANOGRAM_MEDIA", Path(__file__).resolve().parents[1] / "media"))
PRODUCT_FIELDS = ["sku", "gtin", "name", "brand", "category", "width_mm", "height_mm", "depth_mm", "weight_g", "pack_size",
                  "case_pack", "temperature", "dims_source", "dims_verified", "can_stack", "max_stack", "liquid", "fragile",
                  "age_restricted", "hazardous", "safety_reviewed", "price", "status"]


def fetch_url(url: str) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "PlanogramPOC/0.2 (product import)"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read(15_000_000)
    except Exception:  # noqa: BLE001 - a bad URL becomes an I-001 warning
        return None


def _save_image(data: bytes, path: Path) -> str:
    """Normalise to RGB JPEG, longest side 512 px. Returns the dominant colour as #rrggbb."""
    path.parent.mkdir(parents=True, exist_ok=True)
    im = Image.open(io.BytesIO(data))
    if im.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", im.size, "white")
        rgba = im.convert("RGBA")
        bg.paste(rgba, mask=rgba.split()[-1])
        im = bg
    im = im.convert("RGB")
    im.thumbnail((512, 512))
    im.save(path, "JPEG", quality=86)
    r, g, b = im.resize((1, 1), Image.Resampling.BOX).getpixel((0, 0))
    return f"#{r:02x}{g:02x}{b:02x}"


def _categories(s: Session) -> dict[str, dict[str, Any]]:
    return {c.code: {"code": c.code, "department": c.department, "name": c.name, "temperature": c.temperature}
            for c in s.scalars(select(m.Category))}


def stage(s: Session, filename: str, data: bytes, images_zip: bytes | None = None, fetch: bool = True) -> m.ImportRun:
    """Parse and validate a workbook; keep pictures in a staging folder until publish."""
    run_id = str(uuid.uuid7())
    rows = parse_workbook(data, _categories(s), images_zip, fetch_url if fetch else None)
    existing = {p.sku: p for p in s.scalars(select(m.Product))}
    staging = MEDIA_DIR / "staging" / run_id
    out, counts = [], {"rows": len(rows), "ok": 0, "errors": 0, "warnings": 0, "new": 0, "changed": 0, "unchanged": 0, "images": 0}
    for r in rows:
        img_rel = None
        if r.image:
            img_rel = f"staging/{run_id}/{r.row}.jpg"
            try:
                r.data["colour"] = _save_image(r.image, MEDIA_DIR / img_rel)
                counts["images"] += 1
            except Exception:  # noqa: BLE001
                img_rel = None
        action = "error"
        if r.ok:
            old = existing.get(r.data["sku"])
            if old is None:
                action = "new"
            else:
                same = all(_cmp(getattr(old, "category_code" if k == "category" else k, None), r.data.get(k)) for k in PRODUCT_FIELDS)
                action = "unchanged" if same and not img_rel else "changed"
            counts[action] += 1
            counts["ok"] += 1
        else:
            counts["errors"] += 1
        if any(i["severity"] == "warning" for i in r.issues):
            counts["warnings"] += 1
        out.append({"row": r.row, "data": r.data, "issues": r.issues, "image": img_rel, "image_source": r.image_source,
                    "quality": quality_score(r), "action": action})
    run = m.ImportRun(id=run_id, filename=filename, status="validated", counts=counts, rows=out)
    s.add(run)
    return run


def _cmp(a: Any, b: Any) -> bool:
    if isinstance(a, float) or isinstance(b, float):
        return abs((a or 0) - (b or 0)) < 1e-6
    return (a if a not in ("",) else None) == (b if b not in ("",) else None)


def publish(s: Session, run_id: str, store_id: str | None = None) -> dict[str, int]:
    run = s.get(m.ImportRun, run_id)
    if run is None:
        raise KeyError(run_id)
    if run.status == "published":
        return run.counts
    existing = {p.sku: p for p in s.scalars(select(m.Product))}
    stores = [store_id] if store_id else [st.id for st in s.scalars(select(m.Store))]
    published = 0
    for r in run.rows:
        if r["action"] == "error":
            continue
        d = r["data"]
        values = {k: d.get(k) for k in PRODUCT_FIELDS if k != "category"}
        values["category_code"] = d["category"]
        values["quality_score"] = r["quality"]
        values["source"] = run.filename
        if r["image"]:
            rel = f"products/{d['sku']}.jpg"
            (MEDIA_DIR / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(MEDIA_DIR / r["image"], MEDIA_DIR / rel)
            values["image"], values["has_image"], values["colour"] = rel, True, d.get("colour") or "#CBD5E1"
        p = existing.get(d["sku"])
        if p is None:
            p = m.Product(id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"product/{d['sku']}")),
                          **{**{"has_image": False, "colour": "#CBD5E1"}, **values})
            s.add(p)
            existing[d["sku"]] = p
        else:
            for k, v in values.items():
                setattr(p, k, v)
        s.flush()
        upd = d.get("units_per_day")
        if upd is not None:
            price = d.get("price") or 0.0
            for sid in stores:
                st = s.get(m.SkuStoreStats, (sid, p.id))
                vals = {"units_per_day": upd, "revenue_per_day": round(upd * price, 2), "margin_per_day": round(upd * price * 0.2, 2)}
                if st is None:
                    s.add(m.SkuStoreStats(store_id=sid, product_id=p.id, **vals))
                else:
                    for k, v in vals.items():
                        setattr(st, k, v)
        published += 1
    run.status = "published"
    run.counts = {**run.counts, "published": published}
    shutil.rmtree(MEDIA_DIR / "staging" / run_id, ignore_errors=True)
    return run.counts


def export_workbook(s: Session, title: str = "Product catalogue") -> bytes:
    stats: dict[str, float] = {}
    for st in s.scalars(select(m.SkuStoreStats)):
        stats.setdefault(st.product_id, st.units_per_day)
    products = []
    for p in s.scalars(select(m.Product).order_by(m.Product.category_code, m.Product.brand, m.Product.name)):
        products.append({
            "sku": p.sku, "gtin": p.gtin, "name": p.name, "brand": p.brand, "category": p.category_code,
            "width_mm": p.width_mm, "height_mm": p.height_mm, "depth_mm": p.depth_mm, "weight_g": p.weight_g,
            "pack_size": p.pack_size, "case_pack": p.case_pack, "temperature": p.temperature, "dims_source": p.dims_source,
            "dims_verified": p.dims_verified, "can_stack": p.can_stack, "max_stack": p.max_stack, "liquid": p.liquid,
            "fragile": p.fragile, "age_restricted": p.age_restricted, "hazardous": p.hazardous,
            "safety_reviewed": p.safety_reviewed, "price": p.price, "units_per_day": stats.get(p.id),
            "image_file": f"{p.gtin}_front.jpg" if p.image else None, "status": p.status, "_image": p.image,
        })
    return build_workbook(products, list(_categories(s).values()),
                          lambda p: (MEDIA_DIR / p["_image"]).read_bytes() if p.get("_image") and (MEDIA_DIR / p["_image"]).exists() else None,
                          title)


def blank_template(s: Session) -> bytes:
    example = [{
        "sku": "EXAMPLE-001", "gtin": "8901058000290", "name": "Example: Instant Noodles 70 g", "brand": "Brand", "category": "INS",
        "width_mm": 120, "height_mm": 95, "depth_mm": 30, "weight_g": 75, "pack_size": "70 g", "case_pack": 96,
        "temperature": "ambient", "dims_source": "measured", "dims_verified": True, "can_stack": True, "max_stack": 3,
        "liquid": False, "fragile": False, "age_restricted": False, "hazardous": False, "safety_reviewed": True,
        "price": 14, "units_per_day": 12, "image_file": "8901058000290_front.jpg", "status": "active",
    }]
    return build_workbook(example, list(_categories(s).values()), None, "Product import template")


def import_file(s: Session, path: Path, images_zip: Path | None = None) -> dict[str, int]:
    """Stage and publish in one go (seed loader)."""
    run = stage(s, path.name, path.read_bytes(), images_zip.read_bytes() if images_zip else None, fetch=False)
    s.flush()
    return publish(s, run.id)


__all__ = ["ImportRow", "MEDIA_DIR", "blank_template", "export_workbook", "import_file", "publish", "stage"]
