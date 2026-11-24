"""Floor checks: overlaps, aisle widths, blocked doors, out of bounds (spec FR-08, section 8.7).

Rotations are multiples of 90 degrees, so a fixture's footprint is exactly its axis-aligned
rectangle (x_mm, y_mm, footprint_w_mm, footprint_d_mm). Mirrored in apps/web/src/geometry/layout.ts.
"""
from __future__ import annotations

from typing import Any

from .geometry import SETTINGS

Rect = tuple[int, int, int, int]  # x1, y1, x2, y2

DOOR_KINDS = {"entrance", "exit", "stockroom_door"}
SOLID_LANDMARKS = {"pillar"}


def fixture_rect(f: dict[str, Any]) -> Rect:
    return (f["x_mm"], f["y_mm"], f["x_mm"] + f["footprint_w_mm"], f["y_mm"] + f["footprint_d_mm"])


def landmark_rect(lm: dict[str, Any]) -> Rect:
    x, y, w, h = lm["rect"]
    return (x, y, x + w, y + h)


def overlap_area(a: Rect, b: Rect) -> int:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return w * h if w > 0 and h > 0 else 0


def _faces(f: dict[str, Any]) -> set[str]:
    return set((f.get("faces") or "").split("/")) & {"N", "E", "S", "W"}


def aisle_gap(fa: dict[str, Any], a: Rect, fb: dict[str, Any], b: Rect) -> int | None:
    """Width of the aisle between two fixtures, if a merchandised face opens onto it.

    Fixtures side by side along a wall, or free-standing bins and pallets, have gaps that are
    not shopping aisles, so they are not checked.
    """
    x_overlap = min(a[2], b[2]) - max(a[0], b[0])
    y_overlap = min(a[3], b[3]) - max(a[1], b[1])
    if x_overlap > 0 and y_overlap <= 0:      # one above the other
        upper, lower = (fa, fb) if a[1] < b[1] else (fb, fa)
        if "S" in _faces(upper) or "N" in _faces(lower):
            return -y_overlap
    elif y_overlap > 0 and x_overlap <= 0:    # side by side
        left, right = (fa, fb) if a[0] < b[0] else (fb, fa)
        if "E" in _faces(left) or "W" in _faces(right):
            return -x_overlap
    return None


def door_keepout(lm: dict[str, Any], floor_w: int, floor_d: int) -> Rect:
    """Area in front of a door that must stay clear, extended into the store."""
    x1, y1, x2, y2 = landmark_rect(lm)
    k = SETTINGS["door_keepout_mm"]
    if y2 >= floor_d:      # front wall
        return (x1, floor_d - k, x2, floor_d)
    if y1 <= 0:            # back wall
        return (x1, 0, x2, k)
    if x1 <= 0:            # left wall
        return (0, y1, k, y2)
    return (floor_w - k, y1, floor_w, y2)  # right wall


def check_layout(doc: dict[str, Any], only_ids: set[str] | None = None) -> dict[str, Any]:
    """Return {"overlaps", "aisle_warnings", "blocked_doors", "out_of_bounds"} as lists of issues.

    only_ids limits checks to pairs involving those fixtures (fast path while dragging).
    """
    store = doc["store"]
    floor_w, floor_d = store["width_mm"], store["depth_mm"]
    fixtures = sorted(doc["fixtures"].values(), key=lambda f: f["code"])
    rects = {f["id"]: fixture_rect(f) for f in fixtures}
    overlaps, aisles, blocked, oob = [], [], [], []

    for i, a in enumerate(fixtures):
        ra = rects[a["id"]]
        if ra[0] < 0 or ra[1] < 0 or ra[2] > floor_w or ra[3] > floor_d:
            if only_ids is None or a["id"] in only_ids:
                oob.append({"fixtures": [a["id"]], "message": f"{a['code']} is outside the floor"})
        for b in fixtures[i + 1:]:
            if only_ids is not None and a["id"] not in only_ids and b["id"] not in only_ids:
                continue
            rb = rects[b["id"]]
            if overlap_area(ra, rb):
                overlaps.append({"fixtures": [a["id"], b["id"]], "message": f"{a['code']} overlaps {b['code']}"})
                continue
            gap = aisle_gap(a, ra, b, rb)
            if gap is not None and 0 < gap < SETTINGS["min_aisle_mm"]:
                aisles.append({
                    "fixtures": [a["id"], b["id"]], "gap_mm": gap,
                    "message": f"aisle between {a['code']} and {b['code']} is {gap:,} mm (min {SETTINGS['min_aisle_mm']:,} mm)",
                })
        for lm in doc["landmarks"]:
            if only_ids is not None and a["id"] not in only_ids:
                continue
            if lm["kind"] in SOLID_LANDMARKS and overlap_area(ra, landmark_rect(lm)):
                overlaps.append({"fixtures": [a["id"]], "landmark": lm["name"], "message": f"{a['code']} overlaps {lm['name']}"})
            elif lm["kind"] in DOOR_KINDS and overlap_area(ra, door_keepout(lm, floor_w, floor_d)):
                blocked.append({"fixtures": [a["id"]], "landmark": lm["name"], "message": f"{a['code']} blocks {lm['name']}"})

    return {"overlaps": overlaps, "aisle_warnings": aisles, "blocked_doors": blocked, "out_of_bounds": oob}
