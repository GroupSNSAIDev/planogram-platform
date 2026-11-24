"""End-to-end run of the POC demo script in a real browser (Playwright, headless Chromium).

Needs both servers running (API on :8000, web on :5173). Resets the demo data first.
    services/api/.venv/Scripts/python tools/e2e_demo.py [screenshot_dir]
Each step asserts against the API and saves a screenshot.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

WEB, API = "http://localhost:5173", "http://127.0.0.1:8000/api"
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "e2e-shots")
OUT.mkdir(parents=True, exist_ok=True)


def api(path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(f"{API}{path}", method="POST" if body is not None else "GET",
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def shot(page: Page, name: str) -> None:
    page.screenshot(path=str(OUT / f"{name}.png"))
    print(f"  screenshot {name}.png")


def floor_to_screen(page: Page, x_mm: float, y_mm: float) -> tuple[float, float]:
    """Mirror FloorCanvas' fit transform (22 px rulers, pad 40, 48 x 32 m floor)."""
    box = page.locator("canvas").first.bounding_box()
    w, h, r = box["width"], box["height"], 22
    s = min((w - r - 80) / 48000, (h - r - 80) / 32000)
    ox, oy = r + (w - r - 48000 * s) / 2, r + (h - r - 32000 * s) / 2
    return box["x"] + ox + x_mm * s, box["y"] + oy + y_mm * s


def shelf_to_screen(page: Page, x_mm: float, h_mm: float, max_h: int = 1800) -> tuple[float, float]:
    """Mirror ShelfCanvas' default (1:1 height) transform."""
    box = page.locator("canvas").first.bounding_box()
    s = (box["height"] - 16 - 40) / (max_h + 320)
    return box["x"] + 56 + x_mm * s, box["y"] + 16 + (max_h + 320 - h_mm) * s


def main() -> None:
    api("/demo/reset", {})
    layout = api("/stores/SMS-001/layout")["layout"]
    fx = {f["code"]: f for f in layout["fixtures"].values()}
    errors: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("pageerror", lambda e: errors.append(str(e)))

        print("1. Floor planner: overlap, undo, rotate, persist")
        page.goto(f"{WEB}/stores/SMS-001/floor")
        page.wait_for_selector("canvas")
        page.wait_for_timeout(800)
        g05 = fx["G05"]
        sx, sy = floor_to_screen(page, g05["x_mm"] + 500, g05["y_mm"] + 6000)
        tx, ty = floor_to_screen(page, g05["x_mm"] + 500 + 2600, g05["y_mm"] + 6000)
        page.mouse.move(sx, sy)
        page.mouse.down()
        page.mouse.move((sx + tx) / 2, sy, steps=5)
        page.mouse.move(tx, ty, steps=10)
        page.wait_for_timeout(200)
        shot(page, "1a_floor_dragging_overlap")
        page.mouse.up()
        page.wait_for_timeout(900)
        expect(page.get_by_role("button", name="Overlaps 1")).to_be_visible()
        assert api("/stores/SMS-001/layout")["layout"]["fixtures"][g05["id"]]["x_mm"] != g05["x_mm"]
        shot(page, "1b_floor_overlap_saved")
        page.keyboard.press("Control+z")
        page.wait_for_timeout(900)
        expect(page.get_by_role("button", name="Overlaps 0")).to_be_visible()
        assert api("/stores/SMS-001/layout")["layout"]["fixtures"][g05["id"]]["x_mm"] == g05["x_mm"], "undo did not restore G05"

        ec = fx["EC-G01-F"]
        cx, cy = floor_to_screen(page, ec["x_mm"] + 500, ec["y_mm"] + 300)
        page.mouse.click(cx, cy)
        page.wait_for_timeout(300)
        page.keyboard.press("r")
        page.wait_for_timeout(900)
        page.reload()
        page.wait_for_selector("canvas")
        rotated = api("/stores/SMS-001/layout")["layout"]["fixtures"][ec["id"]]
        assert rotated["rotation_deg"] == 90 and rotated["footprint_w_mm"] == 600, rotated
        page.mouse.click(*floor_to_screen(page, rotated["x_mm"] + 300, rotated["y_mm"] + 500))
        page.wait_for_timeout(400)
        shot(page, "1c_floor_endcap_rotated_after_reload")

        print("2. Fixture & sections: split, locked section, shelf snap")
        page.goto(f"{WEB}/stores/SMS-001/fixtures/G03")
        page.get_by_text("Spreads & honey").first.click()
        page.get_by_role("button", name="Split").click()
        page.wait_for_timeout(900)
        secs = [s for s in api("/stores/SMS-001/layout")["layout"]["sections"].values() if s["fixture_id"] == fx["G03"]["id"]]
        assert len(secs) == 5, f"expected 5 sections on G03 after split, got {len(secs)}"
        new = next(s for s in secs if s["code"] == "G03-A-10")
        page.locator("select").nth(1).select_option("HDR")  # category of the selected (new) section
        page.wait_for_timeout(900)
        assert api("/stores/SMS-001/layout")["layout"]["sections"][new["id"]]["category_code"] == "HDR"
        shot(page, "2a_sections_split_and_assigned")

        # drag the top shelf of bay 1 side A down a little: it must land on a 25 mm notch
        page.evaluate("document.querySelectorAll('.overflow-x-auto').forEach(e => e.scrollLeft = 0)")
        page.wait_for_timeout(200)
        svg = page.locator("svg.select-none").first
        box = svg.bounding_box()
        top_surface = f"{fx['G03']['id']}-A1-s5"
        before = api("/stores/SMS-001/layout")["layout"]["surfaces"][top_surface]["height_from_floor_mm"]
        # geometry of SideElevation: left 48, top 34, band 26, +8; scale from svg height
        s = (box["height"] - 34 - 26 - 8 - 26) / 1800
        y_shelf = box["y"] + 34 + 26 + 8 + (1800 - before) * s
        x_bay1 = box["x"] + 48 + 500 * s
        page.mouse.move(x_bay1, y_shelf)
        page.mouse.down()
        page.mouse.move(x_bay1, y_shelf + 30, steps=8)  # ~30 px down
        page.mouse.up()
        page.wait_for_timeout(900)
        after = api("/stores/SMS-001/layout")["layout"]["surfaces"][top_surface]["height_from_floor_mm"]
        assert after % 25 == 0 and after < before, (before, after)
        print(f"  shelf moved {before} -> {after} mm")
        shot(page, "2b_shelf_dragged")
        page.keyboard.press("Control+z")
        page.wait_for_timeout(900)
        assert api("/stores/SMS-001/layout")["layout"]["surfaces"][top_surface]["height_from_floor_mm"] == before

        page.goto(f"{WEB}/stores/SMS-001/fixtures/G06")
        page.get_by_text("Baby care").first.click()
        expect(page.get_by_text("Assignment-locked")).to_be_visible()
        expect(page.get_by_role("button", name="Resize")).to_be_disabled()
        shot(page, "2c_locked_section")

        print("3. Shelf planner: real pictures, auto-fill preview and accept")
        page.goto(f"{WEB}/sections/G03-A-01/plan")
        expect(page.get_by_text("This section is empty")).to_be_visible()
        page.get_by_role("button", name="Auto-fill", exact=True).click()
        expect(page.get_by_text("Auto-fill proposal")).to_be_visible()
        expect(page.get_by_text("How auto-fill decided")).to_be_visible()
        page.wait_for_timeout(800)
        shot(page, "3a_autofill_preview")
        page.get_by_role("button", name="Accept").click()
        page.wait_for_timeout(1000)
        pg = api("/sections/G03-A-01/planogram")
        assert len(pg["positions"]) >= 25, len(pg["positions"])
        assert pg["evaluation"]["hard_breaks"] == 0
        assert pg["evaluation"]["summary"]["fill_pct"] > 80, pg["evaluation"]["summary"]
        with_pictures = sum(1 for q in pg["positions"].values() if next(x for x in pg["products"] if x["id"] == q["product_id"])["image"])
        print(f"  {len(pg['positions'])} positions, {with_pictures} with real pictures, fill {pg['evaluation']['summary']['fill_pct']}%")
        shot(page, "3b_autofill_accepted")

        print("4. Placement-lock a product, then try to push it")
        prods = {x["id"]: x for x in pg["products"]}
        surf = {x["id"]: x for x in pg["surfaces"]}
        first_bay = pg["section"]["bay_from"]
        # the left-most product that has a neighbour on its left (so we can try to push it)
        target = min((q for q in pg["positions"].values() if q["seq"] > 0),
                     key=lambda q: ((surf[q["surface_id"]]["bay_idx"] - first_bay) * 1000 + q["x_mm"], -surf[q["surface_id"]]["level"]))
        su = surf[target["surface_id"]]
        page.get_by_role("button", name="1:1 height").click()
        page.wait_for_timeout(400)
        x_scr, y_scr = shelf_to_screen(page, (su["bay_idx"] - first_bay) * 1000 + target["x_mm"] + 20, su["height_from_floor_mm"] + 40)
        box = page.locator("canvas").first.bounding_box()
        if x_scr > box["x"] + box["width"] - 30:       # pan the shelf so the product is on screen
            dx = x_scr - (box["x"] + box["width"] / 2)
            page.mouse.move(box["x"] + box["width"] / 2, box["y"] + 8)
            page.mouse.down()
            page.mouse.move(box["x"] + box["width"] / 2 - dx, box["y"] + 8, steps=10)
            page.mouse.up()
            page.wait_for_timeout(300)
            x_scr -= dx
        page.mouse.click(x_scr, y_scr)
        page.wait_for_timeout(300)
        expect(page.get_by_text(prods[target["product_id"]]["name"]).last).to_be_visible()
        page.keyboard.press("l")
        page.wait_for_timeout(900)
        locked = api("/sections/G03-A-01/planogram")["positions"][target["id"]]
        assert locked["locked"] and locked["locked_x_mm"] == target["x_mm"], locked
        shot(page, "4a_locked")
        row = sorted((q for q in pg["positions"].values() if q["surface_id"] == target["surface_id"]), key=lambda q: q["seq"])
        left = row[[q["id"] for q in row].index(target["id"]) - 1]
        r = urllib.request.Request(f"{API}/planograms/{pg['planogram']['id']}/commands", method="POST",
                                   data=json.dumps({"commands": [{"type": "SetFacings", "position_id": left["id"], "wide": left["facings_wide"] + 3, "high": 1, "deep": left["facings_deep"]}]}).encode(),
                                   headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(r)
            raise AssertionError("growing into a locked product should fail")
        except urllib.error.HTTPError as e:
            print(f"  refused as expected: {json.loads(e.read())['detail']['message']}")

        print("5. Drag a chilled product onto the shelf: temperature hard break; blocked product")
        chilled = next(x for x in pg["products"] if x["temperature"] == "chilled" and x["eligibility"]["status"] != "blocked")
        blocked = next(x for x in pg["products"] if x["category_code"] == "BRK" and x["eligibility"]["status"] == "blocked")
        page.get_by_label("Eligible only").uncheck()
        page.get_by_label("Breakfast cereals only").uncheck()
        page.get_by_placeholder("Search name, brand, GTIN…").fill(chilled["gtin"])
        card = page.get_by_text(chilled["name"]).first
        page.get_by_role("button", name="1:1 height").click()   # back to the default view after panning
        page.wait_for_timeout(400)
        tx, ty = shelf_to_screen(page, 300, 1250)
        canvas = page.locator("canvas").first
        cbox = canvas.bounding_box()
        card.drag_to(canvas, target_position={"x": max(10, tx - cbox["x"]), "y": ty - cbox["y"]})
        page.wait_for_timeout(1000)
        ev = api("/sections/G03-A-01/planogram")["evaluation"]
        assert ev["hard_breaks"] >= 1 and any(f["rule_id"] == "R-02" for f in ev["findings"]), ev["findings"][:3]
        print(f"  dropped {chilled['name']} (chilled): {ev['hard_breaks']} hard break(s)")
        shot(page, "5a_temperature_hard_break")
        page.get_by_placeholder("Search name, brand, GTIN…").fill(blocked["gtin"])
        expect(page.get_by_text("Blocked · Safety flags not reviewed").first).to_be_visible()
        shot(page, "5b_blocked_product")
        page.evaluate("document.activeElement.blur()")  # shortcuts are ignored while typing
        page.keyboard.press("Control+z")
        page.wait_for_timeout(900)
        assert api("/sections/G03-A-01/planogram")["evaluation"]["hard_breaks"] == 0

        print("6. Re-run auto-fill: the locked product stays put")
        page.get_by_role("button", name="Auto-fill", exact=True).click()
        expect(page.get_by_text("Auto-fill proposal")).to_be_visible()
        expect(page.get_by_text("1 locked kept in place")).to_be_visible()
        shot(page, "6a_autofill_respects_lock")
        page.get_by_role("button", name="Accept").click()
        page.wait_for_timeout(900)
        final = api("/sections/G03-A-01/planogram")["positions"][target["id"]]
        assert final["locked"] and final["x_mm"] == target["x_mm"] and final["surface_id"] == target["surface_id"], final

        print("7. Downloads: floor plan PDF, planogram PDF, execution Excel, design file")
        for path, kind in [("/stores/SMS-001/exports/floor.pdf", b"%PDF"), ("/stores/SMS-001/exports/planograms.pdf?fixture=G03", b"%PDF"),
                           ("/stores/SMS-001/exports/execution.xlsx?fixture=G03", b"PK"), ("/stores/SMS-001/layout/export", b"{")]:
            resp = page.request.get(f"{API}{path}")
            assert resp.ok and resp.body()[:len(kind)] == kind, path
            (OUT / path.split("/")[-1].split("?")[0]).write_bytes(resp.body())
            print(f"  {path}: {len(resp.body()) / 1e6:.1f} MB")
        page.goto(f"{WEB}/stores/SMS-001/fixtures/G03")
        page.get_by_role("button", name="Download").click()
        expect(page.get_by_text("Execution sheet (Excel)")).to_be_visible()
        shot(page, "7a_download_menu")

        print("8. Big store: full-screen designer, auto-fill the whole store, search")
        r = page.request.post(f"{API}/stores/SMS-002/autofill", data={"only_empty": True})
        assert r.ok, r.text()
        print(f"  SMS-002: {r.json()['sections_filled']} sections auto-filled, {r.json()['positions']} placements")
        page.goto(f"{WEB}/design/SMS-002")
        page.wait_for_selector("canvas")
        page.wait_for_timeout(1200)
        expect(page.get_by_role("button", name="Overlaps 0")).to_be_visible()
        page.get_by_placeholder("Find fixture or category…").fill("G12")
        page.keyboard.press("Enter")
        page.wait_for_timeout(900)
        expect(page.get_by_text("Open fixture, sections & products")).to_be_visible()
        shot(page, "8a_designer_big_store")

        print("9. Products: upload the Excel template and read the report")
        page.goto(f"{WEB}/products")
        tpl = page.request.get(f"{API}/catalog/template.xlsx").body()
        tpl_path = OUT / "template.xlsx"
        tpl_path.write_bytes(tpl)
        page.locator("input[type=file]").first.set_input_files(str(tpl_path))
        page.get_by_role("button", name="Upload and check").click()
        expect(page.get_by_text("template.xlsx")).to_be_visible()
        expect(page.get_by_text("1 rows")).to_be_visible()
        shot(page, "9a_import_report")
        page.get_by_role("button", name="Discard").click()

        print("10. Store overview")
        page.goto(f"{WEB}/stores/SMS-001")
        page.wait_for_timeout(1200)
        shot(page, "10a_store_overview")
        browser.close()

    if errors:
        print("PAGE ERRORS:", *errors, sep="\n  ")
        sys.exit(1)
    print("ALL STEPS PASSED")


if __name__ == "__main__":
    main()
