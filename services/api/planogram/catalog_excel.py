"""Product Excel template: build it (blank or filled, with pictures) and read it back with validation.

The template is what we share with stores and suppliers (spec 9.1, Appendix C). One row per product.
Pictures can be given three ways (first found wins):
  1. a picture inserted over the row's Image cell (Insert > Pictures > Place over cells),
  2. a file name in "Image file" that is inside the images ZIP uploaded with the workbook,
  3. a web address in "Image URL" (fetched once at import).
Validation follows spec 9.3 (P-001 ... P-010, I-001); errors block a row, warnings do not.
"""
from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field
from typing import Any, Callable

from openpyxl import Workbook, load_workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from PIL import Image as PILImage

# (key, header, width, required, help)
COLUMNS: list[tuple[str, str, int, bool, str]] = [
    ("image", "Image", 14, False, "Insert the front pack photo over this cell (or use Image file / Image URL)"),
    ("sku", "SKU", 13, True, "Your article number. Unique."),
    ("gtin", "GTIN / EAN", 16, True, "Barcode (8, 12, 13 or 14 digits). Check digit is verified."),
    ("name", "Product name", 34, True, "Name as printed, with pack size, e.g. 'Corn Flakes 475 g'"),
    ("brand", "Brand", 16, True, ""),
    ("category", "Category code", 11, True, "Code from the Categories sheet, e.g. BRK"),
    ("width_mm", "Width mm", 10, True, "Seen from the front, left to right (GS1)"),
    ("height_mm", "Height mm", 10, True, "Base to top (GS1)"),
    ("depth_mm", "Depth mm", 10, True, "Front to back (GS1)"),
    ("weight_g", "Weight g", 10, True, "Gross weight of one unit"),
    ("pack_size", "Pack size", 11, False, "e.g. 500 g, 1 L"),
    ("case_pack", "Case pack", 9, False, "Units per case"),
    ("temperature", "Temperature", 12, True, "ambient, chilled or frozen"),
    ("dims_source", "Size source", 12, True, "measured, supplier, gs1, sap or estimated"),
    ("dims_verified", "Sizes verified", 10, True, "yes / no"),
    ("can_stack", "Can stack", 9, False, "yes / no"),
    ("max_stack", "Max stack", 9, False, "How many high"),
    ("liquid", "Liquid", 8, True, "yes / no"),
    ("fragile", "Fragile", 8, True, "yes / no"),
    ("age_restricted", "Age restricted", 10, True, "yes / no"),
    ("hazardous", "Hazardous", 10, True, "yes / no"),
    ("safety_reviewed", "Safety reviewed", 10, True, "yes when the four safety flags have been checked"),
    ("price", "Price ₹", 10, False, "Selling price"),
    ("units_per_day", "Units / day", 10, False, "Average units sold per day in this store (for facings)"),
    ("image_file", "Image file", 22, False, "File name inside the images ZIP, e.g. 8901058000290_front.jpg"),
    ("image_url", "Image URL", 30, False, "Web address of the front image"),
    ("status", "Status", 9, False, "active or delisted"),
]
KEYS = [c[0] for c in COLUMNS]
HEADERS = {c[1].lower(): c[0] for c in COLUMNS}
YES_NO = {"dims_verified", "can_stack", "liquid", "fragile", "age_restricted", "hazardous", "safety_reviewed"}
INTS = {"width_mm", "height_mm", "depth_mm", "weight_g", "case_pack", "max_stack"}
FLOATS = {"price", "units_per_day"}
ROW_H = 62          # points; thumbnails are drawn into this height
THUMB_PX = 76

INK, INDIGO, LINE = "0F172A", "4338CA", "E2E8F0"
thin = Side(style="thin", color=LINE)


def gtin_check(code: str) -> bool:
    digits = [int(c) for c in code]
    body, check = digits[:-1], digits[-1]
    total = sum(d * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body)))
    return (10 - total % 10) % 10 == check


def normalise_gtin(value: Any) -> str | None:
    s = re.sub(r"\D", "", str(value or "").split(".")[0])
    if len(s) not in (8, 12, 13, 14):
        return None
    return s.zfill(13) if len(s) < 13 else s


# ----------------------------------------------------------------------------- build

def build_workbook(products: list[dict[str, Any]], categories: list[dict[str, Any]],
                   image_bytes: Callable[[dict[str, Any]], bytes | None] | None = None,
                   title: str = "Product catalogue") -> bytes:
    wb = Workbook()
    _instructions(wb.active, title)
    ws = wb.create_sheet("Products")
    _products_sheet(ws, products, image_bytes)
    cs = wb.create_sheet("Categories")
    cs.append(["Code", "Department", "Category", "Temperature"])
    for c in sorted(categories, key=lambda c: (c["department"], c["name"])):
        cs.append([c["code"], c["department"], c["name"], c["temperature"]])
    _style_header(cs, 4)
    for col, w in zip("ABCD", (10, 22, 32, 13)):
        cs.column_dimensions[col].width = w
    # dropdowns
    last = max(len(products) + 2, 500)
    cat_col = get_column_letter(KEYS.index("category") + 1)
    dv = DataValidation(type="list", formula1=f"=Categories!$A$2:$A${len(categories) + 1}", allow_blank=False)
    dv.add(f"{cat_col}2:{cat_col}{last}")
    ws.add_data_validation(dv)
    for key, options in (("temperature", "ambient,chilled,frozen"), ("dims_source", "measured,supplier,gs1,sap,estimated"),
                         ("status", "active,delisted")):
        col = get_column_letter(KEYS.index(key) + 1)
        v = DataValidation(type="list", formula1=f'"{options}"', allow_blank=True)
        v.add(f"{col}2:{col}{last}")
        ws.add_data_validation(v)
    yn = DataValidation(type="list", formula1='"yes,no"', allow_blank=True)
    for key in YES_NO:
        col = get_column_letter(KEYS.index(key) + 1)
        yn.add(f"{col}2:{col}{last}")
    ws.add_data_validation(yn)
    wb.active = 1
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _style_header(ws, n: int) -> None:
    for i in range(1, n + 1):
        c = ws.cell(row=1, column=i)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=INDIGO)
        c.alignment = Alignment(vertical="center", wrap_text=True)
        c.border = Border(bottom=thin)
    ws.row_dimensions[1].height = 32
    ws.freeze_panes = "A2"


def _products_sheet(ws, products, image_bytes) -> None:
    for i, (_, header, width, required, _help) in enumerate(COLUMNS, start=1):
        ws.cell(row=1, column=i, value=header + (" *" if required else ""))
        ws.column_dimensions[get_column_letter(i)].width = width
    _style_header(ws, len(COLUMNS))
    ws.freeze_panes = "C2"
    for r, p in enumerate(products, start=2):
        for i, key in enumerate(KEYS, start=1):
            if key == "image":
                continue
            v = p.get(key)
            if key in YES_NO:
                v = "yes" if v else "no"
            ws.cell(row=r, column=i, value=v).alignment = Alignment(vertical="center", wrap_text=key == "name")
        ws.row_dimensions[r].height = ROW_H
        data = image_bytes(p) if image_bytes else None
        if data:
            try:
                im = PILImage.open(io.BytesIO(data)).convert("RGB")
                im.thumbnail((600, 600))           # keep a usable picture inside the file; it is shown small in the cell
                out = io.BytesIO()
                im.save(out, "JPEG", quality=85)
                xl = XLImage(io.BytesIO(out.getvalue()))
                scale = THUMB_PX / max(im.width, im.height)
                xl.width, xl.height = int(im.width * scale), int(im.height * scale)
                ws.add_image(xl, f"A{r}")
            except Exception:  # noqa: BLE001 - a broken image should not stop the export
                pass


def _instructions(ws, title: str) -> None:
    ws.title = "Instructions"
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 90
    ws["A1"] = f"Planogram platform · {title}"
    ws["A1"].font = Font(bold=True, size=16, color=INK)
    lines = [
        ("How to use", "Fill one row per product on the Products sheet, then upload this file on the Products & imports page. "
                       "Rows with errors are listed and not imported; fix them and upload again (re-imports only change what changed)."),
        ("Sizes", "Millimetres, as seen from the front of the pack (GS1 default front): width left to right, height base to top, "
                  "depth front to back. Wrong sizes make every planogram wrong, so measure the top sellers if you can."),
        ("Pictures", "Front pack photo on a plain background, at least 1,000 px on the long side. Either insert the picture over the "
                     "Image cell of the row (Insert > Pictures > Place over cells), or put the file name in 'Image file' and upload the "
                     "photos as a ZIP with the workbook, or give a web address in 'Image URL'. File names like <GTIN>_front.jpg are best."),
        ("Safety", "Answer every safety column (liquid, fragile, age restricted, hazardous) and set 'Safety reviewed' to yes. "
                   "Blank is not 'no': products without reviewed safety flags cannot be placed."),
        ("Required columns", "Marked with * in the header row."),
        ("Categories", "Use a code from the Categories sheet. The temperature must match the category (chilled, frozen or ambient)."),
    ]
    for i, (k, v) in enumerate(lines, start=3):
        ws.cell(row=i, column=1, value=k).font = Font(bold=True, color=INDIGO)
        c = ws.cell(row=i, column=2, value=v)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[i].height = 48
    r = len(lines) + 4
    ws.cell(row=r, column=1, value="Column").font = Font(bold=True)
    ws.cell(row=r, column=2, value="Meaning").font = Font(bold=True)
    for k, (_, header, _, required, help_) in enumerate(COLUMNS, start=r + 1):
        ws.cell(row=k, column=1, value=header + (" *" if required else ""))
        ws.cell(row=k, column=2, value=help_)


# ----------------------------------------------------------------------------- read

@dataclass
class ImportRow:
    row: int
    data: dict[str, Any]
    image: bytes | None = None
    image_source: str | None = None
    issues: list[dict[str, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(i["severity"] == "error" for i in self.issues)

    def add(self, code: str, severity: str, message: str) -> None:
        self.issues.append({"code": code, "severity": severity, "message": message})


def _yes(v: Any) -> bool | None:
    s = str(v).strip().lower() if v is not None else ""
    if s in ("yes", "y", "true", "1"):
        return True
    if s in ("no", "n", "false", "0"):
        return False
    return None


def parse_workbook(data: bytes, categories: dict[str, dict[str, Any]], images_zip: bytes | None = None,
                   fetch_url: Callable[[str], bytes | None] | None = None) -> list[ImportRow]:
    wb = load_workbook(io.BytesIO(data))
    ws = wb["Products"] if "Products" in wb.sheetnames else wb.worksheets[0]
    header = [str(c.value or "").replace("*", "").strip().lower() for c in ws[1]]
    col_key = {i: HEADERS.get(h) for i, h in enumerate(header)}
    pictures: dict[int, bytes] = {}
    for img in getattr(ws, "_images", []):
        try:
            pictures[img.anchor._from.row + 1] = img._data()
        except Exception:  # noqa: BLE001
            continue
    zip_files: dict[str, bytes] = {}
    if images_zip:
        with zipfile.ZipFile(io.BytesIO(images_zip)) as z:
            for n in z.namelist():
                if not n.endswith("/"):
                    zip_files[n.rsplit("/", 1)[-1].lower()] = z.read(n)

    rows: list[ImportRow] = []
    seen_sku: dict[str, int] = {}
    seen_gtin: dict[str, int] = {}
    for r_idx, cells in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        raw = {col_key[i]: v for i, v in enumerate(cells) if i in col_key and col_key[i]}
        if not any(v not in (None, "") for k, v in raw.items() if k != "image"):
            continue
        row = ImportRow(row=r_idx, data={})
        d = row.data
        for k in KEYS:
            v = raw.get(k)
            if isinstance(v, str):
                v = v.strip()
            if k in INTS:
                try:
                    v = int(round(float(v))) if v not in (None, "") else None
                except (TypeError, ValueError):
                    row.add("P-003", "error", f"{k} must be a number")
                    v = None
            elif k in FLOATS:
                try:
                    v = float(v) if v not in (None, "") else None
                except (TypeError, ValueError):
                    v = None
            elif k in YES_NO:
                v = _yes(v)
            d[k] = v
        d["sku"] = str(d["sku"] or "").split(".")[0]
        # P-001 SKU
        if not d["sku"]:
            row.add("P-001", "error", "SKU is missing")
        elif d["sku"] in seen_sku:
            row.add("P-001", "error", f"SKU {d['sku']} repeats row {seen_sku[d['sku']]}")
        else:
            seen_sku[d["sku"]] = r_idx
        # P-002 GTIN
        g = normalise_gtin(raw.get("gtin"))
        if not g:
            row.add("P-002", "error", "GTIN must have 8, 12, 13 or 14 digits")
        elif not gtin_check(g):
            row.add("P-002", "error", f"GTIN {g} fails its check digit")
        elif g in seen_gtin:
            row.add("P-008", "warning", f"same GTIN as row {seen_gtin[g]} (possible duplicate)")
        if g:
            seen_gtin.setdefault(g, r_idx)
        d["gtin"] = g or str(raw.get("gtin") or "")
        for k in ("name", "brand"):
            if not d[k]:
                row.add("P-001", "error", f"{k} is missing")
        # category and temperature (P-006)
        cat = categories.get(str(d["category"] or "").upper())
        if not cat:
            row.add("P-006", "error", f"unknown category {d['category']!r}")
        else:
            d["category"] = cat["code"]
        d["temperature"] = (d["temperature"] or (cat["temperature"] if cat else "") or "").lower()
        if d["temperature"] not in ("ambient", "chilled", "frozen"):
            row.add("P-006", "error", "temperature must be ambient, chilled or frozen")
        elif cat and cat["temperature"] != d["temperature"]:
            row.add("P-006", "warning", f"temperature {d['temperature']} differs from category ({cat['temperature']})")
        # P-003 / P-004 sizes
        for k in ("width_mm", "height_mm", "depth_mm"):
            v = d[k]
            if v is None:
                row.add("P-003", "error", f"{k} is missing")
            elif not 5 <= v <= 1500:
                row.add("P-004", "warning", f"{k} {v} mm is outside 5-1,500 mm")
        if d["weight_g"] is None:
            row.add("P-003", "error", "weight_g is missing")
        elif all(d[k] for k in ("width_mm", "height_mm", "depth_mm")):
            density = d["weight_g"] / (d["width_mm"] * d["height_mm"] * d["depth_mm"] / 1000)
            if not 0.02 <= density <= 3:
                row.add("P-005", "warning", f"weight vs volume gives {density:.2f} g/cm³")
        d["dims_source"] = (d["dims_source"] or "estimated").lower()
        if d["dims_source"] not in ("measured", "supplier", "gs1", "sap", "estimated"):
            row.add("P-003", "error", "size source must be measured, supplier, gs1, sap or estimated")
        if d["dims_verified"] is None:
            d["dims_verified"] = d["dims_source"] != "estimated"
        if d["dims_source"] == "estimated" and not d["dims_verified"]:
            row.add("P-010", "warning", "sizes are estimated: placement allowed in drafts only")
        # P-009 safety flags
        missing = [k for k in ("liquid", "fragile", "age_restricted", "hazardous") if d[k] is None]
        if missing:
            row.add("P-009", "error", f"answer the safety flags: {', '.join(missing)}")
            d["safety_reviewed"] = False
        elif d["safety_reviewed"] is None:
            d["safety_reviewed"] = True
        d["can_stack"] = bool(d["can_stack"])
        d["max_stack"] = d["max_stack"] or 1
        d["case_pack"] = d["case_pack"] or 1
        d["status"] = (d["status"] or "active").lower()
        # P-007
        if d["case_pack"] < 1:
            row.add("P-007", "warning", "case pack should be at least 1")
        # pictures (I-001)
        if r_idx in pictures:
            row.image, row.image_source = pictures[r_idx], "embedded picture"
        elif d.get("image_file") and str(d["image_file"]).lower() in zip_files:
            row.image, row.image_source = zip_files[str(d["image_file"]).lower()], f"ZIP: {d['image_file']}"
        elif d.get("image_file") and g and f"{g}_front.jpg" in zip_files:
            row.image, row.image_source = zip_files[f"{g}_front.jpg"], f"ZIP: {g}_front.jpg"
        elif d.get("image_url") and fetch_url:
            got = fetch_url(str(d["image_url"]))
            if got:
                row.image, row.image_source = got, "URL"
        if row.image:
            try:
                with PILImage.open(io.BytesIO(row.image)) as im:
                    if max(im.size) < 300:
                        row.add("I-002", "warning", f"picture is small ({im.width}×{im.height} px)")
                    if d["width_mm"] and d["height_mm"]:
                        declared = d["width_mm"] / d["height_mm"]
                        actual = im.width / im.height
                        if abs(actual - declared) / declared > 0.25:
                            row.add("I-003", "warning", f"picture shape {actual:.2f} differs from width/height {declared:.2f}")
            except Exception:  # noqa: BLE001
                row.add("I-001", "warning", "picture could not be read")
                row.image = None
        else:
            row.add("I-001", "warning", "no front picture: a scaled placeholder will be drawn")
        rows.append(row)
    return rows


def quality_score(row: ImportRow) -> int:
    """Spec 9.4, simplified."""
    q = 100
    codes = {i["code"] for i in row.issues}
    if "P-003" in codes:
        q -= 40
    if row.image is None:
        q -= 15
    if not row.data.get("dims_verified"):
        q -= 15
    if "P-004" in codes:
        q -= 10
    if "I-003" in codes:
        q -= 10
    if "P-008" in codes:
        q -= 10
    if "I-002" in codes:
        q -= 5
    return max(0, min(100, q))
