"""Earnings-pattern analytics: event alignment, window returns, statistics, scoring.

Design notes (what makes this more robust than a plain win-rate screener)
-----------------------------------------------------------------------
* Reaction session is derived from the report timing (before open / after close).
  When timing is unknown it is inferred from which session gapped the most.
* Every window is compared to (a) the stock's *normal* return over the same holding
  length on any random day (baseline drift), and (b) SPY over the exact same dates.
  A stock that wins 70% of the time over 5 days *anyway* has no earnings edge.
* Win rates are shrunk for small samples (Wilson lower bound) and the score is pulled
  toward neutral when there are few observations.
* p-values + Benjamini-Hochberg q-values flag patterns that are likely to be luck when
  screening thousands of ticker/window combinations.
* A walk-forward backtest (backtest.py) re-scores every past event using ONLY the data
  available before it, which is the honest test of whether the rating has any value.
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .market_calendar import add_trading_days, is_trading_day, trading_days_between
from .windows import Window

Z = 1.645  # one-sided 95% for Wilson lower bound
SCORE_SMALL_N = 12  # obs needed for full-strength score


@dataclass
class TickerData:
    ticker: str
    prices: pd.DataFrame          # index=date, Open High Low Close Volume
    earnings: pd.DataFrame        # date, timing, eps_est, eps_act, surprise
    meta: dict = field(default_factory=dict)


# ------------------------------------------------------------------ alignment
def align_events(prices: pd.DataFrame, earnings: pd.DataFrame, years: float | None = None,
                 today: dt.date | None = None) -> pd.DataFrame:
    cols = ["date", "timing", "timing_used", "inferred", "pre_i", "react_i", "pre_date", "react_date",
            "eps_est", "eps_act", "surprise"]
    if prices is None or prices.empty or earnings is None or earnings.empty:
        return pd.DataFrame(columns=cols)
    today = today or dt.date.today()
    dates = prices.index.values.astype("datetime64[D]")
    O = prices["Open"].values
    C = prices["Close"].values
    n = len(dates)
    cutoff = np.datetime64(today - dt.timedelta(days=int(365.25 * years))) if years else None
    recs = []
    for r in earnings.itertuples(index=False):
        d = np.datetime64(pd.Timestamp(r.date).date(), "D")
        if cutoff is not None and d < cutoff:
            continue
        pos = int(np.searchsorted(dates, d, side="left"))
        on_day = pos < n and dates[pos] == d
        # candidate (pre, react) pairs
        bmo = (pos - 1, pos)
        amc = (pos, pos + 1) if on_day else (pos - 1, pos)
        timing = str(r.timing).upper() if isinstance(r.timing, str) and r.timing else "UNK"
        inferred = False
        if timing == "BMO":
            pre, react = bmo
        elif timing == "AMC":
            pre, react = amc
        else:
            inferred = True
            def gap(p):
                a, b = p
                if a < 0 or b >= n:
                    return -1.0
                return abs(O[b] / C[a] - 1)
            pre, react = bmo if gap(bmo) >= gap(amc) else amc
            timing_guess = "BMO" if (pre, react) == bmo and on_day else "AMC"
        if pre < 0 or react >= n:
            continue
        # guard against holes in the price data
        if (dates[react] - d).astype(int) > 6 or (d - dates[pre]).astype(int) > 6:
            continue
        recs.append({
            "date": pd.Timestamp(d), "timing": timing,
            "timing_used": timing_guess if inferred else timing, "inferred": inferred,
            "pre_i": pre, "react_i": react,
            "pre_date": pd.Timestamp(dates[pre]), "react_date": pd.Timestamp(dates[react]),
            "eps_est": getattr(r, "eps_est", np.nan), "eps_act": getattr(r, "eps_act", np.nan),
            "surprise": getattr(r, "surprise", np.nan),
        })
    ev = pd.DataFrame(recs, columns=cols)
    if len(ev):
        ev = ev.drop_duplicates("react_i", keep="last").sort_values("date").reset_index(drop=True)
    return ev


# ------------------------------------------------------------- window returns
def _fields(prices: pd.DataFrame) -> dict:
    return {k: prices[k].values.astype(float) for k in ("Open", "High", "Low", "Close")}


def window_returns(prices: pd.DataFrame, events: pd.DataFrame, w: Window,
                   bench: pd.DataFrame | None = None) -> pd.DataFrame:
    cols = ["event_date", "entry_i", "exit_i", "entry_date", "exit_date", "ret", "bench_ret", "excess", "mae", "mfe"]
    if events is None or events.empty:
        return pd.DataFrame(columns=cols)
    F = _fields(prices)
    n = len(prices)
    dates = prices.index
    ea = events["pre_i"].values if w.entry_anchor == "pre" else events["react_i"].values
    xa = events["pre_i"].values if w.exit_anchor == "pre" else events["react_i"].values
    ei = ea.astype(int) + w.entry_off
    xi = xa.astype(int) + w.exit_off
    same_ok = (w.entry_field == "Open") and (w.exit_field == "Close")
    valid = (ei >= 0) & (xi < n) & ((xi > ei) | ((xi == ei) & same_ok))
    ei, xi = ei[valid], xi[valid]
    ev_dates = events["date"].values[valid]
    entry_px = F[w.entry_field][ei]
    exit_px = F[w.exit_field][xi]
    ret = exit_px / entry_px - 1

    # adverse / favourable excursion while holding
    mae = np.zeros(len(ei))
    mfe = np.zeros(len(ei))
    for k, (a, b) in enumerate(zip(ei, xi)):
        lo = a if w.entry_field == "Open" else a + 1
        hi = b if w.exit_field == "Close" else b - 1
        if hi >= lo:
            mae[k] = min(0.0, F["Low"][lo:hi + 1].min() / entry_px[k] - 1)
            mfe[k] = max(0.0, F["High"][lo:hi + 1].max() / entry_px[k] - 1)
        mae[k] = min(mae[k], ret[k], 0.0)
        mfe[k] = max(mfe[k], ret[k], 0.0)

    entry_dates = dates[ei]
    exit_dates = dates[xi]
    if bench is not None and len(bench):
        bi = bench.index.get_indexer(entry_dates)
        bx = bench.index.get_indexer(exit_dates)
        bE = bench[w.entry_field].values
        bX = bench[w.exit_field].values
        ok = (bi >= 0) & (bx >= 0)
        bret = np.full(len(ei), np.nan)
        bret[ok] = bX[bx[ok]] / bE[bi[ok]] - 1
    else:
        bret = np.full(len(ei), np.nan)
    return pd.DataFrame({
        "event_date": pd.to_datetime(ev_dates), "entry_i": ei, "exit_i": xi,
        "entry_date": entry_dates, "exit_date": exit_dates,
        "ret": ret, "bench_ret": bret, "excess": ret - bret, "mae": mae, "mfe": mfe,
    }, columns=cols)


def baseline_series(prices: pd.DataFrame, w: Window) -> tuple[np.ndarray, int]:
    """Return of the same-shaped trade started on EVERY session (index = entry session).

    For a window whose entry/exit anchors differ (pre vs react) the reaction session is
    taken as pre+1, which is how it falls on ordinary days.
    """
    F = _fields(prices)
    ea = w.entry_off + (1 if w.entry_anchor == "react" else 0)
    xa = w.exit_off + (1 if w.exit_anchor == "react" else 0)
    L = xa - ea
    n = len(prices)
    if L < 0 or n <= L:
        return np.array([]), max(L, 0)
    entry = F[w.entry_field][: n - L]
    exit_ = F[w.exit_field][L:]
    return exit_ / entry - 1, L


# ---------------------------------------------------------------- statistics
def wilson_lower(wins: int, n: int, z: float = Z) -> float:
    if n == 0:
        return float("nan")
    p = wins / n
    den = 1 + z * z / n
    centre = p + z * z / (2 * n)
    adj = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (centre - adj) / den


def _clamp(x: float) -> float:
    if x is None or not np.isfinite(x):
        return 0.5
    return float(min(1.0, max(0.0, x)))


def score_arrays(ret: np.ndarray, excess: np.ndarray | None, base_win: float, base_mean: float,
                 direction: int = 1, cost: float = 0.0) -> float:
    """0-100 attractiveness score for taking the trade in `direction` (+1 long, -1 short)."""
    r = np.asarray(ret, float) * direction - cost
    r = r[np.isfinite(r)]
    n = len(r)
    if n < 3:
        return float("nan")
    bw = base_win if direction == 1 else 1 - base_win
    bm = base_mean * direction
    if not np.isfinite(bw):
        bw = 0.5
    if not np.isfinite(bm):
        bm = 0.0
    wins = int((r > 0).sum())
    wr = wins / n
    sd = r.std(ddof=1) if n > 1 else np.nan
    # every component maps "no edge" to 0.5 and a strong edge to 1.0
    # 1. win rate, shrunk toward 50% (10 pseudo-observations) for small samples
    c1 = _clamp(((wins + 5) / (n + 10) - 0.30) / 0.40)
    # 2. win rate edge versus the stock's normal behaviour over the same holding period
    c2 = _clamp(0.5 + (wr - bw) / 0.30)
    # 3. t-stat of excess return (vs SPY if available, else vs baseline drift)
    ex = None
    if excess is not None:
        e = np.asarray(excess, float) * direction - cost
        e = e[np.isfinite(e)]
        if len(e) >= max(3, n // 2):
            ex = e
    if ex is None:
        ex = r - bm
    esd = ex.std(ddof=1) if len(ex) > 1 else np.nan
    t = ex.mean() / (esd / math.sqrt(len(ex))) if esd and esd > 0 else 0.0
    c3 = _clamp(0.5 + t / 4.0)
    # 4. profit factor (log scale: 1 -> 0.5, 3 -> 1.0, 1/3 -> 0)
    gains, losses = r[r > 0].sum(), -r[r < 0].sum()
    pf = gains / losses if losses > 0 else (5.0 if gains > 0 else 1.0)
    c4 = _clamp(0.5 + 0.5 * math.log(max(pf, 1e-6)) / math.log(3.0))
    # 5. recency / consistency (latest 4 & 8 events)
    l4 = (r[-4:] > 0).mean()
    l8 = (r[-8:] > 0).mean()
    c5 = _clamp(0.5 * l4 + 0.5 * l8)
    # 6. reward / risk per trade
    sh = r.mean() / sd if sd and sd > 0 else 0.0
    c6 = _clamp(0.5 + sh / 0.6)
    raw = 0.25 * c1 + 0.15 * c2 + 0.20 * c3 + 0.15 * c4 + 0.15 * c5 + 0.10 * c6
    shrink = math.sqrt(min(1.0, n / SCORE_SMALL_N))
    return 100.0 * (0.5 + (raw - 0.5) * shrink)


def rating_for(score: float, short_score: float, n: int, min_obs: int) -> str:
    if n < min_obs or not np.isfinite(score):
        return "Low Data"
    if score >= 75:
        return "Strong Buy"
    if score >= 62:
        return "Buy"
    if np.isfinite(short_score) and short_score >= 62:
        return "Avoid (Bearish)"
    if score >= 40:
        return "Neutral"
    return "Avoid"


RATING_ORDER = {"Strong Buy": 5, "Buy": 4, "Neutral": 3, "Avoid": 2, "Avoid (Bearish)": 1, "Low Data": 0}


def compute_stats(wr_df: pd.DataFrame, base_win: float, base_mean: float, cost: float = 0.0,
                  min_obs: int = 8) -> dict:
    r = wr_df["ret"].values.astype(float)
    n = len(r)
    out = {"n": n}
    if n == 0:
        return out
    from scipy import stats as sst
    ex = wr_df["excess"].values.astype(float)
    wins = int((r > 0).sum())
    sd = r.std(ddof=1) if n > 1 else np.nan
    out.update({
        "win_rate": wins / n,
        "avg": r.mean(),
        "median": float(np.median(r)),
        "best": r.max(),
        "worst": r.min(),
        "abs_avg": np.abs(r).mean(),
        "abs_low": np.abs(r).min(),
        "abs_high": np.abs(r).max(),
        "std": sd,
        "sharpe": r.mean() / sd if sd and sd > 0 else np.nan,
        "wilson_lb": wilson_lower(wins, n),
        "avg_win": r[r > 0].mean() if wins else np.nan,
        "avg_loss": r[r < 0].mean() if (r < 0).any() else np.nan,
        "avg_mae": wr_df["mae"].mean(),
        "worst_mae": wr_df["mae"].min(),
        "base_win": base_win,
        "base_mean": base_mean,
        "win_edge": wins / n - base_win if np.isfinite(base_win) else np.nan,
        "avg_edge": r.mean() - base_mean if np.isfinite(base_mean) else np.nan,
        "last4": (r[-4:] > 0).mean(),
        "last_ret": r[-1],
    })
    gains, losses = r[r > 0].sum(), -r[r < 0].sum()
    out["profit_factor"] = gains / losses if losses > 0 else np.inf if gains > 0 else np.nan
    exf = ex[np.isfinite(ex)]
    out["avg_excess"] = exf.mean() if len(exf) else np.nan
    out["beat_bench"] = (exf > 0).mean() if len(exf) else np.nan
    # one-sided test: is the mean return above the stock's normal drift?
    d = r - (base_mean if np.isfinite(base_mean) else 0.0)
    if n > 2 and d.std(ddof=1) > 0:
        t = d.mean() / (d.std(ddof=1) / math.sqrt(n))
        out["t_stat"] = t
        out["p_value"] = float(sst.t.sf(t, n - 1))
    else:
        out["t_stat"], out["p_value"] = np.nan, np.nan
    out["score"] = score_arrays(r, ex, base_win, base_mean, 1, cost)
    out["short_score"] = score_arrays(r, ex, base_win, base_mean, -1, cost)
    out["rating"] = rating_for(out["score"], out["short_score"], n, min_obs)
    return out


def bh_qvalues(p: pd.Series) -> pd.Series:
    """Benjamini-Hochberg false-discovery-rate adjusted p-values."""
    s = p.dropna()
    if s.empty:
        return pd.Series(np.nan, index=p.index)
    order = s.sort_values()
    m = len(order)
    q = order.values * m / np.arange(1, m + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    out = pd.Series(np.nan, index=p.index)
    out.loc[order.index] = np.minimum(q, 1.0)
    return out


# ------------------------------------------------------------ upcoming dates
def majority_timing(events: pd.DataFrame) -> str:
    if events is None or events.empty:
        return "UNK"
    t = events["timing_used"].tail(8)
    t = t[t.isin(["BMO", "AMC"])]
    return t.mode().iloc[0] if len(t) else "UNK"


def next_anchor_dates(next_earn: dt.date, timing: str) -> tuple[dt.date, dt.date]:
    """(pre-earnings session, reaction session) for an upcoming report."""
    if timing == "BMO":
        react = next_earn if is_trading_day(next_earn) else add_trading_days(next_earn, 1)
        pre = add_trading_days(react, -1)
    else:  # AMC or unknown (assume after close, the most common case)
        pre = next_earn if is_trading_day(next_earn) else add_trading_days(next_earn, -1)
        react = add_trading_days(pre, 1)
    return pre, react


def planned_dates(w: Window, pre: dt.date, react: dt.date) -> tuple[dt.date, dt.date]:
    a = pre if w.entry_anchor == "pre" else react
    b = pre if w.exit_anchor == "pre" else react
    return add_trading_days(a, w.entry_off), add_trading_days(b, w.exit_off)


# ------------------------------------------------------------- per ticker
def average_path(prices: pd.DataFrame, events: pd.DataFrame, before: int = 20, after: int = 10) -> pd.DataFrame:
    """Close relative to the pre-earnings close for each event, sessions -before..+after."""
    if events is None or events.empty:
        return pd.DataFrame()
    C = prices["Close"].values
    n = len(C)
    offs = np.arange(-before, after + 1)
    rows = {}
    for r in events.itertuples():
        idx = r.pre_i + offs
        vals = np.full(len(offs), np.nan)
        ok = (idx >= 0) & (idx < n)
        vals[ok] = C[idx[ok]] / C[r.pre_i] - 1
        rows[r.date] = vals
    return pd.DataFrame(rows, index=offs)


def analyze_ticker(td: TickerData, windows: list[Window], bench: pd.DataFrame | None,
                   years: float = 10, cost: float = 0.001, min_obs: int = 8,
                   today: dt.date | None = None) -> dict:
    today = today or dt.date.today()
    prices = td.prices
    events = align_events(prices, td.earnings, years, today)
    meta = td.meta or {}
    timing_next = meta.get("next_timing") if meta.get("next_timing") in ("BMO", "AMC") else majority_timing(events)
    nxt = None
    if meta.get("next_earnings"):
        try:
            nxt = dt.date.fromisoformat(str(meta["next_earnings"])[:10])
        except ValueError:
            nxt = None
    pre_d = react_d = None
    if nxt and nxt >= today:
        pre_d, react_d = next_anchor_dates(nxt, timing_next)

    first_event = events["pre_i"].min() - 25 if len(events) else 0
    rows, per_window, base_store = [], {}, {}
    move_abs = np.nan
    for w in windows:
        wr = window_returns(prices, events, w, bench)
        per_window[w.key] = wr
        base, L = baseline_series(prices, w)
        base_store[w.key] = (base, L)
        seg = base[max(0, int(first_event)):] if len(base) else base
        bwin = float((seg > 0).mean()) if len(seg) else np.nan
        bmean = float(seg.mean()) if len(seg) else np.nan
        st = compute_stats(wr, bwin, bmean, cost, min_obs)
        if w.key == "move" and st.get("n"):
            move_abs = st["abs_avg"]
        row = {"ticker": td.ticker, "window": w.label, "window_key": w.key, "group": w.group,
               "window_order": w.order, **st}
        # upcoming trade plan
        if pre_d:
            ed, xd = planned_dates(w, pre_d, react_d)
            row["entry_date"] = pd.Timestamp(ed)
            row["exit_date"] = pd.Timestamp(xd)
            row["days_to_entry"] = trading_days_between(today, ed)
            row["days_to_exit"] = trading_days_between(today, xd)
        rows.append(row)

    common = {
        "name": meta.get("name", td.ticker), "sector": meta.get("sector", ""),
        "industry": meta.get("industry", ""),
        "market_cap": meta.get("market_cap"), "avg_volume": meta.get("avg_volume"),
        "last_price": meta.get("last_price") or (float(prices["Close"].iloc[-1]) if len(prices) else np.nan),
        "option_volume": meta.get("option_volume"), "implied_move": meta.get("implied_move"),
        "next_earnings": pd.Timestamp(nxt) if nxt else pd.NaT,
        "next_timing": timing_next if nxt else "",
        "confirmed": meta.get("next_confirmed"),
        "days_to_earnings": (nxt - today).days if nxt else np.nan,
        "hist_move": move_abs,
        "events_total": len(events),
        "timing_inferred_pct": float(events["inferred"].mean()) if len(events) else np.nan,
    }
    im = common["implied_move"]
    common["implied_vs_hist"] = (im / move_abs) if (im and np.isfinite(move_abs) and move_abs > 0) else np.nan
    for r in rows:
        r.update(common)
    return {"rows": rows, "events": events, "window_returns": per_window, "baseline": base_store,
            "meta": meta, "common": common}


def build_screen(results: dict[str, dict]) -> pd.DataFrame:
    rows = [r for res in results.values() for r in res["rows"]]
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["q_value"] = bh_qvalues(df["p_value"]) if "p_value" in df else np.nan
    df["rating_rank"] = df["rating"].map(RATING_ORDER).fillna(0)
    return df


def event_table(res: dict) -> pd.DataFrame:
    """Per-event summary used on the stock detail tab."""
    ev = res["events"]
    if ev is None or ev.empty:
        return pd.DataFrame()
    out = ev[["date", "timing_used", "inferred", "eps_est", "eps_act", "surprise"]].copy()
    out = out.rename(columns={"timing_used": "timing"})
    for key, col in [("pre5", "run_up_5d"), ("gap", "gap"), ("oc", "open_to_close"), ("move", "day_move"),
                     ("post5", "drift_5d")]:
        wr = res["window_returns"].get(key)
        if wr is not None and len(wr):
            out = out.merge(wr[["event_date", "ret"]].rename(columns={"event_date": "date", "ret": col}),
                            on="date", how="left")
    return out.sort_values("date", ascending=False).reset_index(drop=True)
