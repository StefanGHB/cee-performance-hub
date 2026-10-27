"""
Step 3 - Statistical demand forecast (net sales EUR) per country x category.

Method
  * ETS (exponential smoothing state-space model) with damped additive trend and
    additive 12-month seasonality, fitted on log(net sales): prediction intervals are
    asymmetric and always positive.
  * Back-test: train Jan-2023..Mar-2026, predict Apr..Sep-2026 (6-month hold-out),
    benchmarked against a seasonal-naive forecast (same month last year).
  * Forward forecast: refit on all actuals, predict Oct-2026..Dec-2027.
  * Prediction intervals: 2,000 simulated future paths per series using a residual
    BOOTSTRAP with a shared random state. Every series draws the same historical
    month's residual at each step, so the cross-series correlation of shocks is
    preserved and intervals can be aggregated coherently to country, category and
    total level (summing bounds or assuming independence would be wrong).

Outputs (../data/model):
  fact_forecast.parquet         month x country x category x type (point + series intervals)
  forecast_interval.parquet     forward intervals at Total / Country / Category / Series level
  forecast_accuracy.parquet     WAPE inputs per series, ETS vs seasonal naive
"""
import os
import warnings

import duckdb
import numpy as np
import pandas as pd
from statsmodels.tsa.exponential_smoothing.ets import ETSModel

warnings.filterwarnings("ignore")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = os.path.join(ROOT, "data", "model")
N_SIM = 2000
SEED = 42
HOLDOUT = 6
H_FWD = 15                                   # Oct-2026 .. Dec-2027
Q = {"Lower 95": 0.025, "Lower 80": 0.10, "Upper 80": 0.90, "Upper 95": 0.975}

con = duckdb.connect()
hist = con.execute(f"""
    SELECT date_trunc('month', s."Order Date")::DATE AS month, s."Country Code" AS cc, p."Category ID" AS cat,
           SUM(s."Net Sales EUR") AS ns
    FROM '{MODEL}/fact_sales.parquet' s JOIN '{MODEL}/dim_product.parquet' p USING ("SKU")
    GROUP BY ALL ORDER BY 1""").df()
hist["month"] = pd.to_datetime(hist["month"])
LAST = hist.month.max()


def fit(y: pd.Series):
    m = ETSModel(np.log(y), error="add", trend="add", damped_trend=True, seasonal="add",
                 seasonal_periods=12, initialization_method="heuristic")
    return m.fit(disp=False, maxiter=2000)


def point_forecast(res, n_obs: int, h: int) -> np.ndarray:
    return np.exp(res.get_prediction(start=n_obs, end=n_obs + h - 1).predicted_mean.values)


_IDX = {}


def simulate(res, h: int) -> np.ndarray:
    """h x N_SIM matrix of simulated net sales (EUR).

    Residual bootstrap with a SHARED index matrix: at each simulated step all series
    re-use the residual of the same historical month, preserving cross-series correlation.
    """
    resid = np.asarray(res.resid)
    key = (len(resid), h)
    if key not in _IDX:
        _IDX[key] = np.random.default_rng(SEED).integers(0, len(resid), size=(h, N_SIM))
    sim = res.simulate(nsimulations=h, repetitions=N_SIM, anchor="end", random_errors=resid[_IDX[key]])
    return np.exp(np.asarray(sim))


rows, acc, sims, points = [], [], {}, {}
fwd_months = pd.date_range(LAST + pd.offsets.MonthBegin(1), periods=H_FWD, freq="MS")
for (cc, cat), g in hist.groupby(["cc", "cat"]):
    y = g.set_index("month").ns.asfreq("MS")
    # ---- back-test (out-of-sample)
    train, test = y.iloc[:-HOLDOUT], y.iloc[-HOLDOUT:]
    r_bt = fit(train)
    f_bt = point_forecast(r_bt, len(train), HOLDOUT)
    s_bt = simulate(r_bt, HOLDOUT)
    bt = pd.DataFrame({"Month": test.index, "Forecast EUR": f_bt})
    for k, q in Q.items():
        bt[k] = np.quantile(s_bt, q, axis=1)
    bt["Forecast Type"] = "Back-test"
    snaive = y.shift(12).iloc[-HOLDOUT:].values
    acc.append((cc, cat, "ETS (damped trend)", np.mean(np.abs(f_bt - test.values) / test.values),
                f_bt.sum() / test.values.sum() - 1, np.abs(f_bt - test.values).sum(), test.values.sum()))
    acc.append((cc, cat, "Seasonal naive", np.mean(np.abs(snaive - test.values) / test.values),
                snaive.sum() / test.values.sum() - 1, np.abs(snaive - test.values).sum(), test.values.sum()))
    # ---- forward
    r = fit(y)
    f = point_forecast(r, len(y), H_FWD)
    s = simulate(r, H_FWD)
    # re-centre simulated paths on the point forecast (median-unbiased): keeps the
    # bootstrap spread & correlation while making bounds consistent with the point
    s = s * (f / np.median(s, axis=1))[:, None]
    sims[(cc, cat)], points[(cc, cat)] = s, f
    fw = pd.DataFrame({"Month": fwd_months, "Forecast EUR": f})
    for k, q in Q.items():
        fw[k] = np.quantile(s, q, axis=1)
    fw["Forecast Type"] = "Forward"
    for df in (bt, fw):
        df["Country Code"], df["Category ID"] = cc, cat
        rows.append(df)

fc = pd.concat(rows, ignore_index=True)
fc["Month"] = fc["Month"].dt.date
fc = fc[["Month", "Country Code", "Category ID", "Forecast Type", "Forecast EUR", *Q.keys()]].round(2)

# ---- coherent intervals at every aggregation level (forward only)
levels = []
keys = list(sims)


def add_level(level, cc, cat, members):
    tot_sim = sum(sims[k] for k in members)
    tot_pt = sum(points[k] for k in members)
    d = pd.DataFrame({"Month": fwd_months.date, "Level": level, "Country Code": cc, "Category ID": cat,
                      "Forecast EUR": tot_pt})
    for k, q in Q.items():
        d[k] = np.quantile(tot_sim, q, axis=1)
    levels.append(d)


add_level("Total", "ALL", "ALL", keys)
for cc in sorted({k[0] for k in keys}):
    add_level("Country", cc, "ALL", [k for k in keys if k[0] == cc])
for cat in sorted({k[1] for k in keys}):
    add_level("Category", "ALL", cat, [k for k in keys if k[1] == cat])
for k in keys:
    add_level("Series", k[0], k[1], [k])
fi = pd.concat(levels, ignore_index=True).round(2)

accdf = pd.DataFrame(acc, columns=["Country Code", "Category ID", "Model", "MAPE", "Bias", "Abs Error EUR",
                                   "Actual EUR"])
for name, df in (("fact_forecast", fc), ("forecast_interval", fi), ("forecast_accuracy", accdf)):
    con.register("tmp", df)
    con.execute(f"COPY (SELECT * FROM tmp) TO '{MODEL}/{name}.parquet' (FORMAT PARQUET)")
    con.unregister("tmp")

w = accdf.groupby("Model").apply(lambda d: d["Abs Error EUR"].sum() / d["Actual EUR"].sum())
print("WAPE on 6-month hold-out:\n" + (w * 100).round(2).to_string())
t = fi[fi.Level == "Total"].copy()
t["w80"] = (t["Upper 80"] - t["Lower 80"]) / t["Forecast EUR"] / 2 * 100
print("\nTotal-level forecast (EUR m) and +/- half-width of 80% PI (%):")
print(pd.DataFrame({"month": t.Month, "fc": (t["Forecast EUR"] / 1e6).round(1), "pm80%": t.w80.round(1)})
      .head(6).to_string(index=False))
s = fi[fi.Level == "Series"]
print("median series-level +/-80% half-width:",
      round(float(((s["Upper 80"] - s["Lower 80"]) / s["Forecast EUR"] / 2).median() * 100), 1), "%")
