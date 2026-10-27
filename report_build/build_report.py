"""
Generates the PBIR report definition for 'CEE Performance Hub'.
Output: <OUT>/CEE Performance Hub.Report/ (definition + theme), validated separately.
"""
import os
import shutil
import sys

from pbir import (C, M, Page, SEL_DEFAULT, categorical_filter, color, container_objects, date_ge_filter, dump,
                  field_param_filter_def, in_filter_def, lit, mcolor, measure_filter, obj, proj, sel_fx,
                  sel_metadata, uid)

OUT = sys.argv[1] if len(sys.argv) > 1 else "/home/claude/project/report_out"
REPORT = os.path.join(OUT, "CEE Performance Hub.Report")
DEF = os.path.join(REPORT, "definition")

# ----------------------------------------------------------------- design
NAVY, BLUE, TEAL, AMBER, CORAL, SKY, PLUM, SLATE = ("#0F1E36", "#1F4E79", "#2A9D8F", "#E9A23B", "#D1495B",
                                                    "#6FA8DC", "#6A4C93", "#8492A6")
GOOD, BAD, INK, MUTED, LINE = "#1A7F5A", "#C23B3B", "#1F2937", "#6B7685", "#E1E6ED"
NAV_W = 240
X0, Y0, W_CONTENT = 264, 100, 1632          # content area
GAP = 16

PAGES_DEF = [  # key, display, title, subtitle
    ("exec", "Executive Overview", "Executive Overview",
     "Group performance vs prior year and budget - closed months only"),
    ("sales", "Sales & Customers", "Sales & Customers",
     "Growth drivers: price-volume-mix, channels, categories and key accounts"),
    ("profit", "Profitability & P&L", "Profitability & P&L",
     "Management P&L, margin pressure by category and country profitability"),
    ("ops", "Operations", "Operations & Supply Chain",
     "Service level (OTIF), inventory health and cost-to-serve"),
    ("fcst", "Forecast & Scenarios", "Forecast & Scenarios",
     "Statistical forecast with prediction intervals, latest estimate and what-if simulation"),
    ("dq", "Data Quality", "Data Quality & Governance",
     "Automated data-quality rules, reconciliation and source-feed timeliness"),
]
pages = {}


# ----------------------------------------------------------------- building blocks
def nav_rail(p: Page, active_key):
    p.add("nav_bg", "textbox", 0, 0, NAV_W, 1080,
          objects={"general": [{"properties": {"paragraphs": [
              {"textRuns": [{"value": "DANUBIA DISTRIBUTION GROUP",
                             "textStyle": {"fontSize": "9pt", "color": "#8FA3BF", "fontWeight": "bold"}}]},
              {"textRuns": [{"value": "CEE Performance Hub",
                             "textStyle": {"fontSize": "17pt", "color": "#FFFFFF", "fontWeight": "bold"}}]},
              {"textRuns": [{"value": "Commercial & operations reporting",
                             "textStyle": {"fontSize": "9pt", "color": "#8FA3BF"}}]}]}}]},
          vco=container_objects(background=NAVY, border=False, shadow=False, padding=(28, 20, 0, 22),
                                header=False))
    y = 150
    for key, display, *_ in PAGES_DEF:
        active = key == active_key
        p.add(f"nav_{key}", "actionButton", 16, y, NAV_W - 32, 46,
              objects={
                  "icon": [obj(SEL_DEFAULT, shapeType="blank")],
                  "text": [obj(show=True),
                           obj(SEL_DEFAULT, text=display, fontColor=color("#FFFFFF" if active else "#C5D0DF"),
                               fontSize=11, bold=active, alignment="left", leftMargin=16)],
                  "fill": [obj(show=True),
                           obj(SEL_DEFAULT, fillColor=color(TEAL if active else NAVY), transparency=0),
                           obj({"id": "hover"}, fillColor=color(TEAL if active else "#1C3355"), transparency=0)],
                  "outline": [obj(show=False)],
                  "shape": [obj(SEL_DEFAULT, roundEdge=8)]},
              vco=container_objects(background=False, border=False, shadow=False, header=False,
                                    link={"show": True, "type": "PageNavigation",
                                          "navigationSection": uid("page", key)}))
        y += 54
    # data freshness + disclaimer
    p.add("nav_asof", "cardVisual", 16, 940, NAV_W - 32, 54, query={"Data": [M("Data As Of")]},
          objects=card_objects(value_size=10, value_color=NAVY, show_label=False, units=1),
          vco=container_objects(background=False, border=False, shadow=False, header=False, padding=(0, 0, 0, 0)))
    p.add("nav_note", "textbox", 16, 990, NAV_W - 32, 70,
          objects={"general": [{"properties": {"paragraphs": [
              {"textRuns": [{"value": "Fictional company & synthetic data - portfolio project by Stefan Iliev",
                             "textStyle": {"fontSize": "8pt", "color": "#8FA3BF"}}]}]}}]},
          vco=container_objects(background=False, border=False, shadow=False, header=False))


def header(p: Page, title, subtitle, slicers=True):
    p.add("hdr", "textbox", X0, 12, 960, 84,
          objects={"general": [{"properties": {"paragraphs": [
              {"textRuns": [{"value": title, "textStyle": {"fontSize": "20pt", "color": INK, "fontWeight": "bold"}}]},
              {"textRuns": [{"value": subtitle, "textStyle": {"fontSize": "10pt", "color": MUTED}}]}]}}]},
          vco=container_objects(background=False, border=False, shadow=False, header=False))
    if slicers:
        x = X0 + W_CONTENT - 3 * 200 - 2 * 12
        slicer(p, "sl_year", x, 22, 200, 62, C("Date", "Year"), "Year", single=True, default=[2026], sync="Year")
        slicer(p, "sl_ctry", x + 212, 22, 200, 62, C("Country", "Country"), "Country", sync="Country")
        slicer(p, "sl_cat", x + 424, 22, 200, 62, C("Category", "Category"), "Category", sync="Category")


def slicer(p, key, x, y, w, h, field, title, single=False, default=None, sync=None, mode="Dropdown",
           default_filter=None):
    objects = {"data": [obj(mode=mode)],
               "selection": [obj(singleSelect=single, strictSingleSelect=single, selectAllCheckboxEnabled=not single)],
               "header": [obj(show=True, text=title, fontColor=color(MUTED), textSize=9)],
               "items": [obj(fontColor=color(INK), textSize=10)]}
    if default_filter:
        objects["general"] = [{"properties": {"filter": {"filter": default_filter}}}]
    elif default is not None:
        objects["general"] = [{"properties": {"filter": {"filter": in_filter_def(
            field.expr["Column"]["Expression"]["SourceRef"]["Entity"], field.native, default)}}}]
    return p.add(key, "slicer", x, y, w, h, query={"Values": [field]}, objects=objects,
                 vco=container_objects(background="#FFFFFF", border=LINE, shadow=False, padding=(6, 10, 6, 10),
                                       header=False), sync=sync)


def card_objects(value_size=26, value_color=INK, show_label=True, label_size=10, value_fx=None, units=0,
                 precision=None):
    vprops = dict(fontSize=value_size, fontColor=mcolor(value_fx) if value_fx else color(value_color), bold=False,
                  labelDisplayUnits=units)
    if precision is not None:
        vprops["labelPrecision"] = precision
    o = {"value": [obj(SEL_DEFAULT, **vprops)],
         "label": [obj(SEL_DEFAULT, show=show_label, fontSize=label_size, fontColor=color(MUTED),
                       position="aboveValue")],
         "layout": [obj(SEL_DEFAULT, alignment="left", verticalAlignment="top")]}
    return o


CURRENCY = {"Net Sales", "Gross Margin", "EBITDA", "Net Sales vs Budget", "FY Outlook", "Avg Order Value",
            "Unfulfilled Demand", "Inventory Value", "Forecast Net Sales", "Scenario EBITDA Impact",
            "Scenario Net Sales", "Scenario EBITDA", "EBITDA vs Budget", "Gross Margin vs Budget"}


def kpi(p: Page, key, x, y, w, h, measure, label, delta_measure=None, delta_color=None):
    """KPI tile = white container + value card + (optional) coloured delta line below the value."""
    p.add(f"{key}_bg", "textbox", x, y, w, h,
          objects={"general": [{"properties": {"paragraphs": [{"textRuns": [{"value": " "}]}]}}]},
          vco=container_objects(background="#FFFFFF", border=LINE, header=False))
    units, prec = (0, 1) if measure in CURRENCY else (1, None)
    vh = h - 38 if delta_measure else h - 8
    p.add(f"{key}_v", "cardVisual", x + 2, y + 4, w - 4, vh, query={"Data": [proj(M(measure), display=label)]},
          objects=card_objects(value_size=24, units=units, precision=prec),
          vco=container_objects(background=False, border=False, shadow=False, padding=(8, 12, 0, 14), header=False))
    if delta_measure:
        p.add(f"{key}_d", "cardVisual", x + 2, y + h - 36, w - 4, 32,
              query={"Data": [M(delta_measure)]},
              objects=card_objects(value_size=10, show_label=False, value_fx=delta_color, units=1),
              vco=container_objects(background=False, border=False, shadow=False, padding=(0, 12, 4, 14),
                                    header=False))


def kpi_row(p: Page, items, y=Y0, h=122):
    n = len(items)
    w = (W_CONTENT - (n - 1) * GAP) // n
    for i, it in enumerate(items):
        kpi(p, f"kpi{i}", X0 + i * (w + GAP), y, w, h, *it)


def axis_objects(legend=True, labels=False, value_axis=True, legend_pos="Top", label_units=None, precision=None):
    o = {"legend": [obj(show=legend, position=legend_pos, fontSize=9, labelColor=color(MUTED))],
         "categoryAxis": [obj(show=True, fontSize=9, labelColor=color(MUTED), gridlineShow=False,
                              showAxisTitle=False)],
         "valueAxis": [obj(show=value_axis, fontSize=9, labelColor=color(MUTED), gridlineShow=True,
                           gridlineColor=color("#EEF1F5"), showAxisTitle=False)],
         "labels": [obj(show=labels, fontSize=9, color=color(INK))]}
    if label_units is not None or precision is not None:
        extra = {}
        if label_units is not None:
            extra["labelDisplayUnits"] = label_units
        if precision is not None:
            extra["labelPrecision"] = precision
        o["labels"] = [obj(show=labels, fontSize=9, color=color(INK), **extra)]
    return o


def series_colors(o, pairs):
    o.setdefault("dataPoint", [])
    for f, c in pairs:
        o["dataPoint"].append(obj(sel_metadata(f.query_ref), fill=color(c)))
    return o


def line_styles(o, styles):
    o.setdefault("lineStyles", [])
    for f, st in styles:
        o["lineStyles"].append(obj(sel_metadata(f.query_ref), **st))
    return o


def table_objects(font=10, header_bg="#F3F5F9", row_padding=5):
    return {"columnHeaders": [obj(fontColor=color(MUTED), backColor=color(header_bg), fontSize=font, bold=True,
                                  wordWrap=True)],
            "values": [obj(fontColor=color(INK), fontSize=font, backColorPrimary=color("#FFFFFF"),
                           backColorSecondary=color("#FAFBFD"))],
            "grid": [obj(gridHorizontal=True, gridHorizontalColor=color("#EEF1F5"), rowPadding=row_padding,
                         gridVertical=False, outlineColor=color("#E1E6ED"))],
            "total": [obj(totals=False)]}


def fx_font(o, f, measure, key="values"):
    o.setdefault(key, []).append(obj(sel_fx(f.query_ref), fontColor=mcolor(measure)))
    return o


def fx_back(o, f, measure, key="values"):
    o.setdefault(key, []).append(obj(sel_fx(f.query_ref), backColor=mcolor(measure)))
    return o


def vtitle(t, sub=None):
    return container_objects(title=t, subtitle=sub, header=True)


# =================================================================== PAGES
def new_page(key):
    d = next(x for x in PAGES_DEF if x[0] == key)
    p = Page(key, d[1])
    nav_rail(p, key)
    header(p, d[2], d[3])
    pages[key] = p
    return p


TOOLTIP = uid("page", "tooltip_country")
DRILL = uid("page", "customer")

# ----------------------------------------------------------- 1 Executive
p = new_page("exec")
kpi_row(p, [
    ("Net Sales", "Net sales (EUR)", "KPI Net Sales YoY Label", "Color YoY"),
    ("Gross Margin %", "Gross margin %", "KPI GM pp Label", "Color GM"),
    ("EBITDA", "EBITDA (EUR)", "KPI EBITDA Label", "Color EBITDA"),
    ("Net Sales vs Budget", "Net sales vs budget", "KPI Net Sales vs Budget Label", "Color vs Budget"),
    ("OTIF %", "OTIF (on time in full)", "KPI OTIF Label", "Color OTIF"),
    ("FY Outlook", "Latest estimate FY", "KPI Outlook Label", "Color Outlook"),
])
p.add("summary", "card", X0, 234, W_CONTENT, 100, query={"Values": [proj(M("Executive Summary"), "Key insights")]},
      objects={"labels": [obj(color=color(INK), fontSize=12, fontFamily="Segoe UI")],
               "categoryLabels": [obj(show=False)], "wordWrap": [obj(show=True)]},
      vco=container_objects(title="Key insights (auto-generated)", title_size=9, background="#EAF3F1",
                            border="#CFE6E1", padding=(6, 18, 6, 18), header=False, shadow=False))
o = axis_objects(legend=True)
series_colors(o, [(M("Net Sales"), BLUE), (M("Budget Net Sales"), AMBER), (M("Net Sales PY"), SLATE)])
line_styles(o, [(M("Budget Net Sales"), {"strokeWidth": 2, "lineStyle": "dashed", "showMarker": False}),
                (M("Net Sales PY"), {"strokeWidth": 2, "showMarker": False})])
p.add("trend", "lineClusteredColumnComboChart", X0, 350, 1000, 348,
      query={"Category": [C("Date", "Month Short")], "Y": [proj(M("Net Sales"), "Actual")],
             "Y2": [proj(M("Budget Net Sales"), "Budget"), proj(M("Net Sales PY"), "Prior year")]},
      sort=[(C("Date", "Month Short"), "Ascending")], objects=o,
      vco=vtitle("Monthly net sales vs budget and prior year",
                 "Columns = actual; open months (Oct-Dec) show the remaining budget"))
o = {"sentimentColors": [obj(increaseFill=color(TEAL), decreaseFill=color(CORAL), totalFill=color(BLUE))],
     "labels": [obj(show=True, fontSize=9, color=color(INK), labelPrecision=1)],
     "valueAxis": [obj(show=False)], "categoryAxis": [obj(fontSize=9, labelColor=color(MUTED))],
     "legend": [obj(show=False)]}
p.add("bridge", "waterfallChart", X0 + 1016, 350, 616, 348,
      query={"Category": [C("Bridge Step", "Step")], "Y": [proj(M("Bridge Value"), "Net sales")]},
      sort=[(C("Bridge Step", "Step"), "Ascending")], objects=o,
      vco=vtitle("Net sales bridge: prior year to current year",
                 "Volume, net price (constant FX), mix and FX translation effects"))
o = axis_objects(legend=False, labels=True, precision=1)
o["dataPoint"] = [obj(sel_fx(), fill=mcolor("Color Budget Var Bar"))]
p.add("ctry_budget", "clusteredBarChart", X0, 714, 536, 342,
      query={"Category": [C("Country", "Country")], "Y": [proj(M("Net Sales vs Budget"), "vs budget")]},
      sort=[(M("Net Sales vs Budget"), "Descending")], objects=o,
      vco=container_objects(title="Variance to budget by country", subtitle="Closed months only",
                            tooltip_page=TOOLTIP))
o = axis_objects(legend=False, labels=True, precision=1)
o["dataPoint"] = [obj(sel_fx(), fill=mcolor("Color YoY Bar"))]
p.add("ctry_growth", "clusteredBarChart", X0 + 552, 714, 536, 342,
      query={"Category": [C("Country", "Country")], "Y": [proj(M("Net Sales YoY"), "Growth vs PY")]},
      sort=[(M("Net Sales YoY"), "Descending")], objects=o,
      vco=container_objects(title="Growth contribution by country (vs PY)", tooltip_page=TOOLTIP))
o = axis_objects(legend=False)
o["categoryLabels"] = [obj(show=True, fontSize=9, color=color(INK))]
o["dataPoint"] = [obj(fill=color(BLUE))]
o["bubbles"] = [obj(bubbleSize=-25)]
p.add("quadrant", "scatterChart", X0 + 1104, 714, 528, 342,
      query={"Category": [C("Country", "Country")], "X": [proj(M("Net Sales YoY %"), "Growth vs PY")],
             "Y": [proj(M("EBITDA %"), "EBITDA margin")], "Size": [proj(M("Net Sales"), "Net sales")]},
      objects=o, vco=container_objects(title="Growth vs profitability by country",
                                       subtitle="Bubble size = net sales", tooltip_page=TOOLTIP))

# ----------------------------------------------------------- 2 Sales
p = new_page("sales")
kpi_row(p, [
    ("Net Sales", "Net sales (EUR)", "KPI Net Sales YoY Label", "Color YoY"),
    ("Active Customers", "Active customers", "KPI Customers Label", "Color Customers"),
    ("Avg Order Value", "Average order value", None, None),
    ("Discount %", "Discount % of gross sales", None, None),
    ("Promo Sales %", "Sold on promotion", None, None),
    ("Top 20% Customers Share", "Top-20% customers' share", None, None),
])
# self-service explorer (field parameters)
for key, tbl, ttl, yy in [("sl_metric", "Metric Selector", "Metric", 234),
                          ("sl_breakdown", "Breakdown Selector", "Break down by", 273)]:
    p.add(key, "slicer", X0, yy, 800, 37, query={"Values": [C(tbl, tbl)]},
          objects={"data": [obj(mode="Basic")], "general": [obj(orientation=1)],
                   "selection": [obj(singleSelect=True, strictSingleSelect=True)],
                   "header": [obj(show=False)],
                   "items": [obj(fontColor=color(INK), textSize=9, background=color("#FFFFFF"),
                                 outlineStyle=0)]},
          vco=container_objects(background="#FFFFFF", border=LINE, shadow=False, padding=(2, 10, 2, 10),
                                header=False))
o = axis_objects(legend=False, labels=True)
o["dataPoint"] = [obj(fill=color(BLUE))]
p.add("explorer", "clusteredBarChart", X0, 326, 800, 358,
      query={"Category": {"projections": [proj(C("Country", "Country"), active=True)],
                          "fieldParameters": [{"parameterExpr": C("Breakdown Selector", "Breakdown Selector").expr,
                                               "index": 0, "length": 1}]},
             "Y": {"projections": [proj(M("Net Sales"))],
                   "fieldParameters": [{"parameterExpr": C("Metric Selector", "Metric Selector").expr,
                                        "index": 0, "length": 1}]}},
      objects=o, vco=container_objects(title="Self-service explorer",
                                       subtitle="Pick any metric and dimension above"))
o = axis_objects(legend=True, labels=False)
series_colors(o, [(M("Volume Effect"), BLUE), (M("Price Effect"), TEAL), (M("Mix & Other Effect"), AMBER),
                  (M("FX Effect"), PLUM)])
p.add("pvm_cat", "clusteredBarChart", X0 + 816, 234, 816, 450,
      query={"Category": [C("Category", "Category")],
             "Y": [proj(M("Volume Effect"), "Volume"), proj(M("Price Effect"), "Price"),
                   proj(M("Mix & Other Effect"), "Mix & other"), proj(M("FX Effect"), "FX")]},
      sort=[(C("Category", "Category"), "Ascending")], objects=o,
      vco=vtitle("Price-volume-mix by category (vs PY)",
                 "Where growth comes from: more cases, better net price, or mix"))
o = table_objects()
fx_font(o, M("Net Sales YoY %"), "Color YoY")
p.add("top_cust", "tableEx", X0, 700, 1000, 356,
      query={"Values": [proj(M("Customer Rank"), "#"), proj(C("Customer", "Customer")),
                        proj(C("Customer", "Country Code"), "Country"), proj(C("Customer", "Channel")),
                        proj(M("Net Sales"), "Net sales"), proj(M("Net Sales YoY %"), "YoY"),
                        proj(M("Gross Margin %"), "GM %"), proj(M("Orders")), proj(M("OTIF %"), "OTIF")]},
      sort=[(M("Net Sales"), "Descending")], objects=o,
      filters=[measure_filter("f_rank25", "Customer Rank", 4, 25)],
      vco=vtitle("Top 25 customers", "Right-click a customer > Drill through > Customer Detail"))
o = axis_objects(legend=True, labels=True, value_axis=False)
o["legend"] = [obj(show=True, position="Right", fontSize=9, labelColor=color(MUTED))]
p.add("channel_mix", "hundredPercentStackedColumnChart", X0 + 1016, 700, 616, 356,
      query={"Category": [C("Date", "Year")], "Series": [C("Customer", "Channel")],
             "Y": [proj(M("Net Sales"), "Net sales")]},
      sort=[(C("Date", "Year"), "Ascending")], objects=o,
      filters=[categorical_filter("f_years_act", "Date", "Year", [2023, 2024, 2025, 2026], hidden=True)],
      vco=vtitle("Channel mix by year", "E-commerce is the fastest-growing channel (all years)"))
p.interactions.append({"source": uid("sales", "sl_year"), "target": uid("sales", "channel_mix"), "type": "NoFilter"})

# ----------------------------------------------------------- 3 Profitability
p = new_page("profit")
kpi_row(p, [
    ("Gross Margin", "Gross margin (EUR)", "KPI GM pp Label", "Color GM"),
    ("Gross Margin %", "Gross margin %", None, None),
    ("Opex % of Sales", "Opex % of sales", None, None),
    ("EBITDA", "EBITDA (EUR)", "KPI EBITDA Label", "Color EBITDA"),
    ("EBITDA %", "EBITDA margin", None, None),
    ("EBITDA vs Budget", "EBITDA vs budget", None, None),
])
o = table_objects(font=11, row_padding=3)
o["rowHeaders"] = [obj(fontColor=color(INK), fontSize=11, bold=False)]
o["subTotals"] = [obj(rowSubtotals=False, columnSubtotals=False)]
pnl_vals = [proj(M("P&L Actual"), "Actual"), proj(M("P&L Budget"), "Budget"), proj(M("P&L vs Budget"), "vs Budget"),
            proj(M("P&L vs Budget %"), "vs Budget %"), proj(M("P&L PY"), "Prior year"),
            proj(M("P&L vs PY %"), "vs PY %")]
for nm in ["P&L Actual", "P&L Budget", "P&L vs Budget", "P&L vs Budget %", "P&L PY", "P&L vs PY %"]:
    fx_back(o, M(nm), "P&L Row Background")
fx_font(o, M("P&L vs Budget"), "Color P&L vs Budget")
fx_font(o, M("P&L vs Budget %"), "Color P&L vs Budget")
fx_font(o, M("P&L vs PY %"), "Color P&L vs PY")
p.add("pnl", "pivotTable", X0, 234, 860, 490,
      query={"Rows": [C("P&L Line", "P&L Line")], "Values": pnl_vals},
      sort=[(C("P&L Line", "P&L Line"), "Ascending")], objects=o,
      vco=vtitle("Management P&L (EUR thousands; costs in brackets)",
                 "Budget and prior year cover the same closed months (like-for-like)"))
o = axis_objects(legend=True)
line_styles(o, [])
p.add("gm_trend", "lineChart", X0 + 876, 234, 756, 237,
      query={"Category": [C("Date", "Year Quarter")], "Series": [C("Category", "Category")],
             "Y": [proj(M("Gross Margin %"), "GM %")]},
      sort=[(C("Date", "Year Quarter"), "Ascending")], objects=o,
      filters=[categorical_filter("f_years_act2", "Date", "Year", [2023, 2024, 2025, 2026], hidden=True)],
      vco=vtitle("Gross margin % by category (quarterly, all years)",
                 "Cocoa & coffee cost inflation squeezed Snacks and Coffee in 2024-25"))
p.interactions.append({"source": uid("profit", "sl_year"), "target": uid("profit", "gm_trend"), "type": "NoFilter"})
o = axis_objects(legend=True, labels=True, value_axis=False)
series_colors(o, [(M("Gross Margin %"), BLUE), (M("Budget Gross Margin %"), AMBER)])
p.add("gm_vs_bud", "clusteredColumnChart", X0 + 876, 487, 756, 237,
      query={"Category": [C("Category", "Category")],
             "Y": [proj(M("Gross Margin %"), "Actual GM %"), proj(M("Budget Gross Margin %"), "Budget GM %")]},
      sort=[(C("Category", "Category"), "Ascending")], objects=o,
      vco=vtitle("Gross margin %: actual vs budget by category"))
o = table_objects(row_padding=3)
fx_font(o, M("Net Sales YoY %"), "Color YoY")
fx_font(o, M("EBITDA vs Budget"), "Color vs Budget")
p.add("ctry_profit", "tableEx", X0, 740, W_CONTENT, 316,
      query={"Values": [proj(C("Country", "Country")), proj(C("Country", "Country Manager"), "Manager"),
                        proj(M("Net Sales"), "Net sales"), proj(M("Net Sales YoY %"), "YoY"),
                        proj(M("Gross Margin %"), "GM %"), proj(M("Logistics Cost % of Sales"), "Logistics %"),
                        proj(M("Opex % of Sales"), "Opex %"), proj(M("EBITDA"), "EBITDA"),
                        proj(M("EBITDA %"), "EBITDA %"), proj(M("EBITDA vs Budget"), "EBITDA vs budget")]},
      sort=[(M("Net Sales"), "Descending")], objects=o,
      vco=vtitle("Country profitability", "Romania: logistics cost spike during the Bucharest DC crisis"))

# ----------------------------------------------------------- 4 Operations
p = new_page("ops")
kpi_row(p, [
    ("OTIF %", "OTIF (on time in full)", "KPI OTIF Label", "Color OTIF"),
    ("In-Full %", "In-full lines", None, None),
    ("Avg Lead Time (days)", "Avg lead time (days)", None, None),
    ("Unfulfilled Demand", "Unfulfilled demand (lost sales)", None, None),
    ("Inventory Value", "Closing inventory value", None, None),
    ("Days of Inventory", "Days of inventory", None, None),
])
o = table_objects(font=10)
o["grid"] = [obj(gridHorizontal=True, gridHorizontalColor=color("#FFFFFF"), gridVertical=True,
                 gridVerticalColor=color("#FFFFFF"), rowPadding=4)]
o["rowHeaders"] = [obj(fontColor=color(INK), fontSize=10)]
o["subTotals"] = [obj(rowSubtotals=False, columnSubtotals=False)]
fx_back(o, M("OTIF %"), "Color OTIF Background")
p.add("otif_heat", "pivotTable", X0, 234, 1000, 400,
      query={"Rows": [C("Warehouse", "Warehouse")], "Columns": [C("Date", "Month Short")],
             "Values": [proj(M("OTIF %"), "OTIF")]},
      sort=[(C("Warehouse", "Warehouse"), "Ascending")], objects=o,
      vco=vtitle("OTIF heat map by distribution centre",
                 "Green >= 95% target | amber >= 88% | red below - note Bucharest DC Feb-Apr 2026"))
o = axis_objects(legend=True)
o["lineStyles"] = [obj(lineChartType="linear")]
series_colors(o, [(M("OTIF %"), BLUE), (M("OTIF Target"), CORAL), (M("OTIF % PY"), SLATE)])
line_styles(o, [(M("OTIF Target"), {"strokeWidth": 2, "lineStyle": "dashed", "showMarker": False}),
                (M("OTIF % PY"), {"strokeWidth": 2, "showMarker": False})])
p.add("otif_trend", "lineChart", X0 + 1016, 234, 616, 400,
      query={"Category": [C("Date", "Month Short")],
             "Y": [proj(M("OTIF %"), "OTIF"), proj(M("OTIF Target"), "Target"), proj(M("OTIF % PY"), "Prior year")]},
      sort=[(C("Date", "Month Short"), "Ascending")], objects=o, vco=vtitle("OTIF trend vs 95% target"))
o = axis_objects(legend=True)
p.add("stockouts", "columnChart", X0, 650, 640, 406,
      query={"Category": [C("Date", "Year Month")], "Series": [C("Category", "Category")],
             "Y": [proj(M("Stockout Days"), "Stock-out days")]},
      sort=[(C("Date", "Year Month"), "Ascending")], objects=o,
      filters=[date_ge_filter("f_so_date", "Date", "Date", "2025-01-01"),
               categorical_filter("f_so_years", "Date", "Year", [2025, 2026], hidden=True)],
      vco=vtitle("Stock-out days by category (2025-2026)",
                 "Coffee & Tea supply disruption Oct-Dec 2025"))
p.interactions.append({"source": uid("ops", "sl_year"), "target": uid("ops", "stockouts"), "type": "NoFilter"})
o = axis_objects(legend=False, labels=True)
o["dataPoint"] = [obj(fill=color(TEAL))]
p.add("doi_wh", "clusteredBarChart", X0 + 656, 650, 480, 406,
      query={"Category": [C("Warehouse", "Warehouse")], "Y": [proj(M("Days of Inventory"), "Days of inventory")]},
      sort=[(M("Days of Inventory"), "Descending")], objects=o,
      vco=vtitle("Days of inventory by DC", "Closing stock / avg daily COGS (3 months)"))
o = axis_objects(legend=False, labels=True)
o["dataPoint"] = [obj(fill=color(AMBER))]
p.add("logi_ctry", "clusteredBarChart", X0 + 1152, 650, 480, 406,
      query={"Category": [C("Country", "Country")], "Y": [proj(M("Logistics Cost % of Sales"), "Logistics %")]},
      sort=[(M("Logistics Cost % of Sales"), "Descending")], objects=o,
      vco=container_objects(title="Logistics cost % of net sales", subtitle="Cost-to-serve by country",
                            tooltip_page=TOOLTIP))

# ----------------------------------------------------------- 5 Forecast
p = new_page("fcst")
kpi_row(p, [
    ("FY Outlook", "Latest estimate FY", "KPI Outlook Label", "Color Outlook"),
    ("Forecast Net Sales", "Forecast - open months", None, None),
    ("FY Outlook vs PY %", "Outlook vs prior year", None, None),
    ("Forecast Accuracy %", "Forecast accuracy (1 - WAPE)", None, None),
    ("Forecast Value Added (pp)", "Error reduction vs naive", None, None),
    ("Scenario EBITDA Impact", "Scenario EBITDA impact", None, None),
])
fc_measures = [(M("Net Sales"), "Actual"), (M("Forecast Line"), "Forecast"),
               (M("Forecast Upper 95"), "95% upper"), (M("Forecast Lower 95"), "95% lower"),
               (M("Budget Net Sales"), "Budget")]
o = axis_objects(legend=True)
series_colors(o, [(M("Net Sales"), BLUE), (M("Forecast Line"), TEAL), (M("Forecast Upper 95"), "#7CC4BA"),
                  (M("Forecast Lower 95"), "#7CC4BA"), (M("Budget Net Sales"), AMBER)])
o["lineStyles"] = [obj(lineChartType="linear")]
line_styles(o, [(M("Net Sales"), {"strokeWidth": 3, "showMarker": False}),
                (M("Forecast Line"), {"strokeWidth": 3, "lineStyle": "dashed", "showMarker": False}),
                (M("Forecast Upper 95"), {"strokeWidth": 2, "lineStyle": "dotted", "showMarker": False}),
                (M("Forecast Lower 95"), {"strokeWidth": 2, "lineStyle": "dotted", "showMarker": False}),
                (M("Budget Net Sales"), {"strokeWidth": 2, "lineStyle": "dashed", "showMarker": False})])
p.add("fc_chart", "lineChart", X0, 234, 1100, 430,
      query={"Category": [C("Date", "Year Month")], "Y": [proj(f, d) for f, d in fc_measures]},
      sort=[(C("Date", "Year Month"), "Ascending")], objects=o,
      filters=[categorical_filter("f_fc_years", "Date", "Year", [2025, 2026, 2027], hidden=True)],
      vco=vtitle("Net sales: actuals, ETS forecast and 95% prediction interval (2025-2027)",
                 "Damped-trend ETS per country x category; coherent intervals from 2,000 correlated simulations"))
p.interactions.append({"source": uid("fcst", "sl_year"), "target": uid("fcst", "fc_chart"), "type": "NoFilter"})
# scenario panel
p.add("sc_title", "textbox", X0 + 1116, 234, 516, 64,
      objects={"general": [{"properties": {"paragraphs": [
          {"textRuns": [{"value": "What-if scenario (open months)",
                         "textStyle": {"fontSize": "13pt", "color": INK, "fontWeight": "bold"}}]},
          {"textRuns": [{"value": "Applies to Oct 2026 - Dec 2027 forecast; actuals are not changed",
                         "textStyle": {"fontSize": "9pt", "color": MUTED}}]}]}}]},
      vco=container_objects(background="#FFFFFF", border=LINE, padding=(10, 16, 4, 16), header=False))
for i, (key, fld, ttl) in enumerate([("sl_price", C("Scenario Price Change", "Price Change %"), "Price change"),
                                     ("sl_vol", C("Scenario Volume Change", "Volume Change %"), "Volume change"),
                                     ("sl_cost", C("Scenario Cost Inflation", "Cost Inflation %"), "COGS inflation")]):
    slicer(p, key, X0 + 1116 + i * 176, 306, 164, 62, fld, ttl, single=True, default=[0.0], mode="Dropdown")
kpi(p, "sc_ns", X0 + 1116, 384, 250, 132, "Scenario Net Sales", "Scenario net sales", "Scenario Net Sales Impact",
    "Color Scenario EBITDA")
kpi(p, "sc_eb", X0 + 1382, 384, 250, 132, "Scenario EBITDA", "Scenario EBITDA", "Scenario EBITDA Impact",
    "Color Scenario EBITDA")
o = axis_objects(legend=True, labels=True)
series_colors(o, [(M("Outlook EBITDA (Base)"), SLATE), (M("Scenario EBITDA"), TEAL)])
p.add("sc_chart", "clusteredColumnChart", X0 + 1116, 532, 516, 132 + 392,
      query={"Category": [C("Date", "Year")],
             "Y": [proj(M("Outlook EBITDA (Base)"), "Base"), proj(M("Scenario EBITDA"), "Scenario")]},
      sort=[(C("Date", "Year"), "Ascending")], objects=o,
      filters=[categorical_filter("f_sc_years", "Date", "Year", [2026, 2027], hidden=True)],
      vco=vtitle("EBITDA outlook: base vs scenario", "2026 = actuals + Q4 forecast; 2027 = full forecast"))
p.interactions.append({"source": uid("fcst", "sl_year"), "target": uid("fcst", "sc_chart"), "type": "NoFilter"})
o = axis_objects(legend=True, labels=False)
series_colors(o, [(M("Back-test Actual"), BLUE), (M("Back-test Forecast"), TEAL)])
p.add("backtest", "clusteredColumnChart", X0, 680, 540, 376,
      query={"Category": [C("Date", "Month Short")],
             "Y": [proj(M("Back-test Actual"), "Actual"), proj(M("Back-test Forecast"), "Back-test forecast")]},
      sort=[(C("Date", "Month Short"), "Ascending")], objects=o,
      filters=[categorical_filter("f_bt_year", "Date", "Year", [2026], hidden=True)],
      vco=vtitle("Back-test: Apr-Sep 2026 out-of-sample", "Model trained only on data up to Mar 2026"))
p.interactions.append({"source": uid("fcst", "sl_year"), "target": uid("fcst", "backtest"), "type": "NoFilter"})
o = axis_objects(legend=True, labels=True)
series_colors(o, [(M("Forecast WAPE"), TEAL), (M("Naive WAPE"), SLATE)])
p.add("acc_ctry", "clusteredBarChart", X0 + 556, 680, 544, 376,
      query={"Category": [C("Country", "Country")],
             "Y": [proj(M("Forecast WAPE"), "ETS error (WAPE)"), proj(M("Naive WAPE"), "Naive error")]},
      sort=[(M("Forecast WAPE"), "Ascending")], objects=o,
      vco=vtitle("Forecast error by country: ETS vs seasonal naive", "Lower is better"))

# ----------------------------------------------------------- 6 Data quality
p = new_page("dq")
kpi_row(p, [
    ("Record Accuracy %", "Record-level accuracy", None, None),
    ("DQ Checks Passed", "Rules passed", None, None),
    ("DQ Checks Warning", "Rules with warning", None, None),
    ("DQ Checks Failed", "Rules failed", None, None),
    ("Feed SLA %", "Feeds loaded within SLA", None, None),
    ("DQ Exception Rows", "Exceptions logged", None, None),
])
o = table_objects(font=9, row_padding=2)
st = C("DQ Checks", "Status")
o.setdefault("values", []).append(obj(sel_fx(st.query_ref), fontColor=mcolor("Color DQ Status")))
p.add("dq_table", "tableEx", X0, 234, W_CONTENT, 430,
      query={"Values": [proj(C("DQ Checks", "Check ID"), "ID"), proj(C("DQ Checks", "Check")),
                        proj(C("DQ Checks", "DQ Dimension"), "Dimension"), proj(C("DQ Checks", "Source")),
                        proj(C("DQ Checks", "Business Rule"), "Business rule"),
                        proj(C("DQ Checks", "Rows Failed"), "Failed rows"),
                        proj(C("DQ Checks", "Fail Rate"), "Fail rate"), proj(C("DQ Checks", "Tolerance")),
                        proj(st), proj(C("DQ Checks", "Action Taken"), "Remediation")]},
      sort=[(C("DQ Checks", "Check ID"), "Ascending")], objects=o,
      vco=vtitle("Data-quality rules (ETL run)",
                 "14 automated checks: uniqueness, validity, completeness, consistency, integrity, accuracy, timeliness"))
o = axis_objects(legend=False, labels=True)
o["dataPoint"] = [obj(fill=color(CORAL))]
p.add("dq_exc_bar", "clusteredBarChart", X0, 680, 520, 376,
      query={"Category": [C("DQ Exceptions", "Check")], "Y": [proj(M("DQ Exception Rows"), "Exceptions")]},
      sort=[(M("DQ Exception Rows"), "Descending")], objects=o, vco=vtitle("Exceptions by rule"))
p.add("dq_exc_tbl", "tableEx", X0 + 536, 680, 560, 376,
      query={"Values": [proj(C("DQ Exceptions", "Check ID"), "ID"), proj(C("DQ Exceptions", "Record")),
                        proj(C("DQ Exceptions", "Issue")), proj(C("DQ Exceptions", "Observed Value"), "Observed")]},
      sort=[(C("DQ Exceptions", "Check ID"), "Ascending")], objects=table_objects(font=9),
      vco=vtitle("Exception log (row level)", "Hand-off list for data owners"))
o = table_objects(font=9)
o["rowHeaders"] = [obj(fontColor=color(INK), fontSize=9)]
o["subTotals"] = [obj(rowSubtotals=False, columnSubtotals=False)]
fx_back(o, M("Feed Lag Days"), "Color Feed Lag")
p.add("dq_feeds", "pivotTable", X0 + 1112, 680, 520, 376,
      query={"Rows": [C("Country", "Country")], "Columns": [C("DQ Load Log", "Period")],
             "Values": [proj(M("Feed Lag Days"), "Lag (days)")]},
      sort=[(C("Country", "Country"), "Ascending")], objects=o,
      filters=[date_ge_filter("f_feed_date", "DQ Load Log", "Period", "2026-04-01")],
      vco=vtitle("Feed timeliness (days after month-end)", "SLA = 3 days; red = late feed"))

# ----------------------------------------------------------- 7 Customer drill-through
p = Page("customer", "Customer Detail", ptype="Drillthrough", hidden=False)
pages["customer"] = p
p.filters = [{"name": "f_dt_customer", "field": C("Customer", "Customer").expr, "type": "Categorical",
              "howCreated": "Drillthrough"}]
p.binding = {"name": uid("binding", "customer"), "type": "Drillthrough", "referenceScope": "Default",
             "parameters": [{"name": uid("param", "customer"), "boundFilter": "f_dt_customer",
                             "fieldExpr": C("Customer", "Customer").expr}]}
nav_rail(p, None)
p.add("back", "actionButton", X0, 26, 150, 44,
      objects={"icon": [obj(SEL_DEFAULT, shapeType="blank")],
               "text": [obj(show=True), obj(SEL_DEFAULT, text="\u2190  Back", fontColor=color("#FFFFFF"),
                                            fontSize=12, bold=True)],
               "fill": [obj(show=True), obj(SEL_DEFAULT, fillColor=color(BLUE), transparency=0)],
               "outline": [obj(show=False)], "shape": [obj(SEL_DEFAULT, roundEdge=8)]},
      vco=container_objects(background=False, border=False, shadow=False, header=False,
                            link={"show": True, "type": "Back"}))
p.add("cust_hdr", "cardVisual", X0 + 170, 14, W_CONTENT - 170, 76,
      query={"Data": [proj(M("Selected Customer"), "Customer detail")]},
      objects=card_objects(value_size=16, label_size=9),
      vco=container_objects(background=False, border=False, shadow=False, header=False, padding=(4, 4, 4, 4)))
kpi_row(p, [
    ("Net Sales", "Net sales (EUR)", "KPI Net Sales YoY Label", "Color YoY"),
    ("Gross Margin %", "Gross margin %", None, None),
    ("Orders", "Orders", None, None),
    ("Avg Order Value", "Average order value", None, None),
    ("OTIF %", "OTIF", "KPI OTIF Label", "Color OTIF"),
    ("Discount %", "Discount %", None, None),
])
o = axis_objects(legend=True)
series_colors(o, [(M("Net Sales"), BLUE), (M("Net Sales PY"), SLATE)])
p.add("cust_trend", "lineChart", X0, 234, 1000, 400,
      query={"Category": [C("Date", "Year Month")],
             "Y": [proj(M("Net Sales"), "Net sales"), proj(M("Net Sales PY"), "Prior year")]},
      sort=[(C("Date", "Year Month"), "Ascending")], objects=o,
      vco=vtitle("Monthly net sales vs prior year"))
o = axis_objects(legend=False, labels=True)
o["dataPoint"] = [obj(fill=color(TEAL))]
p.add("cust_cat", "clusteredBarChart", X0 + 1016, 234, 616, 400,
      query={"Category": [C("Category", "Category")], "Y": [proj(M("Net Sales"), "Net sales")]},
      sort=[(M("Net Sales"), "Descending")], objects=o, vco=vtitle("Category mix"))
p.add("cust_prod", "tableEx", X0, 650, W_CONTENT, 406,
      query={"Values": [proj(C("Product", "Product")), proj(C("Product", "Brand")),
                        proj(M("Net Sales"), "Net sales"), proj(M("Net Sales YoY %"), "YoY"),
                        proj(M("Units")), proj(M("Gross Margin %"), "GM %"), proj(M("Discount %")),
                        proj(M("In-Full %"), "In-full")]},
      sort=[(M("Net Sales"), "Descending")], objects=fx_font(table_objects(), M("Net Sales YoY %"), "Color YoY"),
      vco=vtitle("Products bought"))

# ----------------------------------------------------------- 8 Tooltip
p = Page("tooltip_country", "Country Tooltip", width=420, height=270, ptype="Tooltip", hidden=True,
         background="#FFFFFF")
pages["tooltip_country"] = p
p.binding = {"name": uid("binding", "tooltip"), "type": "Tooltip", "referenceScope": "Default"}
p.add("tt_title", "cardVisual", 12, 8, 396, 52, query={"Data": [proj(M("Selected Period"), "Country snapshot")]},
      objects=card_objects(value_size=11, label_size=9),
      vco=container_objects(background=False, border=False, shadow=False, header=False, padding=(0, 0, 0, 0)))
for i, (m_, lbl) in enumerate([("Net Sales", "Net sales"), ("Net Sales YoY %", "vs PY"),
                               ("Net Sales vs Budget %", "vs budget"), ("Gross Margin %", "GM %"),
                               ("EBITDA %", "EBITDA %"), ("OTIF %", "OTIF")]):
    r, c = divmod(i, 3)
    p.add(f"tt_{i}", "cardVisual", 12 + c * 134, 68 + r * 98, 126, 90,
          query={"Data": [proj(M(m_), lbl)]}, objects=card_objects(value_size=17, label_size=9),
          vco=container_objects(background="#F3F5F9", border=False, shadow=False, header=False,
                                padding=(8, 8, 6, 10)))

# =================================================================== WRITE
if os.path.exists(REPORT):
    shutil.rmtree(REPORT)
order = ["exec", "sales", "profit", "ops", "fcst", "dq", "customer", "tooltip_country"]
for key in order:
    pg = pages[key]
    base = os.path.join(DEF, "pages", pg.name)
    dump(os.path.join(base, "page.json"), pg.page_json())
    for v in pg.visuals:
        dump(os.path.join(base, "visuals", v["name"], "visual.json"), v)
dump(os.path.join(DEF, "pages", "pages.json"),
     {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json",
      "pageOrder": [pages[k].name for k in order], "activePageName": pages["exec"].name})
# ---- theme + report.json
THEME = "CEEHubTheme.json"
theme = {
    "name": "CEE Performance Hub",
    "dataColors": [BLUE, TEAL, AMBER, CORAL, SKY, PLUM, SLATE, "#C9B79C", "#3D9970", "#F28E2B"],
    "foreground": INK, "foregroundNeutralSecondary": MUTED, "foregroundNeutralTertiary": "#98A2B3",
    "background": "#FFFFFF", "backgroundLight": "#F3F5F9", "backgroundNeutral": "#E4E8EE",
    "tableAccent": BLUE, "good": GOOD, "neutral": "#D98E04", "bad": BAD,
    "maximum": BLUE, "center": "#9FC5E8", "minimum": "#F3F5F9",
    "textClasses": {
        "callout": {"fontSize": 26, "fontFace": "Segoe UI Semibold", "color": NAVY},
        "title": {"fontSize": 12, "fontFace": "Segoe UI Semibold", "color": INK},
        "header": {"fontSize": 12, "fontFace": "Segoe UI Semibold", "color": INK},
        "label": {"fontSize": 10, "fontFace": "Segoe UI", "color": MUTED}},
    "visualStyles": {
        "*": {"*": {
            "title": [{"show": True, "fontSize": 12, "fontColor": {"solid": {"color": INK}}, "bold": True}],
            "subTitle": [{"show": True, "fontSize": 9, "fontColor": {"solid": {"color": MUTED}}}],
            "border": [{"show": True, "color": {"solid": {"color": LINE}}, "radius": 10, "width": 1}],
            "dropShadow": [{"show": True, "preset": "Custom", "position": "Outer",
                            "color": {"solid": {"color": NAVY}}, "transparency": 93, "shadowBlur": 12,
                            "shadowDistance": 2, "shadowSpread": 0, "angle": 90}],
            "padding": [{"top": 12, "bottom": 12, "left": 14, "right": 14}],
            "valueAxis": [{"gridlineColor": {"solid": {"color": "#EEF1F5"}}}],
            "categoryAxis": [{"gridlineShow": False}]}},
        "page": {"*": {"background": [{"color": {"solid": {"color": "#F3F5F9"}}, "transparency": 0}],
                       "outspace": [{"color": {"solid": {"color": "#E4E8EE"}}}]}}}}
dump(os.path.join(REPORT, "StaticResources", "RegisteredResources", THEME), theme)
VERS = {"visual": "2.14.0", "report": "3.4.0", "page": "2.3.1"}
report = {
    "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.3.0/schema.json",
    "themeCollection": {
        "baseTheme": {"name": "Fluent2-CY26SU10", "reportVersionAtImport": VERS, "type": "SharedResources"},
        "customTheme": {"name": THEME, "reportVersionAtImport": VERS, "type": "RegisteredResources"}},
    "objects": {"section": [{"properties": {"verticalAlignment": {"expr": {"Literal": {"Value": "'Top'"}}}}}]},
    "resourcePackages": [
        {"name": "SharedResources", "type": "SharedResources",
         "items": [{"name": "Fluent2-CY26SU10", "path": "BaseThemes/Fluent2-CY26SU10.json", "type": "BaseTheme"}]},
        {"name": "RegisteredResources", "type": "RegisteredResources",
         "items": [{"name": THEME, "path": THEME, "type": "CustomTheme"}]}],
    "settings": {"useStylableVisualContainerHeader": True, "exportDataMode": "AllowSummarized",
                 "defaultDrillFilterOtherVisuals": True, "allowChangeFilterTypes": True,
                 "useEnhancedTooltips": True, "useDefaultAggregateDisplayName": True}}
dump(os.path.join(DEF, "report.json"), report)
print("pages:", {k: (pages[k].name, len(pages[k].visuals)) for k in order})
print("total visuals:", sum(len(pages[k].visuals) for k in order))
