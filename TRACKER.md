# Progress tracker

_Last updated: 23 Nov 2026._

## POC v2 (current): phases A–H, see [docs/PHASES.md](docs/PHASES.md)

**Overall: all 8 phases built and verified.** Two items are only partly done (marked 🟡).

| Phase | What | Status | Evidence |
|---|---|---|---|
| A | Real product catalogue | 🟡 | 702 real Indian/branded products with pack photos (Open Food Facts) across 27 food categories. Personal care and home care keep placeholders: Open Beauty Facts is unreachable from this network |
| B | Product Excel template + import | ✅ | Template with instructions, dropdowns and picture column; upload → validation report (spec 9.3) → publish; demo catalogue loaded through this path (715 published, 5 bad GTINs rejected) |
| C | Real images on shelves | ✅ | Pack photos on every facing in the shelf planner, panel thumbnails, product library page |
| D | Explain auto-fill | ✅ | Rules page in plain English; 7-step trace and per-product "why this shelf" scores in every proposal |
| E | Big stores + pro floor designer | ✅ | Stores of any size up to 300 × 300 m; generated hypermarket SMS-002 (90 × 62 m, 60,063 sq ft, 345 fixtures, 395 sections, 0 layout issues); full-screen designer with rulers, minimap, hover cards, search, multi-select, align, zone/pillar/door tools; design file export/import round-trips exactly |
| F | Easy manual placement | ✅ | Section picker for the whole store, section switcher, auto-fill a fixture or the whole store (351 sections in ~2 s). Mini-planogram thumbnails not built |
| G | Store execution pack | ✅ | Floor plan PDF (A3, to scale, every fixture code, index), planogram PDF (one page per section with product pictures and a numbered list), execution Excel (Summary, Sections, Placements with pictures, Pick list) |
| H | Polish and QA | ✅ | 42 pytest + 20 vitest pass; type-check and build clean; 10-step browser e2e passes |

### Known limitations (v2)
- Sizes of the open-data products are **estimated** from the declared quantity and picture shape, not measured.
- Big generated stores give each category a lot of shelf; with ~26 products per category many shelves stay partly empty until a store's full catalogue is imported.
- Pictures are raw open-data photos (backgrounds, some angles); client pictures come through the template.
- Single user, no sign-in, no approval workflow yet (Phase 2 of the spec).

---

# Phase 1 POC (v1, completed)

_Plan: 10 working days (see the plan in the README and `docs/spec/` §23)._

**Overall: about 95% of the Phase 1 POC scope is built and verified.** All three editors and rule-based auto-fill
work end to end on the sample store. What remains is demo polish and rehearsal with the team.

| Status | Meaning |
|---|---|
| ✅ Done | Built and covered by an automated check (pytest, vitest or the browser e2e run) |
| 🟡 Partial | Works, but simpler than planned (see notes) |
| ⬜ Not started | Planned for Phase 1 but not built |
| ⏭️ Phase 2 | Out of POC scope by decision |

## Schedule

| Day | Work | Status | Evidence |
|---|---|---|---|
| 1 | Repo scaffold, CLAUDE.md, spec + seed copied, FastAPI + SQLite models, Vite shell with design tokens and nav | ✅ | `README.md`, `CLAUDE.md`, app shell |
| 2 | Seed loader (bays/surfaces/sections), demo cereal catalogue, synthetic sales stats, read endpoints | ✅ | 118 fixtures · 330 shelf bays · 133 sections · 49 categories · 94 products (`test_seed_matches_the_spec`) |
| 3 | Floor planner (read): floor, zones, landmarks, fixtures by department colour, labels, pan/zoom, inspector | ✅ | Matches `seed/store_SMS-001_plan.svg`; seed store has 0 overlaps / 0 aisle warnings / 0 blocked doors |
| 4 | Floor editing: move with snap, rotate, place from library, delete, undo/redo, live overlap/aisle/door checks | ✅ | e2e step 1 (drag G05 onto G06 → overlap, undo, rotate survives reload) |
| 5 | Fixture library page; Fixture & sections page with two-side elevation and section overlays | ✅ | 13 templates; G03 shows its 4 sections |
| 6 | Section tools (create, resize, split, merge, assign category, assignment lock, image policy); shelf-height drag with 25 mm notch snap | ✅ | e2e step 2; tests for overlap refusal, locked section, split + undo, notch snap |
| 7 | Shelf planner render: true-size shelves and products, product panel with eligibility badges, eye-level band, mm rulers | ✅ | G03-A-01 renders at true scale |
| 8 | Shelf editing: drag in/move/reorder, facings, remove, placement lock, live fit (TS) + golden parity, findings panel + score | ✅ | 11 golden fit cases pass in **both** Python and TypeScript; e2e steps 4–5 |
| 9 | Auto-fill engine, preview with reason per product, accept/reject, locked anchors respected, unplaced list | ✅ | Fills G03-A-01 in ~0.03 s: 34 SKUs, 88% fill, score 94, 0 hard breaks; deterministic; e2e steps 3 and 6 |
| 10 | Store overview page, demo reset, README, end-to-end rehearsal | 🟡 | Built, and the automated e2e run passes. **Still to do:** a live rehearsal with the team |

## Feature checklist

### Floor planner
- ✅ Whole store drawn from data (floor, 9 zones, landmarks, 118 fixtures, section colours by department)
- ✅ Pan (drag background), zoom (wheel, buttons, fit), layer toggles (zones, sections, labels, grid)
- ✅ Move with snap (10–500 mm), arrow-key nudge, rotate 90° (R), delete, place by dragging a template from the library
- ✅ Live checks while dragging: overlaps, pillars, blocked doors, out of floor, narrow aisles (face-aware), with counters and an issue list
- ✅ Inspector: position, footprint, faces, zone, temperature, linear shelf, distances, sections with links
- ✅ Undo/redo (Ctrl+Z / Ctrl+Y), persisted to SQLite, audit row in `command_log`
- 🟡 Distances are straight-line, not walking routes (spec says A* on a 250 mm grid)
- ⬜ Multi-select, align and distribute
- ⏭️ Drawing walls/zones, tracing a background plan, layout revisions and freeze

### Fixtures & sections
- ✅ Fixture library: 13 templates with elevation preview, sizes, shelves, load, usage count
- ✅ Elevation of each side at true height, eye-level band, bay numbers
- ✅ Sections: create from free bays, resize (inputs or edge handles), split, merge, assign category (filtered by fixture temperature), image policy, remove
- ✅ Assignment locks: a locked section cannot be resized, split, merged, reassigned or removed
- ✅ Shelf height: drag or type, 25 mm notch snap, 50 mm minimum gap, "apply to section / side"
- ⏭️ Template editor (create/edit templates), peg grids, chest grids

### Shelf planner
- ✅ True-size products (brand-coloured boxes; dashed placeholder when there is no image), one box per facing
- ✅ Product panel: search, "eligible only", "this category only", badges (Eligible / Size estimated / No image / Blocked / Wrong temperature), count on shelf
- ✅ Drag from panel to shelf, drag between shelves and bays, reorder, live fit preview (green/red, with reason)
- ✅ Facings wide/high/deep, units, days of supply, placement details, remove, clear unlocked
- ✅ Placement lock (L): keeps shelf, order, facings and left edge; edits that would push it are refused
- ✅ Hard rules: fit (width, height, depth, stacking), temperature, eligibility, section category, load, lock
- ✅ Soft rules with weighted score: eye level (R-12), heavy low (R-07), brand blocks (R-15), days of supply (R-30), share of shelf vs sales (R-40), assortment (R-50)
- ⏭️ Orientation other than front; peg, chest, bin, bar and stack modes; templates and store overrides

### Auto-fill (rules, no ML)
- ✅ Candidates by category and eligibility; facings from days of supply; shelf levels by eye level, heavy-low and brand block; packs around locked anchors; trims on overflow; shares spare space
- ✅ A reason and rule ids for every position; unplaced products listed with the reason
- ✅ Preview first, nothing saved until Accept; deterministic (same input, same output)

### Quality and tooling
- ✅ 33 pytest tests (engines, commands, rules, auto-fill invariants, golden cases)
- ✅ 20 vitest tests (TypeScript geometry on the same golden cases)
- ✅ `tools/e2e_demo.py`: the demo script run in headless Chromium, with screenshots and API checks (all steps pass)
- ✅ TypeScript strict mode, production build
- ⬜ Performance test (2,000 facings at 30 fps) not measured. Current sections have about 160 facings and are smooth.
- ⬜ Nothing committed to git yet (repository initialised only)

## Differences from the plan
| Plan | What was built | Why |
|---|---|---|
| Client applies commands locally and batches every 1 s | Each edit is sent as soon as it happens; the floor applies moves/rotations optimistically | Simpler and safe for one user; batching comes with edit leases in the full build |
| Typed Pydantic command union | Commands are validated inside the pure engines (clear 422 messages) | Same safety, less code for the POC |
| `uv` for Python, TanStack Router | `pip` + venv, React Router | Fewer moving parts on Windows without Docker |
| Product + product_revision tables | One `product` table holding the current facts | Revisions and freezing are Phase 2 |

## Known limitations
- Auto-fill places each product once (no second location) and only fills shelf surfaces.
- Only G03-A-01 has a full demo catalogue (34 cereals). Other sections have 1–3 sample products each, so auto-fill there looks sparse.
- Single user: no sign-in, no edit leases, no version history beyond undo in the current session.

## Phase 2 (not in this POC)
Azure deployment, Entra sign-in, tenancy, layout revisions and freeze, planogram versions and approval, product and image
onboarding, store mobile app, exports and daily exposure, then ML: demand forecast (LightGBM), space elasticity,
placement scorer (LightGBM ranker), CP-SAT optimiser, and the LLM copilot that proposes change sets.
