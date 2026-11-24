# Planogram & Space Planning Platform — Build Specification v2.1

> Prepared by FusionexLabs · 23 November 2026 · Draft for review. Diagrams and screenshots are in the PDF version.

## How to use this document with Claude Code

- Put the Markdown copy in the repository at `docs/spec/`, the CLAUDE.md template (section 22.3) at the repository root and the seed files in `seed/`.
- Start with the first two weeks in section 23 and the walking skeleton (epic E1). Name the story id (for example S1.3) in each session and ask for a short plan before code.
- Keep the golden rules in CLAUDE.md: commands only, pure engines, module boundaries, composite tenant keys, one transaction per request, frozen revisions, millimetres.
- When a design question comes up, check the ADRs (section 4). If the answer changes, write a new ADR rather than silently changing code.
- Use the acceptance criteria as test names. A story is done when its tests and the fitness functions in section 24 pass.


## 1. Executive summary

We are building a web platform where retail planners draw a store floor, place real fixtures on it, fill every fixture with products shown at true size with real pack images, and apply the retailer's rules, locks and auto-fill. Approved plans are published to stores and exported with full context so that every placement can be joined to sales and used to train models. Later versions add an optimiser and AI that suggest and, within strict guardrails, apply changes automatically.

**Version 2.1 (this document)** answers an external design review of version 2.0, adds a complete sample mall store to build and test against (section 10), lists every page of the web app (section 11), and defines exactly what data is recorded for machine learning (section 17). Development starts with a thin end-to-end slice on that sample store.

### 1.1 What changed in version 2.1

An independent review of version 2.0 (produced with ChatGPT and shared by the project owner) raised a set of findings. We checked each one against the version 2.0 text. Every point we could check was correct, so each one is fixed below. Only the review's summary was available, not its full list of 49 findings; any further items will be handled the same way.

**Table 1. Review findings, verdicts and changes**

| Review finding | Verdict | Change in v2.1 | Where |
|---|---|---|---|
| Approved plans are not frozen: product sizes, images and shelf geometry used by an approved plan can change later | Correct | Immutable **product revisions** and **layout revisions**; a version pins the exact revisions and a manifest hash when it is submitted; approved versions are read-only and reproducible | §7.3, §16.2 |
| No real “section” entity; locks mix up “this category owns this space” with “this product stays here”; growing A's facings can push a locked B | Correct | New **section** entity (category on a bay range of one fixture side); **assignment locks** and **placement locks** are separate; locked positions are anchors that other edits must flow around or fail | §7.3, §13.3 |
| Approval, scheduled activation and the real store reset are one state | Correct | Separate states plus a **store_reset** record per fixture (started, done, verified with photo) | §16 |
| Training export can double count sales when a SKU sits in two places | Correct | Sales stay at store × SKU × day; placements are separate rows; a daily **exposure** table joins them at the same grain | §17 |
| Product data and fit rules are loose: images required in one place, optional in another; rotation, clearance, load and fixture behaviour not defined | Correct | Placement needs verified sizes, temperature and safety flags; images are optional (scaled placeholder) unless a section requires them; rotation table, clearances, load limits and per-fixture behaviour defined | §8, §9.3 |
| Revisions, audit, jobs and events are not written atomically; retries not safe; the event dispatcher sits in a worker that scales to zero | Correct (a real bug) | One transaction writes change, audit, job row and outbox row; **idempotency keys** in PostgreSQL; the outbox relay runs inside the always-on API with a cron safety net | §6.6, §12.4, §21 |
| Tenant isolation relies on row-level security only | Correct | **Composite (tenant_id, id) keys** on every foreign key, so a row can never point at another tenant's row | §7.5, §20 |
| Browser upload with SAS needs a reachable Blob endpoint, but storage is private | Correct | Pilot uploads go through the API in chunks into private storage; no browser-to-Blob path | §9.6, §18, §21 |
| Private networking for Service Bus needs the Premium tier | Correct | Standard tier with Entra ID only (local keys off) for the pilot; Premium budgeted if the client requires network isolation | §21.2 |
| All PDF bookmarks and table-of-contents links open the cover page | Correct (verified) | PDF build fixed and checked automatically: every link now opens its own page | This file |
| The sample GTIN fails its check digit | Correct | Examples now use valid GTINs; demo products use the GS1 20–29 restricted-circulation prefixes | App. B, §10 |
| Start with one real store and a thin end-to-end path; file-first onboarding; people approve everything in the pilot; keep the estimate provisional | Agree | Walking skeleton on the sample store by week 6, then the client's real pilot store; SAP and DataKart APIs move to V1.5; no AI auto-apply in the pilot (people approve every change); about 23 weeks, firmed up after phase 0 | §23 |

We also made one change of our own while fixing the above: section edit locks moved from Redis to PostgreSQL **edit leases** with a fencing token, so a lease that expires during a slow save can never overwrite newer work (§12.4).

### 1.2 How version 2.0 extended version 1.0

Version 1.0 of this design covered the pilot. Version 2.0 keeps the same core and plans further ahead: we studied where the market is going (store-specific plans at scale, continuous optimisation, AI agents for bulk edits, photo-based compliance, digital twins) and made sure the base we build now supports those steps without a rewrite.

**Table 2. Main changes in version 2.0**

| Area | Version 1.0 | Version 2.0 (this document) |
|---|---|---|
| Plans per store | One planogram per fixture section | **Template + store overrides**: cluster templates with small, typed store changes; store-specific plans without copies |
| How edits happen | Edit positions directly | **Every edit is a typed command** (screen, bulk job and AI use the same path, validated by one engine) |
| AI | ML model later, details open | **Autonomy levels L0–L4**, change sets, policy engine, durable approvals, test vs control stores |
| Product data | Import product file | **Full onboarding pipeline**: SAP API, GS1 DataKart, templates, image cut-out, quality score, fix queue |
| Events | Job notifications | **Transactional outbox + Service Bus topics** so sales, delists and photos can trigger re-planning |
| Tenancy | Single client | **Tenant-ready** (row-level security) and partner-ready (suppliers) from day one |
| Database | PostgreSQL 16+ | **PostgreSQL 18** with PostGIS (geometry) and pgvector (image and text embeddings) |
| Evaluation | Quality targets | **ATAM-style review**: utility tree, trade-offs, risks and automated fitness functions |

### 1.3 Key decisions at a glance

**Table 3. Key decisions**

| Decision | Choice | Why |
|---|---|---|
| Architecture style | Modular monolith API + background workers | Fast for a team of three; modules can be split later |
| Front end | React 19.2, TypeScript 7, Vite 8, react-konva | Mature, typed, fast; Konva is built for interactive editors |
| Back end | Python 3.14, FastAPI, Pydantic v2, SQLAlchemy 2 | One language for API, geometry, rules, optimiser, ML and AI |
| Database | Azure Database for PostgreSQL 18 (Flexible Server) | Relational core, JSONB, PostGIS, pgvector, managed backups |
| Messaging | Azure Service Bus (Standard in the pilot) fed by a transactional outbox | Reliable jobs, dead-lettering, domain events; nothing lost or sent twice |
| Long workflows | Durable Task Scheduler | Approvals and rollouts that wait for days and survive restarts |
| Optimiser | Google OR-Tools CP-SAT (V2) | Open source, strong for assignment with many constraints |
| AI | Pydantic AI agents with MCP tools; Microsoft Foundry models | Typed outputs; AI can only call our safe commands |
| Images | BiRefNet (MIT) cut-out on Container Apps (GPU on demand) | Commercial-friendly licence; scale to zero |
| Hosting | Azure Container Apps, Static Web Apps, Front Door | Managed, autoscaling, low operations load |

### 1.4 Timeline

About **23 weeks** of planned work for a team of three reaches a pilot in one store (phases P0–P7, section 23). A walking skeleton (floor → fixture → section → products → approve → reset → export) runs on the sample store by about week 6. Upgrade steps V1.5, V2 and V3 follow, each started by a business gate (section 25). The estimate is provisional and is firmed up after phase 0, when the quality of product sizes, images, floor plans and the sales feed is known.


## 2. Where planogramming is going

Before choosing the base, we looked at what leading vendors, researchers and retailers are doing now. The aim is simple: build the version-1 foundation so that each of these future steps is an addition, not a rebuild. Sources are listed in Appendix E.

### 2.1 Six shifts we design for

**Table 4. Market shifts and design responses**

| Shift | What we see in the market | What it means for our base |
|---|---|---|
| 1 · Store-specific plans at scale | RELEX, Blue Yonder and NIQ Spaceman all promote automated, store-specific planograms instead of one plan per cluster. RELEX reports a UK convenience retailer automating over 30,000 store-specific planograms a year. | Template planograms with typed store overrides; bulk generation as background jobs; store clusters as data. |
| 2 · Continuous, AI-driven optimisation | Blue Yonder describes moving from periodic planning cycles to continuous optimisation that keeps plans up to date as demand changes. | Event backbone (outbox → Service Bus topics) so sales shifts, delists and new items can trigger re-planning. |
| 3 · Agents for bulk edits | Blue Yonder's Shelf-Ops Agent swaps discontinued items and updates hundreds of planograms from natural-language requests. | Every edit is a typed command; AI produces commands, not database writes; MCP tools wrap the same API. |
| 4 · Closed-loop execution with vision | Shelf photos are compared with the planogram; a published study covers 7,000+ 7-Eleven stores in Taiwan. | Realogram and compliance tables beside planograms; photo upload API; product image embeddings stored now. |
| 5 · Digital twin, shelf labels, cameras | ESL vendors such as Hanshow now offer store digital twins that combine shelf labels, vision and 3D maps. | True-size 3D-ready geometry (mm), stable position IDs for label binding, open export format. |
| 6 · Explainable, collaborative planning | Vendors stress explainable decisions and supplier co-creation of planograms. | Provenance on every placement; tenant- and partner-ready security (supplier role, row-level security). |

### 2.2 What research says about optimisation and AI

- **Optimisation is mature and explainable.** Shelf-space allocation has been studied for decades. Recent work such as OPTIMUS (2026) uses a knapsack model for assortment and a mixed-integer model solved with OR-Tools for bay allocation, using space-elasticity curves, and reports sales and margin lift in tests.
- **Generative models are being tried for planogram synthesis** (for example diffusion models that learn from successful layouts), but they still need constraint checks; one paper reports 94.4% constraint satisfaction, which means some outputs break rules. Our design always passes AI output through the rules engine and a solver repair step.
- **LLMs are good at intent, weak at geometry.** Layout papers combine LLMs with integer programming or physics engines. We use the LLM to turn a request into typed commands and let deterministic code do geometry.
- **Vision for compliance is in production** at large chains; it needs product reference images and stable planogram data, both of which our onboarding pipeline and data model produce from day one.

### 2.3 Product data in India

Product master quality decides how good every planogram looks. In India, GS1 India's **DataKart** is the national product data repository: brand owners share attributes, images and dimensions with retailers, and GS1 India positions it explicitly as an aid to planogramming. Premium users get API integration with ERPs such as SAP. Package sizes follow the **GS1 Package and Product Measurement Standard** (height base to top, width left to right, depth front to back, seen from the default front), and image file names follow the **GS1 Product Image Specification**, which has a planogram image section and GTIN-based file naming. We adopt both so imported data needs no translation.


## 3. Scope, users and requirements

### 3.1 Scope

**Table 5. Scope by version**

| Version 1 (pilot) | Later versions |
|---|---|
| Product onboarding from files (Excel/CSV + image ZIP), GS1-style images, cut-out, quality score, fix queue | SAP and DataKart APIs (V1.5); supplier portal and capture app (V1.5–V2) |
| Sample mall store SMS-001 with seed data for development, demos and tests | Client store imports from CAD (V1.5) |
| 2D floor planner with walls, zones, landmarks and fixtures | 3D store viewer, DXF import (V1.5) |
| Fixture library and editor for every surface kind | Fixture import from vendor catalogues |
| Sections (category to bay range); shelf planner with true-size images, facings, assignment and placement locks | Live multi-user co-editing (CRDT) if needed |
| Rules as data, validation, scoring, explanations | Rule learning from approved plans (V2) |
| Heuristic auto-fill with a reason per placement | CP-SAT optimiser and demand forecasts (V2) |
| Templates and store overrides; versions; approval; publishing | Bulk change sets across many stores (V1.5) |
| Store view (mobile web), reset confirmation per fixture, issue reports with photos | Photo compliance with vision models (V3) |
| Training export with daily exposure (XLSX, CSV, Parquet, JSON) and store PDF pack | AI levels L2–L4, copilot (V2–V3) |
| Audit, monitoring, CI/CD, infrastructure as code | ESL binding, digital twin import, .psa/.pln exchange |

Out of scope: replacing ERP or POS, pricing, ordering and replenishment, and store hardware.

### 3.2 Users and roles

| Role | What they do | Main screens |
|---|---|---|
| Admin | Users, roles, tenants, templates, rule libraries, integrations | Admin console |
| Category planner | Onboards products, draws floors, edits planograms, runs auto-fill, prepares change sets | All editors |
| Approver | Reviews diffs and scores, approves or rejects, schedules publishing | Approvals, compare |
| Store user | Views published plans, reports gaps and issues with photos | Store app |
| Data analyst | Downloads exports, builds reports and training sets | Exports, BI |
| Supplier (V2) | Maintains own products and images; proposes changes for own brands | Supplier portal |
| Service principals | Integration jobs and the AI service act with scoped, audited permissions | None (API only) |

### 3.3 Functional requirements

**Table 6. Functional requirements**

| ID | Requirement | Ver. |
|---|---|---|
| FR-01 | Import products from Excel/CSV templates and PIM exports with saved column-mapping profiles (SAP S/4HANA and GS1 DataKart APIs in V1.5) | V1 |
| FR-02 | Validate GTIN check digits, units, sizes, required fields and duplicates; give each product a quality score | V1 |
| FR-03 | Bulk-upload images (ZIP, folder, DataKart); match by GTIN file name; remove background; crop; make renditions | V1 |
| FR-04 | Check that image shape matches declared width/height; flag blur, low resolution and duplicates | V1 |
| FR-05 | Review queue to fix, approve or reject imported rows and images; nothing bad blocks good rows | V1 |
| FR-06 | Create stores, clusters, floors, walls, entrances, checkouts, pillars and zones | V1 |
| FR-07 | Trace over an uploaded floor plan image or PDF at a set scale | V1 |
| FR-08 | Place, move, rotate, snap and align fixtures; check overlaps, aisle widths and blocked doors | V1 |
| FR-09 | Fixture template library for gondolas, wall bays, end caps, chillers, door coolers, chest freezers, peg walls, bins, pallets, checkout racks | V1 |
| FR-10 | Edit bays and surfaces: shelf heights on notches, depths, peg grids, doors, load limits, temperature | V1 |
| FR-11 | Drag products onto surfaces at true size; set facings wide/high/deep, orientation, stacking | V1 |
| FR-12 | Live fit checks (width, height, depth, weight, temperature) while editing | V1 |
| FR-13 | Locks on plan, fixture, section, surface, position or product, as either assignment locks (space belongs to a category) or placement locks (a product keeps its place) | V1 |
| FR-14 | Rule library: hard and soft rules by category, zone, cluster; test rules on a plan | V1 |
| FR-15 | Auto-fill a section from rules, sales and templates with a reason per placement | V1 |
| FR-16 | Validation report; hard breaks block approval; soft rules give a score | V1 |
| FR-17 | Template planograms per cluster; store planograms as template + overrides; re-resolve on template change | V1 |
| FR-18 | Versions (draft, in review, approved, scheduled, published, retired); compare any two versions | V1 |
| FR-19 | Approval workflow with comments, reminders and scheduled publishing | V1 |
| FR-20 | Store view on phones; product lookup by barcode; issue reports with photos | V1 |
| FR-21 | Training export per approved version (10 sheets) and nightly lake export | V1 |
| FR-22 | Store planogram PDF pack per fixture | V1 |
| FR-23 | Audit log of every command with actor, reason and before/after | V1 |
| FR-24 | Bulk change sets: apply the same commands across many planograms with preview and approval | V1.5 |
| FR-25 | 3D viewer and DXF floor import | V1.5 |
| FR-26 | Capture app for pack photos with barcode scan and size guide | V1.5 |
| FR-27 | Demand forecasts, space elasticity and CP-SAT optimiser | V2 |
| FR-28 | AI suggestions at levels L1–L2 with change-set review | V2 |
| FR-29 | Copilot: natural-language requests turned into change sets | V2 |
| FR-30 | Supplier portal with scoped access | V2 |
| FR-31 | Photo to draft planogram (realogram digitisation) | V2+ |
| FR-32 | Policy auto-apply (L3) and continuous planning with test vs control (L4) | V3 |
| FR-33 | Photo compliance scoring and store tasks | V3 |
| FR-34 | ESL binding and digital-twin export | V3 |
| FR-35 | Sections: assign a category to a bay range on one side of a fixture; split, merge, resize; show on floor and shelf views | V1 |
| FR-36 | Freeze inputs on submit: pin layout and product revisions and a manifest hash; approved versions are read-only and can be rebuilt byte-for-byte | V1 |
| FR-37 | Record store resets per fixture (planned, started, done, verified with photo) and derive daily exposure from them | V1 |
| FR-38 | Export placements, daily exposure and sales at matching grain so no sale is counted twice | V1 |
| FR-39 | Image policy per section: images required, or scaled placeholders allowed when sizes are verified | V1 |
| FR-40 | Block placement when sizes, temperature or safety flags are missing or unverified; show the reason | V1 |
| FR-41 | Load the sample mall store and its catalogue from seed files with one command | V1 |
| FR-42 | Floor and shelf reports: where every SKU is (store, zone, fixture, side, bay, shelf, position), facings, capacity and share of space | V1 |

### 3.4 Quality targets

**Table 7. Quality targets (non-functional requirements)**

| Quality | Target (proposal) | How measured |
|---|---|---|
| Editor smoothness | ≥ 30 fps while dragging with 2,000 facings on screen (aim 60) | Scripted Playwright trace on a mid-range laptop in CI |
| Open a planogram | < 2 s at the 95th percentile | Real-user monitoring in Application Insights |
| Save a command batch | < 300 ms p95 for up to 50 commands | API metrics |
| Validate a section | < 500 ms p95 for 300 positions | API metrics |
| Auto-fill | < 30 s for a section with up to 200 SKUs | Job duration metric |
| Optimiser (V2) | Best answer within 60 s time limit; gap reported | Job metric |
| Product import | 100,000 rows validated in < 10 min | Job metric |
| Image processing | ≥ 2,000 images per hour on CPU; more on GPU | Job metric |
| Scale (design) | 1,000 stores · 100,000 SKUs · 150 M positions incl. history | Load test with generated data |
| Concurrent users | 200 planners · 5,000 store users | Load test (Locust) |
| Availability | 99.5% monthly in V1; 99.9% target later | Availability tests |
| Data loss / recovery | RPO ≤ 5 min (point-in-time restore) · RTO ≤ 4 h | Quarterly restore drill |
| Reproducibility | An approved version rebuilds to the same manifest hash and the same export files | Nightly test rebuilds every approved version |
| Event delivery | Every committed change reaches Service Bus within 10 s, even when all workers are at zero | Outbox-lag metric and liveness test |
| Security | OWASP ASVS 5.0 Level 2 | Checklist review + automated scans |
| Accessibility | WCAG 2.2 AA for non-canvas screens | axe checks in E2E tests |
| Browsers | Latest Chrome and Edge (desktop); Safari and Chrome (mobile) | E2E matrix |

> **Note.** All targets are proposals sized for the pilot and a first rollout. They are confirmed in phase 0 and then become acceptance criteria and automated fitness functions (section 24).


## 4. Architecture principles and decisions

### 4.1 Principles

- **One safe path for change.** Every change to a plan, from a mouse drag to an AI suggestion, is a typed command checked by the same rules engine.
- **Data is the product.** We store where, what, why, who and when for every placement, so it can be explained, audited and learned from.
- **Rules are data, engines are code.** Planners change rules; developers change engines. The engine is deterministic and testable.
- **People stay in charge.** AI suggests; autonomy grows level by level only after it proves itself against control stores.
- **Simple first, ready to split.** One API deployable with strict module boundaries; heavy work in queued workers.
- **Managed over self-run.** Azure managed services wherever a good one exists.
- **Standards at the edges.** GS1 for products and images, OpenAPI for the API, OpenTelemetry for telemetry, MCP for AI tools.

### 4.2 Architecture decision records

**Table 8. Architecture decision records (status: proposed)**

| ID | Decision | Reason | Alternatives rejected |
|---|---|---|---|
| ADR-01 | Modular monolith API, separate workers | Team of three; one deployable is cheaper to run. Module boundaries enforced by import-linter so a module can be split out later. | Microservices now: more pipelines, networking and on-call work for no pilot benefit. |
| ADR-02 | Typed command model for all edits | UI, bulk jobs, templates and AI share one validated path; gives audit, undo, replay and AI safety. | Direct row updates: simpler at first, but no safe route for AI and bulk changes. |
| ADR-03 | Template planograms with store overrides | Store-specific plans without copying data; template changes flow to all stores. | Copy per store: easy, but thousands of drifting copies. |
| ADR-04 | One geometry model for all fixtures | Fixture → bay → surface → position with six surface kinds covers every fixture type. | Model per fixture type: more code, harder exports. |
| ADR-05 | Rules as JSON data, plugin rule types | Planners edit rules; new rule types are Python plugins; no schema change. | Rules in code; LLM judging rules (not repeatable). |
| ADR-06 | Edit in 2D, view in 3D | Precise editing; 3D viewer reads the same data later. | Full 3D editing: slower to build, harder to place precisely. |
| ADR-07 | Sequence on shelves, grid on pegs and chests | Order + facings is stable under edits; exact x is calculated. | Free x/y everywhere: drift and overlaps. |
| ADR-08 | Section edit leases in PostgreSQL + optimistic versions (revised in v2.1) | Two planners can work on different sections at once. The lease and the version check are written in the same transaction as the change, with a fencing token, so a stale lease can never overwrite newer work. | Redis TTL locks (v2.0): can expire mid-save with no fencing; live co-editing (Yjs CRDT) now: much more complex. |
| ADR-09 | PostgreSQL 18 as the single source of truth | Relational integrity, JSONB, PostGIS, pgvector and row-level security in one managed service. | Document DB: weaker joins and constraints; separate vector DB: more moving parts. |
| ADR-10 | Transactional outbox + Service Bus | Events are published only if the change committed; no lost or phantom events. | Publish directly from the API: risk of inconsistency. |
| ADR-11 | Durable Task Scheduler for long workflows | Approvals and rollouts wait for days and survive restarts; managed service with Python SDK. | Temporal (self-host or cloud) or a home-made state machine. |
| ADR-12 | AI emits change sets, never writes | Guardrails, explainability and rollback for every AI action. | Let the model edit positions directly: unsafe. |
| ADR-13 | Python engines, TypeScript quick checks | Authoritative checks in Python; instant browser checks in TypeScript; both pass the same golden test cases. | Node back end to share code: weaker for optimisation, ML and vision. |
| ADR-14 | Tenant-ready from day one | tenant_id on every row with PostgreSQL row-level security; cheap now, expensive later. | Single-tenant schema: rework if the product is offered to more retailers. |
| ADR-15 | Self-hosted BiRefNet for image cut-out | MIT licence, runs on our GPU-on-demand containers; paid API as fallback. | RMBG-2.0 weights: non-commercial licence unless bought. |
| ADR-16 | Azure managed platform | Matches the client blueprint; Container Apps, Static Web Apps, Front Door, Entra ID. | AKS or VMs: more operations work. |
| ADR-17 | Immutable product and layout revisions | An approved plan must always show and export exactly what was approved, even after sizes, images or shelves change. | Point to live rows: approved plans silently change. |
| ADR-18 | Frozen version manifest | On submit, the version pins revision ids, rule-set version and engine version, and stores a hash. Approval signs that hash. | Freeze only on publish: reviewers could approve something different from what is published. |
| ADR-19 | Section is a first-class entity | Category space is planned, locked, reported and learned from at section level. | Infer sections from product categories: breaks when a section is empty or mixed. |
| ADR-20 | Two kinds of lock | Assignment locks keep space for a category; placement locks keep a product in its place. Engines treat locked positions as fixed anchors. | One generic lock: ambiguous; edits silently move locked items. |
| ADR-21 | Exposure comes from confirmed resets | Models learn from what was really on the shelf, not from what was approved. | Use approval or publish date: wrong for every late or partial reset. |
| ADR-22 | Sales and exposure at store × SKU × day | One grain for sales, one row per placement, one exposure row per day: joins cannot double count. | Sales per placement row: counts a multi-location SKU twice. |
| ADR-23 | Atomic outbox with an always-on relay | Change, audit, job and event are one transaction; the relay runs in the API (minimum one replica) with a pg_cron safety net. | Relay in a scale-to-zero worker (v2.0): events stall when the queue is empty. |
| ADR-24 | Composite tenant keys | Every foreign key includes tenant_id, so cross-tenant references are impossible even with a bug or an admin connection. | Row-level security alone. |
| ADR-25 | Uploads through the API in the pilot | Storage stays private; the API streams chunks, checks type and size, and writes with managed identity. | Browser SAS upload: needs a public Blob endpoint or extra networking. |


## 5. Technology selection

Each major choice was scored against realistic alternatives on weighted criteria. Scores are 1 (poor) to 5 (best). Weights reflect this project: a small team, a long life, heavy interactive graphics, and AI later.

### 5.1 Canvas library for the editors

**Table 9. Canvas library comparison**

| Criterion (weight) | Konva + react-konva | PixiJS v8 | Fabric.js | tldraw SDK |
|---|---|---|---|---|
| Interactive editing: drag, transform, hit test (30%) | 5 | 3 | 4 | 4 |
| Performance with thousands of images (25%) | 4 | 5 | 3 | 3 |
| React integration (15%) | 5 | 3 | 2 | 5 |
| Licence for commercial use (15%) | 5 (MIT) | 5 (MIT) | 5 (MIT) | 2 (licence key needed in production) |
| Fit for a domain editor, not a whiteboard (15%) | 5 | 4 | 3 | 2 |
| **Weighted score** | **4.75** | **3.95** | **3.45** | **3.3** |

**Choice: Konva with react-konva.** Konva uses Canvas 2D with one canvas per layer, which suits editors with a static background and a busy foreground; PixiJS (WebGL/WebGPU) is faster for heavy animation, so the editor keeps its scene model independent of the renderer. If the 30-fps fitness function fails at scale, the product layer can move to PixiJS without changing data or commands.

### 5.2 Back-end language and framework

**Table 10. Back-end comparison**

| Criterion (weight) | Python + FastAPI | TypeScript + NestJS | .NET 9/10 + ASP.NET |
|---|---|---|---|
| Optimisation, ML, vision, LLM libraries (30%) | 5 | 2 | 3 |
| Team skill (FusionexLabs AI developers) (25%) | 5 | 4 | 2 |
| API performance for this load (15%) | 4 | 4 | 5 |
| Typed contracts, OpenAPI (15%) | 5 (Pydantic) | 4 | 5 |
| Code sharing with the browser (15%) | 2 | 5 | 2 |
| **Weighted score** | **4.4** | **3.55** | **3.2** |

**Choice: Python 3.14 with FastAPI.** Python 3.15 shipped in October 2026; we start on 3.14 because wheels for OR-Tools, scientific and ML libraries are mature, and plan the move to 3.15 in 2027. The browser-sharing gap is closed with golden test cases (ADR-13).

### 5.3 Other major choices

**Table 11. Other technology decisions**

| Need | Chosen | Considered | Deciding reasons |
|---|---|---|---|
| Database | PostgreSQL 18 on Azure Flexible Server | Azure SQL, Cosmos DB | GA on Azure with 80+ extensions incl. PostGIS, pgvector, pg_cron; JSONB; row-level security; built-in uuidv7() |
| Cache, live events | Azure Managed Redis | PostgreSQL LISTEN/NOTIFY only | Pub/sub across API replicas, caches, rate limits. Not used for edit locks (ADR-08) |
| Jobs and events | Azure Service Bus (Standard; Premium if isolated) | Celery + Redis, Kafka/Event Hubs | Dead-letter queues, duplicate detection, topics; managed. VNet and private endpoints need Premium |
| Long workflows | Durable Task Scheduler (Python SDK) | Temporal, custom state tables | Managed; human-approval pattern built in; works on Container Apps |
| Optimiser | OR-Tools CP-SAT | HiGHS/PuLP MIP, Timefold | Strong on assignment + logical constraints; Apache-2.0; Timefold's Python solver was discontinued |
| Agent framework | Pydantic AI (MIT) | Microsoft Agent Framework, LangGraph | Typed structured outputs, MCP support, durable-execution integration, model-agnostic |
| LLM hosting | Microsoft Foundry deployments | Direct vendor APIs | Data stays in the client's Azure tenant; enterprise terms; model choice |
| Background removal | BiRefNet (MIT), self-hosted | RMBG-2.0, paid APIs | RMBG-2.0 weights are non-commercial unless licensed; paid API kept as fallback |
| Hosting | Container Apps + Static Web Apps | AKS, App Service | Scale to zero, KEDA rules, serverless GPU, low operations work |
| Live co-editing (later) | Yjs + Hocuspocus (if needed) | Liveblocks (hosted) | Open source, self-hosted, standard CRDT |
| 3D viewer (V1.5) | React Three Fiber (three.js) | Babylon.js | Same React model; large ecosystem |
| Infrastructure as code | Bicep + azd | Terraform | Azure-native, no state file to manage |

### 5.4 Bill of materials (versions to pin in phase 0)

> **Licences.** PostGIS is GPL-2 but runs as a database extension inside the managed service, so our code is not affected. Licences are listed as published by each project; the client's legal team confirms them before go-live.

**Table 12. Technology bill of materials**

| Layer | Tool | Purpose | Licence |
|---|---|---|---|
| Front end | React 19.2 + React Compiler 1.0 | UI and automatic memoisation | MIT |
| Front end | TypeScript 7 (native compiler) | Types; 8–12× faster builds | Apache-2.0 |
| Front end | Vite 8 (Rolldown) | Dev server and builds | MIT |
| Front end | Konva + react-konva | 2D editors | MIT |
| Front end | Zustand + Immer | Editor state, command history | MIT |
| Front end | TanStack Query + TanStack Router | Server cache, typed routing | MIT |
| Front end | Tailwind CSS 4 + shadcn/ui (Radix) | Design system | MIT |
| Front end | Zod 4 + openapi-typescript | Runtime checks, generated API types | MIT |
| Front end | MSAL React | Entra ID sign-in | MIT |
| Front end | React Three Fiber + drei (V1.5) | 3D store viewer | MIT |
| Back end | Python 3.14 + uv | Runtime and package manager | PSF / MIT-Apache |
| Back end | FastAPI + Uvicorn | REST, WebSocket, OpenAPI 3.1 | MIT / BSD |
| Back end | Pydantic v2 | Schemas, validation, settings | MIT |
| Back end | SQLAlchemy 2 (async) + asyncpg + Alembic | Database access, migrations | MIT / Apache-2.0 |
| Back end | Shapely 2 | Footprints, overlaps, distances | BSD |
| Back end | Polars + pyarrow + openpyxl | Imports, Parquet, Excel | MIT / Apache-2.0 |
| Back end | Pillow + pyvips | Image resizing, WebP | MIT-CMU / LGPL |
| Back end | Playwright (Chromium) | Server-side PDF store packs | Apache-2.0 |
| Back end | azure-servicebus, azure-storage-blob, azure-identity | Azure SDKs | MIT |
| Back end | durabletask (Python SDK) | Durable workflows | MIT |
| Back end | OR-Tools (V2) | CP-SAT optimiser | Apache-2.0 |
| AI / ML | Pydantic AI + MCP Python SDK | Agents and tool server | MIT |
| AI / ML | LightGBM + scikit-learn | Forecasts, scoring, clustering | MIT / BSD |
| AI / ML | BiRefNet (ONNX Runtime / PyTorch) | Background removal | MIT |
| AI / ML | Image embedding model (e.g. SigLIP/DINOv2 family) | Similar products, duplicates, CV reference | Check per model |
| AI / ML | MLflow or Azure Machine Learning | Experiments and registry | Apache-2.0 / managed |
| Data | PostgreSQL 18 + PostGIS + pgvector + pg_cron + pg_trgm | Core data, geometry, vectors, jobs, search | PostgreSQL / GPL-2 (PostGIS) |
| Data | Azure Managed Redis | Cache, pub/sub, rate limits | Managed |
| Data | Azure Service Bus · Blob/ADLS Gen2 · Durable Task Scheduler | Messaging, files, workflows | Managed |
| Platform | Container Apps · Static Web Apps · Front Door + WAF · ACR · Key Vault | Hosting and edge | Managed |
| Platform | Microsoft Entra ID · Microsoft Foundry · Defender for Cloud | Identity, models, security | Managed |
| Platform | Azure Monitor + OpenTelemetry | Logs, metrics, traces | Managed / Apache-2.0 |
| DevOps | GitHub Actions · Bicep · azd · Docker | CI/CD and infrastructure | Service / MIT / Apache-2.0 |
| DevOps | pytest · Hypothesis · Schemathesis · Vitest · Playwright Test · Locust | Testing | MIT / MPL-2.0 / Apache-2.0 |
| DevOps | Ruff · mypy · import-linter · ESLint · Prettier | Quality gates | MIT / BSD |
| DevOps | Dependabot · CodeQL · Trivy · Syft (SBOM) | Supply-chain security | Service / Apache-2.0 |


## 6. System architecture

### 6.1 System context

*Figure 1. System context: people and systems around the platform (diagram in the PDF).*

### 6.2 Layered view

*Figure 2. Layers: channels, edge, core API modules, engines and workers, data, analytics (diagram in the PDF).*

### 6.3 Modules (bounded contexts)

**Table 13. Modules and their responsibilities**

| Module | Owns | Public interface (examples) | Publishes events |
|---|---|---|---|
| Identity & audit | tenants, users, roles, scopes, audit log, notifications | `current_user()`, `authorise(action, resource)` | user.* |
| Catalog & media | products, identifiers, packaging, images, embeddings, import runs | `get_product()`, `search()`, `start_import()` | product.published, product.changed, product.delisted |
| Stores & fixtures | stores, clusters, floors, zones, landmarks, fixture templates, layout revisions, fixtures, bays, surfaces, sections | `get_layout()`, `apply_layout_commands()`, `freeze_layout()` | layout.changed, section.changed |
| Planograms & versions | planograms (template/store), versions, positions, overrides, snapshots | `apply_commands()`, `resolve_store_version()`, `compare()` | planogram.changed, version.status_changed, version.published |
| Rules & locks | rules, rule sets, locks, validation results | `validate(version)`, `test_rules()` | validation.completed |
| Change sets & workflow | change sets, approvals, AI suggestions, activations, store resets, store tasks | `propose()`, `approve()`, `record_reset()` | changeset.applied, reset.completed |
| Integrations & exports | connectors, file drops, exports, exposure builder, sales/stock feeds | `export(version)`, `build_exposure(day)`, `ingest(feed)` | sales.loaded, export.ready |

Modules talk to each other only through their public service interfaces and events. Engines (geometry, rules, auto-fill, optimiser, export builders, imaging) are pure Python packages with no database access: objects in, objects out. The API and every worker reuse them. Boundaries are checked in CI with **import-linter** contracts.

### 6.4 Runtime view: editing a planogram

*Figure 3. A command batch from the editor: lease, validate, one atomic commit, then the relay publishes (diagram in the PDF).*

### 6.5 Runtime view: background auto-fill

*Figure 4. Auto-fill: the job row and its outbox row are written together; the always-on relay hands it to the queue (diagram in the PDF).*

### 6.6 Containers and deployables

**Table 14. Deployables**

| Deployable | Runs | Scaling | Notes |
|---|---|---|---|
| web (Static Web Apps) | React single-page app | Global edge | Images from Front Door cache |
| api (Container App) | FastAPI: REST, WebSocket, command handling, quick validation, chunked uploads, outbox relay loop | 1–4 replicas (minimum 1; 2 in production) | Stateless; leases in PostgreSQL; one replica holds the relay advisory lock |
| worker (Container App) | Imports, exports, auto-fill, PDF packs, exposure build | 0–N, KEDA on Service Bus queue length | Idempotent handlers (job id = message id) |
| optimizer (Container App, V2) | CP-SAT jobs | 0–N, CPU-heavy profile | Time-limited solves |
| vision (Container App) | Cut-out, embeddings, later CV models | 0–N, serverless GPU | Batch-friendly |
| ai-service (Container App, V2) | Agents, MCP tool server, policy engine | 1–2 replicas | Calls API with on-behalf-of tokens |
| scheduled jobs | Nightly exposure and exports, rebuild check of approved versions, clean-up | Cron | Container Apps jobs; pg_cron re-queues stuck outbox rows |


## 7. Domain and data architecture

*Figure 5. Core entities: physical store, plans, and products, changes and feedback (diagram in the PDF).*

### 7.1 Conventions

- Keys are UUIDv7 (time-ordered, generated by PostgreSQL 18's `uuidv7()`); products also keep the retailer SKU and a normalised GTIN-14 with a verified check digit.
- Lengths are whole millimetres, weights grams, angles degrees, money `numeric(12,2)`, times `timestamptz` in UTC.
- Floor coordinates: origin at the floor's top-left corner, x to the right, y downwards (matches the canvas). Geometry columns use PostGIS with SRID 0 (local millimetres).
- Product height, width and depth follow the GS1 default-front rule. Import profiles convert other orientations.
- Every tenant-owned row has `tenant_id`; every foreign key includes it (composite keys), and row-level security is on as a second wall.
- Facts that an approved plan depends on are **immutable revisions** (layout revisions, product revisions, image files). A change makes a new revision; nothing an approved plan points at is ever updated in place.
- Flexible settings (template parameters, rule parameters, product attributes) are JSONB, validated by Pydantic models with a JSON schema stored beside them.
- Rows that matter for history are never hard-deleted; they get a status (retired, delisted).

### 7.2 Core tables (DDL sketch)

The DDL below is the starting point for the first Alembic migration. Column lists are complete enough to build from; extra indexes are added as queries are written. The pattern to copy everywhere: `PRIMARY KEY (tenant_id, id)` and foreign keys that start with `tenant_id`.

```sql
-- conventions: uuidv7() keys (built into PostgreSQL 18), tenant_id on every row,
-- lengths in whole millimetres, weights in grams, timestamps in UTC.
-- v2.1: every tenant-owned table has UNIQUE (tenant_id, id) and every foreign key
-- includes tenant_id, so a row can never reference another tenant's row.
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS ltree;

CREATE TABLE tenant (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  name text NOT NULL, settings jsonb NOT NULL DEFAULT '{}'
);

CREATE TABLE store (
  id uuid NOT NULL DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenant(id),
  code text NOT NULL,                          -- same code as POS and ERP (SMS-001)
  name text NOT NULL, format text, cluster_id uuid,
  timezone text NOT NULL DEFAULT 'Asia/Kolkata',
  status text NOT NULL DEFAULT 'active',
  PRIMARY KEY (tenant_id, id), UNIQUE (tenant_id, code)
);

-- One layout revision = the whole physical store at one point in time.
-- Draft revisions are edited; frozen revisions never change (ADR-17).
CREATE TABLE layout_revision (
  id uuid NOT NULL DEFAULT uuidv7(), tenant_id uuid NOT NULL,
  store_id uuid NOT NULL, number int NOT NULL,
  status text NOT NULL CHECK (status IN ('draft','frozen','retired')),
  parent_id uuid, content_hash text, frozen_at timestamptz, frozen_by uuid,
  PRIMARY KEY (tenant_id, id), UNIQUE (tenant_id, store_id, number),
  FOREIGN KEY (tenant_id, store_id) REFERENCES store (tenant_id, id)
);

-- Rows below are copied into each new draft revision. Their ids stay the same
-- across revisions (stable identity), so the key is (tenant, revision, id).
CREATE TABLE floor (
  tenant_id uuid NOT NULL, layout_revision_id uuid NOT NULL, id uuid NOT NULL,
  level int NOT NULL DEFAULT 0,
  outline geometry(Polygon, 0) NOT NULL,       -- local mm coordinates, SRID 0
  background jsonb,                            -- {blob_path, mm_per_px, offset}
  PRIMARY KEY (tenant_id, layout_revision_id, id),
  FOREIGN KEY (tenant_id, layout_revision_id) REFERENCES layout_revision (tenant_id, id)
);

CREATE TABLE zone (
  tenant_id uuid NOT NULL, layout_revision_id uuid NOT NULL, id uuid NOT NULL,
  floor_id uuid NOT NULL, code text NOT NULL,
  kind text NOT NULL,          -- entrance, main_aisle, checkout, chilled, frozen, perimeter ...
  name text, area geometry(Polygon, 0) NOT NULL, priority int NOT NULL DEFAULT 0,
  PRIMARY KEY (tenant_id, layout_revision_id, id),
  FOREIGN KEY (tenant_id, layout_revision_id, floor_id)
    REFERENCES floor (tenant_id, layout_revision_id, id)
);
CREATE INDEX zone_area_gix ON zone USING gist (area);

CREATE TABLE landmark (
  tenant_id uuid NOT NULL, layout_revision_id uuid NOT NULL, id uuid NOT NULL,
  floor_id uuid NOT NULL,
  kind text NOT NULL,          -- entrance, exit, pillar, door, stockroom_door, trolley_bay
  name text, shape geometry(Polygon, 0) NOT NULL,
  PRIMARY KEY (tenant_id, layout_revision_id, id),
  FOREIGN KEY (tenant_id, layout_revision_id, floor_id)
    REFERENCES floor (tenant_id, layout_revision_id, id)
);

CREATE TABLE fixture_template (
  id uuid NOT NULL DEFAULT uuidv7(), tenant_id uuid NOT NULL,
  code text NOT NULL,                          -- GONDOLA_DS_12, MULTIDECK_2500 ...
  kind text NOT NULL, name text NOT NULL,
  defaults jsonb NOT NULL,                     -- bays, sizes, notch/peg pitch, surfaces
  behaviour jsonb NOT NULL,                    -- rules from the fixture behaviour table
  version int NOT NULL DEFAULT 1,
  PRIMARY KEY (tenant_id, id), UNIQUE (tenant_id, code, version)
);

CREATE TABLE fixture (
  tenant_id uuid NOT NULL, layout_revision_id uuid NOT NULL, id uuid NOT NULL,
  floor_id uuid NOT NULL, template_id uuid,
  code text NOT NULL,                          -- G01, MD-03, CO-07 ...
  kind text NOT NULL,          -- gondola, end_cap, wall_bay, multideck, door_freezer ...
  x_mm int NOT NULL, y_mm int NOT NULL, rotation_deg numeric(5,1) NOT NULL DEFAULT 0,
  footprint geometry(Polygon, 0) NOT NULL,
  temperature text NOT NULL DEFAULT 'ambient', -- ambient, chilled, frozen
  zone_id uuid, dist_entrance_mm int, dist_checkout_mm int,
  PRIMARY KEY (tenant_id, layout_revision_id, id),
  UNIQUE (tenant_id, layout_revision_id, code),
  FOREIGN KEY (tenant_id, layout_revision_id, floor_id)
    REFERENCES floor (tenant_id, layout_revision_id, id),
  FOREIGN KEY (tenant_id, template_id) REFERENCES fixture_template (tenant_id, id)
);

CREATE TABLE bay (
  tenant_id uuid NOT NULL, layout_revision_id uuid NOT NULL, id uuid NOT NULL,
  fixture_id uuid NOT NULL, side text NOT NULL DEFAULT 'A', idx int NOT NULL,
  width_mm int NOT NULL, height_mm int NOT NULL, depth_mm int NOT NULL,
  has_door bool NOT NULL DEFAULT false,
  PRIMARY KEY (tenant_id, layout_revision_id, id),
  UNIQUE (tenant_id, layout_revision_id, fixture_id, side, idx),
  FOREIGN KEY (tenant_id, layout_revision_id, fixture_id)
    REFERENCES fixture (tenant_id, layout_revision_id, id) ON DELETE CASCADE
);

CREATE TABLE surface (
  tenant_id uuid NOT NULL, layout_revision_id uuid NOT NULL, id uuid NOT NULL,
  bay_id uuid NOT NULL,
  kind text NOT NULL CHECK (kind IN ('shelf','peg','chest','bin','bar','stack')),
  idx int NOT NULL,                            -- 1 = lowest
  height_from_floor_mm int NOT NULL, width_mm int NOT NULL, depth_mm int NOT NULL,
  clear_height_mm int,                         -- calculated: gap to the surface above
  grid_cols int, grid_rows int, pitch_mm int,  -- for peg and chest
  max_load_g int, tilt_deg numeric(4,1) DEFAULT 0, lip_mm int DEFAULT 0,
  PRIMARY KEY (tenant_id, layout_revision_id, id),
  FOREIGN KEY (tenant_id, layout_revision_id, bay_id)
    REFERENCES bay (tenant_id, layout_revision_id, id) ON DELETE CASCADE
);

-- A section is a category's space: a bay range on one side of one fixture (ADR-19).
CREATE TABLE section (
  tenant_id uuid NOT NULL, layout_revision_id uuid NOT NULL, id uuid NOT NULL,
  fixture_id uuid NOT NULL, side text NOT NULL, bay_from int NOT NULL, bay_to int NOT NULL,
  code text NOT NULL,                          -- G01-A-01
  category_path ltree NOT NULL,                -- staples.atta
  image_policy text NOT NULL DEFAULT 'placeholder_ok'
    CHECK (image_policy IN ('required','placeholder_ok')),
  assignment_locked bool NOT NULL DEFAULT false,
  PRIMARY KEY (tenant_id, layout_revision_id, id),
  UNIQUE (tenant_id, layout_revision_id, code),
  CHECK (bay_from <= bay_to),
  FOREIGN KEY (tenant_id, layout_revision_id, fixture_id)
    REFERENCES fixture (tenant_id, layout_revision_id, id) ON DELETE CASCADE
);
-- an exclusion constraint (btree_gist) stops two sections overlapping on one fixture side

CREATE TABLE product (                         -- identity only; facts live in revisions
  id uuid NOT NULL DEFAULT uuidv7(), tenant_id uuid NOT NULL,
  sku text NOT NULL,                           -- retailer article number
  gtin14 char(14),                             -- normalised GTIN, check digit verified
  current_revision_id uuid,
  status text NOT NULL DEFAULT 'active',       -- active, delisted, blocked
  PRIMARY KEY (tenant_id, id), UNIQUE (tenant_id, sku)
);

CREATE TABLE product_revision (                -- immutable once written (ADR-17)
  id uuid NOT NULL DEFAULT uuidv7(), tenant_id uuid NOT NULL, product_id uuid NOT NULL,
  number int NOT NULL,
  name text NOT NULL, brand text, category_path ltree,
  width_mm int, height_mm int, depth_mm int,   -- GS1 default-front orientation
  dims_source text CHECK (dims_source IN ('measured','supplier','gs1','sap','estimated')),
  dims_verified bool NOT NULL DEFAULT false,
  weight_g int, case_pack int, tray_qty int,
  can_stack bool, max_stack int, can_lay_down bool, can_rotate bool,
  temperature text NOT NULL,                   -- ambient, chilled, frozen
  safety jsonb NOT NULL DEFAULT '{}',          -- hazardous, age_restricted, fragile, liquid
  attributes jsonb NOT NULL DEFAULT '{}',
  image_set_id uuid,                           -- images valid for this revision
  quality_score int, source text, source_hash text,
  created_at timestamptz NOT NULL DEFAULT now(), created_by text NOT NULL,
  PRIMARY KEY (tenant_id, id), UNIQUE (tenant_id, product_id, number),
  FOREIGN KEY (tenant_id, product_id) REFERENCES product (tenant_id, id)
);
CREATE INDEX product_rev_name_trgm ON product_revision USING gin (name gin_trgm_ops);

CREATE TABLE product_image (                   -- immutable files; a new upload = new row
  id uuid NOT NULL DEFAULT uuidv7(), tenant_id uuid NOT NULL, product_id uuid NOT NULL,
  image_set_id uuid NOT NULL,
  face text NOT NULL CHECK (face IN ('front','left','right','top','back','bottom')),
  original_path text NOT NULL, cutout_path text, sha256 char(64) NOT NULL,
  renditions jsonb,                            -- {"2048": path, "512": path, "128": path}
  aspect_ratio numeric(6,4), dominant_color char(7), phash bigint,
  embedding vector(768),                       -- dimension depends on the chosen model
  checks jsonb NOT NULL DEFAULT '{}', status text NOT NULL DEFAULT 'pending',
  PRIMARY KEY (tenant_id, id),
  FOREIGN KEY (tenant_id, product_id) REFERENCES product (tenant_id, id)
);
CREATE INDEX product_image_emb ON product_image USING hnsw (embedding vector_cosine_ops);
```

#### Planning, changes, concurrency and audit

```sql
CREATE TABLE planogram (
  id uuid NOT NULL DEFAULT uuidv7(), tenant_id uuid NOT NULL,
  kind text NOT NULL CHECK (kind IN ('template','store')),
  name text NOT NULL, category_path ltree,
  cluster_id uuid,                             -- templates
  store_id uuid, section_id uuid,              -- store planograms: one per section
  template_id uuid,                            -- store planogram follows this template
  owner_id uuid,
  PRIMARY KEY (tenant_id, id),
  FOREIGN KEY (tenant_id, store_id) REFERENCES store (tenant_id, id),
  FOREIGN KEY (tenant_id, template_id) REFERENCES planogram (tenant_id, id)
);

CREATE TABLE planogram_version (
  id uuid NOT NULL DEFAULT uuidv7(), tenant_id uuid NOT NULL,
  planogram_id uuid NOT NULL, number int NOT NULL,
  status text NOT NULL CHECK (status IN ('draft','in_review','approved','rejected',
                                        'scheduled','active','superseded','retired')),
  parent_version_id uuid, template_version_id uuid,
  layout_revision_id uuid NOT NULL,            -- geometry this version is planned on
  -- frozen manifest (filled on submit, then never changed; ADR-18)
  rule_set_version_id uuid, engine_version text,
  manifest_hash text, frozen_at timestamptz,
  row_version int NOT NULL DEFAULT 1,          -- optimistic concurrency
  score numeric(5,1), hard_breaks int,
  created_by uuid, approved_by uuid, approved_at timestamptz, approved_hash text,
  activation_date date,                        -- planned; real dates come from store_reset
  source text NOT NULL DEFAULT 'planner',      -- planner, autofill, optimiser, ai, bulk, template
  PRIMARY KEY (tenant_id, id), UNIQUE (tenant_id, planogram_id, number),
  FOREIGN KEY (tenant_id, planogram_id) REFERENCES planogram (tenant_id, id),
  FOREIGN KEY (tenant_id, layout_revision_id) REFERENCES layout_revision (tenant_id, id),
  CHECK (status IN ('draft','rejected') OR manifest_hash IS NOT NULL)
);

CREATE TABLE version_product (                 -- product revisions pinned at submit
  tenant_id uuid NOT NULL, version_id uuid NOT NULL, product_id uuid NOT NULL,
  product_revision_id uuid NOT NULL, image_set_id uuid,
  PRIMARY KEY (tenant_id, version_id, product_id),
  FOREIGN KEY (tenant_id, version_id) REFERENCES planogram_version (tenant_id, id),
  FOREIGN KEY (tenant_id, product_revision_id) REFERENCES product_revision (tenant_id, id)
);

CREATE TABLE position (
  id uuid NOT NULL DEFAULT uuidv7(), tenant_id uuid NOT NULL,
  version_id uuid NOT NULL, layout_revision_id uuid NOT NULL,
  surface_id uuid NOT NULL, product_id uuid NOT NULL,
  seq int,                                     -- order on shelves and bars
  grid_col int, grid_row int,                  -- pegs and chests
  x_mm int,                                    -- calculated from seq and widths
  facings_wide smallint NOT NULL DEFAULT 1,
  facings_high smallint NOT NULL DEFAULT 1,
  facings_deep smallint NOT NULL DEFAULT 1,
  orientation text NOT NULL DEFAULT 'front',   -- see the orientation table, section 8
  capacity_units int,                          -- calculated
  placed_by text NOT NULL,          -- planner:<id>, autofill:<ver>, ai:<model>, template
  rule_ids text[], reason text, score numeric(5,1),
  PRIMARY KEY (tenant_id, version_id, id),
  FOREIGN KEY (tenant_id, version_id) REFERENCES planogram_version (tenant_id, id),
  FOREIGN KEY (tenant_id, layout_revision_id, surface_id)
    REFERENCES surface (tenant_id, layout_revision_id, id),
  FOREIGN KEY (tenant_id, product_id) REFERENCES product (tenant_id, id)
) PARTITION BY HASH (version_id);
-- 32 partitions: position_p00 ... position_p31. A trigger checks that the position's
-- layout_revision_id equals its version's layout_revision_id.

CREATE TABLE planogram_override (              -- store changes on top of a template
  id uuid NOT NULL DEFAULT uuidv7(), tenant_id uuid NOT NULL,
  store_planogram_id uuid NOT NULL,
  op text NOT NULL CHECK (op IN ('remove','add','replace','facings','move','surface')),
  target jsonb NOT NULL, params jsonb NOT NULL, reason text,
  created_by uuid, created_at timestamptz DEFAULT now(),
  PRIMARY KEY (tenant_id, id),
  FOREIGN KEY (tenant_id, store_planogram_id) REFERENCES planogram (tenant_id, id)
);

CREATE TABLE lock (                            -- ADR-20
  id uuid NOT NULL DEFAULT uuidv7(), tenant_id uuid NOT NULL, version_id uuid NOT NULL,
  kind text NOT NULL CHECK (kind IN ('assignment','placement')),
  scope text NOT NULL,  -- assignment: section, surface; placement: position, product
  target_id uuid NOT NULL,
  keep text[] NOT NULL DEFAULT '{}',   -- placement: {surface, seq, x, facings}; see section 13
  note text, created_by uuid,
  PRIMARY KEY (tenant_id, id),
  FOREIGN KEY (tenant_id, version_id) REFERENCES planogram_version (tenant_id, id)
);

CREATE TABLE edit_lease (                      -- replaces Redis edit locks (ADR-08)
  tenant_id uuid NOT NULL, version_id uuid NOT NULL,
  holder_id uuid NOT NULL,
  token bigint NOT NULL,                       -- fencing token, grows on every grant
  expires_at timestamptz NOT NULL,
  PRIMARY KEY (tenant_id, version_id),
  FOREIGN KEY (tenant_id, version_id) REFERENCES planogram_version (tenant_id, id)
);
CREATE SEQUENCE lease_token_seq;

CREATE TABLE idempotency_key (
  tenant_id uuid NOT NULL, key text NOT NULL,
  request_hash char(64) NOT NULL,              -- same key + different body = 422
  status_code int, response jsonb,
  created_at timestamptz NOT NULL DEFAULT now(), expires_at timestamptz NOT NULL,
  PRIMARY KEY (tenant_id, key)
);

CREATE TABLE change_set (
  id uuid NOT NULL DEFAULT uuidv7(), tenant_id uuid NOT NULL,
  source text NOT NULL,                        -- planner, bulk, ai, template
  title text, rationale text,
  status text NOT NULL,       -- proposed, validated, approved, applied, rejected, expired
  autonomy_level smallint, confidence numeric(4,3), risk text, expected jsonb,
  model_version text, created_by uuid, decided_by uuid, decided_at timestamptz,
  PRIMARY KEY (tenant_id, id)
);

CREATE TABLE change_set_item (
  id uuid NOT NULL DEFAULT uuidv7(), tenant_id uuid NOT NULL,
  change_set_id uuid NOT NULL, version_id uuid NOT NULL,
  commands jsonb NOT NULL, findings jsonb, result_version_id uuid,
  PRIMARY KEY (tenant_id, id),
  FOREIGN KEY (tenant_id, change_set_id) REFERENCES change_set (tenant_id, id)
);

CREATE TABLE command_log (                     -- append-only audit of every applied command
  id bigint GENERATED ALWAYS AS IDENTITY, tenant_id uuid NOT NULL,
  version_id uuid NOT NULL, command jsonb NOT NULL, inverse jsonb,
  actor text NOT NULL, change_set_id uuid, request_id text,
  at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (at, id)
) PARTITION BY RANGE (at);

CREATE TABLE job (
  id uuid NOT NULL DEFAULT uuidv7(), tenant_id uuid NOT NULL,
  kind text NOT NULL,                          -- import, autofill, export, exposure ...
  status text NOT NULL CHECK (status IN ('queued','running','done','failed','cancelled')),
  payload jsonb NOT NULL, result jsonb, error jsonb,
  attempts int NOT NULL DEFAULT 0, progress numeric(5,2),
  created_by text, created_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz,
  PRIMARY KEY (tenant_id, id)
);

CREATE TABLE outbox (                          -- written in the same transaction as the change
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, tenant_id uuid NOT NULL,
  destination text NOT NULL,                   -- queue or topic name
  message_id uuid NOT NULL UNIQUE,             -- Service Bus MessageId (duplicate detection)
  key text, payload jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  attempts int NOT NULL DEFAULT 0, next_try_at timestamptz NOT NULL DEFAULT now(),
  published_at timestamptz
);
CREATE INDEX outbox_unsent ON outbox (next_try_at) WHERE published_at IS NULL;
```

#### Store execution, sales and exposure

```sql
CREATE TABLE store_reset (                     -- what really happened in the store (ADR-21)
  id uuid NOT NULL DEFAULT uuidv7(), tenant_id uuid NOT NULL,
  store_id uuid NOT NULL, version_id uuid NOT NULL, fixture_code text NOT NULL,
  planned_date date NOT NULL,
  status text NOT NULL CHECK (status IN ('planned','started','done','verified',
                                        'partial','skipped')),
  started_at timestamptz, done_at timestamptz, verified_at timestamptz,
  done_by uuid, verified_by uuid, photo_paths text[], deviations jsonb, note text,
  PRIMARY KEY (tenant_id, id),
  FOREIGN KEY (tenant_id, store_id) REFERENCES store (tenant_id, id),
  FOREIGN KEY (tenant_id, version_id) REFERENCES planogram_version (tenant_id, id)
);

CREATE TABLE sales_daily (                     -- one row per store, SKU and day
  tenant_id uuid NOT NULL, store_id uuid NOT NULL, product_id uuid NOT NULL,
  day date NOT NULL, units numeric(12,3) NOT NULL, revenue numeric(14,2), margin numeric(14,2),
  promo bool, source_file text,
  PRIMARY KEY (tenant_id, store_id, product_id, day)
) PARTITION BY RANGE (day);

CREATE TABLE exposure_daily (                  -- built nightly from resets + positions
  tenant_id uuid NOT NULL, store_id uuid NOT NULL, product_id uuid NOT NULL,
  day date NOT NULL,
  placements int NOT NULL,                     -- number of locations in the store
  facings_total int NOT NULL, linear_mm int NOT NULL, capacity_units int NOT NULL,
  best_shelf_level text,                       -- floor, knee, waist, eye, reach, top
  in_checkout bool NOT NULL, in_end_cap bool NOT NULL, in_promo_display bool NOT NULL,
  version_ids uuid[] NOT NULL,
  exposure_basis text NOT NULL CHECK (exposure_basis IN ('confirmed','scheduled','mixed')),
  PRIMARY KEY (tenant_id, store_id, product_id, day)
) PARTITION BY RANGE (day);
```

### 7.3 Sections, revisions and what is frozen when

**Table 15. Freezing rules**

| Thing | Editable while | Frozen by | After freezing |
|---|---|---|---|
| Layout revision (floor, zones, landmarks, fixtures, bays, surfaces, sections) | Status draft | “Freeze layout” command, or automatically when a planogram on it is submitted | Read-only. Changes start a new draft revision with the same element ids |
| Product revision (sizes, flags, temperature, image set) | Never: each edit or import writes a new revision | Written once | Old revisions stay for every plan that pinned them |
| Product image file | Never: a new upload is a new file and row (sha256) | Written once | Kept while any pinned revision uses it |
| Planogram version | Status draft | Submit: pins layout revision, product revisions (`version_product`), rule-set and engine versions; stores `manifest_hash` | In review → approved (approval signs the hash) → scheduled → active → superseded |

The **manifest hash** is a SHA-256 over a canonical JSON of: layout revision content hash, every pinned product revision id, every position row, locks, rule-set version and engine version. A nightly job rebuilds the store pack and training export of every approved version and checks that the hash and file checksums still match (section 24).

A **section** is the unit of category space: a bay range on one side of one fixture, owned by one category (for example G01 side A, bays 1–6 = Atta). Store planograms are one per section, sections drive the floor heat map, and every placement row in exports carries its section. Sections cannot overlap on a fixture side.

### 7.4 Other tables

**Table 16. Other tables**

| Table | Key columns | Purpose |
|---|---|---|
| store_cluster | id, name, method, features jsonb | Groups of similar stores (by format, size, sales mix) |
| product_identifier | product_id, type (gtin, sku, supplier_code, ean8...), value | All codes that point to a product |
| product_packaging | product_id, level (each, inner, case, tray), qty, sizes, gtin | Case packs and trays for merchandising |
| assortment | store_id or cluster_id, product_id, listed_from, listed_to | Which products are ranged where |
| category | path (ltree), name, department, temperature | Category tree used by sections, rules and reports |
| rule, rule_set, rule_set_version | type, severity, weight, scope, params jsonb | Rules as data, versioned bundles |
| validation_result | version_id, rule_id, target, passed, score, message | Output of the rules engine |
| version_snapshot | version_id, document jsonb (compressed) | Compacted copy of retired versions |
| approval | change_set_id or version_id, step, decision, comment, by, at, signed_hash | Approval trail |
| upload | id, kind, file name, size, sha256, status, blob_path, chunks | Chunked API uploads (section 9.6) |
| import_run, import_row | profile, upload_id, counts, row data jsonb, issues jsonb | Staging for product and feed imports |
| stock_daily | store_id, product_id, day, on_hand, on_order | Rolling window |
| sku_store_stats | store_id, product_id, units_per_day_13w/52w, rank, margin_per_day | Nightly aggregates used by auto-fill |
| realogram, realogram_detection | store_id, fixture_id, photo_path, taken_at; detections | Photos and what the vision model found (V2+) |
| compliance_result | realogram_id, version_id, score, gaps jsonb | Plan vs shelf comparison (V3) |
| issue | store_id, position_id, kind, photo_path, status | Store-reported problems |
| export_job | version_id, formats, file paths, checksums, status | Training and store exports |
| esl_binding (V3) | position_id, label_id, bound_at | Electronic shelf label link |

### 7.5 Multi-tenancy: two walls

**Wall 1, composite keys.** Because every foreign key includes `tenant_id`, the database itself rejects a row that points at another tenant's row, whatever the application code does. **Wall 2, row-level security.** Every query only sees the current tenant's rows.

```sql
-- Row-level security is the second wall; composite keys are the first.
ALTER TABLE product ENABLE ROW LEVEL SECURITY;
ALTER TABLE product FORCE ROW LEVEL SECURITY;      -- applies to the table owner too
CREATE POLICY tenant_isolation ON product
  USING (tenant_id = current_setting('app.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
-- repeated for every tenant-owned table by a migration helper; the app role is
-- not a superuser and has no BYPASSRLS.

-- in the API (SQLAlchemy), per transaction:
--   SET LOCAL app.tenant_id = '<tenant uuid from the token>';
```

The API resolves the tenant from the Entra ID token and sets it once per transaction. Background workers set it from the job message. A pytest suite tries cross-tenant reads and cross-tenant foreign keys on every table and must see zero rows and constraint errors. A very large tenant can later move to its own database without code changes.

### 7.6 Versions, templates and overrides

*Figure 6. Store-specific plans = template version + small store overrides (diagram in the PDF).*

- A **template planogram** belongs to a store cluster. A **store planogram** covers one section, points to a template and holds a short list of **overrides** (remove, add, replace, facings, move, surface changes).
- Submitting a store version **materialises** the effective positions (template positions with overrides applied), runs the rules engine on the result, pins revisions and stores ordinary `position` rows. Execution, exports and ML always read materialised positions.
- When a template gets a new version, a job re-resolves every store that follows it into new drafts. Overrides whose target no longer exists go to a review queue instead of failing silently.
- Approved versions are read-only. Edits start a new draft from the parent. When the layout changes, a draft is **rebased** onto the new layout revision by surface id; positions that no longer fit become findings.

### 7.7 Volumes, partitioning and storage tiers

**Table 17. Volumes and storage tiers**

| Data | Where | Design size | Retention (proposal) |
|---|---|---|---|
| Positions of live and recent versions | PostgreSQL, 32 hash partitions by version | 1,000 stores × 60 planograms × 250 positions × ~10 versions ≈ 150 M | Kept while live + 12 months |
| Layout revisions | PostgreSQL | ~600 fixtures and ~3,000 surfaces per store per revision; a few revisions a year | All frozen revisions kept |
| Product revisions | PostgreSQL | 100k SKUs × a few revisions a year | Kept while any version pins them |
| Retired versions older than 12 months | version_snapshot (JSONB) + Parquet in the lake | One row per version | Kept; rows deleted from position |
| Command log | PostgreSQL, monthly range partitions | Tens of millions per year | 3 years hot (to confirm), then lake |
| Sales and exposure (store × SKU × day) | PostgreSQL rolling 26 weeks + lake (Parquet) | 1,000 stores × 15k ranged SKUs × 365 ≈ 5.5 bn rows a year in the lake | Full history in the lake |
| Images | Media storage behind Front Door | 100k SKUs × up to 3 faces × 4 renditions | While a pinned revision uses them |
| Exports and store packs | Data storage (ADLS Gen2) | Per approved version | Hot 30 days, then cool tier |
| Uploads and error reports | Data storage landing containers | Daily | 90 days |
| Logs and traces | Log Analytics | Traffic-dependent | 90 days |

### 7.8 Domain events

**Table 18. Domain events (Service Bus topics)**

| Event (topic) | Emitted when | Typical subscribers |
|---|---|---|
| product.published / product.revised / product.delisted | Import publishes a product or writes a new revision | Affected-plan finder, AI triggers, search index |
| layout.frozen / section.changed | A layout revision is frozen; sections are added, resized or reassigned | Distance recalculation, affected-plan finder |
| planogram.changed | A command batch commits | Live viewers, stats, AI triggers |
| version.status_changed | Submit, approve, reject, schedule, activate, supersede | Notifications, exports, store tasks |
| reset.completed / reset.verified | A store finishes or verifies a fixture reset | Exposure builder, compliance, metrics |
| changeset.proposed / changeset.applied | AI, bulk or template proposes or applies changes | Approval workflow, metrics |
| sales.loaded | Daily sales feed lands | Exposure join, stats refresh, continuous planning (V3) |
| realogram.processed (V2+) | A shelf photo has been read | Compliance scoring, store tasks |

Events and job messages are written to the `outbox` table in the **same transaction** as the change. The outbox relay runs inside the API (always at least one replica) and publishes with `MessageId = outbox.message_id`, so Service Bus duplicate detection drops a resend after a crash. Consumers are idempotent too (they keep processed ids).


## 8. Geometry and fixture model

Every fixture is described with four levels: **fixture → bay → surface → position**, with six surface kinds. One editor, one set of fit checks and one export format serve every fixture type, from a gondola to a chest freezer.

### 8.1 Surface kinds

| Surface kind | How products are placed | Facings mean | Used by |
|---|---|---|---|
| Shelf | Ordered left to right; x calculated from order, widths and gaps | Units wide × high × deep | Gondolas, wall bays, end caps, multidecks, door coolers |
| Peg | On hooks at hole positions (column, row) | Hooks × items per hook | Pegboards, slatwall, checkout racks |
| Chest | Top-down grid of cells | Units seen from above | Chest and island freezers |
| Bin | Count or volume only | Units or fill % | Dump bins, produce bins, baskets |
| Bar | A row of items on a bar or clip strip | Items on the strip | Clip strips, hanging bars |
| Stack | Whole cases or pallets | Cases (layers × per layer) | Pallet and case displays |

### 8.2 Fixture templates

**Table 19. Template defaults (real sizes set per store)**

| Fixture type | Surface | Typical size (W × H × D, mm) | Notes |
|---|---|---|---|
| Gondola bay (double-sided) | Shelf | 1,000–1,333 × 1,400–2,200 × 400–600 per side | Notch pitch 25 or 50 mm |
| Wall bay | Shelf | 1,000–1,250 × 1,800–2,400 × 300–600 | Perimeter |
| End cap | Shelf or peg | 600–1,250 wide | Promotions |
| Open multideck chiller | Shelf (chilled) | 1,250–3,750 wide × ~2,000 high | Dairy, drinks, ready meals |
| Glass-door cooler or freezer | Shelf per door | Door ~600–800 wide | Door = bay |
| Chest / island freezer | Chest | 1,500–2,500 long × ~850–900 high | Top view |
| Peg wall / slatwall | Peg | Hole pitch 25 or 50 mm | Small hanging goods |
| Checkout rack | Shelf or peg | 400–800 wide | Impulse |
| Dump / produce bin | Bin | Varies | Fresh, promotions |
| Clip strip | Bar | Varies | Cross-merchandising |
| Pallet / case display | Stack | 1,200 × 800 or 1,200 × 1,000 base | Bulk, seasonal |

### 8.3 Orientation and rotated packs

Product sizes are stored once in the GS1 default front (W = width, H = height, D = depth). An orientation says which product side faces the shopper and which side is up; the engine maps the three sizes to the shelf's x (across), y (up) and z (into the shelf). Only orientations the product allows are offered.

**Table 20. Orientation mapping (x, y, z from W, H, D)**

| Orientation | Facing the shopper | x across | y up | z deep | Allowed when |
|---|---|---|---|---|---|
| front (default) | front | W | H | D | always |
| side | left or right side | D | H | W | `can_rotate` |
| top | top (lying flat, front up) | W | D | H | `can_lay_down` |
| front_rot90 | front, turned 90° | H | W | D | `can_lay_down` and not liquid |
| side_lay | side, lying flat | D | W | H | `can_lay_down` and `can_rotate` |
| chest top view | top (seen from above) | W | D (into chest) | H (stack height) | chest surfaces only |

### 8.4 Fit, clearance and load

```python
# x, y, z = oriented sizes (table above). gap g between positions (default 2 mm).
used_width   = sum(x * facings_wide for p in shelf) + g * (n - 1)
fits_width   = used_width <= surface.width_mm + allowed_overhang          # default 0
x_mm[i]      = sum(width of positions before i) + g * i                   # left edge
clear_height = next_surface.height_from_floor_mm - surface.height_from_floor_mm - shelf_thickness
fits_height  = y * facings_high + finger_clearance <= clear_height        # 25 mm default; 0 on pegs
fits_depth   = z * facings_deep <= surface.depth_mm - back_clearance      # 10 mm; doors: 20 mm
door_ok      = not bay.has_door or z * facings_deep <= surface.depth_mm - door_clearance
stack_ok     = facings_high == 1 or (can_stack and facings_high <= max_stack)
units        = facings_wide * facings_high * facings_deep
load_ok      = sum(weight_g * units for p in surface) <= surface.max_load_g   # hard rule
temp_ok      = product.temperature == fixture.temperature                 # hard rule
peg_ok       = item_on_peg and x <= peg_length and hooks do not overlap   # peg surfaces
chest_ok     = units fit the grid cells and stack height <= load line     # chest surfaces
days_supply  = units / max(stats.units_per_day_13w, 0.01)
eye_band     = top (> 1,600) | eye (1,200–1,600) | waist (800–1,200) | knee (400–800) | floor (< 400)
```

Clearances, gaps and eye bands are settings per tenant and per fixture template, not constants in code. The same formulas exist in TypeScript (`packages/geometry-ts`) for instant feedback and in Python (`engines/geometry`) as the authority. A shared folder of golden cases (`packages/contracts/golden/*.json`) is run by both test suites; CI fails if they disagree.

### 8.5 Fixture behaviour

**Table 21. Behaviour by fixture kind (stored in fixture_template.behaviour)**

| Fixture kind | Surfaces | Temperature | Special rules the engine applies |
|---|---|---|---|
| Gondola (double-sided) | shelf, peg | ambient | Sides A/B are independent; bay 1 at the back; heavy items (> 5 kg) only on the two lowest shelves by default |
| End cap | shelf, peg, stack | ambient | Always its own section; promotions or seasonal; short plan validity (dated) |
| Wall bay | shelf, peg | ambient | Taller (2.1 m+); top shelf may be overstock-only (no facings counted) |
| Open multideck | shelf (tilted lower shelves) | chilled | Tilt changes usable depth; night blind clearance at the front; only chilled products |
| Glass-door cooler / freezer | shelf per door | chilled / frozen | Door = bay; door clearance on depth; nothing may cross a door mullion |
| Chest / island freezer | chest grid | frozen | Top view; stack height below the load line; baskets as cells |
| Produce bin / table | bin | ambient / misted | Volume or count only; loose and weighed items allowed without sizes |
| Pallet display | stack | ambient | Whole cases; layers × cases per layer; floor load and aisle clearance checked |
| Checkout rack | shelf, peg | ambient | Small items only (default max 200 mm high); age-restricted items blocked |
| Checkout counter, self-checkout, service desk | none | — | Landmarks for distances and zones; no products |

### 8.6 When a product may be placed

A product can be placed only when all of the following are true. Otherwise the editor shows it greyed out with the reason, and auto-fill skips it with that reason in its report.

**Table 22. Placement eligibility**

| Condition | Why | If missing |
|---|---|---|
| Width, height and depth present **and verified** (`dims_verified`, source measured, supplier, GS1 or SAP) | Wrong sizes make every planogram wrong | Blocked. Estimated sizes can be used for a draft only with a visible warning badge |
| Temperature class matches the fixture | Food safety | Blocked |
| Safety flags reviewed (hazardous, age-restricted, fragile, liquid) | Legal and safety rules depend on them | Blocked until reviewed |
| Ranged for this store (assortment) | Do not plan what the store cannot order | Warning (planner can override with a reason) |
| Front image present | Realistic view, later vision | Allowed: drawn as a **scaled placeholder** (true size, category colour, name). Blocked only where the section's image policy is `required` |

### 8.7 Store-level geometry

- Fixture footprints are PostGIS polygons. Overlap, aisle width (minimum distance between footprints) and blocked-door checks use Shapely in the engine and PostGIS for store-wide queries.
- Each fixture stores walking distance to the entrance and to the checkout, computed on a coarse grid with obstacles (A* on a 250 mm grid). These are key ML features.
- Zones are polygons; a fixture's zone is the zone that contains most of its footprint.


## 9. Product data and image onboarding

This is how the platform gets every product and every pack image from the company, in bulk, and keeps them up to date. Good product data decides whether planograms look real, so onboarding is built in version 1, not later. **The pilot is file-first:** Excel/CSV product files and image ZIPs, uploaded through the web app. Live SAP and DataKart connectors follow in V1.5, once the file path and data quality are proven.

*Figure 7. Onboarding pipeline for product data and images (diagram in the PDF).*

*Figure 8. Onboarding review screen (mockup with invented products) (diagram in the PDF).*

### 9.1 What we ask the company for

**Table 23. Data request to the company**

| Item | Best source | Fallback | Used for |
|---|---|---|---|
| Product master with sizes | Pilot: export to Excel/CSV using our template. V1.5: SAP S/4HANA product API | Measure in store (sample of top sellers) | Product library, fit checks |
| Pack images (front, side, top) | Pilot: ZIP from category teams or suppliers. V1.5: GS1 India DataKart | Photograph packs ourselves (capture guide, section 10.6) | True-size rendering, vision later |
| Case packs and trays | SAP units of measure | Template columns | Facings, replenishment |
| Assortment by store / cluster | ERP listing data | Template | What may be placed where |
| Store list and formats | ERP / store master | Template | Stores and clusters |
| Floor plans | CAD (DXF) or PDF | Photos + site measurement | Floor planner |
| Daily POS sales | POS / BI extract (Parquet or CSV) with the same store and SKU codes | Weekly file | Facings, stats, training data |
| Stock and delivery days | ERP / WMS | Template | Days of supply |

### 9.2 Connectors (V1.5)

#### SAP S/4HANA (product master)

Read products through the standard product OData API (`API_PRODUCT_SRV`, entity `A_Product` with navigation to descriptions and `A_ProductUnitsOfMeasure`). Units of measure carry length, width, height, their dimension unit, weights and the GTIN (EAN) per unit. A delta job runs daily using the last-changed timestamp; a full reload runs weekly. The mapping below is typical and must be confirmed against the client's system.

| SAP field (typical) | Our field | Rule |
|---|---|---|
| A_Product.Product | sku | Trim, keep leading zeros as text |
| A_ProductDescription.ProductDescription (language EN) | name | Fallback to first language |
| A_Product.ProductGroup / hierarchy | category_path | Mapped through a category table |
| A_ProductUnitsOfMeasure (base unit / each) | width_mm, height_mm, depth_mm | Convert dimension unit to mm; axis mapping set in the import profile |
| UnitSpecificProductLength / Width / Height | (as above) | Orientation is not guaranteed to match GS1 default front; profile decides |
| GlobalTradeItemNumber + category | gtin14 | Validate check digit; pad to 14 |
| GrossWeight + WeightUnit | weight_g | Convert to grams |
| Alternative units (case, inner) | product_packaging | Quantity numerator / denominator |

#### GS1 India DataKart

DataKart holds brand-supplied product data and images, including dimensions, for millions of Indian products; API integration needs a DataKart Premium subscription. The connector pulls by GTIN for every ranged product, stores the source and timestamp, and marks DataKart as the preferred source for images and dimensions when SAP has gaps.

#### Files and folders (pilot)

Excel/CSV templates (Appendix C), PIM exports with a saved column profile, and image ZIPs. Each file goes through the upload path below. SFTP, where a sender needs it later, uses Azure Blob Storage SFTP with one local user per sender.

#### Open data for the demo tenant only

For demos before client data arrives, the demo tenant may import a few hundred Indian products with images from **Open Food Facts**. Its database is under the Open Database Licence and its images under CC BY-SA, so the demo shows attribution and keeps any shared derived data under the same terms; its API asks for a custom User-Agent (`AppName/Version (email)`) and has rate limits, so we import once and cache. Open Food Facts data never enters a client tenant, and client product images are never sent outside the client's Azure tenant.

### 9.3 Validation rules

**Table 24. Onboarding validation rules**

| Code | Check | Severity |
|---|---|---|
| P-001 | SKU present and unique within the tenant | Error |
| P-002 | GTIN check digit valid; GTIN-8/12/13 normalised to GTIN-14 | Error |
| P-003 | Width, height and depth present for ranged products, with a size source (measured, supplier, GS1, SAP, estimated) | Error for ranged, warning otherwise |
| P-004 | Sizes within plausible limits for the category (e.g. 5–1,500 mm) and not swapped (outlier vs category median) | Warning |
| P-005 | Weight vs volume gives a plausible density (0.02–3 g/cm³) | Warning |
| P-006 | Temperature class present for chilled/frozen categories | Error |
| P-007 | Case pack ≥ 1 and consistent with packaging levels | Warning |
| P-008 | Possible duplicate (same GTIN, or name + size similarity > 0.9, or image embedding similarity > 0.95) | Warning |
| P-009 | Safety flags answered (hazardous, age-restricted, fragile, liquid); blank is not “no” | Error for ranged products |
| P-010 | Size source is `estimated` for a ranged product | Warning (placement allowed in drafts only, with a badge) |
| I-001 | Front image present | Warning; error only in sections whose image policy is `required` |
| I-002 | Longest side ≥ 1,000 px (recommended 2,000+) | Warning |
| I-003 | Cut-out aspect ratio within 8% of declared width/height | Warning |
| I-004 | Not blurred (variance of Laplacian above threshold); no watermark | Warning |
| I-005 | File name GTIN matches a product | Error (goes to manual match) |

### 9.4 Quality score

```python
quality = 100
        - 40 * missing_required_size        - 15 * missing_front_image
        - 15 * sizes_not_verified           - 10 * size_outlier
        - 10 * image_aspect_mismatch        - 10 * possible_duplicate
        -  5 * missing_side_or_top_image    -  5 * low_resolution
        -  5 * missing_case_pack
quality = clamp(quality, 0, 100)
# The score ranks the fix queue and gates auto-fill (>= 60). Placement itself is
# decided by the eligibility rules in section 8 (verified sizes, temperature, safety).
```

### 9.5 Image pipeline

1. **Upload and scan.** Files come in through the API upload path (below) into a private landing container; Defender for Storage malware scanning runs on arrival.
2. **Match.** Parse GTIN from the file name (GS1 GTIN-based naming or the simple form `<GTIN>_front.png`); unmatched files go to a manual-match screen with a search box.
3. **Cut out and crop.** BiRefNet produces an alpha mask; the image is cropped to the product's tight bounds with a small margin. Already transparent PNGs skip this step.
4. **Check.** Aspect ratio vs declared width/height (front) or depth/height (side); blur; resolution; perceptual-hash duplicates; face type guess.
5. **Make renditions.** 2,048, 512 and 128 px WebP (with alpha), dominant colour (fallback rendering), embedding vector (pgvector) for similar-product search and later vision reference.
6. **Review and publish.** Problems appear in the fix queue; approved images get a new image set and the product a new revision; renditions go to media storage, which Front Door caches for the editors.

### 9.6 Uploads through the API

Storage accounts have no public network access, so the browser cannot upload straight to Blob storage with a SAS link. In the pilot every file goes through the API (ADR-25):

1. `POST /uploads` with file name, size, type and SHA-256 → returns an upload id and chunk size (8 MB).
2. `PUT /uploads/{id}/chunks/{n}` for each chunk; the API streams it to a staged block in the private landing container using its managed identity. Chunks can be retried; the same chunk twice is harmless.
3. `POST /uploads/{id}/complete` → the API commits the block list, checks size and hash, and writes the `upload` row, a job row and an outbox row in one transaction.
4. Front Door allows request bodies up to the chunk size on `/uploads` only; elsewhere bodies stay small. Max file 2 GB (proposal).

If uploads become a bottleneck later, direct-to-Blob upload can be added with a private-link setup or a dedicated upload storage account that allows public access for user-delegation SAS only; that is a later decision, not a pilot need.

> **Gaps in images.** GS1 India also offers an e-cataloguing service and a capture app for brand owners. Our own capture app (V1.5) is a phone web app: scan the barcode, take front/side/top photos against a plain background with an on-screen guide, and upload straight into the pipeline.

### 9.7 Keeping data fresh

- Re-imports (and in V1.5 the daily delta from SAP and DataKart) compare each row's content hash; only real changes write a new product revision.
- A new revision raises `product.revised`. Approved and active versions are not affected, because they pin their revisions. A job finds every **draft** that uses the product, re-runs fit checks on the new sizes and posts breaks to the planner inbox; the planner moves the draft to the new revision when ready.
- A delist raises `product.delisted`; affected planograms get a suggested swap (rule-based in V1, AI-ranked in V2).

### 9.8 Photos of existing shelves (V2+)

For stores that already exist, planners can photograph each fixture. A vision model detects products (matched by image embeddings against the product library) and shelf edges, and proposes a **draft planogram** for review. This realogram-to-planogram approach is well established in patents and products; we build it after the product library and embeddings exist, which version 1 already produces.


## 10. Sample mall store SMS-001

Development starts before client data arrives, so we designed a complete sample store to build, demo and test against. It is an invented store in a mall, sized like a compact Indian hypermarket, with every fixture type the platform must handle: gondolas, end caps, wall bays, multideck chillers, glass-door freezers, island freezers, produce bins, bakery racks, pallets, checkout counters with impulse racks, self-checkouts and a service desk. The seed files (Appendix D) load it in one command; the first two weeks of development build on it.

*Figure 9. Sample Mall Store SMS-001: fixtures coloured by the department of their sections (diagram in the PDF).*

### 10.1 Layout principles used

- **Racetrack (loop) main aisle** around a grid of ambient gondolas, so shoppers pass the perimeter and the ends of every aisle.
- **Fresh at the entrance** (fruit, vegetables, bakery, promotions): it sets the tone and is bought on most trips.
- **Daily needs at the back wall** (milk, curd, chilled drinks, frozen): destination items pull shoppers through the store, past the centre aisles.
- **Heavy staples on the left wall and bulk pallets** near the trolley route; home care on the right wall.
- **Impulse at checkout:** a rack beside every lane, an express lane and self-checkouts near the exit.
- **Aisles 2.2 m** between gondolas and **3.0–3.2 m** main aisles (trolleys pass each other); nothing blocks the entrance, exit or stockroom door.

### 10.2 Store shell and zones

| Item | Value |
|---|---|
| Store | SMS-001 · Sample Mall Store 001 (demo) · ground floor · time zone Asia/Kolkata |
| Floor | 48 × 32 m = 1,536 m²; origin top-left; x to the right, y down; millimetres |
| Entrance / exit | Entrance from the mall at x 2.5–7.5 m on the front wall; exit at x 38–41 m |
| Zones | Entrance & fresh · Checkout & impulse · Chilled & frozen wall · Frozen islands · Main aisle back · Main aisle front · Centre store · Staples wall · Home care wall |
| Landmarks | Trolley bay, two pillars (P1, P2), stockroom door on the back wall |
| Totals | 118 fixtures · 330 shelf bays · about 339 m of bays · 133 sections · 49 categories |

### 10.3 Fixture inventory

**Table 25. Fixtures in SMS-001**

| Fixture codes | Template | Count | Size and use |
|---|---|---|---|
| G01–G10 | GONDOLA_DS_12 | 10 | Double-sided runs, 12 bays × 1 m per side, 1.8 m high, 5 shelves; side A faces west, side B east |
| EC-Gnn-F / EC-Gnn-B | END_CAP | 20 | One at each end of every gondola: front = promotions, back = seasonal |
| WL-01–16 / WR-01–16 | WALL_BAY | 32 | Left wall staples (atta, rice bulk, oils); right wall detergents, plastics, paper |
| MD-01–11 | MULTIDECK_2500 | 11 | Back wall: dairy (5), chilled drinks (4), ready meals (2); 2.5 m each |
| MD-12 | MULTIDECK_2500 | 1 | Entrance: cut fruit, salads, herbs |
| FZ-01–04 | GLASS_DOOR_FREEZER_4 | 4 | 16 doors in total; frozen veg and snacks |
| IF-01–04 | ISLAND_FREEZER_2500 | 4 | Ice cream (2) and frozen snacks (2); chest grid surfaces |
| PB-01–08 · BK-01–03 · PL-01–04 | PRODUCE_BIN · BAKERY_RACK · PALLET | 15 | Fresh zone: produce bins, bakery, entrance promotion pallets |
| SP-01–04 | PALLET | 4 | Bulk rice and atta bags beside the staples wall |
| CO-01–07 · CR-01–07 · SC-01–02 · CS-01 | CHECKOUT_COUNTER · CHECKOUT_RACK · SELF_CHECKOUT · SERVICE_DESK | 17 | Six staffed lanes and one express lane, each with an impulse rack; two self-checkouts; service desk |

### 10.4 Sections: which category owns which space

Each gondola side is split into sections by bay range. Bay 1 is at the back of the store, so the first section on each side is the one shoppers meet from the back main aisle.

**Table 26. Gondola sections (department colours as in the floor plan)**

| Run | Side A (west face) | Side B (east face) |
|---|---|---|
| G01 | Atta & flours (bays 1–6) · Rice (7–12) | Dal & pulses (1–8) · Dry fruits (9–12) |
| G02 | Edible oils & ghee (1–8) · Salt & sugar (9–12) | Masala & spices (1–12) |
| G03 | Breakfast cereals (1–6) · Spreads & honey (7–12) | Tea & coffee (1–8) · Health drinks (9–12) |
| G04 | Biscuits & cookies (1–12) | Snacks & namkeen (1–12) |
| G05 | Chocolates (1–6) · Instant food & noodles (7–12) | Sauces & pickles (1–6) · Ready-to-cook (7–12) |
| G06 | Soft drinks & juices (1–12) | Water & energy drinks (1–6) · Baby care (7–12, assignment-locked) |
| G07 | Oral care (1–6) · Hair care (7–12) | Skin care (1–8) · Deodorants (9–12) |
| G08 | Bath & soaps (1–8) · Feminine hygiene (9–12) | Men's grooming (1–6) · Wellness (7–12, assignment-locked) |
| G09 | Detergents (1–12) | Cleaners & fresheners (1–8) · Pooja needs (9–12) |
| G10 | Kitchen & household (1–8) · Stationery (9–12) | Pet care (1–6) · Paper & tissues (7–12) |

Perimeter and special fixtures are one section each: dairy, cheese and eggs, chilled drinks and ready meals on the multidecks; frozen in freezers and islands; fruit and vegetables in bins; bakery racks; promotions on front end caps and entrance pallets; seasonal on back end caps; checkout impulse on every checkout rack. Food-safety sections (dairy, frozen, ice cream, produce, impulse) are assignment-locked by default.

### 10.5 Sample products

The seed catalogue has 60 invented products across the main categories (for example “Whole Wheat Atta 5 kg (sample)”, “Toned Milk 1 L (sample)”, “Chewing Gum 10-pack (sample)”), with plausible sizes, weights, temperature classes and safety flags. Their GTINs use the **200–299 prefix range**, which GS1 reserves for restricted circulation (in-store and national uses), so they never collide with real trade items; every check digit is valid. Sizes are marked `estimated` and verified only for the demo tenant. Images are scaled placeholders until real photos are added.

### 10.6 Getting real product images and sizes

**Table 27. Sources of real pack images and sizes**

| Route | How | When to use |
|---|---|---|
| Measure and photograph yourself | Buy or borrow packs of the pilot categories. Measure W × H × D to the millimetre (GS1 default front), weigh, and photograph front, side and top on a plain white background, square to the lens, at 2,000 px or more. Name files `<GTIN>_front.jpg`. Record `dims_source = measured`. | Best quality; start now for the top 100–200 SKUs of the pilot categories |
| Client and brand files | Category teams and suppliers send pack shots and spec sheets; we import them through the upload path. | Main route for the pilot |
| GS1 India DataKart | Brand-supplied images and dimensions by GTIN (API needs a Premium subscription). | V1.5, if the client subscribes |
| Open Food Facts | Open product photos and data for many Indian packaged foods; ODbL for data and CC BY-SA for images, attribution required. | Demo tenant only, never in client tenants |
| Capture app | Phone flow: scan barcode, guided photos, upload (section 9). | V1.5, for gaps found in stores |

> **Brand images.** Mockups and demos must not show real brand packs unless the brand owner or client has provided them for this purpose. The sample catalogue uses invented names for that reason.

### 10.7 What the platform records for each product

Once products are placed, the platform can answer, for any day: **where is every product, in which section, how much space does it have and how many units fit**. The example below shows one invented SKU placed in two locations of SMS-001.

**Table 28. Example: one SKU, two locations (invented data)**

| Field | Location 1 | Location 2 |
|---|---|---|
| Product | SKU00014 · Rolled Oats 1 kg (sample) · GTIN 2000000000145 | same |
| Store · zone | SMS-001 · Centre store | SMS-001 · Main aisle (front) |
| Fixture · side · bay | G03 (gondola) · A · bay 2 | EC-G03-F (end cap) · A · bay 1 |
| Section · category | G03-A-01 · Breakfast cereals | EC-G03-F-01 · Promotions |
| Shelf · height · band | Shelf 4 · 1,200 mm · eye | Shelf 2 · 550 mm · knee |
| Order · x | seq 1 · x 0 mm | seq 2 · x 380 mm |
| Facings (wide × high × deep) | 4 × 1 × 4 = 16 units | 3 × 1 × 3 = 9 units |
| Space | 760 mm of shelf (4 × 190 mm) | 570 mm of shelf (3 × 190 mm) |
| Why · who | Auto-fill 2.1: eye level (R-12), 6.6 days of supply · approved by category planner | Planner: December promotion · locked (placement) |
| When | Version 4 approved 1 Dec; reset done and verified 3 Dec | Same version; reset done 3 Dec, not verified |

For that SKU on 4 December the exposure row says: 2 placements, 7 facings, 1,330 mm, 25 units of capacity, best band eye, in an end cap, basis mixed (one location verified, one only done). Section 17 shows how this joins to sales.


## 11. Pages and user interface

This is the full list of pages for version 1, so the build team and the client can agree the scope of the UI before screens are designed in detail. Each page lists its route, what it shows, the main actions and the phase that builds it. Desktop pages target 1440 px wide screens; store pages (prefix `/m`) are phone-first.

### 11.1 Screen pattern

- **App shell:** left navigation (Home, Products, Stores, Planograms, Rules, Approvals, Execution, Reports, Admin), top bar with store and version switcher, search (products by name or GTIN), notifications and the user menu.
- **Editors** (floor, fixture, shelf): canvas in the middle, tool bar on top, a left panel (layers, products or fixture library) and a right **inspector** for the selected item. Status bar shows version, lease holder, save state, score and hard breaks.
- **Lists:** filter bar, saved views, table with status chips, bulk actions, CSV download.
- **Every page handles:** loading (skeletons), empty (with a first action), error (problem details + trace id), no permission, read-only (frozen or approved) and offline (store app keeps the last plan).
- **Status colours** are the same everywhere: draft grey, in review indigo, approved green, scheduled amber, active teal, superseded and retired slate, rejected red.
- **Keyboard:** undo/redo, delete, arrow-key nudges, +/- facings, L to lock, / to search; every canvas action also has a form or list alternative.

### 11.2 Home and administration

| Page | Route | Shows | Main actions | Phase |
|---|---|---|---|---|
| Home | / | My drafts, approvals waiting, import issues, late resets, recent activity | Open item, start new plan | P1 |
| Users and roles | /admin/users | Users, roles, scopes (stores, categories) | Invite, assign role and scope | P0 |
| Settings | /admin/settings | Clearances, gaps, eye bands, default image policy, units display | Edit settings (audited) | P2 |
| Audit log | /admin/audit | Command history by item, user or date | Filter, open before/after | P6 |
| Jobs | /jobs | Imports, auto-fills, exports, exposure builds with progress and errors | Retry, cancel, download log | P1 |

### 11.3 Products and onboarding

| Page | Route | Shows | Main actions | Phase |
|---|---|---|---|---|
| Imports | /onboarding/imports | Import runs with counts (new, changed, errors) | Start import | P2 |
| Import wizard | /onboarding/imports/new | Upload, choose or create a mapping profile, preview 50 rows | Map columns, run validation | P2 |
| Import review | /onboarding/imports/:id | Rows with issues (P-001…P-010), quality score, side-by-side fix | Fix, accept, reject, publish | P2 |
| Image inbox | /onboarding/images | Uploaded images: matched, unmatched, cut-out preview, checks | Match to GTIN, approve, redo cut-out | P2 |
| Product library | /products | Search and filters; eligibility badge (sizes, safety, temperature, image) | Open, bulk-fix, export list | P1 |
| Product detail | /products/:id | Revisions with size source, images per face, packaging, where used (store, section, version) | New revision, add image | P2 |
| Categories | /categories | Category tree, temperature, default image policy | Add, move, rename | P1 |

### 11.4 Stores, floors and fixtures

| Page | Route | Shows | Main actions | Phase |
|---|---|---|---|---|
| Stores | /stores | Stores and clusters with format, size, active plans | Create store, assign cluster | P1 |
| Store overview | /stores/:id | Floor thumbnail, sections by department, active versions, reset status, space KPIs | Open floor, open section | P1 |
| Floor planner | /stores/:id/floor | Draft layout revision: walls, zones, landmarks, fixtures, section colours, checks | Draw, place, rotate, align, freeze | P3 |
| Layout revisions | /stores/:id/layout/revisions | Revision list with hash, author, date; visual diff of two revisions | Freeze, start draft, compare | P3 |
| Fixture library | /fixtures/templates | Templates by kind with preview and behaviour | New template, duplicate | P4 |
| Template editor | /fixtures/templates/:id | Bays, surfaces, notches, depth, tilt, peg grid, doors, load, temperature | Edit, save new version | P4 |
| Fixture and sections | /stores/:id/fixtures/:code | Elevation of both sides with sections overlaid; bay and surface inspector | Create, resize, split, merge sections; set image policy; assignment lock | P4 |

### 11.5 Planning

| Page | Route | Shows | Main actions | Phase |
|---|---|---|---|---|
| Planograms | /planograms | Plans by store, section, category and status | New draft, open, bulk actions (V1.5) | P1 |
| Shelf planner | /versions/:id/edit | True-size shelf view, product panel (eligible first), facings, orientation, locks, live fit, score | Drag, facings, lock, auto-fill, validate, submit | P5 |
| Templates and overrides | /templates/:id | Cluster template with the stores that follow it and their overrides | Edit template, resolve stores | P5 |
| Rules | /rules | Rule sets and versions; rule editor from JSON schema; test on a version | Add rule, set severity and weight, publish rule set | P6 |
| Validation report | /versions/:id/validation | Hard breaks and soft findings grouped by rule and shelf; score | Jump to item, fix | P6 |
| Change-set review | /versions/:id/changesets/:cs | Auto-fill or bulk result: before/after, reasons, findings | Accept all, accept some, reject | P6 |

### 11.6 Review, activation and stores

| Page | Route | Shows | Main actions | Phase |
|---|---|---|---|---|
| Approvals | /approvals | Versions waiting for me, age, score, hard breaks | Open review | P1 |
| Version review and compare | /versions/:a/compare/:b | Side-by-side or overlay diff; added, removed, moved, re-faced; manifest | Approve, reject with comment | P1 |
| Scheduling | /schedule | Approved versions by store and section with activation dates | Set dates, create reset tasks, print packs | P1 |
| Execution dashboard | /execution | Resets planned, started, done, verified; late and partial; exposure basis | Remind store, open photos | P7 |
| Store app: today | /m/store | Today's resets and open issues for my store | Start reset | P1 |
| Store app: fixture and reset | /m/store/fixtures/:code | Fixture plan by bay, change list, check boxes | Start, done, photo, verify, report partial | P1 |
| Store app: find product | /m/store/find | Barcode scan → every location of the SKU in the store | Scan, open location | P7 |
| Store app: report issue | /m/store/issues/new | Pick position, reason, photo | Send | P7 |

### 11.7 Reports and data

| Page | Route | Shows | Main actions | Phase |
|---|---|---|---|---|
| Where is each SKU | /reports/where | Every placement of every SKU: store, zone, fixture, side, bay, shelf, section, facings, capacity, version, since when | Filter, download CSV/XLSX | P1 |
| Space by section | /reports/space | Linear metres, facings and share of space by section, category and brand vs share of sales | Filter, download | P6 |
| Exports | /exports | Training exports per version, daily exposure, store packs; checksums | Run, download, rebuild check | P1 |

> **Phases.** Phase P1 builds only a thin version of the pages marked P1 (enough for the walking skeleton); later phases complete them.


## 12. Planogram editor design

*Figure 10. Shelf planner (mockup with invented products) (diagram in the PDF).*

*Figure 11. Floor planner (mockup) (diagram in the PDF).*

### 12.1 Command model

The editor never sends raw rows. It sends **commands**. Each command is a small JSON object with a type, a target and parameters. The server applies commands in order inside one transaction, runs the checks and returns the new state. The same commands are produced by bulk jobs, template resolution and the AI service.

**Table 29. Command catalogue (version 1)**

| Command | Parameters | Notes |
|---|---|---|
| PlaceFixture / MoveFixture / RotateFixture / RemoveFixture | template_id or fixture_id, x_mm, y_mm, rotation_deg | Layout commands; checked for overlap and aisle width |
| UpdateBay / UpdateSurface / AddSurface / RemoveSurface | ids, sizes, height_from_floor_mm, grid | Shelf heights snap to notch pitch |
| DrawZone / UpdateZone | polygon, kind, priority | Recomputes fixture zones |
| CreateSection / ResizeSection / SplitSection / MergeSection | fixture_id, side, bay_from, bay_to, category_path, image_policy | No overlaps on a fixture side; assignment-locked sections cannot be resized |
| FreezeLayout | layout_revision_id | Computes the content hash; the revision becomes read-only |
| RebaseDraft | version_id, new layout_revision_id | Maps positions by surface id; what no longer fits becomes findings |
| AddPosition | surface_id, product_id, seq or grid cell, facings, orientation | Fit checks; reason optional |
| MovePosition | position_id, surface_id, seq or grid cell | Within or across surfaces |
| SetFacings | position_id, wide, high, deep | Days of supply recalculated |
| ReplaceProduct / SwapProducts | position_id(s), product_id | Used by delist swaps |
| RemovePosition | position_id |  |
| ReorderSurface | surface_id, ordered position ids | Blocking and price flow |
| Lock / Unlock | kind (assignment or placement), scope, target_id, keep, note | Locks are checked before every other command (section 13.3) |
| UseProductRevision | product_id, product_revision_id | Moves a draft to a newer product revision; fit re-checked |
| AddOverride / RemoveOverride | store planogram, op, target, params | Store changes on top of a template |

```http
PATCH /api/v1/versions/0193c2.../positions
If-Match: "12"
Lease-Token: 48213
Idempotency-Key: 7f1c...
{
  "commands": [
    {"type": "SetFacings", "position_id": "0193c3...", "wide": 4, "high": 1, "deep": 4},
    {"type": "AddPosition", "surface_id": "0193b8...", "product_id": "0193a1...",
     "seq": 5, "facings": {"wide": 2, "high": 1, "deep": 4}, "reason": "new launch"}
  ],
  "client": {"session": "s-81", "batch": 42}
}
-> 200 OK   ETag: "13"
{
  "row_version": 13,
  "applied": 2,
  "positions": [ ...changed positions with calculated x_mm... ],
  "findings": [{"rule_id": "R-20", "severity": "soft", "target": "0193c3...", "message": "Ostra muesli should sit beside oats"}],
  "score": 86.0, "hard_breaks": 0
}
```

### 12.2 Client architecture

- **State:** a normalised `PlanogramDoc` in Zustand (fixtures, bays, surfaces, positions by id). Commands are applied locally by a TypeScript reducer for instant feedback, then batched to the server every second or on idle.
- **Undo/redo:** each local command stores its inverse; undo sends the inverse as a new command (history stays linear and auditable).
- **Conflicts:** on `409 Conflict`, the client reloads the version and re-applies unsent local commands if they still validate; otherwise it shows what changed.
- **Rendering:** Konva layers — cached static layer (floor, fixtures outline, shelf edges), product layer, interaction layer (selection, guides). Only visible items are drawn; product images switch between 128, 512 and 2,048 px by zoom.
- **Heavy work** (fill bars, days of supply for 2,000 facings) runs in a Web Worker.
- **Server data** via TanStack Query; types generated from OpenAPI; Zod validates responses at the boundary.
- **Accessibility:** canvas actions have keyboard shortcuts and a list view alternative for screen-reader users.

### 12.3 Edit leases

- Before editing a section's draft, the editor takes an **edit lease**: `POST /versions/{id}/lease`. The API inserts or takes over the `edit_lease` row if it is free or expired, and returns a **fencing token** from a sequence (it only ever grows) and an expiry of 120 s. The editor renews every 30 s.
- Every command batch carries the token (`Lease-Token`). The save transaction checks, while holding the version row lock, that the lease row still has **this token** and has not expired. A planner whose lease was taken over can never write, even if their request arrives late.
- Different planners can hold leases on different sections (different store planograms) of the same store at the same time.
- Viewers get `version.changed` events (relayed through Redis pub/sub) and refresh.
- **Later:** if planners need simultaneous editing of the same section, the `PlanogramDoc` maps cleanly to a Yjs document; commands become the server-side validation step for CRDT updates.

### 12.4 One atomic save

Everything a save changes is written in **one PostgreSQL transaction**: either all of it is stored or none of it is. There is no second write to Redis, Blob storage or Service Bus inside the request.

```sql
BEGIN;
SET LOCAL app.tenant_id = :tenant;
-- 1. idempotency: same key seen before?  same body -> return stored response; other body -> 422
INSERT INTO idempotency_key (tenant_id, key, request_hash, expires_at)
     VALUES (:t, :key, :hash, now() + interval '24 hours')
ON CONFLICT DO NOTHING RETURNING key;                    -- no row returned = replay
-- 2. version row lock + optimistic check + lease check
SELECT row_version, status FROM planogram_version WHERE tenant_id = :t AND id = :v FOR UPDATE;
  -- status must be 'draft'; row_version must equal If-Match, else 409
SELECT token, expires_at FROM edit_lease WHERE tenant_id = :t AND version_id = :v;
  -- token must equal Lease-Token and expires_at > now(), else 423 Locked
-- 3. apply commands in memory (pure engines), run fit + hard rules; any hard break -> ROLLBACK, 422
-- 4. write the result
INSERT/UPDATE/DELETE position ...;                       -- only changed rows
INSERT INTO command_log (...) VALUES (...);              -- one row per command, with inverse
UPDATE planogram_version SET row_version = row_version + 1, score = :s, hard_breaks = 0
 WHERE tenant_id = :t AND id = :v AND row_version = :expected;   -- 0 rows -> ROLLBACK, 409
INSERT INTO outbox (tenant_id, destination, message_id, payload)
     VALUES (:t, 'planogram.changed', uuidv7(), :event);
UPDATE idempotency_key SET status_code = 200, response = :resp WHERE tenant_id = :t AND key = :key;
COMMIT;
```

### 12.5 Retries and the outbox relay

- **Client retries** reuse the same `Idempotency-Key`; a replay returns the stored response without running anything twice. Keys live 24 hours.
- **Jobs** (import, auto-fill, export) are created the same way: the job row, its outbox message and the idempotency key are one transaction. The job id is the Service Bus `MessageId`.
- **Relay:** a loop inside every API replica; one replica at a time wins a PostgreSQL advisory lock and publishes. It claims rows with `FOR UPDATE SKIP LOCKED`, sends, then marks `published_at`. Because the API always runs at least one replica, the relay runs even when every worker has scaled to zero, which is what lets KEDA start workers in the first place.
- **Safety net:** a pg_cron job every minute raises an alert (and a metric) if any unsent row is older than 60 s; a Container Apps cron job can run the relay too if the API is unhealthy.
- **Workers** start a job with `UPDATE job SET status = 'running' WHERE id = :id AND status = 'queued'`; zero rows means another delivery already took it, so a duplicate message is dropped. Results, job status and follow-up events are again one transaction.


## 13. Rules engine

Rules are JSON documents grouped in versioned **rule sets**. The engine is deterministic Python: the same plan and the same rule set always give the same findings. Hard rules block approval; soft rules give a weighted score.

### 13.1 Rule document

```json
{
  "id": "R-12",
  "name": "Priority brands at eye level",
  "type": "eye_level",
  "severity": "soft",                       // hard = blocks approval; soft = affects score
  "weight": 3,
  "scope": {"category": "Food.Breakfast", "zones": ["main_aisle", "checkout"], "clusters": ["*"]},
  "params": {"brands": ["Sunmill", "Kirra"], "band_mm": [1200, 1600], "min_share": 0.6},
  "effective": {"from": "2026-12-01", "to": null},
  "explain": "Priority brands should take at least 60% of the eye-level band."
}
```

### 13.2 Rule types

**Table 30. Rule types in version 1**

| Type | Checks | Default severity | Parameters |
|---|---|---|---|
| fit | Width, height, depth fit the surface | Hard | finger_gap_mm, max_overhang_mm |
| temperature | Product temperature matches fixture | Hard | — |
| eligibility | Verified sizes, safety flags reviewed, image policy met | Hard | image_policy from the section |
| section_category | Products belong to the section's category (or an allowed list) | Hard or soft | allow_categories, max_foreign_share |
| lock | Assignment and placement locks respected (section 13.3) | Hard | — |
| load | Surface weight under limit | Hard | max_load_g |
| restricted_zone | Restricted products only in allowed zones | Hard | categories, zones |
| assortment | Only ranged products for this store | Hard | — |
| min_facings / days_of_supply | Enough stock on shelf between refills | Hard or soft | min_facings, target_days |
| adjacency | Groups next to / away from each other | Soft | group_a, group_b, mode |
| blocking | Brand or sub-category kept in one block | Soft | group_by, direction (vertical/horizontal) |
| eye_level | Chosen products in a height band | Soft | brands or products, band_mm, min_share |
| heavy_low | Heavy or tall products on lower shelves | Soft | weight_g, max_height_mm |
| zone_affinity | Categories in suitable zones | Soft | category, zones |
| price_flow | Price rises in reading direction within a block | Soft | direction |
| share_of_shelf | Space share close to sales share | Soft | group_by, tolerance |
| sequence_template | Order follows the category sequence (e.g. size small → large) | Soft | attribute, order |
| custom_expression | Planner-written condition over product and surface fields | Either | expression (safe expression language, decided in phase 5) |

### 13.3 Locks

Version 2.0 had one kind of lock. That mixed up two different promises, so version 2.1 has two kinds (ADR-20).

**Table 31. Two kinds of lock**

| Kind | Promise | Scopes | What engines may still do |
|---|---|---|---|
| Assignment lock | This space belongs to this category | section, surface | Change products, order and facings inside the space; never resize, move or reassign the section |
| Placement lock | This product keeps its place | position, product | Nothing to the locked fields. `keep` says which: surface, seq (order), x (exact left edge), facings |

**Locked positions are anchors.** On a shelf, a placement lock with `keep = {surface, x}` fixes its left edge. The shelf is split into free segments between anchors, and every other edit must fit inside a segment. Example: B is locked at x = 600 mm and A sits to its left. Raising A's facings from 3 to 4 needs 90 mm more. If the free segment left of B has 90 mm spare, A grows and B does not move. If not, the command **fails** with a finding (“needs 90 mm, segment has 40 mm; B is locked at 600 mm”) and auto-fill tries the next option. Nothing ever pushes a locked item. A lock with `keep = {surface, seq}` keeps order but lets x shift; the editor shows which kind each lock is.

### 13.4 Plugin interface

```python
class RuleType(Protocol):
    type: ClassVar[str]
    Params: ClassVar[type[BaseModel]]          # Pydantic model, also exported as JSON schema for the rule editor

    def evaluate(self, ctx: PlanContext, rule: Rule) -> list[Finding]: ...
    def repair_hints(self, ctx: PlanContext, rule: Rule) -> list[Hint]: ...   # used by auto-fill and the optimiser

@dataclass(frozen=True)
class Finding:
    rule_id: str; severity: Literal["hard", "soft"]; target: str
    passed: bool; score: float                   # 0..1 for soft rules
    message: str; data: dict                     # e.g. {"share": 0.42, "required": 0.6}
```

### 13.5 Scoring

Plan score = 100 × Σ(weightᵢ × scoreᵢ) ÷ Σ weightᵢ over soft findings in scope. Hard findings are pass/fail. Every position keeps the ids of rules that influenced it and a one-line reason, for example: *“Eye level (R-12, priority brand); 4 facings give 6.6 days of supply; next to Kirra (R-20).”*


## 14. Auto-fill and optimisation

### 14.1 Version 1: heuristic auto-fill

1. **Load** the section's surfaces, anchors (placement-locked positions), eligible ranged products of the section's category with quality ≥ 60, rules in scope, and `sku_store_stats`. All inputs come from pinned revisions, so the job is repeatable.
2. **Facings:** facings = ceil(units per day × target days ÷ units per facing), units per facing = deep × high; clamp to min/max.
3. **Assign shelves:** fill the free segments between anchors; hard rules first (fit, temperature, eligibility, restricted zones, assortment), then soft preferences (eye level, heavy low, blocking).
4. **Order:** blocks, then sequence template, price flow and adjacency.
5. **Trim:** if a shelf overflows, the lowest-ranked products lose facings first; products that still do not fit are listed as unplaced, never forced.
6. **Score and explain:** run soft rules, compute the score, write a reason per position. The result is a change set on the draft; the planner accepts or rejects it.

### 14.2 Version 2: CP-SAT optimiser

The optimiser improves facings and shelf assignment using demand and space elasticity, while keeping every hard rule. It runs in two stages so each solve stays small and fast.

```
Stage 1 - assignment and facings (CP-SAT)
  variables   x[p,s] ∈ {0,1}       product p is on surface s
              f[p,s] ∈ {0..Fmax}    facings of p on s   (f ≤ Fmax · x)
  constraints Σ_s x[p,s] ≤ 1                         each product at most once (= 1 if must-stock)
              Σ_p w[p] · f[p,s] ≤ W[s]                width capacity
              h[p] · high[p] ≤ H[s] for x[p,s] = 1    height fit (pre-filtered: x[p,s] fixed to 0 if it cannot fit)
              temperature, restricted zones, assortment -> x fixed to 0
              locked positions -> x, f fixed
              f[p,s] ≥ ceil(demand[p] · target_days / units_per_facing[p]) · x[p,s]   (if days-of-supply is hard)
  objective   maximise Σ value[p] · g_p(f[p,s])         g = piecewise-linear space-elasticity curve
              + Σ soft-rule rewards (eye level, zone affinity, heavy low)
              - λ · Σ |f - f_current| - μ · Σ moved products          (keep changes small)
  limits      time limit 10–60 s, 8 workers, warm start from the current plan

Stage 2 - order on each surface (heuristic, CP-SAT later)
  blocks by brand/sub-category, then sequence template, price flow and adjacency
```

### 14.3 Space elasticity and demand

- **Demand:** LightGBM model per category on daily sales with seasonality, promotions and store features; fallback to 13-week average.
- **Space elasticity:** log(units) = α + β·log(facings) + controls, estimated per category and store cluster from daily exposure joined to sales at store × SKU × day (section 17). β is shrunk toward the category mean when data is thin. Published studies usually find small positive values.
- **New items:** borrow demand and elasticity from the nearest similar products by image and text embeddings.
- **Validation:** every optimiser result passes the rules engine before it is saved, and the planner sees the before/after diff.


## 15. AI architecture and auto-apply

AI in this platform has one job: propose better plans faster, and apply them only when it is safe. It never writes positions directly. Every AI output becomes a **change set** of ordinary commands that passes the same repair, validation, policy and approval steps as any other change.

*Figure 12. From trigger to measured result: how an AI suggestion becomes a plan (diagram in the PDF).*

*Figure 13. Change-set review screen (mockup with invented products) (diagram in the PDF).*

### 15.1 Autonomy levels

**Table 32. Autonomy levels**

| Level | Name | What happens | Who decides | Version |
|---|---|---|---|---|
| L0 | Manual | Planner places everything; rules check it | Planner | V1 |
| L1 | Assist | Suggestions per product (best shelf, facings, swap for a delist); one click to apply | Planner per suggestion | V2 |
| L2 | Review | AI drafts a whole change set for a planogram or many planograms; planner/approver reviews the diff | Planner + approver | V2 |
| L3 | Policy auto-apply | Low-risk change types are applied automatically inside guardrails; planners are notified and can undo before the reset date | Policy (set by admin) | V3 |
| L4 | Continuous | Events trigger re-planning; changes are rolled out to test stores first, compared with control stores, and rolled back automatically if KPIs fall | Policy + experiment results | V3+ |

### 15.2 Change types and risk

**Table 33. Change types, risk and default autonomy ceiling**

| Change type | Example | Risk | Highest level allowed (default) |
|---|---|---|---|
| Delist removal | Remove a delisted product | Low | L3 |
| Like-for-like swap | Replace delisted item with same size and price band | Low | L3 |
| Facings ±1 | Raise or lower facings by one within days-of-supply limits | Low | L3 |
| New item insertion | Add a new launch, shifting neighbours | Medium | L2 |
| Move within block | Move a product to another shelf in its block | Medium | L2 |
| Block re-layout | Re-order a brand block or category sequence | High | L2 |
| Surface change | Change shelf heights or count | High | L2 |
| Fixture or floor change | Move fixtures, change zones | High | L1 (never automatic) |

### 15.3 Policy engine

```json
{
  "policy_id": "default-2027-01",
  "scopes": [{"category": "Food.Breakfast", "clusters": ["urban_large"], "max_level": 3}],
  "change_types": {
    "delist_removal":     {"max_level": 3},
    "like_for_like_swap": {"max_level": 3, "min_confidence": 0.85},
    "facings_step":       {"max_level": 3, "min_confidence": 0.80, "max_step": 1},
    "new_item_insert":    {"max_level": 2},
    "fixture_change":     {"max_level": 1}
  },
  "guardrails": {
    "hard_rules_pass": true, "locks_untouched": true,
    "max_facings_changed_pct": 15, "min_expected_uplift_pct": 0.5,
    "publish_delay_hours": 48, "max_auto_changes_per_store_per_week": 30
  },
  "experiments": {"require_control_stores": true, "rollback_if_units_drop_pct": 3, "window_days": 14}
}
```

Decision for each change set: if every item's change type allows the requested level for this scope, all hard rules pass, no lock is touched, confidence and expected uplift are above their thresholds and the change size is within the cap, the change set is **auto-approved by the policy principal** and scheduled with a publish delay. Otherwise it goes to the review queue at the highest level allowed. Every decision stores the policy id and the values it checked.

### 15.4 Models

**Table 34. Planned models**

| Model | Version | Input | Output | Method |
|---|---|---|---|---|
| Demand forecast | V2 | Daily sales, calendar, promotions, store features | Units per day per store-SKU | LightGBM, global model per category |
| Space elasticity | V2 | Daily exposure joined to sales (store × SKU × day) | β per category × cluster | Log-log regression with shrinkage |
| Placement scorer | V2 | Placement features (section, zone, shelf level, neighbours, distances) with exposure-weighted sales | Expected sales per facing for each candidate slot | LightGBM ranker (LambdaRank) |
| New-item similarity | V2 | Image and text embeddings | Nearest existing products | pgvector nearest neighbours |
| Store clustering | V2 | Sales mix, format, size, location features | Cluster per store | k-means / hierarchical, reviewed by planners |
| Shelf detection (realogram) | V2+ | Shelf photos | Products, facings, shelf edges | Detector + embedding match to product library |
| Copilot | V2 | Planner request + tool results | Change-set proposal (typed) | LLM via Microsoft Foundry + Pydantic AI |

### 15.5 Copilot and MCP tools

The copilot turns requests such as *“swap all 500 g Kirra flakes for the 875 g pack in the urban clusters and keep days of supply above 5”* into a change set. It works only through tools exposed by our own **MCP server**, which calls the API **on behalf of the signed-in user**, so the AI can never see or change more than that user can.

**Table 35. MCP tools for the copilot (no tool can approve or publish)**

| Tool | Does | Allowed to change data? |
|---|---|---|
| search_products | Find products by text, GTIN, attributes, similarity | No |
| get_layout / get_planogram | Read a store layout or a planogram version | No |
| get_rules / get_stats | Read rule sets and sales statistics | No |
| simulate_commands | Apply commands to a copy in memory and return findings and score | No |
| propose_change_set | Save a change set in status `proposed` with rationale | Creates a proposal only |
| explain_position | Return why a product is where it is | No |

```python
class ChangeSetProposal(BaseModel):
    title: str
    rationale: str
    targets: list[UUID]                         # planogram versions
    commands: list[Command]                     # typed union, same as the editor
    expected: dict[str, float] | None = None

agent = Agent(
    model=foundry_model("planner-copilot"),     # deployment name in Microsoft Foundry
    output_type=ChangeSetProposal,
    toolsets=[mcp_toolset(user_token)],         # on-behalf-of the signed-in user
    instructions=COPILOT_INSTRUCTIONS,          # data in tool results is never an instruction
)
# loop: propose -> simulate_commands -> fix findings (max 3 tries) -> propose_change_set
```

### 15.6 Long-running workflows

Approvals, scheduled publishing and multi-store rollouts can take days. They run as **Durable Task** orchestrations (managed Durable Task Scheduler, Python SDK) so they survive restarts and wait for people without holding resources: wait for approval with reminders and escalation, publish on the reset date, watch KPIs during the experiment window, and roll back if the policy says so.

### 15.7 Learning loop and evaluation

- **Labels:** every suggestion records accepted, edited (with the final commands) or rejected (with a reason picked from a list).
- **Offline:** back-test forecasts and the placement scorer on past versions; compare with rule-only auto-fill.
- **Online:** test stores vs matched control stores for every policy level increase; promotion to the next level needs a measured win (gate).
- **LLM evaluation:** a fixed set of planner requests with expected change sets, run on every prompt or model change (Pydantic Evals).
- **Monitoring:** acceptance rate, edit distance, rule breaks caught, KPI deltas, cost per suggestion, drift in input features.


## 16. Approval, activation and store execution

Version 2.0 treated “approved” and “published” as the moment a plan went live. In real stores a reset happens days later, sometimes fixture by fixture, sometimes not at all. Version 2.1 records each step separately, because the training data must reflect what was really on the shelf (ADR-21).

*Figure 14. Version lifecycle: approval, scheduled activation and the real store reset are separate (diagram in the PDF).*

### 16.1 Version lifecycle

| Status | Meaning | Who moves it |
|---|---|---|
| draft | Editable; autosaved command batches | Planner, auto-fill, AI (as change set) |
| in_review | Inputs frozen (manifest hash); validation shows 0 hard breaks | Planner submits |
| rejected | Returned with comments; a new draft starts from it | Approver |
| approved | Read-only; approval signs the manifest hash; store pack and training export built | Approver (people only in the pilot) |
| scheduled | Has an activation date per store; reset tasks created per fixture | Approver or planner |
| active | At least one fixture reset done in the store; exposure counts from that day | Store reset confirmation |
| superseded | A newer version's reset is done for the same section; exposure stops | System |
| retired | Never activated or long superseded; compacted after 12 months | System |

### 16.2 Submit, freeze and approve

1. **Submit:** the layout revision must be frozen (it is frozen now if it is still a draft). The API pins every product's current revision in `version_product`, records the rule-set and engine versions, materialises template + overrides, validates, and stores the `manifest_hash`. From here the inputs cannot change.
2. **Review:** the approver sees the diff against the active version, findings, score and the changes list for the store.
3. **Approve:** stores `approved_hash = manifest_hash`. If anything were different, approval fails. Exports and the store pack are built from the pinned inputs only, so they can be rebuilt identically at any time.
4. **Change after approval:** not possible. A correction is a new draft from the approved version.

### 16.3 Activation and store resets

- **Scheduling** sets an activation date per store and creates one `store_reset` row per fixture touched by the change (status planned).
- **In the store** the team opens the fixture in the store app, taps *Start*, works from the change list, taps *Done*, and takes a photo. A supervisor (or, in V3, the vision model) marks it *Verified*. Partial resets record what could not be done (for example, product not delivered).
- **Late or missing confirmations:** if a planned reset has no confirmation two days after its date, the store gets a reminder and the planner sees it on the execution dashboard. Exposure for those days is flagged `scheduled` (not confirmed) so models can weight or drop it.
- **Active and superseded** follow from resets, not from approval: a version becomes active in a store on its first completed reset, and the previous version for that section is superseded on the same day.

### 16.4 Store execution tools

- **Store pack:** one PDF page per fixture with images, facings and shelf heights (rendered server-side with Playwright), plus a change list (what to add, move, remove), built from the pinned inputs.
- **Store app:** phone-friendly view per fixture and bay; scan a barcode to find a product's place; start, finish and verify resets.
- **Issue reports:** pick a position, choose a reason (gap, wrong place, damaged label, product missing), add a photo.
- **Compliance (V3):** shelf photos are read by the vision model; differences against the active version become scored tasks.
- **Shelf labels (V3):** positions have stable ids, so ESL systems can bind labels to positions and update them on activation.


## 17. Data for machine learning

Everything the platform records is aimed at one goal: later models must be able to learn **how placement affects sales**, using only data that is true. That needs three things: the exact plan that was approved, the days it was really on the shelf, and sales at a grain that cannot be double counted.

### 17.1 What is recorded, and when

**Table 36. Data captured along the way**

| Moment | Recorded in | Content |
|---|---|---|
| Product imported or fixed | product_revision, product_image | Sizes with source and verification, flags, temperature, image set |
| Layout frozen | layout_revision (+ fixtures, bays, surfaces, sections) | Physical store at that time, with content hash |
| Every edit | command_log | Command, inverse, actor, change set, time |
| Submit | planogram_version, version_product, position | Pinned revisions, rule set, engine version, manifest hash; materialised positions with reasons |
| Approve | planogram_version, approval | Approver, time, signed hash |
| Reset in store | store_reset | Per fixture: planned, started, done, verified, photos, deviations |
| Nightly | exposure_daily | Per store × SKU × day, built from active versions and resets |
| Sales feed lands | sales_daily | Per store × SKU × day: units, revenue, margin, promotion flag |

### 17.2 Three grains, never mixed

| Table | One row per | Use |
|---|---|---|
| placements (from position) | Version × location of a SKU | Where, what, why: features of each location |
| exposure_daily | Store × SKU × day | What was on the shelf that day: number of locations, facings, space, capacity, best band, end cap or checkout, basis |
| sales_daily | Store × SKU × day | What sold that day |

**Worked example.** SKU00014 sits in two places (gondola G03 and end cap EC-G03-F) for one week and sells 100 units. The export contains **2 placement rows**, **7 exposure rows** (one per day) and **7 sales rows** adding up to **100 units**. Joining exposure to sales on store, SKU and day gives 7 rows and 100 units. Joining sales to placements, as version 2.0's export suggested, would give 14 rows and 200 units, which is why sales never appear on placement rows (ADR-22). Models that need per-location detail use the placement rows as features of the day (for example share of capacity on the end cap), not as separate sales.

### 17.3 How daily exposure is built

```python
for each store, day:
    for each section in the store's layout:
        reset   = latest store_reset for the section's fixture with done_at::date <= day   # confirmed
        planned = latest scheduled version with activation_date <= day                     # fallback
        version = reset.version if reset else planned
        basis   = 'confirmed' if reset else 'scheduled'
        collect positions of version on that section's surfaces
    group positions by product:
        placements      = count(positions)
        facings_total   = sum(facings_wide * facings_high)
        linear_mm       = sum(facings_wide * oriented width)
        capacity_units  = sum(facings_wide * facings_high * facings_deep)
        best_shelf_level, in_end_cap, in_checkout, in_promo_display
        version_ids     = distinct versions;  exposure_basis = confirmed | scheduled | mixed
    upsert exposure_daily (tenant, store, product, day)
```

The builder is a pure engine (`engines/exposure`), runs nightly per store and can rebuild any date range. Days on which a reset was only partial carry the deviation list, so models can drop them.

### 17.4 Training export

Each approved version is exported as a workbook and as CSV, Parquet and JSON with the same columns, built only from its pinned inputs. Exposure and sales are exported as daily Parquet files per store and month.

**Table 37. Training export contents**

| Sheet / file | One row per | Main columns |
|---|---|---|
| Store | Store | store_code, format, cluster, floor sizes |
| Zones | Zone | zone_code, kind, area_m2, priority |
| Fixtures | Fixture | fixture_code, kind, x, y, rotation, zone, temperature, distances |
| Sections | Section | section_code, fixture, side, bay_from, bay_to, category, image policy, assignment lock |
| Surfaces | Surface | surface_id, fixture, bay, kind, height_from_floor_mm, width, depth, clear height, load limit |
| Products | Pinned product revision | sku, gtin14, revision, name, brand, category levels, sizes, size source, weight, case pack, flags |
| Placements | Position | where, what, context, why, when (dictionary below) |
| Rules · Rule results | Rule · finding | rule_id, type, severity, weight, params · target, passed, score, message |
| Changes | Command | at, actor, command type, before, after, change_set_id |
| Versions · Resets | Version · reset | status, manifest_hash, approved_by/at · fixture, planned, done, verified, deviations |
| exposure_daily · sales_daily (Parquet) | Store × SKU × day | As in section 7; joined on (store, sku, day) |

**Table 38. Placements column dictionary**

| Group | Placements columns |
|---|---|
| Where | store_code, floor, zone_code, zone_kind, fixture_code, fixture_kind, fixture_x_mm, fixture_y_mm, rotation_deg, dist_entrance_m, dist_checkout_m, side, bay_idx, section_code, section_category, surface_kind, surface_idx, height_from_floor_mm, shelf_level, temperature |
| What | sku, gtin14, product_revision, product_name, brand, category_l1..l4, width_mm, height_mm, depth_mm, dims_source, weight_g, case_pack, orientation, facings_wide, facings_high, facings_deep, capacity_units, seq, x_mm, grid_col, grid_row, linear_mm, section_share_pct |
| Context | left_sku, right_sku, above_sku, below_sku, block_id, surface_fill_pct, products_on_surface, same_sku_other_locations |
| Why | placed_by, source (planner, autofill, optimiser, ai, template, override), rule_ids, lock_kind, reason, score, change_set_id, model_version |
| When | version_id, version_number, manifest_hash, approved_by, approved_at, first_reset_done, last_day_active, exposure_basis |

### 17.5 Checks before data is used for training

- No sales columns on placement rows (schema test).
- Sum of sales after any join equals the sum in `sales_daily` for the same filter (double-count test).
- Exposure basis: train on `confirmed` days by default; `scheduled` days only with a flag.
- Out-of-stock days (from `stock_daily`, when available) and promotion days are flagged, not silently mixed in.
- Every training run stores the export checksums and manifest hashes it used, so a model can be traced back to the plans it learned from.


## 18. API specification

### 18.1 Conventions

| Topic | Convention |
|---|---|
| Style | REST + JSON over HTTPS; base path `/api/v1`; OpenAPI 3.1 generated by FastAPI and committed to `packages/contracts` |
| Auth | Bearer token from Entra ID (authorisation code + PKCE via MSAL); API validates issuer, audience, signature, expiry |
| Tenancy | Tenant from the token; never from the URL |
| Errors | Problem Details JSON (RFC 9457) with `code`, `detail`, `trace_id` |
| Concurrency | `ETag`/`If-Match` with `row_version` (`409` on mismatch) plus `Lease-Token` on edits (`423 Locked` if the lease was lost) |
| Idempotency | `Idempotency-Key` header required on all job-starting and command POST/PATCH calls; stored in PostgreSQL in the same transaction; same key + different body = `422`; kept 24 h |
| Long work | `202 Accepted` + `job_id`; `GET /jobs/{id}`; WebSocket events |
| Paging | Cursor paging: `limit`, `cursor`; filters as query parameters; sort whitelist |
| Limits | Request body ≤ 5 MB, except upload chunks (8 MB) on `/uploads`; per-user rate limits |
| Versioning | Additive changes only within v1; breaking changes get `/api/v2` and a deprecation window |

### 18.2 Endpoint catalogue

**Table 39. Main endpoints**

| Method | Path | Purpose |
|---|---|---|
| GET | /me | Current user, roles, scopes, tenant |
| GET/POST | /stores · /stores/{id} | Stores; create, update |
| GET/POST | /clusters | Store clusters |
| GET | /stores/{id}/layout | Floors, zones, landmarks, fixtures, bays, surfaces |
| PATCH | /stores/{id}/layout | Layout commands (If-Match) |
| POST | /stores/{id}/layout/freeze | Freeze the draft layout revision |
| GET | /stores/{id}/layout/revisions | Layout revision history and hashes |
| GET/POST/PATCH | /stores/{id}/sections | Sections: list, create, resize, split, merge, assign category |
| POST | /uploads · PUT /uploads/{id}/chunks/{n} · POST /uploads/{id}/complete | Chunked uploads into private storage (files, images, floor plans) |
| GET/POST | /fixture-templates | Fixture library |
| GET | /products | Search: text, GTIN, category, size, quality, similarity |
| GET | /products/{id} · /products/{id}/revisions | Product detail and revision history |
| POST | /products/{id}/revisions | Manual fix = new revision (audited) |
| POST | /imports | Start an import (profile, source); returns job |
| GET | /imports/{id} · /imports/{id}/rows | Status, counts, issues, row-level fixes |
| POST | /imports/{id}/publish | Publish approved rows |
| GET/PATCH | /images/{id} | Image status, checks, manual match, approve |
| GET/POST | /planograms | Templates and store planograms |
| GET/POST | /planograms/{id}/versions | Versions; new draft from parent |
| GET | /versions/{id} | Full planogram document |
| PATCH | /versions/{id}/positions | Command batch (If-Match, Idempotency-Key) |
| POST/DELETE | /versions/{id}/lease | Take, renew, release the edit lease (returns fencing token) |
| GET/POST/DELETE | /versions/{id}/locks | Assignment and placement locks |
| POST | /versions/{id}/rebase | Move a draft onto a newer layout revision |
| POST | /versions/{id}/validate | Run the rule set; store results |
| POST | /versions/{id}/autofill | Start auto-fill job |
| POST | /versions/{id}/optimise (V2) | Start optimiser job |
| GET | /versions/{a}/compare/{b} | Diff: added, removed, moved, re-faced, share changes |
| POST | /versions/{id}/submit · approve · reject · schedule · retire | Lifecycle actions (submit freezes; approve signs the hash) |
| GET | /versions/{id}/manifest | Pinned revisions, rule set, engine version, hash |
| GET/POST | /stores/{id}/resets | Planned resets per fixture; store team starts, finishes, verifies (with photo upload id) |
| GET | /stores/{id}/where?sku= | Every location of a SKU in the store's active plans |
| GET | /exposure?store=&from=&to= | Daily exposure rows (analysts, ML) |
| GET/POST | /planograms/{id}/overrides | Store overrides on a template |
| POST | /templates/{id}/resolve-stores | Re-resolve all following stores (job) |
| GET/POST | /rule-sets · /rules | Rule library and versions |
| POST | /rules/test | Test rules on a version without saving |
| GET/POST | /change-sets | List, create (bulk or AI), filter by status |
| POST | /change-sets/{id}/simulate · approve · reject · apply | Change-set actions |
| POST | /exports | Training export, store pack; returns job |
| GET | /jobs/{id} | Status and progress |
| GET/POST | /stores/{id}/issues | Store issue reports |
| POST | /realograms (V2+) | Upload shelf photos for reading |
| GET | /audit?entity=&id= | Command history for an item |
| WS | /ws | Live events |

### 18.3 WebSocket events

| Event | Payload |
|---|---|
| job.progress / job.done / job.failed | job_id, kind, percent, message, links |
| version.changed | version_id, row_version, by |
| lease.changed | version_id, holder, expires_at |
| reset.changed | store_id, fixture_code, version_id, status |
| version.status | version_id, status, by, comment |
| changeset.proposed | change_set_id, source, targets, level |
| import.progress | import_id, stage, counts |


## 19. Integrations

### 19.1 Interface catalogue

**Table 40. Interface catalogue**

| ID | Interface | Direction | Format | Frequency |
|---|---|---|---|---|
| IF-IN-01 | Product master | Client → platform (pilot: file); SAP S/4HANA (V1.5) | Excel/CSV template; OData API_PRODUCT_SRV in V1.5 | On demand; daily delta in V1.5 |
| IF-IN-02 (V1.5) | Product data and images | GS1 India DataKart → platform | DataKart API (Premium) or export | Daily |
| IF-IN-03 | Pack images | Teams / suppliers → platform | ZIP upload through the API, GTIN file names | On demand |
| IF-IN-04 | POS sales | POS / BI → platform | CSV or Parquet at store × SKU × day, uploaded or dropped by SFTP | Daily |
| IF-IN-05 | Stock and deliveries | ERP / WMS → platform | CSV | Daily |
| IF-IN-06 | Stores, assortment, floor plans | Client → platform | Template + DXF/PDF/images | On demand |
| IF-IN-07 (V2+) | Shelf photos | Store app / cameras → platform | JPEG via API | Event |
| IF-IN-08 | Store resets | Store app → platform | API (start, done, verify, photo) | Event |
| IF-OUT-01 | Training export and exposure | Platform → data lake / ML | XLSX, CSV, Parquet, JSON (section 17) | On approval + nightly |
| IF-OUT-02 | Store pack | Platform → stores | PDF + app | On scheduling |
| IF-OUT-03 | BI dataset | Platform → Power BI / Fabric | Reporting views or Parquet | Nightly |
| IF-OUT-04 | Webhooks | Platform → client systems | JSON (signed) | Event |
| IF-OUT-05 (V3) | Shelf label binding | Platform → ESL system | Vendor API | On publish |
| IF-X-01 (later) | Planogram exchange | Platform ↔ other tools | .psa / .pln / JSON | On demand |

The training export and the daily exposure feed are described in section 17. Webhooks are signed (HMAC-SHA256 with a per-subscriber secret), carry an event id for de-duplication and are retried with back-off from the outbox.


## 20. Security, privacy and AI safety

### 20.1 Identity and access

- Workforce users sign in with **Microsoft Entra ID** (SSO, MFA, conditional access per client policy). Supplier users (V2) use Entra External ID with their own sign-in.
- Roles are Entra app roles assigned to groups; **scopes** (stores, clusters, categories, brands for suppliers) are stored in our database and checked in the service layer (attribute-based).
- Service principals: integration jobs and the AI service have their own identities; the AI service always acts **on behalf of** a user for copilot actions and as a policy principal for L3+ actions.

### 20.2 Role permissions

**Table 41. Role permission matrix**

| Permission | Admin | Planner | Approver | Store | Analyst | Supplier (V2) |
|---|---|---|---|---|---|---|
| Manage users, templates, rule libraries, integrations | Yes | – | – | – | – | – |
| Import and fix products and images | Yes | Yes | – | – | – | Own brands |
| Edit floors, fixtures, planograms; run auto-fill | Yes | Yes (scope) | – | – | – | – |
| Create change sets / use copilot | Yes | Yes (scope) | Yes | – | – | Propose (own brands) |
| Approve, schedule, publish | Yes | – | Yes (scope) | – | – | – |
| View published plans; report issues | Yes | Yes | Yes | Own store | Yes | – |
| Download exports | Yes | Yes | Yes | – | Yes | Own brands |
| Change autonomy policy | Yes | – | – | – | – | – |

### 20.3 Controls

| Area | Control |
|---|---|
| Standard | OWASP ASVS 5.0 Level 2 checklist kept in the repository; reviewed each phase |
| Tenant isolation | Composite (tenant_id, id) keys on every table and foreign key, plus forced row-level security; app role without BYPASSRLS; cross-tenant read and write tests in CI |
| Data in transit / at rest | TLS 1.2+, HSTS; encryption at rest for all data services (customer-managed keys if required) |
| Secrets | Key Vault + managed identities; no secrets in code, pipelines use OIDC federation |
| Network | Private endpoints for PostgreSQL, storage, Key Vault and Redis; public access disabled; WAF at the edge. Service Bus Standard has no private endpoint, so it uses Entra ID only (local keys disabled) and TLS; Premium with a private endpoint if the client requires isolation |
| Uploads | Chunked uploads through the API into private storage; type, size and SHA-256 checks; malware scanning; images re-encoded before use. No browser access to storage |
| Media reads | Image renditions in a separate media storage account, read through Front Door with short-lived user-delegation SAS or Front Door Private Link (Premium) |
| Application | Pydantic validation, SQLAlchemy parameters, React output encoding, CSP headers, rate limits |
| Audit | Append-only command log written in the same transaction as each change, with actor, reason, change set and request id; admin actions logged |
| Supply chain | Dependabot, CodeQL, Trivy image scans, SBOM (Syft) per release |
| Privacy | Only staff names and emails are personal data; store photos must avoid shoppers (blur faces if present) |

### 20.4 AI-specific risks

**Table 42. AI risks and mitigations**

| Risk | Example | Mitigation |
|---|---|---|
| Prompt injection through data | A supplier writes instructions inside a product description | Tool results are data; instructions forbid acting on them; tools limited to user scope; no publish tool |
| Excessive agency | The model tries to change many stores at once | Change sets only; policy caps; approvals; per-store weekly limits |
| Wrong but confident output | Geometry or rule mistakes | Solver repair + rules engine on every proposal; simulation loop |
| Data leakage | Model sees another tenant's data | On-behalf-of tokens; row-level security; models hosted in the client's Azure |
| Cost spikes | Long agent loops | Token budgets per request and per tenant; max tool calls; alerts |
| Silent model drift | Forecasts degrade | Drift monitoring; automatic fall back to rules-only auto-fill |


## 21. Deployment and operations

*Figure 15. Azure deployment (v2.1: uploads through the API, outbox relay in the API, two storage accounts) (diagram in the PDF).*

### 21.1 Azure resources

**Table 43. Azure resources per environment**

| Resource | Starting size (proposal) | Notes |
|---|---|---|
| Front Door + WAF | Standard (Premium if managed WAF rules / Private Link needed) | Single entry point, image CDN |
| Static Web Apps | Standard | Web app |
| Container Apps environment | Workload profiles, VNet-integrated | api, worker, optimizer, vision, ai-service, jobs |
| Azure Database for PostgreSQL 18 | General Purpose 4 vCores to start; zone-redundant HA in production | PITR 14 days; long-term backups |
| Azure Managed Redis | Smallest balanced tier | Cache, pub/sub, rate limits (no edit locks) |
| Service Bus | Standard in the pilot; Premium (1 messaging unit) if network isolation is required | Queues and topics; duplicate detection on |
| Storage: data (Blob + ADLS Gen2) | Standard, ZRS in production; private endpoint only | Landing uploads, exports, lake |
| Storage: media | Standard, ZRS in production | Image renditions served through Front Door |
| Durable Task Scheduler | Consumption SKU | Workflows |
| Key Vault, ACR, Log Analytics, App Insights | Standard | Platform |
| Microsoft Foundry | Model deployments per environment | Copilot (V2) |

### 21.2 Networking and messaging tiers

Service Bus virtual-network integration and private endpoints are available only on the **Premium** tier. For the pilot we use **Standard** with local (key) authentication disabled, so only our managed identities can send or receive, and IP firewall rules where the client asks for them. If the client's security policy requires every data service on a private network, Premium is budgeted from the start; nothing in the code changes, only the Bicep parameter.

| Service | Pilot setting | If full network isolation is required |
|---|---|---|
| PostgreSQL, data storage, Key Vault, Redis | Private endpoints; public access off | Same |
| Service Bus | Standard; Entra ID only; TLS | Premium with private endpoint |
| Media storage | Read via Front Door with short-lived SAS | Front Door Premium with Private Link origin |
| Uploads | Through the API | Same |

### 21.3 Environments

| Environment | Purpose | Data | Deploy |
|---|---|---|---|
| dev | Daily integration; preview apps per pull request | Generated data | Every merge |
| test (UAT) | Client testing, pilot preparation | Masked pilot data | Release candidate + approval |
| prod | Pilot and rollout | Live | Manual approval; revision traffic shift |

### 21.4 Scaling and resilience

- API: HTTP-concurrency scaling 2–4 replicas in production, **never below 1** (it hosts the outbox relay); stateless otherwise.
- Workers: KEDA rules on Service Bus queue length; scale to zero when idle; vision on serverless GPU only when images are waiting.
- Database: scale up vCores on CPU alerts; read replica for BI if needed; partitions keep large tables fast.
- Jobs are idempotent and retried three times, then dead-lettered with an alert.
- Disaster recovery: point-in-time restore (RPO ≤ 5 min), infrastructure rebuilt from Bicep, quarterly restore drill (RTO ≤ 4 h).

### 21.5 Observability

**Table 44. Observability and alerts**

| Signal | What we collect | Alert (proposal) |
|---|---|---|
| Traces | OpenTelemetry from web, API, workers, AI service; trace id in every error | — |
| API | Rate, errors, p95 latency per route | 5xx > 2% for 5 min; p95 > 1 s for 15 min |
| Jobs and outbox | Queue length, age of oldest message, duration, dead letters, oldest unsent outbox row | Any dead letter; oldest message > 10 min; outbox lag > 60 s |
| Store execution | Resets planned vs done vs verified, days late | Reset unconfirmed 2 days after its date |
| Database | CPU, IO, connections, slow queries | CPU > 80% for 15 min; storage > 80% |
| Business | Imports, quality scores, plans approved, auto-fill runs, AI acceptance | Import failure; acceptance < 30% for a week |
| Editor | Frame time, open time, client errors | p95 open > 3 s |
| AI | Tokens, cost, tool calls, guardrail blocks | Daily cost over budget |

### 21.6 Cost drivers

- PostgreSQL size and high availability; Container Apps always-on API replicas; GPU minutes for image processing; Front Door traffic; Log Analytics ingestion; LLM tokens (V2+).
- Keep costs down: scale workers to zero, stop dev databases at night, image lifecycle rules, trace sampling, token budgets. A priced estimate is made with the Azure pricing calculator once region and sizes are agreed.


## 22. Engineering standards and testing

### 22.1 Repository layout

```
planogram-platform/
├── CLAUDE.md                      # rules for coding agents (template in 22.3)
├── docs/adr/                      # one file per decision (ADR-01 … ADR-25 to start)
├── docs/spec/                     # this specification in Markdown
├── apps/
│   └── web/                       # React 19.2 + TypeScript 7 + Vite 8
│       └── src/
│           ├── app/               # shell, routing (TanStack Router), auth (MSAL)
│           ├── features/
│           │   ├── onboarding/    # imports, mapping, review queue, image fixes
│           │   ├── floor/         # floor planner
│           │   ├── fixtures/      # fixture library and editor
│           │   ├── shelf/         # shelf planner
│           │   ├── rules/         # rule sets, locks
│           │   ├── changesets/    # compare, approvals, AI suggestions
│           │   ├── store/         # store app (mobile)
│           │   └── admin/
│           ├── canvas/            # Konva layers, culling, image LOD, snapping, transformer
│           ├── doc/               # PlanogramDoc store, command reducer, inverse commands, sync
│           └── api/               # generated types (openapi-typescript) + TanStack Query hooks
├── packages/
│   ├── contracts/                 # openapi.json, JSON schemas (commands, rules), golden/*.json
│   └── geometry-ts/               # browser fit checks (must match engines/geometry)
├── services/
│   └── api/                       # Python 3.14 package "planogram"
│       ├── planogram/
│       │   ├── main.py            # FastAPI app factory
│       │   ├── platform/          # db, tenancy, auth, settings, uow (one transaction), idempotency,
│       │   │                      # leases, outbox + relay, bus, cache, uploads, storage, telemetry
│       │   ├── modules/
│       │   │   ├── identity/  catalog/  stores/  planograms/  rules/  changesets/  integrations/
│       │   │   │   └── (each)  api.py  service.py  repo.py  models.py  schemas.py  commands.py  events.py
│       │   ├── engines/           # pure: geometry/ rules/ autofill/ optimizer/ export/ exposure/ imaging/
│       │   ├── workers/           # Service Bus consumers and job handlers (idempotent)
│       │   ├── workflows/         # Durable Task orchestrations (approval, publish, rollout)
│       │   └── ai/                # agents, MCP tool server, policy engine, evaluations (V2)
│       ├── migrations/            # Alembic
│       └── tests/                 # unit, property, golden, api, tenancy, perf
├── infra/                         # Bicep modules + azd environments (dev, test, prod)
├── seed/                          # sample mall store SMS-001: templates, layout, sections, products
├── tools/                         # seed loader, sales generator, load tests (Locust), scripts
└── .github/workflows/             # ci.yml, deploy.yml, nightly.yml
```

### 22.2 Local development

- `docker compose` runs PostgreSQL 18 with PostGIS and pgvector, Redis, Azurite (Blob emulator) and the Service Bus emulator; `make dev` starts API and web with hot reload.
- `make seed` loads the **sample mall store SMS-001** (section 10): 118 fixtures, 133 sections, 49 categories and the sample catalogue, then a generator adds 26 weeks of synthetic daily sales and confirmed resets, so every feature (and the exposure export) can be built and tested without client data.
- Feature flags (environment-backed) hide unfinished work; trunk-based development with short-lived branches.

### 22.3 CLAUDE.md template

```markdown
# CLAUDE.md — Planogram Platform

## What this repo is
Retail planogram platform. Read docs/spec/ (this specification) before large changes. Decisions live in docs/adr/.

## Golden rules
1. Every change to plans or layouts is a typed command (packages/contracts/schemas/commands). Never write positions directly.
2. Engines in services/api/planogram/engines are pure: no database, no network, no clock. Objects in, objects out.
3. Modules only import other modules' service.py public functions. Run `uv run lint-imports` before committing.
4. Every table: PRIMARY KEY (tenant_id, id); every foreign key starts with tenant_id; RLS forced. Never take tenant from the URL.
5. One request = one transaction (platform/uow.py): changes, command_log, job rows, outbox rows and the idempotency
   record commit together. Never call Service Bus, Blob or Redis to record state inside a request.
6. Frozen things never change: layout revisions, product revisions, image files, submitted versions. Make a new one.
7. Edits need a valid lease token and If-Match; check both inside the transaction, after SELECT ... FOR UPDATE.
8. Sales and exposure live at store x SKU x day. Never put sales on placement rows.
9. Uploads go through /uploads (chunked) into private storage. No SAS links for browsers.
10. Geometry rules exist twice (geometry-ts and engines/geometry). Change both and add a golden case.
11. Units: millimetres, grams, UTC. Product H/W/D follow the GS1 default front. Placement needs verified sizes.
12. AI code may only create change sets through the MCP tools. No tool may approve or activate.

## Commands
- `make dev`          start postgres+postgis, redis, azurite, service bus emulator, api, web
- `make seed`         load sample store SMS-001, its catalogue and 26 weeks of generated sales
- `make check`        ruff, mypy, import-linter, eslint, tsc, unit tests, golden parity
- `make test-all`     + api tests, tenancy tests, e2e (Playwright)
- `make perf`         canvas frame-time test and API smoke load
- `uv run alembic revision --autogenerate -m "..."` then review the SQL by hand

## Definition of done
Tests added (unit + golden where geometry/rules change); OpenAPI and generated types updated; migration reviewed;
telemetry spans added for new jobs; docs/spec or an ADR updated if behaviour changed; feature flag for risky work.

## Style
Python: type hints everywhere, Pydantic models at boundaries, small functions, no bare except.
TypeScript: strict mode, no `any`, components in features/<area>/, shared UI from shadcn/ui.
Plain, short user-facing text. Sizes in mm in the UI with cm/inch display option.
```

### 22.4 Testing strategy

**Table 45. Testing strategy**

| Level | What | Tools | When |
|---|---|---|---|
| Unit | Engines, services, reducers, components | pytest, Vitest | Every push |
| Property-based | Geometry and fit invariants (no overlap after any command sequence; x recalculation stable) | Hypothesis | Every push |
| Golden parity | Same JSON cases through TypeScript and Python geometry and rule checks | pytest + Vitest | Every push |
| API / contract | Endpoints against OpenAPI; role and tenant checks per route | pytest + Schemathesis | Every pull request |
| Tenancy | Cross-tenant reads, writes and foreign keys on every table must fail | pytest | Every pull request |
| Consistency | Kill the process between every step of a save or job: no half-written state, no lost or doubled event; replayed idempotency keys return the same response; stale lease tokens are refused | pytest + fault injection | Every pull request |
| Reproducibility | Rebuild every approved version: same manifest hash, same export checksums | pytest (nightly job in prod) | Nightly |
| Training data | Seeded store where one SKU sits in two places and sells 100 units: export has 2 placement rows, 1 exposure row per day, total sales 100 | pytest | Every pull request |
| Integration | Workers with real Postgres, Redis, emulators | pytest + docker compose | Every pull request |
| End to end | Seed → floor → section → shelf → auto-fill → submit → approve → schedule → reset → exposure → export | Playwright Test | Every deploy to dev |
| Performance | Canvas frame time with 2,000 facings; API and job load | Playwright traces, Locust | Nightly + phase ends |
| AI evaluation (V2) | Fixed request set → expected change sets; guardrail tests | Pydantic Evals | Every prompt/model change |
| Security | SAST, dependency, container scans; ASVS checklist | CodeQL, Dependabot, Trivy | Continuous; before go-live |

### 22.5 Delivery pipeline

1. **Pull request:** format, lint, types, import-linter, unit + property + golden tests, OpenAPI diff check, migration lint.
2. **Build:** web bundle, API and worker images (one image, different commands); SBOM; Trivy scan; push to ACR.
3. **Deploy dev:** Bicep what-if + apply via azd; Alembic upgrade (expand-only: migrations follow expand → migrate → contract, so an app rollback never needs a database rollback); new Container Apps revisions; E2E tests.
4. **Promote:** same images to test, then prod after approval; traffic shifted to the new revision; automatic rollback on failed health checks.


## 23. Delivery plan and backlog

*Figure 16. Phases to the pilot and the architecture scorecard (diagram in the PDF).*

The plan follows the review's advice: build one **thin end-to-end path first** on the sample store, then widen each part. By about week 6 the whole chain works for one gondola section: seed data → floor view → section → products on shelves → atomic saves → submit (frozen) → approve → schedule → reset confirmed → exposure → export. Every later phase deepens one link of a chain that already runs.

### 23.1 Phases

**Table 46. Phases to the pilot (about 23 weeks, provisional until the end of phase 0)**

| Phase | Weeks | Goal | Exit check |
|---|---|---|---|
| P0 Foundation | 2 | Repo, CI/CD, Bicep, auth, tenancy with composite keys, unit-of-work (transaction, idempotency, outbox + relay), job table, seed loader | Empty app deployed; SMS-001 loads with `make seed` |
| P1 Walking skeleton | 4 | Thin slice on SMS-001: read-only floor, sections, simple shelf editor with leases, submit/freeze, approve, schedule, reset, exposure, export | Week 6 demo of the whole chain; reproducibility and double-count tests green |
| P2 Product & image onboarding | 3 | File-first imports, mapping profiles, validation, revisions, chunked uploads, image pipeline, review queue | Pilot categories published; eligibility rules enforced |
| P3 Floor planner | 2.5 | Full floor editing: walls, landmarks, zones, fixture placement, checks, layout revisions | Pilot store drawn and frozen |
| P4 Fixtures & sections | 2 | Template editor for all surface kinds, fixture behaviour, section tools | All pilot fixtures and sections modelled |
| P5 Shelf planner | 3.5 | Full shelf editor: all surface kinds, orientation, facings, locks UI, templates and overrides, performance | Pilot category planned by hand at 30+ fps |
| P6 Rules, locks, auto-fill | 3 | Rule sets, validation, anchors and segments, heuristic auto-fill as change sets | Auto-fill draft accepted by planners |
| P7 Execution, pilot & hardening | 3 | Store app and PDF packs, compare view, reset dashboard, load and security tests, runbooks, training | Pilot store plans weekly and confirms resets in the tool |

### 23.2 Start today: the first two weeks

**Table 47. First two weeks**

| When | Do | Done when |
|---|---|---|
| Day 1 | Create the repo from the layout in 22.1; add CLAUDE.md (22.3), `docs/spec/` (this file in Markdown) and `seed/` (the sample-store files). Write ADR files 01–25 as short stubs. | Repo pushed; CI runs an empty check |
| Day 1–2 | docker compose with PostgreSQL 18 + PostGIS + pgvector, Redis, Azurite, Service Bus emulator; FastAPI app factory; Vite app shell | `make dev` shows a blank app talking to `/healthz` |
| Day 2–3 | First Alembic migration: tenant, store, layout_revision, floor, zone, landmark, fixture_template, fixture, bay, surface, section, product, product_revision (DDL in section 7) | Cross-tenant foreign-key test fails as expected |
| Day 3–4 | `make seed`: loader reads `fixture_templates.json`, `store_SMS-001.json`, `sections_SMS-001.csv`, `products_sample.csv` and writes one frozen layout revision | SMS-001 visible through `GET /stores/{id}/layout` |
| Day 4–5 | Unit of work: transaction helper, idempotency table, outbox table, relay loop with advisory lock, job table | Fault-injection test: no lost or doubled event |
| Week 2 | Read-only floor view (Konva) drawn from the layout API, coloured by section department; Entra sign-in; deploy to dev with azd | The floor plan in section 10 renders in the browser on Azure |

#### First prompts for Claude Code

```
1) "Read docs/spec (sections 7, 12.4, 22) and CLAUDE.md. Propose the monorepo scaffold and the platform/uow.py design
    (transaction, idempotency, outbox, relay). Plan only, no code yet."
2) "Implement S0.1-S0.3 from section 23. Keep every golden rule in CLAUDE.md. Add tests first."
3) "Write the first Alembic migration from the DDL in section 7 for the layout and product tables. Every table:
    PRIMARY KEY (tenant_id, id) or (tenant_id, layout_revision_id, id), composite foreign keys, forced RLS.
    Add the cross-tenant test suite."
4) "Implement S0.6 (seed loader) for seed/*.json|csv. One frozen layout revision; products as revision 1 with
    dims_source=estimated, dims_verified=true for the demo tenant only."
5) "Implement S1.1: read-only floor view in apps/web/features/floor using react-konva, drawing fixtures and
    section colours from GET /stores/{id}/layout. Match the plan figure in section 10."
```

### 23.3 Backlog with acceptance criteria

Each story is sized to fit one or two focused coding sessions. Build them in order within an epic; epics follow the phases.

**Table 48. Version-1 backlog**

| ID | Story | Acceptance criteria |
|---|---|---|
|  | **E0 · Foundation** |  |
| S0.1 | Monorepo scaffold (pnpm workspaces + uv), `make check`, CI on pull requests | All checks run in CI; failing check blocks merge |
| S0.2 | Bicep + azd environment for dev (two storage accounts, Service Bus Standard with local auth off) | `azd up` creates all resources; destroy and recreate works |
| S0.3 | Sign-in (MSAL), token validation, `/me` | No role → 403; tenant set per transaction |
| S0.4 | Tenancy: composite keys + forced RLS helper in migrations | Cross-tenant reads return 0 rows; cross-tenant foreign keys rejected |
| S0.5 | Unit of work: transaction, idempotency keys, outbox, relay in the API, job table, Service Bus consumer | Fault-injection suite: no lost, doubled or phantom events; relay runs with workers at zero |
| S0.6 | Seed loader for SMS-001 and synthetic sales generator | `make seed` loads 118 fixtures, 133 sections; 26 weeks of sales |
| S0.7 | App shell, design system, golden-case harness (TS + Python) | Shell passes axe checks; same JSON cases run in Vitest and pytest |
|  | **E1 · Walking skeleton (to week 6)** |  |
| S1.1 | Read-only floor view from the layout API, coloured by section | Matches the section 10 plan; click a fixture opens its sections |
| S1.2 | Minimal shelf editor for one gondola section: add, move, facings; placeholders for missing images | Commands saved atomically; x recalculated; fit checks |
| S1.3 | Edit leases with fencing token | Stale token → 423; two planners on two sections work at once |
| S1.4 | Submit = freeze + manifest hash; approve signs the hash | Changing a product after submit does not change the version |
| S1.5 | Schedule, store resets (start, done, verify with photo) | Version becomes active only after a done reset |
| S1.6 | Exposure builder and training export (placements, exposure, sales) | Double-count test passes; rebuild gives the same checksums |
|  | **E2 · Product & image onboarding (file-first)** |  |
| S2.1 | Chunked uploads into private storage | 2 GB file uploads with retries; hash verified; malware scan hook |
| S2.2 | Import templates, staging, mapping profiles | 100k rows staged and validated in < 10 min; profile reused |
| S2.3 | Validation P-001…P-010, I-001…I-005, quality score, size provenance | Each rule unit-tested; error report downloadable |
| S2.4 | Product revisions and publish | A re-import with no change writes no revision; a change writes one |
| S2.5 | Image matching, cut-out, renditions, image sets | ≥ 2,000 images/hour on CPU; aspect mismatch flagged |
| S2.6 | Review queue and product library search | Only approved rows publish; `product.revised` emitted |
|  | **E3 · Floor planner** |  |
| S3.1 | Floor background upload, scale from two points | Scale error < 1% on a test drawing |
| S3.2 | Walls, landmarks and zones tools | Saved as PostGIS geometry; undo/redo works |
| S3.3 | Place fixtures: snap, rotate, align, distribute | Snap 50 mm; arrow-key nudges; multi-select |
| S3.4 | Layout checks, distances, zone assignment | Overlap and aisle warnings < 100 ms; values in inspector and export |
| S3.5 | Layout revisions: freeze, new draft, rebase drafts | Positions mapped by surface id; misfits become findings |
|  | **E4 · Fixtures & sections** |  |
| S4.1 | Fixture template editor for every kind, behaviour table | All kinds in section 8 available |
| S4.2 | Bay and surface editor (notches, depth, tilt, peg grid, doors, load, temperature) | Heights snap to notch pitch; clear height recalculated |
| S4.3 | Section tools: create, resize, split, merge, assign category, image policy | No overlaps; assignment-locked sections cannot move |
|  | **E5 · Shelf planner** |  |
| S5.1 | PlanogramDoc store, command reducer, batch sync, undo | 50-command batch saves in < 300 ms p95 |
| S5.2 | Product panel with eligibility, drag to shelf, orientation | Ineligible products greyed with the reason |
| S5.3 | Facing handles, live fit, warnings panel | Golden parity 100% between TS and Python |
| S5.4 | Peg, chest, bin, bar and stack modes | Grid snapping for peg and chest |
| S5.5 | Performance: layers, culling, image LOD, worker | ≥ 30 fps with 2,000 facings in the CI perf test |
| S5.6 | Templates and store overrides | Overrides highlighted; resolve preview before submit |
|  | **E6 · Rules, locks, auto-fill** |  |
| S6.1 | Rule sets and rule editor (form from JSON schema + JSON view) | A new rule-type plugin appears without front-end changes |
| S6.2 | Version-1 rule types and validation UI | Any hard break blocks submit |
| S6.3 | Assignment and placement locks; anchors and segments | Growing A never moves locked B (property test) |
| S6.4 | Heuristic auto-fill as a change set, with reasons | 200-SKU section in < 30 s; every position has a reason |
| S6.5 | Nightly stats from sales | Stats ready by 06:00 store time |
|  | **E7 · Execution, pilot & hardening** |  |
| S7.1 | Approval workflow (Durable Task), reminders | Waiting approvals survive restarts |
| S7.2 | Compare view and store PDF pack | Diff of two 300-position versions in < 1 s; one page per fixture |
| S7.3 | Store app: fixture view, barcode lookup, resets, issues | Works on a mid-range Android phone |
| S7.4 | Execution dashboard (planned vs done vs verified) | Late resets highlighted; exposure basis shown |
| S7.5 | Load, soak and security tests (ASVS L2) | Targets met; no open high findings |
| S7.6 | Runbooks, alerts, restore drill, pilot training | Drill passed; planners use the tool weekly |

### 23.4 Team

| Role | Focus |
|---|---|
| Front-end lead | Canvas editors, PlanogramDoc, performance, design system |
| Back-end and data engineer | API, data model, onboarding, integrations, Azure, CI/CD |
| Engines and AI engineer | Geometry, rules, auto-fill, exports; image pipeline; later optimiser and AI |
| Client side | Product owner, category planning lead, IT contact (Azure, Entra ID, SAP access), data owner for feeds |


## 24. Architecture evaluation

We reviewed the design the way an architecture board would, using a light version of the Architecture Trade-off Analysis Method (ATAM): business drivers, a utility tree of quality scenarios, the approaches that answer them, sensitivity and trade-off points, risks, and fitness functions that keep checking the answers automatically.

### 24.1 Business drivers

- Plan faster and more consistently than spreadsheets and desktop tools.
- Move from cluster plans to store-specific plans without growing the planning team.
- Create clean data that links every placement to sales, so AI can learn.
- Be safe to automate step by step.
- Be run by a small team on managed Azure services.

### 24.2 Utility tree and scenarios

**Table 49. Utility tree scenarios (importance / difficulty)**

| ID | Quality | Scenario (stimulus → response, measure) | Imp./Diff. | Design answer |
|---|---|---|---|---|
| Q01 | Performance | Planner drags on a 2,000-facing gondola → frame time ≤ 33 ms | H / H | Konva layers, culling, image LOD, Web Worker |
| Q02 | Performance | Auto-fill a 200-SKU section → draft in < 30 s, editor stays usable | H / M | Queued job, pure engine in worker |
| Q03 | Scalability | Grow from 5 to 1,000 stores → no schema change; API p95 unchanged | H / M | Partitions, snapshot compaction, stateless API |
| Q04 | Modifiability | Add a new rule type → plugin + schema, no migration, < 2 days | H / L | Rules as data, plugin registry |
| Q05 | Modifiability | Add a new fixture kind → template + existing surface kinds, < 1 day | M / L | One geometry model |
| Q06 | AI-readiness | Copilot swaps an item across 300 planograms → one change set, validated, nothing live without policy | H / M | Commands, change sets, MCP tools, policy |
| Q07 | Safety | AI output breaks a hard rule → repaired or blocked, logged | H / L | Solver repair + rules engine on every proposal |
| Q08 | Availability | Worker or API crashes mid-save or mid-job → nothing half-written, no event lost or doubled | H / M | One transaction, outbox, idempotency keys, guarded job start |
| Q09 | Security | A bug tries to link tenant A's position to tenant B's surface → rejected by the database | H / L | Composite tenant keys + forced RLS, tests |
| Q10 | Interoperability | New retailer with another ERP → new import profile only | M / L | Profiles, staging, open formats |
| Q11 | Data quality | Wrong pack sizes uploaded → flagged before placement | H / M | Size outliers, image aspect check, quality gate |
| Q12 | Recoverability | Database fault → restore in ≤ 4 h with ≤ 5 min loss | H / M | PITR, zone-redundant HA, drills |
| Q13 | Explainability | Auditor asks why an item is at eye level → reason, rules, actor in one click | M / L | Provenance on positions, command log |
| Q14 | Concurrency | Two planners, same store, different sections → no blocking; a lost lease can never overwrite | M / M | Edit leases with fencing token |
| Q15 | Cost | Quiet weekend → workers at zero, events still flow | M / L | KEDA scale-to-zero; relay in the API |
| Q16 | Reproducibility | Auditor asks for the plan approved last March → same PDF and export, byte for byte | H / M | Immutable revisions, manifest hash, nightly rebuild |
| Q17 | Data correctness | SKU in two places sells 100 units → models see 2 placements, 1 exposure row a day, 100 units | H / M | Store × SKU × day grain; exposure from confirmed resets |

### 24.3 Sensitivity and trade-off points

| Point | Type | Analysis |
|---|---|---|
| Position rows per version | Sensitivity | Store-specific plans multiply rows; compaction of retired versions and hash partitions keep the hot set small. |
| Command batch size | Sensitivity | Larger batches cut round trips but raise conflict cost; default 1 s or 50 commands. |
| Image rendition size | Sensitivity | Bigger images look better but cost frame time; three renditions chosen by zoom. |
| Section leases vs live co-editing | Trade-off | Simpler and safer now; CRDT path kept open through the PlanogramDoc model. |
| Immutable revisions | Trade-off | More rows (layout copies, product revisions), in exchange for plans that can always be rebuilt and explained. |
| Service Bus Standard vs Premium | Trade-off | Standard is far cheaper but has no private endpoint; Entra-only auth is enough for the pilot unless policy demands isolation. |
| Materialised store versions vs computed on read | Trade-off | More storage, but exports, stores and ML read one simple shape. |
| Python authority + TypeScript checks | Trade-off | Two implementations, controlled by golden parity tests; Python wins for optimisation and AI. |
| Modular monolith | Trade-off | One deployable to run; heavy work already isolated in workers; modules can be split later. |
| Managed Azure services | Trade-off | Some platform lock-in and cost, in exchange for far less operations work for a team of three. |

### 24.4 Risks and non-risks

| Item | Kind | Response |
|---|---|---|
| Poor product sizes and images | Risk (high) | Onboarding in phase 1, quality gate, capture app, DataKart |
| Canvas speed on low-end laptops | Risk (medium) | Perf test in CI from phase 4; PixiJS fallback for the product layer |
| TS/Python check drift | Risk (medium) | Golden parity tests block merges |
| Template override conflicts | Risk (medium) | Typed overrides, review queue, clear UI |
| Planner trust in AI | Risk (medium) | Levels, explanations, test vs control, easy undo |
| Regional availability of serverless GPU, Durable Task Scheduler, Foundry models | Risk (low–medium) | Check in phase 0 for the chosen region; CPU and queue fallbacks |
| Team of three (bus factor) | Risk (medium) | ADRs, CLAUDE.md, pairing on engines, runbooks |
| Stores do not confirm resets | Risk (high for ML) | Simple phone flow, reminders, dashboard; exposure flagged `scheduled` when unconfirmed |
| Sales feed grain or codes differ from ours | Risk (medium) | Check in phase 0 (Q6); mapping table; reject rows that do not match store × SKU × day |
| PostgreSQL capacity at design scale | Non-risk | Partitioning and compaction keep tables well within managed limits |
| Image delivery | Non-risk | Front Door cache; renditions |

### 24.5 Fitness functions

**Table 50. Automated fitness functions**

| Fitness function | Check | Threshold |
|---|---|---|
| Module boundaries | import-linter contracts in CI | 0 violations |
| Editor frame time | Playwright trace with 2,000 facings | p95 ≤ 33 ms |
| API latency | Locust smoke per release | Command batch p95 ≤ 300 ms |
| Geometry parity | Golden cases in Vitest and pytest | 100% equal |
| Tenant isolation | Cross-tenant read and foreign-key suite | 0 rows; all writes rejected |
| Reproducibility | Nightly rebuild of approved versions | 100% same hash and checksums |
| Training-data grain | Double-count test on the seed store | Sales total unchanged by joins |
| Outbox liveness | Commit a change with workers at zero | Event on Service Bus in ≤ 10 s |
| Lease fencing | Save with an older token after takeover | Always refused |
| Migration safety | Upgrade/downgrade on a prod-sized copy; migration lint | No long locks, no data loss |
| Bundle size | Build report | Initial JS ≤ 400 kB gzip |
| Dependencies | Dependabot, Trivy | No critical or high |
| AI guardrails (V2) | Adversarial proposal suite | 100% of rule-breaking proposals blocked |
| Cost | Budget alerts per environment | Within monthly budget |

### 24.6 Scorecard

| Quality | Score (1–5) | Comment |
|---|---|---|
| Performance | 4 | Strong design; must be proven with the perf test on pilot hardware |
| Scalability | 4 | Ready for 1,000 stores; compaction job is essential |
| Modifiability | 5 | Rules as data, one geometry model, plugin rule types |
| AI-readiness | 5 | Commands, change sets, MCP, policy, provenance in place from V1 |
| Security | 4 | Composite keys + RLS, Entra ID, private endpoints, uploads via API; external test before go-live |
| Data for ML | 5 | Confirmed exposure, single grain, frozen inputs, provenance (new in v2.1) |
| Availability | 3 | 99.5% target; single region; DR by restore |
| Operability / cost | 4 | Managed services, scale to zero, IaC |


## 25. Future roadmap

Each future capability below is an addition to the version-1 base. The middle column shows what already exists, which is why it is cheap to add later.

**Table 51. Future capabilities and what the base already provides**

| Capability | When | Already in the base | Extra work |
|---|---|---|---|
| Bulk change sets across stores | V1.5 | Commands, change-set tables, workflows | Selection UI, preview at scale |
| 3D store viewer | V1.5 | mm geometry, fixture heights, surfaces | React Three Fiber viewer, fixture models |
| DXF floor import | V1.5 | PostGIS floors and zones | DXF parser and layer mapping |
| Capture app for pack photos | V1.5 | Image pipeline, GTIN matching | Phone camera flow |
| Store-specific generation at scale | V2 | Templates, overrides, clusters, jobs | Per-store optimiser runs, orchestration |
| Forecasts and space elasticity | V2 | Daily exposure and sales at the same grain, frozen versions | Feature pipeline, models |
| CP-SAT optimiser | V2 | Rule repair hints, workers | Model formulation, tuning |
| AI suggestions L1–L2 and copilot | V2 | Change sets, MCP-ready API, policy tables | Models, Foundry deployment, eval sets |
| Supplier portal | V2 | Partner scopes, RLS | External ID, portal screens |
| Photo to draft planogram | V2+ | Embeddings, realogram tables | Detector, matching, review UI |
| Photo compliance and store tasks | V3 | Realograms, published versions | Scoring, task flow |
| Policy auto-apply (L3) and continuous planning (L4) | V3 | Policy engine, durable workflows, events | Experiment framework, KPI monitors |
| Electronic shelf label binding | V3 | Stable position ids, publish events | Vendor connector |
| Digital-twin export | V3 | 3D-ready geometry, open JSON | glTF/USD export |
| Labour-aware resets | Later | Version diffs | Time model per change, task planning |
| Retail media placements | Later | Provenance, position inventory | Sponsored-slot rules and reporting |
| .psa / .pln exchange | Later | Open document model | Format adapters |
| Multi-retailer SaaS | Later | Tenants, RLS, scopes | Billing, self-service onboarding, isolation tiers |

### 25.1 Gates between versions

| Gate | Condition |
|---|---|
| V1 → V1.5 | Pilot store plans weekly in the tool; product data quality ≥ 90% of ranged SKUs above score 80 |
| V1.5 → V2 | Confirmed exposure joined to POS sales for at least one quarter in several stores |
| V2 → V3 | AI suggestions accepted ≥ 50% at L2 for two months, and a measured win in test vs control stores |


## 26. Risks, open questions and decisions

### 26.1 Open questions for the client

| # | Question | Needed by |
|---|---|---|
| Q1 | Which store and categories run the pilot? | P0 |
| Q2 | Can we get a full product export with sizes and units of measure now (file), and read access to the SAP product API for V1.5? | P0 |
| Q3 | Does the client (or its brands) use GS1 India DataKart, and can we get API access? | P0 |
| Q4 | Who owns pack images, and may we process and store them? | P0 |
| Q5 | In what form are floor plans available (DXF, PDF, photos)? | P0 |
| Q6 | Do POS sales use the same store codes and SKUs as SAP? | P0 |
| Q7 | Azure subscription, region and Entra ID tenant; any data-residency rules? | P0 |
| Q8 | Who approves planograms; does approval differ by category? | P5 |
| Q9 | Which rules should be loaded first (eye level, adjacency, restricted items)? | P5 |
| Q10 | How long must history, exports and backups be kept? | P6 |
| Q11 | Is an external penetration test required before production? | P6 |
| Q12 | Are suppliers expected to use the platform, and when? | V2 planning |
| Q13 | Who confirms resets in the store, and can they use a phone app for it? | P1 |
| Q14 | Does security policy require every data service on a private network (Service Bus Premium)? | P0 |
| Q15 | At what grain does the POS feed arrive (store × SKU × day expected), and how are returns and promotions marked? | P0 |

### 26.2 Decisions needed now

1. Approve architecture v2.1 and the ADRs in section 4.
2. Confirm the pilot scope and categories.
3. Grant data access (SAP, sales feed) and decide the image source.
4. Provide the Azure subscription and Entra ID tenant, and confirm the region.
5. Agree the quality targets in section 3 as acceptance criteria.


## Appendix A. Glossary

|  |  |
|---|---|
| Planogram | Plan that shows which products go where on a fixture and with how many facings |
| Realogram | What is actually on the shelf, read from a photo |
| Fixture / bay / surface / position | Holder of products / vertical slice / where products sit / one product on one surface |
| Facing | One unit visible at the front; facings wide × high × deep give the space |
| GTIN | Global Trade Item Number (the barcode number); stored as 14 digits |
| Template / override | Cluster-level planogram / small typed store change on top of it |
| Command | Typed change (e.g. SetFacings) applied and validated by the server |
| Change set | A group of commands proposed by a planner, bulk job, template or AI |
| Autonomy level | How far AI may act on its own (L0 manual … L4 continuous) |
| Hard / soft rule | Must pass (blocks approval) / preference (affects score) |
| Space elasticity | How sales change when a product gets more or less space |
| Days of supply | How many days of sales the shelf holds |
| Outbox | Table of events and job messages written in the same transaction as the change, published afterwards by the relay |
| Section | A category's space: a bay range on one side of one fixture |
| Layout revision | A frozen snapshot of the whole physical store (floor, fixtures, surfaces, sections) |
| Product revision | A frozen copy of a product's sizes, flags and images; edits create new revisions |
| Manifest hash | Fingerprint of everything a version depends on; approval signs it |
| Assignment / placement lock | Space stays with a category / a product stays in its place |
| Edit lease, fencing token | Time-limited right to edit a draft; a growing number that makes stale saves fail |
| Store reset | The real change-over of a fixture in the store: started, done, verified |
| Exposure | What was on the shelf for a SKU on a day: locations, facings, space, capacity |
| Idempotency key | Client-chosen id that makes a retried request safe |
| RLS | Row-level security: the database filters rows by tenant |
| MCP | Model Context Protocol: standard way to give AI models tools |
| CP-SAT | Constraint solver in Google OR-Tools |
| ATAM | Architecture Trade-off Analysis Method |
| ESL | Electronic shelf label |


## Appendix B. JSON examples

### B.1 Planogram document (trimmed)

```json
{
  "version": {"id": "0193c2a4-...", "number": 4, "status": "in_review", "row_version": 13,
              "layout_revision_id": "0193b1...", "template_version_id": "0193b0...",
              "rule_set_version_id": "0193a9...", "engine_version": "2.1.0",
              "manifest_hash": "sha256:7c1e...", "frozen_at": "2026-12-01T09:12:00Z"},
  "store": {"code": "SMS-001", "cluster": "mall_large"},
  "section": {"code": "G03-A-01", "category": "packaged_food.breakfast_cereals", "bays": [1, 6],
              "image_policy": "placeholder_ok"},
  "fixture": {"code": "G03", "kind": "gondola", "x_mm": 11600, "y_mm": 5200, "rotation_deg": 90,
              "zone": "main_aisle", "temperature": "ambient",
              "bays": [{"idx": 1, "side": "A", "width_mm": 1000, "height_mm": 1900, "depth_mm": 450,
                        "surfaces": [{"id": "0193b8...", "kind": "shelf", "idx": 4,
                                      "height_from_floor_mm": 1200, "width_mm": 1000, "depth_mm": 450,
                                      "positions": [{"id": "0193c3...", "sku": "SKU00014", "gtin14": "02000000000145",
                                                     "seq": 1, "x_mm": 0, "facings": {"wide": 4, "high": 1, "deep": 4},
                                                     "orientation": "front", "product_revision": 2,
                                                     "lock": {"kind": "placement", "keep": ["surface", "seq"]},
                                                     "placed_by": "autofill:1.0", "rule_ids": ["R-12", "R-07"],
                                                     "reason": "Eye level (R-12); 4 facings give 6.6 days of supply"}]}]}]},
  "score": 91.0, "hard_breaks": 0
}
```

### B.2 Change set proposed by AI

```json
{
  "id": "0193d1...", "source": "ai", "status": "proposed", "autonomy_level": 2,
  "title": "Swap delisted Kirra 500 g and add Ostra Nut Muesli",
  "rationale": "Kirra 500 g delisted on 12 Dec; Ostra Nut Muesli is a new launch with similar items selling 4.1 units/day.",
  "confidence": 0.84, "risk": "medium", "model_version": "placement-scorer-0.3",
  "expected": {"units_pct": 3.6, "margin_pct": 2.9},
  "items": [{"version_id": "0193c2...", "commands": [
      {"type": "ReplaceProduct", "position_id": "0193c5...", "product_id": "0193a7..."},
      {"type": "SetFacings", "position_id": "0193c5...", "wide": 3, "high": 1, "deep": 4},
      {"type": "AddPosition", "surface_id": "0193b7...", "product_id": "0193aa...", "seq": 4,
       "facings": {"wide": 2, "high": 1, "deep": 4}}]}],
  "guardrails": {"hard_rules_pass": true, "locks_untouched": true, "facings_changed_pct": 9.0}
}
```


## Appendix C. Product import template

**Table 52. Import template columns**

| Column | Required | Type / unit | Example | Notes |
|---|---|---|---|---|
| sku | Yes | text | 100245 | Retailer article number |
| gtin | Yes* | 8/12/13/14 digits, check digit valid | 2000000000145 | *Required unless store-made item. Demo data uses the GS1 20–29 restricted-circulation prefixes |
| name | Yes | text | Sunmill Rolled Oats 1 kg |  |
| brand | Yes | text | Sunmill |  |
| category_l1 … category_l4 | Yes (l1–l2) | text | Food › Breakfast › Oats |  |
| height_mm / width_mm / depth_mm | Yes | integer mm | 290 / 190 / 70 | GS1 default front |
| dims_source | Yes | measured / supplier / gs1 / sap / estimated | measured | Estimated sizes allow drafts only |
| weight_g | Recommended | integer g | 1050 | Gross weight |
| case_pack | Recommended | integer | 12 | Units per case |
| tray_qty | Optional | integer | 6 | Units per tray |
| temperature | Yes | ambient / chilled / frozen | ambient |  |
| can_stack / can_lay_down / can_rotate | Optional | yes/no | yes / no / yes | Allowed orientations (section 8) |
| status | Yes | active / delisted | active |  |
| listed_from / delist_date | Optional | date | 2026-12-12 |  |
| price_band | Optional | text | mid | For price flow |
| is_private_label | Optional | yes/no | no |  |
| supplier_code | Optional | text | SUP-0091 |  |
| age_restricted / hazardous / fragile | Yes | yes/no | no / no / no | Blank is not “no”; placement blocked until answered |
| image_front / image_side / image_top | Optional | file name | 2000000000145_front.png | If images come in a ZIP |
| attributes.* | Optional | any | attributes.flavour = plain | Extra columns kept in JSONB |


## Appendix D. Seed data files

The sample mall store ships as plain files in `seed/`, generated by `seed/make_seed.py` and loaded with `make seed`. They are delivered with this document.

| File | Contents | Rows |
|---|---|---|
| fixture_templates.json | 13 fixture templates with surfaces, sizes, temperature and load limits | 13 |
| store_SMS-001.json | Store, floor outline, landmarks, zones and 118 placed fixtures (x, y, rotation, footprint) | 1 store |
| sections_SMS-001.csv | Section code, fixture, side, bay range, category, department, assignment lock | 133 |
| categories.csv | Category code, department, name, temperature | 49 |
| products_sample.csv | Invented sample products with GTINs in the 200 range, sizes, weight, temperature, flags | 60 |
| product_import_template.csv | Empty import template with every column of Appendix C | header |
| store_SMS-001_plan.svg | The floor plan drawn from the files above | — |


## Appendix E. References

| Source | Title | Where |
|---|---|---|
| Blue Yonder | Every store can finally be local: from static space planning to continuous AI-driven optimization (2026) | blueyonder.com/blog/2026/every-store-can-finally-be-local-from-static-space-planning-to-continuous-ai-driven-optimization |
| Blue Yonder | The Shelf Ops Agent takes center stage (2025) | blueyonder.com/blog/2025/the-shelf-ops-agent-takes-center-stage |
| Blue Yonder / Business Wire | New Cognitive Solutions for Space Planning at ICON 2026 | businesswire.com/news/home/20260519113371/en |
| NIQ via destinationCRM | NIQ adds AI and automation to Spaceman (Oct 2026) | destinationcrm.com (article 176865) |
| RELEX | Store-specific planogram optimization | relexsolutions.com/resources/planogram-optimization |
| RELEX | 4 ways to use AI in DIY retail (One Stop example) | relexsolutions.com/resources/4-ways-to-use-ai-to-master-diy-retail-supply-chain-challenges |
| Scientific Reports | Real-time retail planogram compliance using computer vision and virtual shelves (Dec 2025) | doi.org/10.1038/s41598-025-27773-5 |
| arXiv 2605.14430 | OPTIMUS: Optimization productivity tool for intelligent management of utilizable space | arxiv.org/abs/2605.14430 |
| arXiv 2601.00527 | Cloud-native generative AI for automated planogram synthesis | arxiv.org/abs/2601.00527 |
| Hanshow / PR Newswire | Store Digital Twin solutions at EuroShop 2026 | prnewswire.com (20260223EN92886) |
| GS1 India | DataKart: national product data repository | gs1india.org/datakart |
| GS1 | Package and Product Measurement Standard | ref.gs1.org/standards/ppm |
| GS1 | Product Image Specification Standard (incl. planogram images) | gs1.org/standards/gs1-product-image-specification-standard/current-standard |
| SAP | Product master API (API_PRODUCT_SRV, A_ProductUnitsOfMeasure) | help.sap.com / api.sap.com |
| Microsoft | PostgreSQL 18 GA on Azure Database for PostgreSQL | techcommunity.microsoft.com/blog/adforpostgresql (4469802) |
| Microsoft | Azure Container Apps serverless GPUs GA | learn.microsoft.com/azure/container-apps/gpu-serverless-overview |
| Microsoft | Durable Task Scheduler (Consumption SKU GA, 2026) | learn.microsoft.com/azure/durable-task/scheduler |
| Microsoft | Azure Durable Task for Pydantic AI agents (Nov 2026) | techcommunity.microsoft.com/blog/appsonazureblog (4571024) |
| Microsoft | Foundry Models sold directly by Azure | learn.microsoft.com/azure/foundry/foundry-models |
| Konva | Best JavaScript canvas library — how to choose | konvajs.org/docs/guides/best-canvas-library.html |
| tldraw | License key required in production | tldraw.dev/sdk-features/license-key |
| Timefold / SolverForge | Timefold Python solver discontinued | pypi.org/project/solverforge-legacy |
| Pydantic | Pydantic AI (MIT, MCP support) | pydantic.dev/pydantic-ai |
| BRIA | RMBG-2.0 licence (non-commercial weights) | huggingface.co/briaai/RMBG-2.0 |
| Peng Zheng et al. | BiRefNet (MIT) | github.com/ZhengPeng7/BiRefNet |
| Python | Python 3.15.0 released 9 Oct 2026 | python.org/downloads/release/python-3150 |
| Microsoft | TypeScript 7.0 (native compiler) | devblogs.microsoft.com/typescript/announcing-typescript-7-0 |
| Vite | Vite 8 with Rolldown | vite.dev/blog/announcing-vite8 |
| React | React 19.2 and React Compiler 1.0 | react.dev/blog |
| Yjs / Tiptap | Yjs CRDT and Hocuspocus server | github.com/yjs/yjs · tiptap.dev/docs/hocuspocus |
| Microsoft | Service Bus network security (VNet and private endpoints on Premium only) | learn.microsoft.com/azure/service-bus-messaging/network-security |
| Microsoft | Service Bus: disable local (SAS key) authentication | learn.microsoft.com/azure/service-bus-messaging/disable-local-authentication |
| Microsoft | Service Bus duplicate detection | learn.microsoft.com/azure/service-bus-messaging/duplicate-detection |
| Open Food Facts | API documentation (User-Agent, rate limits) and data licence (ODbL; images CC BY-SA) | openfoodfacts.github.io/openfoodfacts-server/api · world.openfoodfacts.org/terms-of-use |
| GS1 | General Specifications: restricted circulation numbers (prefixes 20–29) | gs1.org/standards/barcodes-epcglobal-tag-data/gs1-general-specifications |
| M. Kleppmann | How to do distributed locking (fencing tokens) | martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html |
| microservices.io | Pattern: transactional outbox | microservices.io/patterns/data/transactional-outbox.html |
