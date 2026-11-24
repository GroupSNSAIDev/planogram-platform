"""Golden geometry cases, shared with the TypeScript tests (ADR-13)."""
import json

import pytest

from planogram.engines.geometry import check_surface, clear_heights, eye_band

from .conftest import GOLDEN

CASES = json.loads(GOLDEN.read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES["surface_cases"], ids=lambda c: c["name"])
def test_surface_case(case):
    positions = [{"locked": False, "locked_x_mm": None, **p} for p in case["positions"]]
    result = check_surface(case["surface"], case["clear_height_mm"], case["has_door"],
                           case["fixture_temperature"], positions, CASES["products"])
    assert result["x_mm"] == case["expected"]["x_mm"]
    assert result["used_width_mm"] == case["expected"]["used_width_mm"]
    assert sorted(f"{i['code']}:{i['target']}" for i in result["issues"]) == sorted(case["expected"]["issues"])


@pytest.mark.parametrize("case", CASES["clear_height_cases"], ids=lambda c: c["name"])
def test_clear_heights(case):
    assert clear_heights(case["heights"], case["bay_height_mm"]) == case["expected"]


@pytest.mark.parametrize("case", CASES["eye_band_cases"], ids=lambda c: str(c["height_mm"]))
def test_eye_band(case):
    assert eye_band(case["height_mm"]) == case["band"]
