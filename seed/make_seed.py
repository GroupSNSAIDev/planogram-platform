"""Seed data for the sample mall store SMS-001 (development and demo only).
All units: millimetres, grams. Origin: floor top-left, x right, y down."""
import json, csv, os, html
OUT = "/home/claude/arch3/seed/out/"
os.makedirs(OUT, exist_ok=True)

# ----------------------------------------------------------------- fixture templates
T = {
 "GONDOLA_DS_12": {"kind": "gondola", "name": "Gondola run, double-sided, 12 bays", "bay_width": 1000, "bays_per_side": 12, "sides": ["A", "B"],
                   "height": 1800, "depth_per_side": 450, "footprint": [12000, 1000], "temperature": "ambient", "notch_pitch": 25,
                   "surfaces": [{"kind": "shelf", "h": 150, "base": True}, {"kind": "shelf", "h": 500}, {"kind": "shelf", "h": 850}, {"kind": "shelf", "h": 1200}, {"kind": "shelf", "h": 1550}],
                   "max_load_g_per_shelf": 80000},
 "END_CAP": {"kind": "end_cap", "name": "End cap", "bay_width": 1000, "bays_per_side": 1, "sides": ["A"], "height": 1800, "depth_per_side": 500,
             "footprint": [1000, 600], "temperature": "ambient", "notch_pitch": 25,
             "surfaces": [{"kind": "shelf", "h": 150, "base": True}, {"kind": "shelf", "h": 550}, {"kind": "shelf", "h": 950}, {"kind": "shelf", "h": 1350}], "max_load_g_per_shelf": 60000},
 "WALL_BAY": {"kind": "wall_bay", "name": "Wall bay", "bay_width": 1000, "bays_per_side": 1, "sides": ["A"], "height": 2100, "depth_per_side": 500,
              "footprint": [1000, 500], "temperature": "ambient", "notch_pitch": 25,
              "surfaces": [{"kind": "shelf", "h": 150, "base": True}, {"kind": "shelf", "h": 500}, {"kind": "shelf", "h": 850}, {"kind": "shelf", "h": 1200}, {"kind": "shelf", "h": 1550}, {"kind": "shelf", "h": 1850}],
              "max_load_g_per_shelf": 100000},
 "MULTIDECK_2500": {"kind": "multideck", "name": "Open multideck chiller 2.5 m", "bay_width": 2500, "bays_per_side": 1, "sides": ["A"], "height": 2000, "depth_per_side": 650,
                    "footprint": [2500, 900], "temperature": "chilled", "notch_pitch": 25,
                    "surfaces": [{"kind": "shelf", "h": 300, "base": True}, {"kind": "shelf", "h": 650}, {"kind": "shelf", "h": 1000}, {"kind": "shelf", "h": 1300}, {"kind": "shelf", "h": 1600}],
                    "max_load_g_per_shelf": 60000},
 "GLASS_DOOR_FREEZER_4": {"kind": "door_freezer", "name": "Glass-door freezer, 4 doors", "bay_width": 750, "bays_per_side": 4, "sides": ["A"], "height": 2100, "depth_per_side": 700,
                          "footprint": [3000, 900], "temperature": "frozen", "doors": True, "door_swing_mm": 700,
                          "surfaces": [{"kind": "shelf", "h": 200, "base": True}, {"kind": "shelf", "h": 550}, {"kind": "shelf", "h": 900}, {"kind": "shelf", "h": 1250}, {"kind": "shelf", "h": 1600}],
                          "max_load_g_per_shelf": 40000},
 "ISLAND_FREEZER_2500": {"kind": "chest_freezer", "name": "Island chest freezer 2.5 m", "bay_width": 2500, "bays_per_side": 1, "sides": ["TOP"], "height": 850, "depth_per_side": 1000,
                         "footprint": [2500, 1000], "temperature": "frozen", "surfaces": [{"kind": "chest", "h": 850, "grid": [10, 4], "load_line_mm": 600}]},
 "PRODUCE_BIN": {"kind": "produce_bin", "name": "Produce bin / table", "bay_width": 1200, "bays_per_side": 1, "sides": ["TOP"], "height": 800, "depth_per_side": 1200,
                 "footprint": [1200, 1200], "temperature": "ambient", "surfaces": [{"kind": "bin", "h": 800, "capacity_l": 300}]},
 "PALLET": {"kind": "pallet", "name": "Pallet display", "bay_width": 1200, "bays_per_side": 1, "sides": ["TOP"], "height": 1400, "depth_per_side": 1000,
            "footprint": [1200, 1000], "temperature": "ambient", "surfaces": [{"kind": "stack", "h": 150, "max_layers": 6}]},
 "BAKERY_RACK": {"kind": "bakery_rack", "name": "Bakery rack", "bay_width": 1000, "bays_per_side": 1, "sides": ["A"], "height": 1600, "depth_per_side": 500,
                 "footprint": [1000, 500], "temperature": "ambient", "surfaces": [{"kind": "shelf", "h": 300, "base": True}, {"kind": "shelf", "h": 700}, {"kind": "shelf", "h": 1100}]},
 "CHECKOUT_COUNTER": {"kind": "checkout", "name": "Checkout counter with belt", "bay_width": 1000, "bays_per_side": 0, "sides": [], "height": 900, "footprint": [1000, 2800], "temperature": "ambient", "surfaces": []},
 "CHECKOUT_RACK": {"kind": "checkout_rack", "name": "Checkout impulse rack", "bay_width": 300, "bays_per_side": 1, "sides": ["A"], "height": 1400, "depth_per_side": 300,
                   "footprint": [300, 1400], "temperature": "ambient",
                   "surfaces": [{"kind": "shelf", "h": 500}, {"kind": "shelf", "h": 800}, {"kind": "shelf", "h": 1100}, {"kind": "peg", "h": 1300, "grid": [3, 2], "pitch": 50}]},
 "SELF_CHECKOUT": {"kind": "self_checkout", "name": "Self-checkout kiosk", "bay_width": 800, "bays_per_side": 0, "sides": [], "height": 1500, "footprint": [800, 800], "temperature": "ambient", "surfaces": []},
 "SERVICE_DESK": {"kind": "service_desk", "name": "Customer service desk", "bay_width": 3000, "bays_per_side": 0, "sides": [], "height": 1100, "footprint": [3000, 1000], "temperature": "ambient", "surfaces": []},
}

# ----------------------------------------------------------------- store, landmarks, zones
store = {"code": "SMS-001", "name": "Sample Mall Store 001 (demo)", "format": "hypermarket_mall", "floor": {"level": 0, "width_mm": 48000, "depth_mm": 32000,
         "outline": [[0, 0], [48000, 0], [48000, 32000], [0, 32000]]}, "timezone": "Asia/Kolkata"}
landmarks = [
    {"kind": "entrance", "name": "Mall entrance", "rect": [2500, 31800, 5000, 200]},
    {"kind": "exit", "name": "Exit", "rect": [38000, 31800, 3000, 200]},
    {"kind": "trolley_bay", "name": "Trolleys and baskets", "rect": [0, 29000, 2200, 3000]},
    {"kind": "pillar", "name": "Pillar P1", "rect": [18300, 22200, 600, 600]},
    {"kind": "pillar", "name": "Pillar P2", "rect": [30300, 22200, 600, 600]},
    {"kind": "stockroom_door", "name": "Stockroom door", "rect": [46000, 0, 1500, 200]},
]
zones = [
    {"code": "Z-FRESH", "kind": "entrance", "name": "Entrance and fresh", "rect": [0, 21000, 18000, 11000]},
    {"code": "Z-CHECKOUT", "kind": "checkout", "name": "Checkout and impulse", "rect": [20000, 23600, 28000, 8400]},
    {"code": "Z-CHILLED", "kind": "chilled", "name": "Chilled and frozen wall", "rect": [0, 0, 48000, 1600]},
    {"code": "Z-FROZEN-ISLAND", "kind": "frozen", "name": "Frozen islands", "rect": [36200, 6000, 8400, 6600]},
    {"code": "Z-MAIN-BACK", "kind": "main_aisle", "name": "Main aisle (back)", "rect": [0, 1600, 48000, 3000]},
    {"code": "Z-MAIN-FRONT", "kind": "main_aisle", "name": "Main aisle (front)", "rect": [0, 17800, 48000, 3200]},
    {"code": "Z-CENTRE", "kind": "centre_store", "name": "Centre store (ambient grid)", "rect": [4600, 4600, 31000, 13200]},
    {"code": "Z-WALL-L", "kind": "perimeter", "name": "Staples wall", "rect": [0, 3000, 3600, 16000]},
    {"code": "Z-WALL-R", "kind": "perimeter", "name": "Home care wall", "rect": [44800, 3000, 3200, 16000]},
]

fixtures = []
def fx(code, tpl, x, y, rot=0, faces=None, note=None):
    w, d = T[tpl]["footprint"]
    fw, fd = (w, d) if rot in (0, 180) else (d, w)
    fixtures.append({"code": code, "template": tpl, "kind": T[tpl]["kind"], "x_mm": x, "y_mm": y, "rotation_deg": rot,
                     "footprint_w_mm": fw, "footprint_d_mm": fd, "temperature": T[tpl]["temperature"], "faces": faces, "note": note})

for i in range(5): fx(f"MD-{i+1:02d}", "MULTIDECK_2500", 3000 + i * 2500, 0, 0, "S")
for i in range(4): fx(f"MD-{i+6:02d}", "MULTIDECK_2500", 16000 + i * 2500, 0, 0, "S")
for i in range(4): fx(f"FZ-{i+1:02d}", "GLASS_DOOR_FREEZER_4", 26500 + i * 3000, 0, 0, "S")
for i in range(2): fx(f"MD-{i+10:02d}", "MULTIDECK_2500", 39000 + i * 2500, 0, 0, "S")
for i in range(16): fx(f"WL-{i+1:02d}", "WALL_BAY", 0, 3000 + i * 1000, 90, "E")
for i in range(16): fx(f"WR-{i+1:02d}", "WALL_BAY", 47500, 3000 + i * 1000, 270, "W")
GX = [5200 + i * 3200 for i in range(10)]
for i, x in enumerate(GX):
    fx(f"G{i+1:02d}", "GONDOLA_DS_12", x, 5200, 90, "W/E", "Side A faces west, side B faces east; bay 1 at the back")
    fx(f"EC-G{i+1:02d}-B", "END_CAP", x, 4600, 0, "N")
    fx(f"EC-G{i+1:02d}-F", "END_CAP", x, 17200, 0, "S")
for j, y in enumerate([6000, 8500, 11000, 13500]): fx(f"SP-{j+1:02d}", "PALLET", 2000, y, 0, "ALL", "Bulk rice and atta bags")
for j, (x, y) in enumerate([(37000, 7000), (41000, 7000), (37000, 10500), (41000, 10500)]): fx(f"IF-{j+1:02d}", "ISLAND_FREEZER_2500", x, y, 0, "TOP")
fx("MD-12", "MULTIDECK_2500", 0, 21500, 90, "E", "Cut fruit, salads, herbs")
for r, y in enumerate([23200, 25400]):
    for c in range(4): fx(f"PB-{r*4+c+1:02d}", "PRODUCE_BIN", 2600 + c * 1800, y, 0, "TOP")
for i in range(3): fx(f"BK-{i+1:02d}", "BAKERY_RACK", 10600 + i * 1000, 22600, 180, "S")
for i in range(4): fx(f"PL-{i+1:02d}", "PALLET", 10600 + i * 1600, 26200, 0, "ALL", "Entrance promotions")
for i in range(6):
    x = 22000 + i * 2400
    fx(f"CO-{i+1:02d}", "CHECKOUT_COUNTER", x, 25000, 0, None, f"Lane {i+1}")
    fx(f"CR-{i+1:02d}", "CHECKOUT_RACK", x + 1050, 25200, 0, "E", f"Impulse rack lane {i+1}")
fx("CO-07", "CHECKOUT_COUNTER", 36400, 25000, 0, None, "Express lane (10 items)")
fx("CR-07", "CHECKOUT_RACK", 37450, 25200, 0, "E", "Impulse rack express")
fx("SC-01", "SELF_CHECKOUT", 39400, 25400, 0); fx("SC-02", "SELF_CHECKOUT", 40600, 25400, 0)
fx("CS-01", "SERVICE_DESK", 43500, 28000, 0, None, "Customer service and returns")

# ----------------------------------------------------------------- categories
CATS = [
 ("FV", "Fresh", "Fruits & vegetables", "ambient"), ("CUT", "Fresh", "Cut fruit & salads", "chilled"), ("BAK", "Fresh", "Bakery", "ambient"),
 ("DAI", "Dairy & chilled", "Milk, curd, paneer, butter", "chilled"), ("CHE", "Dairy & chilled", "Cheese & eggs", "chilled"), ("RTE", "Dairy & chilled", "Ready meals & deli", "chilled"),
 ("BEVC", "Beverages", "Chilled beverages", "chilled"), ("FRZ", "Frozen", "Frozen veg & snacks", "frozen"), ("ICE", "Frozen", "Ice cream & desserts", "frozen"),
 ("ATA", "Staples", "Atta & flours", "ambient"), ("RIC", "Staples", "Rice", "ambient"), ("DAL", "Staples", "Dal & pulses", "ambient"), ("DRY", "Staples", "Dry fruits", "ambient"),
 ("OIL", "Staples", "Edible oils & ghee", "ambient"), ("SAL", "Staples", "Salt & sugar", "ambient"), ("MAS", "Staples", "Masala & spices", "ambient"),
 ("BRK", "Packaged food", "Breakfast cereals", "ambient"), ("SPR", "Packaged food", "Spreads & honey", "ambient"), ("TEA", "Beverages", "Tea & coffee", "ambient"),
 ("HDR", "Beverages", "Health drinks", "ambient"), ("BIS", "Packaged food", "Biscuits & cookies", "ambient"), ("SNK", "Packaged food", "Snacks & namkeen", "ambient"),
 ("CHO", "Packaged food", "Chocolates & confectionery", "ambient"), ("INS", "Packaged food", "Instant food & noodles", "ambient"), ("SAU", "Packaged food", "Sauces, pickles & ketchup", "ambient"),
 ("RTC", "Packaged food", "Ready-to-cook", "ambient"), ("BEVA", "Beverages", "Soft drinks & juices", "ambient"), ("WAT", "Beverages", "Water & energy drinks", "ambient"),
 ("BAB", "Personal care", "Baby care", "ambient"), ("ORA", "Personal care", "Oral care", "ambient"), ("HAI", "Personal care", "Hair care", "ambient"),
 ("SKN", "Personal care", "Skin care", "ambient"), ("DEO", "Personal care", "Deodorants & fragrance", "ambient"), ("BAT", "Personal care", "Bath & soaps", "ambient"),
 ("FEM", "Personal care", "Feminine hygiene", "ambient"), ("MEN", "Personal care", "Men's grooming", "ambient"), ("WEL", "Personal care", "Wellness", "ambient"),
 ("DET", "Home care", "Detergents", "ambient"), ("CLN", "Home care", "Cleaners & fresheners", "ambient"), ("POO", "Home care", "Pooja needs", "ambient"),
 ("KIT", "General merchandise", "Kitchen & household", "ambient"), ("STA", "General merchandise", "Stationery", "ambient"), ("PET", "Home care", "Pet care", "ambient"),
 ("PAP", "Home care", "Paper & tissues", "ambient"), ("BULK", "Staples", "Bulk bags (5–25 kg)", "ambient"), ("PLA", "Home care", "Plastics & storage", "ambient"),
 ("IMP", "Impulse", "Checkout impulse", "ambient"), ("PRO", "Promotions", "Promotions", "ambient"), ("SEA", "Promotions", "Seasonal", "ambient"),
]
cat_by = {c[0]: c for c in CATS}

# ----------------------------------------------------------------- sections (category per bay range)
sections = []
def sec(fixture, side, b1, b2, cat, lock=None):
    sections.append({"code": f"{fixture}-{side}-{b1:02d}", "fixture": fixture, "side": side, "bay_from": b1, "bay_to": b2,
                     "category": cat, "category_name": cat_by[cat][2], "department": cat_by[cat][1], "assignment_lock": lock})
GPLAN = {
 "G01": [("A", 1, 6, "ATA"), ("A", 7, 12, "RIC"), ("B", 1, 8, "DAL"), ("B", 9, 12, "DRY")],
 "G02": [("A", 1, 8, "OIL"), ("A", 9, 12, "SAL"), ("B", 1, 12, "MAS")],
 "G03": [("A", 1, 6, "BRK"), ("A", 7, 12, "SPR"), ("B", 1, 8, "TEA"), ("B", 9, 12, "HDR")],
 "G04": [("A", 1, 12, "BIS"), ("B", 1, 12, "SNK")],
 "G05": [("A", 1, 6, "CHO"), ("A", 7, 12, "INS"), ("B", 1, 6, "SAU"), ("B", 7, 12, "RTC")],
 "G06": [("A", 1, 12, "BEVA"), ("B", 1, 6, "WAT"), ("B", 7, 12, "BAB")],
 "G07": [("A", 1, 6, "ORA"), ("A", 7, 12, "HAI"), ("B", 1, 8, "SKN"), ("B", 9, 12, "DEO")],
 "G08": [("A", 1, 8, "BAT"), ("A", 9, 12, "FEM"), ("B", 1, 6, "MEN"), ("B", 7, 12, "WEL")],
 "G09": [("A", 1, 12, "DET"), ("B", 1, 8, "CLN"), ("B", 9, 12, "POO")],
 "G10": [("A", 1, 8, "KIT"), ("A", 9, 12, "STA"), ("B", 1, 6, "PET"), ("B", 7, 12, "PAP")],
}
for g, rows in GPLAN.items():
    for side, b1, b2, cat in rows: sec(g, side, b1, b2, cat, "category" if cat in ("BAB", "WEL") else None)
for i in range(10):
    sec(f"EC-G{i+1:02d}-F", "A", 1, 1, "PRO"); sec(f"EC-G{i+1:02d}-B", "A", 1, 1, "SEA")
for i in range(16): sec(f"WL-{i+1:02d}", "A", 1, 1, "BULK" if i < 10 else "OIL")
for i in range(16): sec(f"WR-{i+1:02d}", "A", 1, 1, "DET" if i < 6 else ("PLA" if i < 12 else "PAP"))
for i in range(5): sec(f"MD-{i+1:02d}", "A", 1, 1, "DAI" if i < 4 else "CHE", "category")
for i in range(4): sec(f"MD-{i+6:02d}", "A", 1, 1, "BEVC")
for i in range(4): sec(f"FZ-{i+1:02d}", "A", 1, 4, "FRZ", "category")
for i in range(2): sec(f"MD-{i+10:02d}", "A", 1, 1, "RTE")
for i in range(4): sec(f"IF-{i+1:02d}", "TOP", 1, 1, "ICE" if i < 2 else "FRZ", "category")
sec("MD-12", "A", 1, 1, "CUT")
for i in range(8): sec(f"PB-{i+1:02d}", "TOP", 1, 1, "FV", "category")
for i in range(3): sec(f"BK-{i+1:02d}", "A", 1, 1, "BAK")
for i in range(4): sec(f"PL-{i+1:02d}", "TOP", 1, 1, "PRO")
for i in range(4): sec(f"SP-{i+1:02d}", "TOP", 1, 1, "BULK")
for i in range(7): sec(f"CR-{i+1:02d}", "A", 1, 1, "IMP", "category")

# ----------------------------------------------------------------- sample products (invented; GS1 prefix 200 = restricted circulation)
def gtin13(body12):
    s = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(body12))
    return body12 + str((10 - s % 10) % 10)
P = [
 ("ATA", "Whole Wheat Atta 5 kg", "Demo Mills", 300, 440, 110, 5050), ("ATA", "Multigrain Atta 1 kg", "Demo Mills", 150, 230, 70, 1020),
 ("RIC", "Basmati Rice 1 kg", "Demo Grains", 160, 250, 80, 1015), ("RIC", "Sona Masoori Rice 5 kg", "Demo Grains", 300, 450, 120, 5040),
 ("DAL", "Toor Dal 1 kg", "Demo Pulses", 170, 260, 70, 1010), ("DAL", "Moong Dal 500 g", "Demo Pulses", 140, 200, 60, 505),
 ("OIL", "Sunflower Oil 1 L pouch", "Demo Oils", 160, 230, 70, 930), ("OIL", "Mustard Oil 1 L bottle", "Demo Oils", 85, 280, 85, 990),
 ("OIL", "Cow Ghee 500 ml jar", "Demo Dairy", 95, 120, 95, 480), ("SAL", "Iodised Salt 1 kg", "Demo Basics", 110, 190, 60, 1005),
 ("MAS", "Turmeric Powder 200 g", "Demo Spice", 90, 150, 50, 205), ("MAS", "Garam Masala 100 g", "Demo Spice", 75, 120, 40, 105),
 ("BRK", "Corn Flakes 875 g", "Demo Foods", 200, 300, 75, 900), ("BRK", "Rolled Oats 1 kg", "Demo Foods", 190, 290, 70, 1050),
 ("SPR", "Mixed Fruit Jam 500 g", "Demo Foods", 80, 110, 80, 560), ("SPR", "Peanut Butter 340 g", "Demo Foods", 85, 115, 85, 370),
 ("TEA", "Assam Tea 500 g", "Demo Leaf", 120, 190, 70, 510), ("TEA", "Instant Coffee 100 g jar", "Demo Brew", 75, 120, 75, 240),
 ("HDR", "Malt Health Drink 500 g", "Demo Health", 110, 170, 110, 560), ("BIS", "Digestive Biscuits 400 g", "Demo Bakers", 120, 180, 60, 410),
 ("BIS", "Glucose Biscuits 800 g", "Demo Bakers", 210, 140, 70, 820), ("BIS", "Cream Biscuits 120 g", "Demo Bakers", 140, 60, 45, 125),
 ("SNK", "Salted Chips 150 g", "Demo Snacks", 150, 230, 80, 160), ("SNK", "Masala Chips 150 g", "Demo Snacks", 150, 230, 80, 160),
 ("SNK", "Mixture Namkeen 400 g", "Demo Snacks", 170, 260, 70, 410), ("CHO", "Milk Chocolate 40 g", "Demo Choco", 75, 140, 12, 45),
 ("CHO", "Fruit Toffees 200 g", "Demo Choco", 130, 180, 40, 210), ("INS", "Instant Noodles 4-pack", "Demo Foods", 180, 130, 80, 290),
 ("SAU", "Tomato Ketchup 1 kg", "Demo Foods", 95, 230, 65, 1080), ("SAU", "Mango Pickle 400 g", "Demo Foods", 90, 130, 90, 460),
 ("BEVA", "Cola 750 ml", "Demo Drinks", 80, 300, 80, 790), ("BEVA", "Mango Drink 1 L", "Demo Drinks", 95, 240, 65, 1060),
 ("WAT", "Packaged Water 1 L", "Demo Springs", 75, 280, 75, 1030), ("WAT", "Energy Drink 250 ml can", "Demo Drinks", 66, 122, 66, 270),
 ("BAB", "Baby Diapers M 50", "Demo Baby", 230, 300, 140, 1600), ("ORA", "Toothpaste 150 g", "Demo Care", 200, 50, 45, 175),
 ("ORA", "Toothbrush soft", "Demo Care", 30, 230, 25, 30), ("HAI", "Shampoo 340 ml", "Demo Care", 80, 210, 50, 380),
 ("HAI", "Hair Oil 300 ml", "Demo Care", 75, 190, 45, 330), ("SKN", "Moisturising Lotion 400 ml", "Demo Care", 85, 220, 50, 450),
 ("DEO", "Deodorant 150 ml", "Demo Care", 50, 170, 50, 140), ("BAT", "Bathing Soap 4 × 100 g", "Demo Care", 230, 70, 60, 420),
 ("MEN", "Shaving Foam 200 g", "Demo Care", 60, 190, 60, 230), ("DET", "Detergent Powder 1 kg", "Demo Home", 190, 260, 80, 1030),
 ("DET", "Liquid Detergent 2 L", "Demo Home", 150, 280, 90, 2150), ("CLN", "Floor Cleaner 975 ml", "Demo Home", 110, 250, 70, 1050),
 ("CLN", "Dishwash Bar 3-pack", "Demo Home", 180, 90, 60, 610), ("POO", "Agarbatti 100 sticks", "Demo Pooja", 60, 260, 40, 140),
 ("KIT", "Aluminium Foil 9 m", "Demo Home", 310, 50, 50, 260), ("STA", "Notebook A4 pack of 3", "Demo Paper", 210, 297, 25, 650),
 ("PET", "Dog Food 1.2 kg", "Demo Pet", 200, 300, 80, 1230), ("PAP", "Tissue Box 100 pulls", "Demo Paper", 230, 90, 115, 180),
 ("DAI", "Toned Milk 1 L", "Demo Dairy", 95, 240, 95, 1040), ("DAI", "Curd 400 g cup", "Demo Dairy", 95, 75, 95, 420),
 ("DAI", "Paneer 200 g", "Demo Dairy", 130, 30, 90, 210), ("CHE", "Cheese Slices 200 g", "Demo Dairy", 100, 25, 100, 210),
 ("BEVC", "Cold Coffee 200 ml", "Demo Dairy", 55, 140, 55, 220), ("FRZ", "Frozen Green Peas 500 g", "Demo Frozen", 180, 250, 50, 510),
 ("ICE", "Vanilla Ice Cream 1 L tub", "Demo Frozen", 150, 90, 150, 560), ("IMP", "Chewing Gum 10-pack", "Demo Choco", 75, 25, 20, 30),
]
products = []
for i, (cat, name, brand, w, h, d, g) in enumerate(P):
    gt = gtin13(f"200{i+1:09d}")
    products.append({"sku": f"SKU{i+1:05d}", "gtin": gt, "name": f"{name} (sample)", "brand": brand, "category": cat,
                     "category_name": cat_by[cat][2], "department": cat_by[cat][1], "width_mm": w, "height_mm": h, "depth_mm": d,
                     "weight_g": g, "case_pack": 12, "temperature": cat_by[cat][3], "dims_source": "estimated", "status": "active",
                     "image_front": f"{gt}_front.png", "age_restricted": "no", "hazardous": "no"})

# ----------------------------------------------------------------- write files
json.dump(T, open(OUT + "fixture_templates.json", "w"), indent=1)
json.dump({"store": store, "landmarks": landmarks, "zones": zones, "fixtures": fixtures}, open(OUT + "store_SMS-001.json", "w"), indent=1)
with open(OUT + "categories.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["code", "department", "category", "temperature"]); w.writerows(CATS)
with open(OUT + "sections_SMS-001.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(sections[0].keys())); w.writeheader(); w.writerows(sections)
with open(OUT + "products_sample.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(products[0].keys())); w.writeheader(); w.writerows(products)
with open(OUT + "product_import_template.csv", "w", newline="") as f:
    csv.writer(f).writerow(["sku", "gtin", "name", "brand", "category", "width_mm", "height_mm", "depth_mm", "weight_g", "case_pack", "tray_qty",
                            "temperature", "can_stack", "can_lay_down", "can_rotate", "status", "listed_from", "delist_date", "price_band",
                            "is_private_label", "supplier_code", "age_restricted", "hazardous", "fragile", "dims_source", "image_front", "image_side", "image_top"])

# summary
from collections import Counter
kinds = Counter(f["kind"] for f in fixtures)
bays = sum(T[f["template"]]["bays_per_side"] * len(T[f["template"]]["sides"]) for f in fixtures if T[f["template"]]["sides"] and T[f["template"]]["sides"][0] != "TOP")
lm = sum(T[f["template"]]["bay_width"] * T[f["template"]]["bays_per_side"] * len(T[f["template"]]["sides"]) for f in fixtures if T[f["template"]]["sides"] and T[f["template"]]["sides"][0] != "TOP") / 1000
summary = {"fixtures": len(fixtures), "by_kind": dict(kinds), "shelf_bays": bays, "linear_m_bays": lm, "sections": len(sections), "categories": len(CATS), "sample_products": len(products)}
json.dump(summary, open(OUT + "summary.json", "w"), indent=1)
print(json.dumps(summary, indent=1))

# ----------------------------------------------------------------- render plan
DEPT_COL = {"Fresh": "#BBF7D0", "Dairy & chilled": "#BFDBFE", "Beverages": "#A5F3FC", "Frozen": "#C7D2FE", "Staples": "#FDE68A", "Packaged food": "#FED7AA",
            "Personal care": "#FBCFE8", "Home care": "#DDD6FE", "General merchandise": "#E5E7EB", "Impulse": "#FCA5A5", "Promotions": "#D9F99D"}
K = 0.031; OX, OY = 30, 60  # px per mm
X = lambda v: OX + v * K; Y = lambda v: OY + v * K
W, H = int(48000 * K + 2 * OX + 330), int(32000 * K + OY + 70)
s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}"><rect width="{W}" height="{H}" fill="#fff"/>']
s.append(f'<text x="{OX}" y="30" font-family="Inter" font-size="19" font-weight="800" fill="#0F172A">Sample Mall Store SMS-001 · 48 × 32 m (1,536 m²) · ground floor</text>')
s.append(f'<text x="{OX}" y="50" font-family="Inter" font-size="12.5" fill="#64748B">Racetrack main aisle around an ambient grid; fresh at the entrance, dairy and frozen on the back wall, impulse at checkout</text>')
ZC = {"entrance": "#059669", "checkout": "#D97706", "chilled": "#2563EB", "frozen": "#4F46E5", "main_aisle": "#94A3B8", "centre_store": "#64748B", "perimeter": "#A16207"}
for z in zones:
    x, y, w, h = z["rect"]
    if z["kind"] in ("main_aisle",):
        s.append(f'<rect x="{X(x)}" y="{Y(y)}" width="{w*K}" height="{h*K}" fill="#E0E7FF" fill-opacity=".45"/>')
    elif z["kind"] not in ("centre_store", "perimeter"):
        s.append(f'<rect x="{X(x)}" y="{Y(y)}" width="{w*K}" height="{h*K}" fill="{ZC[z["kind"]]}" fill-opacity=".07" stroke="{ZC[z["kind"]]}" stroke-opacity=".5" stroke-dasharray="5 4"/>')
s.append(f'<rect x="{X(0)}" y="{Y(0)}" width="{48000*K}" height="{32000*K}" fill="none" stroke="#0F172A" stroke-width="5"/>')
for lmk in landmarks:
    x, y, w, h = lmk["rect"]
    if lmk["kind"] in ("entrance", "exit"):
        s.append(f'<rect x="{X(x)}" y="{Y(32000)-4}" width="{w*K}" height="8" fill="#fff"/>')
        s.append(f'<text x="{X(x+w/2)}" y="{Y(32000)+18}" font-family="Inter" font-size="12" font-weight="800" fill="{"#059669" if lmk["kind"]=="entrance" else "#64748B"}" text-anchor="middle">{"▲ ENTRANCE (from mall)" if lmk["kind"]=="entrance" else "EXIT ▼"}</text>')
    elif lmk["kind"] == "pillar":
        s.append(f'<rect x="{X(x)}" y="{Y(y)}" width="{w*K}" height="{h*K}" fill="#334155"/>')
    elif lmk["kind"] == "trolley_bay":
        s.append(f'<rect x="{X(x)}" y="{Y(y)}" width="{w*K}" height="{h*K}" fill="#F1F5F9" stroke="#94A3B8"/><text x="{X(x+w/2)}" y="{Y(y+h/2)+4}" font-family="Inter" font-size="9.5" fill="#475569" text-anchor="middle">Trolleys</text>')
    elif lmk["kind"] == "stockroom_door":
        s.append(f'<rect x="{X(x)}" y="{Y(0)-4}" width="{w*K}" height="8" fill="#fff"/><text x="{X(x+w/2)}" y="{Y(0)-8}" font-family="Inter" font-size="10" fill="#64748B" text-anchor="middle">stockroom</text>')
sec_by_fx = {}
for sc in sections: sec_by_fx.setdefault(sc["fixture"], []).append(sc)
for f in fixtures:
    x, y, w, h = f["x_mm"], f["y_mm"], f["footprint_w_mm"], f["footprint_d_mm"]
    secs = sec_by_fx.get(f["code"], [])
    if f["kind"] == "gondola":
        for sc in secs:
            hx = x if sc["side"] == "A" else x + w / 2
            sy = y + (sc["bay_from"] - 1) * 1000; sh = (sc["bay_to"] - sc["bay_from"] + 1) * 1000
            s.append(f'<rect x="{X(hx)}" y="{Y(sy)}" width="{w/2*K}" height="{sh*K}" fill="{DEPT_COL[sc["department"]]}" stroke="#94A3B8" stroke-width=".6"/>')
        s.append(f'<rect x="{X(x)}" y="{Y(y)}" width="{w*K}" height="{h*K}" fill="none" stroke="#475569" stroke-width="1.1"/>')
        s.append(f'<text transform="translate({X(x+w/2)+3.5},{Y(y+h/2)}) rotate(-90)" font-family="Inter" font-size="10" font-weight="800" fill="#0F172A" text-anchor="middle">{f["code"]}</text>')
    else:
        col = DEPT_COL[secs[0]["department"]] if secs else "#E2E8F0"
        if f["kind"] in ("checkout", "self_checkout", "service_desk"): col = "#CBD5E1"
        rx = 6 if f["kind"] in ("produce_bin",) else 1.5
        s.append(f'<rect x="{X(x)}" y="{Y(y)}" width="{w*K}" height="{h*K}" rx="{rx}" fill="{col}" stroke="#475569" stroke-width=".8"/>')
        if f["kind"] in ("door_freezer",):
            for dd in range(1, 4): s.append(f'<line x1="{X(x+dd*750)}" x2="{X(x+dd*750)}" y1="{Y(y)}" y2="{Y(y+h)}" stroke="#475569" stroke-width=".6"/>')
lab = lambda x, y, t, sz=10, c="#0F172A", a="middle", wgt=600: s.append(f'<text x="{X(x)}" y="{Y(y)}" font-family="Inter" font-size="{sz}" font-weight="{wgt}" fill="{c}" text-anchor="{a}">{html.escape(t)}</text>')
lab(9300, 650, "Dairy multidecks MD-01–05"); lab(21000, 650, "Chilled drinks MD-06–09"); lab(32500, 650, "Glass-door freezers FZ-01–04"); lab(41500, 650, "Ready meals")
lab(40250, 9500, "Island freezers IF-01–04", 10, "#3730A3")
s.append(f'<text transform="translate({X(1300)},{Y(11000)}) rotate(-90)" font-family="Inter" font-size="10" font-weight="600" fill="#713F12" text-anchor="middle">Staples wall WL-01–16</text>')
s.append(f'<text transform="translate({X(46900)},{Y(11000)}) rotate(-90)" font-family="Inter" font-size="10" font-weight="600" fill="#4C1D95" text-anchor="middle">Home care wall WR-01–16</text>')
lab(2600, 5600, "Bulk pallets", 9.5, "#713F12", "start")
lab(6100, 28400, "Fruit & vegetable bins", 10, "#166534"); lab(12100, 22300, "Bakery", 10, "#166534"); lab(13000, 27900, "Promo pallets", 10, "#854D0E")
lab(29800, 24600, "Checkouts CO-01–07 with impulse racks", 10.5, "#0F172A"); lab(40000, 27100, "Self", 9.5); lab(45000, 29700, "Service desk", 9.5)
lab(24000, 3300, "MAIN AISLE (BACK)", 10.5, "#4338CA", "middle", 800); lab(24000, 19700, "MAIN AISLE (FRONT)", 10.5, "#4338CA", "middle", 800)
lab(9000, 30600, "ENTRANCE · FRESH", 10.5, "#059669", "middle", 800); lab(34000, 31200, "CHECKOUT · IMPULSE", 10.5, "#B45309", "middle", 800)
s.append(f'<path d="M{X(5000)},{Y(31500)} L{X(5000)},{Y(20500)} L{X(3600)},{Y(19500)} L{X(3600)},{Y(3000)} L{X(44000)},{Y(3000)} L{X(44000)},{Y(19400)} L{X(36000)},{Y(19400)} L{X(36000)},{Y(23400)}" fill="none" stroke="#4338CA" stroke-width="2.2" stroke-dasharray="7 6" stroke-opacity=".75"/>')
# legend
LX = X(48000) + 24; ly = OY + 4
s.append(f'<text x="{LX}" y="{ly}" font-family="Inter" font-size="12" font-weight="800" fill="#0F172A">DEPARTMENTS</text>'); ly += 14
for dname, col in DEPT_COL.items():
    s.append(f'<rect x="{LX}" y="{ly}" width="16" height="12" rx="2" fill="{col}" stroke="#94A3B8"/><text x="{LX+24}" y="{ly+10}" font-family="Inter" font-size="11.5" fill="#334155">{html.escape(dname)}</text>'); ly += 19
ly += 10
s.append(f'<text x="{LX}" y="{ly}" font-family="Inter" font-size="12" font-weight="800" fill="#0F172A">KEY NUMBERS</text>'); ly += 18
for t in [f"{summary['fixtures']} fixtures", f"{summary['shelf_bays']} shelf bays", f"{summary['linear_m_bays']:.0f} m of bays", f"{summary['sections']} sections, {summary['categories']} categories",
          "10 gondola runs, 20 end caps", "11 multidecks, 16 freezer doors", "4 island freezers, 8 produce bins", "7 checkouts + 2 self-checkout", "Aisles 2.2 m · main aisles 3.0–3.2 m"]:
    s.append(f'<text x="{LX}" y="{ly}" font-family="Inter" font-size="11.5" fill="#334155">{html.escape(t)}</text>'); ly += 17
ly += 8
s.append(f'<text x="{LX}" y="{ly}" font-family="Inter" font-size="11" fill="#64748B">Gondola side A faces west,</text>'); ly += 15
s.append(f'<text x="{LX}" y="{ly}" font-family="Inter" font-size="11" fill="#64748B">side B east; bay 1 at the back.</text>'); ly += 15
s.append(f'<text x="{LX}" y="{ly}" font-family="Inter" font-size="11" fill="#64748B">Dashed line: main shopper path.</text>')
s.append(f'<line x1="{X(0)}" x2="{X(5000)}" y1="{Y(32000)+40}" y2="{Y(32000)+40}" stroke="#0F172A" stroke-width="2"/><text x="{X(0)}" y="{Y(32000)+56}" font-family="Inter" font-size="10" fill="#475569">0</text><text x="{X(5000)}" y="{Y(32000)+56}" font-family="Inter" font-size="10" fill="#475569" text-anchor="middle">5 m</text>')
s.append("</svg>")
svg = "".join(s)
open(OUT + "store_SMS-001_plan.svg", "w").write(svg)
import sys; sys.path.insert(0, "/home/claude/arch3")
from diagrams import render
render([("/home/claude/arch3/fig/sample_store.png", svg, W, H)])
print("plan", W, H)
