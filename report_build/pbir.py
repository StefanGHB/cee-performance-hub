"""Tiny helper library to author Power BI PBIR (enhanced report format) files from Python."""
import hashlib
import json

VC_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.14.0/schema.json"
PAGE_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"

MEASURE_TABLE = "_Measures"


def uid(*parts) -> str:
    """Deterministic 20-char id (Power BI style)."""
    return hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:20]


# ------------------------------------------------------------------ literals
def lit(v):
    if isinstance(v, bool):
        s = "true" if v else "false"
    elif isinstance(v, (int, float)):
        s = f"{v}D"
    else:
        s = "'" + str(v).replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": s}}}


def color(hex_):
    return {"solid": {"color": {"expr": {"Literal": {"Value": f"'{hex_}'"}}}}}


def mexpr(measure):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": MEASURE_TABLE}}, "Property": measure}}


def mcolor(measure):
    """Colour driven by a measure returning a hex code (conditional formatting fx)."""
    return {"solid": {"color": {"expr": mexpr(measure)}}}


def _wrap(v):
    if isinstance(v, dict) and ("solid" in v or "expr" in v or "filter" in v):
        return v
    return lit(v)


def obj(selector=None, **props):
    d = {"properties": {k: _wrap(v) for k, v in props.items()}}
    if selector is not None:
        d["selector"] = selector
    return d


SEL_DEFAULT = {"id": "default"}


def sel_metadata(query_ref):
    return {"metadata": query_ref}


def sel_fx(query_ref=None):
    s = {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}
    if query_ref:
        s["metadata"] = query_ref
    return s


# ------------------------------------------------------------------- fields
class F:
    """A field reference usable in projections, sorts and filters."""

    def __init__(self, expr, query_ref, native):
        self.expr, self.query_ref, self.native = expr, query_ref, native


def M(name):
    return F(mexpr(name), f"{MEASURE_TABLE}.{name}", name)


def C(table, col):
    return F({"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": col}}, f"{table}.{col}", col)


def proj(f: F, display=None, active=None):
    p = {"field": f.expr, "queryRef": f.query_ref, "nativeQueryRef": f.native}
    if display:
        p["displayName"] = display
    if active is not None:
        p["active"] = active
    return p


# ------------------------------------------------------------------ filters
def _src(entity, alias):
    return {"Name": alias, "Entity": entity, "Type": 0}


def in_filter_def(table, col, values, alias="d"):
    vals = []
    for v in values:
        if isinstance(v, bool):
            s = "true" if v else "false"
        elif isinstance(v, int):
            s = f"{v}L"
        elif isinstance(v, float):
            s = f"{v}D"
        else:
            s = "'" + str(v).replace("'", "''") + "'"
        vals.append([{"Literal": {"Value": s}}])
    return {"Version": 2, "From": [_src(table, alias)],
            "Where": [{"Condition": {"In": {"Expressions": [
                {"Column": {"Expression": {"SourceRef": {"Source": alias}}, "Property": col}}], "Values": vals}}}]}


def categorical_filter(name, table, col, values, hidden=False):
    f = {"name": name, "field": C(table, col).expr, "type": "Categorical",
         "filter": in_filter_def(table, col, values), "howCreated": "User"}
    if hidden:
        f["isHiddenInViewMode"] = True
    return f


def measure_filter(name, measure, kind, value, hidden=True):
    """kind: 0 '=', 1 '>', 2 '>=', 3 '<', 4 '<='."""
    s = f"{value}L" if isinstance(value, int) else f"{value}D"
    f = {"name": name, "field": M(measure).expr, "type": "Advanced",
         "filter": {"Version": 2, "From": [_src(MEASURE_TABLE, "m")],
                    "Where": [{"Condition": {"Comparison": {
                        "ComparisonKind": kind,
                        "Left": {"Measure": {"Expression": {"SourceRef": {"Source": "m"}}, "Property": measure}},
                        "Right": {"Literal": {"Value": s}}}}}]},
         "howCreated": "User"}
    if hidden:
        f["isHiddenInViewMode"] = True
    return f


def date_ge_filter(name, table, col, iso_date, hidden=True):
    f = {"name": name, "field": C(table, col).expr, "type": "Advanced",
         "filter": {"Version": 2, "From": [_src(table, "d")],
                    "Where": [{"Condition": {"Comparison": {
                        "ComparisonKind": 2,
                        "Left": {"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": col}},
                        "Right": {"Literal": {"Value": f"datetime'{iso_date}T00:00:00'"}}}}}]},
         "howCreated": "User"}
    if hidden:
        f["isHiddenInViewMode"] = True
    return f


# ------------------------------------------------------------------ visuals
def container_objects(title=None, subtitle=None, background=None, border=None, shadow=None, padding=None,
                      header=None, link=None, tooltip_page=None, title_size=12):
    vco = {}
    if title is None:
        vco["title"] = [obj(show=False)]
    else:
        vco["title"] = [obj(show=True, text=title, fontSize=title_size, fontColor=color("#1F2937"), bold=True)]
    if subtitle:
        vco["subTitle"] = [obj(show=True, text=subtitle, fontSize=9, fontColor=color("#6B7685"))]
    else:
        vco["subTitle"] = [obj(show=False)]
    if background is not None:
        if background is False:
            vco["background"] = [obj(show=False)]
        else:
            vco["background"] = [obj(show=True, color=color(background), transparency=0)]
    if border is not None:
        if border is False:
            vco["border"] = [obj(show=False)]
        else:
            vco["border"] = [obj(show=True, color=color(border), radius=10, width=1)]
    if shadow is not None:
        vco["dropShadow"] = [obj(show=shadow)]
    if padding is not None:
        vco["padding"] = [obj(top=padding[0], right=padding[1], bottom=padding[2], left=padding[3])]
    if header is not None:
        vco["visualHeader"] = [obj(show=header)]
    if link is not None:
        vco["visualLink"] = [obj(**link)]
    if tooltip_page is not None:
        vco["visualTooltip"] = [obj(show=True, type="ReportPage", section=tooltip_page)]
    return vco


class Page:
    def __init__(self, key, display, width=1920, height=1080, ptype=None, hidden=False, background="#F3F5F9"):
        self.key, self.name, self.display = key, uid("page", key), display
        self.width, self.height, self.ptype, self.hidden = width, height, ptype, hidden
        self.background = background
        self.visuals = []
        self.filters = []
        self.binding = None
        self.interactions = []
        self._z = 0

    def add(self, key, vtype, x, y, w, h, query=None, objects=None, vco=None, sort=None, filters=None,
            sync=None, drill_filter=None):
        name = uid(self.key, key)
        self._z += 1
        v = {"visualType": vtype}
        if query:
            qs = {}
            for role, items in query.items():
                if isinstance(items, dict):  # already a projection state (e.g. field parameter)
                    qs[role] = items
                else:
                    qs[role] = {"projections": [i if isinstance(i, dict) else proj(i) for i in items]}
            v["query"] = {"queryState": qs}
            if sort:
                v["query"]["sortDefinition"] = {
                    "sort": [{"field": f.expr, "direction": d} for f, d in sort], "isDefaultSort": False}
        if objects:
            v["objects"] = objects
        if vco:
            v["visualContainerObjects"] = vco
        if sync:
            v["syncGroup"] = {"groupName": sync, "fieldChanges": True, "filterChanges": True}
        if drill_filter is not None:
            v["drillFilterOtherVisuals"] = drill_filter
        container = {"$schema": VC_SCHEMA, "name": name,
                     "position": {"x": x, "y": y, "z": self._z * 1000, "height": h, "width": w,
                                  "tabOrder": self._z * 1000},
                     "visual": v}
        if filters:
            container["filterConfig"] = {"filters": filters}
        self.visuals.append(container)
        return name

    def page_json(self):
        p = {"$schema": PAGE_SCHEMA, "name": self.name, "displayName": self.display,
             "displayOption": "FitToPage", "height": self.height, "width": self.width,
             "objects": {"background": [obj(color=color(self.background), transparency=0)],
                         "outspace": [{"properties": {"color": color("#E4E8EE")}}]}}
        if self.ptype:
            p["type"] = self.ptype
        if self.hidden:
            p["visibility"] = "HiddenInViewMode"
        if self.filters:
            p["filterConfig"] = {"filters": self.filters}
        if self.binding:
            p["pageBinding"] = self.binding
        if self.interactions:
            p["visualInteractions"] = self.interactions
        return p


def dump(path, data):
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def field_param_filter_def(table, display_col, fields_col, display_value, field_ref):
    """Default selection for a field-parameter slicer (composite key: display + fields column)."""
    q = lambda x: "'" + x.replace("'", "''") + "'"
    return {"Version": 2, "From": [_src(table, "p")],
            "Where": [{"Condition": {"In": {
                "Expressions": [
                    {"Column": {"Expression": {"SourceRef": {"Source": "p"}}, "Property": display_col}},
                    {"Column": {"Expression": {"SourceRef": {"Source": "p"}}, "Property": fields_col}}],
                "Values": [[{"Literal": {"Value": q(display_value)}}, {"Literal": {"Value": q(field_ref)}}]]}}}]}
