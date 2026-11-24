"""Write seed/poc_demo_products.csv: fictional breakfast-cereal catalogue for the POC hero section
G03-A-01. Brands are the design system's test brands. GTINs use the GS1 21x restricted-circulation
range with valid check digits. A few rows are deliberately imperfect so the eligibility badges show:
estimated sizes, unreviewed safety flags, no image, too tall for any shelf."""
import csv
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "seed" / "poc_demo_products.csv"

# name, brand, w, h, d, weight_g, price, units_per_day, flags
ROWS = [
    ("Sunmill Rolled Oats 1 kg", "Sunmill", 190, 280, 70, 1050, 199, 6.0, ""),
    ("Sunmill Instant Oats 500 g", "Sunmill", 170, 250, 60, 540, 129, 4.5, ""),
    ("Sunmill Masala Oats 400 g", "Sunmill", 160, 240, 60, 430, 149, 3.8, ""),
    ("Sunmill Oats Jar 1 kg", "Sunmill", 120, 220, 120, 1080, 249, 1.5, ""),
    ("Sunmill Oats Jumbo Tub 2 kg", "Sunmill", 230, 470, 150, 2100, 399, 0.8, ""),
    ("Sunmill Steel-cut Oats 500 g", "Sunmill", 150, 230, 60, 520, 169, 1.2, ""),
    ("Kirra Corn Flakes 875 g", "Kirra", 220, 285, 65, 900, 289, 5.5, ""),
    ("Kirra Corn Flakes 475 g", "Kirra", 180, 250, 60, 490, 169, 4.0, ""),
    ("Kirra Choco Flakes 375 g", "Kirra", 190, 260, 50, 390, 179, 4.2, ""),
    ("Kirra Honey Loops 300 g", "Kirra", 170, 240, 55, 315, 159, 2.6, ""),
    ("Kirra Corn Flakes Family 1.2 kg", "Kirra", 240, 340, 75, 1250, 379, 1.4, ""),
    ("Kirra Strawberry Flakes 300 g", "Kirra", 170, 240, 55, 310, 169, 1.8, ""),
    ("Ostra Fruit Muesli 750 g", "Ostra", 180, 270, 60, 770, 379, 2.4, "estimated"),
    ("Ostra Nut Muesli 500 g", "Ostra", 160, 240, 55, 510, 329, 1.9, "no_image"),
    ("Ostra Crunchy Muesli 500 g", "Ostra", 160, 240, 55, 520, 299, 1.6, ""),
    ("Ostra No-Sugar Muesli 400 g", "Ostra", 150, 230, 55, 410, 349, 1.1, ""),
    ("Pellio Granola 450 g", "Pellio", 150, 220, 80, 460, 349, 1.7, ""),
    ("Pellio Choco Granola 450 g", "Pellio", 150, 220, 80, 460, 349, 1.3, ""),
    ("Pellio Berry Granola 350 g", "Pellio", 140, 210, 75, 360, 329, 0.9, ""),
    ("Pellio Granola Bars 6-pack", "Pellio", 160, 120, 45, 180, 149, 2.2, ""),
    ("Vexa Multigrain Flakes 1 kg", "Vexa", 210, 285, 75, 1040, 259, 2.8, "safety_unreviewed"),
    ("Vexa Multigrain Flakes 500 g", "Vexa", 180, 250, 60, 520, 149, 3.0, ""),
    ("Vexa Wheat Flakes 475 g", "Vexa", 180, 250, 60, 490, 139, 2.1, ""),
    ("Vexa Bran Flakes 400 g", "Vexa", 170, 240, 55, 410, 159, 1.0, ""),
    ("Vexa Ragi Flakes 375 g", "Vexa", 170, 240, 55, 385, 169, 0.8, ""),
    ("Mavo Choco Puffs 250 g", "Mavo", 160, 230, 50, 260, 119, 3.4, ""),
    ("Mavo Fruit Rings 285 g", "Mavo", 160, 230, 50, 290, 139, 2.0, ""),
    ("Mavo Honey Stars 250 g", "Mavo", 160, 230, 50, 260, 129, 1.5, ""),
    ("Mavo Choco Fills 250 g", "Mavo", 150, 200, 60, 260, 149, 2.7, ""),
    ("Lumo Corn Flakes 1 kg", "Lumo", 220, 285, 70, 1020, 199, 2.5, ""),
    ("Lumo Oats 1 kg", "Lumo", 190, 280, 70, 1030, 149, 2.2, ""),
    ("Lumo Wheat Flakes 500 g", "Lumo", 180, 250, 60, 510, 99, 1.4, ""),
    ("Lumo Muesli 500 g", "Lumo", 160, 240, 55, 510, 199, 0.9, ""),
    ("Lumo Choco Flakes 375 g", "Lumo", 180, 250, 50, 390, 119, 1.1, ""),
]
BRAND_COLOUR = {"Sunmill": "#F59E0B", "Kirra": "#EAB308", "Ostra": "#9333EA", "Pellio": "#16A34A",
                "Vexa": "#0D9488", "Mavo": "#2563EB", "Lumo": "#64748B"}
MARGIN = {"Lumo": 0.28}  # private label earns more per unit sold


def gtin13(body12: str) -> str:
    s = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(body12))
    return body12 + str((10 - s % 10) % 10)


def main() -> None:
    cols = ["sku", "gtin", "name", "brand", "category", "width_mm", "height_mm", "depth_mm", "weight_g",
            "case_pack", "temperature", "dims_source", "dims_verified", "safety_reviewed", "has_image",
            "can_stack", "max_stack", "colour", "price", "units_per_day", "margin_rate"]
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for i, (name, brand, wd, ht, dp, g, price, upd, flag) in enumerate(ROWS, start=1):
            w.writerow([f"BRK{i:05d}", gtin13(f"210{i:09d}"), name, brand, "BRK", wd, ht, dp, g, 12, "ambient",
                        "estimated" if flag == "estimated" else "measured",
                        "no" if flag == "estimated" else "yes",
                        "no" if flag == "safety_unreviewed" else "yes",
                        "no" if flag == "no_image" else "yes",
                        "no", 1, BRAND_COLOUR[brand], price, upd, MARGIN.get(brand, 0.2)])
    print(f"wrote {len(ROWS)} products to {OUT}")


if __name__ == "__main__":
    main()
