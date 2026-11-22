"""Local SQLite cache so the app works offline and only refreshes stale tickers."""
from __future__ import annotations

import datetime as dt
import json
import sqlite3
import threading
from pathlib import Path

import pandas as pd

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS prices (
    ticker TEXT NOT NULL, date TEXT NOT NULL,
    open REAL, high REAL, low REAL, close REAL, volume REAL,
    PRIMARY KEY (ticker, date)
);
CREATE TABLE IF NOT EXISTS earnings (
    ticker TEXT NOT NULL, date TEXT NOT NULL,
    timing TEXT,            -- BMO / AMC / UNK
    eps_est REAL, eps_act REAL, surprise REAL,
    PRIMARY KEY (ticker, date)
);
CREATE TABLE IF NOT EXISTS meta (
    ticker TEXT PRIMARY KEY,
    data TEXT,              -- JSON blob
    updated_at TEXT
);
"""


class DataStore:
    def __init__(self, path: Path | str = DB_PATH):
        self.path = str(path)
        self._lock = threading.Lock()
        with self._conn() as c:
            c.executescript(SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path, timeout=30)
        c.execute("PRAGMA journal_mode=WAL")
        return c

    # ---------------------------------------------------------------- writes
    def save_ticker(self, ticker: str, prices: pd.DataFrame | None,
                    earnings: pd.DataFrame | None, meta: dict) -> None:
        with self._lock, self._conn() as c:
            if prices is not None and len(prices):
                c.execute("DELETE FROM prices WHERE ticker=?", (ticker,))
                rows = [(ticker, d.strftime("%Y-%m-%d"), float(r.Open), float(r.High), float(r.Low),
                         float(r.Close), float(r.Volume))
                        for d, r in prices.iterrows()]
                c.executemany("INSERT OR REPLACE INTO prices VALUES (?,?,?,?,?,?,?)", rows)
            if earnings is not None and len(earnings):
                c.execute("DELETE FROM earnings WHERE ticker=?", (ticker,))
                rows = [(ticker, pd.Timestamp(r.date).strftime("%Y-%m-%d"), r.timing,
                         _f(r.eps_est), _f(r.eps_act), _f(r.surprise))
                        for r in earnings.itertuples()]
                c.executemany("INSERT OR REPLACE INTO earnings VALUES (?,?,?,?,?,?)", rows)
            meta = dict(meta)
            c.execute("INSERT OR REPLACE INTO meta VALUES (?,?,?)",
                      (ticker, json.dumps(meta, default=str), dt.datetime.now().isoformat(timespec="seconds")))

    # ----------------------------------------------------------------- reads
    def tickers(self) -> list[str]:
        with self._conn() as c:
            return [r[0] for r in c.execute("SELECT ticker FROM meta ORDER BY ticker")]

    def last_updated(self, ticker: str) -> dt.datetime | None:
        with self._conn() as c:
            r = c.execute("SELECT updated_at FROM meta WHERE ticker=?", (ticker,)).fetchone()
        return dt.datetime.fromisoformat(r[0]) if r and r[0] else None

    def load_prices(self, ticker: str) -> pd.DataFrame:
        with self._conn() as c:
            df = pd.read_sql("SELECT date, open, high, low, close, volume FROM prices WHERE ticker=? ORDER BY date",
                             c, params=(ticker,))
        df["date"] = pd.to_datetime(df["date"])
        return df.set_index("date").rename(columns=str.capitalize)

    def load_earnings(self, ticker: str) -> pd.DataFrame:
        with self._conn() as c:
            df = pd.read_sql("SELECT date, timing, eps_est, eps_act, surprise FROM earnings WHERE ticker=? ORDER BY date",
                             c, params=(ticker,))
        df["date"] = pd.to_datetime(df["date"])
        return df

    def load_meta(self, ticker: str) -> dict:
        with self._conn() as c:
            r = c.execute("SELECT data FROM meta WHERE ticker=?", (ticker,)).fetchone()
        return json.loads(r[0]) if r else {}

    def load_all_meta(self) -> dict[str, dict]:
        with self._conn() as c:
            return {t: json.loads(d) for t, d in c.execute("SELECT ticker, data FROM meta")}

    def delete_ticker(self, ticker: str) -> None:
        with self._lock, self._conn() as c:
            for tbl in ("prices", "earnings", "meta"):
                c.execute(f"DELETE FROM {tbl} WHERE ticker=?", (ticker,))


def _f(x):
    try:
        x = float(x)
        return None if pd.isna(x) else x
    except (TypeError, ValueError):
        return None
