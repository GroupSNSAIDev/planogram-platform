"""Shelf planner commands, rules and auto-fill invariants."""
import pytest

from planogram.engines.geometry import SETTINGS


@pytest.fixture()
def pg(client):
    return client.get("/api/sections/G03-A-01/planogram").json()


def cmd(client, pg_id, cmds):
    return client.post(f"/api/planograms/{pg_id}/commands", json={"commands": cmds})


def product(pg, name):
    return next(p for p in pg["products"] if p["name"].startswith(name))


def eye_shelf(pg, bay=1):
    return next(s for s in pg["surfaces"] if s["bay_idx"] == bay and s["level"] == 4)


def test_add_move_facings_and_undo(client, pg):
    pid, s = pg["planogram"]["id"], eye_shelf(pg)
    oats, kirra = product(pg, "Sunmill Rolled Oats"), product(pg, "Kirra Corn Flakes 875")
    r = cmd(client, pid, [
        {"type": "AddPosition", "position_id": "p1", "surface_id": s["id"], "product_id": oats["id"], "facings_wide": 2},
        {"type": "AddPosition", "position_id": "p2", "surface_id": s["id"], "product_id": kirra["id"], "facings_wide": 1},
    ])
    assert r.status_code == 200
    pos = r.json()["positions"]
    assert pos["p2"]["x_mm"] == 2 * 190 + SETTINGS["gap_mm"]
    assert pos["p1"]["facings_deep"] == 440 // 70  # deepest that fits
    r = cmd(client, pid, [{"type": "MovePosition", "position_id": "p2", "surface_id": s["id"], "seq": 0}])
    assert r.json()["positions"]["p1"]["x_mm"] == 220 + SETTINGS["gap_mm"]
    r = cmd(client, pid, r.json()["inverse"])
    assert r.json()["positions"]["p2"]["x_mm"] == 382


def test_blocked_product_cannot_be_placed(client, pg):
    vexa = product(pg, "Vexa Multigrain Flakes 1 kg")
    assert vexa["eligibility"]["status"] == "blocked"
    r = cmd(client, pg["planogram"]["id"], [{"type": "AddPosition", "position_id": "v",
                                              "surface_id": eye_shelf(pg)["id"], "product_id": vexa["id"]}])
    assert r.status_code == 422
    assert "Safety flags" in r.json()["detail"]["message"]


def test_chilled_product_is_a_hard_break(client, pg):
    milk = product(pg, "Toned Milk")
    r = cmd(client, pg["planogram"]["id"], [{"type": "AddPosition", "position_id": "m",
                                              "surface_id": eye_shelf(pg)["id"], "product_id": milk["id"]}])
    assert r.status_code == 200
    rules = {f["rule_id"] for f in r.json()["evaluation"]["findings"] if f["severity"] == "hard"}
    assert {"R-02", "R-04"} <= rules  # temperature and section category


def test_locked_product_cannot_be_pushed(client, pg):
    pid, s = pg["planogram"]["id"], eye_shelf(pg)
    oats, kirra = product(pg, "Sunmill Rolled Oats"), product(pg, "Kirra Corn Flakes 875")
    cmd(client, pid, [
        {"type": "AddPosition", "position_id": "a", "surface_id": s["id"], "product_id": oats["id"], "facings_wide": 2},
        {"type": "AddPosition", "position_id": "b", "surface_id": s["id"], "product_id": kirra["id"], "facings_wide": 1},
        {"type": "Lock", "position_id": "b"},
    ])
    r = cmd(client, pid, [{"type": "SetFacings", "position_id": "a", "wide": 3, "high": 1, "deep": 6}])
    assert r.status_code == 422
    assert "locked at 382 mm" in r.json()["detail"]["message"]


def test_autofill_invariants(client, pg):
    pid = pg["planogram"]["id"]
    surfaces = {s["id"]: s for s in pg["surfaces"]}
    products = {p["id"]: p for p in pg["products"]}
    # lock one product first: auto-fill must leave it exactly where it is
    s = eye_shelf(pg, bay=3)
    oats = product(pg, "Sunmill Rolled Oats")
    cmd(client, pid, [{"type": "AddPosition", "position_id": "locked", "surface_id": s["id"], "product_id": oats["id"],
                       "facings_wide": 3}, {"type": "Lock", "position_id": "locked", "locked_x_mm": 300}])
    first = client.post(f"/api/planograms/{pid}/autofill").json()
    second = client.post(f"/api/planograms/{pid}/autofill").json()
    assert first["positions"] == second["positions"]  # deterministic

    ev = first["evaluation"]
    assert ev["hard_breaks"] == 0
    assert ev["summary"]["fill_pct"] > 80
    anchor = next(p for p in first["positions"] if p["id"] == "locked")
    assert (anchor["x_mm"], anchor["facings_wide"], anchor["surface_id"]) == (300, 3, s["id"])
    for p in first["positions"]:
        assert products[p["product_id"]]["temperature"] == "ambient"
        if p["id"] != "locked":
            assert p["reason"] and "R-30" in p["rule_ids"]
    used: dict = {}
    for p in first["positions"]:
        right = p["x_mm"] + products[p["product_id"]]["width_mm"] * p["facings_wide"]
        used[p["surface_id"]] = max(used.get(p["surface_id"], 0), right)
    assert all(used[sid] <= surfaces[sid]["width_mm"] for sid in used)
    reasons = {u["name"]: u["reason"] for u in first["unplaced"]}
    assert "Too tall" in reasons["Sunmill Oats Jumbo Tub 2 kg"]
    assert "Safety" in reasons["Vexa Multigrain Flakes 1 kg"]

    # accepting the proposal keeps the lock and gives the same score
    r = cmd(client, pid, [{"type": "ReplacePositions", "positions": first["positions"], "keep_locked": True}])
    assert r.status_code == 200
    assert r.json()["evaluation"]["score"] == ev["score"]
    assert r.json()["positions"]["locked"]["x_mm"] == 300
