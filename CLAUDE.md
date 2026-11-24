# CLAUDE.md — Planogram Platform (Phase 1 POC)

## What this repo is
Proof of concept of the retail planogram platform in `docs/spec/` (Build Specification v2.1).
Phase 1 = floor planner, fixtures & sections, shelf planner, rule-based auto-fill. Progress: `TRACKER.md`.
Deliberately deferred to the full build: Azure, Entra ID, tenancy/RLS, Service Bus + outbox, edit leases,
layout revisions/freeze, versions/approval, product import, image pipeline, store app, ML/optimiser/AI.

## Golden rules (POC subset of spec 22.3)
1. Every change to a layout or planogram is a typed command (`engines/layout_doc.py`, `engines/planogram_doc.py`).
   Every command returns its inverse; undo sends the inverse. Never write rows directly from the API.
2. Engines in `services/api/planogram/engines` are pure: no database, no network, no clock. Dicts in, dicts out.
3. One request = one transaction (`db.unit_of_work`): changes and `command_log` commit together.
4. Geometry exists twice (`engines/geometry.py`, `apps/web/src/geometry/`). Change both and add a golden case in
   `packages/contracts/golden/fit_cases.json`.
5. Units: millimetres and grams. Product W/H/D follow the GS1 default front. Order on a shelf (seq) is the truth;
   x_mm is recalculated. Placement-locked positions are anchors and are never pushed.
6. Auto-fill returns a proposal; it is applied only when the planner accepts it (`ReplacePositions`).
7. Keep table and column names aligned with spec section 7.2 so the PostgreSQL move is mechanical.

## Modules added in POC v2 (docs/PHASES.md)
- `catalog_excel.py` + `imports.py`: product workbook template, validation (spec 9.3), staged import, pictures in `media/`.
- `layout_io.py`: design files (export/import a whole store by business codes). `engines/store_generator.py`: hypermarket layout for any size.
- `exports.py`: floor plan PDF, planogram PDF, execution workbook (reportlab, openpyxl).
- `services.autofill_many`: auto-fill a fixture or a whole store in one transaction.
- Demo catalogue: Open Food Facts (ODbL / CC BY-SA), demo tenant only; never mix into client data.
- Tests set `PLANOGRAM_SEED=csv` and a temp `PLANOGRAM_MEDIA`; never point tests at the dev media folder.

## Commands
- API: `cd services/api && .venv/Scripts/python -m uvicorn planogram.main:app --port 8000` (restart after Python changes; `fastapi dev` reload can hang on Windows)
- Web: `cd apps/web && npm run dev`
- Tests: `cd services/api && .venv/Scripts/python -m pytest -q` · `cd apps/web && npm test && npx tsc -b`
- E2E: `services/api/.venv/Scripts/python tools/e2e_demo.py <dir>` (both servers running)
- Reseed: `cd services/api && .venv/Scripts/python -m planogram.seed_loader --reset`
- On Git Bash, prefix commands that take `/paths` as arguments with `MSYS_NO_PATHCONV=1`.
