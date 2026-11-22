"""Application paths and persistent user settings (watchlist, saved filters, API keys...)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

APP_NAME = "EarningsScreener"
APP_VERSION = "1.0.0"


def app_data_dir() -> Path:
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    d = base / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


DB_PATH = app_data_dir() / "cache.sqlite"
SETTINGS_PATH = app_data_dir() / "settings.json"

DEFAULT_SETTINGS: dict[str, Any] = {
    "years_history": 10,          # years of earnings events to analyse
    "universe": "default",        # default | sp500 | custom
    "custom_tickers": [],
    "watchlist": [],
    "saved_filters": {},          # name -> filter-state dict
    "custom_windows": [],         # list of window dicts (see windows.py)
    "alpha_vantage_key": "",      # optional fallback for earnings dates
    "fetch_options": False,       # option volume + implied move (slower)
    "refresh_hours": 12,          # cached data older than this is re-downloaded
    "benchmark": "SPY",
    "opportunity_days": 10,       # "act within N trading days" horizon
    "min_obs_for_rating": 8,
    "max_workers": 4,
    "cost_bps": 10,               # round-trip trading cost assumed in scores & backtests
    "hidden_columns": [],
}


class Settings:
    def __init__(self, path: Path = SETTINGS_PATH):
        self.path = path
        self.data: dict[str, Any] = dict(DEFAULT_SETTINGS)
        self.load()

    def load(self) -> None:
        if self.path.exists():
            try:
                stored = json.loads(self.path.read_text(encoding="utf-8"))
                self.data.update(stored)
            except Exception:
                pass

    def save(self) -> None:
        try:
            self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def __getitem__(self, key: str) -> Any:
        return self.data.get(key, DEFAULT_SETTINGS.get(key))

    def __setitem__(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.save()

    # watchlist helpers
    def toggle_watch(self, ticker: str) -> bool:
        wl = list(self["watchlist"])
        if ticker in wl:
            wl.remove(ticker)
            on = False
        else:
            wl.append(ticker)
            on = True
        self["watchlist"] = sorted(wl)
        return on
