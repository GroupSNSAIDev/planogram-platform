# POC v2: development phases

Builds on the Phase 1 POC (see TRACKER.md). It answers the review of v1:
- show how placement works
- use real product images
- make manual placement easy
- support big stores and a professional floor designer
- add store execution exports (PDF and Excel)
- add a product Excel template that stores fill in and we import

Research basis:
- Large Indian hypermarkets are about 35,000 sq ft on average; new DMart stores are 50,000–67,000 sq ft.
- Layouts are dense with narrow aisles, and daily FMCG items are on the ground floor.
- Standard layout practice: a racetrack main aisle around a gondola grid, staples and daily needs at the back, end caps for high-visibility promotions, impulse items at checkout.

Product images come from Open Food Facts (Open Beauty Facts was planned for personal care but its servers are not reachable from this network). These are open databases: data under ODbL, images under CC BY-SA. Spec §9.2 and §10.6 allow them for the **demo tenant only**, with attribution shown. Client products always come through the Excel template instead.

| Phase | Name | What it delivers | Done when | Status |
|---|---|---|---|---|
| **A** | Real product catalogue | ~400 real Indian products with front images across all store categories. Fetched once, cached in `seed/catalogue/`. Sizes estimated from pack quantity and category. Attribution file | Every shelf category has at least 6 real products with images | 🟡 Done for food (702 products, 27 food categories × 26). Open Beauty Facts was unreachable from this network, so personal care and home care keep placeholder products until stores send their workbook |
| **B** | Product Excel template + import | `Product_Import_Template.xlsx`: an instructions sheet; a Products sheet with sizes, safety flags and an embedded picture or image file name; a Categories sheet. Import page (upload .xlsx and optional image ZIP) → validation report → publish. A filled workbook with all products and images, imported as the demo catalogue | The filled workbook re-imports with 0 errors and the images appear in the app | ✅ Done: 720 rows, 715 published with 702 pictures; 5 open-data rows are correctly rejected for bad GTIN check digits |
| **C** | Real images on shelves | Media endpoint; pack images on every facing in the shelf planner; thumbnails in the product panel; product library page | Shelves show real pack photos at true size | ✅ Done |
| **D** | Explain auto-fill | Rules page: every rule, hard/soft, weight, parameters, plain-English meaning. "How auto-fill works" panel with the live numbers for this section. Step trace in each proposal | A planner can see why each product went where it went | ✅ Done |
| **E** | Big stores + pro floor designer | Create a store of any size (up to 300 × 300 m). New research-based sample hypermarket SMS-002 (~90 × 62 m, ~60,000 sq ft, ~400 fixtures). Full-screen designer in a new tab: fixture icons and type styling, readable labels, hover cards, search-and-jump, minimap, rulers, box select, align/distribute. Export a design to a file and import it later | SMS-002 edits smoothly; an exported design re-imports identically | ✅ Done |
| **F** | Easy manual placement | Click a fixture → drawer with every section, mini-planogram thumbnails and a Plan button. Section switcher in the shelf planner. Product panel with images and category filter. Auto-fill a whole fixture or the whole store in one click | Any section can be filled by hand or auto-filled in two clicks | ✅ Done (the fixture panel lists sections with product counts and Plan links; mini-planogram thumbnails not built) |
| **G** | Store execution pack | (1) Floor plan PDF: top view with every fixture code and a legend. (2) Planogram PDF: one page per section with the elevation drawn with product images, plus the shelf list. (3) Execution Excel: summary, sections, and a row per shelf position with product, GTIN, image, facings, units and W × H × D | Download buttons produce all three files for a filled store | ✅ Done |
| **H** | Polish and QA | UI pass, e2e script extended, tests, README and tracker | All tests and the e2e run pass | ✅ Done |
