/* ---------------------------------------------------------------
   DeliveryLens - Step 3: the business questions
   Run in SSMS (F5). 8 result grids, Q1 to Q8 in order.
   Source: vw_delivered_orders (03). Seller-level questions use
   single-seller orders only (seller_id is NULL for the 1,249 others).
---------------------------------------------------------------- */
USE DeliveryLens;
GO

/* Q1. Is late delivery getting better or worse?  Late share by month */
SELECT purchase_month,
       COUNT(*)                                   AS orders,
       SUM(is_late)                               AS late_orders,
       ROUND(100.0 * AVG(CAST(is_late AS FLOAT)), 1) AS late_pct,
       ROUND(AVG(total_days), 1)                  AS avg_total_days,
       ROUND(AVG(CAST(promised_days AS FLOAT)), 1) AS avg_promised_days
FROM vw_delivered_orders
GROUP BY purchase_month
ORDER BY purchase_month;

/* Q2. Who causes the delay: seller or courier?
   Compare time split of late vs on-time orders, and how many late
   orders started with the seller missing its hand-over deadline. */
SELECT CASE WHEN is_late = 1 THEN 'Late' ELSE 'On time' END AS delivery,
       COUNT(*)                                          AS orders,
       ROUND(AVG(handling_days), 2)                      AS avg_handling_days,
       ROUND(AVG(transit_days), 2)                       AS avg_transit_days,
       ROUND(AVG(total_days), 2)                         AS avg_total_days,
       ROUND(100.0 * AVG(CAST(seller_missed_deadline AS FLOAT)), 1) AS seller_missed_deadline_pct
FROM vw_delivered_orders
GROUP BY is_late;

/* Q3. Which customer states get the most late orders?  (states with 500+ orders) */
SELECT customer_state,
       COUNT(*)                                       AS orders,
       ROUND(100.0 * AVG(CAST(is_late AS FLOAT)), 1)  AS late_pct,
       ROUND(AVG(transit_days), 1)                    AS avg_transit_days,
       ROUND(AVG(CAST(promised_days AS FLOAT)), 1)    AS avg_promised_days,
       RANK() OVER (ORDER BY AVG(CAST(is_late AS FLOAT)) DESC) AS late_rank
FROM vw_delivered_orders
GROUP BY customer_state
HAVING COUNT(*) >= 500
ORDER BY late_rank;

/* Q4. Does shipping within the same state help? */
SELECT CASE WHEN same_state = 1 THEN 'Same state' ELSE 'Different state' END AS route,
       COUNT(*)                                      AS orders,
       ROUND(100.0 * AVG(CAST(is_late AS FLOAT)), 1) AS late_pct,
       ROUND(AVG(transit_days), 1)                   AS avg_transit_days
FROM vw_delivered_orders
WHERE seller_id IS NOT NULL
GROUP BY same_state;

/* Q5. Are late orders concentrated in a few sellers?  (Pareto)
   Sort sellers by number of late orders; running share of all late orders. */
WITH s AS (
    SELECT seller_id, COUNT(*) AS orders, SUM(is_late) AS late_orders
    FROM vw_delivered_orders
    WHERE seller_id IS NOT NULL
    GROUP BY seller_id
),
ranked AS (
    SELECT *,
           ROW_NUMBER() OVER (ORDER BY late_orders DESC, orders DESC)          AS seller_rank,
           COUNT(*)     OVER ()                                                AS n_sellers,
           SUM(late_orders) OVER (ORDER BY late_orders DESC, orders DESC
                                  ROWS UNBOUNDED PRECEDING) * 1.0
             / SUM(late_orders) OVER ()                                        AS cum_late_share
    FROM s
)
SELECT TOP 1                                 -- first point where 50% of late orders is reached
       seller_rank                           AS sellers_needed,
       n_sellers,
       ROUND(100.0 * seller_rank / n_sellers, 1) AS pct_of_sellers,
       ROUND(100.0 * cum_late_share, 1)      AS pct_of_late_orders
FROM ranked
WHERE cum_late_share >= 0.5
ORDER BY seller_rank;

/* Q6. Worst sellers  (50+ orders, ranked by late share) */
SELECT TOP 15 v.seller_id, s.seller_state,
       COUNT(*)                                      AS orders,
       SUM(is_late)                                  AS late_orders,
       ROUND(100.0 * AVG(CAST(is_late AS FLOAT)), 1) AS late_pct,
       ROUND(100.0 * AVG(CAST(seller_missed_deadline AS FLOAT)), 1) AS missed_deadline_pct,
       ROUND(AVG(handling_days), 1)                  AS avg_handling_days,
       ROUND(AVG(CAST(review_score AS FLOAT)), 2)    AS avg_review
FROM vw_delivered_orders v
JOIN sellers s ON s.seller_id = v.seller_id
GROUP BY v.seller_id, s.seller_state
HAVING COUNT(*) >= 50
ORDER BY late_pct DESC;

/* Q7. What does lateness do to the review score? */
WITH b AS (
    SELECT review_score,
           CASE WHEN days_vs_promise <= -15 THEN '1 Early 15+ days'
                WHEN days_vs_promise <=  -8 THEN '2 Early 8-14 days'
                WHEN days_vs_promise <=  -1 THEN '3 Early 1-7 days'
                WHEN days_vs_promise  =   0 THEN '4 On the promised day'
                WHEN days_vs_promise <=   3 THEN '5 Late 1-3 days'
                WHEN days_vs_promise <=   7 THEN '6 Late 4-7 days'
                ELSE                             '7 Late 8+ days' END AS bucket
    FROM vw_delivered_orders
    WHERE review_score IS NOT NULL
)
SELECT bucket,
       COUNT(*)                                                    AS orders,
       ROUND(AVG(CAST(review_score AS FLOAT)), 2)                  AS avg_review,
       ROUND(100.0 * AVG(CASE WHEN review_score = 1 THEN 1.0 ELSE 0 END), 1) AS one_star_pct
FROM b
GROUP BY bucket
ORDER BY bucket;

/* Q8. Is the promised date too cautious?
   Spread of (actual - promised) in days; negative = arrived early. */
SELECT DISTINCT
       PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY days_vs_promise) OVER () AS p10,
       PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY days_vs_promise) OVER () AS p25,
       PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY days_vs_promise) OVER () AS median,
       PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY days_vs_promise) OVER () AS p75,
       PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY days_vs_promise) OVER () AS p90
FROM vw_delivered_orders;
