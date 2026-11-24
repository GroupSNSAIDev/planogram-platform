"""Store design files: export a whole store (floor, zones, landmarks, fixtures, shelf heights, sections and
placed products) to one JSON document, and import it back as a new store or over an existing one.

Format "planogram-layout" v1 uses business codes only (fixture codes, template codes, category codes, SKUs),
so a file can move between databases. The seed files for SMS-001 use the same shape for fixtures.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from . import models as m
from .engines.layout_doc import build_fixture_parts, rotated_size

FORMAT, VERSION = "planogram-layout", 1
NS = uuid.UUID("1b4e28ba-2fa1-11d2-883f-0016d3cca427")


def _id(*parts: str) -> str:
    return str(uuid.uuid5(NS, "/".join(parts)))


def export_layout(s: Session, store: m.Store, include_planograms: bool = True) -> dict[str, Any]:
    fixtures = list(s.scalars(select(m.Fixture).where(m.Fixture.store_id == store.id).order_by(m.Fixture.code)))
    templates = {t.code: t.defaults for t in s.scalars(select(m.FixtureTemplate))}
    fx_by_id = {f.id: f for f in fixtures}
    bays = {b.id: b for b in s.scalars(select(m.Bay).where(m.Bay.fixture_id.in_(list(fx_by_id))))}
    shelf_heights = []
    for su in s.scalars(select(m.Surface).where(m.Surface.bay_id.in_(list(bays)))):
        b = bays[su.bay_id]
        f = fx_by_id[b.fixture_id]
        tpl = templates.get(f.template_code, {})
        tpl_surfaces = tpl.get("surfaces") or []
        default = tpl_surfaces[su.idx - 1]["h"] if 0 < su.idx <= len(tpl_surfaces) else None
        if default != su.height_from_floor_mm:
            shelf_heights.append({"fixture": f.code, "side": b.side, "bay": b.idx, "shelf": su.idx, "height_mm": su.height_from_floor_mm})
    sections = list(s.scalars(select(m.Section).where(m.Section.fixture_id.in_(list(fx_by_id))).order_by(m.Section.code)))
    out: dict[str, Any] = {
        "format": FORMAT, "version": VERSION, "exported_at": datetime.now(UTC).isoformat(),
        "store": {"code": store.code, "name": store.name, "format": store.format, "timezone": store.timezone,
                  "width_mm": store.width_mm, "depth_mm": store.depth_mm},
        "zones": [{"code": z.code, "kind": z.kind, "name": z.name, "rect": z.rect}
                  for z in s.scalars(select(m.Zone).where(m.Zone.store_id == store.id).order_by(m.Zone.code))],
        "landmarks": [{"kind": lm.kind, "name": lm.name, "rect": lm.rect}
                      for lm in s.scalars(select(m.Landmark).where(m.Landmark.store_id == store.id).order_by(m.Landmark.name))],
        "fixtures": [{"code": f.code, "template": f.template_code, "x_mm": f.x_mm, "y_mm": f.y_mm, "rotation_deg": f.rotation_deg,
                      "faces": f.faces, "note": f.note} for f in fixtures],
        "shelf_heights": shelf_heights,
        "sections": [{"code": sc.code, "fixture": fx_by_id[sc.fixture_id].code, "side": sc.side, "bay_from": sc.bay_from,
                      "bay_to": sc.bay_to, "category": sc.category_code, "image_policy": sc.image_policy,
                      "assignment_locked": sc.assignment_locked} for sc in sections],
    }
    if include_planograms:
        skus = {p.id: p.sku for p in s.scalars(select(m.Product))}
        surfaces = {su.id: su for su in s.scalars(select(m.Surface).where(m.Surface.bay_id.in_(list(bays))))}
        plans = []
        for sc in sections:
            pg = s.scalar(select(m.Planogram).where(m.Planogram.section_id == sc.id))
            if pg is None:
                continue
            rows = []
            for p in s.scalars(select(m.Position).where(m.Position.planogram_id == pg.id).order_by(m.Position.surface_id, m.Position.seq)):
                su = surfaces.get(p.surface_id)
                if su is None:
                    continue
                b = bays[su.bay_id]
                rows.append({"bay": b.idx, "shelf": su.idx, "seq": p.seq, "sku": skus.get(p.product_id),
                             "facings": [p.facings_wide, p.facings_high, p.facings_deep], "locked": p.locked,
                             "locked_x_mm": p.locked_x_mm, "placed_by": p.placed_by, "reason": p.reason, "rule_ids": p.rule_ids})
            if rows:
                plans.append({"section": sc.code, "positions": rows})
        out["planograms"] = plans
    return out


class LayoutFileError(ValueError):
    pass


def import_layout(s: Session, data: dict[str, Any], code: str | None = None, name: str | None = None,
                  replace: bool = False) -> dict[str, int]:
    """Create (or replace) a store from a design file. Returns counts."""
    if data.get("format") != FORMAT and "fixtures" not in data:
        raise LayoutFileError("not a planogram layout file")
    st = data["store"]
    code = code or st["code"]
    templates = {t.code: t.defaults for t in s.scalars(select(m.FixtureTemplate))}
    categories = {c.code for c in s.scalars(select(m.Category))}
    existing = s.scalar(select(m.Store).where(m.Store.code == code))
    if existing is not None:
        if not replace:
            raise LayoutFileError(f"store {code} already exists; choose another code or replace it")
        delete_store(s, existing)
    width = int(st.get("width_mm") or st.get("floor", {}).get("width_mm"))
    depth = int(st.get("depth_mm") or st.get("floor", {}).get("depth_mm"))
    store = m.Store(id=_id("store", code), code=code, name=name or st.get("name") or code, format=st.get("format"),
                    timezone=st.get("timezone") or "Asia/Kolkata", width_mm=width, depth_mm=depth, layout_version=1)
    s.add(store)
    s.flush()
    for i, z in enumerate(data.get("zones", [])):
        s.add(m.Zone(id=_id("zone", code, z.get("code") or str(i)), store_id=store.id, code=z.get("code") or f"Z-{i + 1:02d}",
                     kind=z["kind"], name=z.get("name") or z["kind"], rect=[int(v) for v in z["rect"]]))
    for i, lm in enumerate(data.get("landmarks", [])):
        s.add(m.Landmark(id=_id("landmark", code, str(i)), store_id=store.id, kind=lm["kind"], name=lm.get("name") or lm["kind"],
                         rect=[int(v) for v in lm["rect"]]))
    s.flush()

    fixture_ids: dict[str, str] = {}
    surface_key: dict[tuple, str] = {}
    for f in data.get("fixtures", []):
        tpl_code = f.get("template") or f.get("template_code")
        tpl = templates.get(tpl_code)
        if tpl is None:
            raise LayoutFileError(f"fixture {f['code']}: unknown template {tpl_code}")
        rot = int(f.get("rotation_deg", 0)) % 360
        w, d = rotated_size(tpl, rot)
        fid = _id("fixture", code, f["code"])
        fx = {"id": fid, "code": f["code"], "template_code": tpl_code, "kind": tpl["kind"], "x_mm": int(f["x_mm"]),
              "y_mm": int(f["y_mm"]), "rotation_deg": rot, "footprint_w_mm": w, "footprint_d_mm": d,
              "temperature": tpl["temperature"], "faces": f.get("faces"), "note": f.get("note")}
        s.add(m.Fixture(store_id=store.id, **fx))
        fixture_ids[f["code"]] = fid
        s.flush()
        bays, surfaces = build_fixture_parts(fx, tpl)
        s.add_all(m.Bay(**b) for b in bays.values())
        s.flush()
        s.add_all(m.Surface(**x) for x in surfaces.values())
        for x in surfaces.values():
            b = bays[x["bay_id"]]
            surface_key[(f["code"], b["side"], b["idx"], x["idx"])] = x["id"]
    s.flush()
    for h in data.get("shelf_heights", []):
        sid = surface_key.get((h["fixture"], h["side"], h["bay"], h["shelf"]))
        if sid:
            s.get(m.Surface, sid).height_from_floor_mm = int(h["height_mm"])

    section_ids: dict[str, str] = {}
    for sc in data.get("sections", []):
        if sc["fixture"] not in fixture_ids or sc["category"] not in categories:
            continue
        sid = _id("section", code, sc["code"])
        s.add(m.Section(id=sid, fixture_id=fixture_ids[sc["fixture"]], side=sc["side"], bay_from=int(sc["bay_from"]),
                        bay_to=int(sc["bay_to"]), code=sc["code"],
                        category_code=sc["category"], image_policy=sc.get("image_policy") or "placeholder_ok",
                        assignment_locked=bool(sc.get("assignment_locked") or sc.get("assignment_lock"))))
        section_ids[sc["code"]] = sid
    s.flush()

    placed = 0
    if data.get("planograms"):
        products = {p.sku: p.id for p in s.scalars(select(m.Product))}
        sections = {sc["code"]: sc for sc in data.get("sections", [])}
        for plan in data["planograms"]:
            sc = sections.get(plan["section"])
            sid = section_ids.get(plan["section"])
            if not sc or not sid:
                continue
            pg = m.Planogram(id=_id("planogram", code, plan["section"]), section_id=sid, status="draft", row_version=1)
            s.add(pg)
            s.flush()
            for i, r in enumerate(plan["positions"]):
                surf = surface_key.get((sc["fixture"], sc["side"], r["bay"], r["shelf"]))
                pid = products.get(r.get("sku"))
                if not surf or not pid:
                    continue
                fw, fh, fd = r.get("facings", [1, 1, 1])
                s.add(m.Position(id=_id("position", code, plan["section"], str(i)), planogram_id=pg.id, surface_id=surf,
                                 product_id=pid, seq=r.get("seq", i), x_mm=0, facings_wide=fw, facings_high=fh, facings_deep=fd,
                                 placed_by=r.get("placed_by") or "import", reason=r.get("reason"), rule_ids=r.get("rule_ids") or [],
                                 locked=bool(r.get("locked")), locked_x_mm=r.get("locked_x_mm")))
                placed += 1
        s.flush()
        # positions need their x recalculated: reuse the command path (an empty replace keeps everything)
        from .services import apply_planogram
        for pg in s.scalars(select(m.Planogram).join(m.Section).join(m.Fixture).where(m.Fixture.store_id == store.id)):
            from .services import load_positions
            current = list(load_positions(s, pg.id).values())
            if current:
                apply_planogram(s, pg.id, [{"type": "ReplacePositions", "positions": current, "keep_locked": False}])
    # demo: a new store borrows the sales stats of an existing store so auto-fill has demand to work with
    if s.scalar(select(m.SkuStoreStats).where(m.SkuStoreStats.store_id == store.id).limit(1)) is None:
        donor = s.scalar(select(m.SkuStoreStats.store_id).where(m.SkuStoreStats.store_id != store.id).limit(1))
        if donor:
            for st in list(s.scalars(select(m.SkuStoreStats).where(m.SkuStoreStats.store_id == donor))):
                s.add(m.SkuStoreStats(store_id=store.id, product_id=st.product_id, units_per_day=st.units_per_day,
                                      revenue_per_day=st.revenue_per_day, margin_per_day=st.margin_per_day))
            s.flush()
    return {"fixtures": len(fixture_ids), "sections": len(section_ids), "positions": placed,
            "zones": len(data.get("zones", [])), "landmarks": len(data.get("landmarks", []))}


def delete_store(s: Session, store: m.Store) -> None:
    fids = list(s.scalars(select(m.Fixture.id).where(m.Fixture.store_id == store.id)))
    sids = list(s.scalars(select(m.Section.id).where(m.Section.fixture_id.in_(fids))))
    pgs = list(s.scalars(select(m.Planogram.id).where(m.Planogram.section_id.in_(sids))))
    bay_ids = list(s.scalars(select(m.Bay.id).where(m.Bay.fixture_id.in_(fids))))
    s.execute(delete(m.Position).where(m.Position.planogram_id.in_(pgs)))
    s.execute(delete(m.Planogram).where(m.Planogram.id.in_(pgs)))
    s.execute(delete(m.Section).where(m.Section.id.in_(sids)))
    s.execute(delete(m.Surface).where(m.Surface.bay_id.in_(bay_ids)))
    s.execute(delete(m.Bay).where(m.Bay.id.in_(bay_ids)))
    s.execute(delete(m.Fixture).where(m.Fixture.id.in_(fids)))
    s.execute(delete(m.Zone).where(m.Zone.store_id == store.id))
    s.execute(delete(m.Landmark).where(m.Landmark.store_id == store.id))
    s.execute(delete(m.SkuStoreStats).where(m.SkuStoreStats.store_id == store.id))
    s.delete(store)
    s.flush()
