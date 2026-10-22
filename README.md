# 📦 DeliveryLens: Why Do Online Orders Arrive Late?

**Where does delivery delay come from (seller or courier, region or season), and what does it cost in customer ratings?**

A SQL Server + Power BI analysis of **96,018 delivered orders** from Olist, a Brazilian e-commerce marketplace (Jan 2017 – Aug 2018). All cleaning and analysis is in T-SQL (SSMS); the dashboard is built in Power BI on top of one SQL view; significance tests, a regression and what-if estimates are in Python.

---

## Executive summary

1. **Late delivery is a peak-season problem.** In Nov 2017, Feb and Mar 2018 the late rate was **15.1% vs 4.5%** in other months (difference 10.7 pts, 95% CI 10.2–11.2). Bringing those months to the normal rate would have avoided **≈2,200 late orders, 34% of all late orders**.
2. **Lateness costs ratings, even after controls.** An order 8+ days late scores **2.5 points lower** (on a 1–5 scale) than an on-time order from the same state and month with a similar value and freight; 1–3 days late already costs **≈1 point**.
3. **The delay sits with the courier, triggered by sellers.** Late orders spend 27.9 days in transit vs 8.0; in 27.7% of them the seller had already missed its hand-over deadline. If every seller met that deadline, **≈1,350 late orders (21%)** would be expected to disappear.

**Actions for a logistics manager:** book extra courier capacity before peak months, enforce the seller hand-over deadline (alerts on the 98 sellers that cause half of late orders), and set longer promised dates for Northeast routes.

*These are historical patterns from one marketplace in 2017–2018, not a measure of current performance.*

---

## Key findings

| | Finding |
|---|---|
| **Late rate** | **6.8%** of orders (6,528) arrived after the promised date |
| **Cost in ratings** | Avg review falls from **4.33** (15+ days early) to **1.70** (8+ days late); 1-star share rises from **6.5%** to **69.8%** |
| **Peaks** | Late % jumps from ~3% to **12.4%** (Nov 2017, Black Friday), **14.1%** (Feb 2018) and **19.0%** (Mar 2018) |
| **Where the time goes** | Late orders spend **27.9 days** with the courier vs **8.0** for on-time orders; seller handling is **6.0 vs 3.0 days** |
| **Seller trigger** | In **27.7%** of late orders the seller had already missed its hand-over deadline (vs 7.6% of on-time orders) |
| **Geography** | Northeast states are worst (**MA 17.6%**, CE 13.8%, BA 12.2%); RJ is 12.2% on 12,291 orders. SP 4.5%, PR 4.1% |
| **Distance** | Same-state shipments are late **4.6%** of the time vs **8.2%** across states |
| **Concentration** | **98 sellers (3.4% of 2,923)** account for **50%** of all late orders |
| **Promise padding** | The median order arrives **12 days early**; 90% arrive at least 2 days early, yet 6.8% are still late |

### Recommendations (what the data supports)

1. **Plan courier capacity for peaks.** Peak months run at 15.1% late vs 4.5%; matching normal months would avoid ≈2,200 late orders (34%).
2. **Enforce the seller hand-over deadline.** Meeting it everywhere would avoid ≈1,350 late orders (21%); start with alerts on the 98 sellers that cause half of late orders.
3. **Make the promised date depend on route and season**, not one rule: the median order is 12 days early, but Northeast and peak-month orders still miss.
4. **Fulfil closer to the customer.** Same-state orders are late half as often (see [HubShift India](https://github.com/SanjayNalluri/hubshift-india-network-design) for a warehouse-network model).

---

## Dashboard (Power BI)

![Overview](outputs/01_overview.png)
![Where & why](outputs/02_where_why.png)
![Sellers](outputs/03_sellers.png)

| Page | Visuals |
|---|---|
| Overview | 5 KPI cards, late % by month, review score by days early/late |
| Where & why | Region slicer, late % by customer state (500+ orders), seller vs courier time, same vs different state |
| Sellers | Pareto of late orders (top 85 sellers, cumulative share of all late orders), table of sellers with 50+ orders |

**Power Query** adds 4 columns (Delivery Status, Promise Bucket, Route, Region). **DAX**: 12 measures incl. a Pareto cumulative-share measure (`powerbi/measures.dax`). Full report: `powerbi/DeliveryLens.pbix`, PDF: `outputs/DeliveryLens_dashboard.pdf`.

---

## Statistical checks (`src/step5_stats_impact.py`)

**Are the differences real?** All three main comparisons are far outside chance (p < 0.001):

| Comparison | Result | Difference [95% CI] |
|---|---|---|
| Avg review, late vs on-time | 2.27 vs 4.29 | −2.02 [−2.06, −1.98]; effect size (Cohen's d) −1.47, large |
| Late %, different vs same state | 8.2% vs 4.6% | +3.6 pts [3.3, 3.9] |
| Late %, peak vs other months | 15.1% vs 4.5% | +10.7 pts [10.2, 11.2] |

**Late % by state with 95% confidence intervals.** MA (17.6%, CI 15.0–20.6) is clearly worst even on 710 orders; SP (4.5%, CI 4.3–4.7) and PR (4.1%, CI 3.6–4.7) are clearly best.

![State CI](outputs/04_state_ci.png)

**Does lateness itself lower the review?** A regression (OLS, robust standard errors, 95,376 reviewed orders) controls for customer state, purchase month, order value, freight, item count and multi-seller orders. The rating drop barely changes once these are held equal:

| Delivery vs promise | Raw gap vs on-time | After controls [95% CI] |
|---|---|---|
| Late 1–3 days | −1.00 | **−0.99** [−1.06, −0.92] |
| Late 4–7 days | −2.19 | **−2.16** [−2.24, −2.09] |
| Late 8+ days | −2.60 | **−2.54** [−2.59, −2.49] |

This rules out the listed factors as the explanation, but it is still observational: something not in the data (e.g. a damaged parcel that is also slow) could affect both.

## What-if impact

Each scenario changes one thing and keeps everything else as it was. They overlap, so they must not be added together. Rating change uses the regression penalties above. No cost data exists in Olist, so impact is stated in late orders and rating points, not money.

| Scenario | Assumption | Late orders avoided | Late % | Avg review |
|---|---|---|---|---|
| Peak months perform like other months | peak late % 15.1% → 4.5% | **2,223** (34% of late) | 6.8% → 4.5% | +0.05 |
| Every seller meets the hand-over deadline | late % of missed-deadline orders 21.1% → 5.4% | **1,349** (21%) | 6.8% → 5.4% | +0.03 |
| The 98 Pareto sellers perform like the rest | their late % 8.2% → 5.9% | **1,009** (16%) | 6.8% → 5.8% | +0.02 |

The 98 sellers are mostly **high-volume** sellers with a modest late rate (8.2%), so fixing them alone avoids less than fixing peak capacity. The average review moves little because only 6.8% of orders are late; for the customers involved the gain is 1–2.5 points.


---

## Data

[Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) (Kaggle, CC BY-NC-SA 4.0): 99,441 orders, 8 tables.

**Cleaning** (`sql/02_data_checks.sql`, `sql/03_delivery_view.sql`), from 99,441 orders to 96,018:

| Removed | Orders |
|---|---|
| Not delivered (canceled, shipped, unavailable, …) | 2,963 |
| Delivered but missing customer / carrier date | 8 / 2 |
| Handed to carrier before purchase; received before hand-over | 165 / 23 |
| Purchased before Jan 2017 or after Aug 2018 (sparse months) | 329 / 20 |

*Some orders fall in more than one row.* Seller-level results use the 94,769 single-seller orders.

**Definitions**
- **Late** = received on a later calendar day than the promised (estimated) date
- **Handling time** = purchase → handed to carrier (seller); **transit time** = carrier → customer (courier)
- **Seller missed deadline** = handed to carrier after the order's `shipping_limit_date`
- Orders with several reviews use the latest one

---

## Method

| Step | File | What it does |
|---|---|---|
| 1a | `sql/01_create_tables.sql` | Creates the `DeliveryLens` database: 8 tables with primary/foreign keys and indexes |
| 1b | `src/step1_load_sqlserver.py` | Loads the 8 CSVs into SQL Server (pandas + pyodbc) |
| 2a | `sql/02_data_checks.sql` | 12 data-quality checks + orders per month |
| 2b | `sql/03_delivery_view.sql` | View `vw_delivered_orders`: one clean row per order with handling/transit days, days vs promise, late flag, latest review |
| 3 | `sql/04_analysis.sql` | 8 business questions (CTEs, window functions: `ROW_NUMBER`, `RANK`, running `SUM() OVER`, `PERCENTILE_CONT`) |
| 4 | `powerbi/` | Power BI report on the view (Import mode), Power Query columns, DAX measures |
| 5 | `src/step5_stats_impact.py` | Wilson 95% CIs, Welch t / Mann-Whitney / chi-square tests, OLS regression with controls, what-if scenarios → `outputs/stats_*.csv`, `whatif_scenarios.csv`, `04_state_ci.png` |

---

## Limitations

- **One marketplace, 2017–2018, Brazil.** Results are historical patterns of Olist's network then, not evidence about current logistics performance.
- **Observational data.** The regression controls for state, month, value, freight and items, but cannot prove that lateness alone causes the lower rating. What-if scenarios assume the improved group would behave like the comparison group.
- **"Late" uses the date only**, not the time of day, and the promised date is the one shown at purchase.
- **The data does not say why** Feb–Mar 2018 spiked; the dashboard shows when, not the cause.
- **Seller vs courier split** is by timestamp: a late hand-over by the seller can also push the courier into a slower period.
- **Multi-seller orders** (1,249) are excluded from seller and same-state results because one order cannot be assigned to one seller.

---

## Run it

1. Download the Kaggle dataset; put the CSVs in `data/raw/`.
2. In **SSMS**, run `sql/01_create_tables.sql`.
3. Set `SERVER` in `src/step1_load_sqlserver.py` to your server name, then:
   ```bash
   pip install -r requirements.txt
   python src/step1_load_sqlserver.py
   ```
4. In SSMS, run `sql/02_data_checks.sql`, `sql/03_delivery_view.sql`, `sql/04_analysis.sql`.
5. `python src/step5_stats_impact.py` (same `SERVER` setting); compare with the tables above.
6. Open `powerbi/DeliveryLens.pbix` → **Transform data → Data source settings** → change the server to yours → **Refresh**.

**Tech:** SQL Server 2022 · SSMS · T-SQL · Power BI (Power Query, DAX) · Python (pandas, pyodbc, SciPy, statsmodels, matplotlib)

**Author:** Nalluri Sanjay, B.Tech (Hons.) Industrial & Systems Engineering, IIT Kharagpur · [LinkedIn](https://www.linkedin.com/in/sanjaynalluri2405/) · [GitHub](https://github.com/SanjayNalluri)
