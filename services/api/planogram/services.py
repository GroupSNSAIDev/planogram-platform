"""Load documents from the database, apply command batches through the pure engines, and
persist only what changed, all inside one transaction (spec 12.4, simplified for the POC)."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from . import models as m
from .engines.autofill import autofill
from .engines.context import build_context, eligibility
from .engines.layout_checks import check_layout
from .engines.layout_doc import CommandError, apply_layout_commands
from .engines.planogram_doc import apply_planogram_commands
from .engines.rules import evaluate


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


def row(obj: Any) -> dict[str, Any]:
    return {c.key: getattr(obj, c.key) for c in obj.__table__.columns}


def _strip(d: dict[str, Any], *keys: str) -> dict[str, Any]:
    return {k: v for k, v in d.items() if k not in keys}


# ----------------------------------------------------------------------------- reference data

def load_templates(s: Session) -> dict[str, dict[str, Any]]:
    return {t.code: t.defaults for t in s.scalars(select(m.FixtureTemplate))}


def load_categories(s: Session) -> dict[str, dict[str, Any]]:
    return {c.code: row(c) for c in s.scalars(select(m.Category))}


def load_products(s: Session) -> dict[str, dict[str, Any]]:
    return {p.id: row(p) for p in s.scalars(select(m.Product))}


def load_stats(s: Session, store_id: str) -> dict[str, dict[str, Any]]:
    q = select(m.SkuStoreStats).where(m.SkuStoreStats.store_id == store_id)
    return {st.product_id: _strip(row(st), "store_id", "product_id") for st in s.scalars(q)}


def get_store(s: Session, code: str) -> m.Store:
    store = s.scalar(select(m.Store).where(m.Store.code == code))
    if store is None:
        raise NotFound(f"store {code} not found")
    return store


# ----------------------------------------------------------------------------- layout

def load_layout(s: Session, store: m.Store) -> dict[str, Any]:
    fixtures = {f.id: _strip(row(f), "store_id") for f in s.scalars(select(m.Fixture).where(m.Fixture.store_id == store.id))}
    fids = list(fixtures)
    bays = {b.id: row(b) for b in s.scalars(select(m.Bay).where(m.Bay.fixture_id.in_(fids)))}
    surfaces = {x.id: row(x) for x in s.scalars(select(m.Surface).where(m.Surface.bay_id.in_(list(bays))))}
    sections = {x.id: row(x) for x in s.scalars(select(m.Section).where(m.Section.fixture_id.in_(fids)))}
    return {
        "store": row(store),
        "zones": [_strip(row(z), "store_id") for z in s.scalars(select(m.Zone).where(m.Zone.store_id == store.id))],
        "landmarks": [_strip(row(lm), "store_id") for lm in s.scalars(select(m.Landmark).where(m.Landmark.store_id == store.id))],
        "fixtures": fixtures, "bays": bays, "surfaces": surfaces, "sections": sections,
    }


def sections_with_positions(s: Session) -> set[str]:
    q = select(m.Planogram.section_id).join(m.Position, m.Position.planogram_id == m.Planogram.id).distinct()
    return set(s.scalars(q))


def _persist_map(s: Session, model: type, old: dict[str, dict], new: dict[str, dict], extra: dict | None = None) -> tuple[list, list]:
    """Insert and update changed rows; return ids to delete (deleted later, children first)."""
    cols = {c.key for c in model.__table__.columns}
    removed = [k for k in old if k not in new]
    added = []
    for k, v in new.items():
        values = {c: v[c] for c in cols if c in v}
        if k not in old:
            added.append(model(**values, **(extra or {})))
        elif v != old[k]:
            obj = s.get(model, k)
            for c, val in values.items():
                setattr(obj, c, val)
    return removed, added


def apply_layout(s: Session, store_code: str, commands: list[dict], expected_version: int | None = None) -> dict[str, Any]:
    store = get_store(s, store_code)
    if expected_version is not None and expected_version != store.layout_version:
        raise Conflict(f"layout changed (version {store.layout_version}, you had {expected_version}); reload")
    old = load_layout(s, store)
    new, inverse = apply_layout_commands(old, load_templates(s), load_categories(s), commands, sections_with_positions(s))

    order = [("fixtures", m.Fixture, {"store_id": store.id}), ("bays", m.Bay, None),
             ("surfaces", m.Surface, None), ("sections", m.Section, None)]
    removed: dict[str, list] = {}
    for key, model, extra in order:                      # parents first for inserts
        rem, add = _persist_map(s, model, old[key], new[key], extra)
        removed[key] = rem
        s.add_all(add)
        s.flush()
    for key, model, _ in reversed(order):                # children first for deletes
        if removed[key]:
            s.execute(delete(model).where(model.id.in_(removed[key])))
    for key, model in (("zones", m.Zone), ("landmarks", m.Landmark)):
        old_map = {z["id"]: z for z in old[key]}
        new_map = {z["id"]: z for z in new[key]}
        rem, add = _persist_map(s, model, old_map, new_map, {"store_id": store.id})
        s.add_all(add)
        if rem:
            s.execute(delete(model).where(model.id.in_(rem)))
    for k in ("name", "width_mm", "depth_mm"):
        if new["store"][k] != old["store"][k]:
            setattr(store, k, new["store"][k])
    store.layout_version += 1
    for c in commands:
        s.add(m.CommandLog(scope="layout", target_id=store.id, command=c, inverse=inverse))
    return {"layout_version": store.layout_version, "inverse": inverse, "checks": check_layout(new)}


def layout_payload(s: Session, store_code: str) -> dict[str, Any]:
    store = get_store(s, store_code)
    layout = load_layout(s, store)
    counts = dict(s.execute(
        select(m.Planogram.section_id, func.count(m.Position.id))
        .join(m.Position, m.Position.planogram_id == m.Planogram.id).group_by(m.Planogram.section_id)).all())
    for sec_id, sec in layout["sections"].items():
        layout["sections"][sec_id] = {**sec, "positions": counts.get(sec_id, 0)}
    return {"layout": layout, "templates": load_templates(s), "categories": load_categories(s),
            "checks": check_layout(layout)}


# ----------------------------------------------------------------------------- planograms

def get_section(s: Session, code_or_id: str) -> m.Section:
    sec = s.get(m.Section, code_or_id) or s.scalar(select(m.Section).where(m.Section.code == code_or_id).limit(1))
    if sec is None:
        raise NotFound(f"section {code_or_id} not found")
    return sec


def get_or_create_planogram(s: Session, section: m.Section) -> m.Planogram:
    pg = s.scalar(select(m.Planogram).where(m.Planogram.section_id == section.id))
    if pg is None:
        pg = m.Planogram(id=str(uuid.uuid7()), section_id=section.id, status="draft", row_version=1)
        s.add(pg)
        s.flush()
    return pg


def load_positions(s: Session, planogram_id: str) -> dict[str, dict[str, Any]]:
    q = select(m.Position).where(m.Position.planogram_id == planogram_id)
    return {p.id: _strip(row(p), "planogram_id") for p in s.scalars(q)}


def planogram_context(s: Session, section: m.Section) -> dict[str, Any]:
    fixture = s.get(m.Fixture, section.fixture_id)
    store = s.get(m.Store, fixture.store_id)
    layout = load_layout(s, store)
    return build_context(layout, section.id, load_products(s), load_stats(s, store.id), load_categories(s))


def planogram_payload(s: Session, section_code: str) -> dict[str, Any]:
    section = get_section(s, section_code)
    pg = get_or_create_planogram(s, section)
    ctx = planogram_context(s, section)
    positions = load_positions(s, pg.id)
    fixture = ctx["fixture"]
    temp, policy = fixture["temperature"], ctx["section"]["image_policy"]
    catalogue = []
    for prod in sorted(ctx["products"].values(), key=lambda p: (p["category_code"] != section.category_code, p["brand"], p["name"])):
        st = ctx["stats"].get(prod["id"], {})
        catalogue.append({**prod, "eligibility": eligibility(prod, temp, policy),
                          "units_per_day": st.get("units_per_day", 0.0), "margin_per_day": st.get("margin_per_day", 0.0)})
    return {
        "planogram": row(pg),
        "section": ctx["section"], "fixture": fixture, "category": ctx["category"],
        "store": {"code": s.get(m.Store, s.get(m.Fixture, section.fixture_id).store_id).code},
        "surfaces": ctx["surfaces"], "positions": positions, "products": catalogue,
        "evaluation": evaluate(ctx, positions),
    }


def _persist_positions(s: Session, pg: m.Planogram, old: dict, new: dict) -> None:
    rem, add = _persist_map(s, m.Position, old, new, {"planogram_id": pg.id})
    if rem:
        s.execute(delete(m.Position).where(m.Position.id.in_(rem)))
        s.flush()
    s.add_all(add)


def apply_planogram(s: Session, planogram_id: str, commands: list[dict], expected_version: int | None = None) -> dict[str, Any]:
    pg = s.get(m.Planogram, planogram_id)
    if pg is None:
        raise NotFound(f"planogram {planogram_id} not found")
    if pg.status != "draft":
        raise Conflict("only drafts can be edited")
    if expected_version is not None and expected_version != pg.row_version:
        raise Conflict(f"planogram changed (version {pg.row_version}, you had {expected_version}); reload")
    section = s.get(m.Section, pg.section_id)
    ctx = planogram_context(s, section)
    old = load_positions(s, pg.id)
    new, inverse = apply_planogram_commands(ctx, old, commands)
    _persist_positions(s, pg, old, new)
    result = evaluate(ctx, new)
    pg.row_version += 1
    pg.score, pg.hard_breaks = result["score"], result["hard_breaks"]
    for c in commands:
        s.add(m.CommandLog(scope="planogram", target_id=pg.id, command=c, inverse=inverse))
    return {"row_version": pg.row_version, "positions": new, "evaluation": result, "inverse": inverse}


def run_autofill(s: Session, planogram_id: str) -> dict[str, Any]:
    pg = s.get(m.Planogram, planogram_id)
    if pg is None:
        raise NotFound(f"planogram {planogram_id} not found")
    ctx = planogram_context(s, s.get(m.Section, pg.section_id))
    return autofill(ctx, load_positions(s, pg.id))


def validate(s: Session, planogram_id: str) -> dict[str, Any]:
    pg = s.get(m.Planogram, planogram_id)
    if pg is None:
        raise NotFound(f"planogram {planogram_id} not found")
    ctx = planogram_context(s, s.get(m.Section, pg.section_id))
    return evaluate(ctx, load_positions(s, pg.id))


__all__ = ["CommandError", "Conflict", "NotFound"]


def autofill_many(s: Session, store_code: str, fixture_code: str | None = None, only_empty: bool = True) -> dict[str, Any]:
    """Auto-fill every shelf section of a store (or of one fixture) and accept the proposals.

    Loads the layout, products and stats once; each section is filled by the same pure engine and saved
    through the same command (ReplacePositions keeps placement-locked products).
    """
    from .engines.autofill import autofill as run_engine
    store = get_store(s, store_code)
    layout = load_layout(s, store)
    products, stats, cats = load_products(s), load_stats(s, store.id), load_categories(s)
    filled = skipped = placed = 0
    details = []
    for sec in sorted(layout["sections"].values(), key=lambda x: x["code"]):
        fx = layout["fixtures"][sec["fixture_id"]]
        if fixture_code and fx["code"] != fixture_code:
            continue
        ctx = build_context(layout, sec["id"], products, stats, cats)
        if not ctx["surfaces"]:
            continue  # chest, bin, stack and pallet surfaces are not planned by shelf in the POC
        section = s.get(m.Section, sec["id"])
        pg = get_or_create_planogram(s, section)
        old = load_positions(s, pg.id)
        if only_empty and old:
            skipped += 1
            continue
        proposal = run_engine(ctx, old)
        new, _ = apply_planogram_commands(ctx, old, [{"type": "ReplacePositions", "positions": proposal["positions"], "keep_locked": True}])
        _persist_positions(s, pg, old, new)
        ev = proposal["evaluation"]
        pg.row_version += 1
        pg.score, pg.hard_breaks = ev["score"], ev["hard_breaks"]
        filled += 1
        placed += len(new)
        details.append({"section": sec["code"], "section_id": sec["id"], "positions": len(new), "score": ev["score"],
                        "fill_pct": ev["summary"]["fill_pct"], "unplaced": len(proposal["unplaced"])})
    s.add(m.CommandLog(scope="layout", target_id=store.id, command={"type": "AutofillMany", "fixture": fixture_code,
                                                                     "only_empty": only_empty}, inverse=[]))
    return {"sections_filled": filled, "sections_skipped": skipped, "positions": placed, "details": details}


def section_list(s: Session, store_code: str) -> list[dict[str, Any]]:
    """Every shelf section of a store with its planning progress (for the section picker)."""
    store = get_store(s, store_code)
    layout = load_layout(s, store)
    cats = load_categories(s)
    shelf_bays = {b["id"] for b in layout["bays"].values()}
    has_shelf = {layout["bays"][x["bay_id"]]["fixture_id"] for x in layout["surfaces"].values() if x["kind"] == "shelf" and x["bay_id"] in shelf_bays}
    pgs = {pg.section_id: pg for pg in s.scalars(select(m.Planogram))}
    counts = dict(s.execute(select(m.Planogram.section_id, func.count(m.Position.id))
                            .join(m.Position, m.Position.planogram_id == m.Planogram.id).group_by(m.Planogram.section_id)).all())
    out = []
    for sec in layout["sections"].values():
        fx = layout["fixtures"][sec["fixture_id"]]
        if fx["id"] not in has_shelf:
            continue
        pg = pgs.get(sec["id"])
        cat = cats.get(sec["category_code"], {})
        out.append({**sec, "fixture_code": fx["code"], "fixture_kind": fx["kind"], "category_name": cat.get("name"),
                    "department": cat.get("department"), "positions": counts.get(sec["id"], 0),
                    "score": pg.score if pg else None, "hard_breaks": pg.hard_breaks if pg else None,
                    "bays": sec["bay_to"] - sec["bay_from"] + 1})
    return sorted(out, key=lambda x: (x["department"] or "", x["fixture_code"], x["side"], x["bay_from"]))
