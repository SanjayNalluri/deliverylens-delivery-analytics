/* ---------------------------------------------------------------
   DeliveryLens - Step 1a: create the database and tables
   Run in SSMS (connected to your server) - press F5.
   Safe to re-run: drops and recreates everything.
---------------------------------------------------------------- */
USE master;
GO
IF DB_ID('DeliveryLens') IS NOT NULL
BEGIN
    ALTER DATABASE DeliveryLens SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE DeliveryLens;
END
GO
CREATE DATABASE DeliveryLens;
GO
USE DeliveryLens;
GO

-- Customers: customer_id is per order; customer_unique_id is the real person
CREATE TABLE customers (
    customer_id              CHAR(32)      NOT NULL PRIMARY KEY,
    customer_unique_id       CHAR(32)      NOT NULL,
    customer_zip_code_prefix CHAR(5)       NOT NULL,
    customer_city            NVARCHAR(60)  NOT NULL,
    customer_state           CHAR(2)       NOT NULL
);

CREATE TABLE sellers (
    seller_id                CHAR(32)      NOT NULL PRIMARY KEY,
    seller_zip_code_prefix   CHAR(5)       NOT NULL,
    seller_city              NVARCHAR(60)  NOT NULL,
    seller_state             CHAR(2)       NOT NULL
);

-- Column names keep Olist's spelling ("lenght") so they match the CSV
CREATE TABLE products (
    product_id                 CHAR(32)     NOT NULL PRIMARY KEY,
    product_category_name      NVARCHAR(60) NULL,
    product_name_lenght        INT          NULL,
    product_description_lenght INT          NULL,
    product_photos_qty         INT          NULL,
    product_weight_g           INT          NULL,
    product_length_cm          INT          NULL,
    product_height_cm          INT          NULL,
    product_width_cm           INT          NULL
);

-- Portuguese -> English category names (2 categories have no translation)
CREATE TABLE category_en (
    product_category_name         NVARCHAR(60) NOT NULL PRIMARY KEY,
    product_category_name_english NVARCHAR(60) NOT NULL
);

CREATE TABLE orders (
    order_id                      CHAR(32)     NOT NULL PRIMARY KEY,
    customer_id                   CHAR(32)     NOT NULL REFERENCES customers(customer_id),
    order_status                  VARCHAR(15)  NOT NULL,
    order_purchase_timestamp      DATETIME2(0) NOT NULL,
    order_approved_at             DATETIME2(0) NULL,
    order_delivered_carrier_date  DATETIME2(0) NULL,   -- seller hands to courier
    order_delivered_customer_date DATETIME2(0) NULL,   -- customer receives
    order_estimated_delivery_date DATETIME2(0) NOT NULL -- date promised at purchase
);

-- One row per item; an order can have several items from different sellers
CREATE TABLE order_items (
    order_id            CHAR(32)      NOT NULL REFERENCES orders(order_id),
    order_item_id       INT           NOT NULL,
    product_id          CHAR(32)      NOT NULL REFERENCES products(product_id),
    seller_id           CHAR(32)      NOT NULL REFERENCES sellers(seller_id),
    shipping_limit_date DATETIME2(0)  NOT NULL,   -- deadline for seller to hand over
    price               DECIMAL(10,2) NOT NULL,
    freight_value       DECIMAL(10,2) NOT NULL,
    PRIMARY KEY (order_id, order_item_id)
);

CREATE TABLE payments (
    order_id             CHAR(32)      NOT NULL REFERENCES orders(order_id),
    payment_sequential   INT           NOT NULL,
    payment_type         VARCHAR(15)   NOT NULL,
    payment_installments INT           NOT NULL,
    payment_value        DECIMAL(10,2) NOT NULL,
    PRIMARY KEY (order_id, payment_sequential)
);

-- review_id repeats across orders (827 cases), so the key is the pair
CREATE TABLE reviews (
    review_id               CHAR(32)       NOT NULL,
    order_id                CHAR(32)       NOT NULL REFERENCES orders(order_id),
    review_score            TINYINT        NOT NULL,
    review_comment_title    NVARCHAR(100)  NULL,
    review_comment_message  NVARCHAR(1000) NULL,
    review_creation_date    DATETIME2(0)   NOT NULL,
    review_answer_timestamp DATETIME2(0)   NOT NULL,
    PRIMARY KEY (review_id, order_id)
);

-- Indexes on the join columns used later
CREATE INDEX ix_orders_customer ON orders(customer_id);
CREATE INDEX ix_items_seller    ON order_items(seller_id);
CREATE INDEX ix_items_product   ON order_items(product_id);
CREATE INDEX ix_reviews_order   ON reviews(order_id);
GO
PRINT 'DeliveryLens database and 8 tables created.';