"""Seed store and layout commands (floor planner, fixtures and sections)."""
from .conftest import fixture_by_code, section_by_code


def post(client, cmds):
    return client.post("/api/stores/SMS-001/layout/commands", json={"commands": cmds})


def get_layout(client):
    return client.get("/api/stores/SMS-001/layout").json()["layout"]


def test_seed_matches_the_spec(client):
    data = client.get("/api/stores/SMS-001/layout").json()
    layout = data["layout"]
    assert len(layout["fixtures"]) == 118
    assert len(layout["sections"]) == 133
    assert sum(1 for b in layout["bays"].values() if b["side"] != "TOP") == 330
    assert len(data["categories"]) == 49
    # the designed store is clean
    assert {k: len(v) for k, v in data["checks"].items()} == {
        "overlaps": 0, "aisle_warnings": 0, "blocked_doors": 0, "out_of_bounds": 0}


def test_moving_a_gondola_onto_another_is_flagged_and_undo_restores(client, layout):
    g05, g06 = fixture_by_code(layout, "G05"), fixture_by_code(layout, "G06")
    r = post(client, [{"type": "MoveFixture", "fixture_id": g05["id"], "x_mm": g06["x_mm"] - 500, "y_mm": g05["y_mm"]}])
    assert r.status_code == 200
    body = r.json()
    assert any("G05 overlaps G06" in o["message"] for o in body["checks"]["overlaps"])
    r = post(client, body["inverse"])
    assert r.json()["checks"]["overlaps"] == []


def test_rotate_swaps_footprint_and_faces(client, layout):
    ec = fixture_by_code(layout, "EC-G01-F")
    r = post(client, [{"type": "RotateFixture", "fixture_id": ec["id"], "rotation_deg": 90,
                       "x_mm": ec["x_mm"], "y_mm": ec["y_mm"]}])
    assert r.status_code == 200
    after = fixture_by_code(get_layout(client), "EC-G01-F")
    assert (after["footprint_w_mm"], after["footprint_d_mm"]) == (ec["footprint_d_mm"], ec["footprint_w_mm"])
    assert after["faces"] == "W"  # S turned a quarter clockwise


def test_place_and_remove_fixture(client):
    r = post(client, [{"type": "PlaceFixture", "fixture_id": "new-1", "template_code": "PALLET", "code": "PL-09",
                       "x_mm": 20000, "y_mm": 21500, "rotation_deg": 0}])
    assert r.status_code == 200
    assert "new-1" in get_layout(client)["fixtures"]
    post(client, r.json()["inverse"])
    assert "new-1" not in get_layout(client)["fixtures"]


def test_sections_cannot_overlap(client, layout):
    g03 = fixture_by_code(layout, "G03")
    r = post(client, [{"type": "CreateSection", "section_id": "x", "fixture_id": g03["id"], "side": "A",
                       "bay_from": 5, "bay_to": 7, "category_code": "BRK"}])
    assert r.status_code == 422
    assert "overlap" in r.json()["detail"]["message"]


def test_assignment_locked_section_cannot_be_resized(client, layout):
    baby = section_by_code(layout, "G06-B-07")
    assert baby["assignment_locked"]
    r = post(client, [{"type": "ResizeSection", "section_id": baby["id"], "bay_from": 8, "bay_to": 12}])
    assert r.status_code == 422
    assert "assignment-locked" in r.json()["detail"]["message"]


def test_split_then_undo_restores_the_section(client, layout):
    spr = section_by_code(layout, "G03-A-07")
    r = post(client, [{"type": "SplitSection", "section_id": spr["id"], "at_bay": 10, "new_section_id": "new-sec"}])
    assert r.status_code == 200
    after = get_layout(client)["sections"]
    assert (after[spr["id"]]["bay_to"], after["new-sec"]["bay_from"], after["new-sec"]["code"]) == (9, 10, "G03-A-10")
    post(client, r.json()["inverse"])
    after = get_layout(client)["sections"]
    assert "new-sec" not in after and after[spr["id"]]["bay_to"] == 12


def test_shelf_height_snaps_to_notches_and_stays_between_neighbours(client, layout):
    g03 = fixture_by_code(layout, "G03")
    top = f"{g03['id']}-A1-s5"
    assert post(client, [{"type": "UpdateSurface", "surface_id": top, "height_from_floor_mm": 1530}]).status_code == 422
    assert post(client, [{"type": "UpdateSurface", "surface_id": top, "height_from_floor_mm": 1225}]).status_code == 422
    assert post(client, [{"type": "UpdateSurface", "surface_id": top, "height_from_floor_mm": 1525}]).status_code == 200
