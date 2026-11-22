"""Synthetic market data for testing / offline demo (python main.py --demo).

Some tickers get a planted pre-earnings run-up so you can verify the screener finds it.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from .engine import TickerData
from .market_calendar import add_trading_days, is_trading_day

SECTORS = ["Technology", "Healthcare", "Financial Services", "Consumer Cyclical", "Energy", "Industrials"]


def _trading_days(start: dt.date, end: dt.date) -> pd.DatetimeIndex:
    days = pd.bdate_range(start, end)
    return pd.DatetimeIndex([d for d in days if is_trading_day(d.date())])


def _ohlc(close: np.ndarray, gaps: np.ndarray, rng) -> pd.DataFrame:
    prev = np.concatenate([[close[0]], close[:-1]])
    open_ = prev * (1 + gaps)
    hi = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.006, len(close))))
    lo = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.006, len(close))))
    vol = rng.integers(1_000_000, 20_000_000, len(close)).astype(float)
    return pd.DataFrame({"Open": open_, "High": hi, "Low": lo, "Close": close, "Volume": vol})


def demo_memberships(n_tickers: int = 40) -> dict[str, list[str]]:
    """Fake index membership so the Index filter can be tried in demo mode."""
    out = {}
    for k in range(n_tickers):
        m = []
        if k < 20:
            m.append("S&P 500")
        if k % 3 == 0:
            m.append("Nasdaq-100")
        if k < 5:
            m.append("Dow 30")
        if 20 <= k < 30:
            m.append("S&P 400")
        if k < 30:
            m.append("Russell 1000")
        if k >= 30:
            m += ["S&P 600", "Russell 2000"]
        out[f"DEMO{k:02d}"] = m
    return out


def make_demo(n_tickers: int = 30, years: int = 11, seed: int = 7, today: dt.date | None = None):
    rng = np.random.default_rng(seed)
    today = today or dt.date.today()
    idx = _trading_days(today - dt.timedelta(days=int(365.25 * years)), today - dt.timedelta(days=1))
    n = len(idx)
    # benchmark
    spy_r = rng.normal(0.0004, 0.011, n)
    spy_close = 300 * np.cumprod(1 + spy_r)
    spy = _ohlc(spy_close, rng.normal(0, 0.003, n), rng)
    spy.index = idx

    out = []
    for k in range(n_tickers):
        tkr = f"DEMO{k:02d}"
        beta = rng.uniform(0.7, 1.5)
        idio = rng.normal(0.0002, 0.016, n)
        r = beta * spy_r + idio
        gaps = rng.normal(0, 0.004, n)
        timing = "BMO" if k % 3 == 0 else "AMC"
        # quarterly reports ~ every 63 sessions with jitter
        start = int(rng.integers(20, 63))
        rep_idx = []
        i = start
        while i < n - 2:
            rep_idx.append(i)
            i += 63 + int(rng.integers(-3, 4))
        runup = 0.007 if k < 6 else (-0.006 if 6 <= k < 9 else 0.0)  # planted patterns
        dates, timings = [], []
        for ri in rep_idx:
            react = ri if timing == "BMO" else ri + 1
            if react >= n:
                continue
            if runup:
                r[max(0, react - 6): react - 1] += runup        # drift into the pre session
            g = rng.normal(0.004, 0.06)
            gaps[react] += g
            r[react] += g + rng.normal(0, 0.02)
            dates.append(idx[ri])
            timings.append(timing if k % 5 else "UNK")           # some unknown timings to infer
        close = 50 * np.cumprod(1 + r)
        px = _ohlc(close, gaps, rng)
        px.index = idx
        earn = pd.DataFrame({"date": dates, "timing": timings,
                             "eps_est": rng.normal(1, 0.2, len(dates)),
                             "eps_act": rng.normal(1.05, 0.25, len(dates))})
        earn["surprise"] = (earn["eps_act"] / earn["eps_est"] - 1) * 100
        nxt = add_trading_days(today, int(rng.integers(2, 45)))
        meta = {
            "ticker": tkr, "name": f"Demo Company {k:02d}", "sector": SECTORS[k % len(SECTORS)],
            "industry": "Demo", "market_cap": float(10 ** rng.uniform(9, 12.3)),
            "avg_volume": float(rng.integers(1, 40) * 1e6), "last_price": float(close[-1]),
            "next_earnings": nxt.isoformat(), "next_confirmed": bool(rng.random() > 0.3),
            "next_timing": timing, "option_volume": float(rng.integers(1, 200) * 1000),
            "implied_move": float(abs(rng.normal(0.06, 0.02))),
            "exchange": "Nasdaq" if k % 3 == 0 else "NYSE",
        }
        out.append(TickerData(tkr, px, earn, meta))
    return out, spy
