"""Stock detail: all timeframes for one ticker, per-event chart, average path, event history."""
from __future__ import annotations

import pandas as pd
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QHBoxLayout, QHeaderView, QLabel, QPushButton,
                               QSplitter, QTableView, QTabWidget, QVBoxLayout, QWidget)

from ..engine import average_path, event_table
from .charts import Chart
from .columns import C, DETAIL_COLS, EVENT_COLS
from .table_model import DataFrameModel, fmt_value


def make_table(model) -> QTableView:
    t = QTableView()
    t.setModel(model)
    t.setSortingEnabled(True)
    t.setAlternatingRowColors(True)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setSelectionMode(QAbstractItemView.SingleSelection)
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(24)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
    t.horizontalHeader().setHighlightSections(False)
    t.horizontalHeader().setResizeContentsPrecision(40)  # measure only ~40 rows when auto-sizing
    t.setWordWrap(False)
    return t


class DetailTab(QWidget):
    watch_toggled = Signal(str)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.results: dict = {}
        self.screen = pd.DataFrame()
        self.ticker = None
        v = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("Stock:"))
        self.picker = QComboBox()
        self.picker.setEditable(True)
        self.picker.setMinimumWidth(140)
        self.picker.activated.connect(lambda _: self.show_ticker(self.picker.currentText().strip().upper()))
        top.addWidget(self.picker)
        self.watch_btn = QPushButton("☆ Watch")
        self.watch_btn.clicked.connect(self._toggle_watch)
        top.addWidget(self.watch_btn)
        self.header = QLabel("Select a stock (double-click any row in the screener).")
        self.header.setObjectName("DetailHeader")
        self.header.setTextFormat(Qt.RichText)
        top.addWidget(self.header, 1)
        v.addLayout(top)

        split = QSplitter(Qt.Vertical)
        upper = QSplitter(Qt.Horizontal)
        self.win_model = DataFrameModel([C[k] for k in DETAIL_COLS])
        self.win_table = make_table(self.win_model)
        self.win_table.selectionModel().currentRowChanged.connect(self._on_window)
        upper.addWidget(self.win_table)
        self.charts = QTabWidget()
        self.bar_chart = Chart()
        self.path_chart = Chart()
        self.price_chart = Chart()
        self.charts.addTab(self.bar_chart, "Returns by Event")
        self.charts.addTab(self.path_chart, "Average Path Around Earnings")
        self.charts.addTab(self.price_chart, "Price History")
        upper.addWidget(self.charts)
        upper.setSizes([620, 560])
        split.addWidget(upper)
        lower = QWidget()
        lv = QVBoxLayout(lower)
        lv.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel("Earnings history")
        lbl.setObjectName("SubHeader")
        lv.addWidget(lbl)
        self.ev_model = DataFrameModel(EVENT_COLS)
        self.ev_table = make_table(self.ev_model)
        lv.addWidget(self.ev_table)
        split.addWidget(lower)
        split.setSizes([420, 260])
        v.addWidget(split, 1)
        for c in (self.bar_chart, self.path_chart, self.price_chart):
            c.message("No stock selected")

    def set_data(self, results: dict, screen: pd.DataFrame):
        self.results, self.screen = results, screen
        cur = self.picker.currentText()
        self.picker.blockSignals(True)
        self.picker.clear()
        self.picker.addItems(sorted(results))
        self.picker.setCurrentText(cur)
        self.picker.blockSignals(False)
        if self.ticker in results:
            self.show_ticker(self.ticker)

    def show_ticker(self, ticker: str, window_key: str | None = None):
        if ticker not in self.results:
            return
        self.ticker = ticker
        self.picker.setCurrentText(ticker)
        res = self.results[ticker]
        c = res["common"]
        nxt = fmt_value(c.get("next_earnings"), "date")
        timing = {"BMO": "before open", "AMC": "after close"}.get(c.get("next_timing"), "time unknown")
        conf = "" if c.get("confirmed") is None else (" · confirmed" if c.get("confirmed") else " · estimated")
        self.header.setText(
            f"<span style='font-size:15pt;font-weight:600'>{ticker}</span>&nbsp;&nbsp;{c.get('name', '')}"
            f"&nbsp;&nbsp;<span style='color:#6b7884'>{c.get('sector', '')} · Mkt cap {fmt_value(c.get('market_cap'), 'cap')}"
            f" · Last {fmt_value(c.get('last_price'), 'num')}</span><br>"
            f"Next earnings: <b>{nxt}</b> ({timing}{conf}) · {c.get('events_total', 0)} past reports analyzed · "
            f"Avg earnings-day move {fmt_value(c.get('hist_move'), 'pctp')}"
            + (f" · Implied {fmt_value(c.get('implied_move'), 'pctp')}" if c.get("implied_move") else ""))
        self._update_watch_btn()
        df = self.screen[self.screen["ticker"] == ticker].sort_values("window_order")
        self.win_model.set_df(df)
        self.win_table.resizeColumnsToContents()
        self.ev_model.set_df(event_table(res))
        self.ev_table.resizeColumnsToContents()
        paths = average_path(res["prices"], res["events"])
        self.path_chart.avg_path(paths, f"{ticker}: price path around {len(paths.columns)} reports")
        self.price_chart.price(res["prices"], res["events"], f"{ticker}: last 3 years")
        row = 0
        if window_key is not None:
            m = self.win_model.df.index[self.win_model.df["window_key"] == window_key]
            row = int(m[0]) if len(m) else 0
        if len(df):
            self.win_table.selectRow(row)
            self._on_window(self.win_model.index(row, 0))

    def _on_window(self, idx, *_):
        if not idx.isValid() or self.ticker is None:
            return
        r = self.win_model.row(idx.row())
        wr = self.results[self.ticker]["window_returns"].get(r["window_key"])
        self.bar_chart.event_bars(wr, f"{self.ticker} · {r['window']}: return at each report")
        self.charts.setCurrentIndex(0)

    def _toggle_watch(self):
        if self.ticker:
            self.settings.toggle_watch(self.ticker)
            self._update_watch_btn()
            self.watch_toggled.emit(self.ticker)

    def _update_watch_btn(self):
        on = self.ticker in set(self.settings["watchlist"])
        self.watch_btn.setText("★ Watching" if on else "☆ Watch")
