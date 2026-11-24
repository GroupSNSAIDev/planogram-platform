"""Rules engine (spec section 13), POC subset. Deterministic and pure.

Hard rules block approval; soft rules give a weighted score:
    score = 100 * sum(weight_i * score_i) / sum(weight_i)   over soft rules that apply.
Rules are data (RULE_SET); engines are code.
"""
from __future__ import annotations

from collections import defaultdict
from itertools import groupby
from typing import Any

from .context import eligibility
from .geometry import check_surface, days_of_supply, units

RULE_SET: dict[str, Any] = {
    "id": "breakfast-v5",
    "name": "Breakfast & packaged food v5",
    "rules": [
        {"id": "R-01", "type": "fit", "severity": "hard", "name": "Products fit the shelf (width, height, depth, stacking)"},
        {"id": "R-02", "type": "temperature", "severity": "hard", "name": "Product temperature matches fixture"},
        {"id": "R-03", "type": "eligibility", "severity": "hard", "name": "Verified sizes and reviewed safety flags"},
        {"id": "R-04", "type": "section_category", "severity": "hard", "name": "Products belong to the section's category"},
        {"id": "R-05", "type": "load", "severity": "hard", "name": "Shelf load under limit"},
        {"id": "R-06", "type": "lock", "severity": "hard", "name": "Locked products keep their place"},
        {"id": "R-12", "type": "eye_level", "severity": "soft", "weight": 3, "name": "Priority brands at eye level",
         "params": {"brands": "top_by_sales", "top_n": 2, "min_share": 0.6}},
        {"id": "R-07", "type": "heavy_low", "severity": "soft", "weight": 2, "name": "Heavy items low",
         "params": {"weight_g": 1000, "max_height_mm": 1199}},
        {"id": "R-15", "type": "blocking", "severity": "soft", "weight": 2, "name": "Brand blocks kept together",
         "params": {"group_by": "brand"}},
        {"id": "R-30", "type": "days_of_supply", "severity": "soft", "weight": 3, "name": "Enough stock between refills",
         "params": {"target_days": 5}},
        {"id": "R-40", "type": "share_of_shelf", "severity": "soft", "weight": 2, "name": "Space share follows sales share",
         "params": {"group_by": "brand"}},
        {"id": "R-50", "type": "assortment", "severity": "soft", "weight": 1, "name": "Ranged products are on the shelf"},
    ],
}

GEOMETRY_RULE = {"FIT_W": "R-01", "FIT_H": "R-01", "FIT_D": "R-01", "STACK": "R-01",
                 "TEMP": "R-02", "LOAD": "R-05", "ANCHOR": "R-06"}


def rule(rule_id: str) -> dict[str, Any]:
    return next(r for r in RULE_SET["rules"] if r["id"] == rule_id)


def priority_brands(ctx: dict[str, Any]) -> list[str]:
    """R-12 brands: a fixed list, or the section category's top brands by sales."""
    params = rule("R-12")["params"]
    if isinstance(params["brands"], list):
        return list(params["brands"])
    sales: dict[str, float] = defaultdict(float)
    for pr in ctx["products"].values():
        if pr["category_code"] == ctx["section"]["category_code"]:
            sales[pr["brand"]] += ctx["stats"].get(pr["id"], {}).get("revenue_per_day", 0.0)
    return sorted(sales, key=lambda b: (-sales[b], b))[: params["top_n"]] if len(sales) > params["top_n"] else []


def in_scope(rule_id: str, category_code: str) -> bool:
    cats = rule(rule_id).get("scope", {}).get("categories")
    return not cats or category_code in cats


def _finding(rule_id: str, target: str | None, message: str, severity: str | None = None, **data: Any) -> dict[str, Any]:
    r = rule(rule_id)
    return {"rule_id": rule_id, "type": r["type"], "severity": severity or r["severity"],
            "target": target, "message": message, "data": data}


def surface_label(s: dict[str, Any]) -> str:
    return f"Bay {s['bay_idx']} · Shelf {s['level']}"


def evaluate(ctx: dict[str, Any], positions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Validate a section's positions. Returns findings, score, hard_breaks and summary stats."""
    products, stats = ctx["products"], ctx["stats"]
    section, fixture = ctx["section"], ctx["fixture"]
    findings: list[dict[str, Any]] = []
    by_surface: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for p in positions.values():
        by_surface[p["surface_id"]].append(p)

    # ---- hard rules
    capacity = sum(s["width_mm"] for s in ctx["surfaces"])
    used = 0
    for sid, row in by_surface.items():
        surface = ctx["surface_by_id"].get(sid)
        if surface is None:
            for p in row:
                findings.append(_finding("R-01", p["id"], f"{products[p['product_id']]['name']} is outside this section"))
            continue
        result = check_surface(surface, surface["clear_height_mm"], surface["bay_has_door"],
                               fixture["temperature"], row, products)
        used += min(result["used_width_mm"], surface["width_mm"])
        for issue in result["issues"]:
            msg = issue["message"]
            if issue["target"] == sid:
                msg = f"{surface_label(surface)}: {msg}"
            findings.append(_finding(GEOMETRY_RULE[issue["code"]], issue["target"], msg, code=issue["code"], **issue["data"]))
    for p in positions.values():
        prod = products[p["product_id"]]
        elig = eligibility(prod, None, section["image_policy"])
        if elig["status"] == "blocked":
            findings.append(_finding("R-03", p["id"], f"{prod['name']}: {elig['reason']}"))
        elif elig["status"] == "estimated":
            findings.append(_finding("R-03", p["id"], f"{prod['name']}: size estimated (drafts only)", severity="info"))
        if prod["category_code"] != section["category_code"]:
            findings.append(_finding("R-04", p["id"], f"{prod['name']} is not in this section's category"))

    # ---- soft rules
    scores: dict[str, float] = {}
    placed = [p for p in positions.values() if p["surface_id"] in ctx["surface_by_id"]]
    surf = ctx["surface_by_id"]

    # R-12 eye level: priority brands' share of the eye-level band
    r12 = {**rule("R-12")["params"], "brands": priority_brands(ctx)}
    eye = [p for p in placed if surf[p["surface_id"]]["band"] == "eye"]
    eye_width = sum(products[p["product_id"]]["width_mm"] * p["facings_wide"] for p in eye)
    if eye_width and r12["brands"] and in_scope("R-12", section["category_code"]):
        prio = sum(products[p["product_id"]]["width_mm"] * p["facings_wide"] for p in eye
                   if products[p["product_id"]]["brand"] in r12["brands"])
        share = prio / eye_width
        scores["R-12"] = min(1.0, share / r12["min_share"])
        if share < r12["min_share"]:
            findings.append(_finding("R-12", None, f"Priority brands ({', '.join(r12['brands'])}) take "
                                     f"{share:.0%} of the eye-level band (target {r12['min_share']:.0%})", share=share))

    # R-07 heavy low
    r07 = rule("R-07")["params"]
    heavy = [p for p in placed if (products[p["product_id"]].get("weight_g") or 0) >= r07["weight_g"]]
    if heavy:
        bad = [p for p in heavy if surf[p["surface_id"]]["height_from_floor_mm"] > r07["max_height_mm"]]
        scores["R-07"] = 1 - len(bad) / len(heavy)
        for p in bad:
            prod, s = products[p["product_id"]], surf[p["surface_id"]]
            findings.append(_finding("R-07", p["id"], f"Heavy item high: {prod['name']} ({prod['weight_g']:,} g) "
                                     f"on {surface_label(s)} at {s['height_from_floor_mm']:,} mm"))

    # R-15 brand blocking: per shelf, brand changes vs the minimum possible
    block_scores = []
    for sid, row in by_surface.items():
        if sid not in surf or not row:
            continue
        brands = [products[p["product_id"]]["brand"] for p in sorted(row, key=lambda q: q["seq"])]
        switches = sum(1 for a, b in zip(brands, brands[1:]) if a != b)
        ideal = len(set(brands)) - 1
        block_scores.append(1.0 if switches == 0 else ideal / switches)
        if switches > ideal:
            runs = [b for b, _ in groupby(brands)]
            split = sorted({b for b in runs if runs.count(b) > 1})
            findings.append(_finding("R-15", sid, f"{surface_label(surf[sid])}: brand blocks broken "
                                     f"({', '.join(split)} in more than one place)"))
    if block_scores:
        scores["R-15"] = sum(block_scores) / len(block_scores)

    # R-30 days of supply per product
    r30 = rule("R-30")["params"]
    units_by_product: dict[str, int] = defaultdict(int)
    for p in placed:
        units_by_product[p["product_id"]] += units(p)
    if units_by_product:
        ok = 0
        for pid, u in sorted(units_by_product.items()):
            upd = stats.get(pid, {}).get("units_per_day", 0.0)
            dos = days_of_supply(u, upd)
            if dos >= r30["target_days"]:
                ok += 1
            else:
                findings.append(_finding("R-30", pid, f"{products[pid]['name']}: {dos:.1f} days of supply "
                                         f"(target {r30['target_days']})", days=round(dos, 1)))
        scores["R-30"] = ok / len(units_by_product)

    # R-40 share of shelf vs share of sales, by brand
    space: dict[str, float] = defaultdict(float)
    for p in placed:
        prod = products[p["product_id"]]
        space[prod["brand"]] += prod["width_mm"] * p["facings_wide"]
    sales: dict[str, float] = defaultdict(float)
    ranged = [pr for pr in products.values() if pr["category_code"] == section["category_code"]]
    for pr in ranged:
        sales[pr["brand"]] += stats.get(pr["id"], {}).get("revenue_per_day", 0.0)
    total_space, total_sales = sum(space.values()), sum(sales.values())
    if total_space and total_sales:
        brands = sorted(set(space) | set(sales))
        diffs = {b: space.get(b, 0) / total_space - sales.get(b, 0) / total_sales for b in brands}
        scores["R-40"] = max(0.0, 1 - 0.5 * sum(abs(d) for d in diffs.values()))
        worst = max(brands, key=lambda b: abs(diffs[b]))
        if abs(diffs[worst]) > 0.05:
            findings.append(_finding("R-40", None, f"{worst} has {space.get(worst, 0) / total_space:.0%} of the space "
                                     f"but {sales.get(worst, 0) / total_sales:.0%} of sales"))

    # R-50 assortment: eligible ranged products that are not on the shelf
    eligible = [pr for pr in ranged
                if eligibility(pr, fixture["temperature"], section["image_policy"])["status"] in ("eligible", "estimated")]
    if eligible:
        on_shelf = {p["product_id"] for p in placed}
        missing = [pr for pr in eligible if pr["id"] not in on_shelf]
        scores["R-50"] = 1 - len(missing) / len(eligible)
        if missing:
            findings.append(_finding("R-50", None, f"{len(missing)} ranged product(s) not on the shelf",
                                     products=[pr["id"] for pr in missing]))

    weights = {r["id"]: r.get("weight", 0) for r in RULE_SET["rules"]}
    total_w = sum(weights[k] for k in scores)
    score = round(100 * sum(weights[k] * v for k, v in scores.items()) / total_w, 1) if total_w and placed else 0.0
    hard = [f for f in findings if f["severity"] == "hard"]
    soft = [f for f in findings if f["severity"] == "soft"]
    return {
        "findings": hard + soft + [f for f in findings if f["severity"] == "info"],
        "score": score,
        "rule_scores": {k: round(v, 3) for k, v in scores.items()},
        "hard_breaks": len(hard),
        "soft_findings": len(soft),
        "summary": {
            "positions": len(placed), "skus": len({p["product_id"] for p in placed}),
            "facings": sum(p["facings_wide"] * p["facings_high"] for p in placed),
            "units": sum(units(p) for p in placed),
            "used_mm": used, "capacity_mm": capacity,
            "fill_pct": round(100 * used / capacity, 1) if capacity else 0.0,
        },
    }


# Plain-English meaning of each rule, shown on the Rules page and in the auto-fill explanation.
RULE_TEXT: dict[str, dict[str, str]] = {
    "R-01": {"what": "Every product must physically fit: its width × facings within the shelf, its height plus 25 mm finger space "
                     "under the shelf above, its depth × facings within the shelf depth (minus 10 mm, or 20 mm behind a door), "
                     "and it may only be stacked if it is stackable.",
             "measure": "Pass / fail per product and shelf."},
    "R-02": {"what": "Chilled products only on chilled fixtures, frozen only on frozen, ambient only on ambient (food safety).",
             "measure": "Pass / fail per product."},
    "R-03": {"what": "Products need sizes and reviewed safety flags (liquid, fragile, age-restricted, hazardous). Estimated sizes are "
                     "allowed in drafts with a warning. If the section requires pictures, products without one are blocked.",
             "measure": "Pass / fail per product."},
    "R-04": {"what": "Products belong to the category that owns the section (for example only breakfast cereals in G03-A-01).",
             "measure": "Pass / fail per product."},
    "R-05": {"what": "The total weight on a shelf stays under its load limit.", "measure": "Pass / fail per shelf."},
    "R-06": {"what": "A placement-locked product keeps its shelf, order, facings and left edge. Edits that would push it are refused.",
             "measure": "Pass / fail per locked product."},
    "R-12": {"what": "The section's two best-selling brands should take at least 60% of the eye-level band (1,200–1,600 mm), "
                     "where shoppers look first.",
             "measure": "Share of eye-level width ÷ 60%, capped at 100%."},
    "R-07": {"what": "Heavy items (1 kg or more) belong on shelves below 1,200 mm: easier and safer to lift.",
             "measure": "Share of heavy items that are low."},
    "R-15": {"what": "Each brand should form one block on a shelf instead of being scattered, so shoppers find it quickly.",
             "measure": "Fewest possible brand changes ÷ actual brand changes, per shelf."},
    "R-30": {"what": "Each product should hold at least 5 days of its sales on the shelf, so it does not run out between refills.",
             "measure": "Share of products with ≥ 5 days of supply."},
    "R-40": {"what": "Each brand's share of shelf space should be close to its share of sales.",
             "measure": "1 − half the sum of the differences between space share and sales share."},
    "R-50": {"what": "Every ranged, eligible product of the category should be on the shelf.",
             "measure": "Share of eligible products that are placed."},
}


def rules_catalogue() -> dict[str, Any]:
    from .autofill import ENGINE_VERSION, PARAMS
    return {
        "rule_set": {"id": RULE_SET["id"], "name": RULE_SET["name"]},
        "rules": [{**r, **RULE_TEXT.get(r["id"], {})} for r in RULE_SET["rules"]],
        "score_formula": "score = 100 × Σ(weight × rule score) ÷ Σ weight, over the soft rules that apply. Hard rules block approval.",
        "autofill": {"engine_version": ENGINE_VERSION, "params": PARAMS},
    }
