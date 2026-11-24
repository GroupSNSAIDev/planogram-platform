"""Print an auto-fill proposal for a section as a text grid (dev helper).
Usage (from services/api): .venv/Scripts/python ../../tools/autofill_grid.py G03-A-01"""
import sys
from collections import defaultdict

from fastapi.testclient import TestClient

from planogram.main import app

code = sys.argv[1] if len(sys.argv) > 1 else "G03-A-01"
with TestClient(app) as c:
    pg = c.get(f"/api/sections/{code}/planogram").json()
    surf = {s["id"]: s for s in pg["surfaces"]}
    prods = {p["id"]: p for p in pg["products"]}
    af = c.post(f"/api/planograms/{pg['planogram']['id']}/autofill").json()
    ev = af["evaluation"]
    print("score", ev["score"], ev["rule_scores"], "hard", ev["hard_breaks"], ev["summary"])
    for f in ev["findings"]:
        print("  F", f["severity"], f["rule_id"], f["message"])
    for u in af["unplaced"]:
        print("  U", u["name"], "-", u["reason"])
    grid = defaultdict(list)
    for p in af["positions"]:
        s = surf[p["surface_id"]]
        grid[(s["level"], s["bay_idx"])].append(f'{prods[p["product_id"]]["brand"][:3]}x{p["facings_wide"]}')
    levels = sorted({s["level"] for s in surf.values()}, reverse=True)
    bays = sorted({s["bay_idx"] for s in surf.values()})
    for lvl in levels:
        print(lvl, " | ".join(",".join(grid[(lvl, b)]) for b in bays))
