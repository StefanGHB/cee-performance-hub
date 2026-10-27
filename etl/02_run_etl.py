"""
Step 2 - ETL: raw extracts -> data-quality checks -> star schema (Parquet) for Power BI.
Runs the SQL scripts in ../sql in order using DuckDB.

Run:  python 02_run_etl.py
"""
import os
import time

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW = os.path.join(ROOT, "data", "raw").replace("\\", "/")
OUT = os.path.join(ROOT, "data", "model")
AS_OF = "2026-09-30"
os.makedirs(OUT, exist_ok=True)

SCRIPTS = ["01_staging.sql", "02_data_quality_checks.sql", "03_transform_star_schema.sql",
           "04_reconciliation.sql"]
EXPORTS = {  # duckdb table -> parquet file consumed by Power BI
    "dim_date": "dim_date", "dim_country": "dim_country", "dim_category": "dim_category",
    "dim_product": "dim_product", "dim_customer": "dim_customer", "dim_warehouse": "dim_warehouse",
    "dim_pnl_line": "dim_pnl_line", "fact_sales": "fact_sales", "fact_budget": "fact_budget",
    "fact_opex": "fact_opex", "fact_inventory": "fact_inventory", "fact_fx": "fact_fx",
    "dq_results": "dq_results", "dq_exception_log": "dq_exception_log", "dq_load_log": "dq_load_log",
}

con = duckdb.connect(os.path.join(ROOT, "data", "etl_workspace.duckdb"))
t0 = time.time()
for script in SCRIPTS:
    sql = open(os.path.join(ROOT, "sql", script), encoding="utf-8").read()
    sql = sql.replace("${RAW}", RAW).replace("${AS_OF}", AS_OF)
    con.execute(sql)
    print(f"  ran {script}")

for tbl, name in EXPORTS.items():
    path = os.path.join(OUT, f"{name}.parquet").replace("\\", "/")
    con.execute(f"COPY {tbl} TO '{path}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    n = con.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
    print(f"  exported {name:<18} {n:>9,} rows")

print("\nData-quality summary:")
for r in con.execute('SELECT "Check ID", "Check", "Rows Failed", "Status" FROM dq_results ORDER BY 1').fetchall():
    print(f"  {r[0]}  {r[1]:<34} failed={r[2]:<6} {r[3]}")
print(f"\nETL finished in {time.time() - t0:.1f}s")
con.close()
