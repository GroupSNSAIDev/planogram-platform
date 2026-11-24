import os
import tempfile
from pathlib import Path

os.environ["PLANOGRAM_SEED"] = "csv"  # fictional catalogue: fast and deterministic
_tmp = Path(tempfile.mkdtemp())
os.environ["PLANOGRAM_DB"] = str(_tmp / "test.db")
os.environ["PLANOGRAM_MEDIA"] = str(_tmp / "media")  # never touch the dev server's pictures

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from planogram.main import app  # noqa: E402
from planogram.seed_loader import reset_and_load  # noqa: E402

GOLDEN = Path(__file__).resolve().parents[3] / "packages" / "contracts" / "golden" / "fit_cases.json"


@pytest.fixture()
def client():
    reset_and_load()
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def layout(client):
    return client.get("/api/stores/SMS-001/layout").json()["layout"]


def fixture_by_code(layout, code):
    return next(f for f in layout["fixtures"].values() if f["code"] == code)


def section_by_code(layout, code):
    return next(s for s in layout["sections"].values() if s["code"] == code)
