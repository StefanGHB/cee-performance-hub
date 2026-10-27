-- =====================================================================
-- 03_transform_star_schema.sql  |  Cleanse, conform and build the star schema
--   * remediation rules from 02_data_quality_checks.sql are applied here
--   * local-currency amounts are converted to EUR at monthly average rates
--   * constant-currency (prior-year FX) amounts are derived for FX analysis
-- ${AS_OF} = last closed month-end (reporting cut-off)
-- =====================================================================

-- ---------------------------------------------------------------- Date
CREATE OR REPLACE TABLE dim_date AS
WITH d AS (SELECT CAST(range AS DATE) AS dt
           FROM range(DATE '2023-01-01', DATE '2028-01-01', INTERVAL 1 DAY))
SELECT dt                                                   AS "Date",
       year(dt)                                             AS "Year",
       'Q' || quarter(dt)                                   AS "Quarter",
       year(dt) || ' Q' || quarter(dt)                      AS "Year Quarter",
       year(dt) * 10 + quarter(dt)                          AS "Year Quarter Sort",
       month(dt)                                            AS "Month No",
       strftime(dt, '%B')                                   AS "Month",
       strftime(dt, '%b')                                   AS "Month Short",
       strftime(dt, '%b %Y')                                AS "Year Month",
       year(dt) * 100 + month(dt)                           AS "Year Month Sort",
       CAST(date_trunc('month', dt) AS DATE)                AS "Month Start",
       weekofyear(dt)                                       AS "ISO Week",
       strftime(dt, '%A')                                   AS "Weekday",
       isodow(dt)                                           AS "Weekday No",
       isodow(dt) >= 6                                      AS "Is Weekend",
       dt <= DATE '${AS_OF}'                                AS "Is Actual Period",
       CASE WHEN dt <= DATE '${AS_OF}' THEN 'Actual' ELSE 'Forecast' END AS "Period Type",
       (year(dt) - year(DATE '${AS_OF}')) * 12 + month(dt) - month(DATE '${AS_OF}') AS "Month Offset",
       year(dt) - year(DATE '${AS_OF}')                     AS "Year Offset",
       month(dt) <= month(DATE '${AS_OF}')                  AS "Is YTD Month"
FROM d;

-- ------------------------------------------------------------- Country
CREATE OR REPLACE TABLE dim_country AS
SELECT country_code AS "Country Code",
       country      AS "Country",
       region       AS "Region",
       CASE WHEN country_code = 'BG' THEN 'EUR (BGN until 2025)' ELSE currency END AS "Currency",
       country_manager AS "Country Manager",
       manager_email   AS "Manager Email"
FROM stg_countries;

-- ------------------------------------------------------------ Category
CREATE OR REPLACE TABLE dim_category AS
SELECT category_id AS "Category ID",
       category    AS "Category",
       CASE category_id WHEN 'BEV' THEN 1 WHEN 'SNK' THEN 2 WHEN 'HOM' THEN 3
                        WHEN 'PER' THEN 4 WHEN 'COF' THEN 5 WHEN 'BAB' THEN 6 END AS "Category Sort"
FROM stg_categories;

-- ------------------------------------------------------------- Product
-- master data + "Unmapped SKU" members for orphan keys found in sales (DQ02)
CREATE OR REPLACE TABLE dim_product AS
SELECT p.sku AS "SKU", p.product_name AS "Product", p.brand AS "Brand", p.category_id AS "Category ID",
       p.variant AS "Variant", p.pack_size AS "Pack Size", p.status AS "Product Status",
       p.launch_date AS "Launch Date", p.discontinued_date AS "Discontinued Date"
FROM stg_products p
UNION ALL
SELECT DISTINCT s.sku, 'Unmapped SKU ' || s.sku, 'Unmapped', split_part(s.sku, '-', 1),
       'Unmapped', 'Unmapped', 'Unmapped (pending master data)', NULL::DATE, NULL::DATE
FROM stg_sales s LEFT JOIN stg_products p USING (sku) WHERE p.sku IS NULL;

-- ------------------------------------------------------------ Customer
CREATE OR REPLACE TABLE dim_customer AS
SELECT customer_code                               AS "Customer Code",
       customer_name                               AS "Customer",
       upper(trim(country_code))                   AS "Country Code",          -- DQ07
       city                                        AS "City",
       warehouse_code                              AS "Home Warehouse",
       COALESCE(channel, 'Unassigned')             AS "Channel",               -- DQ06
       sales_rep                                   AS "Sales Rep",
       customer_since                              AS "Customer Since",
       churn_date                                  AS "Churn Date",
       CASE WHEN churn_date IS NOT NULL AND churn_date <= DATE '${AS_OF}' THEN 'Churned' ELSE 'Active' END
                                                   AS "Customer Status",
       CASE WHEN customer_since < DATE '2023-01-01' THEN 'Pre-2023'
            ELSE CAST(year(customer_since) AS VARCHAR) END AS "Acquisition Cohort"
FROM stg_customers;

-- ----------------------------------------------------------- Warehouse
CREATE OR REPLACE TABLE dim_warehouse AS
SELECT w.warehouse_code AS "Warehouse Code", w.warehouse AS "Warehouse", w.city AS "Warehouse City",
       c.country AS "Warehouse Country"
FROM stg_warehouses w JOIN stg_countries c USING (country_code);

-- ---------------------------------------------------- P&L structure
CREATE OR REPLACE TABLE dim_pnl_line AS
SELECT * FROM (VALUES
  ('GS',     'Gross Sales',                    1, 'Line',     0),
  ('DISC',   'Discounts & Promotions',         2, 'Line',     0),
  ('NS',     'Net Sales',                      3, 'Subtotal', 0),
  ('COGS',   'Cost of Goods Sold',             4, 'Line',     0),
  ('GM',     'Gross Margin',                   5, 'Subtotal', 0),
  ('GMP',    'Gross Margin %',                 6, 'Ratio',    1),
  ('6100',   'Logistics & Transport',          7, 'Line',     0),
  ('6200',   'Warehousing',                    8, 'Line',     0),
  ('6300',   'Sales & Marketing',              9, 'Line',     0),
  ('6400',   'General & Administrative',      10, 'Line',     0),
  ('OPEX',   'Total Operating Expenses',      11, 'Subtotal', 0),
  ('EBITDA', 'EBITDA',                        12, 'Subtotal', 0),
  ('EBITDAP','EBITDA %',                      13, 'Ratio',    1)
) t("P&L Key", "P&L Line", "P&L Sort", "Line Type", "Is Ratio");

-- ------------------------------------------------------------ FX rates
CREATE OR REPLACE TABLE fact_fx AS
SELECT month AS "Month", currency AS "Currency", lcy_per_eur AS "LCY per EUR" FROM stg_fx;

-- ---------------------------------------------------------- Sales fact
-- DQ01: deterministic de-duplication (prefer the most complete / valid copy)
CREATE OR REPLACE TABLE stg_sales_dedup AS
SELECT * FROM stg_sales
QUALIFY row_number() OVER (
    PARTITION BY order_id, line_no
    ORDER BY (qty_ordered > 0) DESC, (discount_pct IS NOT NULL) DESC,
             (delivery_date >= order_date) DESC, sku, qty_ordered DESC) = 1;

CREATE OR REPLACE TABLE fact_sales AS
WITH valid AS (                                   -- DQ03 quarantine negatives
    SELECT * FROM stg_sales_dedup WHERE qty_ordered > 0 AND qty_delivered >= 0
),
cust_disc AS (                                    -- DQ05 imputation basis
    SELECT customer_code, median(discount_pct) FILTER (WHERE NOT promo_flag) AS med_disc
    FROM valid WHERE discount_pct IS NOT NULL GROUP BY ALL
),
enriched AS (
    SELECT v.*,
           COALESCE(v.discount_pct, cd.med_disc, 0.08)          AS disc,
           (v.discount_pct IS NULL)::INTEGER                    AS discount_imputed,
           CASE WHEN v.delivery_date < v.order_date THEN NULL ELSE v.delivery_date END AS delivery_clean, -- DQ04
           fx.lcy_per_eur                                       AS fx_rate,
           COALESCE(fxpy.lcy_per_eur, fx.lcy_per_eur)           AS fx_rate_py,
           pc.std_cost_eur
    FROM valid v
    LEFT JOIN cust_disc cd USING (customer_code)
    JOIN stg_fx fx   ON fx.month = date_trunc('month', v.order_date) AND fx.currency = v.currency
    LEFT JOIN stg_fx fxpy ON fxpy.month = date_trunc('month', v.order_date) - INTERVAL 12 MONTH
                         AND fxpy.currency = v.currency
    LEFT JOIN stg_price_cost pc ON pc.sku = v.sku AND pc.year = year(v.order_date)
),
amounts AS (
    SELECT *,
           qty_delivered * unit_list_price_lcy                         AS gross_lcy,
           qty_delivered * unit_list_price_lcy * (1 - disc)            AS net_lcy,
           (qty_ordered - qty_delivered) * unit_list_price_lcy * (1 - disc) AS unfulfilled_lcy,
           -- functional currency: Bulgarian BGN history restated to EUR at the
           -- irrevocable euro conversion rate (1 EUR = 1.95583 BGN)
           CASE WHEN currency = 'BGN' THEN 'EUR' ELSE currency END     AS functional_currency,
           CASE WHEN currency = 'BGN' THEN 1.95583 ELSE 1 END          AS restate_div
    FROM enriched
),
cat_cost_ratio AS (                               -- DQ02 COGS estimate for unmapped SKUs
    SELECT split_part(a.sku, '-', 1) AS cat, year(a.order_date) AS yr,
           SUM(a.qty_delivered * a.std_cost_eur) / SUM(a.net_lcy / a.fx_rate) AS ratio
    FROM amounts a WHERE a.std_cost_eur IS NOT NULL GROUP BY ALL
)
SELECT a.order_id                                    AS "Order ID",
       a.line_no                                     AS "Line No",
       a.order_date                                  AS "Order Date",
       a.promised_date                               AS "Promised Date",
       a.ship_date                                   AS "Ship Date",
       a.delivery_clean                              AS "Delivery Date",
       a.customer_code                               AS "Customer Code",
       a.sku                                         AS "SKU",
       a.warehouse_code                              AS "Warehouse Code",
       a.country_code                                AS "Country Code",
       a.currency                                    AS "Transaction Currency",
       a.functional_currency                         AS "Functional Currency",
       a.promo_flag::INTEGER                         AS "Is Promo",
       a.qty_ordered                                 AS "Qty Ordered",
       a.qty_delivered                               AS "Qty Delivered",
       round(a.disc, 4)                              AS "Discount %",
       a.discount_imputed                            AS "Discount Imputed",
       a.fx_rate                                     AS "FX Rate",
       round(a.net_lcy / a.restate_div, 2)           AS "Net Sales LCY",
       round(a.gross_lcy / a.fx_rate, 2)             AS "Gross Sales EUR",
       round((a.gross_lcy - a.net_lcy) / a.fx_rate, 2) AS "Discount EUR",
       round(a.net_lcy / a.fx_rate, 2)               AS "Net Sales EUR",
       round(a.net_lcy / a.fx_rate_py, 2)            AS "Net Sales EUR @PY FX",
       round(COALESCE(a.qty_delivered * a.std_cost_eur, a.net_lcy / a.fx_rate * r.ratio), 2) AS "COGS EUR",
       (a.std_cost_eur IS NULL)::INTEGER             AS "COGS Estimated",
       round(a.unfulfilled_lcy / a.fx_rate, 2)       AS "Unfulfilled Net EUR",
       CASE WHEN a.delivery_clean IS NULL THEN NULL
            ELSE date_diff('day', a.order_date, a.delivery_clean) END AS "Lead Time Days",
       CASE WHEN a.delivery_clean IS NULL THEN NULL
            ELSE (a.delivery_clean <= a.promised_date)::INTEGER END   AS "On Time",
       (a.qty_delivered >= a.qty_ordered)::INTEGER   AS "In Full",
       CASE WHEN a.delivery_clean IS NULL THEN NULL
            ELSE (a.delivery_clean <= a.promised_date AND a.qty_delivered >= a.qty_ordered)::INTEGER END AS "OTIF"
FROM amounts a
LEFT JOIN cat_cost_ratio r ON r.cat = split_part(a.sku, '-', 1) AND r.yr = year(a.order_date)
ORDER BY a.order_date, a.order_id, a.line_no;

-- --------------------------------------------------------- Budget fact
CREATE OR REPLACE TABLE fact_budget AS
SELECT month AS "Month", country_code AS "Country Code", category_id AS "Category ID",
       round(budget_net_sales_eur, 2)                            AS "Budget Net Sales EUR",
       round(budget_gross_margin_eur, 2)                         AS "Budget Gross Margin EUR",
       round(budget_net_sales_eur - budget_gross_margin_eur, 2)  AS "Budget COGS EUR"
FROM stg_budget;

-- ----------------------------------------------------------- Opex fact
CREATE OR REPLACE TABLE fact_opex AS
SELECT month AS "Month", country_code AS "Country Code", account_code AS "P&L Key",
       round(SUM(amount_eur) FILTER (WHERE scenario = 'Actual'), 2) AS "Actual EUR",
       round(SUM(amount_eur) FILTER (WHERE scenario = 'Budget'), 2) AS "Budget EUR"
FROM stg_opex GROUP BY ALL;

-- ------------------------------------------------------ Inventory fact
CREATE OR REPLACE TABLE fact_inventory AS
SELECT i.snapshot_date AS "Snapshot Date", i.warehouse_code AS "Warehouse Code",
       w.country_code AS "Country Code", i.sku AS "SKU",
       i.on_hand_qty AS "On Hand Qty", i.on_hand_value_eur AS "On Hand Value EUR",
       i.stockout_days AS "Stockout Days",
       CASE WHEN p.discontinued_date IS NOT NULL AND p.discontinued_date < i.snapshot_date
            THEN 'Discontinued (aged)' ELSE 'Active' END AS "Stock Status"
FROM stg_inventory i
JOIN stg_warehouses w USING (warehouse_code)
JOIN stg_products p USING (sku);

-- ------------------------------------------------------------ DQ facts
CREATE OR REPLACE TABLE dq_results AS
SELECT check_id AS "Check ID", check_name AS "Check", dq_dimension AS "DQ Dimension",
       source_table AS "Source", business_rule AS "Business Rule", rows_checked AS "Rows Checked",
       rows_failed AS "Rows Failed", round(fail_pct / 100, 6) AS "Fail Rate", round(threshold_pct / 100, 6) AS "Tolerance",
       status AS "Status",
       CASE status WHEN 'Pass' THEN 1 WHEN 'Warning' THEN 2 ELSE 3 END AS "Status Sort",
       action_taken AS "Action Taken"
FROM dq_check_results;

CREATE OR REPLACE TABLE dq_exception_log AS
SELECT e.check_id AS "Check ID", r.check_name AS "Check", e.source_table AS "Source",
       e.record_key AS "Record", e.issue AS "Issue", e.observed_value AS "Observed Value"
FROM dq_exceptions e JOIN dq_check_results r USING (check_id);

CREATE OR REPLACE TABLE dq_load_log AS
SELECT period AS "Period", country_code AS "Country Code", loaded_on AS "Loaded On", lag_days AS "Lag Days",
       3 AS "SLA Days", CASE WHEN lag_days <= 3 THEN 'Within SLA' ELSE 'Late' END AS "SLA Status"
FROM stg_load_log;
