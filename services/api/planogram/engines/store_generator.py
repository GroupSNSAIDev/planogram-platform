"""Parametric hypermarket layout for any floor size. Pure: returns a "planogram-layout" design dict.

Layout principles (spec 10.1, industry practice; large Indian hypermarkets are 35,000-67,000 sq ft):
- racetrack main aisle (3.0-3.2 m) around a grid of ambient gondola blocks, with cross aisles between blocks
- destination categories on the back wall (dairy, chilled drinks, frozen) to pull shoppers through the store
- heavy staples on the left wall, home care on the right wall, frozen islands beside the grid
- fresh (produce, bakery, cut fruit) and promotions at the entrance; checkouts with impulse racks at the exit
- gondola aisles 2.2 m; category space roughly follows typical sales shares; related categories are adjacent
Coordinates: millimetres, origin top-left, back wall at y = 0, front (entrance/checkouts) at y = depth.
"""
from __future__ import annotations

from typing import Any

MAIN_AISLE = 3100
GONDOLA_AISLE = 2200
WALL_DEPTH = 500
FRONT_DEPTH_MIN = 11500

# ambient gondola categories in racetrack order (left to right) with relative space weights
GONDOLA_PLAN: list[tuple[str, float]] = [
    ("ATA", 3), ("RIC", 3), ("DAL", 3), ("DRY", 2), ("OIL", 3), ("SAL", 1.5), ("MAS", 2.5),
    ("BRK", 2), ("SPR", 1.5), ("TEA", 2.5), ("HDR", 1.5), ("BIS", 3.5), ("SNK", 3.5), ("CHO", 2.5), ("INS", 2),
    ("SAU", 2), ("RTC", 1.5), ("BEVA", 3), ("WAT", 1.5),
    ("BAB", 1.5), ("ORA", 1.5), ("HAI", 2.5), ("SKN", 2), ("DEO", 1), ("BAT", 2), ("FEM", 1), ("MEN", 1), ("WEL", 1),
    ("CLN", 2), ("POO", 1), ("PET", 1), ("KIT", 2), ("STA", 1.5),
]
LOCKED = {"BAB", "WEL", "DAI", "CHE", "FRZ", "ICE", "FV", "IMP"}


def generate(width_mm: int, depth_mm: int, code: str, name: str) -> dict[str, Any]:
    W, D = int(width_mm), int(depth_mm)
    if W < 30000 or D < 25000:
        raise ValueError("the generator needs at least 30 × 25 m; draw smaller stores by hand")
    fixtures: list[dict[str, Any]] = []
    sections: list[dict[str, Any]] = []
    zones: list[dict[str, Any]] = []
    landmarks: list[dict[str, Any]] = []
    counters: dict[str, int] = {}

    def fx(prefix: str, template: str, x: int, y: int, rot: int = 0, faces: str | None = None, note: str | None = None) -> str:
        counters[prefix] = counters.get(prefix, 0) + 1
        c = f"{prefix}{counters[prefix]:02d}"
        fixtures.append({"code": c, "template": template, "x_mm": int(x), "y_mm": int(y), "rotation_deg": rot, "faces": faces, "note": note})
        return c

    def sec(fixture: str, side: str, b1: int, b2: int, cat: str) -> None:
        sections.append({"code": f"{fixture}-{side}-{b1:02d}", "fixture": fixture, "side": side, "bay_from": b1, "bay_to": b2,
                         "category": cat, "assignment_locked": cat in LOCKED})

    # ------------------------------------------------------------------ shell
    front_depth = max(FRONT_DEPTH_MIN, int(D * 0.2))
    y_front = D - front_depth                       # start of the front zone (fresh, checkouts)
    landmarks += [
        {"kind": "entrance", "name": "Main entrance", "rect": [3000, D - 200, 6000, 200]},
        {"kind": "exit", "name": "Exit", "rect": [W - 9000, D - 200, 4000, 200]},
        {"kind": "trolley_bay", "name": "Trolleys and baskets", "rect": [0, D - 3500, 2500, 3500]},
        {"kind": "stockroom_door", "name": "Stockroom door", "rect": [W - 4500, 0, 2000, 200]},
    ]

    # ------------------------------------------------------------------ back wall: dairy, chilled drinks, frozen
    x = 3000
    back_end = W - 5000
    back = []
    n_md = max(4, int((back_end - x) * 0.55 // 2500))
    for i in range(n_md):
        back.append(("MD-", "MULTIDECK_2500", 2500, "DAI" if i < n_md * 0.45 else "CHE" if i < n_md * 0.55 else "BEVC" if i < n_md * 0.85 else "RTE"))
    n_fz = max(2, int((back_end - x - n_md * 2500) // 3000))
    for _ in range(n_fz):
        back.append(("FZ-", "GLASS_DOOR_FREEZER_4", 3000, "FRZ"))
    for prefix, tpl, w, cat in back:
        if x + w > back_end:
            break
        c = fx(prefix, tpl, x, 0, 0, "S")
        sec(c, "A", 1, 4 if tpl == "GLASS_DOOR_FREEZER_4" else 1, cat)
        x += w
    zones.append({"code": "Z-CHILLED", "kind": "chilled", "name": "Chilled and frozen wall", "rect": [0, 0, W, 1600]})
    zones.append({"code": "Z-MAIN-BACK", "kind": "main_aisle", "name": "Main aisle (back)", "rect": [0, 900, W, MAIN_AISLE + 100]})

    # ------------------------------------------------------------------ side walls
    y0 = 900 + MAIN_AISLE + 100
    n_wall = (y_front - y0) // 1000
    for i in range(n_wall):
        c = fx("WL-", "WALL_BAY", 0, y0 + i * 1000, 90, "E")
        sec(c, "A", 1, 1, "BULK" if i < n_wall * 0.6 else "OIL")
        c = fx("WR-", "WALL_BAY", W - WALL_DEPTH, y0 + i * 1000, 270, "W")
        sec(c, "A", 1, 1, "DET" if i < n_wall * 0.45 else "PLA" if i < n_wall * 0.75 else "PAP")
    zones.append({"code": "Z-WALL-L", "kind": "perimeter", "name": "Staples wall", "rect": [0, y0, 3600, n_wall * 1000]})
    zones.append({"code": "Z-WALL-R", "kind": "perimeter", "name": "Home care wall", "rect": [W - 3600, y0, 3600, n_wall * 1000]})

    # ------------------------------------------------------------------ frozen islands (right of the grid)
    island_w = 2 * 2500 + 2000
    grid_x0 = WALL_DEPTH + MAIN_AISLE
    grid_x1 = W - WALL_DEPTH - MAIN_AISLE - island_w - MAIN_AISLE
    ix = grid_x1 + MAIN_AISLE
    iy = y0 + 1500
    n_islands = 0
    while iy + 1000 <= y_front - MAIN_AISLE - 1500 and n_islands < 12:
        for col in range(2):
            c = fx("IF-", "ISLAND_FREEZER_2500", ix + col * 4500, iy, 0, "TOP")
            sec(c, "TOP", 1, 1, "ICE" if n_islands % 3 == 0 else "FRZ")
            n_islands += 1
        iy += 3200
    zones.append({"code": "Z-FROZEN-ISLAND", "kind": "frozen", "name": "Frozen islands",
                  "rect": [ix - 600, y0 + 900, 9000 + 1200, max(3000, iy - y0 - 900)]})

    # ------------------------------------------------------------------ gondola blocks
    block_len = 600 + 12000 + 600
    avail = y_front - MAIN_AISLE - y0
    n_blocks = max(1, (avail + MAIN_AISLE) // (block_len + MAIN_AISLE))
    spare = avail - (n_blocks * block_len + (n_blocks - 1) * MAIN_AISLE)
    by = y0 + spare // 2
    pitch = 1000 + GONDOLA_AISLE
    n_cols = max(1, (grid_x1 - grid_x0 + GONDOLA_AISLE) // pitch)
    gx0 = grid_x0 + ((grid_x1 - grid_x0) - (n_cols * pitch - GONDOLA_AISLE)) // 2
    gondola_sides: list[tuple[str, str]] = []
    for b in range(n_blocks):
        for col in range(n_cols):
            gx = gx0 + col * pitch
            g = fx("G", "GONDOLA_DS_12", gx, by + 600, 90, "W/E")
            gondola_sides += [(g, "A"), (g, "B")]
            eb = fx("EC-", "END_CAP", gx, by, 0, "N")
            sec(eb, "A", 1, 1, "SEA")
            ef = fx("EC-", "END_CAP", gx, by + 600 + 12000, 0, "S")
            sec(ef, "A", 1, 1, "PRO")
        if b < n_blocks - 1:
            zones.append({"code": f"Z-CROSS-{b + 1}", "kind": "main_aisle", "name": f"Cross aisle {b + 1}",
                          "rect": [grid_x0, by + block_len, grid_x1 - grid_x0, MAIN_AISLE]})
            landmarks.append({"kind": "pillar", "name": f"Pillar C{b + 1}", "rect": [grid_x0 - 1800, by + block_len + MAIN_AISLE // 2 - 300, 600, 600]})
        by += block_len + MAIN_AISLE
    zones.append({"code": "Z-CENTRE", "kind": "centre_store", "name": "Centre store (ambient grid)",
                  "rect": [grid_x0, y0, grid_x1 - grid_x0, y_front - MAIN_AISLE - y0]})

    # categories to gondola sides: proportional, whole bays, at least 3 bays per section, in racetrack order
    total_bays = len(gondola_sides) * 12
    weight = sum(w for _, w in GONDOLA_PLAN)
    want = [(c, max(3, round(total_bays * w / weight))) for c, w in GONDOLA_PLAN]
    side_i, bay = 0, 1
    for cat, n in want:
        while n > 0 and side_i < len(gondola_sides):
            g, sd = gondola_sides[side_i]
            take = min(n, 13 - bay)
            if 13 - bay - take < 3 and 13 - bay - take > 0:   # do not leave a sliver of 1-2 bays
                take = 13 - bay
            sec(g, sd, bay, bay + take - 1, cat)
            n -= take
            bay += take
            if bay > 12:
                side_i, bay = side_i + 1, 1
    while side_i < len(gondola_sides):                          # any leftover space: seasonal / general
        g, sd = gondola_sides[side_i]
        sec(g, sd, bay, 12, "SEA")
        side_i, bay = side_i + 1, 1

    # ------------------------------------------------------------------ front: main aisle, fresh, promotions, checkouts
    zones.append({"code": "Z-MAIN-FRONT", "kind": "main_aisle", "name": "Main aisle (front)", "rect": [0, y_front - MAIN_AISLE, W, MAIN_AISLE]})
    fy = y_front + 600
    fresh_w = int(W * 0.36)
    zones.append({"code": "Z-FRESH", "kind": "entrance", "name": "Entrance and fresh", "rect": [0, y_front, fresh_w, front_depth]})
    c = fx("MD-", "MULTIDECK_2500", 0, fy, 90, "E", "Cut fruit, salads, herbs")
    sec(c, "A", 1, 1, "CUT")
    px = 3800
    bx = fresh_w - 3000
    rows = 0
    while rows < 2 and fy + rows * 2200 + 1200 < D - 4500:
        x = px
        while x + 1200 <= bx - 1000:   # keep a 1 m aisle in front of the bakery racks
            c = fx("PB-", "PRODUCE_BIN", x, fy + rows * 2200, 0, "TOP")
            sec(c, "TOP", 1, 1, "FV")
            x += 1800
        rows += 1
    for i in range(3):
        c = fx("BK-", "BAKERY_RACK", bx, fy + i * 1500, 90, "W")
        sec(c, "A", 1, 1, "BAK")
    for i in range(4):
        c = fx("PL-", "PALLET", 3800 + i * 1700, D - 4300, 0, "ALL", "Entrance promotions")
        sec(c, "TOP", 1, 1, "PRO")

    co_x0 = fresh_w + 2500
    co_x1 = W - 12000
    zones.append({"code": "Z-CHECKOUT", "kind": "checkout", "name": "Checkout and impulse", "rect": [fresh_w, y_front, W - fresh_w, front_depth]})
    lane = 2400
    n_lanes = max(4, (co_x1 - co_x0) // lane)
    cy = D - 2800 - 2500
    for i in range(n_lanes):
        x = co_x0 + i * lane
        fx("CO-", "CHECKOUT_COUNTER", x, cy, 0, None, f"Lane {i + 1}")
        r = fx("CR-", "CHECKOUT_RACK", x + 1050, cy + 200, 0, "E", f"Impulse rack lane {i + 1}")
        sec(r, "A", 1, 1, "IMP")
    sx = co_x0 + n_lanes * lane + 600
    for i in range(4):
        fx("SC-", "SELF_CHECKOUT", sx + (i % 2) * 1200, cy + (i // 2) * 1200, 0)
    fx("CS-", "SERVICE_DESK", W - 4000, D - 5200, 0, None, "Customer service and returns")
    for k in range(1, W // 15000):
        x = k * 15000
        if co_x0 - 1000 < x < W - 3000 or x < fresh_w - 2000:
            landmarks.append({"kind": "pillar", "name": f"Pillar F{k}", "rect": [x - 300, y_front - MAIN_AISLE // 2 - 300, 600, 600]})

    return {
        "format": "planogram-layout", "version": 1,
        "store": {"code": code, "name": name, "format": "hypermarket", "timezone": "Asia/Kolkata", "width_mm": W, "depth_mm": D},
        "zones": zones, "landmarks": landmarks, "fixtures": fixtures, "shelf_heights": [], "sections": sections,
    }
