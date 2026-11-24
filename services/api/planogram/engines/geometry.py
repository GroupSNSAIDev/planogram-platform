"""Shelf geometry and fit checks (spec section 8.4). Pure: dicts in, dicts out.

Mirrored in apps/web/src/geometry/geometry.ts. Both are tested against
packages/contracts/golden/*.json, so change both together and add a golden case.

Units: millimetres and grams. Orientation: front only in the POC
(x across = width, y up = height, z deep = depth).
"""
from __future__ import annotations

import math
from typing import Any

SETTINGS: dict[str, int] = {
    "gap_mm": 2,                  # gap between neighbouring positions on a shelf
    "finger_clearance_mm": 25,    # space above the top of a product
    "back_clearance_mm": 10,
    "door_clearance_mm": 20,      # depth lost behind a glass door
    "shelf_thickness_mm": 15,
    "top_shelf_headroom_mm": 250,  # how far above the fixture top the top shelf may be merchandised
    "min_aisle_mm": 900,
    "door_keepout_mm": 1500,
}

# (lower bound in mm, band name); spec: floor < 400, knee 400-800, waist 800-1200, eye 1200-1600, top > 1600
EYE_BANDS: list[tuple[int, str]] = [(0, "floor"), (400, "knee"), (800, "waist"), (1200, "eye"), (1601, "top")]


def eye_band(height_mm: int) -> str:
    band = "floor"
    for lower, name in EYE_BANDS:
        if height_mm >= lower:
            band = name
    return band


def clear_heights(surface_heights: list[int], bay_height_mm: int) -> list[int]:
    """Clear height above each surface, in the same order as the input heights."""
    order = sorted(range(len(surface_heights)), key=lambda i: surface_heights[i])
    out = [0] * len(surface_heights)
    for rank, i in enumerate(order):
        h = surface_heights[i]
        if rank + 1 < len(order):
            ceiling = surface_heights[order[rank + 1]]
        else:
            ceiling = bay_height_mm + SETTINGS["top_shelf_headroom_mm"]
        out[i] = ceiling - h - SETTINGS["shelf_thickness_mm"]
    return out


def usable_depth(surface_depth_mm: int, has_door: bool) -> int:
    clearance = SETTINGS["door_clearance_mm"] if has_door else SETTINGS["back_clearance_mm"]
    return surface_depth_mm - clearance


def max_facings_deep(product_depth_mm: int, usable_depth_mm: int) -> int:
    if product_depth_mm <= 0:
        return 1
    return max(1, usable_depth_mm // product_depth_mm)


def units(p: dict[str, Any]) -> int:
    return p["facings_wide"] * p["facings_high"] * p["facings_deep"]


def position_width(p: dict[str, Any], product: dict[str, Any]) -> int:
    return product["width_mm"] * p["facings_wide"]


def check_surface(
    surface: dict[str, Any],
    clear_height_mm: int,
    has_door: bool,
    fixture_temperature: str,
    positions: list[dict[str, Any]],
    products: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Lay out one shelf and check every fit rule.

    positions: dicts with id, product_id, seq, facings_wide/high/deep, locked, locked_x_mm.
    Locked positions with locked_x_mm are anchors: their left edge never moves.

    Returns {"x_mm": {id: x}, "used_width_mm": int, "issues": [{code, target, message, data}]}.
    Issue codes: FIT_W, FIT_H, FIT_D, STACK, LOAD, TEMP, ANCHOR.
    """
    gap = SETTINGS["gap_mm"]
    issues: list[dict[str, Any]] = []
    x_by_id: dict[str, int] = {}
    cursor = 0
    right_edge = 0
    load_g = 0
    depth_avail = usable_depth(surface["depth_mm"], has_door)

    for p in sorted(positions, key=lambda q: (q["seq"], q["id"])):
        prod = products[p["product_id"]]
        width = position_width(p, prod)
        if p.get("locked") and p.get("locked_x_mm") is not None:
            anchor = p["locked_x_mm"]
            if cursor > anchor:
                issues.append({
                    "code": "ANCHOR", "target": p["id"],
                    "message": f"needs {cursor - anchor} mm more; {prod['name']} is locked at {anchor} mm",
                    "data": {"needed_mm": cursor - anchor, "locked_x_mm": anchor},
                })
            x = anchor
        else:
            x = cursor
        x_by_id[p["id"]] = x
        cursor = x + width + gap
        right_edge = max(right_edge, x + width)

        height_needed = prod["height_mm"] * p["facings_high"] + SETTINGS["finger_clearance_mm"]
        if height_needed > clear_height_mm:
            issues.append({
                "code": "FIT_H", "target": p["id"],
                "message": f"{prod['name']} needs {height_needed} mm height, shelf has {clear_height_mm} mm",
                "data": {"needed_mm": height_needed, "available_mm": clear_height_mm},
            })
        depth_needed = prod["depth_mm"] * p["facings_deep"]
        if depth_needed > depth_avail:
            issues.append({
                "code": "FIT_D", "target": p["id"],
                "message": f"{prod['name']} needs {depth_needed} mm depth, shelf has {depth_avail} mm",
                "data": {"needed_mm": depth_needed, "available_mm": depth_avail},
            })
        if p["facings_high"] > 1 and not (prod.get("can_stack") and p["facings_high"] <= (prod.get("max_stack") or 1)):
            issues.append({
                "code": "STACK", "target": p["id"],
                "message": f"{prod['name']} cannot be stacked {p['facings_high']} high",
                "data": {"facings_high": p["facings_high"]},
            })
        if prod["temperature"] != fixture_temperature:
            issues.append({
                "code": "TEMP", "target": p["id"],
                "message": f"{prod['name']} is {prod['temperature']}, fixture is {fixture_temperature}",
                "data": {"product": prod["temperature"], "fixture": fixture_temperature},
            })
        load_g += (prod.get("weight_g") or 0) * units(p)

    if right_edge > surface["width_mm"]:
        issues.append({
            "code": "FIT_W", "target": surface["id"],
            "message": f"shelf over-filled by {right_edge - surface['width_mm']} mm",
            "data": {"used_mm": right_edge, "available_mm": surface["width_mm"]},
        })
    max_load = surface.get("max_load_g")
    if max_load and load_g > max_load:
        issues.append({
            "code": "LOAD", "target": surface["id"],
            "message": f"load {load_g / 1000:.1f} kg exceeds {max_load / 1000:.0f} kg",
            "data": {"load_g": load_g, "max_load_g": max_load},
        })
    return {"x_mm": x_by_id, "used_width_mm": right_edge, "issues": issues}


def days_of_supply(units_on_shelf: int, units_per_day: float) -> float:
    return units_on_shelf / max(units_per_day, 0.01)


def facings_for_days(units_per_day: float, target_days: float, units_per_facing: int, lo: int, hi: int) -> int:
    need = math.ceil(units_per_day * target_days / max(units_per_facing, 1))
    return max(lo, min(hi, need))
