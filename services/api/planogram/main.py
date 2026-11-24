"""FastAPI app factory. Run with:  fastapi dev planogram/main.py"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, select

from . import models as m
from .api.catalog import router as catalog_router
from .api.routes import router
from .api.stores import router as stores_router
from .imports import MEDIA_DIR
from .db import Base, engine, unit_of_work
from .seed_loader import reset_and_load


@asynccontextmanager
async def lifespan(_: FastAPI):
    # First start: create tables and load the sample store so the demo works out of the box.
    insp = inspect(engine)
    stale = insp.has_table("product") and "image" not in {c["name"] for c in insp.get_columns("product")}
    if not insp.has_table("store") or stale or not insp.has_table("import_run"):
        reset_and_load()  # first start, or the schema changed: rebuild the demo database
    else:
        with unit_of_work() as s:
            if s.scalar(select(m.Store).limit(1)) is None:
                reset_and_load()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Planogram Platform API (POC)", version="0.1.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                       allow_methods=["*"], allow_headers=["*"])
    app.include_router(router)
    app.include_router(catalog_router)
    app.include_router(stores_router)
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/api/media", StaticFiles(directory=MEDIA_DIR), name="media")
    return app


app = create_app()
