-- =====================================================================
-- 02_data_quality_checks.sql  |  Rule-based DQ checks on RAW staging data
-- Each check records: dimension, rule, rows checked, rows failed,
-- tolerance threshold, resulting status and the remediation applied.
-- =====================================================================

CREATE OR REPLACE TABLE dq_exceptions (
    check_id VARCHAR, source_table VARCHAR, record_key VARCHAR, issue VARCHAR, observed_value VARCHAR);

-- DQ01 Uniqueness: exact duplicate order lines
INSERT INTO dq_exceptions
SELECT 'DQ01', 'ERP Sales Lines', order_id || ' / line ' || line_no, 'Duplicate order line',
       cnt || ' copies'
FROM (SELECT order_id, line_no, COUNT(*) AS cnt FROM stg_sales GROUP BY ALL HAVING COUNT(*) > 1);

-- DQ02 Referential integrity: SKU missing from product master
INSERT INTO dq_exceptions
SELECT 'DQ02', 'ERP Sales Lines', s.order_id || ' / line ' || s.line_no, 'SKU not in product master', s.sku
FROM stg_sales s LEFT JOIN stg_products p USING (sku) WHERE p.sku IS NULL;

-- DQ03 Validity: negative quantities
INSERT INTO dq_exceptions
SELECT 'DQ03', 'ERP Sales Lines', order_id || ' / line ' || line_no, 'Negative quantity',
       CAST(qty_ordered AS VARCHAR)
FROM stg_sales WHERE qty_ordered < 0 OR qty_delivered < 0;

-- DQ04 Validity: delivery date before order date
INSERT INTO dq_exceptions
SELECT 'DQ04', 'ERP Sales Lines', order_id || ' / line ' || line_no, 'Delivery date before order date',
       strftime(order_date, '%Y-%m-%d') || ' -> ' || strftime(delivery_date, '%Y-%m-%d')
FROM stg_sales WHERE delivery_date < order_date;

-- DQ05 Completeness: missing discount %
INSERT INTO dq_exceptions
SELECT 'DQ05', 'ERP Sales Lines', order_id || ' / line ' || line_no, 'Missing discount %', 'NULL'
FROM stg_sales WHERE discount_pct IS NULL;

-- DQ06 Completeness: customer without sales channel
INSERT INTO dq_exceptions
SELECT 'DQ06', 'CRM Customers', customer_code, 'Missing sales channel', 'NULL'
FROM stg_customers WHERE channel IS NULL;

-- DQ07 Consistency: non-standard country code
INSERT INTO dq_exceptions
SELECT 'DQ07', 'CRM Customers', customer_code, 'Non-standard country code', '"' || country_code || '"'
FROM stg_customers WHERE country_code <> upper(trim(country_code));

-- DQ08 Referential integrity: customer missing from CRM
INSERT INTO dq_exceptions
SELECT 'DQ08', 'ERP Sales Lines', s.order_id || ' / line ' || s.line_no, 'Customer not in CRM', s.customer_code
FROM stg_sales s LEFT JOIN stg_customers c USING (customer_code) WHERE c.customer_code IS NULL;

-- DQ09 Validity: invoiced list price deviates >2% from the official price list (converted to EUR)
INSERT INTO dq_exceptions
SELECT 'DQ09', 'ERP Sales Lines', s.order_id || ' / line ' || s.line_no, 'Price deviates from price list',
       CAST(round(s.unit_list_price_lcy / f.lcy_per_eur, 2) AS VARCHAR) || ' vs ' || CAST(pc.list_price_eur AS VARCHAR)
FROM stg_sales s
JOIN stg_fx f ON f.month = date_trunc('month', s.order_date) AND f.currency = s.currency
JOIN stg_price_cost pc ON pc.sku = s.sku AND pc.year = year(s.order_date)
WHERE abs(s.unit_list_price_lcy / f.lcy_per_eur / pc.list_price_eur - 1) > 0.02;

-- DQ11 Timeliness: monthly feeds loaded later than the 3-day SLA
INSERT INTO dq_exceptions
SELECT 'DQ11', 'ETL Load Log', country_code || ' ' || strftime(period, '%Y-%m'), 'Feed loaded after SLA',
       lag_days || ' days after month-end'
FROM stg_load_log WHERE lag_days > 3;

-- DQ12 Completeness: missing budget cell (country x category x month)
INSERT INTO dq_exceptions
SELECT 'DQ12', 'FP&A Budget', c.country_code || ' ' || k.category_id || ' ' || strftime(m.month, '%Y-%m'),
       'Missing budget cell', 'NULL'
FROM (SELECT DISTINCT country_code FROM stg_countries) c
CROSS JOIN stg_categories k
CROSS JOIN (SELECT DISTINCT month FROM stg_budget) m
LEFT JOIN stg_budget b ON b.country_code = c.country_code AND b.category_id = k.category_id AND b.month = m.month
WHERE b.month IS NULL;

-- DQ13 Consistency: FX rate missing for a sales month / currency
INSERT INTO dq_exceptions
SELECT 'DQ13', 'Treasury FX', s.currency || ' ' || strftime(s.m, '%Y-%m'), 'Missing FX rate', 'NULL'
FROM (SELECT DISTINCT date_trunc('month', order_date) AS m, currency FROM stg_sales) s
LEFT JOIN stg_fx f ON f.month = s.m AND f.currency = s.currency
WHERE f.month IS NULL;

-- ---------------------------------------------------------------------
-- Summary per check
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE dq_check_results AS
WITH defs AS (
    SELECT * FROM (VALUES
     ('DQ01', 'Duplicate order lines',            'Uniqueness',            'ERP Sales Lines', 'Order ID + line number must be unique',                 (SELECT COUNT(*) FROM stg_sales),     0.10, 'Duplicates removed (first record kept)'),
     ('DQ02', 'Unknown SKU on order line',        'Referential integrity', 'ERP Sales Lines', 'Every SKU must exist in the product master (PIM)',       (SELECT COUNT(*) FROM stg_sales),     0.05, 'Mapped to "Unmapped SKU" members; sent to PIM team'),
     ('DQ03', 'Negative quantity',                'Validity',              'ERP Sales Lines', 'Quantities must be > 0 (returns use a separate flow)',   (SELECT COUNT(*) FROM stg_sales),     0.10, 'Quarantined - excluded from reporting'),
     ('DQ04', 'Delivery before order date',       'Validity',              'ERP Sales Lines', 'Delivery date must be on/after order date',              (SELECT COUNT(*) FROM stg_sales),     0.05, 'Delivery date blanked; line excluded from OTIF'),
     ('DQ05', 'Missing discount %',               'Completeness',          'ERP Sales Lines', 'Discount % must be populated',                           (SELECT COUNT(*) FROM stg_sales),     0.20, 'Imputed with customer median discount'),
     ('DQ06', 'Customer without channel',         'Completeness',          'CRM Customers',   'Every customer must have a sales channel',               (SELECT COUNT(*) FROM stg_customers), 0.20, 'Set to "Unassigned"; CRM owner notified'),
     ('DQ07', 'Non-standard country code',        'Consistency',           'CRM Customers',   'ISO 3166 alpha-2, upper case, no spaces',                (SELECT COUNT(*) FROM stg_customers), 0.50, 'Standardised (trim + upper case)'),
     ('DQ08', 'Unknown customer on order line',   'Referential integrity', 'ERP Sales Lines', 'Every customer must exist in CRM',                       (SELECT COUNT(*) FROM stg_sales),     0.05, 'None required'),
     ('DQ09', 'Price deviates from price list',   'Validity',              'ERP Sales Lines', 'Invoiced list price within 2% of the official price list', (SELECT COUNT(*) FROM stg_sales),   0.50, 'None required'),
     ('DQ11', 'Late data feed',                   'Timeliness',            'ETL Load Log',    'Country feed loaded within 3 days of month-end',         (SELECT COUNT(*) FROM stg_load_log),  0.10, 'Flagged on report; owner escalated'),
     ('DQ12', 'Missing budget cell',              'Completeness',          'FP&A Budget',     'Budget for every country x category x month',            (SELECT COUNT(*) FROM stg_budget),    0.00, 'None required'),
     ('DQ13', 'Missing FX rate',                  'Consistency',           'Treasury FX',     'FX rate for every currency and month with sales',        (SELECT COUNT(*) FROM stg_fx),        0.00, 'None required')
    ) t(check_id, check_name, dq_dimension, source_table, business_rule, rows_checked, threshold_pct, action_taken)
),
fails AS (SELECT check_id, COUNT(*) AS rows_failed FROM dq_exceptions GROUP BY ALL)
SELECT d.check_id, d.check_name, d.dq_dimension, d.source_table, d.business_rule,
       d.rows_checked, COALESCE(f.rows_failed, 0) AS rows_failed,
       COALESCE(f.rows_failed, 0) * 100.0 / NULLIF(d.rows_checked, 0) AS fail_pct,
       d.threshold_pct,
       CASE WHEN COALESCE(f.rows_failed, 0) = 0 THEN 'Pass'
            WHEN COALESCE(f.rows_failed, 0) * 100.0 / d.rows_checked <= d.threshold_pct THEN 'Pass'
            WHEN COALESCE(f.rows_failed, 0) * 100.0 / d.rows_checked <= d.threshold_pct * 5 THEN 'Warning'
            ELSE 'Fail' END AS status,
       d.action_taken
FROM defs d LEFT JOIN fails f USING (check_id);
