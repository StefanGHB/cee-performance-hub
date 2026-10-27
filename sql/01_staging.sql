-- =====================================================================
-- 01_staging.sql  |  Load raw source extracts with explicit data types
-- Engine: DuckDB.  ${RAW} is replaced by the runner with the raw folder.
-- =====================================================================

CREATE OR REPLACE TABLE stg_sales AS
SELECT *
FROM read_csv('${RAW}/erp_sales_lines_*.csv', header = true, union_by_name = true,
    columns = {
        'order_id': 'VARCHAR', 'line_no': 'INTEGER', 'order_date': 'DATE', 'customer_code': 'VARCHAR',
        'sku': 'VARCHAR', 'warehouse_code': 'VARCHAR', 'country_code': 'VARCHAR', 'currency': 'VARCHAR',
        'qty_ordered': 'INTEGER', 'qty_delivered': 'INTEGER', 'unit_list_price_lcy': 'DOUBLE',
        'discount_pct': 'DOUBLE', 'promo_flag': 'BOOLEAN', 'promised_date': 'DATE', 'ship_date': 'DATE',
        'delivery_date': 'DATE'});

CREATE OR REPLACE TABLE stg_customers AS
SELECT * FROM read_csv('${RAW}/crm_customers.csv', header = true,
    columns = {
        'customer_code': 'VARCHAR', 'customer_name': 'VARCHAR', 'country_code': 'VARCHAR', 'city': 'VARCHAR',
        'warehouse_code': 'VARCHAR', 'channel': 'VARCHAR', 'sales_rep': 'VARCHAR', 'customer_since': 'DATE',
        'churn_date': 'DATE'});

CREATE OR REPLACE TABLE stg_products AS
SELECT * FROM read_csv('${RAW}/pim_products.csv', header = true,
    columns = {
        'sku': 'VARCHAR', 'product_name': 'VARCHAR', 'brand': 'VARCHAR', 'category_id': 'VARCHAR',
        'variant': 'VARCHAR', 'pack_size': 'VARCHAR', 'list_price_2023_eur': 'DOUBLE', 'launch_date': 'DATE',
        'discontinued_date': 'DATE', 'status': 'VARCHAR'});

CREATE OR REPLACE TABLE stg_price_cost AS
SELECT * FROM read_csv('${RAW}/erp_price_cost_list.csv', header = true,
    columns = {'sku': 'VARCHAR', 'year': 'INTEGER', 'std_cost_eur': 'DOUBLE', 'list_price_eur': 'DOUBLE'});

CREATE OR REPLACE TABLE stg_categories AS SELECT * FROM read_csv('${RAW}/pim_categories.csv', header = true);
CREATE OR REPLACE TABLE stg_warehouses AS SELECT * FROM read_csv('${RAW}/wms_warehouses.csv', header = true);
CREATE OR REPLACE TABLE stg_countries  AS SELECT * FROM read_csv('${RAW}/mdm_countries.csv', header = true);
CREATE OR REPLACE TABLE stg_accounts   AS SELECT * FROM read_csv('${RAW}/gl_accounts.csv', header = true,
    columns = {'account_code': 'VARCHAR', 'account_name': 'VARCHAR'});

CREATE OR REPLACE TABLE stg_fx AS
SELECT * FROM read_csv('${RAW}/treasury_fx_monthly.csv', header = true,
    columns = {'month': 'DATE', 'currency': 'VARCHAR', 'lcy_per_eur': 'DOUBLE'});

CREATE OR REPLACE TABLE stg_budget AS
SELECT * FROM read_csv('${RAW}/fpa_budget_sales.csv', header = true,
    columns = {'month': 'DATE', 'country_code': 'VARCHAR', 'category_id': 'VARCHAR',
               'budget_net_sales_eur': 'DOUBLE', 'budget_gross_margin_eur': 'DOUBLE'});

CREATE OR REPLACE TABLE stg_opex AS
SELECT * FROM read_csv('${RAW}/gl_opex_monthly.csv', header = true,
    columns = {'month': 'DATE', 'country_code': 'VARCHAR', 'account_code': 'VARCHAR', 'scenario': 'VARCHAR',
               'amount_eur': 'DOUBLE'});

CREATE OR REPLACE TABLE stg_inventory AS
SELECT * FROM read_csv('${RAW}/wms_inventory_snapshot.csv', header = true,
    columns = {'snapshot_date': 'DATE', 'warehouse_code': 'VARCHAR', 'sku': 'VARCHAR', 'on_hand_qty': 'INTEGER',
               'on_hand_value_eur': 'DOUBLE', 'stockout_days': 'INTEGER'});

CREATE OR REPLACE TABLE stg_load_log AS
SELECT * FROM read_csv('${RAW}/etl_load_log.csv', header = true,
    columns = {'period': 'DATE', 'country_code': 'VARCHAR', 'loaded_on': 'DATE', 'lag_days': 'INTEGER'});
