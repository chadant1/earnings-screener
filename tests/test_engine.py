import datetime as dt

import numpy as np
import pandas as pd

from screener.backtest import BacktestParams, run_backtest
from screener.demo_data import make_demo
from screener.engine import (align_events, analyze_ticker, bh_qvalues, build_screen, next_anchor_dates,
                             wilson_lower)
from screener.market_calendar import add_trading_days, is_trading_day, nyse_holidays, trading_days_between
from screener.windows import DEFAULT_WINDOWS, Window


def _px(dates, close, open_=None):
    close = np.asarray(close, float)
    open_ = close if open_ is None else np.asarray(open_, float)
    return pd.DataFrame({"Open": open_, "High": np.maximum(open_, close), "Low": np.minimum(open_, close),
                         "Close": close, "Volume": 1.0}, index=pd.DatetimeIndex(dates))


def test_calendar():
    assert dt.date(2026, 11, 26) in nyse_holidays(2026)       # Thanksgiving
    assert dt.date(2026, 4, 3) in nyse_holidays(2026)         # Good Friday
    assert not is_trading_day(dt.date(2026, 11, 26))
    assert add_trading_days(dt.date(2026, 11, 25), 1) == dt.date(2026, 11, 27)
    assert add_trading_days(dt.date(2026, 11, 30), -1) == dt.date(2026, 11, 27)
    assert add_trading_days(dt.date(2026, 11, 28), -1) == dt.date(2026, 11, 27)  # from a Saturday
    assert trading_days_between(dt.date(2026, 11, 23), dt.date(2026, 11, 30)) == 4


def test_alignment_bmo_amc_and_inference():
    dates = pd.bdate_range("2024-01-01", periods=10)
    o = [10] * 10
    c = [10] * 10
    o[5] = 12  # big gap on day 5 open
    px = _px(dates, c, o)
    d4, d5 = dates[4], dates[5]
    earn = pd.DataFrame({"date": [d5, d4, d4], "timing": ["BMO", "AMC", "UNK"],
                         "eps_est": np.nan, "eps_act": np.nan, "surprise": np.nan})
    for i, row in earn.iterrows():
        ev = align_events(px, earn.iloc[[i]], None, dt.date(2024, 2, 1))
        assert ev.loc[0, "react_i"] == 5 and ev.loc[0, "pre_i"] == 4, row.to_dict()
    ev = align_events(px, earn.iloc[[2]], None, dt.date(2024, 2, 1))
    assert bool(ev.loc[0, "inferred"])


def test_wilson_and_bh():
    assert 0.4 < wilson_lower(8, 10) < 0.8
    q = bh_qvalues(pd.Series([0.01, 0.04, 0.03, 0.5]))
    assert (q >= pd.Series([0.01, 0.04, 0.03, 0.5])).all()


def test_planted_pattern_is_found():
    tds, spy = make_demo(n_tickers=12, seed=3)
    res = {td.ticker: analyze_ticker(td, DEFAULT_WINDOWS, spy, years=10) for td in tds}
    df = build_screen(res)
    pre5 = df[df.window_key == "pre5"].set_index("ticker")
    planted = pre5.loc[[f"DEMO{k:02d}" for k in range(6)], "score"]
    neutral = pre5.loc[[f"DEMO{k:02d}" for k in range(9, 12)], "score"]
    bearish = pre5.loc[[f"DEMO{k:02d}" for k in range(6, 9)], "short_score"]
    assert planted.min() > neutral.max(), (planted, neutral)
    assert pre5.loc[planted.index, "rating"].isin(["Buy", "Strong Buy"]).sum() >= 5
    assert (bearish > 62).all()
    assert pre5["n"].min() >= 30


def test_upcoming_dates():
    pre, react = next_anchor_dates(dt.date(2026, 11, 25), "AMC")
    assert pre == dt.date(2026, 11, 25) and react == dt.date(2026, 11, 27)
    pre, react = next_anchor_dates(dt.date(2026, 11, 30), "BMO")
    assert pre == dt.date(2026, 11, 27) and react == dt.date(2026, 11, 30)


def test_walk_forward():
    tds, spy = make_demo(n_tickers=12, seed=3)
    res = {td.ticker: analyze_ticker(td, DEFAULT_WINDOWS, spy, years=10) for td in tds}
    bt = run_backtest(res, BacktestParams(window_keys=["pre5"], min_prior=8, min_score=62))
    s, a = bt["summary_selected"], bt["summary_all"]
    assert s["trades"] > 50
    assert s["avg"] > a["avg"]


def test_trading_days_between_past():
    assert trading_days_between(dt.date(2026, 11, 22), dt.date(2026, 11, 20)) == -1  # Sun -> prior Fri
    assert trading_days_between(dt.date(2026, 11, 22), dt.date(2026, 11, 23)) == 0   # next session
    assert trading_days_between(dt.date(2026, 11, 23), dt.date(2026, 11, 20)) == -1
