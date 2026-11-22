"""Walk-forward backtest tab: does the rating actually predict future results?"""
from __future__ import annotations

import pandas as pd
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QDateEdit, QDoubleSpinBox, QFormLayout, QGridLayout, QGroupBox,
                               QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QSpinBox, QSplitter,
                               QTabWidget, QVBoxLayout, QWidget)

from ..backtest import BacktestParams, equity_curve
from . import themes
from .charts import Chart
from .columns import TRADE_COLS, Col
from .detail_tab import make_table
from .table_model import DataFrameModel, fmt_value

SUMMARY_ROWS = [("trades", "Trades", "int"), ("tickers", "Stocks", "int"), ("win_rate", "Win rate", "pctp"),
                ("avg", "Avg return / trade", "pct"), ("median", "Median return", "pct"),
                ("avg_excess", "Avg vs SPY", "pct"), ("beat_spy", "Beat SPY", "pctp"),
                ("profit_factor", "Profit factor", "num"), ("sharpe_per_trade", "Sharpe / trade", "num"),
                ("total", "Sum of returns", "pct"), ("max_drawdown", "Max drawdown (sum)", "pct")]


class BacktestTab(QWidget):
    run_requested = Signal(object)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        h = QHBoxLayout(self)
        # ---------------- controls
        ctl = QGroupBox("Rules (applied with no look-ahead)")
        ctl.setMaximumWidth(330)
        f = QFormLayout(ctl)
        self.windows = QListWidget()
        self.windows.setMinimumHeight(190)
        f.addRow(QLabel("Timeframes to trade:"))
        f.addRow(self.windows)
        self.min_prior = QSpinBox(); self.min_prior.setRange(3, 60); self.min_prior.setValue(8)
        f.addRow("Min. prior events:", self.min_prior)
        self.lookback = QSpinBox(); self.lookback.setRange(0, 80); self.lookback.setValue(0)
        self.lookback.setSpecialValueText("All prior")
        f.addRow("Use last N events:", self.lookback)
        self.min_score = QDoubleSpinBox(); self.min_score.setRange(0, 100); self.min_score.setValue(62)
        f.addRow("Min. score at entry:", self.min_score)
        self.min_win = QSpinBox(); self.min_win.setRange(0, 100); self.min_win.setValue(0); self.min_win.setSuffix(" %")
        f.addRow("Min. prior win rate:", self.min_win)
        self.direction = QComboBox(); self.direction.addItems(["Long (buy)", "Short (sell)"])
        f.addRow("Direction:", self.direction)
        self.cost = QSpinBox(); self.cost.setRange(0, 200); self.cost.setValue(int(settings["cost_bps"]))
        self.cost.setSuffix(" bps")
        f.addRow("Round-trip cost:", self.cost)
        self.universe = QComboBox(); self.universe.addItems(["All analyzed stocks", "Watchlist only"])
        f.addRow("Stocks:", self.universe)
        self.start = QDateEdit(); self.start.setCalendarPopup(True); self.start.setDisplayFormat("yyyy-MM-dd")
        self.start.setDate(pd.Timestamp("2015-01-01").date())
        f.addRow("Trades from:", self.start)
        self.run_btn = QPushButton("Run Backtest")
        self.run_btn.setObjectName("Primary")
        self.run_btn.clicked.connect(self._emit_run)
        f.addRow(self.run_btn)
        expl = QLabel("Each past report is re-scored using only reports that had already closed before entry. "
                      "If the 'Selected' line beats 'Every event', the rating adds value beyond the raw pattern.")
        expl.setWordWrap(True)
        expl.setObjectName("Muted")
        f.addRow(expl)
        h.addWidget(ctl)

        # ---------------- results
        right = QSplitter(Qt.Vertical)
        top = QWidget()
        tg = QGridLayout(top)
        tg.setContentsMargins(0, 0, 0, 0)
        self.summary = QLabel("Run a backtest to see results.")
        self.summary.setTextFormat(Qt.RichText)
        self.summary.setObjectName("SummaryBox")
        self.summary.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.summary.setMinimumWidth(330)
        tg.addWidget(self.summary, 0, 0)
        self.ctabs = QTabWidget()
        self.eq_chart = Chart()
        self.bucket_chart = Chart()
        self.ctabs.addTab(self.eq_chart, "Equity Curve")
        self.ctabs.addTab(self.bucket_chart, "Score Calibration")
        tg.addWidget(self.ctabs, 0, 1)
        tg.setColumnStretch(1, 1)
        right.addWidget(top)
        btabs = QTabWidget()
        self.trade_model = DataFrameModel(TRADE_COLS)
        self.trade_table = make_table(self.trade_model)
        btabs.addTab(self.trade_table, "Trades")
        self.year_model = DataFrameModel([
            Col("year", "Year", "int"), Col("selected_trades", "Selected Trades", "int"),
            Col("selected_win", "Selected Win %", "pctp"), Col("selected_avg", "Selected Avg", "pct"),
            Col("all_trades", "All Events", "int"), Col("all_win", "All Win %", "pctp"), Col("all_avg", "All Avg", "pct")])
        btabs.addTab(make_table(self.year_model), "By Year")
        right.addWidget(btabs)
        right.setSizes([380, 300])
        h.addWidget(right, 1)
        self.eq_chart.message("No backtest yet")
        self.bucket_chart.message("No backtest yet")

    def set_windows(self, windows):
        checked = {self.windows.item(i).data(Qt.UserRole) for i in range(self.windows.count())
                   if self.windows.item(i).checkState() == Qt.Checked} or {"pre5"}
        self.windows.clear()
        for w in windows:
            it = QListWidgetItem(f"{w.label}")
            it.setToolTip(w.describe())
            it.setData(Qt.UserRole, w.key)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if w.key in checked else Qt.Unchecked)
            self.windows.addItem(it)

    def _emit_run(self):
        keys = [self.windows.item(i).data(Qt.UserRole) for i in range(self.windows.count())
                if self.windows.item(i).checkState() == Qt.Checked]
        p = BacktestParams(
            window_keys=keys, min_prior=self.min_prior.value(), lookback=self.lookback.value(),
            min_score=self.min_score.value(), min_win_rate=self.min_win.value() / 100,
            direction=1 if self.direction.currentIndex() == 0 else -1, cost_bps=self.cost.value(),
            start=pd.Timestamp(self.start.date().toPython()),
            tickers=list(self.settings["watchlist"]) if self.universe.currentIndex() == 1 else None)
        self.run_btn.setEnabled(False)
        self.run_btn.setText("Running…")
        self.run_requested.emit(p)

    def show_results(self, bt: dict):
        self.run_btn.setEnabled(True)
        self.run_btn.setText("Run Backtest")
        self._last_bt = bt
        t = themes.current()
        s, a = bt["summary_selected"], bt["summary_all"]
        rows = "".join(
            f"<tr><td>{lbl}</td><td align='right'><b>{fmt_value(s.get(k), kind)}</b></td>"
            f"<td align='right' style='color:{t['muted']}'>{fmt_value(a.get(k), kind)}</td></tr>"
            for k, lbl, kind in SUMMARY_ROWS)
        verdict = ""
        if s.get("trades", 0) >= 20 and a.get("trades", 0):
            better = s["avg"] > a["avg"] and s["win_rate"] > a["win_rate"]
            verdict = (f"<p style='color:{t['up']}'><b>Rules beat the unfiltered pattern out-of-sample.</b></p>" if better
                       else f"<p style='color:{t['down']}'><b>Rules did NOT beat the unfiltered pattern – treat ratings with caution.</b></p>")
        elif s.get("trades", 0) < 20:
            verdict = f"<p style='color:{t['warn']}'><b>Fewer than 20 trades – too few to judge.</b></p>"
        self.summary.setText(
            "<table cellspacing='4'><tr><th align='left'></th><th align='right'>Selected</th>"
            f"<th align='right'>Every event</th></tr>{rows}</table>{verdict}")
        self.eq_chart.equity({"Selected by rules": equity_curve(bt["trades"]),
                              "Every event (no filter)": equity_curve(bt["universe"])},
                             "Walk-forward equity (1 unit per trade, net of costs)")
        self.bucket_chart.buckets(bt["by_score"], "Avg next-trade return by score bucket")
        tr = bt["trades"]
        self.trade_model.set_df(tr.sort_values("entry_date", ascending=False) if len(tr) else tr)
        self.trade_table.resizeColumnsToContents()
        self.year_model.set_df(bt["by_year"])

    def refresh_theme(self):
        for ch in (self.eq_chart, self.bucket_chart):
            ch.redraw()
        if getattr(self, "_last_bt", None) is not None:
            self.show_results(self._last_bt)
        self.trade_model.repaint_all()
        self.year_model.repaint_all()

    def show_error(self):
        self.run_btn.setEnabled(True)
        self.run_btn.setText("Run Backtest")
