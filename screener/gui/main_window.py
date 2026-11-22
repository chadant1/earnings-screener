"""Main application window."""
from __future__ import annotations

import sys

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel, QMainWindow,
                               QMenu, QMessageBox, QProgressBar, QSizePolicy, QSpinBox, QStatusBar, QTabWidget,
                               QToolBar, QVBoxLayout, QWidget)

from ..config import APP_NAME, APP_VERSION, Settings
from ..data_store import DataStore
from ..windows import all_windows
from . import workers
from .backtest_tab import BacktestTab
from .columns import C, OPPORTUNITY_COLS, SCREENER_COLS
from .detail_tab import DetailTab, make_table
from .dialogs import CustomWindowsDialog, SettingsDialog, UniverseDialog, resolve_universe
from .filters import FilterPanel
from . import themes
from .table_model import DataFrameModel

HELP_TEXT = """
<h3>How the screener works</h3>
<p><b>Events.</b> For every past earnings report the app finds the <i>pre-earnings session</i> (last close before
the news) and the <i>reaction session</i> (first session trading on the news), using the report time
(before open / after close). Missing times are inferred from which session gapped.</p>
<p><b>Timeframes.</b> Each timeframe is a buy/sell rule around those sessions, e.g. <i>1 Week Before</i> = buy at the
close 5 sessions before the pre-earnings session and sell at the pre-earnings close (you are out before the report).
<i>Hold Through</i> timeframes keep the position through the report. You can add your own under Custom Timeframes.</p>
<p><b>Beyond win rate.</b> Each pattern is compared with the stock's <i>normal</i> behaviour over the same holding
length on any day, and with SPY over the exact same dates. Small samples are penalised (Wilson lower bound and
shrinkage), and q-values estimate the chance a pattern is just luck after screening thousands of combinations.</p>
<p><b>Score (0-100).</b> 50 means no edge. It blends: shrunk win rate (25%), win edge vs normal (15%),
excess-return t-stat vs SPY (20%), profit factor (15%), recent consistency (15%) and reward/risk (10%), net of your
trading-cost setting. <b>Strong Buy</b> ≥ 75, <b>Buy</b> ≥ 62, <b>Neutral</b> ≥ 40, otherwise <b>Avoid</b>.
<b>Avoid (Bearish)</b> means the short side scores ≥ 62. Fewer events than your minimum shows <b>Low Data</b>.</p>
<p><b>Opportunities</b> lists Buy-rated setups whose entry date for the next report falls inside your horizon.
<b>Backtest</b> re-scores history with no look-ahead to check whether ratings actually predicted results.</p>
<p style='color:$DOWN'><b>Not financial advice.</b> Historical patterns can and do stop working. Always confirm earnings
dates, and size positions for the worst case.</p>
"""


class MainWindow(QMainWindow):
    def __init__(self, demo: bool = False):
        super().__init__()
        self.demo = demo
        self.settings = Settings()
        self.store = DataStore()
        self.results: dict = {}
        self.screen = pd.DataFrame()
        self.windows = all_windows(self.settings["custom_windows"])
        self._theme_busy = False
        themes.apply(QApplication.instance(), self.settings["theme"])
        self._thread = None
        self._worker = None
        self._last_errors: dict = {}
        self.setWindowTitle(f"{APP_NAME} – Earnings Pattern Screener" + (" [DEMO DATA]" if demo else ""))
        self.resize(1480, 900)
        self._build_toolbar()
        self._build_tabs()
        self.setStatusBar(QStatusBar())
        self.status("Ready")
        self._start_analysis()

    # ------------------------------------------------------------------ UI
    def _build_toolbar(self):
        tb = QToolBar("Main")
        tb.setMovable(False)
        self.addToolBar(tb)

        def act(text, fn, tip=""):
            a = QAction(text, self)
            a.triggered.connect(fn)
            a.setToolTip(tip or text)
            tb.addAction(a)
            return a
        self.a_update = act("⟳  Update Data", lambda: self._start_download(False),
                            "Download new/stale data for your universe, then re-analyze")
        self.a_force = act("Force Refresh", lambda: self._start_download(True), "Re-download everything")
        self.a_cancel = act("✕ Cancel", self._cancel, "Stop the current job")
        self.a_cancel.setEnabled(False)
        tb.addSeparator()
        act("Universe…", self._universe, "Choose which stocks to analyze")
        act("Custom Timeframes…", self._custom_windows, "Create your own buy/sell timing rules")
        act("Settings…", self._settings)
        tb.addSeparator()
        act("Export…", self._export, "Export the current table to CSV or Excel")
        act("Help", self._help)
        tb.addSeparator()
        tb.addWidget(QLabel(" Theme "))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(themes.CHOICES)
        self.theme_combo.setCurrentText(self.settings["theme"] if self.settings["theme"] in themes.CHOICES else "System")
        self.theme_combo.setToolTip("Colour theme. 'System' follows your Windows light/dark setting. "
                                    "Shortcut: Ctrl+Shift+T cycles themes.")
        self.theme_combo.currentTextChanged.connect(self._set_theme)
        tb.addWidget(self.theme_combo)
        cycle = QAction("Cycle theme", self)
        cycle.setShortcut("Ctrl+Shift+T")
        cycle.triggered.connect(lambda: self.theme_combo.setCurrentIndex(
            (self.theme_combo.currentIndex() + 1) % self.theme_combo.count()))
        self.addAction(cycle)
        try:
            QApplication.instance().styleHints().colorSchemeChanged.connect(self._on_system_scheme)
        except Exception:
            pass
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)
        self.prog_lbl = QLabel("")
        tb.addWidget(self.prog_lbl)
        self.prog = QProgressBar()
        self.prog.setFixedWidth(220)
        self.prog.setVisible(False)
        tb.addWidget(self.prog)
        if self.demo:
            self.a_update.setEnabled(False)
            self.a_force.setEnabled(False)

    def _make_main_table(self, cols, name):
        model = DataFrameModel([C[k] for k in cols], watchlist_getter=lambda: set(self.settings["watchlist"]))
        view = make_table(model)
        view.doubleClicked.connect(lambda idx, m=model: self._open_detail(m, idx))
        view.clicked.connect(lambda idx, m=model: self._on_click(m, idx))
        hh = view.horizontalHeader()
        hh.setContextMenuPolicy(Qt.CustomContextMenu)
        hh.customContextMenuRequested.connect(lambda pos, v=view, m=model, n=name: self._column_menu(v, m, n, pos))
        hidden = self.settings.data.get(f"hidden_{name}")
        for i, c in enumerate(model.cols):
            hide = (c.key in hidden) if hidden is not None else c.hidden
            view.setColumnHidden(i, hide)
        view.setToolTip("")
        return model, view

    def _build_tabs(self):
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # ---- Opportunities
        opp = QWidget()
        ov = QVBoxLayout(opp)
        intro = QLabel("Buy-rated setups whose entry date for the <b>next</b> earnings report is coming up. "
                       "Double-click a row for the full history. Right-click column headers to show/hide columns.")
        intro.setObjectName("Intro")
        ov.addWidget(intro)
        ctl = QHBoxLayout()
        ctl.addWidget(QLabel("Entry within"))
        self.opp_days = QSpinBox()
        self.opp_days.setRange(0, 60)
        self.opp_days.setValue(int(self.settings["opportunity_days"]))
        self.opp_days.setSuffix(" sessions")
        ctl.addWidget(self.opp_days)
        ctl.addSpacing(12)
        ctl.addWidget(QLabel("Minimum rating"))
        self.opp_rating = QComboBox()
        self.opp_rating.addItems(["Buy or better", "Strong Buy only", "Neutral or better"])
        ctl.addWidget(self.opp_rating)
        ctl.addSpacing(12)
        self.opp_hold = QCheckBox("Include hold-through-earnings timeframes")
        self.opp_best = QCheckBox("Best timeframe per stock")
        self.opp_best.setChecked(True)
        self.opp_watch = QCheckBox("Watchlist only")
        self.opp_confirmed = QCheckBox("Confirmed dates only")
        for w in (self.opp_hold, self.opp_best, self.opp_watch, self.opp_confirmed):
            ctl.addWidget(w)
        ctl.addStretch(1)
        self.opp_count = QLabel("")
        ctl.addWidget(self.opp_count)
        ov.addLayout(ctl)
        for w in (self.opp_days,):
            w.valueChanged.connect(self._refresh_opportunities)
        self.opp_rating.currentIndexChanged.connect(self._refresh_opportunities)
        for w in (self.opp_hold, self.opp_best, self.opp_watch, self.opp_confirmed):
            w.toggled.connect(self._refresh_opportunities)
        self.banner = QLabel("")
        self.banner.setObjectName("Banner")
        self.banner.setWordWrap(True)
        self.banner.setVisible(False)
        ov.addWidget(self.banner)
        self.opp_model, self.opp_view = self._make_main_table(OPPORTUNITY_COLS, "opp")
        ov.addWidget(self.opp_view, 1)
        self.tabs.addTab(opp, "Opportunities")

        # ---- Screener
        scr = QWidget()
        sv = QVBoxLayout(scr)
        self.filters = FilterPanel(self.settings)
        self.filters.changed.connect(self._refresh_screener)
        sv.addWidget(self.filters)
        self.scr_model, self.scr_view = self._make_main_table(SCREENER_COLS, "screener")
        sv.addWidget(self.scr_view, 1)
        self.tabs.addTab(scr, "Screener")

        # ---- Detail
        self.detail = DetailTab(self.settings)
        self.detail.watch_toggled.connect(lambda _: self._refresh_all_views())
        self.tabs.addTab(self.detail, "Stock Detail")

        # ---- Backtest
        self.backtest = BacktestTab(self.settings)
        self.backtest.set_windows(self.windows)
        self.backtest.run_requested.connect(self._run_backtest)
        self.tabs.addTab(self.backtest, "Backtest")

    # ---------------------------------------------------------- helpers
    def status(self, text: str):
        self.statusBar().showMessage(text)

    def _busy(self, on: bool, label: str = ""):
        self.prog.setVisible(on)
        self.prog_lbl.setText(label)
        self.a_cancel.setEnabled(on)
        if not self.demo:
            self.a_update.setEnabled(not on)
            self.a_force.setEnabled(not on)
        if on:
            self.prog.setRange(0, 0)

    def _on_progress(self, i, n, msg):
        self.prog.setRange(0, n)
        self.prog.setValue(i)
        self.prog.setFormat(f"{i}/{n}")
        self.prog_lbl.setText(msg)

    def _on_fail(self, tb):
        self._busy(False)
        self.backtest.show_error()
        QMessageBox.critical(self, "Error", tb[-2000:])

    def _cancel(self):
        if self._worker:
            self._worker.cancel()
        self.prog_lbl.setText("Cancelling…")

    # ---------------------------------------------------------- download
    def _start_download(self, force: bool):
        if self._thread is not None:
            return
        tickers = resolve_universe(self.settings)
        self._busy(True, f"Downloading {len(tickers)} stocks…")
        self._launch(workers.DownloadWorker(self.store, tickers, self.settings, force), self._download_done)

    def _launch(self, worker, done, progress=True):
        self._worker = worker
        self._thread = workers.start(worker, done, self._on_progress if progress else None, self._on_fail)
        self._thread.finished.connect(self._on_thread_finished)

    def _on_thread_finished(self):
        if self.sender() is self._thread:
            self._thread = None
            self._worker = None

    def _download_done(self, info):
        self._busy(False)
        self._last_errors = info.get("errors", {})
        # chain analysis once the download thread has fully stopped
        from PySide6.QtCore import QTimer
        QTimer.singleShot(200, self._start_analysis)

    # ---------------------------------------------------------- analysis
    def _start_analysis(self):
        if self._thread is not None:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(300, self._start_analysis)
            return
        demo = None
        tickers = []
        if self.demo:
            from ..demo_data import make_demo
            demo = make_demo(n_tickers=40)
        else:
            cached = set(self.store.tickers())
            tickers = [t for t in resolve_universe(self.settings) if t in cached]
            if not tickers:
                self._show_banner("<b>No data yet.</b> Click <b>⟳ Update Data</b> in the toolbar to download price and "
                                  "earnings history for your stock universe (about 5–15 minutes the first time; later "
                                  "updates only refresh stale data).")
                return
        self._busy(True, "Analyzing…")
        self._launch(workers.AnalyzeWorker(self.store, tickers, self.windows, self.settings, demo),
                     self._analysis_done)

    def _analysis_done(self, out):
        self._busy(False)
        self.results = out["results"]
        screen = out["screen"]
        if len(screen):
            wmap = {w.key: w for w in self.windows}
            screen["window_desc"] = screen["window_key"].map(lambda k: wmap[k].describe() if k in wmap else "")
            screen["plan"] = [self._plan(wmap.get(k), e, x) for k, e, x in
                              zip(screen["window_key"], screen.get("entry_date", pd.NaT), screen.get("exit_date", pd.NaT))]
        self.screen = screen
        sectors = screen["sector"].dropna().unique().tolist() if len(screen) else []
        self.filters.set_choices(sectors, [(w.label, w.group) for w in self.windows])
        self._refresh_all_views()
        self.detail.set_data(self.results, self.screen)
        n_err = len(self._last_errors)
        msg = f"Analyzed {len(self.results)} stocks × {len(self.windows)} timeframes = {len(screen):,} patterns."
        if n_err:
            msg += f"  {n_err} tickers had download problems (see Help → Download log)."
        self.status(msg)
        if not self.results:
            self._show_banner("No stocks could be analyzed. Check your internet connection and click Update Data.")
        else:
            self.banner.setVisible(False)

    @staticmethod
    def _plan(w, entry, exit_) -> str:
        if w is None or pd.isna(entry) or pd.isna(exit_):
            return ""
        e, x = pd.Timestamp(entry), pd.Timestamp(exit_)
        return f"Buy {w.entry_field.lower()} {e:%a %b %d} → Sell {w.exit_field.lower()} {x:%a %b %d}"

    def _show_banner(self, html):
        self.banner.setText(html)
        self.banner.setVisible(True)

    # ---------------------------------------------------------- refresh views
    def _refresh_all_views(self):
        self._refresh_screener()
        self._refresh_opportunities()

    def _refresh_screener(self):
        df = self.filters.apply(self.screen) if len(self.screen) else self.screen
        if df is not None and len(df):
            df = df.sort_values(["score"], ascending=False, na_position="last")
        self.scr_model.set_df(df)
        self.filters.count_lbl.setText(f"{len(df) if df is not None else 0:,} of {len(self.screen):,} patterns")
        self._autosize(self.scr_view)

    def _refresh_opportunities(self):
        df = self.screen
        if df is None or df.empty or "days_to_entry" not in df:
            self.opp_model.set_df(pd.DataFrame())
            return
        groups = ["Before", "Custom"] + (["Hold Through"] if self.opp_hold.isChecked() else [])
        ratings = {0: ["Buy", "Strong Buy"], 1: ["Strong Buy"], 2: ["Neutral", "Buy", "Strong Buy"]}[
            self.opp_rating.currentIndex()]
        m = (df["group"].isin(groups) & df["rating"].isin(ratings) & (df["days_to_entry"] >= 0)
             & (df["days_to_entry"] <= self.opp_days.value()))
        if "Custom" in groups:  # custom windows must be entered before the report to count here
            wmap = {w.key: w for w in self.windows}
            m &= df["window_key"].map(lambda k: k in wmap and (wmap[k].entry_anchor == "pre")).astype(bool)
        if self.opp_watch.isChecked():
            m &= df["ticker"].isin(self.settings["watchlist"])
        if self.opp_confirmed.isChecked():
            m &= df["confirmed"] == True  # noqa: E712
        out = df[m].sort_values("score", ascending=False)
        if self.opp_best.isChecked():
            out = out.drop_duplicates("ticker")
        out = out.sort_values(["days_to_entry", "score"], ascending=[True, False])
        self.opp_model.set_df(out)
        self.opp_count.setText(f"{len(out)} setups · {out['ticker'].nunique() if len(out) else 0} stocks")
        self._autosize(self.opp_view)

    @staticmethod
    def _autosize(view):
        # size columns once per table (re-measuring on every filter change is slow)
        if getattr(view, "_sized", False) or view.model().rowCount() == 0:
            return
        view._sized = True
        view.resizeColumnsToContents()
        hh = view.horizontalHeader()
        for i in range(hh.count()):
            if hh.sectionSize(i) > 260:
                hh.resizeSection(i, 260)

    # ---------------------------------------------------------- interactions
    def _on_click(self, model, idx):
        if model.cols[idx.column()].kind == "watch":
            self.settings.toggle_watch(model.row(idx.row())["ticker"])
            self._refresh_all_views()

    def _open_detail(self, model, idx):
        if model.cols[idx.column()].kind == "watch":
            return
        r = model.row(idx.row())
        self.detail.show_ticker(r["ticker"], r.get("window_key"))
        self.tabs.setCurrentWidget(self.detail)

    def _column_menu(self, view, model, name, pos):
        menu = QMenu(self)
        for i, c in enumerate(model.cols):
            a = menu.addAction(c.header if c.key != "watch" else "Watchlist ★")
            a.setCheckable(True)
            a.setChecked(not view.isColumnHidden(i))
            a.toggled.connect(lambda on, i=i: view.setColumnHidden(i, not on))
        menu.exec(view.horizontalHeader().mapToGlobal(pos))
        self.settings[f"hidden_{name}"] = [c.key for i, c in enumerate(model.cols) if view.isColumnHidden(i)]

    def _run_backtest(self, params):
        if not self.results:
            self.backtest.show_error()
            QMessageBox.information(self, "Backtest", "No analyzed data yet – click Update Data first.")
            return
        if not params.window_keys:
            self.backtest.show_error()
            QMessageBox.information(self, "Backtest", "Tick at least one timeframe.")
            return
        if self._thread is not None:
            self.backtest.show_error()
            return
        self._busy(True, "Backtesting…")
        self._launch(workers.BacktestWorker(self.results, params), self._backtest_done, progress=False)

    def _backtest_done(self, bt):
        self._busy(False)
        self.backtest.show_results(bt)

    # ---------------------------------------------------------- dialogs
    def _universe(self):
        if UniverseDialog(self.settings, self).exec():
            n = len(resolve_universe(self.settings))
            if QMessageBox.question(self, "Universe updated",
                                    f"Universe now has {n} stocks. Download any missing data now?") == QMessageBox.Yes:
                self._start_download(False)
            else:
                self._start_analysis()

    def _custom_windows(self):
        if CustomWindowsDialog(self.settings, self).exec():
            self.windows = all_windows(self.settings["custom_windows"])
            self.backtest.set_windows(self.windows)
            self._start_analysis()

    def _settings(self):
        if SettingsDialog(self.settings, self).exec():
            self.opp_days.setValue(int(self.settings["opportunity_days"]))
            self._start_analysis()

    def _export(self):
        w = self.tabs.currentWidget()
        model = self.opp_model if self.tabs.currentIndex() == 0 else self.scr_model
        if w is self.detail:
            model = self.detail.win_model
        elif w is self.backtest:
            model = self.backtest.trade_model
        df = model.df
        if df is None or df.empty:
            QMessageBox.information(self, "Export", "Nothing to export in this view.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export", "earnings_screen.xlsx",
                                              "Excel (*.xlsx);;CSV (*.csv)")
        if not path:
            return
        keep = [c.key for c in model.cols if c.key in df.columns]
        out = df[keep].rename(columns={c.key: c.header for c in model.cols})
        try:
            if path.lower().endswith(".csv"):
                out.to_csv(path, index=False)
            else:
                out.to_excel(path, index=False)
            self.status(f"Exported {len(out)} rows to {path}")
        except Exception as e:
            QMessageBox.warning(self, "Export failed", str(e))

    def _help(self):
        box = QMessageBox(self)
        box.setWindowTitle("How it works")
        box.setTextFormat(Qt.RichText)
        t = themes.current()
        text = HELP_TEXT.replace("$DOWN", t["down"]) + f"<p style='color:{t['muted']}'>{APP_NAME} v{APP_VERSION} · data folder: {self.store.path}</p>"
        if self._last_errors:
            items = "".join(f"<li>{t}: {e}</li>" for t, e in list(self._last_errors.items())[:30])
            text += f"<h4>Download log ({len(self._last_errors)} issues)</h4><ul>{items}</ul>"
        box.setText(text)
        box.exec()

    # ---------------------------------------------------------- themes
    def _set_theme(self, name: str):
        self.settings["theme"] = name
        self._apply_theme()

    def _on_system_scheme(self, *_):
        if self.settings["theme"] == "System" and not self._theme_busy:
            self._apply_theme()

    def _apply_theme(self):
        if self._theme_busy:
            return
        self._theme_busy = True
        try:
            t = themes.apply(QApplication.instance(), self.settings["theme"])
            themes.set_title_bar_dark(self, t.dark)
            for m in (self.opp_model, self.scr_model):
                m.repaint_all()
            self.detail.refresh_theme()
            self.backtest.refresh_theme()
            self.status(f"Theme: {self.settings['theme']}" + (f" ({t.name})" if self.settings["theme"] == "System" else ""))
        finally:
            self._theme_busy = False

    def showEvent(self, e):
        super().showEvent(e)
        themes.set_title_bar_dark(self, themes.current().dark)

    def closeEvent(self, e):
        if self._worker:
            self._worker.cancel()
        if self._thread is not None:
            try:
                self._thread.quit()
                self._thread.wait(3000)
            except RuntimeError:
                pass
        super().closeEvent(e)


def _asset(name: str) -> str | None:
    from pathlib import Path
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    p = base / "assets" / name
    return str(p) if p.exists() else None


def run(demo: bool = False):
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    icon = _asset("icon.png")
    if icon:
        app.setWindowIcon(QIcon(icon))
    if sys.platform.startswith("win"):
        try:  # show our icon (not python's) in the Windows taskbar
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("EarningsScreener.App")
        except Exception:
            pass
    w = MainWindow(demo=demo)
    w.show()
    return app.exec()
