"""All report measures: name, folder, expression, format, description."""
import json

EUR = '€#,0'
PCT = '0.0%'
PCT_D = '+0.0%;-0.0%;0.0%'
PP = '+0.0 "pp";-0.0 "pp";0.0 "pp"'
INT = '#,0'
DEC1 = '#,0.0'

# dynamic format strings (auto-scale to K / M)
FMT_EUR = 'VAR v = ABS(SELECTEDMEASURE()) RETURN IF(v >= 1E6, "€#,0,,.0\\"M\\"", IF(v >= 1E3, "€#,0,\\"K\\"", "€#,0"))'
FMT_VAR = ('VAR v = ABS(SELECTEDMEASURE()) RETURN IF(v >= 1E6, "+€#,0,,.0\\"M\\";-€#,0,,.0\\"M\\"", '
           'IF(v >= 1E3, "+€#,0,\\"K\\";-€#,0,\\"K\\"", "+€#,0;-€#,0"))')

F1, F2, F3, F4, F5, F6, F7, F8, F9, F10 = (
    "01 Sales", "02 Profitability", "03 Budget", "04 Time Intelligence", "05 FX & Price-Volume-Mix",
    "06 Operations", "07 Forecast", "08 Scenario", "09 Data Quality", "10 Report UI")

PY = "CALCULATETABLE(SAMEPERIODLASTYEAR('Date'[Date]), 'Date'[Is Actual Period] = TRUE())"
PYTD = "CALCULATETABLE(SAMEPERIODLASTYEAR(DATESYTD('Date'[Date])), 'Date'[Is Actual Period] = TRUE())"
NOT_ALLOCABLE = "ISCROSSFILTERED('Product') || ISCROSSFILTERED(Customer) || ISCROSSFILTERED(Warehouse)"
BUDGET_GUARD = "ISFILTERED('Product') || ISCROSSFILTERED(Customer) || ISCROSSFILTERED(Warehouse)"

M = []


def m(name, folder, expr, fmt=None, desc="", dyn=None, hidden=False):
    d = {"name": name, "tableName": "_Measures", "displayFolder": folder, "expression": expr.strip(),
         "description": desc}
    # Static format strings on purpose: dynamic (K/M) format strings double-scale
    # when a visual applies Auto display units (shows "€0.0MM"), so scaling is left to visuals.
    if dyn == FMT_VAR and name != "Bridge Value":
        d["formatString"] = '+€#,0;-€#,0;€0'
    elif dyn:
        d["formatString"] = '€#,0;-€#,0' if name == "Bridge Value" else EUR
    elif fmt:
        d["formatString"] = fmt
    if hidden:
        d["isHidden"] = True
    M.append(d)


# ------------------------------------------------------------------ 01 Sales
m("Net Sales", F1, "SUM(Sales[Net Sales EUR])", EUR,
  "Invoiced net sales in EUR (gross sales less discounts & promotions), converted at monthly average FX.", FMT_EUR)
m("Gross Sales", F1, "SUM(Sales[Gross Sales EUR])", EUR, "Delivered quantity x list price, EUR.", FMT_EUR)
m("Discounts", F1, "SUM(Sales[Discount EUR])", EUR, "Trade discounts and promotional allowances, EUR.", FMT_EUR)
m("Discount %", F1, "DIVIDE([Discounts], [Gross Sales])", PCT, "Discounts as % of gross sales.")
m("Units", F1, "SUM(Sales[Qty Delivered])", INT, "Delivered units (cases).")
m("Orders", F1, "DISTINCTCOUNT(Sales[Order ID])", INT, "Number of distinct sales orders.")
m("Order Lines", F1, "COUNTROWS(Sales)", INT, "Number of order lines.")
m("Avg Order Value", F1, "DIVIDE([Net Sales], [Orders])", EUR, "Net sales per order.", FMT_EUR)
m("Avg Net Price per Unit", F1, "DIVIDE([Net Sales], [Units])", '€#,0.00', "Net sales per delivered unit.")
m("Promo Sales %", F1, "DIVIDE(CALCULATE([Net Sales], Sales[Is Promo] = 1), [Net Sales])", PCT,
  "Share of net sales sold on promotion.")
m("Active Customers", F1, "DISTINCTCOUNT(Sales[Customer Code])", INT, "Customers with at least one invoice in the period.")
m("Net Sales per Customer", F1, "DIVIDE([Net Sales], [Active Customers])", EUR, "Average net sales per active customer.", FMT_EUR)
m("New Customers", F1, """
VAR _start = MIN('Date'[Date])
VAR _end = MAX('Date'[Date])
RETURN
    IF(
        NOT ISBLANK([Net Sales]),
        COUNTROWS(
            FILTER(
                VALUES(Sales[Customer Code]),
                VAR _since = LOOKUPVALUE(Customer[Customer Since], Customer[Customer Code], Sales[Customer Code])
                RETURN _since >= _start && _since <= _end
            )
        ) + 0
    )
""", INT, "Customers acquired (CRM 'customer since' date) in the period that already placed an order.")
m("Churned Customers", F1, """
VAR _start = MIN('Date'[Date])
VAR _end = MAX('Date'[Date])
VAR _customers = CALCULATETABLE(VALUES(Sales[Customer Code]), REMOVEFILTERS('Date'))
RETURN
    IF(
        _start <= [Last Actual Date],
        COUNTROWS(
            FILTER(
                _customers,
                VAR _churn = LOOKUPVALUE(Customer[Churn Date], Customer[Customer Code], Sales[Customer Code])
                RETURN NOT ISBLANK(_churn) && _churn >= _start && _churn <= _end
            )
        ) + 0
    )
""", INT, "Customers whose CRM churn date falls in the period.")
m("Unfulfilled Demand", F1, "SUM(Sales[Unfulfilled Net EUR])", EUR,
  "Net value of ordered quantity that was not delivered (short shipments) - lost sales opportunity.", FMT_EUR)
m("Unfulfilled Demand %", F1, "DIVIDE([Unfulfilled Demand], [Net Sales] + [Unfulfilled Demand])", PCT,
  "Unfulfilled demand as % of total demand.")
m("Net Sales LCY", F1, """
IF(
    DISTINCTCOUNT(Sales[Functional Currency]) = 1,
    SUM(Sales[Net Sales LCY])
)
""", '#,0', "Net sales in the country's functional currency. Blank when several currencies are mixed. BGN history restated to EUR at 1.95583.")
m("Customer Rank", F1, """
IF(
    HASONEVALUE(Customer[Customer]) && NOT ISBLANK([Net Sales]),
    RANKX(ALLSELECTED(Customer[Customer]), [Net Sales], , DESC, Dense)
)
""", INT, "Rank of the customer by net sales within the current selection.")
m("Cumulative Customer Share %", F1, """
VAR _total = CALCULATE([Net Sales], ALLSELECTED(Customer))
VAR _current = [Net Sales]
VAR _tbl =
    FILTER(
        ADDCOLUMNS(ALLSELECTED(Customer[Customer]), "@ns", [Net Sales]),
        NOT ISBLANK([@ns])
    )
VAR _cum = SUMX(FILTER(_tbl, [@ns] >= _current), [@ns])
RETURN IF(NOT ISBLANK(_current), DIVIDE(_cum, _total))
""", PCT, "Pareto: cumulative share of net sales of customers ranked at or above the current customer.")
m("Top 20% Customers Share", F1, """
VAR _tbl =
    FILTER(ADDCOLUMNS(VALUES(Sales[Customer Code]), "@ns", [Net Sales]), [@ns] > 0)
VAR _n = COUNTROWS(_tbl)
VAR _top = TOPN(ROUNDUP(_n * 0.2, 0), _tbl, [@ns], DESC)
RETURN DIVIDE(SUMX(_top, [@ns]), SUMX(_tbl, [@ns]))
""", PCT, "Share of net sales generated by the top 20% of customers (concentration risk).")

# ------------------------------------------------------------ 02 Profitability
m("COGS", F2, "SUM(Sales[COGS EUR])", EUR, "Cost of goods sold at standard cost, EUR.", FMT_EUR)
m("Gross Margin", F2, "[Net Sales] - [COGS]", EUR, "Net sales less COGS.", FMT_EUR)
m("Gross Margin %", F2, "DIVIDE([Gross Margin], [Net Sales])", PCT, "Gross margin as % of net sales.")
m("Opex", F2, f"""
IF(
    NOT ({NOT_ALLOCABLE}),
    SUM(Opex[Actual EUR])
)
""", EUR, "Operating expenses (GL actuals). Not allocated to products, customers or warehouses - blank at those levels.", FMT_EUR)
m("Opex % of Sales", F2, "DIVIDE([Opex], [Net Sales])", PCT, "Operating expenses as % of net sales.")
m("Logistics Cost % of Sales", F2, "DIVIDE(CALCULATE([Opex], 'P&L Line'[P&L Key] = \"6100\"), [Net Sales])", PCT,
  "Logistics & transport cost as % of net sales.")
m("EBITDA", F2, f"IF(NOT ({NOT_ALLOCABLE}), [Gross Margin] - [Opex])", EUR,
  "Gross margin less operating expenses. Available at company / country / period level.", FMT_EUR)
m("EBITDA %", F2, "DIVIDE([EBITDA], [Net Sales])", PCT, "EBITDA margin.")

# ------------------------------------------------------------------ 03 Budget
m("Budget Net Sales", F3, f"IF(NOT ({BUDGET_GUARD}), SUM(Budget[Budget Net Sales EUR]))", EUR,
  "FP&A budget net sales (set at month x country x category).", FMT_EUR)
m("Budget Gross Margin", F3, f"IF(NOT ({BUDGET_GUARD}), SUM(Budget[Budget Gross Margin EUR]))", EUR,
  "FP&A budget gross margin.", FMT_EUR)
m("Budget COGS", F3, "[Budget Net Sales] - [Budget Gross Margin]", EUR, "Budget cost of goods sold.", FMT_EUR)
m("Budget Gross Margin %", F3, "DIVIDE([Budget Gross Margin], [Budget Net Sales])", PCT, "Budget gross margin %.")
m("Budget Opex", F3, f"IF(NOT ({NOT_ALLOCABLE}), SUM(Opex[Budget EUR]))", EUR, "Budget operating expenses.", FMT_EUR)
m("Budget EBITDA", F3, "[Budget Gross Margin] - [Budget Opex]", EUR, "Budget EBITDA.", FMT_EUR)
m("Budget EBITDA %", F3, "DIVIDE([Budget EBITDA], [Budget Net Sales])", PCT, "Budget EBITDA margin.")
m("Budget Net Sales (Closed Periods)", F3,
  "CALCULATE([Budget Net Sales], KEEPFILTERS('Date'[Is Actual Period] = TRUE()))", EUR,
  "Budget for the months that already have actuals - the like-for-like comparison base.", FMT_EUR)
m("Budget Gross Margin (Closed Periods)", F3,
  "CALCULATE([Budget Gross Margin], KEEPFILTERS('Date'[Is Actual Period] = TRUE()))", EUR,
  "Budget gross margin for closed months.", FMT_EUR)
m("Budget EBITDA (Closed Periods)", F3,
  "CALCULATE([Budget EBITDA], KEEPFILTERS('Date'[Is Actual Period] = TRUE()))", EUR,
  "Budget EBITDA for closed months.", FMT_EUR)
m("Net Sales vs Budget", F3,
  "IF(NOT ISBLANK([Net Sales]) && NOT ISBLANK([Budget Net Sales (Closed Periods)]), [Net Sales] - [Budget Net Sales (Closed Periods)])",
  EUR, "Actual net sales minus budget (closed months only).", FMT_VAR)
m("Net Sales vs Budget %", F3, "DIVIDE([Net Sales vs Budget], [Budget Net Sales (Closed Periods)])", PCT_D,
  "Net sales variance to budget, %.")
m("Budget Achievement %", F3, "DIVIDE([Net Sales], [Budget Net Sales (Closed Periods)])", PCT,
  "Actual net sales as % of budget (closed months).")
m("Gross Margin vs Budget", F3,
  "IF(NOT ISBLANK([Gross Margin]) && NOT ISBLANK([Budget Gross Margin (Closed Periods)]), [Gross Margin] - [Budget Gross Margin (Closed Periods)])",
  EUR, "Gross margin variance to budget (closed months).", FMT_VAR)
m("Gross Margin % vs Budget (pp)", F3, """
VAR _b = DIVIDE([Budget Gross Margin (Closed Periods)], [Budget Net Sales (Closed Periods)])
RETURN IF(NOT ISBLANK([Gross Margin %]) && NOT ISBLANK(_b), ([Gross Margin %] - _b) * 100)
""", PP, "Gross margin % difference to budget in percentage points.")
m("EBITDA vs Budget", F3,
  "IF(NOT ISBLANK([EBITDA]) && NOT ISBLANK([Budget EBITDA (Closed Periods)]), [EBITDA] - [Budget EBITDA (Closed Periods)])",
  EUR, "EBITDA variance to budget (closed months).", FMT_VAR)

# -------------------------------------------------------- 04 Time Intelligence
m("Last Actual Date", F4, "CALCULATE(MAX('Date'[Date]), 'Date'[Is Actual Period] = TRUE(), REMOVEFILTERS('Date'))",
  'dd mmm yyyy', "Reporting cut-off: last day of the last closed month.")
m("Net Sales PY", F4, f"CALCULATE([Net Sales], {PY})", EUR,
  "Net sales in the same period last year (like-for-like: only months that are closed in the current year).", FMT_EUR)
m("Net Sales YoY", F4, "IF(NOT ISBLANK([Net Sales]) && NOT ISBLANK([Net Sales PY]), [Net Sales] - [Net Sales PY])",
  EUR, "Net sales change vs prior year.", FMT_VAR)
m("Net Sales YoY %", F4, "DIVIDE([Net Sales YoY], [Net Sales PY])", PCT_D, "Net sales growth vs prior year.")
m("Net Sales YTD", F4, "CALCULATE([Net Sales], DATESYTD('Date'[Date]))", EUR, "Year-to-date net sales.", FMT_EUR)
m("Net Sales PY YTD", F4, f"CALCULATE([Net Sales], {PYTD})", EUR, "Prior-year year-to-date net sales (same months).", FMT_EUR)
m("Net Sales YTD YoY %", F4, "DIVIDE([Net Sales YTD] - [Net Sales PY YTD], [Net Sales PY YTD])", PCT_D,
  "Year-to-date growth vs prior year.")
m("Net Sales R12M", F4, """
VAR _end = MIN(MAX('Date'[Date]), [Last Actual Date])
RETURN CALCULATE([Net Sales], DATESINPERIOD('Date'[Date], _end, -12, MONTH))
""", EUR, "Rolling 12-month net sales ending at the last closed date in context.", FMT_EUR)
m("Gross Margin PY", F4, f"CALCULATE([Gross Margin], {PY})", EUR, "Gross margin, same period last year.", FMT_EUR)
m("Gross Margin YoY %", F4, "DIVIDE([Gross Margin] - [Gross Margin PY], [Gross Margin PY])", PCT_D,
  "Gross margin growth vs prior year.")
m("Gross Margin % PY", F4, f"CALCULATE([Gross Margin %], {PY})", PCT, "Gross margin %, same period last year.")
m("Gross Margin % YoY (pp)", F4,
  "IF(NOT ISBLANK([Gross Margin %]) && NOT ISBLANK([Gross Margin % PY]), ([Gross Margin %] - [Gross Margin % PY]) * 100)",
  PP, "Gross margin % change vs prior year, percentage points.")
m("EBITDA PY", F4, f"CALCULATE([EBITDA], {PY})", EUR, "EBITDA, same period last year.", FMT_EUR)
m("EBITDA YoY %", F4, "DIVIDE([EBITDA] - [EBITDA PY], ABS([EBITDA PY]))", PCT_D, "EBITDA growth vs prior year.")
m("EBITDA % PY", F4, f"CALCULATE([EBITDA %], {PY})", PCT, "EBITDA margin, same period last year.")
m("Units PY", F4, f"CALCULATE([Units], {PY})", INT, "Units, same period last year.")
m("Active Customers PY", F4, f"CALCULATE([Active Customers], {PY})", INT, "Active customers, same period last year.")
m("OTIF % PY", F4, f"CALCULATE([OTIF %], {PY})", PCT, "OTIF, same period last year.")

# ------------------------------------------------------ 05 FX & PVM
m("Net Sales @ PY FX", F5, "SUM(Sales[Net Sales EUR @PY FX])", EUR,
  "Current-period local-currency sales translated at prior-year FX rates (constant currency).", FMT_EUR)
m("FX Impact", F5, "IF(NOT ISBLANK([Net Sales]), [Net Sales] - [Net Sales @ PY FX])", EUR,
  "Translation effect of exchange-rate movements on EUR net sales.", FMT_VAR)
m("Constant Currency Growth %", F5, "DIVIDE([Net Sales @ PY FX] - [Net Sales PY], [Net Sales PY])", PCT_D,
  "Net sales growth excluding FX translation effects.")
m("Volume Effect", F5, """
VAR _unitsCY = [Units]
VAR _unitsPY = [Units PY]
VAR _avgPricePY = DIVIDE([Net Sales PY], _unitsPY)
RETURN IF(NOT ISBLANK(_unitsPY) && NOT ISBLANK(_unitsCY), (_unitsCY - _unitsPY) * _avgPricePY)
""", EUR, "Change in net sales explained by total volume at prior-year average price.", FMT_VAR)
m("Price Effect", F5, """
IF(
    NOT ISBLANK([Net Sales PY]) && NOT ISBLANK([Net Sales]),
    SUMX(
        VALUES('Product'[SKU]),
        VAR _uCY = [Units]
        VAR _uPY = [Units PY]
        VAR _pCY = DIVIDE([Net Sales @ PY FX], _uCY)
        VAR _pPY = DIVIDE([Net Sales PY], _uPY)
        RETURN IF(_uCY > 0 && _uPY > 0, _uCY * (_pCY - _pPY))
    )
)
""", EUR, "Net price realisation (list price & discount changes) per SKU at constant FX.", FMT_VAR)
m("FX Effect", F5, "IF(NOT ISBLANK([Net Sales PY]), [FX Impact])", EUR, "FX translation effect (bridge step).", FMT_VAR)
m("Mix & Other Effect", F5, """
IF(
    NOT ISBLANK([Net Sales PY]) && NOT ISBLANK([Net Sales]),
    [Net Sales] - [Net Sales PY] - [Volume Effect] - [Price Effect] - [FX Effect]
)
""", EUR, "Residual: product / customer mix, new and discontinued SKUs.", FMT_VAR)
m("Bridge Value", F5, """
SWITCH(
    SELECTEDVALUE('Bridge Step'[Step]),
    "Net Sales PY", [Net Sales PY],
    "Volume", [Volume Effect],
    "Price", [Price Effect],
    "Mix & Other", [Mix & Other Effect],
    "FX", [FX Effect]
)
""", EUR, "Value of each step of the net sales bridge (use with 'Bridge Step'[Step] in a waterfall).", FMT_VAR)

# ------------------------------------------------------------ 06 Operations
m("OTIF %", F6, "AVERAGE(Sales[OTIF])", PCT, "Order lines delivered on time AND in full (lines with an invalid delivery date excluded).")
m("On-Time %", F6, "AVERAGE(Sales[On Time])", PCT, "Order lines delivered on or before the promised date.")
m("In-Full %", F6, "AVERAGE(Sales[In Full])", PCT, "Order lines delivered with the full ordered quantity.")
m("Fill Rate %", F6, "DIVIDE(SUM(Sales[Qty Delivered]), SUM(Sales[Qty Ordered]))", PCT, "Delivered units / ordered units.")
m("OTIF Target", F6, "0.95", PCT, "Service-level target for OTIF.")
m("OTIF vs Target (pp)", F6, "IF(NOT ISBLANK([OTIF %]), ([OTIF %] - [OTIF Target]) * 100)", PP, "OTIF gap to target, percentage points.")
m("Avg Lead Time (days)", F6, "AVERAGE(Sales[Lead Time Days])", DEC1, "Average days from order to delivery.")
m("Late Lines", F6, "CALCULATE(COUNTROWS(Sales), Sales[On Time] = 0)", INT, "Order lines delivered after the promised date.")
m("Inventory Value", F6, """
VAR _lastSnapshot = CALCULATE(MAX(Inventory[Snapshot Date]), ALL(Inventory), VALUES('Date'[Date]))
RETURN CALCULATE(SUM(Inventory[On Hand Value EUR]), 'Date'[Date] = _lastSnapshot)
""", EUR, "Closing inventory value at standard cost (semi-additive: last month-end in the period).", FMT_EUR)
m("Inventory Units", F6, """
VAR _lastSnapshot = CALCULATE(MAX(Inventory[Snapshot Date]), ALL(Inventory), VALUES('Date'[Date]))
RETURN CALCULATE(SUM(Inventory[On Hand Qty]), 'Date'[Date] = _lastSnapshot)
""", INT, "Closing inventory units (last month-end in the period).")
m("Days of Inventory", F6, """
VAR _lastSnapshot = CALCULATE(MAX(Inventory[Snapshot Date]), ALL(Inventory), VALUES('Date'[Date]))
VAR _period = DATESINPERIOD('Date'[Date], _lastSnapshot, -3, MONTH)
VAR _cogs = CALCULATE([COGS], _period)
VAR _days = COUNTROWS(_period)
RETURN DIVIDE([Inventory Value], DIVIDE(_cogs, _days))
""", DEC1, "Closing inventory / average daily COGS of the trailing 3 months.")
m("Stockout Days", F6, "SUM(Inventory[Stockout Days])", INT, "SKU x warehouse days out of stock.")
m("Stockout Days per SKU", F6, "DIVIDE([Stockout Days], COUNTROWS(Inventory))", DEC1,
  "Average stock-out days per SKU-warehouse-month.")
m("Aged Stock Value", F6, """
VAR _lastSnapshot = CALCULATE(MAX(Inventory[Snapshot Date]), ALL(Inventory), VALUES('Date'[Date]))
RETURN CALCULATE(SUM(Inventory[On Hand Value EUR]), 'Date'[Date] = _lastSnapshot, Inventory[Stock Status] = "Discontinued (aged)")
""", EUR, "Closing value of stock of discontinued SKUs (obsolescence risk).", FMT_EUR)
m("Aged Stock %", F6, "DIVIDE([Aged Stock Value], [Inventory Value])", PCT, "Aged stock as % of inventory value.")

# ------------------------------------------------------------- 07 Forecast
m("Forecast Net Sales", F7, "CALCULATE(SUM(Forecast[Forecast EUR]), Forecast[Forecast Type] = \"Forward\")", EUR,
  "ETS statistical forecast of net sales for open months (Oct 2026 onwards).", FMT_EUR)
m("Forecast Lower 80", F7, """
VAR _f = [Forecast Net Sales]
VAR _err = SQRT(SUMX(FILTER(Forecast, Forecast[Forecast Type] = "Forward"), (Forecast[Forecast EUR] - Forecast[Lower 80]) ^ 2))
RETURN IF(NOT ISBLANK(_f), _f - _err)
""", EUR, "Lower bound of the 80% prediction interval (series errors combined in quadrature).", FMT_EUR)
m("Forecast Upper 80", F7, """
VAR _f = [Forecast Net Sales]
VAR _err = SQRT(SUMX(FILTER(Forecast, Forecast[Forecast Type] = "Forward"), (Forecast[Upper 80] - Forecast[Forecast EUR]) ^ 2))
RETURN IF(NOT ISBLANK(_f), _f + _err)
""", EUR, "Upper bound of the 80% prediction interval.", FMT_EUR)
m("Forecast Lower 95", F7, """
VAR _f = [Forecast Net Sales]
VAR _err = SQRT(SUMX(FILTER(Forecast, Forecast[Forecast Type] = "Forward"), (Forecast[Forecast EUR] - Forecast[Lower 95]) ^ 2))
RETURN IF(NOT ISBLANK(_f), _f - _err)
""", EUR, "Lower bound of the 95% prediction interval.", FMT_EUR)
m("Forecast Upper 95", F7, """
VAR _f = [Forecast Net Sales]
VAR _err = SQRT(SUMX(FILTER(Forecast, Forecast[Forecast Type] = "Forward"), (Forecast[Upper 95] - Forecast[Forecast EUR]) ^ 2))
RETURN IF(NOT ISBLANK(_f), _f + _err)
""", EUR, "Upper bound of the 95% prediction interval.", FMT_EUR)
m("Forecast Line", F7, """
VAR _monthEnd = MAX('Date'[Date])
VAR _lastActual = [Last Actual Date]
RETURN
    IF(
        _monthEnd = _lastActual,
        [Net Sales],
        [Forecast Net Sales]
    )
""", EUR, "Forecast series for charts, anchored on the last actual month so the line is continuous.", FMT_EUR)
m("Back-test Forecast", F7, "CALCULATE(SUM(Forecast[Forecast EUR]), Forecast[Forecast Type] = \"Back-test\")", EUR,
  "Out-of-sample forecast for Apr-Sep 2026 (model trained on data up to Mar 2026).", FMT_EUR)
m("Back-test Actual", F7, """
VAR _months = CALCULATETABLE(VALUES(Forecast[Month]), Forecast[Forecast Type] = "Back-test")
RETURN CALCULATE([Net Sales], KEEPFILTERS(TREATAS(_months, 'Date'[Month Start])))
""", EUR, "Actual net sales for the back-test months only (Apr-Sep 2026).", FMT_EUR)
m("Back-test Error %", F7, """
VAR _f = [Back-test Forecast]
VAR _a = [Back-test Actual]
RETURN IF(NOT ISBLANK(_f) && NOT ISBLANK(_a), DIVIDE(_f - _a, _a))
""", PCT_D, "Back-test forecast vs actual for the same months, % (positive = over-forecast).")
m("Forecast WAPE", F7, """
CALCULATE(
    DIVIDE(SUM('Forecast Accuracy'[Abs Error EUR]), SUM('Forecast Accuracy'[Actual EUR])),
    'Forecast Accuracy'[Model] = "ETS (damped trend)"
)
""", PCT, "Weighted absolute % error of the ETS model on the 6-month hold-out.")
m("Naive WAPE", F7, """
CALCULATE(
    DIVIDE(SUM('Forecast Accuracy'[Abs Error EUR]), SUM('Forecast Accuracy'[Actual EUR])),
    'Forecast Accuracy'[Model] = "Seasonal naive"
)
""", PCT, "Weighted absolute % error of the seasonal-naive benchmark (same month last year).")
m("Forecast Value Added (pp)", F7, "([Naive WAPE] - [Forecast WAPE]) * 100", PP,
  "Error reduction of the ETS model vs the naive benchmark, percentage points.")
m("Forecast Accuracy %", F7, "1 - [Forecast WAPE]", PCT, "1 - WAPE.")
m("FY Outlook", F7, "[Net Sales] + [Forecast Net Sales]", EUR,
  "Latest estimate: actuals for closed months + statistical forecast for open months.", FMT_EUR)
m("FY Outlook vs Budget", F7, "IF(NOT ISBLANK([Budget Net Sales]), [FY Outlook] - [Budget Net Sales])", EUR,
  "Latest estimate minus full-period budget.", FMT_VAR)
m("FY Outlook vs Budget %", F7, "DIVIDE([FY Outlook vs Budget], [Budget Net Sales])", PCT_D,
  "Latest estimate vs budget, %.")
m("FY Outlook vs PY %", F7, """
VAR _py = CALCULATE([Net Sales], SAMEPERIODLASTYEAR('Date'[Date]))
RETURN DIVIDE([FY Outlook] - _py, _py)
""", PCT_D, "Latest estimate vs full prior-year actuals.")

# ------------------------------------------------------------- 08 Scenario
m("Price Change %", F8, "SELECTEDVALUE('Scenario Price Change'[Price Change %], 0)", '+0%;-0%;0%', "Selected what-if price change.")
m("Volume Change %", F8, "SELECTEDVALUE('Scenario Volume Change'[Volume Change %], 0)", '+0%;-0%;0%', "Selected what-if volume change.")
m("Cost Inflation %", F8, "SELECTEDVALUE('Scenario Cost Inflation'[Cost Inflation %], 0)", '+0%;-0%;0%', "Selected what-if COGS inflation.")
m("R12M Gross Margin %", F8, """
VAR _end = [Last Actual Date]
RETURN CALCULATE([Gross Margin %], DATESINPERIOD('Date'[Date], _end, -12, MONTH), REMOVEFILTERS('Date'))
""", PCT, "Gross margin % of the last 12 closed months (basis for open-period margin).", hidden=False)
m("R12M Opex % of Sales", F8, """
VAR _end = [Last Actual Date]
RETURN CALCULATE([Opex % of Sales], DATESINPERIOD('Date'[Date], _end, -12, MONTH), REMOVEFILTERS('Date'))
""", PCT, "Opex % of sales of the last 12 closed months (basis for open-period opex).")
m("Outlook Gross Margin (Base)", F8, "[Gross Margin] + [Forecast Net Sales] * [R12M Gross Margin %]", EUR,
  "Actual gross margin + forecast net sales x trailing GM %.", FMT_EUR)
m("Outlook EBITDA (Base)", F8, """
IF(
    NOT (ISCROSSFILTERED('Product') || ISCROSSFILTERED(Customer) || ISCROSSFILTERED(Warehouse)),
    [Outlook Gross Margin (Base)] - [Opex] - [Forecast Net Sales] * [R12M Opex % of Sales]
)
""", EUR, "Latest-estimate EBITDA before scenario adjustments.", FMT_EUR)
m("Scenario Net Sales", F8, "[Net Sales] + [Forecast Net Sales] * (1 + [Price Change %]) * (1 + [Volume Change %])", EUR,
  "Latest estimate with what-if price and volume changes applied to open periods.", FMT_EUR)
m("Scenario Gross Margin", F8, """
VAR _fc = [Forecast Net Sales]
VAR _cogsOpen = _fc * (1 - [R12M Gross Margin %]) * (1 + [Volume Change %]) * (1 + [Cost Inflation %])
VAR _salesOpen = _fc * (1 + [Price Change %]) * (1 + [Volume Change %])
RETURN [Gross Margin] + _salesOpen - _cogsOpen
""", EUR, "Scenario gross margin: price changes flow to margin, volume scales COGS, cost inflation raises COGS.", FMT_EUR)
m("Scenario EBITDA", F8, """
IF(
    NOT (ISCROSSFILTERED('Product') || ISCROSSFILTERED(Customer) || ISCROSSFILTERED(Warehouse)),
    VAR _opexOpen = [Forecast Net Sales] * [R12M Opex % of Sales] * (1 + 0.6 * [Volume Change %])
    RETURN [Scenario Gross Margin] - [Opex] - _opexOpen
)
""", EUR, "Scenario EBITDA. Assumes 60% of opex is variable with volume.", FMT_EUR)
m("Scenario EBITDA %", F8, "DIVIDE([Scenario EBITDA], [Scenario Net Sales])", PCT, "Scenario EBITDA margin.")
m("Scenario Net Sales Impact", F8, "[Scenario Net Sales] - [FY Outlook]", EUR, "Scenario minus base latest estimate.", FMT_VAR)
m("Scenario EBITDA Impact", F8, "[Scenario EBITDA] - [Outlook EBITDA (Base)]", EUR, "Scenario EBITDA minus base.", FMT_VAR)

# ---------------------------------------------------------- 09 Data Quality
m("DQ Checks", F9, "COUNTROWS('DQ Checks')", INT, "Number of data-quality rules executed.")
m("DQ Checks Passed", F9, "CALCULATE(COUNTROWS('DQ Checks'), 'DQ Checks'[Status] = \"Pass\") + 0", INT, "Rules within tolerance.")
m("DQ Checks Warning", F9, "CALCULATE(COUNTROWS('DQ Checks'), 'DQ Checks'[Status] = \"Warning\") + 0", INT, "Rules above tolerance (up to 5x).")
m("DQ Checks Failed", F9, "CALCULATE(COUNTROWS('DQ Checks'), 'DQ Checks'[Status] = \"Fail\") + 0", INT, "Rules above 5x tolerance.")
m("DQ Rule Pass Rate", F9, "DIVIDE([DQ Checks Passed], [DQ Checks])", PCT, "Share of rules passing.")
m("Record Accuracy %", F9, "1 - DIVIDE(SUM('DQ Checks'[Rows Failed]), SUM('DQ Checks'[Rows Checked]))", '0.00%',
  "1 - failed records / checked records across all rules.")
m("DQ Exception Rows", F9, "COUNTROWS('DQ Exceptions') + 0", INT, "Row-level exceptions logged by the ETL.")
m("Feeds Loaded Late", F9, "CALCULATE(COUNTROWS('DQ Load Log'), 'DQ Load Log'[SLA Status] = \"Late\") + 0", INT,
  "Country feeds loaded after the 3-day SLA.")
m("Feed SLA %", F9, "DIVIDE(CALCULATE(COUNTROWS('DQ Load Log'), 'DQ Load Log'[SLA Status] = \"Within SLA\"), COUNTROWS('DQ Load Log'))",
  PCT, "Share of feeds loaded within SLA.")
m("Imputed Discount Lines", F9, "CALCULATE(COUNTROWS(Sales), Sales[Discount Imputed] = 1) + 0", INT,
  "Order lines where a missing discount was imputed (DQ05).")
m("Estimated COGS Share", F9, "DIVIDE(CALCULATE([COGS], Sales[COGS Estimated] = 1), [COGS])", '0.00%',
  "Share of COGS estimated for unmapped SKUs (DQ02).")
m("Data As Of", F9, "\"Data as of \" & FORMAT([Last Actual Date], \"d mmm yyyy\")", None, "Reporting cut-off label.")

# -------------------------------------------------------------- 10 Report UI
m("Color YoY", F10, "IF([Net Sales YoY] >= 0, \"#1A7F5A\", \"#C23B3B\")", None, "Green/red by YoY sign.")
m("Color vs Budget", F10, "IF([Net Sales vs Budget] >= 0, \"#1A7F5A\", \"#C23B3B\")", None, "Green/red by budget variance.")
m("Color OTIF", F10, """
SWITCH(TRUE(), ISBLANK([OTIF %]), BLANK(), [OTIF %] >= [OTIF Target], "#1A7F5A", [OTIF %] >= 0.88, "#D98E04", "#C23B3B")
""", None, "Traffic light vs OTIF target (>= 95% green, >= 88% amber, else red).")
m("Color DQ Status", F10, """
SWITCH(SELECTEDVALUE('DQ Checks'[Status]), "Pass", "#1A7F5A", "Warning", "#D98E04", "Fail", "#C23B3B")
""", None, "Traffic light for data-quality status.")
m("Color Scenario EBITDA", F10, "IF([Scenario EBITDA Impact] >= 0, \"#1A7F5A\", \"#C23B3B\")", None, "Green/red by scenario impact.")
m("KPI Net Sales YoY Label", F10, """
VAR _v = [Net Sales YoY %]
RETURN IF(ISBLANK(_v), "", IF(_v >= 0, "▲ ", "▼ ") & FORMAT(ABS(_v), "0.0%") & " vs PY")
""", None, "Arrow label for KPI cards.")
m("KPI Net Sales vs Budget Label", F10, """
VAR _v = [Net Sales vs Budget %]
RETURN IF(ISBLANK(_v), "", IF(_v >= 0, "▲ ", "▼ ") & FORMAT(ABS(_v), "0.0%") & " vs budget")
""", None, "Arrow label for KPI cards.")
m("KPI GM pp Label", F10, """
VAR _v = [Gross Margin % YoY (pp)]
RETURN IF(ISBLANK(_v), "", IF(_v >= 0, "▲ ", "▼ ") & FORMAT(ABS(_v), "0.0") & " pp vs PY")
""", None, "Arrow label for KPI cards.")
m("KPI EBITDA Label", F10, """
VAR _v = [EBITDA YoY %]
RETURN IF(ISBLANK(_v), "", IF(_v >= 0, "▲ ", "▼ ") & FORMAT(ABS(_v), "0.0%") & " vs PY")
""", None, "Arrow label for KPI cards.")
m("KPI OTIF Label", F10, """
VAR _v = [OTIF vs Target (pp)]
RETURN IF(ISBLANK(_v), "", IF(_v >= 0, "▲ ", "▼ ") & FORMAT(ABS(_v), "0.0") & " pp vs 95% target")
""", None, "Arrow label for KPI cards.")
m("Selected Period", F10, """
VAR _min = MIN('Date'[Date])
VAR _max = MIN(MAX('Date'[Date]), [Last Actual Date])
RETURN
    IF(
        _max < _min,
        "Open period (forecast only)",
        FORMAT(_min, "mmm yyyy") & IF(FORMAT(_min, "yyyymm") <> FORMAT(_max, "yyyymm"), " – " & FORMAT(_max, "mmm yyyy"))
    )
""", None, "Closed months covered by the current date selection, e.g. 'Jan 2026 – Sep 2026'.")
m("Executive Summary", F10, """
VAR _ns = [Net Sales]
VAR _yoy = [Net Sales YoY %]
VAR _ccy = [Constant Currency Growth %]
VAR _vb = [Net Sales vs Budget]
VAR _gm = [Gross Margin %]
VAR _gmpp = [Gross Margin % YoY (pp)]
VAR _ebitda = [EBITDA %]
VAR _otif = [OTIF %]
VAR _ctry =
    ADDCOLUMNS(VALUES(Country[Country]), "@yoy", [Net Sales YoY], "@vb", [Net Sales vs Budget])
VAR _topGrowth = TOPN(1, _ctry, [@yoy], DESC)
VAR _worstBudget = TOPN(1, _ctry, [@vb], ASC)
VAR _fmtM = "€#,0,,.0\\"M\\""
RETURN
    IF(
        ISBLANK(_ns),
        "No closed-period data for the current selection.",
        "Net sales of " & FORMAT(_ns, _fmtM) & " are " & FORMAT(_yoy, "+0.0%;-0.0%") & " vs prior year ("
            & FORMAT(_ccy, "+0.0%;-0.0%") & " at constant FX) and " & FORMAT(_vb, "+€#,0,,.0\\"M\\";-€#,0,,.0\\"M\\"")
            & " vs budget. Gross margin is " & FORMAT(_gm, "0.0%") & " (" & FORMAT(_gmpp, "+0.0;-0.0") & " pp YoY), EBITDA margin "
            & FORMAT(_ebitda, "0.0%") & " and OTIF " & FORMAT(_otif, "0.0%") & ". "
            & IF(COUNTROWS(_ctry) > 1,
                "Largest growth contributor: " & MAXX(_topGrowth, Country[Country]) & " (" & FORMAT(MAXX(_topGrowth, [@yoy]), "+€#,0,,.0\\"M\\";-€#,0,,.0\\"M\\"")
                & "). Largest budget gap: " & MAXX(_worstBudget, Country[Country]) & " (" & FORMAT(MAXX(_worstBudget, [@vb]), "+€#,0,,.0\\"M\\";-€#,0,,.0\\"M\\"") & ").",
                "")
    )
""", None, "Auto-generated narrative of the headline KPIs for the current selection.")

if __name__ == "__main__":
    order = [F1, F2, F3, F6, F4, F5, F7, F8, F9, F10]
    M.sort(key=lambda d: order.index(d["displayFolder"]))
    for d in M:  # DAX escapes quotes inside strings by doubling them
        for k in ("expression", "formatStringExpression"):
            if k in d:
                d[k] = d[k].replace('\\"', '""')
                assert '\\' not in d[k], d["name"]
    json.dump(M, open("measures.json", "w"), ensure_ascii=False, indent=0)
    print(len(M), "measures")
