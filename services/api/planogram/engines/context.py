"""Planning context for one section, and product eligibility (spec section 8.6). Pure."""
from __future__ import annotations

from typing import Any

from .geometry import clear_heights, eye_band, usable_depth


def eligibility(product: dict[str, Any], fixture_temperature: str | None = None,
                image_policy: str = "placeholder_ok") -> dict[str, Any]:
    """Can this product be placed? Returns {"status", "reason", "badges"}.

    status: eligible | estimated (drafts only, with a badge) | wrong_temperature (placing it is a
    hard break) | blocked (cannot be placed at all).
    """
    badges: list[str] = []
    if not product.get("has_image"):
        badges.append("no_image")
    if not all(product.get(k) for k in ("width_mm", "height_mm", "depth_mm")):
        return {"status": "blocked", "reason": "Sizes missing", "badges": badges}
    if not product.get("safety_reviewed"):
        return {"status": "blocked", "reason": "Safety flags not reviewed", "badges": badges}
    if image_policy == "required" and not product.get("has_image"):
        return {"status": "blocked", "reason": "Section requires a front image", "badges": badges}
    if fixture_temperature and product["temperature"] != fixture_temperature:
        return {"status": "wrong_temperature",
                "reason": f"{product['temperature'].capitalize()} product, {fixture_temperature} fixture",
                "badges": badges}
    if not product.get("dims_verified"):
        if product.get("dims_source") == "estimated":
            badges.append("size_estimated")
            return {"status": "estimated", "reason": "Size estimated · drafts only", "badges": badges}
        return {"status": "blocked", "reason": "Sizes not verified", "badges": badges}
    return {"status": "eligible", "reason": None, "badges": badges}


def build_context(layout: dict[str, Any], section_id: str, products: dict[str, dict[str, Any]],
                  stats: dict[str, dict[str, Any]], categories: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Everything the rules and auto-fill engines need for one section."""
    section = layout["sections"][section_id]
    fixture = layout["fixtures"][section["fixture_id"]]
    bays = sorted(
        (b for b in layout["bays"].values()
         if b["fixture_id"] == fixture["id"] and b["side"] == section["side"]
         and section["bay_from"] <= b["idx"] <= section["bay_to"]),
        key=lambda b: b["idx"])
    surfaces: list[dict[str, Any]] = []
    for bay in bays:
        own = sorted((s for s in layout["surfaces"].values() if s["bay_id"] == bay["id"]),
                     key=lambda s: s["height_from_floor_mm"])
        shelves = [s for s in own if s["kind"] == "shelf"]
        clears = clear_heights([s["height_from_floor_mm"] for s in shelves], bay["height_mm"])
        for level, (s, clear) in enumerate(zip(shelves, clears), start=1):
            surfaces.append({
                **s, "bay_idx": bay["idx"], "bay_has_door": bay["has_door"], "bay_height_mm": bay["height_mm"],
                "level": level, "clear_height_mm": clear, "band": eye_band(s["height_from_floor_mm"]),
                "usable_depth_mm": usable_depth(s["depth_mm"], bay["has_door"]),
            })
    return {
        "section": section, "fixture": fixture, "category": categories.get(section["category_code"]),
        "bays": bays, "surfaces": surfaces, "surface_by_id": {s["id"]: s for s in surfaces},
        "products": products, "stats": stats,
    }
