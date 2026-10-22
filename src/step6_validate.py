"""
Step 6 - End-to-end validation.
Rebuilds the delivered-order table from the raw CSVs in pandas (no SQL), then
  A) compares it row by row with the SQL Server view vw_delivered_orders
  B) recomputes every headline number in the README from both sources and
     checks them against the values quoted in the README
Inputs : data/raw/*.csv, view vw_delivered_orders in SQL Server
Output : outputs/validation_report.csv  (one row per check, PASS / FAIL)
Needs  : pip install pandas pyodbc
"""
from pathlib import Path
import warnings
import numpy as np
import pandas as pd
import pyodbc

warnings.filterwarnings("ignore", category=UserWarning)

# --- Block 1: settings ----------------------------------------------------
SERVER, DATABASE = "DESKTOP-0CCEUEQ", "DeliveryLens"
ROOT = Path(__file__).resolve().parents[1]
RAW, OUT = ROOT / "data" / "raw", ROOT / "outputs"
PEAK = ["2017-11", "2018-02", "2018-03"]

# Numbers quoted in the README (value, allowed rounding error)
README = {
    "orders_kept":              (96018, 0),
    "late_orders":              (6528, 0),
    "late_pct":                 (6.8, 0.05),
    "late_handling_days":       (6.0, 0.05),
    "late_transit_days":        (27.9, 0.05),
    "ontime_handling_days":     (3.0, 0.05),
    "ontime_transit_days":      (8.0, 0.05),
    "late_missed_deadline_pct": (27.7, 0.05),
    "ontime_missed_deadline_pct": (7.6, 0.05),
    "peak_late_pct":            (15.1, 0.05),
    "other_late_pct":           (4.5, 0.05),
    "same_state_late_pct":      (4.6, 0.05),
    "diff_state_late_pct":      (8.2, 0.05),
    "late_pct_MA":              (17.6, 0.05),
    "late_pct_SP":              (4.5, 0.05),
    "late_pct_PR":              (4.1, 0.05),
    "late_pct_2017_11":         (12.4, 0.05),
    "late_pct_2018_03":         (19.0, 0.05),
    "pareto_sellers_50pct":     (98, 0),
    "n_single_sellers":         (2923, 0),
    "median_days_vs_promise":   (-12, 0),
    "multi_seller_orders":      (1249, 0),
}


# --- Block 2: source 1 = SQL Server view ----------------------------------
def load_sql():
    driver = sorted([d for d in pyodbc.drivers() if "SQL Server" in d],
                    key=lambda d: ("ODBC Driver" in d, d))[-1]
    con = pyodbc.connect(f"DRIVER={{{driver}}};SERVER={SERVER};DATABASE={DATABASE};"
                         "Trusted_Connection=yes;TrustServerCertificate=yes;")
    df = pd.read_sql("SELECT * FROM vw_delivered_orders", con)
    con.close()
    # DECIMAL/NUMERIC columns arrive as Python Decimal objects: make them floats
    for c in ["items_value", "freight_value", "handling_days", "transit_days", "total_days"]:
        df[c] = df[c].astype(float)
    return df


# --- Block 3: source 2 = pandas rebuild from the raw CSVs -----------------
# Same rules as sql/03_delivery_view.sql, written independently.
def load_pandas():
    dates = ["order_purchase_timestamp", "order_delivered_carrier_date",
             "order_delivered_customer_date", "order_estimated_delivery_date"]
    o = pd.read_csv(RAW / "olist_orders_dataset.csv", parse_dates=dates)
    it = pd.read_csv(RAW / "olist_order_items_dataset.csv", parse_dates=["shipping_limit_date"])
    cu = pd.read_csv(RAW / "olist_customers_dataset.csv", dtype=str)
    se = pd.read_csv(RAW / "olist_sellers_dataset.csv", dtype=str)
    rv = pd.read_csv(RAW / "olist_order_reviews_dataset.csv", parse_dates=["review_answer_timestamp"])

    rv = rv.sort_values("review_answer_timestamp").groupby("order_id").tail(1)[["order_id", "review_score"]]
    items = it.groupby("order_id").agg(n_items=("order_item_id", "size"), n_sellers=("seller_id", "nunique"),
                                       seller_id=("seller_id", "min"),
                                       shipping_limit_date=("shipping_limit_date", "max"),
                                       items_value=("price", "sum"), freight_value=("freight_value", "sum"))
    v = (o[o.order_status == "delivered"].merge(items.reset_index(), on="order_id")
         .merge(cu, on="customer_id").merge(se, on="seller_id").merge(rv, on="order_id", how="left"))
    v = v[v.order_delivered_carrier_date.notna() & v.order_delivered_customer_date.notna()
          & (v.order_delivered_carrier_date >= v.order_purchase_timestamp)
          & (v.order_delivered_customer_date >= v.order_delivered_carrier_date)
          & (v.order_purchase_timestamp >= "2017-01-01") & (v.order_purchase_timestamp < "2018-09-01")].copy()

    def days(a, b):   # SQL DATEDIFF(MINUTE) counts minute boundaries, so floor to the minute first
        return (v[b].dt.floor("min") - v[a].dt.floor("min")).dt.total_seconds() / 86400
    v["handling_days"] = days("order_purchase_timestamp", "order_delivered_carrier_date")
    v["transit_days"] = days("order_delivered_carrier_date", "order_delivered_customer_date")
    v["total_days"] = days("order_purchase_timestamp", "order_delivered_customer_date")
    v["promised_days"] = (v.order_estimated_delivery_date.dt.normalize()
                          - v.order_purchase_timestamp.dt.normalize()).dt.days
    v["days_vs_promise"] = (v.order_delivered_customer_date.dt.normalize()
                            - v.order_estimated_delivery_date.dt.normalize()).dt.days
    v["is_late"] = (v.days_vs_promise > 0).astype(int)
    v["seller_missed_deadline"] = (v.order_delivered_carrier_date > v.shipping_limit_date).astype(int)
    v["same_state"] = ((v.customer_state == v.seller_state) & (v.n_sellers == 1)).astype(int)
    v.loc[v.n_sellers > 1, ["seller_id", "seller_state"]] = None
    v["purchase_month"] = v.order_purchase_timestamp.dt.to_period("M").dt.to_timestamp()
    return v


# --- Block 4: headline metrics (same function for both sources) -----------
def metrics(df):
    m = {}
    df = df.copy()
    df["month"] = pd.to_datetime(df.purchase_month).dt.strftime("%Y-%m")
    late, ok = df[df.is_late == 1], df[df.is_late == 0]
    m["orders_kept"] = len(df)
    m["late_orders"] = int(df.is_late.sum())
    m["late_pct"] = 100 * df.is_late.mean()
    m["late_handling_days"], m["late_transit_days"] = late.handling_days.mean(), late.transit_days.mean()
    m["ontime_handling_days"], m["ontime_transit_days"] = ok.handling_days.mean(), ok.transit_days.mean()
    m["late_missed_deadline_pct"] = 100 * late.seller_missed_deadline.mean()
    m["ontime_missed_deadline_pct"] = 100 * ok.seller_missed_deadline.mean()
    m["peak_late_pct"] = 100 * df[df.month.isin(PEAK)].is_late.mean()
    m["other_late_pct"] = 100 * df[~df.month.isin(PEAK)].is_late.mean()
    single = df[df.seller_id.notna()]
    m["same_state_late_pct"] = 100 * single[single.same_state == 1].is_late.mean()
    m["diff_state_late_pct"] = 100 * single[single.same_state == 0].is_late.mean()
    for s in ["MA", "SP", "PR"]:
        m[f"late_pct_{s}"] = 100 * df[df.customer_state == s].is_late.mean()
    for mo in ["2017-11", "2018-03"]:
        m[f"late_pct_{mo.replace('-', '_')}"] = 100 * df[df.month == mo].is_late.mean()
    s = single.groupby("seller_id").agg(n=("is_late", "size"), late=("is_late", "sum"))
    s = s.sort_values(["late", "n"], ascending=False)
    m["pareto_sellers_50pct"] = int((s.late.cumsum() / s.late.sum() < 0.5).sum()) + 1
    m["n_single_sellers"] = len(s)
    m["median_days_vs_promise"] = float(df.days_vs_promise.median())
    m["multi_seller_orders"] = int(df.seller_id.isna().sum())
    return m


report = []


def check(area, name, ok, detail):
    report.append([area, name, "PASS" if ok else "FAIL", detail])


sql, pdf = load_sql(), load_pandas()
print(f"SQL view: {len(sql):,} rows | pandas rebuild: {len(pdf):,} rows\n")

# --- Block 5: A) row-by-row comparison ------------------------------------
a, b = set(sql.order_id), set(pdf.order_id)
check("Rows", "same set of order_ids", a == b, f"only SQL {len(a - b)}, only pandas {len(b - a)}")
j = sql.merge(pdf, on="order_id", suffixes=("_sql", "_pd"))
for col, tol in [("is_late", 0), ("days_vs_promise", 0), ("promised_days", 0), ("seller_missed_deadline", 0),
                 ("same_state", 0), ("n_items", 0), ("n_sellers", 0), ("handling_days", 1e-6),
                 ("transit_days", 1e-6), ("total_days", 1e-6), ("items_value", 0.005),
                 ("freight_value", 0.005), ("review_score", 0)]:
    x = pd.to_numeric(j[f"{col}_sql"], errors="coerce").astype(float)
    y = pd.to_numeric(j[f"{col}_pd"], errors="coerce").astype(float)
    bad = ~(((x - y).abs() <= tol) | (x.isna() & y.isna()))
    check("Rows", f"{col} matches per order", bad.sum() == 0, f"{bad.sum()} mismatches of {len(j):,}")
same_seller = (j.seller_id_sql.fillna("") == j.seller_id_pd.fillna("")).all()
check("Rows", "seller_id matches per order", same_seller, "NULL for multi-seller orders in both")

# --- Block 6: B) headline metrics: SQL vs pandas vs README ----------------
ms, mp = metrics(sql), metrics(pdf)
for k, (quoted, tol) in README.items():
    agree = abs(ms[k] - mp[k]) < 1e-4          # SQL keeps 6 decimals in day columns
    matches_readme = abs(round(ms[k], 1) - quoted) <= tol + 1e-9
    check("README", k, agree and matches_readme,
          f"SQL {ms[k]:.3f} | pandas {mp[k]:.3f} | README {quoted}")

rep = pd.DataFrame(report, columns=["area", "check", "result", "detail"])
rep.to_csv(OUT / "validation_report.csv", index=False)
print(rep.to_string(index=False))
n_fail = (rep.result == "FAIL").sum()
print(f"\n{len(rep) - n_fail} of {len(rep)} checks passed. Saved outputs/validation_report.csv")