/* ---------------------------------------------------------------
   DeliveryLens - Step 2b: one clean row per delivered order
   Run in SSMS (F5). Creates view vw_delivered_orders, used by
   every later query and by Power BI.

   Kept   : status 'delivered', all dates present, dates in order,
            purchased Jan 2017 - Aug 2018 (full months only)
   Time split of each order:
     handling_days = purchase  -> handed to carrier   (seller)
     transit_days  = carrier   -> received by customer (courier)
   Late = received on a later calendar day than the promised date
---------------------------------------------------------------- */
USE DeliveryLens;
GO
CREATE OR ALTER VIEW vw_delivered_orders AS
WITH items AS (            -- order-level totals from the item table
    SELECT order_id,
           COUNT(*)                  AS n_items,
           COUNT(DISTINCT seller_id) AS n_sellers,
           MIN(seller_id)            AS seller_id,          -- the seller when n_sellers = 1
           MAX(shipping_limit_date)  AS shipping_limit_date, -- seller's hand-over deadline
           SUM(price)                AS items_value,
           SUM(freight_value)        AS freight_value
    FROM order_items
    GROUP BY order_id
),
last_review AS (           -- some orders have 2-3 reviews: keep the latest
    SELECT order_id, review_score,
           ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY review_answer_timestamp DESC) AS rn
    FROM reviews
)
SELECT
    o.order_id,
    c.customer_unique_id,
    c.customer_state,
    CASE WHEN i.n_sellers = 1 THEN i.seller_id END     AS seller_id,     -- NULL for multi-seller orders
    CASE WHEN i.n_sellers = 1 THEN s.seller_state END  AS seller_state,
    i.n_items, i.n_sellers, i.items_value, i.freight_value,
    o.order_purchase_timestamp,
    DATEFROMPARTS(YEAR(o.order_purchase_timestamp), MONTH(o.order_purchase_timestamp), 1) AS purchase_month,
    o.order_delivered_carrier_date,
    o.order_delivered_customer_date,
    o.order_estimated_delivery_date,
    i.shipping_limit_date,
    DATEDIFF(MINUTE, o.order_purchase_timestamp,     o.order_delivered_carrier_date)  / 1440.0 AS handling_days,
    DATEDIFF(MINUTE, o.order_delivered_carrier_date, o.order_delivered_customer_date) / 1440.0 AS transit_days,
    DATEDIFF(MINUTE, o.order_purchase_timestamp,     o.order_delivered_customer_date) / 1440.0 AS total_days,
    DATEDIFF(DAY,    o.order_purchase_timestamp,     o.order_estimated_delivery_date)          AS promised_days,
    -- positive = days late, negative = days early (calendar days)
    DATEDIFF(DAY, o.order_estimated_delivery_date, CAST(o.order_delivered_customer_date AS DATE)) AS days_vs_promise,
    CASE WHEN CAST(o.order_delivered_customer_date AS DATE) > o.order_estimated_delivery_date
         THEN 1 ELSE 0 END                                         AS is_late,
    CASE WHEN o.order_delivered_carrier_date > i.shipping_limit_date
         THEN 1 ELSE 0 END                                         AS seller_missed_deadline,
    CASE WHEN c.customer_state = s.seller_state AND i.n_sellers = 1
         THEN 1 ELSE 0 END                                         AS same_state,
    r.review_score
FROM orders o
JOIN customers c   ON c.customer_id = o.customer_id
JOIN items i       ON i.order_id    = o.order_id
JOIN sellers s     ON s.seller_id   = i.seller_id
LEFT JOIN last_review r ON r.order_id = o.order_id AND r.rn = 1
WHERE o.order_status = 'delivered'
  AND o.order_delivered_carrier_date  IS NOT NULL
  AND o.order_delivered_customer_date IS NOT NULL
  AND o.order_delivered_carrier_date  >= o.order_purchase_timestamp
  AND o.order_delivered_customer_date >= o.order_delivered_carrier_date
  AND o.order_purchase_timestamp >= '2017-01-01'
  AND o.order_purchase_timestamp <  '2018-09-01';
GO

-- Quick look at the result
SELECT COUNT(*)                          AS orders_kept,
       AVG(CAST(is_late AS FLOAT))       AS late_share,
       AVG(total_days)                   AS avg_total_days,
       AVG(handling_days)                AS avg_handling_days,
       AVG(transit_days)                 AS avg_transit_days,
       AVG(CAST(promised_days AS FLOAT)) AS avg_promised_days,
       SUM(CASE WHEN seller_id IS NULL THEN 1 ELSE 0 END) AS multi_seller_orders
FROM vw_delivered_orders;
