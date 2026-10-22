"""
Step 1b - Load the 8 Olist CSVs into the SQL Server tables made by sql/01_create_tables.sql.
Inputs : data/raw/*.csv  (Kaggle: olistbr/brazilian-ecommerce)
Output : rows in the DeliveryLens database on your SQL Server
Needs  : pip install pandas pyodbc
"""
from pathlib import Path
import pandas as pd
import pyodbc

# --- Block 1: settings ----------------------------------------------------
SERVER = "DESKTOP-0CCEUEQ"          # server name from the SSMS login screen
DATABASE = "DeliveryLens"

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

# Load order matters: parent tables before tables that reference them
TABLES = [
    ("customers",   "olist_customers_dataset.csv"),
    ("sellers",     "olist_sellers_dataset.csv"),
    ("products",    "olist_products_dataset.csv"),
    ("category_en", "product_category_name_translation.csv"),
    ("orders",      "olist_orders_dataset.csv"),
    ("order_items", "olist_order_items_dataset.csv"),
    ("payments",    "olist_order_payments_dataset.csv"),
    ("reviews",     "olist_order_reviews_dataset.csv"),
]
DATE_COLS = ["order_purchase_timestamp", "order_approved_at", "order_delivered_carrier_date",
             "order_delivered_customer_date", "order_estimated_delivery_date",
             "shipping_limit_date", "review_creation_date", "review_answer_timestamp"]
INT_COLS = ["product_name_lenght", "product_description_lenght", "product_photos_qty",
            "product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm"]

# --- Block 2: connect (picks the newest SQL Server ODBC driver installed) ---
drivers = [d for d in pyodbc.drivers() if "SQL Server" in d]
if not drivers:
    raise SystemExit("No SQL Server ODBC driver found. Install 'ODBC Driver 18 for SQL Server'.")
driver = sorted(drivers, key=lambda d: ("ODBC Driver" in d, d))[-1]
print(f"Using driver: {driver}")
con = pyodbc.connect(f"DRIVER={{{driver}}};SERVER={SERVER};DATABASE={DATABASE};"
                     "Trusted_Connection=yes;TrustServerCertificate=yes;")
cur = con.cursor()
cur.fast_executemany = True

# --- Block 3: empty the tables (children first) so the script can re-run ---
for table, _ in reversed(TABLES):
    cur.execute(f"DELETE FROM {table}")
con.commit()

# --- Block 4: read each CSV and insert ------------------------------------
for table, file in TABLES:
    # zip prefixes stay text (leading zeros); utf-8-sig drops the BOM in one file
    df = pd.read_csv(RAW / file, encoding="utf-8-sig",
                     dtype={"customer_zip_code_prefix": str, "seller_zip_code_prefix": str})
    for c in df.columns:
        if c in DATE_COLS:
            df[c] = pd.to_datetime(df[c])
        elif c in INT_COLS:
            df[c] = df[c].astype("Int64")
    # pyodbc needs None for missing values, and plain Python types
    df = df.astype(object).where(df.notna(), None)
    rows = [tuple(x.to_pydatetime() if isinstance(x, pd.Timestamp) else x for x in r)
            for r in df.itertuples(index=False)]
    cols = ", ".join(df.columns)
    marks = ", ".join("?" * len(df.columns))
    cur.executemany(f"INSERT INTO {table} ({cols}) VALUES ({marks})", rows)
    con.commit()
    n = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"{table:12s} {n:>8,} rows")

con.close()
print("Done. Check in SSMS: DeliveryLens > Tables")