/* ---------------------------------------------------------------
   DeliveryLens - Step 2a: data quality checks
   Run in SSMS (F5). One results grid; each row is one check.
   These decide what the analysis view (03) keeps or drops.
---------------------------------------------------------------- */
USE DeliveryLens;
GO

WITH d AS (SELECT * FROM orders WHERE order_status = 'delivered')
SELECT '01 All orders'                                   AS [check], COUNT(*) AS n FROM orders
UNION ALL SELECT '02 Delivered orders',                   COUNT(*) FROM d
UNION ALL SELECT '03 Delivered but no customer date',     COUNT(*) FROM d WHERE order_delivered_customer_date IS NULL
UNION ALL SELECT '04 Delivered but no carrier date',      COUNT(*) FROM d WHERE order_delivered_carrier_date IS NULL
UNION ALL SELECT '05 Handed to carrier before purchase',  COUNT(*) FROM d WHERE order_delivered_carrier_date < order_purchase_timestamp
UNION ALL SELECT '06 Received before handed to carrier',  COUNT(*) FROM d WHERE order_delivered_customer_date < order_delivered_carrier_date
UNION ALL SELECT '07 Not delivered but has customer date',COUNT(*) FROM orders WHERE order_status <> 'delivered' AND order_delivered_customer_date IS NOT NULL
UNION ALL SELECT '08 Orders with more than one seller',   COUNT(*) FROM (SELECT order_id FROM order_items GROUP BY order_id HAVING COUNT(DISTINCT seller_id) > 1) x
UNION ALL SELECT '09 Orders with more than one review',   COUNT(*) FROM (SELECT order_id FROM reviews GROUP BY order_id HAVING COUNT(*) > 1) x
UNION ALL SELECT '10 Delivered orders with no review',    COUNT(*) FROM d WHERE NOT EXISTS (SELECT 1 FROM reviews r WHERE r.order_id = d.order_id)
UNION ALL SELECT '11 Purchases before Jan 2017 (sparse)', COUNT(*) FROM orders WHERE order_purchase_timestamp <  '2017-01-01'
UNION ALL SELECT '12 Purchases after Aug 2018 (sparse)',  COUNT(*) FROM orders WHERE order_purchase_timestamp >= '2018-09-01';

-- Orders per purchase month (shows why we keep Jan 2017 - Aug 2018 only)
SELECT FORMAT(order_purchase_timestamp, 'yyyy-MM') AS purchase_month, COUNT(*) AS orders
FROM orders
GROUP BY FORMAT(order_purchase_timestamp, 'yyyy-MM')
ORDER BY purchase_month;
