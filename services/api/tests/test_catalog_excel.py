"""Product workbook: template round trip, validation and import through the API."""
import io

from PIL import Image

from planogram.catalog_excel import build_workbook, gtin_check, normalise_gtin, parse_workbook

CATS = {"BRK": {"code": "BRK", "department": "Packaged food", "name": "Breakfast cereals", "temperature": "ambient"},
        "DAI": {"code": "DAI", "department": "Dairy & chilled", "name": "Milk", "temperature": "chilled"}}


def picture(w=300, h=400, colour=(200, 30, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), colour).save(buf, "PNG")
    return buf.getvalue()


def row(**kw):
    base = {"sku": "T1", "gtin": "8901058000290", "name": "Test Oats 500 g", "brand": "Testco", "category": "BRK",
            "width_mm": 150, "height_mm": 200, "depth_mm": 60, "weight_g": 520, "temperature": "ambient",
            "dims_source": "measured", "dims_verified": True, "liquid": False, "fragile": False, "age_restricted": False,
            "hazardous": False, "safety_reviewed": True, "price": 99, "units_per_day": 3}
    return {**base, **kw}


def test_gtin_rules():
    assert gtin_check("8901058000290")
    assert not gtin_check("8901058000291")
    assert normalise_gtin("12345670") == "0000012345670"      # GTIN-8 padded to 13 digits
    assert normalise_gtin("8901058000290.0") == "8901058000290"  # Excel number formatting
    assert normalise_gtin("123") is None


def test_round_trip_with_embedded_picture_and_errors():
    data = build_workbook(
        [row(), row(sku="T2", gtin="8901058000291"), row(sku="T3", gtin="5000108478119", category="DAI", temperature="ambient")],
        list(CATS.values()), lambda p: picture() if p["sku"] == "T1" else None)
    rows = parse_workbook(data, CATS)
    assert len(rows) == 3
    good, bad_gtin, temp = rows
    assert good.ok and good.image is not None and good.image_source == "embedded picture"
    assert not bad_gtin.ok and any(i["code"] == "P-002" for i in bad_gtin.issues)
    assert any(i["code"] == "P-006" and i["severity"] == "warning" for i in temp.issues)
    assert any(i["code"] == "I-001" for i in temp.issues)  # no picture -> placeholder warning


def test_upload_and_publish_through_the_api(client):
    data = build_workbook([row(sku="NEW-1", name="Brand New Muesli 400 g")], list(CATS.values()), lambda p: picture())
    r = client.post("/api/imports", files={"file": ("products.xlsx", data, "application/octet-stream")})
    assert r.status_code == 200, r.text
    run = r.json()
    assert run["counts"]["ok"] == 1 and run["counts"]["new"] == 1 and run["counts"]["images"] == 1
    r = client.post(f"/api/imports/{run['id']}/publish")
    assert r.json()["published"] == 1
    prod = next(p for p in client.get("/api/products").json() if p["sku"] == "NEW-1")
    assert prod["image"] == "products/NEW-1.jpg" and prod["has_image"]
    assert client.get(f"/api/media/{prod['image']}").status_code == 200
    # re-importing the same file changes nothing
    r = client.post("/api/imports", files={"file": ("products.xlsx", data, "application/octet-stream")})
    assert r.json()["counts"]["changed"] + r.json()["counts"]["unchanged"] == 1


def test_template_downloads(client):
    r = client.get("/api/catalog/template.xlsx")
    assert r.status_code == 200 and r.content[:2] == b"PK"
    r = client.get("/api/catalog/export.xlsx")
    assert r.status_code == 200 and r.content[:2] == b"PK"
