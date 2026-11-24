"""Layout commands (spec section 12.1): apply a batch to a layout document. Pure.

A layout document is a dict:
  store, zones[], landmarks[], fixtures{id: ...}, bays{id: ...}, surfaces{id: ...}, sections{id: ...}
Entity dicts are never mutated in place (copy on write), so the caller can diff old and new.

Every command returns its inverse, so undo is just another command batch (history stays linear).
Mirrored for instant feedback in apps/web/src/doc/layoutReducer.ts.
"""
from __future__ import annotations

from typing import Any

Doc = dict[str, Any]
Command = dict[str, Any]

MAPS = ("fixtures", "bays", "surfaces", "sections")
COMPASS = ["N", "E", "S", "W"]
MIN_SHELF_GAP_MM = 50


class CommandError(Exception):
    def __init__(self, message: str, index: int | None = None):
        super().__init__(message)
        self.message = message
        self.index = index


# ----------------------------------------------------------------------------- helpers

def bay_id(fixture_id: str, side: str, idx: int) -> str:
    return f"{fixture_id}-{side}{idx}"


def surface_id(bay: str, k: int) -> str:
    return f"{bay}-s{k}"


def rotated_size(template: dict[str, Any], rotation_deg: int) -> tuple[int, int]:
    w, d = template["footprint"]
    return (w, d) if rotation_deg % 180 == 0 else (d, w)


def default_faces(template: dict[str, Any]) -> str | None:
    sides = template.get("sides") or []
    if not sides:
        return None
    if sides == ["TOP"]:
        return "TOP"
    return "S/N" if len(sides) == 2 else "S"


def rotate_faces(faces: str | None, steps: int) -> str | None:
    """Rotate compass faces clockwise by 90 degrees per step ("W/E" -> "N/S")."""
    if not faces or faces in ("TOP", "ALL"):
        return faces
    out = []
    for part in faces.split("/"):
        out.append(COMPASS[(COMPASS.index(part) + steps) % 4] if part in COMPASS else part)
    return "/".join(out)


def build_fixture_parts(fixture: dict[str, Any], template: dict[str, Any]) -> tuple[dict, dict]:
    """Generate bays and surfaces for a fixture from its template (stable, derived ids)."""
    bays: dict[str, dict] = {}
    surfaces: dict[str, dict] = {}
    for side in template.get("sides") or []:
        for idx in range(1, template.get("bays_per_side", 0) + 1):
            b = bay_id(fixture["id"], side, idx)
            bays[b] = {
                "id": b, "fixture_id": fixture["id"], "side": side, "idx": idx,
                "width_mm": template["bay_width"], "height_mm": template["height"],
                "depth_mm": template.get("depth_per_side", 0), "has_door": bool(template.get("doors")),
            }
            for k, s in enumerate(template.get("surfaces") or [], start=1):
                grid = s.get("grid") or [None, None]
                sid = surface_id(b, k)
                surfaces[sid] = {
                    "id": sid, "bay_id": b, "kind": s["kind"], "idx": k,
                    "height_from_floor_mm": s["h"], "width_mm": template["bay_width"],
                    "depth_mm": template.get("depth_per_side", 0),
                    "max_load_g": template.get("max_load_g_per_shelf"),
                    "notch_pitch_mm": template.get("notch_pitch", 25),
                    "grid_cols": grid[0], "grid_rows": grid[1],
                }
    return bays, surfaces


def section_code(doc: Doc, fixture_code: str, side: str, bay_from: int, exclude_id: str | None = None) -> str:
    base = f"{fixture_code}-{side}-{bay_from:02d}"
    taken = {s["code"] for s in doc["sections"].values() if s["id"] != exclude_id}
    code, n = base, 0
    while code in taken:
        n += 1
        code = f"{base}{chr(ord('a') + n - 1)}"
    return code


def side_bay_count(doc: Doc, fixture_id: str, side: str) -> int:
    return sum(1 for b in doc["bays"].values() if b["fixture_id"] == fixture_id and b["side"] == side)


def _get(doc: Doc, kind: str, id_: str, label: str) -> dict[str, Any]:
    item = doc[kind].get(id_)
    if item is None:
        raise CommandError(f"{label} {id_} not found")
    return item


def _check_section_range(doc: Doc, sec: dict[str, Any]) -> None:
    n = side_bay_count(doc, sec["fixture_id"], sec["side"])
    if n == 0:
        raise CommandError(f"fixture has no side {sec['side']}")
    if not (1 <= sec["bay_from"] <= sec["bay_to"] <= n):
        raise CommandError(f"bays {sec['bay_from']}-{sec['bay_to']} are outside 1-{n}")
    for other in doc["sections"].values():
        if other["id"] == sec["id"] or other["fixture_id"] != sec["fixture_id"] or other["side"] != sec["side"]:
            continue
        if sec["bay_from"] <= other["bay_to"] and other["bay_from"] <= sec["bay_to"]:
            raise CommandError(
                f"bays {sec['bay_from']}-{sec['bay_to']} overlap section {other['code']} "
                f"(bays {other['bay_from']}-{other['bay_to']})")


def _check_rect(rect: list) -> None:
    if len(rect) != 4 or rect[2] <= 0 or rect[3] <= 0:
        raise CommandError("a rectangle needs x, y, a positive width and a positive height")


def _require_unlocked(sec: dict[str, Any]) -> None:
    if sec.get("assignment_locked"):
        raise CommandError(f"section {sec['code']} is assignment-locked; unlock it first")


# ----------------------------------------------------------------------------- apply

def apply_layout_commands(
    doc: Doc,
    templates: dict[str, dict[str, Any]],
    categories: dict[str, dict[str, Any]],
    commands: list[Command],
    sections_with_positions: set[str] | None = None,
) -> tuple[Doc, list[Command]]:
    """Apply commands in order. Returns (new_doc, inverse_batch). Raises CommandError."""
    protected = sections_with_positions or set()
    new = {**doc, **{k: dict(doc[k]) for k in MAPS}, "zones": list(doc["zones"]), "landmarks": list(doc["landmarks"]),
           "store": dict(doc["store"])}
    inverse: list[Command] = []
    for i, cmd in enumerate(commands):
        try:
            inv = _apply_one(new, templates, categories, cmd, protected)
        except CommandError as e:
            e.index = i
            raise
        except KeyError as e:
            raise CommandError(f"{cmd.get('type', 'command')}: missing field {e}", i) from e
        inverse = inv + inverse
    return new, inverse


def _apply_one(doc: Doc, templates, categories, cmd: Command, protected: set[str]) -> list[Command]:
    t = cmd.get("type")
    fixtures, bays, surfaces, sections = doc["fixtures"], doc["bays"], doc["surfaces"], doc["sections"]

    if t == "PlaceFixture":
        tpl = templates.get(cmd["template_code"])
        if tpl is None:
            raise CommandError(f"unknown template {cmd['template_code']}")
        if cmd["fixture_id"] in fixtures:
            raise CommandError(f"fixture {cmd['fixture_id']} already exists")
        if any(f["code"] == cmd["code"] for f in fixtures.values()):
            raise CommandError(f"fixture code {cmd['code']} is already used")
        rot = int(cmd.get("rotation_deg", 0)) % 360
        if rot % 90:
            raise CommandError("rotation must be a multiple of 90 degrees")
        w, d = rotated_size(tpl, rot)
        f = {
            "id": cmd["fixture_id"], "code": cmd["code"], "template_code": cmd["template_code"],
            "kind": tpl["kind"], "x_mm": int(cmd["x_mm"]), "y_mm": int(cmd["y_mm"]), "rotation_deg": rot,
            "footprint_w_mm": w, "footprint_d_mm": d, "temperature": tpl["temperature"],
            "faces": cmd.get("faces") or rotate_faces(default_faces(tpl), rot // 90), "note": cmd.get("note"),
        }
        fixtures[f["id"]] = f
        new_bays, new_surfaces = build_fixture_parts(f, tpl)
        bays.update(new_bays)
        surfaces.update(new_surfaces)
        return [{"type": "RemoveFixture", "fixture_id": f["id"]}]

    if t == "MoveFixture":
        f = _get(doc, "fixtures", cmd["fixture_id"], "fixture")
        fixtures[f["id"]] = {**f, "x_mm": int(cmd["x_mm"]), "y_mm": int(cmd["y_mm"])}
        return [{"type": "MoveFixture", "fixture_id": f["id"], "x_mm": f["x_mm"], "y_mm": f["y_mm"]}]

    if t == "RotateFixture":
        f = _get(doc, "fixtures", cmd["fixture_id"], "fixture")
        rot = int(cmd["rotation_deg"]) % 360
        if rot % 90:
            raise CommandError("rotation must be a multiple of 90 degrees")
        tpl = templates.get(f["template_code"])
        w, d = rotated_size(tpl, rot) if tpl else (
            (f["footprint_w_mm"], f["footprint_d_mm"]) if (rot - f["rotation_deg"]) % 180 == 0
            else (f["footprint_d_mm"], f["footprint_w_mm"]))
        steps = ((rot - f["rotation_deg"]) // 90) % 4
        fixtures[f["id"]] = {**f, "rotation_deg": rot, "x_mm": int(cmd["x_mm"]), "y_mm": int(cmd["y_mm"]),
                             "footprint_w_mm": w, "footprint_d_mm": d, "faces": rotate_faces(f["faces"], steps)}
        return [{"type": "RotateFixture", "fixture_id": f["id"], "rotation_deg": f["rotation_deg"],
                 "x_mm": f["x_mm"], "y_mm": f["y_mm"]}]

    if t == "RemoveFixture":
        f = _get(doc, "fixtures", cmd["fixture_id"], "fixture")
        own_sections = [s for s in sections.values() if s["fixture_id"] == f["id"]]
        busy = [s["code"] for s in own_sections if s["id"] in protected]
        if busy:
            raise CommandError(f"{f['code']} has products placed in {', '.join(busy)}; clear those planograms first")
        own_bays = [b for b in bays.values() if b["fixture_id"] == f["id"]]
        bay_ids = {b["id"] for b in own_bays}
        own_surfaces = [s for s in surfaces.values() if s["bay_id"] in bay_ids]
        del fixtures[f["id"]]
        for b in own_bays:
            del bays[b["id"]]
        for s in own_surfaces:
            del surfaces[s["id"]]
        for s in own_sections:
            del sections[s["id"]]
        return [{"type": "RestoreFixture", "fixture": f, "bays": own_bays, "surfaces": own_surfaces,
                 "sections": own_sections}]

    if t == "RestoreFixture":
        f = cmd["fixture"]
        if f["id"] in fixtures:
            raise CommandError(f"fixture {f['code']} already exists")
        fixtures[f["id"]] = dict(f)
        for b in cmd.get("bays", []):
            bays[b["id"]] = dict(b)
        for s in cmd.get("surfaces", []):
            surfaces[s["id"]] = dict(s)
        for s in cmd.get("sections", []):
            sections[s["id"]] = dict(s)
        return [{"type": "RemoveFixture", "fixture_id": f["id"]}]

    if t == "UpdateSurface":
        s = _get(doc, "surfaces", cmd["surface_id"], "surface")
        h = int(cmd["height_from_floor_mm"])
        pitch = s.get("notch_pitch_mm") or 25
        if h % pitch:
            raise CommandError(f"shelf height {h} mm is not on the {pitch} mm notch pitch")
        bay = bays[s["bay_id"]]
        others = sorted(o["height_from_floor_mm"] for o in surfaces.values()
                        if o["bay_id"] == s["bay_id"] and o["id"] != s["id"])
        below = [o for o in others if o < s["height_from_floor_mm"]]
        above = [o for o in others if o > s["height_from_floor_mm"]]
        lo = (below[-1] + MIN_SHELF_GAP_MM) if below else 0
        hi = (above[0] - MIN_SHELF_GAP_MM) if above else bay["height_mm"]
        if not lo <= h <= hi:
            raise CommandError(f"shelf height must stay between {lo} and {hi} mm (neighbouring shelves)")
        surfaces[s["id"]] = {**s, "height_from_floor_mm": h}
        return [{"type": "UpdateSurface", "surface_id": s["id"], "height_from_floor_mm": s["height_from_floor_mm"]}]

    if t == "CreateSection":
        if cmd["section_id"] in sections:
            raise CommandError(f"section {cmd['section_id']} already exists")
        f = _get(doc, "fixtures", cmd["fixture_id"], "fixture")
        if cmd["category_code"] not in categories:
            raise CommandError(f"unknown category {cmd['category_code']}")
        sec = {
            "id": cmd["section_id"], "fixture_id": f["id"], "side": cmd["side"],
            "bay_from": int(cmd["bay_from"]), "bay_to": int(cmd["bay_to"]),
            "category_code": cmd["category_code"], "image_policy": cmd.get("image_policy", "placeholder_ok"),
            "assignment_locked": bool(cmd.get("assignment_locked", False)),
        }
        sec["code"] = cmd.get("code") or section_code(doc, f["code"], sec["side"], sec["bay_from"])
        _check_section_range(doc, sec)
        sections[sec["id"]] = sec
        return [{"type": "RemoveSection", "section_id": sec["id"]}]

    if t == "RemoveSection":
        sec = _get(doc, "sections", cmd["section_id"], "section")
        _require_unlocked(sec)
        if sec["id"] in protected:
            raise CommandError(f"section {sec['code']} has products placed; clear its planogram first")
        del sections[sec["id"]]
        return [{"type": "RestoreSection", "section": sec}]

    if t == "RestoreSection":
        sec = dict(cmd["section"])
        _check_section_range(doc, sec)
        sections[sec["id"]] = sec
        return [{"type": "RemoveSection", "section_id": sec["id"]}]

    if t == "ResizeSection":
        sec = _get(doc, "sections", cmd["section_id"], "section")
        _require_unlocked(sec)
        new_sec = {**sec, "bay_from": int(cmd["bay_from"]), "bay_to": int(cmd["bay_to"])}
        _check_section_range(doc, new_sec)
        sections[sec["id"]] = new_sec
        return [{"type": "ResizeSection", "section_id": sec["id"], "bay_from": sec["bay_from"], "bay_to": sec["bay_to"]}]

    if t == "SplitSection":
        sec = _get(doc, "sections", cmd["section_id"], "section")
        _require_unlocked(sec)
        at = int(cmd["at_bay"])
        if not sec["bay_from"] < at <= sec["bay_to"]:
            raise CommandError(f"split bay must be between {sec['bay_from'] + 1} and {sec['bay_to']}")
        if cmd["new_section_id"] in sections:
            raise CommandError("new section id already exists")
        f = fixtures[sec["fixture_id"]]
        sections[sec["id"]] = {**sec, "bay_to": at - 1}
        new_sec = {**sec, "id": cmd["new_section_id"], "bay_from": at, "bay_to": sec["bay_to"],
                   "category_code": cmd.get("category_code") or sec["category_code"]}
        new_sec["code"] = cmd.get("new_code") or section_code(doc, f["code"], sec["side"], at)
        sections[new_sec["id"]] = new_sec
        return [{"type": "RemoveSection", "section_id": new_sec["id"]},
                {"type": "ResizeSection", "section_id": sec["id"], "bay_from": sec["bay_from"], "bay_to": sec["bay_to"]}]

    if t == "MergeSection":
        sec = _get(doc, "sections", cmd["section_id"], "section")
        other = _get(doc, "sections", cmd["other_section_id"], "section")
        _require_unlocked(sec)
        _require_unlocked(other)
        if sec["fixture_id"] != other["fixture_id"] or sec["side"] != other["side"]:
            raise CommandError("only sections on the same fixture side can be merged")
        if not (sec["bay_to"] + 1 == other["bay_from"] or other["bay_to"] + 1 == sec["bay_from"]):
            raise CommandError(f"{sec['code']} and {other['code']} are not next to each other")
        if other["id"] in protected:
            raise CommandError(f"section {other['code']} has products placed; clear its planogram first")
        del sections[other["id"]]
        sections[sec["id"]] = {**sec, "bay_from": min(sec["bay_from"], other["bay_from"]),
                               "bay_to": max(sec["bay_to"], other["bay_to"])}
        return [{"type": "ResizeSection", "section_id": sec["id"], "bay_from": sec["bay_from"], "bay_to": sec["bay_to"]},
                {"type": "RestoreSection", "section": other}]

    if t == "AssignSectionCategory":
        sec = _get(doc, "sections", cmd["section_id"], "section")
        _require_unlocked(sec)
        if cmd["category_code"] not in categories:
            raise CommandError(f"unknown category {cmd['category_code']}")
        sections[sec["id"]] = {**sec, "category_code": cmd["category_code"]}
        return [{"type": "AssignSectionCategory", "section_id": sec["id"], "category_code": sec["category_code"]}]

    if t in ("AddZone", "AddLandmark"):
        key = "zones" if t == "AddZone" else "landmarks"
        item = dict(cmd["zone" if t == "AddZone" else "landmark"])
        if any(z["id"] == item["id"] for z in doc[key]):
            raise CommandError(f"{key[:-1]} {item['id']} already exists")
        _check_rect(item["rect"])
        item["rect"] = [int(v) for v in item["rect"]]
        doc[key].append(item)
        return [{"type": "RemoveZone" if t == "AddZone" else "RemoveLandmark", "id": item["id"]}]

    if t in ("UpdateZone", "UpdateLandmark"):
        key = "zones" if t == "UpdateZone" else "landmarks"
        i = next((k for k, z in enumerate(doc[key]) if z["id"] == cmd["id"]), None)
        if i is None:
            raise CommandError(f"{key[:-1]} {cmd['id']} not found")
        old = doc[key][i]
        changes = {k: cmd[k] for k in ("rect", "name", "kind", "code") if k in cmd}
        if "rect" in changes:
            _check_rect(changes["rect"])
            changes["rect"] = [int(v) for v in changes["rect"]]
        doc[key][i] = {**old, **changes}
        return [{"type": t, "id": old["id"], **{k: old[k] for k in changes}}]

    if t in ("RemoveZone", "RemoveLandmark"):
        key = "zones" if t == "RemoveZone" else "landmarks"
        old = next((z for z in doc[key] if z["id"] == cmd["id"]), None)
        if old is None:
            raise CommandError(f"{key[:-1]} {cmd['id']} not found")
        doc[key] = [z for z in doc[key] if z["id"] != cmd["id"]]
        return [{"type": "AddZone", "zone": old} if t == "RemoveZone" else {"type": "AddLandmark", "landmark": old}]

    if t == "ResizeFloor":
        w, d = int(cmd["width_mm"]), int(cmd["depth_mm"])
        if not (5000 <= w <= 300000 and 5000 <= d <= 300000):
            raise CommandError("floor must be between 5 m and 300 m on each side")
        old = doc["store"]
        doc["store"] = {**old, "width_mm": w, "depth_mm": d}
        return [{"type": "ResizeFloor", "width_mm": old["width_mm"], "depth_mm": old["depth_mm"]}]

    if t == "RenameStore":
        old = doc["store"]
        doc["store"] = {**old, "name": str(cmd["name"])[:120]}
        return [{"type": "RenameStore", "name": old["name"]}]

    if t == "RenameFixture":
        f = _get(doc, "fixtures", cmd["fixture_id"], "fixture")
        new_code = str(cmd["code"]).strip()
        if not new_code or any(o["code"] == new_code and o["id"] != f["id"] for o in fixtures.values()):
            raise CommandError(f"fixture code {new_code!r} is empty or already used")
        fixtures[f["id"]] = {**f, "code": new_code}
        return [{"type": "RenameFixture", "fixture_id": f["id"], "code": f["code"]}]

    if t == "SetSectionImagePolicy":
        sec = _get(doc, "sections", cmd["section_id"], "section")
        if cmd["image_policy"] not in ("required", "placeholder_ok"):
            raise CommandError("image policy must be 'required' or 'placeholder_ok'")
        sections[sec["id"]] = {**sec, "image_policy": cmd["image_policy"]}
        return [{"type": "SetSectionImagePolicy", "section_id": sec["id"], "image_policy": sec["image_policy"]}]

    if t == "SetAssignmentLock":
        sec = _get(doc, "sections", cmd["section_id"], "section")
        sections[sec["id"]] = {**sec, "assignment_locked": bool(cmd["locked"])}
        return [{"type": "SetAssignmentLock", "section_id": sec["id"], "locked": sec["assignment_locked"]}]

    raise CommandError(f"unknown layout command {t!r}")
