"""Fetch a real product catalogue for the DEMO tenant from Open Food Facts / Open Beauty Facts.

Data: ODbL. Images: CC BY-SA. Spec 9.2 / 10.6: demo tenant only, with attribution; never mixed into a
client tenant. We fetch once and cache (search responses in seed/catalogue/raw/, images in
seed/catalogue/images/), politely: a generic User-Agent, <= 1 search request per 7 s.

    python tools/fetch_catalogue.py            # resumable; re-running only fetches what is missing

Output: seed/catalogue/catalogue.json (one record per product, our category codes, estimated sizes).
"""
from __future__ import annotations

import io
import json
import math
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "seed" / "catalogue"
RAW, IMG = OUT / "raw", OUT / "images"
UA = "PlanogramPOC/0.2 (demo catalogue import)"
PER_CATEGORY = 26

# our category -> (site, [category tags]); tags are tried in order until we have enough products
SOURCES: dict[str, tuple[str, list[str]]] = {
    "ATA": ("off", ["flours", "wheat-flours"]),
    "RIC": ("off", ["rices", "basmati-rices"]),
    "DAL": ("off", ["pulses", "lentils"]),
    "DRY": ("off", ["dried-fruits", "nuts"]),
    "OIL": ("off", ["vegetable-oils", "ghee"]),
    "SAL": ("off", ["sugars", "salts"]),
    "MAS": ("off", ["spices", "spice-mixes"]),
    "BRK": ("off", ["breakfast-cereals"]),
    "SPR": ("off", ["jams", "honeys", "spreads"]),
    "TEA": ("off", ["teas", "coffees"]),
    "HDR": ("off", ["cocoa-and-chocolate-powders", "malted-drinks", "instant-beverages"]),
    "BIS": ("off", ["biscuits", "cookies"]),
    "SNK": ("off", ["salty-snacks", "chips-and-fries", "crisps"]),
    "CHO": ("off", ["chocolates", "confectioneries"]),
    "INS": ("off", ["instant-noodles", "noodles"]),
    "SAU": ("off", ["sauces", "pickles", "ketchup"]),
    "RTC": ("off", ["pastas", "soups", "ready-to-cook"]),
    "BEVA": ("off", ["fruit-juices", "sodas", "carbonated-drinks"]),
    "WAT": ("off", ["waters", "energy-drinks"]),
    "DAI": ("off", ["yogurts", "milks", "butters"]),
    "CHE": ("off", ["cheeses", "paneer"]),
    "RTE": ("off", ["meals", "prepared-meals"]),
    "BEVC": ("off", ["flavoured-milks", "milk-drinks", "iced-teas"]),
    "FRZ": ("off", ["frozen-foods"]),
    "ICE": ("off", ["ice-creams", "frozen-desserts"]),
    "BAK": ("off", ["breads", "cakes"]),
    "IMP": ("off", ["chewing-gum", "candies"]),
    "PET": ("off", ["pet-food", "dog-food"]),
    "ORA": ("off", ["toothpastes", "toothbrushes", "mouthwashes"]),
    "HAI": ("off", ["shampoos", "hair-oils", "conditioners"]),
    "SKN": ("off", ["face-creams", "moisturizers", "body-lotions", "creams"]),
    "DEO": ("off", ["deodorants", "perfumes"]),
    "BAT": ("off", ["soaps", "shower-gels", "body-washes"]),
    "MEN": ("off", ["shaving-foams", "shaving", "after-shaves"]),
}
SITES = {"off": "world.openfoodfacts.org", "obf": "world.openbeautyfacts.org"}

# rough pack shape per category: depth as a share of width, density g/ml, max height mm
SHAPE: dict[str, tuple[float, float, int]] = {
    "BRK": (0.33, 0.30, 330), "BIS": (0.45, 0.45, 260), "SNK": (0.35, 0.10, 320), "CHO": (0.25, 0.9, 220),
    "INS": (0.40, 0.35, 220), "TEA": (0.55, 0.40, 260), "HDR": (0.80, 0.55, 260), "SPR": (0.90, 1.2, 200),
    "SAU": (0.60, 1.1, 300), "OIL": (0.45, 0.92, 330), "ATA": (0.35, 0.65, 420), "RIC": (0.35, 0.85, 420),
    "DAL": (0.35, 0.85, 320), "DRY": (0.40, 0.55, 260), "SAL": (0.40, 1.0, 260), "MAS": (0.45, 0.55, 200),
    "BEVA": (0.80, 1.0, 330), "WAT": (0.95, 1.0, 330), "DAI": (0.90, 1.03, 260), "CHE": (0.90, 1.0, 120),
    "RTE": (0.80, 1.0, 200), "BEVC": (0.95, 1.03, 220), "FRZ": (0.30, 0.6, 300), "ICE": (0.95, 0.6, 200),
    "BAK": (0.60, 0.25, 260), "IMP": (0.30, 0.9, 140), "PET": (0.35, 0.6, 400), "RTC": (0.40, 0.5, 260),
    "ORA": (0.25, 1.3, 220), "HAI": (0.40, 1.0, 280), "SKN": (0.55, 1.0, 220), "DEO": (0.95, 0.5, 200),
    "BAT": (0.55, 1.1, 140), "MEN": (0.95, 0.4, 220),
}
LIQUID = {"OIL", "BEVA", "WAT", "DAI", "BEVC", "SAU", "HAI", "SKN"}


def get(url: str, timeout: int = 40) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def search(site: str, tag: str, country: bool, page_size: int) -> list[dict]:
    """Open Food Facts search service (search-a-licious); results sorted by scans, most popular first."""
    key = f"{site}_{tag}_{'in' if country else 'all'}.json"
    cache = RAW / key
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    q = f'categories_tags:"en:{tag}"' + (' AND countries_tags:"en:india"' if country else "")
    params = {"q": q, "page_size": str(max(page_size, 100)),
              "fields": "code,product_name,product_name_en,brands,quantity,product_quantity,product_quantity_unit,"
                        "images,unique_scans_n,categories_tags"}
    url = f"https://search.openfoodfacts.org/search?{urllib.parse.urlencode(params)}"
    for attempt in range(4):
        time.sleep(2)
        try:
            hits = json.loads(get(url)).get("hits", [])
            for h in hits:
                if isinstance(h.get("brands"), list):
                    h["brands"] = ", ".join(h["brands"])
            hits.sort(key=lambda h: -(h.get("unique_scans_n") or 0))
            cache.write_text(json.dumps(hits, ensure_ascii=False), encoding="utf-8")
            print(f"  {tag}{' (India)' if country else ''}: {len(hits)}")
            return hits
        except (json.JSONDecodeError, OSError) as e:
            wait = 10 * (attempt + 1)
            print(f"  {tag} retry in {wait}s ({type(e).__name__})")
            time.sleep(wait)
    return []


S3 = "https://openfoodfacts-images.s3.eu-west-3.amazonaws.com/data"


def front_image_url(p: dict) -> str | None:
    """Raw front photo on the Open Food Facts open-data mirror (the image host itself is not reachable here)."""
    imgs = p.get("images") or {}
    front = imgs.get("front_en") or next((v for k, v in imgs.items() if k.startswith("front")), None)
    imgid = (front or {}).get("imgid")
    if not imgid:
        return None
    code = p["code"]
    folder = code if len(code) <= 8 else "/".join([code.zfill(13)[:3], code.zfill(13)[3:6], code.zfill(13)[6:9], code.zfill(13)[9:]])
    return f"{S3}/{folder}/{imgid}.400.jpg"


def parse_quantity(p: dict) -> tuple[float | None, str]:
    """Return (amount in g or ml, 'g'|'ml')."""
    q = p.get("product_quantity")
    unit = (p.get("product_quantity_unit") or "").lower()
    try:
        if q:
            v = float(q)
            return v, "ml" if unit in ("ml", "l", "cl") else "g"
    except ValueError:
        pass
    text = (p.get("quantity") or "").lower().replace(",", ".")
    m = re.search(r"(\d+(?:\.\d+)?)\s*(kg|g|gm|gms|grams|l|ltr|litre|ml|cl)\b", text)
    if not m:
        return None, "g"
    v, u = float(m.group(1)), m.group(2)
    mult = {"kg": 1000, "l": 1000, "ltr": 1000, "litre": 1000, "cl": 10}.get(u, 1)
    return v * mult, "ml" if u in ("l", "ltr", "litre", "ml", "cl") else "g"


def estimate_size(cat: str, amount: float, aspect: float) -> tuple[int, int, int]:
    """W, H, D in mm from pack contents and the front image's aspect ratio (W/H)."""
    depth_ratio, density, max_h = SHAPE.get(cat, (0.5, 0.8, 300))
    volume_mm3 = amount / density * 1000 * 1.25  # 25% headspace and packaging
    a = min(max(aspect, 0.3), 2.5)
    h = (volume_mm3 / (a * a * depth_ratio)) ** (1 / 3)
    h = min(h, max_h)
    w = a * h
    d = max(25.0, w * depth_ratio)
    # keep volume roughly right if height was capped
    if h == max_h:
        d = max(25.0, volume_mm3 / (w * h))
    return int(round(w / 5) * 5), int(round(h / 5) * 5), int(round(d / 5) * 5)


def clean_name(p: dict) -> str:
    name = (p.get("product_name_en") or p.get("product_name") or "").strip()
    return re.sub(r"\s+", " ", name)


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    IMG.mkdir(parents=True, exist_ok=True)
    out_file = OUT / "catalogue.json"
    catalogue: dict[str, dict] = {}
    if out_file.exists():
        catalogue = {r["gtin"]: r for r in json.loads(out_file.read_text(encoding="utf-8"))}

    only = set(sys.argv[1:])
    for cat, (site, tags) in SOURCES.items():
        if only and cat not in only:
            continue
        have = [r for r in catalogue.values() if r["category"] == cat]
        if len(have) >= PER_CATEGORY:
            continue
        print(f"{cat}: have {len(have)}")
        picked = {r["gtin"] for r in have}
        seen_keys: set = set()
        for country in (True, False):
            for tag in tags:
                if len(picked) >= PER_CATEGORY:
                    break
                for p in search(site, tag, country, 60):
                    if len(picked) >= PER_CATEGORY:
                        break
                    code, name = p.get("code", ""), clean_name(p)
                    url = front_image_url(p) if code else None
                    if not (code.isdigit() and 8 <= len(code) <= 14 and name and url) or code in catalogue:
                        continue
                    if f"en:{tag}" not in (p.get("categories_tags") or []):
                        continue  # only products tagged with this exact category
                    amount, unit = parse_quantity(p)
                    if not amount or amount < 40 or amount > 10000:
                        continue  # skip sample sachets and bulk sacks
                    key = (p.get("brands", "").lower(), name.lower(), round(amount))
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    img_path = IMG / f"{code}.jpg"
                    try:
                        if not img_path.exists():
                            raw = get(url, 30)
                            im = Image.open(io.BytesIO(raw)).convert("RGB")
                            if min(im.size) < 120:
                                continue
                            im.thumbnail((400, 400))
                            im.save(img_path, "JPEG", quality=85)
                        with Image.open(img_path) as im:
                            aspect = im.width / im.height
                    except Exception as e:  # noqa: BLE001 - skip unreadable images
                        print(f"    skip image {code}: {e}")
                        continue
                    w, h, d = estimate_size(cat, amount, aspect)
                    brand = (p.get("brands") or "").split(",")[0].strip() or "Unbranded"
                    rec = {
                        "gtin": code.zfill(13) if len(code) < 13 else code, "source_code": code,
                        "name": name[:80], "brand": brand[:40], "category": cat,
                        "quantity": p.get("quantity") or f"{amount:g} {unit}", "amount": amount, "unit": unit,
                        "width_mm": w, "height_mm": h, "depth_mm": d,
                        "weight_g": int(amount * (1.0 if unit == "g" else 1.03) * 1.08),
                        "liquid": cat in LIQUID, "popularity": int(p.get("unique_scans_n") or 0),
                        "image": f"images/{code}.jpg", "source": site,
                        "source_url": f"https://{SITES[site]}/product/{code}",
                    }
                    catalogue[rec["gtin"]] = rec
                    picked.add(rec["gtin"])
            if len(picked) >= PER_CATEGORY:
                break
        print(f"  -> {cat}: {len(picked)} products")
        out_file.write_text(json.dumps(sorted(catalogue.values(), key=lambda r: (r["category"], r["name"])),
                                       ensure_ascii=False, indent=1), encoding="utf-8")

    counts: dict[str, int] = {}
    for r in catalogue.values():
        counts[r["category"]] = counts.get(r["category"], 0) + 1
    print(json.dumps(counts, indent=0))
    (OUT / "ATTRIBUTION.md").write_text(
        "# Attribution\n\nProduct data and images in this folder come from **Open Food Facts** "
        "(https://world.openfoodfacts.org) and **Open Beauty Facts** (https://world.openbeautyfacts.org).\n\n"
        "- Data: Open Database License (ODbL) 1.0\n- Images: Creative Commons Attribution-ShareAlike (CC BY-SA)\n\n"
        "Used for the demo tenant only (spec 9.2, 10.6). Pack sizes are **estimated** from the declared quantity "
        "and the image aspect ratio; they are not measured. Each record keeps its `source_url`.\n", encoding="utf-8")


if __name__ == "__main__":
    main()
