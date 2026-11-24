"""REST API (spec section 18, POC subset). Every write is a command batch in one transaction."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from .. import models as m
from .. import services as svc
from ..db import unit_of_work
from ..engines.layout_doc import CommandError
from ..engines.rules import rules_catalogue
from ..seed_loader import reset_and_load

router = APIRouter(prefix="/api")


class CommandBatch(BaseModel):
    commands: list[dict[str, Any]] = Field(min_length=1, max_length=500)
    expected_version: int | None = None


def _errors(fn):
    """Map domain errors to HTTP problems."""
    try:
        return fn()
    except CommandError as e:
        raise HTTPException(422, {"message": e.message, "index": e.index}) from e
    except svc.NotFound as e:
        raise HTTPException(404, {"message": str(e)}) from e
    except svc.Conflict as e:
        raise HTTPException(409, {"message": str(e)}) from e


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/stores")
def stores() -> list[dict[str, Any]]:
    with unit_of_work() as s:
        out = []
        for st in s.scalars(select(m.Store)):
            n_fx = s.scalar(select(func.count()).select_from(m.Fixture).where(m.Fixture.store_id == st.id))
            n_sec = s.scalar(select(func.count()).select_from(m.Section).join(m.Fixture).where(m.Fixture.store_id == st.id))
            out.append({**svc.row(st), "fixtures": n_fx, "sections": n_sec})
        return out


@router.get("/stores/{code}/layout")
def layout(code: str) -> dict[str, Any]:
    with unit_of_work() as s:
        return _errors(lambda: svc.layout_payload(s, code))


@router.post("/stores/{code}/layout/commands")
def layout_commands(code: str, batch: CommandBatch) -> dict[str, Any]:
    def run():
        with unit_of_work() as s:
            return svc.apply_layout(s, code, batch.commands, batch.expected_version)
    return _errors(run)


@router.get("/fixture-templates")
def fixture_templates() -> list[dict[str, Any]]:
    with unit_of_work() as s:
        usage = dict(s.execute(select(m.Fixture.template_code, func.count()).group_by(m.Fixture.template_code)).all())
        return [{"code": t.code, "kind": t.kind, "name": t.name, "version": t.version, "used_by": usage.get(t.code, 0),
                 **{"defaults": t.defaults}} for t in s.scalars(select(m.FixtureTemplate))]


@router.get("/categories")
def categories() -> list[dict[str, Any]]:
    with unit_of_work() as s:
        return list(svc.load_categories(s).values())


@router.get("/sections/{code}/planogram")
def section_planogram(code: str) -> dict[str, Any]:
    with unit_of_work() as s:
        return _errors(lambda: svc.planogram_payload(s, code))


@router.post("/planograms/{planogram_id}/commands")
def planogram_commands(planogram_id: str, batch: CommandBatch) -> dict[str, Any]:
    def run():
        with unit_of_work() as s:
            return svc.apply_planogram(s, planogram_id, batch.commands, batch.expected_version)
    return _errors(run)


@router.post("/planograms/{planogram_id}/autofill")
def planogram_autofill(planogram_id: str) -> dict[str, Any]:
    with unit_of_work() as s:
        return _errors(lambda: svc.run_autofill(s, planogram_id))


@router.post("/planograms/{planogram_id}/validate")
def planogram_validate(planogram_id: str) -> dict[str, Any]:
    with unit_of_work() as s:
        return _errors(lambda: svc.validate(s, planogram_id))


@router.get("/rules")
def rules() -> dict[str, Any]:
    return rules_catalogue()


@router.post("/demo/reset")
def demo_reset() -> dict[str, int]:
    return reset_and_load()
