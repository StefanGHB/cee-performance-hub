import json, duckdb
M = "/home/claude/project/data/model"
con = duckdb.connect()
tmap = {"VARCHAR": "String", "DATE": "DateTime", "INTEGER": "Int64", "BIGINT": "Int64", "DOUBLE": "Double",
        "BOOLEAN": "Boolean", "HUGEINT": "Int64", "DECIMAL(18,3)": "Double"}
TABLES = [  # model name, parquet, description
 ("Date", "dim_date", "Calendar 2023-2027. Reporting cut-off (last closed month): 30 Sep 2026."),
 ("Country", "dim_country", "Operating countries with country manager (used for dynamic row-level security)."),
 ("Category", "dim_category", "Product categories (budget is set at this grain)."),
 ("Product", "dim_product", "Product master (PIM) incl. 'Unmapped SKU' members created by the DQ02 rule."),
 ("Customer", "dim_customer", "B2B customers (CRM) with channel, sales rep, acquisition cohort and churn status."),
 ("Warehouse", "dim_warehouse", "Distribution centres (WMS)."),
 ("P&L Line", "dim_pnl_line", "Management P&L structure used by the P&L matrix."),
 ("Sales", "fact_sales", "Invoiced order lines (ERP). Grain: order line. Amounts in EUR at monthly average FX."),
 ("Budget", "fact_budget", "FP&A sales & gross-margin budget. Grain: month x country x category."),
 ("Opex", "fact_opex", "Operating expenses actual vs budget (GL). Grain: month x country x account."),
 ("Inventory", "fact_inventory", "Month-end inventory snapshots (WMS). Semi-additive: use closing balance measures."),
 ("FX Rates", "fact_fx", "Monthly average FX rates, local currency units per 1 EUR (Treasury)."),
 ("Forecast", "fact_forecast", "ETS statistical forecast with 80%/95% prediction intervals (back-test + forward)."),
 ("Forecast Accuracy", "forecast_accuracy", "6-month hold-out accuracy per series: ETS vs seasonal-naive benchmark."),
 ("DQ Checks", "dq_results", "Data-quality rule results per ETL run."),
 ("DQ Exceptions", "dq_exception_log", "Row-level data-quality exceptions."),
 ("DQ Load Log", "dq_load_log", "Source feed load timeliness vs 3-day SLA."),
]
money_fmt = '#,0'
date_fmt = 'dd mmm yyyy'
hidden_all = {"Sales", "Budget", "Opex", "Inventory", "FX Rates", "Forecast"}
sort_by = {("Date", "Month"): "Month No", ("Date", "Month Short"): "Month No", ("Date", "Year Month"): "Year Month Sort",
           ("Date", "Year Quarter"): "Year Quarter Sort", ("Date", "Weekday"): "Weekday No",
           ("Category", "Category"): "Category Sort", ("P&L Line", "P&L Line"): "P&L Sort", ("DQ Checks", "Status"): "Status Sort"}
hide = {("Date", "Year Quarter Sort"), ("Date", "Year Month Sort"), ("Date", "Weekday No"), ("Category", "Category Sort"),
        ("P&L Line", "P&L Sort"), ("P&L Line", "P&L Key"), ("P&L Line", "Is Ratio"), ("P&L Line", "Line Type"), ("DQ Checks", "Status Sort"),
        ("Product", "Category ID"), ("Category", "Category ID"), ("Country", "Manager Email"),
        ("Forecast Accuracy", "Country Code"), ("Forecast Accuracy", "Category ID"), ("Forecast Accuracy", "Abs Error EUR"),
        ("Forecast Accuracy", "Actual EUR"), ("DQ Load Log", "Country Code"), ("Date", "Is YTD Month"), ("Date", "Month Offset"),
        ("Date", "Year Offset"), ("Date", "Is Actual Period")}
pct_cols = {"Discount %", "MAPE", "Bias", "Fail Rate", "Tolerance"}
defs = []
for name, pq, desc in TABLES:
    cols = con.execute(f"DESCRIBE SELECT * FROM '{M}/{pq}.parquet'").fetchall()
    cdefs = []
    for c in cols:
        cn, ct = c[0], c[1]
        dt = tmap.get(ct, "Double" if ct.startswith("DECIMAL") else None)
        assert dt, (name, cn, ct)
        d = {"name": cn, "dataType": dt, "sourceColumn": cn}
        if dt in ("Int64", "Double"):
            d["summarizeBy"] = "None"
            if dt == "Double":
                d["formatString"] = "0.0%" if cn in pct_cols else ("#,0.0000" if cn in ("FX Rate", "LCY per EUR") else money_fmt)
            else:
                d["formatString"] = "#,0" if cn not in ("Year", "Year Month Sort", "Year Quarter Sort") else "0"
        if dt == "DateTime":
            d["formatString"] = date_fmt
        if name in hidden_all or (name, cn) in hide:
            d["isHidden"] = True
        if (name, cn) in sort_by:
            d["sortByColumn"] = sort_by[(name, cn)]
        if name == "Date" and cn == "Date":
            d["isKey"] = True
        if name == "Country" and cn == "Country":
            d["dataCategory"] = "Country"
        if cn == "Customer" and name == "Customer":
            d["defaultLabel"] = True
        cdefs.append(d)
    m = (f'let\n    Source = Parquet.Document(File.Contents(DataFolder & "{pq}.parquet"))\nin\n    Source')
    defs.append({"name": name, "mode": "Import", "description": desc, "mExpression": m, "columns": cdefs})
json.dump(defs, open("table_defs.json", "w"), indent=0)
for d in defs:
    print(d["name"], len(d["columns"]))
