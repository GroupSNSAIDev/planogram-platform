"""Big stores: generated layouts, design file export/import, zones and landmarks."""


def checks(client, code):
    return {k: len(v) for k, v in client.get(f"/api/stores/{code}/layout").json()["checks"].items()}


def test_generated_store_is_clean(client):
    r = client.post("/api/stores", json={"code": "BIG-1", "name": "Big test", "width_m": 90, "depth_m": 62, "layout": "generated"})
    assert r.status_code == 200, r.text
    assert r.json()["fixtures"] > 300 and r.json()["sections"] > 350
    assert checks(client, "BIG-1") == {"overlaps": 0, "aisle_warnings": 0, "blocked_doors": 0, "out_of_bounds": 0}
    # section codes can repeat across stores; each store's own sections are separate
    layout = client.get("/api/stores/BIG-1/layout").json()["layout"]
    assert any(s["code"] == "G01-A-01" for s in layout["sections"].values())


def test_empty_store_and_duplicate_code(client):
    assert client.post("/api/stores", json={"code": "E1", "name": "Empty", "width_m": 20, "depth_m": 15, "layout": "empty"}).status_code == 200
    assert client.post("/api/stores", json={"code": "E1", "name": "Again", "width_m": 20, "depth_m": 15, "layout": "empty"}).status_code == 422


def test_design_round_trip_with_planogram(client):
    pg = client.get("/api/sections/G03-A-01/planogram").json()
    prop = client.post(f"/api/planograms/{pg['planogram']['id']}/autofill").json()
    client.post(f"/api/planograms/{pg['planogram']['id']}/commands",
                json={"commands": [{"type": "ReplacePositions", "positions": prop["positions"], "keep_locked": True}]})
    design = client.get("/api/stores/SMS-001/layout/export").content
    r = client.post("/api/stores/import", files={"file": ("d.json", design, "application/json")}, data={"code": "COPY-1"})
    assert r.status_code == 200, r.text
    assert r.json()["fixtures"] == 118 and r.json()["sections"] == 133 and r.json()["positions"] == len(prop["positions"])
    copy = client.get("/api/stores/COPY-1/layout").json()["layout"]
    sec = next(s for s in copy["sections"].values() if s["code"] == "G03-A-01")
    again = client.get(f"/api/sections/{sec['id']}/planogram").json()
    xs_before = sorted((p["x_mm"], p["facings_wide"]) for p in prop["positions"])
    xs_after = sorted((p["x_mm"], p["facings_wide"]) for p in again["positions"].values())
    assert xs_before == xs_after
    # importing over an existing code needs replace
    assert client.post("/api/stores/import", files={"file": ("d.json", design, "application/json")}, data={"code": "COPY-1"}).status_code == 422
    assert client.delete("/api/stores/COPY-1").status_code == 200


def test_zone_and_landmark_commands_with_undo(client):
    url = "/api/stores/SMS-001/layout/commands"
    r = client.post(url, json={"commands": [
        {"type": "AddZone", "zone": {"id": "z-new", "code": "Z-NEW", "kind": "entrance", "name": "Promo court", "rect": [1000, 1000, 5000, 4000]}},
        {"type": "AddLandmark", "landmark": {"id": "p-new", "kind": "pillar", "name": "Pillar X", "rect": [24000, 19000, 600, 600]}},
        {"type": "ResizeFloor", "width_mm": 50000, "depth_mm": 33000},
    ]})
    assert r.status_code == 200, r.text
    layout = client.get("/api/stores/SMS-001/layout").json()["layout"]
    assert any(z["id"] == "z-new" for z in layout["zones"]) and layout["store"]["width_mm"] == 50000
    client.post(url, json={"commands": r.json()["inverse"]})
    layout = client.get("/api/stores/SMS-001/layout").json()["layout"]
    assert not any(z["id"] == "z-new" for z in layout["zones"]) and layout["store"]["width_mm"] == 48000
    assert not any(lm["id"] == "p-new" for lm in layout["landmarks"])
