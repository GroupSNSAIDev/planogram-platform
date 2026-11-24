"""Store execution pack: floor plan PDF, planogram PDF and execution workbook."""
import io

from openpyxl import load_workbook


def test_exports_after_autofill(client):
    r = client.post("/api/stores/SMS-001/autofill", json={"fixture_code": "G03", "only_empty": True})
    assert r.status_code == 200 and r.json()["sections_filled"] == 4
    again = client.post("/api/stores/SMS-001/autofill", json={"fixture_code": "G03", "only_empty": True}).json()
    assert again["sections_filled"] == 0 and again["sections_skipped"] == 4  # planned sections are kept

    floor = client.get("/api/stores/SMS-001/exports/floor.pdf")
    assert floor.status_code == 200 and floor.content[:4] == b"%PDF"
    plan = client.get("/api/stores/SMS-001/exports/planograms.pdf?fixture=G03")
    assert plan.status_code == 200 and plan.content[:4] == b"%PDF" and plan.content.count(b"/Type /Page") >= 5

    xlsx = client.get("/api/stores/SMS-001/exports/execution.xlsx?fixture=G03")
    assert xlsx.status_code == 200
    wb = load_workbook(io.BytesIO(xlsx.content))
    assert wb.sheetnames == ["Summary", "Sections", "Placements", "Pick list"]
    sections = wb["Sections"]
    placements = wb["Placements"]
    assert sections.max_row - 1 == 4
    total = sum(sections.cell(row=r, column=8).value for r in range(2, sections.max_row + 1))
    assert placements.max_row - 1 == total
    header = [c.value for c in placements[1]]
    for col in ("Section", "Bay", "Shelf", "GTIN", "Product", "Facings wide", "Units on shelf", "Cases to fill", "Width mm"):
        assert col in header
