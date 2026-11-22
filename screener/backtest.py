"""Walk-forward (out-of-sample) backtest of the rating system.

For each historical earnings event, the ticker/window is re-scored using ONLY events
that had fully closed before the trade's entry date, and baseline drift measured only
on prices before entry.  If the score passes the rule, the trade is taken.  Comparing
the selected trades against "every event" tells you whether the screener's ratings
actually predicted anything, rather than just describing the past.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .engine import score_arrays, wilson_lower


@dataclass
class BacktestParams:
    window_keys: list
    min_prior: int = 8           # prior events required before trading
    lookback: int = 0            # 0 = use all prior events, else last K
    min_score: float = 62.0
    min_win_rate: float = 0.0    # on prior events
    direction: int = 1           # +1 long, -1 short
    cost_bps: float = 10.0       # round-trip cost per trade
    start: pd.Timestamp | None = None
    tickers: list | None = None  # restrict universe


def run_backtest(results: dict[str, dict], p: BacktestParams) -> dict:
    cost = p.cost_bps / 10000.0
    trades, universe = [], []
    for tkr, res in results.items():
        if p.tickers and tkr not in p.tickers:
            continue
        for key in p.window_keys:
            wr = res["window_returns"].get(key)
            base, L = res["baseline"].get(key, (np.array([]), 0))
            if wr is None or len(wr) <= p.min_prior:
                continue
            wr = wr.sort_values("entry_date").reset_index(drop=True)
            label = next((r["window"] for r in res["rows"] if r["window_key"] == key), key)
            # cumulative baseline stats available up to each index
            if len(base):
                cs = np.concatenate([[0.0], np.cumsum(base)])
                cw = np.concatenate([[0], np.cumsum(base > 0)])
            ent = wr["entry_date"].values.astype("datetime64[ns]")
            ext = wr["exit_date"].values.astype("datetime64[ns]")
            rets = wr["ret"].values.astype(float)
            excs = wr["excess"].values.astype(float)
            eis = wr["entry_i"].values.astype(int)
            evd = wr["event_date"].values
            start = np.datetime64(p.start) if p.start is not None else None
            for k in range(len(wr)):
                if start is not None and ent[k] < start:
                    continue
                m = np.flatnonzero(ext < ent[k])
                if p.lookback:
                    m = m[-p.lookback:]
                if len(m) < p.min_prior:
                    continue
                # baseline only from returns fully realised before entry
                upto = int(eis[k]) - L
                if len(base) and upto > 50:
                    bmean = cs[upto] / upto
                    bwin = cw[upto] / upto
                else:
                    bmean, bwin = 0.0, 0.5
                pr = rets[m]
                sc = score_arrays(pr, excs[m], bwin, bmean, p.direction, cost)
                pwr = ((pr * p.direction) > 0).mean()
                net = rets[k] * p.direction - cost
                rec = {
                    "ticker": tkr, "window": label, "event_date": pd.Timestamp(evd[k]),
                    "entry_date": pd.Timestamp(ent[k]), "exit_date": pd.Timestamp(ext[k]),
                    "ret": net, "gross": rets[k] * p.direction,
                    "excess": (excs[k] * p.direction - cost) if np.isfinite(excs[k]) else np.nan,
                    "score": sc, "prior_n": len(m), "prior_win": pwr,
                    "prior_wilson": wilson_lower(int(((pr * p.direction) > 0).sum()), len(pr)),
                }
                universe.append(rec)
                if np.isfinite(sc) and sc >= p.min_score and pwr >= p.min_win_rate:
                    trades.append(rec)
    tdf = pd.DataFrame(trades)
    udf = pd.DataFrame(universe)
    out = {"trades": tdf, "universe": udf,
           "summary_selected": summarize(tdf), "summary_all": summarize(udf)}
    out["by_year"] = by_year(tdf, udf)
    out["by_score"] = by_score_bucket(udf)
    return out


def summarize(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {"trades": 0}
    r = df["ret"].values
    curve = equity_curve(df)
    gains, losses = r[r > 0].sum(), -r[r < 0].sum()
    ex = df["excess"].dropna().values
    return {
        "trades": len(r),
        "win_rate": (r > 0).mean(),
        "avg": r.mean(),
        "median": float(np.median(r)),
        "std": r.std(ddof=1) if len(r) > 1 else np.nan,
        "sharpe_per_trade": r.mean() / r.std(ddof=1) if len(r) > 1 and r.std(ddof=1) > 0 else np.nan,
        "profit_factor": gains / losses if losses > 0 else np.inf,
        "avg_excess": ex.mean() if len(ex) else np.nan,
        "beat_spy": (ex > 0).mean() if len(ex) else np.nan,
        "total": r.sum(),
        "max_drawdown": float((curve["cum"] - curve["cum"].cummax()).min()) if len(curve) else np.nan,
        "tickers": df["ticker"].nunique(),
    }


def equity_curve(df: pd.DataFrame) -> pd.DataFrame:
    """Cumulative sum of per-trade returns by exit date (1 unit risked per trade)."""
    if df is None or df.empty:
        return pd.DataFrame(columns=["date", "cum"])
    s = df.groupby("exit_date")["ret"].sum().sort_index().cumsum()
    return pd.DataFrame({"date": s.index, "cum": s.values})


def by_year(sel: pd.DataFrame, all_: pd.DataFrame) -> pd.DataFrame:
    def agg(df, tag):
        if df is None or df.empty:
            return pd.DataFrame()
        g = df.assign(year=pd.to_datetime(df["entry_date"]).dt.year).groupby("year")["ret"]
        return pd.DataFrame({f"{tag}_trades": g.size(), f"{tag}_win": g.apply(lambda x: (x > 0).mean()),
                             f"{tag}_avg": g.mean()})
    a, b = agg(sel, "selected"), agg(all_, "all")
    if a.empty:
        return b.reset_index()
    return a.join(b, how="outer").reset_index()


def by_score_bucket(udf: pd.DataFrame) -> pd.DataFrame:
    """Out-of-sample results grouped by the score at the time of entry (calibration check)."""
    if udf is None or udf.empty:
        return pd.DataFrame()
    bins = [-1, 30, 45, 55, 62, 75, 101]
    labels = ["<30", "30-45", "45-55", "55-62", "62-75", "75+"]
    d = udf.dropna(subset=["score"]).copy()
    d["bucket"] = pd.cut(d["score"], bins=bins, labels=labels)
    g = d.groupby("bucket", observed=False)["ret"]
    return pd.DataFrame({"trades": g.size(), "win_rate": g.apply(lambda x: (x > 0).mean() if len(x) else np.nan),
                         "avg": g.mean(), "median": g.median()}).reset_index()
