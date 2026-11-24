# Planogram Platform — proof of concept (v2)

Design a store floor of any size, define fixtures and category sections, fill shelves with **real products and
pictures** automatically by rules (no ML yet) or by hand, and hand stores a ready-to-execute pack:
a **floor plan PDF**, a **planogram PDF** with product pictures and an **execution Excel**.

- Full design: [docs/spec/](docs/spec/Planogram_Platform_Build_Specification_v2_1.md)
- Phases: [docs/PHASES.md](docs/PHASES.md)
- Progress: [TRACKER.md](TRACKER.md)

## Run it (Windows, no Docker needed)

Needs Python 3.13+ and Node 22+.

```bash
# 1. API (FastAPI + SQLite) on http://127.0.0.1:8000
cd services/api
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m uvicorn planogram.main:app --port 8000
#    first start builds planogram.db: sample store SMS-001, the 60,000 sq ft hypermarket SMS-002,
#    and the real product catalogue (seed/catalogue/Product_Catalogue_Demo.xlsx, ~15 s)

# 2. Web app (React + Vite) on http://localhost:5173, in a second terminal
cd apps/web
npm install
npm run dev
```

Open http://localhost:5173. **Reset demo data** (bottom of the left menu) rebuilds everything.

## What you can do

| Area | Where | What |
|---|---|---|
| Stores | Stores | Create a store of any size up to 300 × 300 m: an empty floor, or a generated hypermarket layout (racetrack aisle, gondola blocks, chilled/frozen back wall, staples and home-care walls, fresh at the entrance, checkout bank). Import and export design files. |
| Floor designer | Floor planner, or **Open in new tab** for full screen | Drag fixtures from the library, move/rotate/delete, Shift+click or Shift+drag to multi-select, align and distribute, draw zones, pillars and doors, search a fixture or category, rulers and overview map, hover cards, live overlap/aisle/door checks, undo/redo. |
| Fixtures & sections | Click a fixture → Open fixture, sections & products | Elevation of each side; create, resize, split, merge, lock sections; drag shelf heights (25 mm notches); auto-fill the whole fixture. |
| Shelf planner | Shelf planner (all sections of the store) | Real pack pictures at true size; drag products in, move, facings, placement locks, live fit, findings and score; auto-fill with a reason per product and a step-by-step explanation; section switcher. |
| Products | Products & imports | 715 real products with pictures; blank template and full catalogue as Excel; upload a filled workbook (+ optional pictures ZIP) → validation report → publish. |
| Rules | Rules & auto-fill | Every rule in plain English, its weight and parameters, and how auto-fill works. |
| Downloads | Download / Store pack menus | Floor plan PDF, planogram PDF (store, fixture or section), execution Excel, design file. |

## Product workbook (for stores and suppliers)

`seed/catalogue/Product_Import_Template.xlsx` (or **Blank template** in the app) has an Instructions sheet, a Products
sheet (one row per product: SKU, GTIN, name, brand, category, W × H × D mm, weight, temperature, safety flags,
price, units per day) and a Categories sheet. Pictures: insert the photo over the row's Image cell, or put file
names in *Image file* and upload a ZIP, or give an *Image URL*. Validation follows spec §9.3 (GTIN check digit,
sizes, temperature vs category, safety flags, picture shape). `Product_Catalogue_Demo.xlsx` is the same template
filled with the demo catalogue; the demo database is loaded through this exact import path.

Demo product data and pictures come from Open Food Facts (ODbL / CC BY-SA), for the demo tenant only
(`seed/catalogue/ATTRIBUTION.md`). Pack sizes are estimated from the declared quantity and picture shape.
Rebuild with `tools/fetch_catalogue.py` then `tools/build_seed_workbook.py`.

## Tests

```bash
cd services/api && .venv/Scripts/python -m pytest -q        # 42 tests: engines, commands, rules, auto-fill, imports, stores, exports
cd apps/web && npm test                                      # TypeScript geometry on the shared golden cases
cd apps/web && npx tsc -b && npm run build                   # type-check and production build
# end-to-end in a real browser (both servers running; pip install playwright && playwright install chromium)
services/api/.venv/Scripts/python tools/e2e_demo.py e2e-shots   # 10 steps, screenshots and downloads in e2e-shots/
```

## Layout

```
apps/web/src/
  app/            shell, navigation, current store, theme, export menu, toasts
  api/            typed API client
  geometry/       TS fit checks + floor checks (mirror the Python engines; golden-tested)
  canvas/         canvas hooks (size, keys, image cache)
  features/       floor/ fixtures/ sections/ shelf/ store/ products/ rules/
services/api/planogram/
  engines/        pure Python: geometry, layout_checks, layout_doc, planogram_doc, context, rules, autofill, store_generator
  api/            routes.py (layouts, planograms), catalog.py (products, imports), stores.py (stores, design files, exports)
  services.py     load docs, apply commands, persist only what changed, store-wide auto-fill
  catalog_excel.py, imports.py   product workbook template, validation, staged import
  layout_io.py    design file export/import
  exports.py      floor plan PDF, planogram PDF, execution workbook
seed/             SMS-001 seed files; catalogue/ (real catalogue, pictures, workbooks)
tools/            e2e_demo.py, fetch_catalogue.py, build_seed_workbook.py, shot.py, autofill_grid.py
```
