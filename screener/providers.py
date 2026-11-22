"""Market data download.

Primary source: Yahoo Finance via `yfinance` (free, no key).
Optional fallback for earnings dates: Alpha Vantage (free key at alphavantage.co).
"""
from __future__ import annotations

import datetime as dt
import logging
import time

import numpy as np
import pandas as pd
import requests

log = logging.getLogger(__name__)

EARN_COLS = ["date", "timing", "eps_est", "eps_act", "surprise"]


def _retry(fn, tries: int = 3, wait: float = 2.0):
    last = None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:  # network hiccups / Yahoo rate limiting
            last = e
            time.sleep(wait * (i + 1))
    raise last


def _timing_from_hour(ts: pd.Timestamp) -> str:
    """Yahoo stamps the call time (New York). 00:00 means 'time not supplied'."""
    h, m = ts.hour, ts.minute
    if h == 0 and m == 0:
        return "UNK"
    if h < 10 or (h == 9 and m < 30):
        return "BMO"
    if h >= 16:
        return "AMC"
    if h >= 13:
        return "AMC"   # rare afternoon calls usually react the next session
    return "BMO"       # mid-morning call: reaction is that same session


def normalize_prices(hist: pd.DataFrame) -> pd.DataFrame:
    if hist is None or hist.empty:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    df = hist[["Open", "High", "Low", "Close", "Volume"]].copy()
    idx = pd.DatetimeIndex(df.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    df.index = idx.normalize()
    df = df[~df.index.duplicated(keep="last")].dropna(subset=["Open", "Close"])
    df = df[(df["Open"] > 0) & (df["Close"] > 0)]
    return df.sort_index()


# ------------------------------------------------------------------ yfinance
def yf_earnings(tk, years: int) -> pd.DataFrame:
    limit = int(min(100, max(12, years * 4 + 8)))
    df = _retry(lambda: tk.get_earnings_dates(limit=limit))
    if df is None or df.empty:
        return pd.DataFrame(columns=EARN_COLS)
    df = df.copy()
    idx = pd.DatetimeIndex(df.index)
    if idx.tz is not None:
        idx = idx.tz_convert("America/New_York")
    out = pd.DataFrame({
        "date": idx.tz_localize(None).normalize() if idx.tz is not None else idx.normalize(),
        "timing": [_timing_from_hour(t) for t in idx],
        "eps_est": pd.to_numeric(df.get("EPS Estimate"), errors="coerce").values,
        "eps_act": pd.to_numeric(df.get("Reported EPS"), errors="coerce").values,
        "surprise": pd.to_numeric(df.get("Surprise(%)"), errors="coerce").values,
    })
    if "Event Type" in df.columns:  # drop shareholder meetings etc. if present
        out = out[df["Event Type"].astype(str).str.contains("Earnings", case=False).values]
    out = out.drop_duplicates("date").sort_values("date").reset_index(drop=True)
    return out


def alpha_vantage_earnings(symbol: str, key: str) -> pd.DataFrame:
    r = requests.get("https://www.alphavantage.co/query",
                     params={"function": "EARNINGS", "symbol": symbol, "apikey": key}, timeout=20)
    js = r.json()
    rows = js.get("quarterlyEarnings") or []
    if not rows:
        raise RuntimeError(js.get("Note") or js.get("Information") or "no Alpha Vantage data")
    recs = []
    for q in rows:
        t = str(q.get("reportTime", "")).lower()
        timing = "BMO" if "pre" in t else "AMC" if "post" in t else "UNK"
        recs.append({
            "date": pd.Timestamp(q["reportedDate"]),
            "timing": timing,
            "eps_est": pd.to_numeric(q.get("estimatedEPS"), errors="coerce"),
            "eps_act": pd.to_numeric(q.get("reportedEPS"), errors="coerce"),
            "surprise": pd.to_numeric(q.get("surprisePercentage"), errors="coerce"),
        })
    return pd.DataFrame(recs).drop_duplicates("date").sort_values("date").reset_index(drop=True)


def _options_snapshot(tk, spot: float, next_earn: dt.date | None) -> dict:
    """Total option volume (nearest expiry) and the ATM-straddle implied earnings move."""
    out = {"option_volume": None, "implied_move": None}
    exps = list(tk.options or [])
    if not exps:
        return out
    ch = tk.option_chain(exps[0])
    out["option_volume"] = float(np.nansum(ch.calls["volume"]) + np.nansum(ch.puts["volume"]))
    if next_earn and spot:
        after = [e for e in exps if dt.date.fromisoformat(e) >= next_earn]
        if after:
            ch2 = ch if after[0] == exps[0] else tk.option_chain(after[0])
            c, p = ch2.calls, ch2.puts
            strike = c.loc[(c["strike"] - spot).abs().idxmin(), "strike"]

            def mid(df):
                row = df[df["strike"] == strike]
                if row.empty:
                    return np.nan
                b, a, last = row["bid"].iloc[0], row["ask"].iloc[0], row["lastPrice"].iloc[0]
                return (b + a) / 2 if (b > 0 and a > 0) else last
            straddle = mid(c) + mid(p)
            if np.isfinite(straddle) and straddle > 0:
                out["implied_move"] = float(straddle / spot)
    return out


def fetch_ticker(symbol: str, years: int = 10, av_key: str = "", fetch_options: bool = False):
    """Download prices, earnings history and metadata for one ticker.

    Returns (prices_df, earnings_df, meta_dict).  Raises on hard failure.
    """
    import yfinance as yf

    tk = yf.Ticker(symbol)
    hist = _retry(lambda: tk.history(period=f"{years + 1}y", auto_adjust=True, actions=False))
    prices = normalize_prices(hist)
    if prices.empty:
        raise RuntimeError("no price data")

    meta: dict = {"ticker": symbol, "errors": []}
    earnings = pd.DataFrame(columns=EARN_COLS)
    try:
        earnings = yf_earnings(tk, years)
    except Exception as e:
        meta["errors"].append(f"yahoo earnings: {e}")
    if (earnings.empty or len(earnings) < 4) and av_key:
        try:
            earnings = alpha_vantage_earnings(symbol, av_key)
            meta["earnings_source"] = "alphavantage"
        except Exception as e:
            meta["errors"].append(f"alphavantage: {e}")
    meta.setdefault("earnings_source", "yahoo")

    # ---- metadata
    try:
        fi = tk.fast_info
        meta["market_cap"] = _num(fi.get("marketCap"))
        meta["avg_volume"] = _num(fi.get("threeMonthAverageVolume"))
        meta["last_price"] = _num(fi.get("lastPrice"))
    except Exception as e:
        meta["errors"].append(f"fast_info: {e}")
    try:
        info = tk.info or {}
        meta["name"] = info.get("shortName") or info.get("longName") or symbol
        meta["sector"] = info.get("sector") or ""
        meta["industry"] = info.get("industry") or ""
        meta.setdefault("market_cap", _num(info.get("marketCap")))
        if not meta.get("market_cap"):
            meta["market_cap"] = _num(info.get("marketCap"))
    except Exception as e:
        meta["errors"].append(f"info: {e}")
        meta.setdefault("name", symbol)

    # ---- next earnings date (+ "confirmed" heuristic: Yahoo gives a 2-date range when estimated)
    today = pd.Timestamp(dt.date.today())
    nxt, confirmed = None, None
    try:
        cal = tk.calendar or {}
        ed = cal.get("Earnings Date") or []
        ed = [pd.Timestamp(d) for d in ed if d is not None]
        if ed:
            nxt = min(ed)
            confirmed = len(ed) == 1
    except Exception as e:
        meta["errors"].append(f"calendar: {e}")
    fut = earnings[earnings["date"] >= today] if len(earnings) else earnings
    if len(fut):
        cand = fut["date"].min()
        if nxt is None or abs((cand - nxt).days) <= 3:
            nxt = cand
            meta["next_timing"] = fut.loc[fut["date"].idxmin(), "timing"]
    if nxt is not None and nxt >= today:
        meta["next_earnings"] = nxt.strftime("%Y-%m-%d")
        meta["next_confirmed"] = confirmed

    if fetch_options:
        try:
            ne = dt.date.fromisoformat(meta["next_earnings"]) if meta.get("next_earnings") else None
            meta.update(_options_snapshot(tk, float(prices["Close"].iloc[-1]), ne))
        except Exception as e:
            meta["errors"].append(f"options: {e}")

    # only keep events that already happened for the history table (future row is in meta)
    if len(earnings):
        earnings = earnings[earnings["date"] < today].reset_index(drop=True)
    return prices, earnings, meta


def _num(x):
    try:
        x = float(x)
        return None if not np.isfinite(x) else x
    except (TypeError, ValueError):
        return None
