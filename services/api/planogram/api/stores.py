"""Stores: create (empty or generated hypermarket layout), export and import design files, delete."""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from .. import models as m
from .. import services as svc
from ..db import unit_of_work
from ..engines.store_generator import generate
from .. import exports
from ..layout_io import LayoutFileError, delete_store, export_layout, import_layout

router = APIRouter(prefix="/api")


class NewStore(BaseModel):
    code: str = Field(min_length=2, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=120)
    width_m: float = Field(ge=5, le=300)
    depth_m: float = Field(ge=5, le=300)
    layout: str = Field(default="generated", pattern="^(generated|empty)$")


@router.post("/stores")
def create_store(body: NewStore) -> dict[str, Any]:
    w, d = int(body.width_m * 1000), int(body.depth_m * 1000)
    try:
        if body.layout == "generated":
            design = generate(w, d, body.code.upper(), body.name)
        else:
            design = {"format": "planogram-layout", "version": 1,
                      "store": {"code": body.code.upper(), "name": body.name, "format": "custom", "width_mm": w, "depth_mm": d},
                      "zones": [], "landmarks": [{"kind": "entrance", "name": "Entrance", "rect": [2000, d - 200, 4000, 200]}],
                      "fixtures": [], "sections": []}
        with unit_of_work() as s:
            counts = import_layout(s, design)
        return {"code": body.code.upper(), **counts}
    except (ValueError, LayoutFileError) as e:
        raise HTTPException(422, {"message": str(e)}) from e


class AutofillScope(BaseModel):
    fixture_code: str | None = None
    only_empty: bool = True


@router.post("/stores/{code}/autofill")
def autofill_store(code: str, body: AutofillScope) -> dict[str, Any]:
    with unit_of_work() as s:
        try:
            return svc.autofill_many(s, code, body.fixture_code, body.only_empty)
        except svc.NotFound as e:
            raise HTTPException(404, {"message": str(e)}) from e


@router.get("/stores/{code}/sections")
def store_sections(code: str) -> list[dict[str, Any]]:
    with unit_of_work() as s:
        try:
            return svc.section_list(s, code)
        except svc.NotFound as e:
            raise HTTPException(404, {"message": str(e)}) from e


def _file(data: bytes, media: str, name: str) -> Response:
    return Response(data, media_type=media, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/stores/{code}/exports/floor.pdf")
def export_floor_pdf(code: str) -> Response:
    with unit_of_work() as s:
        return _file(exports.floor_pdf(s, code), "application/pdf", f"{code}_floor_plan.pdf")


@router.get("/stores/{code}/exports/planograms.pdf")
def export_planograms_pdf(code: str, fixture: str | None = None, section: str | None = None) -> Response:
    with unit_of_work() as s:
        suffix = f"_{fixture}" if fixture else "_section" if section else ""
        return _file(exports.planogram_pdf(s, code, fixture, section), "application/pdf", f"{code}{suffix}_planograms.pdf")


@router.get("/stores/{code}/exports/execution.xlsx")
def export_execution_xlsx(code: str, fixture: str | None = None, section: str | None = None) -> Response:
    with unit_of_work() as s:
        suffix = f"_{fixture}" if fixture else "_section" if section else ""
        return _file(exports.execution_xlsx(s, code, fixture, section),
                     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", f"{code}{suffix}_execution.xlsx")


@router.get("/stores/{code}/layout/export")
def export(code: str, planograms: bool = True) -> Response:
    with unit_of_work() as s:
        try:
            store = svc.get_store(s, code)
        except svc.NotFound as e:
            raise HTTPException(404, {"message": str(e)}) from e
        data = export_layout(s, store, planograms)
    body = json.dumps(data, ensure_ascii=False, indent=1)
    return Response(body, media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{code}_design.planogram.json"'})


@router.post("/stores/import")
async def import_design(file: UploadFile = File(...), code: str | None = Form(None), name: str | None = Form(None),
                        replace: bool = Form(False)) -> dict[str, Any]:
    try:
        data = json.loads(await file.read())
    except json.JSONDecodeError as e:
        raise HTTPException(422, {"message": "the file is not a design file (.planogram.json)"}) from e
    try:
        with unit_of_work() as s:
            counts = import_layout(s, data, code.upper() if code else None, name, replace)
        return {"code": (code or data["store"]["code"]).upper(), **counts}
    except (LayoutFileError, KeyError, ValueError) as e:
        raise HTTPException(422, {"message": str(e)}) from e


@router.delete("/stores/{code}")
def remove_store(code: str) -> dict[str, str]:
    with unit_of_work() as s:
        store = s.scalar(select(m.Store).where(m.Store.code == code))
        if store is None:
            raise HTTPException(404, {"message": f"store {code} not found"})
        if s.scalar(select(m.Store).where(m.Store.code != code).limit(1)) is None:
            raise HTTPException(422, {"message": "cannot delete the last store"})
        delete_store(s, store)
    return {"deleted": code}
