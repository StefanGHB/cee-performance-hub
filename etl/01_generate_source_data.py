"""
CEE Commercial & Operations Performance Hub
Step 1 - Generate realistic *source-system* extracts for a fictional
B2B FMCG distributor ("Danubia Distribution Group", fictional) operating in 8 CEE countries.

The output imitates raw ERP / WMS / GL extracts:
  * amounts in LOCAL currency (as each country ERP records them)
  * a handful of deliberate data-quality defects (duplicates, orphan keys,
    invalid dates, missing attributes, negative quantities, late data)
    so the ETL and the Data Quality page have something real to catch.

Business stories built into the data (to be "discovered" in the report):
  1. Romania & Poland drive growth; Hungary grows in HUF but declines in EUR (FX).
  2. Cocoa & coffee cost inflation squeeze Snacks & Coffee margins in 2024-2025.
  3. Personal Care promo intensity jumps in Q2 2026 -> margin erosion.
  4. Bucharest DC capacity issue Jan-May 2026 -> OTIF collapse + higher logistics cost.
  5. Coffee & Tea supply disruption Oct-Dec 2025 -> short shipments / stock-outs.
  6. E-commerce is the fastest-growing channel; strong customer concentration (Pareto).
  7. Orthodox vs Western Easter timing differs by country.

Run:  python 01_generate_source_data.py  (writes ../data/raw)
"""
from __future__ import annotations

import os
from datetime import date, timedelta

import numpy as np
import pandas as pd

SEED = 20261026
rng = np.random.default_rng(SEED)
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
os.makedirs(OUT, exist_ok=True)

START = pd.Timestamp("2023-01-01")
END_ACT = pd.Timestamp("2026-09-30")          # last closed month
MONTHS = pd.date_range(START, END_ACT, freq="MS")
YEARS = [2023, 2024, 2025, 2026]

# --------------------------------------------------------------------------
# Countries
# --------------------------------------------------------------------------
countries = pd.DataFrame(
    [
        # code, name, region, currency, base 2023 net sales EUR m, EUR growth p.a., customers
        ("PL", "Poland",   "Central Europe",       "PLN", 42.0, 0.085, 280),
        ("RO", "Romania",  "South-Eastern Europe", "RON", 34.0, 0.120, 220),
        ("CZ", "Czechia",  "Central Europe",       "CZK", 26.0, 0.040, 170),
        ("HU", "Hungary",  "Central Europe",       "HUF", 22.0, -0.022, 150),
        ("GR", "Greece",   "South-Eastern Europe", "EUR", 20.0, 0.030, 140),
        ("BG", "Bulgaria", "South-Eastern Europe", "BGN", 14.0, 0.060, 110),
        ("RS", "Serbia",   "South-Eastern Europe", "RSD", 9.0,  0.100, 70),
        ("HR", "Croatia",  "South-Eastern Europe", "EUR", 8.0,  0.050, 60),
    ],
    columns=["country_code", "country", "region", "currency", "base_m", "growth", "n_cust"],
)
ORTHODOX = {"BG", "RO", "GR", "RS"}

# --------------------------------------------------------------------------
# FX: local currency units per 1 EUR, monthly average
# --------------------------------------------------------------------------
fx_anchor = {  # (Jan-2023 level, Sep-2026 level, monthly noise sd as % of level)
    "PLN": (4.72, 4.27, 0.008),
    "RON": (4.92, 5.09, 0.002),
    "CZK": (24.0, 24.55, 0.007),
    "HUF": (382.0, 418.0, 0.006),
    "RSD": (117.3, 117.15, 0.0005),
}
fx_rows = []
n_m = len(MONTHS)
for cur, (a, b, sd) in fx_anchor.items():
    # smooth trend + autocorrelated noise (3-month moving average of shocks)
    shocks = np.convolve(rng.normal(0, sd, n_m + 2), np.ones(3) / 3, mode="valid")
    path = np.linspace(a, b, n_m) * (1 + shocks)
    for m, r in zip(MONTHS, path):
        fx_rows.append((m.date(), cur, round(float(r), 4)))
for m in MONTHS:
    fx_rows.append((m.date(), "EUR", 1.0))
    # Bulgaria: currency board peg until euro adoption on 1 Jan 2026
    if m < pd.Timestamp("2026-01-01"):
        fx_rows.append((m.date(), "BGN", 1.95583))
fx = pd.DataFrame(fx_rows, columns=["month", "currency", "lcy_per_eur"])


def country_currency(cc: str, d: pd.Timestamp) -> str:
    if cc == "BG":
        return "BGN" if d < pd.Timestamp("2026-01-01") else "EUR"
    return countries.set_index("country_code").at[cc, "currency"]


fx_lookup = {(r.month, r.currency): r.lcy_per_eur for r in fx.itertuples()}

# --------------------------------------------------------------------------
# Categories, brands, products
# --------------------------------------------------------------------------
cat_def = [
    # id, name, revenue share, price range EUR/case, base GM% (vs list), brands, variants, packs
    ("BEV", "Beverages", 0.24, (7, 18), 0.335, ["AquaPeak", "Citrella", "Fizzo", "VitaPress"],
     ["Still Water", "Sparkling Water", "Orange Juice", "Apple Juice", "Cola", "Lemonade", "Iced Tea Peach",
      "Energy Drink", "Multivitamin Juice", "Tonic"], ["6x1.5L", "12x0.5L", "24x0.33L"]),
    ("SNK", "Snacks & Confectionery", 0.20, (12, 32), 0.355, ["Crunchy Hills", "ChocoNova", "Nutty Bay", "Sweet Danube"],
     ["Milk Chocolate", "Dark Chocolate", "Wafer", "Salted Crisps", "Paprika Crisps", "Mixed Nuts", "Biscuits",
      "Protein Bar", "Gummies", "Pretzels"], ["24x40g", "12x100g", "10x200g"]),
    ("COF", "Coffee & Tea", 0.14, (20, 60), 0.365, ["Black Ridge", "Aroma Bianca", "Leafline", "Kavanta"],
     ["Espresso Beans", "Ground Classic", "Instant Gold", "Capsules Lungo", "Capsules Ristretto", "Green Tea",
      "Black Tea", "Herbal Tea", "Decaf Ground", "Cold Brew"], ["6x250g", "8x500g", "10x1kg"]),
    ("HOM", "Home Care", 0.16, (14, 40), 0.325, ["Sparkla", "CleanWave", "Lumio Home", "OxyGuard"],
     ["Dish Liquid", "Laundry Gel", "Laundry Powder", "Surface Spray", "Glass Cleaner", "Fabric Softener",
      "Toilet Cleaner", "Dishwasher Tabs", "Bleach", "Stain Remover"], ["8x1L", "4x3L", "12x500ml"]),
    ("PER", "Personal Care", 0.16, (18, 45), 0.375, ["Velora", "Aquasilk", "Dermaline", "NordFresh"],
     ["Shampoo", "Conditioner", "Shower Gel", "Deodorant", "Toothpaste", "Hand Soap", "Body Lotion",
      "Sun Cream SPF50", "Face Cream", "Razor Blades"], ["12x250ml", "6x400ml", "24x75ml"]),
    ("BAB", "Baby Care", 0.10, (24, 62), 0.335, ["Little Bloom", "TinySteps", "SoftCloud"],
     ["Diapers S3", "Diapers S4", "Diapers S5", "Baby Wipes", "Baby Shampoo", "Baby Lotion", "Infant Cereal",
      "Baby Puree", "Diaper Pants", "Nappy Cream"], ["4x packs", "6x packs", "12x units"]),
]
categories = pd.DataFrame(
    [(c[0], c[1], c[2]) for c in cat_def], columns=["category_id", "category", "share"]
)

# list-price and standard-cost indices by year (2023 = 1.00)
price_idx = {
    "BEV": [1.00, 1.040, 1.070, 1.095], "SNK": [1.00, 1.060, 1.130, 1.180],
    "COF": [1.00, 1.050, 1.150, 1.230], "HOM": [1.00, 1.035, 1.065, 1.090],
    "PER": [1.00, 1.040, 1.070, 1.095], "BAB": [1.00, 1.040, 1.075, 1.100],
}
cost_idx = {
    "BEV": [1.00, 1.035, 1.060, 1.082], "SNK": [1.00, 1.090, 1.200, 1.190],
    "COF": [1.00, 1.070, 1.220, 1.270], "HOM": [1.00, 1.030, 1.055, 1.078],
    "PER": [1.00, 1.035, 1.060, 1.085], "BAB": [1.00, 1.035, 1.065, 1.090],
}

prod_rows, cost_rows = [], []
sku_n = 1000
for cid, cname, share, (plo, phi), gm, brands, variants, packs in cat_def:
    combos = [(b, v, p) for b in brands for v in variants for p in packs]
    idx = rng.choice(len(combos), size=30, replace=False)
    for rank, i in enumerate(idx):
        b, v, p = combos[i]
        sku_n += 1
        sku = f"{cid}-{sku_n}"
        lp = round(float(rng.uniform(plo, phi)), 2)
        g = gm + rng.normal(0, 0.025)
        cost = round(lp * (1 - g), 2)
        launch, disc, status = date(2019, 1, 1), None, "Active"
        u = rng.random()
        if u < 0.06:
            launch = (pd.Timestamp("2024-03-01") + pd.Timedelta(days=int(rng.integers(0, 540)))).date()
            status = "New"
        elif u < 0.11:
            disc = (pd.Timestamp("2024-04-01") + pd.Timedelta(days=int(rng.integers(0, 520)))).date()
            status = "Discontinued"
        prod_rows.append((sku, f"{b} {v} {p}", b, cid, v, p, lp, launch, disc, status))
        for yi, y in enumerate(YEARS):
            cost_rows.append((sku, y, round(cost * cost_idx[cid][yi] * (1 + rng.normal(0, 0.008)), 2),
                              round(lp * price_idx[cid][yi], 2)))
products = pd.DataFrame(
    prod_rows,
    columns=["sku", "product_name", "brand", "category_id", "variant", "pack_size", "list_price_2023_eur",
             "launch_date", "discontinued_date", "status"],
)
prod_prices = pd.DataFrame(cost_rows, columns=["sku", "year", "std_cost_eur", "list_price_eur"])
products["popularity"] = 0.0
for cid in categories.category_id:
    m = products.category_id == cid
    k = m.sum()
    w = 1 / np.arange(1, k + 1) ** 0.85
    products.loc[m, "popularity"] = rng.permutation(w)

# --------------------------------------------------------------------------
# Warehouses
# --------------------------------------------------------------------------
warehouses = pd.DataFrame(
    [
        ("PL-WAW", "Warsaw DC", "PL", "Warsaw", 52.23, 21.01),
        ("PL-POZ", "Poznan DC", "PL", "Poznan", 52.41, 16.93),
        ("RO-BUC", "Bucharest DC", "RO", "Bucharest", 44.43, 26.10),
        ("RO-CLJ", "Cluj DC", "RO", "Cluj-Napoca", 46.77, 23.62),
        ("CZ-PRG", "Prague DC", "CZ", "Prague", 50.08, 14.43),
        ("HU-BUD", "Budapest DC", "HU", "Budapest", 47.50, 19.04),
        ("GR-ATH", "Athens DC", "GR", "Athens", 37.98, 23.73),
        ("BG-SOF", "Sofia DC", "BG", "Sofia", 42.70, 23.32),
        ("RS-BEG", "Belgrade DC", "RS", "Belgrade", 44.79, 20.45),
        ("HR-ZAG", "Zagreb DC", "HR", "Zagreb", 45.81, 15.98),
    ],
    columns=["warehouse_code", "warehouse", "country_code", "city", "lat", "lon"],
)

# --------------------------------------------------------------------------
# Customers & sales reps
# --------------------------------------------------------------------------
cities = {
    "PL": [("Warsaw", "PL-WAW"), ("Lodz", "PL-WAW"), ("Lublin", "PL-WAW"), ("Gdansk", "PL-WAW"),
           ("Krakow", "PL-WAW"), ("Poznan", "PL-POZ"), ("Wroclaw", "PL-POZ"), ("Szczecin", "PL-POZ")],
    "RO": [("Bucharest", "RO-BUC"), ("Constanta", "RO-BUC"), ("Iasi", "RO-BUC"), ("Brasov", "RO-BUC"),
           ("Cluj-Napoca", "RO-CLJ"), ("Timisoara", "RO-CLJ"), ("Oradea", "RO-CLJ")],
    "CZ": [("Prague", "CZ-PRG"), ("Brno", "CZ-PRG"), ("Ostrava", "CZ-PRG"), ("Plzen", "CZ-PRG")],
    "HU": [("Budapest", "HU-BUD"), ("Debrecen", "HU-BUD"), ("Szeged", "HU-BUD"), ("Gyor", "HU-BUD")],
    "GR": [("Athens", "GR-ATH"), ("Thessaloniki", "GR-ATH"), ("Patras", "GR-ATH"), ("Heraklion", "GR-ATH")],
    "BG": [("Sofia", "BG-SOF"), ("Plovdiv", "BG-SOF"), ("Varna", "BG-SOF"), ("Burgas", "BG-SOF"),
           ("Ruse", "BG-SOF")],
    "RS": [("Belgrade", "RS-BEG"), ("Novi Sad", "RS-BEG"), ("Nis", "RS-BEG")],
    "HR": [("Zagreb", "HR-ZAG"), ("Split", "HR-ZAG"), ("Rijeka", "HR-ZAG")],
}
rep_names = {
    "PL": ["Anna Kowalska", "Piotr Nowak", "Marta Wisniewska", "Tomasz Zielinski", "Kasia Lewandowska"],
    "RO": ["Andrei Popescu", "Ioana Ionescu", "Mihai Dumitru", "Elena Stan", "Radu Georgescu"],
    "CZ": ["Jan Novak", "Petra Svobodova", "Tomas Dvorak", "Lucie Cerna"],
    "HU": ["Bence Nagy", "Zsofia Kovacs", "Gabor Toth", "Eszter Szabo"],
    "GR": ["Nikos Papadopoulos", "Maria Georgiou", "Dimitris Nikolaou", "Eleni Christou"],
    "BG": ["Ivan Petrov", "Maria Dimitrova", "Georgi Ivanov", "Elena Stoyanova"],
    "RS": ["Marko Jovanovic", "Jelena Petrovic", "Nikola Nikolic"],
    "HR": ["Luka Horvat", "Ana Kovacevic", "Ivan Babic"],
}
managers = {
    "PL": "Agnieszka Wojcik", "RO": "Cristina Marin", "CZ": "Martin Prochazka", "HU": "Laszlo Varga",
    "GR": "Yannis Alexiou", "BG": "Stefan Iliev", "RS": "Milos Stojanovic", "HR": "Petra Juric",
}
channels = {
    # channel: (customer share, revenue share base 2023, lognormal sigma, yearly revenue trend)
    "Modern Trade": (0.045, 0.43, 0.55, 0.035),
    "Traditional Trade": (0.48, 0.25, 0.70, -0.030),
    "HoReCa": (0.22, 0.11, 0.65, 0.040),
    "Pharmacy & Drugstore": (0.15, 0.13, 0.60, 0.050),
    "E-commerce": (0.095, 0.08, 0.80, 0.320),
}
# category affinity by channel (relative propensity)
affinity = {
    "Modern Trade":        {"BEV": 1.0, "SNK": 1.0, "COF": 1.0, "HOM": 1.0, "PER": 1.0, "BAB": 1.0},
    "Traditional Trade":   {"BEV": 1.4, "SNK": 1.4, "COF": 1.0, "HOM": 0.8, "PER": 0.7, "BAB": 0.5},
    "HoReCa":              {"BEV": 2.2, "SNK": 0.8, "COF": 2.6, "HOM": 0.6, "PER": 0.1, "BAB": 0.02},
    "Pharmacy & Drugstore": {"BEV": 0.15, "SNK": 0.2, "COF": 0.1, "HOM": 0.7, "PER": 2.6, "BAB": 3.0},
    "E-commerce":          {"BEV": 0.7, "SNK": 0.9, "COF": 1.5, "HOM": 1.1, "PER": 1.3, "BAB": 1.6},
}
key_account_names = ["HyperNova", "Prima Retail", "CityMart", "EuroSave Discount", "FamilyFresh",
                     "MegaBasket", "UrbanGrocer", "ValueWay"]
trad_words = ["Mini Market", "Corner Shop", "Grocery", "Food Store", "Express Shop", "Neighbourhood Store"]
horeca_words = ["Hotel", "Cafe", "Bistro", "Catering", "Restaurant Group", "Coffee Bar"]
pharma_words = ["Pharmacy", "Drugstore", "Health & Beauty", "Apothecary"]
ecom_words = ["Online", "eShop", "Delivery", "Marketplace", "Quick Commerce"]
name_stems = ["Aurora", "Delta", "Orion", "Sunrise", "Riverside", "Green Valley", "Central", "Royal", "Star",
              "Golden", "Lotus", "Vega", "Nova", "Alpine", "Harbor", "Linden", "Crystal", "Union", "Echo",
              "Maple", "Silver", "Atlas", "Zenith", "Horizon", "Meridian", "Solaris", "Amber", "Cedar", "Pinnacle"]

cust_rows = []
cid_n = 10000
for c in countries.itertuples():
    reps = rep_names[c.country_code]
    n = c.n_cust
    ch_names = list(channels)
    ch_p = np.array([channels[k][0] for k in ch_names])
    ch_assign = rng.choice(ch_names, size=n, p=ch_p / ch_p.sum())
    ch_assign[: max(4, int(n * 0.03))] = "Modern Trade"  # guarantee key accounts per country
    ka_pool = list(rng.permutation(key_account_names))
    for i in range(n):
        cid_n += 1
        ch = ch_assign[i]
        city, wh = cities[c.country_code][int(rng.integers(0, len(cities[c.country_code])))]
        if ch == "Modern Trade":
            if ka_pool:
                nm = f"{ka_pool.pop()} {c.country_code}"
            else:
                nm = f"{rng.choice(name_stems)} Supermarkets {city}"
        elif ch == "Traditional Trade":
            nm = f"{rng.choice(name_stems)} {rng.choice(trad_words)} {city}"
        elif ch == "HoReCa":
            nm = f"{rng.choice(name_stems)} {rng.choice(horeca_words)} {city}"
        elif ch == "Pharmacy & Drugstore":
            nm = f"{rng.choice(name_stems)} {rng.choice(pharma_words)} {city}"
        else:
            nm = f"{rng.choice(name_stems)} {rng.choice(ecom_words)} {c.country_code}"
        u = rng.random()
        if u < 0.72:
            since = (pd.Timestamp("2012-01-01") + pd.Timedelta(days=int(rng.integers(0, 3900)))).date()
        else:
            since = (START + pd.Timedelta(days=int(rng.integers(0, (END_ACT - START).days - 60)))).date()
        churn = None
        if rng.random() < 0.11:
            lo = max(pd.Timestamp(since) + pd.Timedelta(days=200), START + pd.Timedelta(days=60))
            if lo < END_ACT - pd.Timedelta(days=30):
                churn = (lo + pd.Timedelta(days=int(rng.integers(0, max(1, (END_ACT - lo).days))))).date()
        sigma = channels[ch][2]
        cust_rows.append((f"C{cid_n}", nm, c.country_code, city, wh, ch, str(rng.choice(reps)), since, churn,
                          float(rng.lognormal(0, sigma))))
customers = pd.DataFrame(
    cust_rows,
    columns=["customer_code", "customer_name", "country_code", "city", "warehouse_code", "channel", "sales_rep",
             "customer_since", "churn_date", "w"],
)
# de-duplicate names (append a store number)
dup = customers.duplicated("customer_name", keep=False)
customers.loc[dup, "customer_name"] = (customers.loc[dup, "customer_name"] + " #" +
                                        customers.loc[dup].groupby("customer_name").cumcount().add(1).astype(str))
# normalise weights so each channel's total weight = its base revenue share (per country)
for cc in countries.country_code:
    for ch, (_, rshare, _, _) in channels.items():
        m = (customers.country_code == cc) & (customers.channel == ch)
        if m.sum():
            customers.loc[m, "w"] = customers.loc[m, "w"] / customers.loc[m, "w"].sum() * rshare

# --------------------------------------------------------------------------
# Seasonality, Easter, weekday effects
# --------------------------------------------------------------------------
season = {  # Jan..Dec index by category
    "BEV": [0.74, 0.76, 0.88, 0.96, 1.08, 1.30, 1.40, 1.34, 1.04, 0.90, 0.80, 0.98],
    "SNK": [0.82, 0.86, 0.96, 1.02, 0.90, 0.84, 0.82, 0.86, 0.98, 1.08, 1.30, 1.56],
    "COF": [1.12, 1.04, 1.00, 0.96, 0.92, 0.86, 0.84, 0.88, 0.98, 1.06, 1.12, 1.20],
    "HOM": [0.92, 0.96, 1.10, 1.12, 1.04, 0.98, 0.94, 0.94, 1.00, 1.02, 0.98, 1.00],
    "PER": [0.88, 0.90, 0.96, 1.00, 1.06, 1.16, 1.14, 1.04, 0.94, 0.94, 1.00, 1.18],
    "BAB": [0.98, 0.97, 1.00, 1.00, 1.01, 1.00, 0.99, 1.00, 1.01, 1.02, 1.01, 1.02],
}
easter_w = {2023: date(2023, 4, 9), 2024: date(2024, 3, 31), 2025: date(2025, 4, 20), 2026: date(2026, 4, 5)}
easter_o = {2023: date(2023, 4, 16), 2024: date(2024, 5, 5), 2025: date(2025, 4, 20), 2026: date(2026, 4, 12)}
wd_w = np.array([1.15, 1.10, 1.06, 1.05, 1.00, 0.42, 0.08])


def day_weights(days: pd.DatetimeIndex, cc: str, cat: str) -> np.ndarray:
    w = wd_w[days.dayofweek.values].copy()
    for i, d in enumerate(days):
        if (d.month, d.day) in {(1, 1), (12, 25), (12, 26)}:
            w[i] = 0.05
        if cat in ("SNK", "BEV"):
            e = (easter_o if cc in ORTHODOX else easter_w)[d.year]
            delta = (e - d.date()).days
            if 1 <= delta <= 16:
                w[i] *= 1.45 if cat == "SNK" else 1.15
    return w


# --------------------------------------------------------------------------
# Monthly value targets (EUR) per country x category
# --------------------------------------------------------------------------
def month_index(m: pd.Timestamp) -> float:
    return (m.year - 2023) + (m.month - 1) / 12


target = {}
cat_noise = {k: rng.normal(0, 0.035, n_m) for k in categories.category_id}
for c in countries.itertuples():
    ctry_noise = rng.normal(0, 0.03, n_m)
    for k in categories.itertuples():
        for mi, m in enumerate(MONTHS):
            t = month_index(m)
            g = c.growth
            base_month = c.base_m * 1e6 / 12 * k.share
            v = base_month * (1 + g) ** t * season[k.category_id][m.month - 1]
            if c.country_code == "BG" and m >= pd.Timestamp("2026-01-01"):
                v *= 1.035  # euro adoption tailwind (one-off level shift)
            if c.country_code == "RO" and pd.Timestamp("2026-01-01") <= m <= pd.Timestamp("2026-05-31"):
                v *= 0.93   # volume lost during the Bucharest DC crisis
            v *= (1 + ctry_noise[mi]) * (1 + cat_noise[k.category_id][mi])
            target[(m, c.country_code, k.category_id)] = v

# promo / discount policy
base_disc = {"Modern Trade": 0.13, "Traditional Trade": 0.05, "HoReCa": 0.075, "Pharmacy & Drugstore": 0.095,
             "E-commerce": 0.085}
promo_rate = {"Modern Trade": 0.24, "Traditional Trade": 0.06, "HoReCa": 0.05, "Pharmacy & Drugstore": 0.18,
              "E-commerce": 0.20}

# operations parameters
def on_time_prob(wh: str, d: pd.Timestamp, ch: str) -> float:
    p = 0.955 if ch != "Traditional Trade" else 0.94
    if wh == "RO-BUC" and pd.Timestamp("2026-01-05") <= d <= pd.Timestamp("2026-05-31"):
        p = 0.74 if d.month in (2, 3, 4) else 0.83
    if d.month == 12 and d.day >= 15:
        p -= 0.05
    if wh == "GR-ATH" and d.month in (7, 8):
        p -= 0.03
    return p


def in_full_prob(cat: str, d: pd.Timestamp, wh: str) -> float:
    p = 0.968
    if cat == "COF" and pd.Timestamp("2025-10-01") <= d <= pd.Timestamp("2025-12-31"):
        p = 0.78
    if wh == "RO-BUC" and pd.Timestamp("2026-01-05") <= d <= pd.Timestamp("2026-05-31"):
        p -= 0.07
    return p


# --------------------------------------------------------------------------
# Generate order lines
# --------------------------------------------------------------------------
lines = []
avg_line_eur = 3600.0
cust_by_cc = {cc: g.reset_index(drop=True) for cc, g in customers.groupby("country_code")}
prod_by_cat = {k: g.reset_index(drop=True) for k, g in products.groupby("category_id")}
pp = prod_prices.set_index(["sku", "year"])

for mi, m in enumerate(MONTHS):
    m_end = m + pd.offsets.MonthEnd(0)
    days = pd.date_range(m, m_end, freq="D")
    t = month_index(m)
    for cc in countries.country_code:
        cust = cust_by_cc[cc]
        since = pd.to_datetime(cust.customer_since)
        churn = pd.to_datetime(cust.churn_date)
        active = (since <= m_end) & (churn.isna() | (churn >= m))
        ch_trend = cust.channel.map({k: (1 + v[3]) ** t for k, v in channels.items()}).values
        for k in categories.category_id:
            T = target[(m, cc, k)]
            n = max(5, int(rng.poisson(T / avg_line_eur)))
            dw = day_weights(days, cc, k)
            d_idx = rng.choice(len(days), size=n, p=dw / dw.sum())
            aff = cust.channel.map({ch: affinity[ch][k] for ch in affinity}).values
            w = cust.w.values * aff * ch_trend * active.values
            p_sel = w ** 0.62
            p_sel = p_sel / p_sel.sum()
            ci = rng.choice(len(cust), size=n, p=p_sel)
            prods = prod_by_cat[k]
            launch = pd.to_datetime(prods.launch_date)
            disc = pd.to_datetime(prods.discontinued_date)
            alive = (launch <= m_end) & (disc.isna() | (disc >= m))
            pw = prods.popularity.values * alive.values
            si = rng.choice(len(prods), size=n, p=pw / pw.sum())
            # value allocation: bigger customers place bigger orders
            s = (cust.w.values[ci] ** 0.38) * rng.lognormal(0, 0.55, n)
            val = T * s / s.sum()
            chs = cust.channel.values[ci]
            yr = m.year
            lp = np.array([pp.at[(sku, yr), "list_price_eur"] for sku in prods.sku.values[si]])
            d_base = np.array([base_disc[c] for c in chs]) + rng.normal(0, 0.012, n)
            pr = np.array([promo_rate[c] for c in chs])
            if k == "PER" and pd.Timestamp("2026-04-01") <= m <= pd.Timestamp("2026-07-31"):
                pr = pr * 2.1   # aggressive promo push
            promo = rng.random(n) < pr
            d_promo = np.where(promo, rng.uniform(0.08, 0.17, n), 0.0)
            if k == "PER" and pd.Timestamp("2026-04-01") <= m <= pd.Timestamp("2026-07-31"):
                d_promo = np.where(promo, rng.uniform(0.12, 0.22, n), 0.0)
            disc_pct = np.clip(d_base + d_promo, 0, 0.38).round(4)
            net_unit = lp * (1 - disc_pct)
            qty = np.maximum(1, np.round(val / net_unit)).astype(int)
            dates = days[d_idx]
            whs = cust.warehouse_code.values[ci]
            for j in range(n):
                lines.append((dates[j], cc, cust.customer_code.values[ci[j]], prods.sku.values[si[j]], whs[j],
                              chs[j], int(qty[j]), float(lp[j]), float(disc_pct[j]), bool(promo[j])))

sales = pd.DataFrame(lines, columns=["order_date", "country_code", "customer_code", "sku", "warehouse_code",
                                     "channel", "qty_ordered", "list_price_eur", "discount_pct", "promo_flag"])
sales["category_id"] = sales.sku.str[:3]
print("order lines generated:", len(sales))

# --- fulfilment: promised / delivered dates and quantities
n = len(sales)
lead = np.where(sales.channel.isin(["Modern Trade", "E-commerce"]), 2,
                np.where(sales.channel == "Traditional Trade", 3, 2))
sales["promised_date"] = sales.order_date + pd.to_timedelta(lead, unit="D")
p_on = np.array([on_time_prob(w, d, c) for w, d, c in zip(sales.warehouse_code, sales.order_date, sales.channel)])
on_time = rng.random(n) < p_on
delay = np.where(on_time, -rng.binomial(1, 0.15, n), rng.integers(1, 5, n))
sales["delivery_date"] = sales.promised_date + pd.to_timedelta(delay, unit="D")
sales["ship_date"] = sales.delivery_date - pd.to_timedelta(np.where(lead == 3, 2, 1), unit="D")
sales.loc[sales.ship_date < sales.order_date, "ship_date"] = sales.order_date
p_full = np.array([in_full_prob(k, d, w) for k, d, w in zip(sales.category_id, sales.order_date,
                                                              sales.warehouse_code)])
in_full = rng.random(n) < p_full
short = np.floor(sales.qty_ordered * rng.uniform(0.55, 0.95, n)).astype(int)
sales["qty_delivered"] = np.where(in_full, sales.qty_ordered, short)

# --- order ids (one order = customer x day)
sales = sales.sort_values(["order_date", "country_code", "customer_code", "sku"]).reset_index(drop=True)
okey = sales.order_date.dt.strftime("%Y%m%d") + sales.customer_code
codes, uniq = pd.factorize(okey, sort=False)
sales["order_id"] = [f"SO-{sales.country_code[i]}-{codes[i] + 1:07d}" for i in range(n)]
sales["line_no"] = sales.groupby("order_id").cumcount() + 1
# a customer can't order the same sku twice in one order: merge such lines
sales = (sales.groupby(["order_id", "sku"], as_index=False)
         .agg({"order_date": "first", "country_code": "first", "customer_code": "first",
               "warehouse_code": "first", "channel": "first", "category_id": "first",
               "qty_ordered": "sum", "qty_delivered": "sum", "list_price_eur": "first",
               "discount_pct": "first", "promo_flag": "first", "promised_date": "first",
               "ship_date": "first", "delivery_date": "first"}))
sales = sales.sort_values(["order_date", "order_id", "sku"]).reset_index(drop=True)
sales["line_no"] = sales.groupby("order_id").cumcount() + 1

# --- local currency (ERP books in LCY)
sales["month"] = sales.order_date.dt.to_period("M").dt.to_timestamp().dt.date
sales["currency"] = [country_currency(cc, d) for cc, d in zip(sales.country_code, sales.order_date)]
rate = np.array([fx_lookup[(mm, cur)] for mm, cur in zip(sales.month, sales.currency)])
sales["unit_list_price_lcy"] = (sales.list_price_eur * rate).round(2)

# --------------------------------------------------------------------------
# Inject data-quality defects into the RAW extract
# --------------------------------------------------------------------------
raw = sales[["order_id", "line_no", "order_date", "customer_code", "sku", "warehouse_code", "country_code",
             "currency", "qty_ordered", "qty_delivered", "unit_list_price_lcy", "discount_pct", "promo_flag",
             "promised_date", "ship_date", "delivery_date"]].copy()
dq_log = {}
# 1) exact duplicate lines (double-posted interface records)
dups = raw.sample(frac=0.0035, random_state=1)
dq_log["duplicate_lines"] = len(dups)
# 2) orphan SKUs (SKU not yet in product master)
orph = raw.sample(n=140, random_state=2).index
raw.loc[orph, "sku"] = raw.loc[orph, "sku"].str.replace(r"-(\d+)$", r"-9\1", regex=True)
dq_log["orphan_sku"] = len(orph)
# 3) negative quantities (returns keyed as negative order lines)
neg = raw.drop(orph).sample(n=95, random_state=3).index
raw.loc[neg, ["qty_ordered", "qty_delivered"]] = -raw.loc[neg, ["qty_ordered", "qty_delivered"]].abs()
dq_log["negative_qty"] = len(neg)
# 4) delivery before order date (manual date entry errors)
bad_dt = raw.drop(orph).drop(neg).sample(n=180, random_state=4).index
raw.loc[bad_dt, "delivery_date"] = raw.loc[bad_dt, "order_date"] - pd.to_timedelta(
    rng.integers(1, 30, len(bad_dt)), unit="D")
dq_log["delivery_before_order"] = len(bad_dt)
# 5) missing discount (null) - should default to channel policy
miss_disc = raw.sample(n=260, random_state=5).index
raw.loc[miss_disc, "discount_pct"] = np.nan
dq_log["missing_discount"] = len(miss_disc)
raw = pd.concat([raw, dups], ignore_index=True).sort_values(["order_date", "order_id", "line_no"])

for y in YEARS:
    part = raw[pd.to_datetime(raw.order_date).dt.year == y].copy()
    for col in ["order_date", "promised_date", "ship_date", "delivery_date"]:
        part[col] = pd.to_datetime(part[col]).dt.strftime("%Y-%m-%d")
    part.to_csv(os.path.join(OUT, f"erp_sales_lines_{y}.csv"), index=False)

# customers: missing channel + inconsistent casing on country codes
cust_raw = customers.drop(columns="w").copy()
mc = cust_raw.sample(n=14, random_state=6).index
cust_raw.loc[mc, "channel"] = np.nan
lc = cust_raw.drop(mc).sample(n=9, random_state=7).index
cust_raw.loc[lc, "country_code"] = cust_raw.loc[lc, "country_code"].str.lower() + " "
dq_log["customer_missing_channel"] = len(mc)
dq_log["customer_bad_country_code"] = len(lc)
cust_raw.to_csv(os.path.join(OUT, "crm_customers.csv"), index=False)

products.drop(columns="popularity").to_csv(os.path.join(OUT, "pim_products.csv"), index=False)
prod_prices.to_csv(os.path.join(OUT, "erp_price_cost_list.csv"), index=False)
categories[["category_id", "category"]].to_csv(os.path.join(OUT, "pim_categories.csv"), index=False)
warehouses.to_csv(os.path.join(OUT, "wms_warehouses.csv"), index=False)
fx.to_csv(os.path.join(OUT, "treasury_fx_monthly.csv"), index=False)
ctry = countries[["country_code", "country", "region", "currency"]].copy()
ctry["country_manager"] = ctry.country_code.map(managers)
ctry["manager_email"] = "manager." + ctry.country_code.str.lower() + "@danubia-demo.com"
ctry.to_csv(os.path.join(OUT, "mdm_countries.csv"), index=False)

# --------------------------------------------------------------------------
# Budget (sales & gross margin), set before each year starts
# --------------------------------------------------------------------------
budget_bias = {  # >0 = budget too ambitious
    2023: {"PL": 0.01, "RO": 0.00, "CZ": 0.02, "HU": 0.02, "GR": 0.00, "BG": 0.01, "RS": -0.01, "HR": 0.01},
    2024: {"PL": 0.02, "RO": -0.02, "CZ": 0.01, "HU": 0.04, "GR": 0.01, "BG": 0.00, "RS": -0.02, "HR": 0.00},
    2025: {"PL": 0.01, "RO": -0.03, "CZ": 0.02, "HU": 0.06, "GR": 0.00, "BG": 0.01, "RS": -0.01, "HR": 0.01},
    2026: {"PL": 0.02, "RO": 0.05, "CZ": 0.01, "HU": 0.08, "GR": 0.01, "BG": 0.01, "RS": -0.02, "HR": 0.00},
}
budget_gm = {"BEV": 0.248, "SNK": 0.265, "COF": 0.288, "HOM": 0.234, "PER": 0.290, "BAB": 0.240}
bud_rows = []
for c in countries.itertuples():
    for k in categories.itertuples():
        for y in YEARS:
            for mo in range(1, 13):
                m = pd.Timestamp(year=y, month=mo, day=1)
                t = month_index(m)
                v = (c.base_m * 1e6 / 12 * k.share * (1 + c.growth) ** t * season[k.category_id][mo - 1])
                v *= 0.985 * (1 + budget_bias[y][c.country_code] + rng.normal(0, 0.01))
                gmp = budget_gm[k.category_id] + rng.normal(0, 0.004)
                bud_rows.append((m.date(), c.country_code, k.category_id, round(v, 2), round(v * gmp, 2)))
budget = pd.DataFrame(bud_rows, columns=["month", "country_code", "category_id", "budget_net_sales_eur",
                                         "budget_gross_margin_eur"])
budget.to_csv(os.path.join(OUT, "fpa_budget_sales.csv"), index=False)

# --------------------------------------------------------------------------
# Operating expenses (GL actuals + budget), EUR
# --------------------------------------------------------------------------
sales["net_eur"] = sales.qty_delivered * sales.list_price_eur * (1 - sales.discount_pct)
ns_m = sales.groupby(["month", "country_code"]).net_eur.sum()
bud_m = budget.groupby(["month", "country_code"]).budget_net_sales_eur.sum()
accounts = [("6100", "Logistics & Transport", 0.052), ("6200", "Warehousing", 0.030),
            ("6300", "Sales & Marketing", 0.058), ("6400", "General & Administrative", 0.035)]
opex_rows = []
for (m, cc), ns in ns_m.items():
    mt = pd.Timestamp(m)
    for acc, name, rt in accounts:
        r = rt * (1 + rng.normal(0, 0.05))
        if acc == "6100" and cc == "RO" and pd.Timestamp("2026-01-01") <= mt <= pd.Timestamp("2026-06-30"):
            r *= 1.42  # 3PL overflow + overtime during DC crisis
        if acc == "6100" and mt.year >= 2025:
            r *= 1.03  # fuel & tolls
        if acc == "6400":
            r = rt * 0.75 + 0.25 * rt * (bud_m.get((m, cc), ns) / ns)  # partly fixed
        opex_rows.append((m, cc, acc, "Actual", round(ns * r, 2)))
for (m, cc), bns in bud_m.items():
    for acc, name, rt in accounts:
        opex_rows.append((m, cc, acc, "Budget", round(bns * rt * 0.985, 2)))
opex = pd.DataFrame(opex_rows, columns=["month", "country_code", "account_code", "scenario", "amount_eur"])
opex.to_csv(os.path.join(OUT, "gl_opex_monthly.csv"), index=False)
pd.DataFrame(accounts, columns=["account_code", "account_name", "plan_rate"]).drop(columns="plan_rate") \
    .to_csv(os.path.join(OUT, "gl_accounts.csv"), index=False)

# --------------------------------------------------------------------------
# Inventory month-end snapshots (WMS)
# --------------------------------------------------------------------------
sales["ship_qty"] = sales.qty_delivered
mq = sales.groupby(["month", "warehouse_code", "sku"]).ship_qty.sum().rename("q").reset_index()
mq["month"] = pd.to_datetime(mq.month)
inv_rows = []
cost_map = prod_prices.set_index(["sku", "year"]).std_cost_eur
disc_map = products.set_index("sku").discontinued_date
all_keys = mq[["warehouse_code", "sku"]].drop_duplicates()
mq_idx = mq.set_index(["month", "warehouse_code", "sku"]).q
for m in MONTHS:
    me = (m + pd.offsets.MonthEnd(0)).date()
    dim = (m + pd.offsets.MonthEnd(0)).day
    for wh, sku in all_keys.itertuples(index=False):
        q = mq_idx.get((m, wh, sku), 0.0)
        q3 = np.mean([mq_idx.get((m - pd.DateOffset(months=i), wh, sku), 0.0) for i in range(3)])
        dd = disc_map.get(sku)
        is_disc = dd is not None and not pd.isna(dd) and pd.Timestamp(dd) < m
        if q3 == 0 and not is_disc:
            continue
        daily = max(q3, 1) / dim
        doi = rng.normal(38, 6)
        if sku.startswith("COF") and pd.Timestamp("2025-10-01") <= m <= pd.Timestamp("2025-12-31"):
            doi = rng.normal(9, 3)
        if wh == "RO-BUC" and pd.Timestamp("2026-01-01") <= m <= pd.Timestamp("2026-05-31"):
            doi = rng.normal(55, 8)  # receiving backlog -> stock piles up
        if is_disc:
            # discontinued items: residual stock ages and is only partially cleared
            months_since = (m.year - pd.Timestamp(dd).year) * 12 + m.month - pd.Timestamp(dd).month
            qty = int(max(0, rng.normal(1500, 220) * (0.965 ** months_since)))
            so = 0
        else:
            qty = int(max(0, daily * doi))
            so = int(np.clip(rng.poisson(0.4 if doi > 15 else 6), 0, dim))
        if qty == 0 and so == 0:
            continue
        cst = cost_map.get((sku, m.year))
        inv_rows.append((me, wh, sku, qty, round(qty * cst, 2), so))
inventory = pd.DataFrame(inv_rows, columns=["snapshot_date", "warehouse_code", "sku", "on_hand_qty",
                                            "on_hand_value_eur", "stockout_days"])
inventory.to_csv(os.path.join(OUT, "wms_inventory_snapshot.csv"), index=False)

# --------------------------------------------------------------------------
# Load log (timeliness): Serbia's September feed arrived late & partial
# --------------------------------------------------------------------------
loads = []
for cc in countries.country_code:
    for m in MONTHS:
        me = m + pd.offsets.MonthEnd(0)
        lag = int(rng.integers(1, 3))
        if cc == "RS" and m == MONTHS[-1]:
            lag = 6
        loads.append((m.date(), cc, (me + pd.Timedelta(days=lag)).date(), lag))
pd.DataFrame(loads, columns=["period", "country_code", "loaded_on", "lag_days"]).to_csv(
    os.path.join(OUT, "etl_load_log.csv"), index=False)

pd.Series(dq_log).to_csv(os.path.join(OUT, "_injected_defects_reference.csv"), header=["rows"])
print("defects injected:", dq_log)
print("files:", sorted(os.listdir(OUT)))
