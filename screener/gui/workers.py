"""Background workers so downloads and analysis never freeze the window."""
from __future__ import annotations

import datetime as dt
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

from PySide6.QtCore import QObject, QThread, Signal

from ..backtest import BacktestParams, run_backtest
from ..data_store import DataStore
from ..engine import TickerData, analyze_ticker, build_screen
from ..providers import fetch_ticker
from ..universe import INDEX_BY_KEY, refresh_indexes, resolve_universe


class _Worker(QObject):
    progress = Signal(int, int, str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self):
        super().__init__()
        self._cancel = False

    def cancel(self):
        self._cancel = True


class DownloadWorker(_Worker):
    def __init__(self, store: DataStore, tickers: list[str] | None, settings, force: bool = False):
        super().__init__()
        self.store, self.tickers, self.settings, self.force = store, tickers, settings, force

    def _stale(self, t: str) -> bool:
        if self.force:
            return True
        last = self.store.last_updated(t)
        return last is None or (dt.datetime.now() - last).total_seconds() > self.settings["refresh_hours"] * 3600

    def run(self):
        try:
            bench = self.settings["benchmark"]
            errors: dict[str, str] = {}
            # 1) refresh index constituent lists (cheap; monthly) so universe + Index filter stay current
            self.progress.emit(0, 0, "Updating index lists…")
            for k, e in refresh_indexes(self.settings, max_age_days=30).items():
                errors[f"[{INDEX_BY_KEY[k].short} list]"] = e
            if self.tickers is None:
                self.tickers = resolve_universe(self.settings)
            todo = [t for t in dict.fromkeys([bench] + self.tickers) if self._stale(t)]
            total = len(todo)
            if not total:
                self.finished.emit({"errors": {}, "downloaded": 0})
                return
            years = int(self.settings["years_history"])
            av = self.settings["alpha_vantage_key"]
            opts = bool(self.settings["fetch_options"])
            done = 0
            with ThreadPoolExecutor(max_workers=int(self.settings["max_workers"])) as ex:
                futs = {ex.submit(fetch_ticker, t, years, av, opts and t != bench): t for t in todo}
                for f in as_completed(futs):
                    t = futs[f]
                    done += 1
                    if self._cancel:
                        for g in futs:
                            g.cancel()
                        break
                    try:
                        prices, earnings, meta = f.result()
                        self.store.save_ticker(t, prices, earnings, meta)
                        if t != bench and len(earnings) < 4:
                            errors[t] = f"only {len(earnings)} earnings dates found"
                    except Exception as e:
                        errors[t] = str(e)[:200]
                    self.progress.emit(done, total, f"Downloaded {t}")
            self.finished.emit({"errors": errors, "downloaded": done, "cancelled": self._cancel})
        except Exception:
            self.failed.emit(traceback.format_exc())


class AnalyzeWorker(_Worker):
    def __init__(self, store: DataStore | None, tickers: list[str], windows, settings, demo=None):
        super().__init__()
        self.store, self.tickers, self.windows, self.settings, self.demo = store, tickers, windows, settings, demo

    def run(self):
        try:
            years = float(self.settings["years_history"])
            cost = float(self.settings["cost_bps"]) / 10000
            min_obs = int(self.settings["min_obs_for_rating"])
            results = {}
            if self.demo is not None:
                tds, bench = self.demo
            else:
                bench_t = self.settings["benchmark"]
                bench = self.store.load_prices(bench_t)
                bench = bench if len(bench) else None
                tds = None
            items = tds if tds is not None else self.tickers
            total = len(items)
            for i, it in enumerate(items, 1):
                if self._cancel:
                    break
                try:
                    if isinstance(it, TickerData):
                        td = it
                    else:
                        px = self.store.load_prices(it)
                        if px.empty:
                            continue
                        td = TickerData(it, px, self.store.load_earnings(it), self.store.load_meta(it))
                    if td.earnings is None or len(td.earnings) == 0:
                        continue
                    results[td.ticker] = analyze_ticker(td, self.windows, bench, years, cost, min_obs)
                    results[td.ticker]["prices"] = td.prices
                except Exception as e:
                    print("analyze failed", it, e)
                if i % 5 == 0 or i == total:
                    self.progress.emit(i, total, f"Analyzing {getattr(it, 'ticker', it)}")
            screen = build_screen(results)
            self.finished.emit({"results": results, "screen": screen, "bench": bench})
        except Exception:
            self.failed.emit(traceback.format_exc())


class BacktestWorker(_Worker):
    def __init__(self, results, params: BacktestParams):
        super().__init__()
        self.results, self.params = results, params

    def run(self):
        try:
            self.finished.emit(run_backtest(self.results, self.params))
        except Exception:
            self.failed.emit(traceback.format_exc())


def start(worker: _Worker, on_done, on_progress=None, on_fail=None) -> QThread:
    th = QThread()
    worker.moveToThread(th)
    th.started.connect(worker.run)
    worker.finished.connect(on_done)
    if on_progress:
        worker.progress.connect(on_progress)
    if on_fail:
        worker.failed.connect(on_fail)
    worker.finished.connect(th.quit)
    worker.failed.connect(th.quit)
    th.finished.connect(th.deleteLater)
    th._worker = worker  # keep a reference alive
    th.start()
    return th
