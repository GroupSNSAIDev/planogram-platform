"""Planogram commands (spec section 12.1): apply a batch to a section's positions. Pure.

positions: {id: {id, surface_id, product_id, seq, x_mm, facings_wide, facings_high, facings_deep,
                 placed_by, reason, rule_ids, locked, locked_x_mm}}
Order on a shelf is the source of truth (seq); x_mm is always recalculated (ADR-07).
Placement locks are anchors: a command that would push a locked product fails (spec 13.3).
Mirrored for instant feedback in apps/web/src/doc/planogramReducer.ts.
"""
from __future__ import annotations

from typing import Any

from .context import eligibility
from .geometry import check_surface, max_facings_deep
from .layout_doc import CommandError

Positions = dict[str, dict[str, Any]]
Command = dict[str, Any]


def on_surface(positions: Positions, surface_id: str) -> list[dict[str, Any]]:
    return sorted((p for p in positions.values() if p["surface_id"] == surface_id), key=lambda p: (p["seq"], p["id"]))


def _renumber(positions: Positions, surface_id: str) -> None:
    for i, p in enumerate(on_surface(positions, surface_id)):
        if p["seq"] != i:
            positions[p["id"]] = {**p, "seq": i}


def _insert(positions: Positions, pos: dict[str, Any], seq: int) -> None:
    """Insert pos on its surface at index seq, shifting the rest right."""
    row = [p for p in on_surface(positions, pos["surface_id"]) if p["id"] != pos["id"]]
    seq = max(0, min(seq, len(row)))
    row.insert(seq, pos)
    positions[pos["id"]] = pos
    for i, p in enumerate(row):
        positions[p["id"]] = {**positions[p["id"]], "seq": i}


def relayout(ctx: dict[str, Any], positions: Positions, surface_ids: set[str]) -> list[dict[str, Any]]:
    """Recalculate x_mm on the given surfaces. Returns anchor conflicts."""
    conflicts = []
    for sid in surface_ids:
        surface = ctx["surface_by_id"].get(sid)
        if surface is None:
            continue
        row = on_surface(positions, sid)
        result = check_surface(surface, surface["clear_height_mm"], surface["bay_has_door"],
                               ctx["fixture"]["temperature"], row, ctx["products"])
        for p in row:
            x = result["x_mm"][p["id"]]
            if p["x_mm"] != x:
                positions[p["id"]] = {**positions[p["id"]], "x_mm": x}
        conflicts += [i for i in result["issues"] if i["code"] == "ANCHOR"]
    return conflicts


def _locked_guard(p: dict[str, Any], ctx: dict[str, Any]) -> None:
    if p.get("locked"):
        name = ctx["products"].get(p["product_id"], {}).get("name", "product")
        raise CommandError(f"{name} is placement-locked; unlock it first")


def apply_planogram_commands(ctx: dict[str, Any], positions: Positions,
                             commands: list[Command]) -> tuple[Positions, list[Command]]:
    """Apply commands in order. Returns (new_positions, inverse_batch). Raises CommandError."""
    new = dict(positions)
    inverse: list[Command] = []
    for i, cmd in enumerate(commands):
        try:
            inv, touched = _apply_one(ctx, new, cmd)
            conflicts = relayout(ctx, new, touched)
            if conflicts and cmd["type"] != "ReplacePositions":
                raise CommandError(conflicts[0]["message"])
        except CommandError as e:
            e.index = i
            raise
        except KeyError as e:
            raise CommandError(f"{cmd.get('type', 'command')}: missing field {e}", i) from e
        inverse = inv + inverse
    return new, inverse


def _apply_one(ctx: dict[str, Any], positions: Positions, cmd: Command) -> tuple[list[Command], set[str]]:
    t = cmd.get("type")
    products = ctx["products"]

    if t == "AddPosition":
        if cmd["position_id"] in positions:
            raise CommandError("position already exists")
        surface = ctx["surface_by_id"].get(cmd["surface_id"])
        if surface is None:
            raise CommandError("that shelf is not part of this section")
        product = products.get(cmd["product_id"])
        if product is None:
            raise CommandError(f"unknown product {cmd['product_id']}")
        elig = eligibility(product, None, ctx["section"]["image_policy"])
        if elig["status"] == "blocked":
            raise CommandError(f"{product['name']} cannot be placed: {elig['reason']}")
        deep = cmd.get("facings_deep") or max_facings_deep(product["depth_mm"], surface["usable_depth_mm"])
        pos = {
            "id": cmd["position_id"], "surface_id": surface["id"], "product_id": product["id"], "seq": 0, "x_mm": 0,
            "facings_wide": int(cmd.get("facings_wide", 1)), "facings_high": int(cmd.get("facings_high", 1)),
            "facings_deep": int(deep), "placed_by": cmd.get("placed_by", "planner"),
            "reason": cmd.get("reason"), "rule_ids": cmd.get("rule_ids", []), "locked": False, "locked_x_mm": None,
        }
        _insert(positions, pos, int(cmd.get("seq", 10**6)))
        return [{"type": "RemovePosition", "position_id": pos["id"]}], {surface["id"]}

    if t == "RemovePosition":
        p = positions.get(cmd["position_id"])
        if p is None:
            raise CommandError("position not found")
        _locked_guard(p, ctx)
        del positions[p["id"]]
        _renumber(positions, p["surface_id"])
        return [{"type": "RestorePosition", "position": p}], {p["surface_id"]}

    if t == "RestorePosition":
        p = dict(cmd["position"])
        if p["surface_id"] not in ctx["surface_by_id"]:
            raise CommandError("that shelf is not part of this section")
        _insert(positions, p, p["seq"])
        return [{"type": "RemovePosition", "position_id": p["id"]}], {p["surface_id"]}

    if t == "MovePosition":
        p = positions.get(cmd["position_id"])
        if p is None:
            raise CommandError("position not found")
        _locked_guard(p, ctx)
        if cmd["surface_id"] not in ctx["surface_by_id"]:
            raise CommandError("that shelf is not part of this section")
        old_surface, old_seq = p["surface_id"], p["seq"]
        del positions[p["id"]]
        _renumber(positions, old_surface)
        _insert(positions, {**p, "surface_id": cmd["surface_id"], "placed_by": "planner"}, int(cmd["seq"]))
        return ([{"type": "MovePosition", "position_id": p["id"], "surface_id": old_surface, "seq": old_seq}],
                {old_surface, cmd["surface_id"]})

    if t == "SetFacings":
        p = positions.get(cmd["position_id"])
        if p is None:
            raise CommandError("position not found")
        _locked_guard(p, ctx)
        wide, high, deep = int(cmd["wide"]), int(cmd["high"]), int(cmd["deep"])
        if min(wide, high, deep) < 1 or max(wide, high, deep) > 30:
            raise CommandError("facings must be between 1 and 30")
        positions[p["id"]] = {**p, "facings_wide": wide, "facings_high": high, "facings_deep": deep}
        return ([{"type": "SetFacings", "position_id": p["id"], "wide": p["facings_wide"],
                  "high": p["facings_high"], "deep": p["facings_deep"]}], {p["surface_id"]})

    if t == "Lock":
        p = positions.get(cmd["position_id"])
        if p is None:
            raise CommandError("position not found")
        x = cmd.get("locked_x_mm")
        positions[p["id"]] = {**p, "locked": True, "locked_x_mm": p["x_mm"] if x is None else int(x)}
        return [{"type": "Unlock", "position_id": p["id"]}], {p["surface_id"]}

    if t == "Unlock":
        p = positions.get(cmd["position_id"])
        if p is None:
            raise CommandError("position not found")
        positions[p["id"]] = {**p, "locked": False, "locked_x_mm": None}
        return [{"type": "Lock", "position_id": p["id"], "locked_x_mm": p["locked_x_mm"]}], {p["surface_id"]}

    if t == "ReplacePositions":
        keep_locked = bool(cmd.get("keep_locked", True))
        old = list(positions.values())
        touched = {p["surface_id"] for p in old}
        for p in old:
            if not (keep_locked and p.get("locked")):
                del positions[p["id"]]
        for p in cmd["positions"]:
            if p["surface_id"] not in ctx["surface_by_id"]:
                raise CommandError("a proposed position is not on a shelf of this section")
            positions[p["id"]] = {"locked": False, "locked_x_mm": None, "rule_ids": [], "reason": None,
                                  "x_mm": 0, **p}
            touched.add(p["surface_id"])
        for sid in touched:
            _renumber(positions, sid)
        return [{"type": "ReplacePositions", "positions": old, "keep_locked": False}], touched

    raise CommandError(f"unknown planogram command {t!r}")
