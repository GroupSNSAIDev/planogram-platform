"""Heuristic auto-fill (spec section 14.1). Deterministic: same inputs, same proposal.

Steps: load anchors and eligible products -> facings from days of supply -> assign shelf levels
(hard rules first, then eye level / heavy low / brand blocks) -> order by brand block -> pack the
free segments between locked anchors -> trim on overflow -> share spare width -> explain each position.

The result is a proposal (a change set), never written directly: the planner accepts or rejects it.
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any

from .context import eligibility
from .geometry import SETTINGS, check_surface, days_of_supply, facings_for_days, max_facings_deep
from .rules import RULE_SET, evaluate, in_scope, priority_brands, rule

ENGINE_VERSION = "autofill-1.0"
PARAMS = {"target_days": 6, "min_facings": 1, "max_facings": 8, "max_facings_fill": 16, "top_seller_share": 0.3, "heavy_g": 1000}
_NS = uuid.UUID("6f1c2a52-6a0b-4b8e-9d3f-2f9f1f3c7a10")


def _segments(surface: dict[str, Any], anchors: list[dict[str, Any]], products: dict[str, Any]) -> list[dict[str, Any]]:
    """Free segments on a shelf between locked anchors: [{start, end, items: []}].

    An item fits while cursor + width <= end; after it, cursor += width + gap.
    """
    gap = SETTINGS["gap_mm"]
    segs, start = [], 0
    for a in sorted(anchors, key=lambda p: p["locked_x_mm"]):
        width = products[a["product_id"]]["width_mm"] * a["facings_wide"]
        segs.append({"start": start, "end": a["locked_x_mm"] - gap, "items": [], "after_anchor": a})
        start = a["locked_x_mm"] + width + gap
    segs.append({"start": start, "end": surface["width_mm"], "items": [], "after_anchor": None})
    return [s for s in segs if s["end"] > s["start"]]


def _seg_used(seg: dict[str, Any]) -> int:
    gap = SETTINGS["gap_mm"]
    return sum(i["width_mm"] * i["facings"] for i in seg["items"]) + gap * max(0, len(seg["items"]) - 1)


def _fits(seg: dict[str, Any], extra: int) -> bool:
    gap = SETTINGS["gap_mm"]
    add = extra + (gap if seg["items"] else 0)
    return seg["start"] + _seg_used(seg) + add <= seg["end"]


def autofill(ctx: dict[str, Any], positions: dict[str, dict[str, Any]], params: dict[str, Any] | None = None) -> dict[str, Any]:
    p_ = {**PARAMS, **(params or {})}
    products, stats = ctx["products"], ctx["stats"]
    section, fixture = ctx["section"], ctx["fixture"]
    surfaces = ctx["surfaces"]
    gap, finger = SETTINGS["gap_mm"], SETTINGS["finger_clearance_mm"]
    priority = set(priority_brands(ctx)) if in_scope("R-12", section["category_code"]) else set()

    anchors = [p for p in positions.values() if p.get("locked") and p["surface_id"] in ctx["surface_by_id"]]
    anchored_products = {a["product_id"] for a in anchors}
    unplaced: list[dict[str, Any]] = []

    # 1. candidates: the section's category, eligible for this fixture
    candidates = []
    for prod in sorted(products.values(), key=lambda pr: pr["sku"]):
        if prod["category_code"] != section["category_code"] or prod["id"] in anchored_products:
            continue
        elig = eligibility(prod, fixture["temperature"], section["image_policy"])
        if elig["status"] in ("blocked", "wrong_temperature"):
            unplaced.append({"product_id": prod["id"], "name": prod["name"], "reason": elig["reason"]})
            continue
        fit_surfaces = [s for s in surfaces
                        if prod["height_mm"] + finger <= s["clear_height_mm"] and prod["depth_mm"] <= s["usable_depth_mm"]
                        and prod["width_mm"] <= s["width_mm"]]
        if not fit_surfaces:
            tallest = max((s["clear_height_mm"] for s in surfaces), default=0)
            unplaced.append({"product_id": prod["id"], "name": prod["name"],
                             "reason": f"Too tall for every shelf: needs {prod['height_mm'] + finger} mm, "
                                       f"largest gap is {tallest} mm (raise a shelf in Fixture & sections)"})
            continue
        st = stats.get(prod["id"], {})
        deep = max_facings_deep(prod["depth_mm"], min(s["usable_depth_mm"] for s in fit_surfaces))
        facings = facings_for_days(st.get("units_per_day", 0.0), p_["target_days"], deep, p_["min_facings"], p_["max_facings"])
        facings = min(facings, max(1, min(s["width_mm"] for s in fit_surfaces) // prod["width_mm"]))  # one position fits one bay
        candidates.append({
            "product": prod, "id": prod["id"], "brand": prod["brand"], "width_mm": prod["width_mm"],
            "deep": deep, "facings": facings, "target_facings": facings,
            "value": st.get("margin_per_day", 0.0), "upd": st.get("units_per_day", 0.0),
            "heavy": (prod.get("weight_g") or 0) >= p_["heavy_g"], "priority": prod["brand"] in priority,
            "fit_ids": {s["id"] for s in fit_surfaces},
        })

    unplaced_pre = list(unplaced)
    candidates.sort(key=lambda c: (-c["value"], c["product"]["sku"]))
    top_n = max(1, round(len(candidates) * p_["top_seller_share"]))
    for rank, c in enumerate(candidates, start=1):
        c["rank"], c["top"] = rank, rank <= top_n

    # 2. shelf levels and their free segments
    levels: dict[int, dict[str, Any]] = {}
    for s in surfaces:
        lv = levels.setdefault(s["level"], {"level": s["level"], "band": s["band"], "height": s["height_from_floor_mm"],
                                            "surfaces": [], "segments": [], "items": []})
        lv["surfaces"].append(s)
        for seg in _segments(s, [a for a in anchors if a["surface_id"] == s["id"]], products):
            seg["surface"] = s
            lv["segments"].append(seg)
    for lv in levels.values():
        lv["capacity"] = sum(seg["end"] - seg["start"] for seg in lv["segments"])
        lv["free"] = lv["capacity"]

    def level_parts(c: dict[str, Any], lv: dict[str, Any]) -> list[tuple[str, float]]:
        """Why a shelf level suits a product: named score parts (shown in the auto-fill explanation)."""
        band, parts = lv["band"], []
        if c["priority"] and band == "eye":
            parts.append(("priority brand at eye level (R-12)", 3.0))
        if c["top"] and band in ("eye", "waist"):
            parts.append((f"top seller at {band} level", 2.0 if band == "eye" else 1.0))
        if c["heavy"]:
            high = lv["height"] > rule("R-07")["params"]["max_height_mm"]
            parts.append(("heavy item kept low (R-07)", -4.0 if high else 1.5))
        if any(i["brand"] == c["brand"] for i in lv["items"]):
            parts.append(("joins its brand block (R-15)", 1.0))
        used = 1 - lv["free"] / max(1, lv["capacity"])
        if used > 0:
            parts.append((f"shelf already {used:.0%} full", -2.5 * used))
        return parts

    def level_score(c: dict[str, Any], lv: dict[str, Any]) -> float:
        return sum(v for _, v in level_parts(c, lv)) - lv["level"] * 0.01  # tie-break: lower level first

    # 3. assign levels (hard: fits height on the whole level; then preferences; then capacity)
    for c in candidates:
        options = [lv for lv in levels.values() if all(s["id"] in c["fit_ids"] for s in lv["surfaces"])]
        c["no_fit_levels"] = sorted(lv["level"] for lv in levels.values() if lv not in options)
        c["scores"] = {lv["level"]: round(level_score(c, lv), 2) for lv in options}
        c["parts_by_level"] = {lv["level"]: level_parts(c, lv) for lv in options}
        options.sort(key=lambda lv: -level_score(c, lv))
        chosen = None
        for want in (c["facings"], 1):
            need = c["width_mm"] * want + gap
            chosen = next((lv for lv in options if lv["free"] >= need), None)
            if chosen:
                c["facings"] = want
                break
        if chosen is None:
            unplaced.append({"product_id": c["id"], "name": c["product"]["name"],
                             "reason": "No space left on the shelves where it fits"})
            continue
        c["level"] = chosen
        chosen["items"].append(c)
        chosen["free"] -= c["width_mm"] * c["facings"] + gap

    # 4-5. order each level by brand block and pack its segments; trim on overflow
    trims = 0
    for lv in sorted(levels.values(), key=lambda lv: lv["level"]):
        brand_value: dict[str, float] = defaultdict(float)
        for c in lv["items"]:
            brand_value[c["brand"]] += c["value"]
        while True:
            order = sorted(lv["items"], key=lambda c: (-brand_value[c["brand"]], c["brand"],
                                                       -c["product"]["height_mm"], c["product"]["sku"]))
            for seg in lv["segments"]:
                seg["items"] = []
            segs = lv["segments"]
            for c in order:
                c["facings"] = min(c["facings"], max(1, lv["surfaces"][0]["width_mm"] // c["width_mm"]))
            # spread the level's products over all its bays in proportion, so no bay is left empty
            need = sum(c["width_mm"] * c["facings"] + gap for c in order)
            ratio = min(1.0, need / max(1, lv["capacity"]))
            overflow, si = [], 0
            for c in order:
                w = c["width_mm"] * c["facings"]

                def ok(k: int, use_share: bool) -> bool:
                    seg = segs[k]
                    if seg["surface"]["id"] not in c["fit_ids"] or not _fits(seg, w):
                        return False
                    if not use_share or not seg["items"] or k == len(segs) - 1:
                        return True
                    share_end = seg["start"] + (seg["end"] - seg["start"]) * ratio
                    return seg["start"] + _seg_used(seg) + gap + w / 2 <= share_end

                # keep the block order: only search forward from the current segment
                j = next((k for k in range(si, len(segs)) if ok(k, True)), None)
                if j is None:
                    j = next((k for k in range(si, len(segs)) if ok(k, False)), None)
                if j is None:
                    overflow.append(c)
                else:
                    segs[j]["items"].append(c)
                    si = j
            if not overflow:
                break
            shrinkable = sorted((c for c in lv["items"] if c["facings"] > 1), key=lambda c: (c["value"], c["product"]["sku"]))
            if shrinkable:
                shrinkable[0]["facings"] -= 1
                shrinkable[0]["trimmed"] = shrinkable[0].get("trimmed", 0) + 1
                trims += 1
                continue
            drop = min(overflow, key=lambda c: (c["value"], c["product"]["sku"]))
            lv["items"].remove(drop)
            unplaced.append({"product_id": drop["id"], "name": drop["product"]["name"],
                             "reason": "Trimmed: not enough space on its shelf level"})

    # 6. share spare width: extra facings by value, round-robin, while they fit
    for c in candidates:
        c["packed_facings"] = c["facings"]
    for lv in levels.values():
        for seg in lv["segments"]:
            grown = True
            while grown:
                grown = False
                for c in sorted(seg["items"], key=lambda c: (-c["value"], c["product"]["sku"])):
                    if c["facings"] < p_["max_facings_fill"] and _fits(seg, c["width_mm"]):
                        c["facings"] += 1
                        grown = True

    # 6b. a bay left empty continues its neighbour's product (keeps the brand block, fills the shelf)
    for lv in levels.values():
        segs = lv["segments"]
        for k, seg in enumerate(segs):
            if seg["items"]:
                continue
            nb = segs[k - 1]["items"][-1] if k > 0 and segs[k - 1]["items"] else (
                segs[k + 1]["items"][0] if k + 1 < len(segs) and segs[k + 1]["items"] else None)
            if nb is None or seg["surface"]["id"] not in nb["fit_ids"]:
                continue
            n = min(p_["max_facings_fill"], (seg["end"] - seg["start"] + gap) // (nb["width_mm"] + gap) if nb["width_mm"] else 0)
            n = max(0, min(n, (seg["end"] - seg["start"]) // nb["width_mm"]))
            if n >= 1:
                seg["items"].append({**nb, "facings": n, "continuation": True})

    # 7. build positions with a reason for each
    new_positions: dict[str, dict[str, Any]] = {}
    for s in surfaces:
        row: list[tuple[int, dict[str, Any]]] = [(a["locked_x_mm"], a) for a in anchors if a["surface_id"] == s["id"]]
        for seg in (sg for lv in levels.values() for sg in lv["segments"] if sg["surface"]["id"] == s["id"]):
            x = seg["start"]
            for c in seg["items"]:
                pid = str(uuid.uuid5(_NS, f"{section['id']}/{c['id']}" + (f"/{s['id']}" if c.get("continuation") else "")))
                reason, rule_ids = _explain(c, s, p_)
                if c.get("continuation"):
                    reason = f"Continues its {c['brand']} block into an otherwise empty bay (R-15); " + reason.split("; ", 2)[-1]
                row.append((x, {
                    "id": pid, "surface_id": s["id"], "product_id": c["id"], "seq": 0, "x_mm": x,
                    "facings_wide": c["facings"], "facings_high": 1, "facings_deep": c["deep"],
                    "placed_by": ENGINE_VERSION, "reason": reason, "rule_ids": rule_ids,
                    "locked": False, "locked_x_mm": None,
                }))
                x += c["width_mm"] * c["facings"] + gap
        for seq, (_, pos) in enumerate(sorted(row, key=lambda t: (t[0], t[1]["id"]))):
            new_positions[pos["id"]] = {**pos, "seq": seq}
        result = check_surface(s, s["clear_height_mm"], s["bay_has_door"], fixture["temperature"],
                               [p for p in new_positions.values() if p["surface_id"] == s["id"]], products)
        for pid, x in result["x_mm"].items():
            new_positions[pid] = {**new_positions[pid], "x_mm": x}

    evaluation = evaluate(ctx, new_positions)
    placed_ids = {p["product_id"] for p in new_positions.values()}
    decisions = {}
    for c in candidates:
        lv = c.get("level")
        if lv is None or c["id"] not in placed_ids:
            continue
        decisions[c["id"]] = {
            "rank": c["rank"], "top_seller": c["top"], "priority_brand": c["priority"], "heavy": c["heavy"],
            "units_per_day": c["upd"], "margin_per_day": round(c["value"], 2), "facings_deep": c["deep"],
            "target_facings": c["target_facings"], "packed_facings": c.get("packed_facings", c["facings"]),
            "final_facings": c["facings"], "trimmed": c.get("trimmed", 0),
            "level": lv["level"], "band": lv["band"], "level_scores": c["scores"],
            "why_level": [{"reason": r, "points": round(v, 2)} for r, v in c["parts_by_level"].get(lv["level"], [])],
            "too_tall_for_levels": c["no_fit_levels"],
        }
    cat_name = ctx["category"]["name"] if ctx.get("category") else section["category_code"]
    skipped = sorted({u["reason"].split(":")[0] for u in unplaced_pre})
    trace = [
        {"step": 1, "title": "Choose candidates",
         "detail": f"{len(candidates)} products of {cat_name} can go on this {fixture['temperature']} fixture; "
                   f"{len(unplaced_pre)} cannot ({', '.join(skipped) or 'none'})."
                   + (f" {len(anchors)} placement-locked product(s) stay exactly where they are." if anchors else "")},
        {"step": 2, "title": "Facings from days of supply",
         "detail": f"facings = ceil(units per day x {p_['target_days']} days / units per facing), between {p_['min_facings']} "
                   f"and {p_['max_facings']}; units per facing = how many fit front to back on the shelf."},
        {"step": 3, "title": "Rank by margin",
         "detail": f"Products are ranked by margin per day. The top {top_n} count as top sellers. "
                   f"Priority brands (R-12, the section's two best-selling brands): {', '.join(sorted(priority)) or 'none'}."},
        {"step": 4, "title": "Pick a shelf level for each product",
         "detail": "Only levels where the product fits in height are allowed. Then: priority brand at eye level +3, top seller at "
                   "eye +2 / waist +1, heavy item (1 kg or more) low +1.5 or high -4, next to its own brand +1, minus up to 2.5 for "
                   "how full the level already is. The best-scoring level with room wins."},
        {"step": 5, "title": "Order and pack each shelf",
         "detail": "Each level is ordered by brand block (best-selling brand first, tallest first inside a brand) and spread across "
                   f"all bays, flowing around locked products. {trims} facing(s) were trimmed from low sellers to make everything fit."},
        {"step": 6, "title": "Share spare space",
         "detail": f"Leftover width on each shelf goes to the best sellers there, one facing at a time (up to {p_['max_facings_fill']})."},
        {"step": 7, "title": "Score and explain",
         "detail": f"The result is checked with every rule: {evaluation['hard_breaks']} hard breaks, score {evaluation['score']}. "
                   "Nothing is saved until you accept."},
    ]
    return {
        "engine_version": ENGINE_VERSION, "rule_set": RULE_SET["id"], "params": p_,
        "positions": sorted(new_positions.values(), key=lambda p: (p["surface_id"], p["seq"])),
        "unplaced": sorted(unplaced, key=lambda u: u["name"]),
        "anchors": [a["id"] for a in anchors],
        "evaluation": evaluation,
        "trace": trace,
        "decisions": decisions,
        "priority_brands": sorted(priority),
    }


def _explain(c: dict[str, Any], s: dict[str, Any], p_: dict[str, Any]) -> tuple[str, list[str]]:
    band, parts, ids = s["band"], [], []
    if c["priority"] and band == "eye":
        parts.append(f"Eye level (R-12, priority brand {c['brand']})")
        ids.append("R-12")
    elif c["top"] and band in ("eye", "waist"):
        parts.append(f"{band.capitalize()} level: top seller (#{c['rank']} by margin)")
    elif c["heavy"] and s["height_from_floor_mm"] <= rule("R-07")["params"]["max_height_mm"]:
        parts.append(f"Low shelf: heavy item {c['product']['weight_g']:,} g (R-07)")
        ids.append("R-07")
    else:
        parts.append(f"{band.capitalize()} band, rank #{c['rank']} by margin")
    parts.append(f"{c['brand']} block (R-15)")
    ids.append("R-15")
    total_units = c["facings"] * c["deep"]
    dos = days_of_supply(total_units, c["upd"])
    parts.append(f"{c['facings']} facings × {c['deep']} deep = {total_units} units ≈ {dos:.1f} days of supply")
    ids.append("R-30")
    return "; ".join(parts), ids
