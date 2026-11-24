---
name: Planogram Precision Engine
colors:
  surface: '#faf8ff'
  surface-dim: '#d2d9f4'
  surface-bright: '#faf8ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f3ff'
  surface-container: '#eaedff'
  surface-container-high: '#e2e7ff'
  surface-container-highest: '#dae2fd'
  on-surface: '#131b2e'
  on-surface-variant: '#464554'
  inverse-surface: '#283044'
  inverse-on-surface: '#eef0ff'
  outline: '#777586'
  outline-variant: '#c7c4d7'
  surface-tint: '#5148d7'
  primary: '#2a14b4'
  on-primary: '#ffffff'
  primary-container: '#4338ca'
  on-primary-container: '#c1beff'
  inverse-primary: '#c3c0ff'
  secondary: '#006a61'
  on-secondary: '#ffffff'
  secondary-container: '#86f2e4'
  on-secondary-container: '#006f66'
  tertiary: '#553300'
  on-tertiary: '#ffffff'
  tertiary-container: '#744800'
  on-tertiary-container: '#ffb759'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#e3dfff'
  primary-fixed-dim: '#c3c0ff'
  on-primary-fixed: '#100069'
  on-primary-fixed-variant: '#372abf'
  secondary-fixed: '#89f5e7'
  secondary-fixed-dim: '#6bd8cb'
  on-secondary-fixed: '#00201d'
  on-secondary-fixed-variant: '#005049'
  tertiary-fixed: '#ffddb8'
  tertiary-fixed-dim: '#ffb95f'
  on-tertiary-fixed: '#2a1700'
  on-tertiary-fixed-variant: '#653e00'
  background: '#faf8ff'
  on-background: '#131b2e'
  surface-variant: '#dae2fd'
typography:
  headline-lg:
    fontFamily: Inter
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.015em
  headline-sm:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.01em
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: 0em
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
    letterSpacing: 0em
  body-sm-medium:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
    letterSpacing: 0em
  label-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-uppercase:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.06em
  code-tabular:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
    letterSpacing: -0.02em
  code-tabular-bold:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: -0.02em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 16px
  gutter-dense: 8px
  margin: 16px
  space-xs: 4px
  space-sm: 8px
  space-md: 12px
  space-lg: 16px
  space-xl: 24px
---

## Brand & Style

The design system is crafted for high-density, professional visual merchandising, floor-planning, and shelf-space orchestration. Drawing direct inspiration from modern toolsets like Linear, Figma, and Notion, the visual tone is quiet, razor-sharp, analytical, and highly structured. The user interface prioritizes utility and spatial efficiency over ornamental decoration, ensuring that merchandisers, retail architects, and category managers can parse massive SKU libraries, spatial constraints, and volumetric metrics without cognitive fatigue.

### Core Principles
- **Instrument-Grade Clarity**: Visual real estate is dedicated to store fixtures, spatial canvas rendering, and data tables. Interface chrome remains understated and lightweight.
- **Calm Density**: Information is tightly packed using a disciplined 4px/8px rhythm, compact controls, and explicit typography levels that balance high scanability with ergonomic interaction.
- **Structural Separation**: Boundaries and hierarchy are defined primarily through crisp 1px borders and surface tonal shifts rather than heavy drop shadows.
- **Spatial Precision**: The interface respects real-world CAD spatial mechanics, leveraging unambiguous department color codes, fixture guides, and monospaced measurement tokens.

## Colors

The color palette is engineered for precision CAD rendering, high-density reporting tables, and instant visual categorization across retail floor plans.

### Base & Structural Palette
- **Ink / Primary Text**: `#0F172A`
- **Secondary Text**: `#475569`
- **Muted / Placeholder Text**: `#64748B`
- **Structural Borders**: `#E2E8F0`
- **Page Canvas Background**: `#F4F5F8`
- **Surfaces & Cards**: `#FFFFFF`
- **Canvas Work Area**: `#F8FAFC` with a 50mm virtual grid overlay

### Primary & Feedback
- **Primary Indigo**: `#4338CA` (Hover: `#3730A3`, Surface Tint: `#EEF2FF`)
- **Accent Amber**: `#F59E0B` (Warning Surface: `#FEF3C7`, Warning Text: `#D97706`)
- **Success Green**: `#059669` (Tint: `#ECFDF5`)
- **Danger Red**: `#DC2626` (Tint: `#FEF2F2`)
- **Info Teal**: `#0D9488` (Tint: `#CCFBF1`)

### Status Chip Tokens
All status chips use a soft tinted background with high-contrast text:
- **Draft**: Background `#F1F5F9`, Text `#475569`
- **In Review**: Background `#EEF2FF`, Text `#4338CA`
- **Approved**: Background `#ECFDF5`, Text `#059669`
- **Scheduled**: Background `#FEF3C7`, Text `#D97706`
- **Active**: Background `#CCFBF1`, Text `#0F766E`
- **Superseded**: Background `#E2E8F0`, Text `#334155`
- **Rejected**: Background `#FEF2F2`, Text `#DC2626`
- **Frozen**: Background `#334155`, Text `#F8FAFC` (paired with snowflake icon)

### Department Floorplan & Shelf Tokens
Muted pastels calibrated to allow high-contrast dark text and SKU bounding boxes:
- **Fresh**: `#BBF7D0`
- **Dairy & Chilled**: `#BFDBFE`
- **Beverages**: `#A5F3FC`
- **Frozen**: `#C7D2FE`
- **Staples**: `#FDE68A`
- **Packaged Food**: `#FED7AA`
- **Personal Care**: `#FBCFE8`
- **Home Care**: `#DDD6FE`
- **General Merchandise**: `#E5E7EB`
- **Impulse**: `#FCA5A5`
- **Promotions**: `#D9F99D`

### CAD & Canvas Tokens
- **Shelf Edges / Structural Rails**: `#334155`
- **Selection Bounding Box**: `#4338CA` (2px stroke, outer halo `#EEF2FF`)
- **Dimension Callout Lines**: `#64748B` (1px dashed or solid with end ticks)
- **Constraint / Collision Warnings**: `#F59E0B`
- **Hard Collision / Out-of-Bounds Breaks**: `#DC2626`

## Typography

Typography enforces rigid tabular alignment and quick visual parsing. 

### Font Configuration
- **Primary Interface**: `Inter` handles all structural headers, interactive elements, forms, and general UI copy.
- **Data & Identifiers**: `JetBrains Mono` is strictly applied to SKUs, GTIN barcodes, fixture IDs (e.g., `BAY-04-A`), coordinate pairs, hashes, and real-world linear dimensions.

### Numerical & Tabular Data Rules
- All numeric tables, financial values, fixture dimensions, and bay capacities must enforce `font-variant-numeric: tabular-nums`.
- Section headers inside dense sidebars and inspector groups use `label-uppercase` in all-caps with `0.06em` letter spacing for immediate block separation without heavy border divisions.

### Content & Localization Formatting
- **Metric Distances**: Millimeters formatted with comma thousands separators (e.g., `1,200 mm`, `450 mm`).
- **Currency**: Indian Rupee (`₹`), formatted without unnecessary trailing decimals when whole (e.g., `₹4,250`, `₹18,900.50`).
- **Dates**: Universal format `DD MMM YYYY` (e.g., `23 Nov 2026`).
- **Store Nomenclature**: Structured format `[Store Code] · [Store Description]` (e.g., `SMS-001 · Sample Mall Store`).
- **Fictional Test Brands**: Sunmill, Kirra, Ostra, Mavo, Pellio, Fizza, Lumo, Zesto, Vexa.

## Layout & Spacing

The layout is built around a CAD workbench framework with a fixed chrome shell surrounding an infinitely scrollable or pannable 2D planogram viewport.

### Workbench Architecture
- **Left Navigation / Asset Library**: Fixed width `280px` (collapsible to `48px` icon rail). Contains fixture catalogs, SKU drag-and-drop pallets, and store hierarchy trees.
- **Center Canvas**: Fluid flex canvas filling all remaining viewport width. Incorporates zoom, pan, snapping toggles, and live dimensions.
- **Right Inspector Panel**: Fixed width `320px`. Contains collapsible accordion field groups for selected bays, shelves, facings, or inventory constraints.
- **Bottom Status Bar**: Fixed height `28px`. Displays canvas cursor coordinates (X, Y, Z in mm), snap grid interval (`50 mm`), active viewport scale (`1:20`), and error tally.

### Responsive Behavior & Screen Constraints
- **Desktop (>= 1440px)**: Default 3-column setup (Left Asset Drawer + Canvas + Right Inspector) fully expanded.
- **Compact Desktop / Tablet Landscape (1024px - 1439px)**: Inspector transitions to an overlay drawer; left asset tree defaults to narrow icon rail.
- **Mobile (< 1024px)**: Read-only inspection mode with a vertical stack; canvas editing is disabled in favor of planogram approval and compliance checklists.

## Elevation & Depth

This design system avoids multi-tiered drop shadow systems to preserve maximum visual clarity across data-heavy interfaces. Hierarchy is communicated through flat plane separation and hairline boundaries.

### Structural Boundaries
- All panels, toolbars, tables, and modal shells use a crisp `1px solid #E2E8F0` border.
- Floating overlay panels, canvas tooltips, context menus, and elevated dialogs utilize a single, subtle ambient shadow:
  `box-shadow: 0 4px 20px -2px rgba(15, 23, 42, 0.08), 0 0 0 1px rgba(15, 23, 42, 0.04);`

### Layer Stacking Tiers
- **Tier 0 (Canvas Surface)**: `#F8FAFC` with 50mm grid lines.
- **Tier 1 (Panels & Toolbars)**: Solid `#FFFFFF`, demarcated with `1px #E2E8F0` edge borders.
- **Tier 2 (Popovers, Dropdowns, Toolbars)**: `#FFFFFF` floating directly over the canvas, using the single elevation shadow.
- **Tier 3 (Modal Modifiers & Drawers)**: `#FFFFFF` with darkened backdrop scrim (`rgba(15, 23, 42, 0.35)` with `backdrop-filter: blur(2px)`).

## Shapes

The design system uses a compact, disciplined geometric shape language that reinforces architectural precision:

- **Inputs, Buttons, and Interactive Badges**: `6px` radius (`rounded-md`).
- **Cards, Accordion Containers, and Field Groups**: `10px` radius.
- **Modals, Floating Drawers, and Dialog Windows**: `12px` radius (`rounded-xl`).
- **Status Chips & Entity Pills**: Full pill radius (`9999px`).
- **CAD Fixtures, Shelf Bins, and Shelf Outlines**: Sharp `0px` radius to reflect authentic sheet-metal and wire retail shelving.

## Components

### Buttons
- **Primary**: Solid Indigo (`#4338CA`), white label, hover `#3730A3`, focus ring `2px #EEF2FF`. Height `32px` (compact) or `36px` (standard).
- **Secondary**: Surface `#FFFFFF`, border `1px #E2E8F0`, text `#0F172A`, hover `#F8FAFC`.
- **Ghost**: Transparent background, text `#475569`, hover background `#F1F5F9`.
- **Danger**: Solid Red (`#DC2626`), white label, hover `#B91C1C`.
- **Icon Buttons**: Fixed `32x32px` square with `16px` icon centered; hover `#F1F5F9`.

### Form Controls & Inputs
- **Text & Numeric Inputs**: Height `32px` (dense) to `36px`. Background `#FFFFFF`, border `1px #E2E8F0`, inner padding `0 10px`, typography `13px`. Focus border `#4338CA` with zero shadow.
- **Search Input**: Includes leading 16px search icon and trailing `⌘K` keyboard shortcut badge (`10px` font, background `#F1F5F9`, border `1px #CBD5E1`, border-radius `4px`).
- **Stepper Counters**: Integrated segmented pill `[ - | Value | + ]` using `JetBrains Mono` for value readout.
- **Segmented Controls**: Enclosed container in `#F1F5F9` with `4px` padding; active segment has `#FFFFFF` background, `1px #E2E8F0` border, and subtle text weight increase.

### Data Tables
- **Rows**: Fixed `40px` row height. Alternating rows remain white; hover state triggers `#F8FAFC`.
- **Headers**: Height `34px`, sticky, background `#F8FAFC`, uppercase `11px` typography, equipped with sort direction carets and column filter triggers.
- **Selection**: Custom `16x16px` checkboxes with `4px` border radius; selected row acquires `#EEF2FF` tint.

### Status Chips & Utility Tags
- **Status Chips**: Height `22px`, pill-shaped, `12px` font size with `500` weight, horizontal padding `8px`. Tinted backgrounds paired with darker foreground tones as specified in the color token system.
- **Utility / Metadata Tags**: Small rectangular tags (`4px` radius, height `18px`, `11px` text):
  - *Eligible*: `#ECFDF5` / `#059669`
  - *No image*: `#F1F5F9` / `#64748B`
  - *Size estimated*: `#FEF3C7` / `#D97706`
  - *Locked*: `#F1F5F9` / `#334155` with lock icon
  - *Lease*: `#EEF2FF` / `#4338CA`

### Metric & KPI Tiles
- Compact metric card with `10px` radius, `1px #E2E8F0` border, and `12px` inner padding.
- Displays label in `label-uppercase`, headline numeric value in `22px` Inter semibold (`tabular-nums`), followed by an inline trend badge (`+4.2%` green or `-1.8%` red) and an embedded `24px` high inline sparkline.

### Iconography
- Icons adhere strictly to the Lucide outline style with a uniform `1.5px` stroke width. Standard dimensions: `16x16px` for inline table and input controls; `20x20px` for top-level navigation rails.