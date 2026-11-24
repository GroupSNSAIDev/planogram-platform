"""Build the demo product workbook from the fetched catalogue (tools/fetch_catalogue.py).

Writes, with the same layout stores receive:
  seed/catalogue/Product_Catalogue_Demo.xlsx    every demo product with its picture embedded
  seed/catalogue/Product_Import_Template.xlsx   blank template with one example row
The seed loader imports Product_Catalogue_Demo.xlsx through the normal import path, so the demo
catalogue is "uploaded" exactly like a store's file.

    services/api/.venv/Scripts/python tools/build_seed_workbook.py
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from planogram.catalog_excel import build_workbook  # noqa: E402

SEED = ROOT / "seed"
CAT_DIR = SEED / "catalogue"

PRICE_PER_KG = {
    "BRK": 450, "BIS": 260, "SNK": 420, "CHO": 1100, "INS": 260, "TEA": 650, "HDR": 620, "SPR": 520, "SAU": 260,
    "OIL": 190, "ATA": 55, "RIC": 95, "DAL": 150, "DRY": 950, "SAL": 45, "MAS": 650, "BEVA": 110, "WAT": 30,
    "DAI": 75, "CHE": 620, "RTE": 420, "BEVC": 160, "FRZ": 320, "ICE": 320, "BAK": 130, "IMP": 900, "PET": 380,
    "RTC": 320, "ORA": 650, "HAI": 850, "SKN": 1100, "DEO": 1500, "BAT": 420, "MEN": 800,
}
FRAGILE = {"SPR", "SAU", "HDR"}  # glass jars and bottles are common in these
MIN_REAL = 6                     # categories with fewer real products keep the sample products too


def main() -> None:
    catalogue = json.loads((CAT_DIR / "catalogue.json").read_text(encoding="utf-8"))
    categories = []
    with (SEED / "categories.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            categories.append({"code": r["code"], "department": r["department"], "name": r["category"], "temperature": r["temperature"]})
    temp = {c["code"]: c["temperature"] for c in categories}

    rows: list[dict] = []
    by_cat: dict[str, list[dict]] = {}
    for r in catalogue:
        by_cat.setdefault(r["category"], []).append(r)
    for cat, items in sorted(by_cat.items()):
        items.sort(key=lambda r: -r["popularity"])
        for rank, r in enumerate(items):
            amount = r["amount"]
            per_kg = PRICE_PER_KG.get(cat, 300)
            price = max(10, round(per_kg * amount / 1000 * (amount / 500) ** -0.15))
            rows.append({
                "sku": f"{cat}{rank + 1:04d}", "gtin": r["gtin"], "name": r["name"], "brand": r["brand"], "category": cat,
                "width_mm": r["width_mm"], "height_mm": r["height_mm"], "depth_mm": r["depth_mm"], "weight_g": r["weight_g"],
                "pack_size": r["quantity"], "case_pack": 12, "temperature": temp.get(cat, "ambient"),
                "dims_source": "estimated", "dims_verified": True,  # demo tenant: estimated sizes accepted (spec prompt 4)
                "can_stack": cat in {"BIS", "CHO", "INS", "TEA", "SPR", "DAI", "CHE"}, "max_stack": 2,
                "liquid": r["liquid"], "fragile": cat in FRAGILE, "age_restricted": False, "hazardous": False,
                "safety_reviewed": True, "price": price, "units_per_day": round(6.0 * 0.88 ** rank + 0.4, 1),
                "image_file": f"{r['source_code']}.jpg", "status": "active", "_img": CAT_DIR / r["image"],
            })
    # two deliberate data problems in breakfast cereals, so the eligibility badges can be demonstrated
    brk = [r for r in rows if r["category"] == "BRK"]
    if len(brk) > 4:
        brk[-1]["dims_verified"] = False                 # "Size estimated · drafts only"
        brk[-2]["safety_reviewed"] = False               # "Blocked · safety flags not reviewed"

    # sample products (no pictures) for categories without enough real products
    with (SEED / "products_sample.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if len(by_cat.get(r["category"], [])) >= MIN_REAL:
                continue
            rows.append({
                "sku": r["sku"], "gtin": r["gtin"], "name": r["name"], "brand": r["brand"], "category": r["category"],
                "width_mm": int(r["width_mm"]), "height_mm": int(r["height_mm"]), "depth_mm": int(r["depth_mm"]),
                "weight_g": int(r["weight_g"]), "pack_size": None, "case_pack": int(r["case_pack"]), "temperature": r["temperature"],
                "dims_source": "estimated", "dims_verified": True, "can_stack": False, "max_stack": 1,
                "liquid": r["category"] in {"OIL", "DAI", "BEVA", "WAT", "BEVC", "DET", "CLN", "HAI"}, "fragile": False,
                "age_restricted": r["age_restricted"] == "yes", "hazardous": r["hazardous"] == "yes", "safety_reviewed": True,
                "price": round(30 + int(r["weight_g"]) * 0.12), "units_per_day": 1.5, "image_file": None, "status": "active",
            })

    data = build_workbook(rows, categories, lambda p: p["_img"].read_bytes() if p.get("_img") and p["_img"].exists() else None,
                          "Demo product catalogue (Open Food Facts, CC BY-SA)")
    (CAT_DIR / "Product_Catalogue_Demo.xlsx").write_bytes(data)
    blank = build_workbook([], categories, None, "Product import template")
    (CAT_DIR / "Product_Import_Template.xlsx").write_bytes(blank)
    real = sum(1 for r in rows if r.get("_img"))
    print(f"wrote {len(rows)} products ({real} with real pictures) to {CAT_DIR / 'Product_Catalogue_Demo.xlsx'}")


if __name__ == "__main__":
    main()
