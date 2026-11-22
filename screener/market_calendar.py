"""NYSE trading-day calendar (no external dependency).

Used to project *future* entry dates ("buy 5 trading days before earnings").
Historical analysis uses the actual trading days present in the price data.
"""
from __future__ import annotations

import datetime as dt
from functools import lru_cache

import numpy as np


def _easter(year: int) -> dt.date:
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return dt.date(year, month, day)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> dt.date:
    d = dt.date(year, month, 1)
    d += dt.timedelta(days=(weekday - d.weekday()) % 7)
    return d + dt.timedelta(weeks=n - 1)


def _last_weekday(year: int, month: int, weekday: int) -> dt.date:
    d = dt.date(year + (month == 12), month % 12 + 1, 1) - dt.timedelta(days=1)
    return d - dt.timedelta(days=(d.weekday() - weekday) % 7)


def _observed(d: dt.date) -> dt.date:
    if d.weekday() == 5:
        return d - dt.timedelta(days=1)
    if d.weekday() == 6:
        return d + dt.timedelta(days=1)
    return d


@lru_cache(maxsize=None)
def nyse_holidays(year: int) -> frozenset:
    h = {
        _nth_weekday(year, 1, 0, 3),               # MLK day
        _nth_weekday(year, 2, 0, 3),               # Presidents day
        _easter(year) - dt.timedelta(days=2),      # Good Friday
        _last_weekday(year, 5, 0),                 # Memorial day
        _observed(dt.date(year, 7, 4)),
        _nth_weekday(year, 9, 0, 1),               # Labor day
        _nth_weekday(year, 11, 3, 4),              # Thanksgiving
        _observed(dt.date(year, 12, 25)),
    }
    ny = dt.date(year, 1, 1)
    if ny.weekday() != 5:                          # NYSE does not observe on prior Friday
        h.add(_observed(ny))
    if year >= 2022:
        h.add(_observed(dt.date(year, 6, 19)))     # Juneteenth
    return frozenset(h)


def _holiday_array(start_year: int, end_year: int) -> np.ndarray:
    days = []
    for y in range(start_year, end_year + 1):
        days.extend(nyse_holidays(y))
    return np.array(sorted(days), dtype="datetime64[D]")


def is_trading_day(d: dt.date) -> bool:
    return d.weekday() < 5 and d not in nyse_holidays(d.year)


def add_trading_days(d: dt.date, n: int) -> dt.date:
    """Move n trading days from d (n may be negative). d itself need not be a trading day."""
    hol = _holiday_array(d.year - 2, d.year + 2)
    roll = "forward" if n > 0 else "backward"
    if n == 0:
        return d if is_trading_day(d) else np.busday_offset(d, 0, roll="backward", holidays=hol).astype(dt.date)
    # busday_offset with roll first moves d onto a business day; adjust so that
    # offset is counted from d itself
    base = np.datetime64(d, "D")
    if not is_trading_day(d):
        base = np.busday_offset(base, 0, roll=("backward" if n > 0 else "forward"), holidays=hol)
    return np.busday_offset(base, n, roll=roll, holidays=hol).astype(dt.date)


def trading_days_between(a: dt.date, b: dt.date) -> int:
    """Number of trading days from a to b (b exclusive), negative if b < a."""
    hol = _holiday_array(min(a.year, b.year) - 1, max(a.year, b.year) + 1)
    if b >= a:
        return int(np.busday_count(np.datetime64(a, "D"), np.datetime64(b, "D"), holidays=hol))
    # b in the past: minus the number of sessions in [b, a)
    return -int(np.busday_count(np.datetime64(b, "D"), np.datetime64(a, "D"), holidays=hol))
