"""Load the sample mall store SMS-001 (spec section 10, FR-41).

    python -m planogram.seed_loader --reset

Reads seed/*.json|csv, generates bays and surfaces from each fixture's template, and adds
synthetic daily sales stats (fixed random seed, so every run is identical). Ids are uuid5 of the
business codes, so a reseed keeps the same ids and links stay valid.
"""
from __future__ import annotations

import argparse
import os
import csv
import json
import random
import uuid
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.orm import Session

from . import models as m
from .db import Base, engine, unit_of_work
from .engines.layout_doc import build_fixture_parts

SEED_DIR = Path(__file__).resolve().parents[3] / "seed"
NS = uuid.UUID("1b4e28ba-2fa1-11d2-883f-0016d3cca427")

DEPT_PRODUCT_COLOUR = {
    "Fresh": "#22C55E", "Dairy & chilled": "#3B82F6", "Beverages": "#06B6D4", "Frozen": "#6366F1",
    "Staples": "#D97706", "Packaged food": "#EA580C", "Personal care": "#DB2777", "Home care": "#7C3AED",
    "General merchandise": "#6B7280", "Impulse": "#EF4444", "Promotions": "#65A30D",
}


def sid(kind: str, code: str) -> str:
    return str(uuid.uuid5(NS, f"{kind}/{code}"))


def _csv(name: str) -> list[dict[str, str]]:
    with (SEED_DIR / name).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _yes(v: str | None) -> bool:
    return (v or "").strip().lower() in ("yes", "true", "1", "y")


def load(session: Session) -> dict[str, int]:
    templates = json.loads((SEED_DIR / "fixture_templates.json").read_text(encoding="utf-8"))
    store_json = json.loads((SEED_DIR / "store_SMS-001.json").read_text(encoding="utf-8"))
    st = store_json["store"]
    store_id = sid("store", st["code"])

    session.add(m.Store(id=store_id, code=st["code"], name=st["name"], format=st.get("format"),
                        timezone=st.get("timezone", "Asia/Kolkata"),
                        width_mm=st["floor"]["width_mm"], depth_mm=st["floor"]["depth_mm"]))
    session.flush()
    for code, t in templates.items():
        session.add(m.FixtureTemplate(code=code, kind=t["kind"], name=t["name"], defaults=t))
    categories = {}
    for row in _csv("categories.csv"):
        categories[row["code"]] = row
        session.add(m.Category(code=row["code"], department=row["department"], name=row["category"],
                               temperature=row["temperature"]))
    session.flush()
    for z in store_json["zones"]:
        session.add(m.Zone(id=sid("zone", z["code"]), store_id=store_id, code=z["code"], kind=z["kind"],
                           name=z["name"], rect=z["rect"]))
    for i, lm in enumerate(store_json["landmarks"]):
        session.add(m.Landmark(id=sid("landmark", f"{st['code']}/{i}"), store_id=store_id, kind=lm["kind"],
                               name=lm["name"], rect=lm["rect"]))
    session.flush()

    fixture_ids: dict[str, str] = {}
    n_bays = n_surfaces = 0
    for f in store_json["fixtures"]:
        fid = sid("fixture", f"{st['code']}/{f['code']}")
        fixture_ids[f["code"]] = fid
        fx = {"id": fid, "code": f["code"], "template_code": f["template"], "kind": f["kind"], "x_mm": f["x_mm"],
              "y_mm": f["y_mm"], "rotation_deg": f["rotation_deg"], "footprint_w_mm": f["footprint_w_mm"],
              "footprint_d_mm": f["footprint_d_mm"], "temperature": f["temperature"], "faces": f.get("faces"),
              "note": f.get("note")}
        session.add(m.Fixture(store_id=store_id, **fx))
        session.flush()
        bays, surfaces = build_fixture_parts(fx, templates[f["template"]])
        session.add_all(m.Bay(**b) for b in bays.values())
        session.flush()
        session.add_all(m.Surface(**s) for s in surfaces.values())
        n_bays += sum(1 for b in bays.values() if b["side"] != "TOP")
        n_surfaces += len(surfaces)
    session.flush()

    n_sections = 0
    for row in _csv(f"sections_{st['code']}.csv"):
        session.add(m.Section(
            id=sid("section", row["code"]), fixture_id=fixture_ids[row["fixture"]], side=row["side"],
            bay_from=int(row["bay_from"]), bay_to=int(row["bay_to"]), code=row["code"], category_code=row["category"],
            image_policy="placeholder_ok", assignment_locked=bool(row.get("assignment_lock"))))
        n_sections += 1
    session.flush()

    workbook = SEED_DIR / "catalogue" / "Product_Catalogue_Demo.xlsx"
    if workbook.exists() and os.environ.get("PLANOGRAM_SEED") != "csv":
        # the demo catalogue goes through the same import path as a store's workbook
        from .imports import import_file
        session.flush()
        counts = import_file(session, workbook)
        session.flush()
        add_generated_store(session, "SMS-002", "Sample Hypermarket 002 (demo, 60,000 sq ft)", 90000, 62000)
        return {"fixtures": len(fixture_ids), "shelf_bays": n_bays, "surfaces": n_surfaces, "sections": n_sections,
                "categories": len(categories), "products": counts.get("published", 0)}

    # fallback: the original sample CSVs (sizes estimated but verified for the demo tenant, spec prompt 4)
    rng = random.Random(42)
    n_products = 0
    for row in _csv("products_sample.csv"):
        pid = sid("product", row["sku"])
        weight = int(row["weight_g"])
        price = float(round(30 + weight * 0.12))
        upd = round(rng.uniform(0.6, 5.0), 1)
        session.add(m.Product(
            id=pid, sku=row["sku"], gtin=row["gtin"], name=row["name"], brand=row["brand"],
            category_code=row["category"], width_mm=int(row["width_mm"]), height_mm=int(row["height_mm"]),
            depth_mm=int(row["depth_mm"]), weight_g=weight, case_pack=int(row["case_pack"]),
            temperature=row["temperature"], dims_source=row["dims_source"], dims_verified=True,
            safety_reviewed=True, age_restricted=_yes(row.get("age_restricted")), hazardous=_yes(row.get("hazardous")),
            has_image=False, colour=DEPT_PRODUCT_COLOUR.get(row["department"], "#94A3B8"), price=price))
        session.flush()
        session.add(m.SkuStoreStats(store_id=store_id, product_id=pid, units_per_day=upd,
                                    revenue_per_day=round(upd * price, 2), margin_per_day=round(upd * price * 0.2, 2)))
        n_products += 1

    # products: the POC breakfast-cereal catalogue for the hero section G03-A-01
    for row in _csv("poc_demo_products.csv"):
        pid = sid("product", row["sku"])
        price, upd = float(row["price"]), float(row["units_per_day"])
        session.add(m.Product(
            id=pid, sku=row["sku"], gtin=row["gtin"], name=row["name"], brand=row["brand"],
            category_code=row["category"], width_mm=int(row["width_mm"]), height_mm=int(row["height_mm"]),
            depth_mm=int(row["depth_mm"]), weight_g=int(row["weight_g"]), case_pack=int(row["case_pack"]),
            temperature=row["temperature"], dims_source=row["dims_source"], dims_verified=_yes(row["dims_verified"]),
            safety_reviewed=_yes(row["safety_reviewed"]), has_image=_yes(row["has_image"]),
            can_stack=_yes(row["can_stack"]), max_stack=int(row["max_stack"]), colour=row["colour"], price=price))
        session.flush()
        session.add(m.SkuStoreStats(store_id=store_id, product_id=pid, units_per_day=upd,
                                    revenue_per_day=round(upd * price, 2),
                                    margin_per_day=round(upd * price * float(row["margin_rate"]), 2)))
        n_products += 1

    return {"fixtures": len(fixture_ids), "shelf_bays": n_bays, "surfaces": n_surfaces,
            "sections": n_sections, "categories": len(categories), "products": n_products}


def add_generated_store(session: Session, code: str, name: str, width_mm: int, depth_mm: int) -> dict[str, int]:
    from .engines.store_generator import generate
    from .layout_io import import_layout
    return import_layout(session, generate(width_mm, depth_mm, code, name))


def reset_and_load() -> dict[str, int]:
    from .imports import MEDIA_DIR
    import shutil
    shutil.rmtree(MEDIA_DIR / "products", ignore_errors=True)
    shutil.rmtree(MEDIA_DIR / "staging", ignore_errors=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with unit_of_work() as s:
        return load(s)


def clear_planograms(session: Session) -> None:
    session.execute(delete(m.Position))
    session.execute(delete(m.Planogram))


def main() -> None:
    parser = argparse.ArgumentParser(description="Load the sample store SMS-001")
    parser.add_argument("--reset", action="store_true", help="drop and recreate all tables first")
    parser.parse_args()
    print(json.dumps(reset_and_load(), indent=1))


if __name__ == "__main__":
    main()
