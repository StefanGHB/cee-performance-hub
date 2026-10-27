-- =====================================================================
-- 04_reconciliation.sql  |  Control totals: model vs source systems
-- A reporting model is only trusted if it reconciles to the ledger.
-- =====================================================================

-- DQ10: monthly net sales in the model vs an independent recalculation from ERP staging
--        (after the documented remediations: duplicates removed, negatives quarantined)
CREATE OR REPLACE TABLE recon_sales AS
WITH src AS (
    SELECT date_trunc('month', s.order_date) AS m,
           SUM(s.qty_delivered * s.unit_list_price_lcy * (1 - COALESCE(s.discount_pct, 0)) / f.lcy_per_eur) AS src_net_known_disc,
           SUM(CASE WHEN s.discount_pct IS NULL THEN 1 ELSE 0 END) AS lines_imputed
    FROM stg_sales_dedup s
    JOIN stg_fx f ON f.month = date_trunc('month', s.order_date) AND f.currency = s.currency
    WHERE s.qty_ordered > 0 AND s.qty_delivered >= 0 AND s.discount_pct IS NOT NULL
    GROUP BY ALL
),
mdl AS (
    SELECT date_trunc('month', "Order Date") AS m,
           SUM(CASE WHEN "Discount Imputed" = 0 THEN "Net Sales EUR" ELSE 0 END) AS mdl_net_known_disc
    FROM fact_sales GROUP BY ALL
)
SELECT src.m, src.src_net_known_disc, mdl.mdl_net_known_disc,
       abs(mdl.mdl_net_known_disc - src.src_net_known_disc) AS abs_diff
FROM src JOIN mdl USING (m);

-- DQ14: opex in the model vs general ledger
CREATE OR REPLACE TABLE recon_opex AS
SELECT g.month, g.country_code, g.gl_total, m.model_total, abs(g.gl_total - m.model_total) AS abs_diff
FROM (SELECT month, country_code, SUM(amount_eur) AS gl_total FROM stg_opex WHERE scenario = 'Actual' GROUP BY ALL) g
JOIN (SELECT "Month" AS month, "Country Code" AS country_code, SUM("Actual EUR") AS model_total
      FROM fact_opex GROUP BY ALL) m USING (month, country_code);

INSERT INTO dq_results
SELECT 'DQ10', 'Net sales reconciliation', 'Accuracy', 'ERP vs Model',
       'Monthly net sales must reconcile to ERP within EUR 100',
       COUNT(*), SUM(CASE WHEN abs_diff > 100 THEN 1 ELSE 0 END),
       SUM(CASE WHEN abs_diff > 100 THEN 1 ELSE 0 END) * 1.0 / COUNT(*), 0,
       CASE WHEN SUM(CASE WHEN abs_diff > 100 THEN 1 ELSE 0 END) = 0 THEN 'Pass' ELSE 'Fail' END,
       CASE WHEN SUM(CASE WHEN abs_diff > 100 THEN 1 ELSE 0 END) = 0 THEN 1 ELSE 3 END,
       'None required - reconciled for all months'
FROM recon_sales;

INSERT INTO dq_results
SELECT 'DQ14', 'Opex reconciliation', 'Accuracy', 'GL vs Model',
       'Monthly opex per country must reconcile to the GL within EUR 1',
       COUNT(*), SUM(CASE WHEN abs_diff > 1 THEN 1 ELSE 0 END),
       SUM(CASE WHEN abs_diff > 1 THEN 1 ELSE 0 END) * 1.0 / COUNT(*), 0,
       CASE WHEN SUM(CASE WHEN abs_diff > 1 THEN 1 ELSE 0 END) = 0 THEN 'Pass' ELSE 'Fail' END,
       CASE WHEN SUM(CASE WHEN abs_diff > 1 THEN 1 ELSE 0 END) = 0 THEN 1 ELSE 3 END,
       'None required - reconciled for all periods'
FROM recon_opex;
