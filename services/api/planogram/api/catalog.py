"""Products, product workbook template/export, and imports (spec 9, 11.3)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select

from .. import imports
from .. import models as m
from .. import services as svc
from ..db import unit_of_work
from ..engines.context import eligibility

router = APIRouter(prefix="/api")
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx(data: bytes, name: str) -> Response:
    return Response(data, media_type=XLSX, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/products")
def products() -> list[dict[str, Any]]:
    with unit_of_work() as s:
        stats = {}
        for st in s.scalars(select(m.SkuStoreStats)):
            stats.setdefault(st.product_id, st)
        cats = svc.load_categories(s)
        out = []
        for p in s.scalars(select(m.Product).order_by(m.Product.category_code, m.Product.brand, m.Product.name)):
            row = svc.row(p)
            st = stats.get(p.id)
            row.update({
                "category_name": cats.get(p.category_code, {}).get("name"),
                "department": cats.get(p.category_code, {}).get("department"),
                "units_per_day": st.units_per_day if st else 0.0,
                "eligibility": eligibility(row),
            })
            out.append(row)
        return out


@router.get("/catalog/template.xlsx")
def template() -> Response:
    with unit_of_work() as s:
        return _xlsx(imports.blank_template(s), "Product_Import_Template.xlsx")


@router.get("/catalog/export.xlsx")
def export() -> Response:
    with unit_of_work() as s:
        return _xlsx(imports.export_workbook(s), "Product_Catalogue.xlsx")


@router.get("/imports")
def import_runs() -> list[dict[str, Any]]:
    with unit_of_work() as s:
        q = select(m.ImportRun).order_by(m.ImportRun.created_at.desc())
        return [{"id": r.id, "filename": r.filename, "status": r.status, "created_at": r.created_at.isoformat(),
                 "counts": r.counts} for r in s.scalars(q)]


@router.post("/imports")
async def upload(file: UploadFile = File(...), images: UploadFile | None = File(None)) -> dict[str, Any]:
    if not (file.filename or "").lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(422, {"message": "upload the product workbook as .xlsx"})
    data = await file.read()
    zip_data = await images.read() if images is not None else None
    try:
        with unit_of_work() as s:
            run = imports.stage(s, file.filename or "upload.xlsx", data, zip_data)
            return {"id": run.id, "filename": run.filename, "status": run.status, "counts": run.counts, "rows": run.rows}
    except (KeyError, ValueError, OSError) as e:
        raise HTTPException(422, {"message": f"could not read the workbook: {e}"}) from e


@router.get("/imports/{run_id}")
def import_run(run_id: str) -> dict[str, Any]:
    with unit_of_work() as s:
        r = s.get(m.ImportRun, run_id)
        if r is None:
            raise HTTPException(404, {"message": "import not found"})
        return {"id": r.id, "filename": r.filename, "status": r.status, "counts": r.counts, "rows": r.rows}


@router.post("/imports/{run_id}/publish")
def publish(run_id: str) -> dict[str, Any]:
    with unit_of_work() as s:
        try:
            return imports.publish(s, run_id)
        except KeyError as e:
            raise HTTPException(404, {"message": "import not found"}) from e
