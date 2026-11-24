"""Tables (spec section 7.2, POC subset: no tenant_id or layout revisions yet).
Lengths in whole millimetres, weights in grams."""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class Store(Base):
    __tablename__ = "store"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    code: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    format: Mapped[str | None] = mapped_column(String)
    timezone: Mapped[str] = mapped_column(String, default="Asia/Kolkata")
    width_mm: Mapped[int] = mapped_column(Integer)
    depth_mm: Mapped[int] = mapped_column(Integer)
    layout_version: Mapped[int] = mapped_column(Integer, default=1)


class Zone(Base):
    __tablename__ = "zone"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    store_id: Mapped[str] = mapped_column(ForeignKey("store.id"))
    code: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    rect: Mapped[list] = mapped_column(JSON)  # [x, y, w, h]


class Landmark(Base):
    __tablename__ = "landmark"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    store_id: Mapped[str] = mapped_column(ForeignKey("store.id"))
    kind: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    rect: Mapped[list] = mapped_column(JSON)


class FixtureTemplate(Base):
    __tablename__ = "fixture_template"
    code: Mapped[str] = mapped_column(String, primary_key=True)
    kind: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    defaults: Mapped[dict] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(Integer, default=1)


class Category(Base):
    __tablename__ = "category"
    code: Mapped[str] = mapped_column(String, primary_key=True)
    department: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    temperature: Mapped[str] = mapped_column(String)


class Fixture(Base):
    __tablename__ = "fixture"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    store_id: Mapped[str] = mapped_column(ForeignKey("store.id"))
    code: Mapped[str] = mapped_column(String)
    template_code: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)
    x_mm: Mapped[int] = mapped_column(Integer)
    y_mm: Mapped[int] = mapped_column(Integer)
    rotation_deg: Mapped[int] = mapped_column(Integer, default=0)
    footprint_w_mm: Mapped[int] = mapped_column(Integer)
    footprint_d_mm: Mapped[int] = mapped_column(Integer)
    temperature: Mapped[str] = mapped_column(String, default="ambient")
    faces: Mapped[str | None] = mapped_column(String)
    note: Mapped[str | None] = mapped_column(String)


class Bay(Base):
    __tablename__ = "bay"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    fixture_id: Mapped[str] = mapped_column(ForeignKey("fixture.id", ondelete="CASCADE"))
    side: Mapped[str] = mapped_column(String)
    idx: Mapped[int] = mapped_column(Integer)
    width_mm: Mapped[int] = mapped_column(Integer)
    height_mm: Mapped[int] = mapped_column(Integer)
    depth_mm: Mapped[int] = mapped_column(Integer)
    has_door: Mapped[bool] = mapped_column(Boolean, default=False)


class Surface(Base):
    __tablename__ = "surface"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    bay_id: Mapped[str] = mapped_column(ForeignKey("bay.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String)
    idx: Mapped[int] = mapped_column(Integer)
    height_from_floor_mm: Mapped[int] = mapped_column(Integer)
    width_mm: Mapped[int] = mapped_column(Integer)
    depth_mm: Mapped[int] = mapped_column(Integer)
    max_load_g: Mapped[int | None] = mapped_column(Integer)
    notch_pitch_mm: Mapped[int] = mapped_column(Integer, default=25)
    grid_cols: Mapped[int | None] = mapped_column(Integer)
    grid_rows: Mapped[int | None] = mapped_column(Integer)


class Section(Base):
    __tablename__ = "section"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    fixture_id: Mapped[str] = mapped_column(ForeignKey("fixture.id", ondelete="CASCADE"))
    side: Mapped[str] = mapped_column(String)
    bay_from: Mapped[int] = mapped_column(Integer)
    bay_to: Mapped[int] = mapped_column(Integer)
    code: Mapped[str] = mapped_column(String, index=True)   # unique within a store (checked by the layout engine)
    category_code: Mapped[str] = mapped_column(ForeignKey("category.code"))
    image_policy: Mapped[str] = mapped_column(String, default="placeholder_ok")
    assignment_locked: Mapped[bool] = mapped_column(Boolean, default=False)


class Product(Base):
    """Product identity plus its current facts (spec splits these into product + product_revision)."""
    __tablename__ = "product"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    sku: Mapped[str] = mapped_column(String, unique=True)
    gtin: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    brand: Mapped[str] = mapped_column(String)
    category_code: Mapped[str] = mapped_column(ForeignKey("category.code"))
    width_mm: Mapped[int | None] = mapped_column(Integer)
    height_mm: Mapped[int | None] = mapped_column(Integer)
    depth_mm: Mapped[int | None] = mapped_column(Integer)
    weight_g: Mapped[int | None] = mapped_column(Integer)
    case_pack: Mapped[int | None] = mapped_column(Integer)
    temperature: Mapped[str] = mapped_column(String)
    dims_source: Mapped[str] = mapped_column(String)
    dims_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    safety_reviewed: Mapped[bool] = mapped_column(Boolean, default=True)
    age_restricted: Mapped[bool] = mapped_column(Boolean, default=False)
    hazardous: Mapped[bool] = mapped_column(Boolean, default=False)
    can_stack: Mapped[bool] = mapped_column(Boolean, default=False)
    max_stack: Mapped[int] = mapped_column(Integer, default=1)
    has_image: Mapped[bool] = mapped_column(Boolean, default=True)
    image: Mapped[str | None] = mapped_column(String)          # path under media/, e.g. products/SKU123.jpg
    colour: Mapped[str] = mapped_column(String, default="#CBD5E1")
    price: Mapped[float] = mapped_column(Float, default=0.0)
    pack_size: Mapped[str | None] = mapped_column(String)
    liquid: Mapped[bool] = mapped_column(Boolean, default=False)
    fragile: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String, default="active")
    source: Mapped[str | None] = mapped_column(String)          # import file, or open-data source for the demo
    quality_score: Mapped[int | None] = mapped_column(Integer)


class SkuStoreStats(Base):
    """Nightly aggregates used by auto-fill (synthetic in the POC)."""
    __tablename__ = "sku_store_stats"
    store_id: Mapped[str] = mapped_column(ForeignKey("store.id"), primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("product.id"), primary_key=True)
    units_per_day: Mapped[float] = mapped_column(Float)
    revenue_per_day: Mapped[float] = mapped_column(Float)
    margin_per_day: Mapped[float] = mapped_column(Float)


class Planogram(Base):
    """One draft planogram per section in the POC (versions and approval come later)."""
    __tablename__ = "planogram"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    section_id: Mapped[str] = mapped_column(ForeignKey("section.id", ondelete="CASCADE"), unique=True)
    status: Mapped[str] = mapped_column(String, default="draft")
    row_version: Mapped[int] = mapped_column(Integer, default=1)
    score: Mapped[float | None] = mapped_column(Float)
    hard_breaks: Mapped[int | None] = mapped_column(Integer)


class Position(Base):
    __tablename__ = "position"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    planogram_id: Mapped[str] = mapped_column(ForeignKey("planogram.id", ondelete="CASCADE"), index=True)
    surface_id: Mapped[str] = mapped_column(ForeignKey("surface.id"))
    product_id: Mapped[str] = mapped_column(ForeignKey("product.id"))
    seq: Mapped[int] = mapped_column(Integer)
    x_mm: Mapped[int] = mapped_column(Integer)
    facings_wide: Mapped[int] = mapped_column(Integer, default=1)
    facings_high: Mapped[int] = mapped_column(Integer, default=1)
    facings_deep: Mapped[int] = mapped_column(Integer, default=1)
    placed_by: Mapped[str] = mapped_column(String)
    reason: Mapped[str | None] = mapped_column(Text)
    rule_ids: Mapped[list] = mapped_column(JSON, default=list)
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    locked_x_mm: Mapped[int | None] = mapped_column(Integer)


class ImportRun(Base):
    """A product workbook upload, staged for review before publishing (spec 9, FR-01/FR-05)."""
    __tablename__ = "import_run"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    filename: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="validated")   # validated | published
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    counts: Mapped[dict] = mapped_column(JSON, default=dict)
    rows: Mapped[list] = mapped_column(JSON, default=list)


class CommandLog(Base):
    """Append-only audit of every applied command, with its inverse."""
    __tablename__ = "command_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String)      # layout | planogram
    target_id: Mapped[str] = mapped_column(String)  # store id or planogram id
    command: Mapped[dict] = mapped_column(JSON)
    inverse: Mapped[list] = mapped_column(JSON)
    actor: Mapped[str] = mapped_column(String, default="planner:demo")
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
