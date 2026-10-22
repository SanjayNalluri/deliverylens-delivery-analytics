"""
Step 5 - Statistical checks and what-if impact estimates.
Input  : view vw_delivered_orders in SQL Server (sql/03_delivery_view.sql)
Outputs: outputs/stats_late_rate_ci.csv   late % with 95% confidence intervals
         outputs/stats_tests.csv          significance tests
         outputs/stats_review_regression.csv  review score vs lateness, with controls
         outputs/whatif_scenarios.csv     late orders avoided / rating change
         outputs/04_state_ci.png          late % by state with 95% CI
Needs  : pip install pandas pyodbc scipy statsmodels matplotlib
"""
from pathlib import Path
import warnings
import numpy as np
import pandas as pd
import pyodbc
from scipy import stats
import statsmodels.formula.api as smf
from statsmodels.stats.proportion import proportion_confint
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore", category=UserWarning)   # pandas + pyodbc notice

# --- Block 1: settings + load the view ------------------------------------
SERVER, DATABASE = "DESKTOP-0CCEUEQ", "DeliveryLens"
PEAK_MONTHS = ["2017-11", "2018-02", "2018-03"]          # from Q1 in sql/04_analysis.sql
MIN_STATE_ORDERS = 500

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"


def load_view():
    driver = sorted([d for d in pyodbc.drivers() if "SQL Server" in d],
                    key=lambda d: ("ODBC Driver" in d, d))[-1]
    con = pyodbc.connect(f"DRIVER={{{driver}}};SERVER={SERVER};DATABASE={DATABASE};"
                         "Trusted_Connection=yes;TrustServerCertificate=yes;")
    df = pd.read_sql("SELECT * FROM vw_delivered_orders", con)
    con.close()
    return df


df = load_view()
df["month"] = pd.to_datetime(df["purchase_month"]).dt.strftime("%Y-%m")
df["is_peak"] = df["month"].isin(PEAK_MONTHS).astype(int)
df["late_bucket"] = pd.cut(df["days_vs_promise"], [-1e9, 0, 3, 7, 1e9],
                           labels=["On time or early", "Late 1-3 days", "Late 4-7 days", "Late 8+ days"])
print(f"Loaded {len(df):,} orders, late share {df.is_late.mean():.1%}\n")


def fmt_p(p):
    return "<0.001" if p < 0.001 else f"{p:.3f}"


# --- Block 2: late % with 95% Wilson confidence intervals ------------------
# Wilson interval: stays inside 0-100% and works for small groups.
def ci_table(group_col, label, min_orders=0):
    g = df.groupby(group_col).agg(orders=("is_late", "size"), late=("is_late", "sum")).reset_index()
    g = g[g.orders >= min_orders]
    lo, hi = proportion_confint(g.late, g.orders, alpha=0.05, method="wilson")
    return pd.DataFrame({"group_type": label, "group": g[group_col].astype(str),
                         "orders": g.orders, "late_orders": g.late,
                         "late_pct": 100 * g.late / g.orders,
                         "ci_low_pct": 100 * lo, "ci_high_pct": 100 * hi})


df["all"] = "All orders"
ci = pd.concat([ci_table("all", "Overall"),
                ci_table("customer_state", "Customer state (500+ orders)", MIN_STATE_ORDERS),
                ci_table("month", "Purchase month")], ignore_index=True).round(2)
ci.to_csv(OUT / "stats_late_rate_ci.csv", index=False)

st = ci[ci.group_type.str.startswith("Customer")].sort_values("late_pct")
print("Late % by state, 95% CI (worst 3, best 3):")
print(pd.concat([st.tail(3)[::-1], st.head(3)])[["group", "orders", "late_pct", "ci_low_pct", "ci_high_pct"]]
      .to_string(index=False), "\n")

# Chart: states with CI error bars
fig, ax = plt.subplots(figsize=(8, 6))
ax.barh(st.group, st.late_pct, color="#118DFF",
        xerr=[st.late_pct - st.ci_low_pct, st.ci_high_pct - st.late_pct], capsize=3, ecolor="#333333")
ax.axvline(100 * df.is_late.mean(), color="#8C2F39", ls="--", lw=1, label=f"All orders {df.is_late.mean():.1%}")
ax.set_xlabel("Late % (bars = 95% confidence interval)")
ax.set_title(f"Late % by customer state ({MIN_STATE_ORDERS}+ orders)", loc="left")
ax.legend(loc="lower right"); ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout(); fig.savefig(OUT / "04_state_ci.png", dpi=150)

# --- Block 3: significance tests ------------------------------------------
tests = []

# 3a. Review score: late vs on-time (Welch t-test + Mann-Whitney, which does not assume normal data)
r = df.dropna(subset=["review_score"])
late_r, ok_r = r.loc[r.is_late == 1, "review_score"], r.loc[r.is_late == 0, "review_score"]
t = stats.ttest_ind(late_r, ok_r, equal_var=False)
mw = stats.mannwhitneyu(late_r, ok_r)
diff = late_r.mean() - ok_r.mean()
se = np.sqrt(late_r.var() / len(late_r) + ok_r.var() / len(ok_r))
d = diff / np.sqrt((late_r.var() + ok_r.var()) / 2)                 # Cohen's d (effect size)
tests.append(["Avg review: late vs on-time", f"{late_r.mean():.2f} vs {ok_r.mean():.2f}",
              f"{diff:.2f} [{diff - 1.96*se:.2f}, {diff + 1.96*se:.2f}]", "Welch t-test", fmt_p(t.pvalue),
              f"Mann-Whitney p {fmt_p(mw.pvalue)}; Cohen's d {d:.2f}"])


# 3b/3c. Two late rates compared (chi-square test of the 2x2 table)
def compare_rates(name, mask_a, mask_b, label_a, label_b, base=df):
    a, b = base[mask_a], base[mask_b]
    pa, pb = a.is_late.mean(), b.is_late.mean()
    chi2, p, _, _ = stats.chi2_contingency([[a.is_late.sum(), len(a) - a.is_late.sum()],
                                            [b.is_late.sum(), len(b) - b.is_late.sum()]])
    se = np.sqrt(pa * (1 - pa) / len(a) + pb * (1 - pb) / len(b))
    dd = 100 * (pa - pb)
    tests.append([name, f"{label_a} {100*pa:.1f}% vs {label_b} {100*pb:.1f}%",
                  f"{dd:.1f} pts [{dd - 196*se:.1f}, {dd + 196*se:.1f}]", "Chi-square", fmt_p(p),
                  f"n = {len(a):,} vs {len(b):,}"])


single = df[df.seller_id.notna()]
compare_rates("Late %: different vs same state", single.same_state == 0, single.same_state == 1,
              "different", "same", base=single)
compare_rates("Late %: peak vs other months", df.is_peak == 1, df.is_peak == 0, "peak", "other")

tests = pd.DataFrame(tests, columns=["test", "groups", "difference [95% CI]", "method", "p_value", "notes"])
tests.to_csv(OUT / "stats_tests.csv", index=False)
print("Significance tests:")
print(tests.to_string(index=False), "\n")

# --- Block 4: review score vs lateness, controlling for other factors -----
# OLS with robust (HC1) standard errors. Controls: customer state, purchase month,
# order value, freight, number of items, multi-seller. The coefficient on each
# late bucket = review change vs an on-time order with the same controls.
r = df.dropna(subset=["review_score"]).copy()
r["log_value"] = np.log1p(r.items_value)
model = smf.ols("review_score ~ C(late_bucket) + C(customer_state) + C(month)"
                " + log_value + freight_value + n_items + C(n_sellers > 1)", data=r).fit(cov_type="HC1")
rows = [k for k in model.params.index if k.startswith("C(late_bucket)")]
reg = pd.DataFrame({"term": [k.split("T.")[1].rstrip("]") for k in rows],
                    "review_change": model.params[rows].values,
                    "ci_low": model.conf_int().loc[rows, 0].values,
                    "ci_high": model.conf_int().loc[rows, 1].values,
                    "p_value": [fmt_p(p) for p in model.pvalues[rows]]}).round(3)
raw = r.groupby("late_bucket", observed=True).review_score.mean()
reg.insert(1, "raw_gap", [round(raw[t] - raw["On time or early"], 3) for t in reg.term])
reg.to_csv(OUT / "stats_review_regression.csv", index=False)
print(f"Review score vs lateness (OLS, n = {int(model.nobs):,}, R-squared {model.rsquared:.3f}):")
print(reg.to_string(index=False), "\n")

# --- Block 5: what-if scenarios -------------------------------------------
# Rating penalty per late order = regression coefficient of its late bucket.
coef = dict(zip(reg.term, reg.review_change))
df["penalty"] = df.late_bucket.astype(str).map(coef).fillna(0.0)
n_orders, n_late = len(df), int(df.is_late.sum())
n_reviewed = int(df.review_score.notna().sum())
scen = []


def add_scenario(name, assumption, avoided, fixed_rows):
    # avoided late orders are assumed to be a random share of fixed_rows' late orders
    late_rows = fixed_rows[fixed_rows.is_late == 1]
    share = avoided / len(late_rows) if len(late_rows) else 0
    gain = -share * late_rows.loc[late_rows.review_score.notna(), "penalty"].sum() / n_reviewed
    scen.append([name, assumption, round(avoided), round(100 * avoided / n_late, 1),
                 round(100 * n_late / n_orders, 2), round(100 * (n_late - avoided) / n_orders, 2),
                 round(gain, 3)])


# 5a. Worst sellers: the sellers that together cause 50% of late orders (Pareto, as in SQL Q5)
s = single.groupby("seller_id").agg(orders=("is_late", "size"), late=("is_late", "sum"))
s = s.sort_values(["late", "orders"], ascending=False)
k = int((s.late.cumsum() / s.late.sum() < 0.5).sum()) + 1
worst = s.index[:k]
rest = s.iloc[k:]
rest_rate = rest.late.sum() / rest.orders.sum()
w = s.iloc[:k]
avoided = (w.late - w.orders * rest_rate).clip(lower=0).sum()
add_scenario(f"Worst {k} sellers reach other sellers' late rate",
             f"their late % falls from {100*w.late.sum()/w.orders.sum():.1f}% to {100*rest_rate:.1f}%",
             avoided, df[df.seller_id.isin(worst)])

# 5b. Peak months reach the average late rate of the other months
pk, off = df[df.is_peak == 1], df[df.is_peak == 0]
avoided = pk.is_late.sum() - len(pk) * off.is_late.mean()
add_scenario("Peak months reach other months' late rate",
             f"peak late % falls from {100*pk.is_late.mean():.1f}% to {100*off.is_late.mean():.1f}%",
             avoided, pk)

# 5c. Sellers that missed the hand-over deadline had met it
#     (late orders with a missed deadline get the late rate of late-risk orders that met it)
m, nm = df[df.seller_missed_deadline == 1], df[df.seller_missed_deadline == 0]
avoided = m.is_late.sum() - len(m) * nm.is_late.mean()
add_scenario("Every seller meets the hand-over deadline",
             f"late % of missed-deadline orders falls from {100*m.is_late.mean():.1f}% to {100*nm.is_late.mean():.1f}%",
             avoided, m)

scen = pd.DataFrame(scen, columns=["scenario", "assumption", "late_orders_avoided", "pct_of_late_orders",
                                   "late_pct_now", "late_pct_after", "avg_review_change"])
scen.to_csv(OUT / "whatif_scenarios.csv", index=False)
print("What-if scenarios (each on its own; they overlap, so do not add them):")
print(scen.to_string(index=False))
print("\nSaved: stats_late_rate_ci.csv, stats_tests.csv, stats_review_regression.csv, "
      "whatif_scenarios.csv, 04_state_ci.png in outputs/")