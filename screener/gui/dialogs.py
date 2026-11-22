"""Settings, universe and custom-window dialogs."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
                               QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox, QPlainTextEdit,
                               QPushButton, QRadioButton, QSpinBox, QVBoxLayout, QButtonGroup, QGroupBox)

from ..universe import DEFAULT_TICKERS, load_sp500, load_ticker_file, parse_ticker_text
from ..windows import Window


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.s = settings
        f = QFormLayout(self)
        self.years = QSpinBox(); self.years.setRange(2, 25); self.years.setValue(int(settings["years_history"]))
        self.years.setSuffix(" years")
        f.addRow("History to analyze:", self.years)
        self.min_obs = QSpinBox(); self.min_obs.setRange(3, 60); self.min_obs.setValue(int(settings["min_obs_for_rating"]))
        f.addRow("Min. events for a rating:", self.min_obs)
        self.cost = QSpinBox(); self.cost.setRange(0, 200); self.cost.setValue(int(settings["cost_bps"]))
        self.cost.setSuffix(" bps (0.01%)")
        f.addRow("Round-trip trading cost:", self.cost)
        self.opp = QSpinBox(); self.opp.setRange(1, 60); self.opp.setValue(int(settings["opportunity_days"]))
        self.opp.setSuffix(" sessions")
        f.addRow("Opportunities horizon:", self.opp)
        self.refresh = QSpinBox(); self.refresh.setRange(1, 24 * 14); self.refresh.setValue(int(settings["refresh_hours"]))
        self.refresh.setSuffix(" hours")
        f.addRow("Re-download data older than:", self.refresh)
        self.workers = QSpinBox(); self.workers.setRange(1, 16); self.workers.setValue(int(settings["max_workers"]))
        f.addRow("Parallel downloads:", self.workers)
        self.bench = QLineEdit(settings["benchmark"])
        f.addRow("Benchmark ticker:", self.bench)
        self.options = QCheckBox("Fetch option volume and implied earnings move (slower)")
        self.options.setChecked(bool(settings["fetch_options"]))
        f.addRow("", self.options)
        self.av = QLineEdit(settings["alpha_vantage_key"])
        self.av.setPlaceholderText("optional – free key from alphavantage.co")
        f.addRow("Alpha Vantage API key:", self.av)
        note = QLabel("Alpha Vantage is only used as a fallback when Yahoo has no earnings dates for a ticker.")
        note.setWordWrap(True); note.setObjectName("Muted")
        f.addRow("", note)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        f.addRow(bb)

    def accept(self):
        d = self.s.data
        d["years_history"] = self.years.value()
        d["min_obs_for_rating"] = self.min_obs.value()
        d["cost_bps"] = self.cost.value()
        d["opportunity_days"] = self.opp.value()
        d["refresh_hours"] = self.refresh.value()
        d["max_workers"] = self.workers.value()
        d["benchmark"] = self.bench.text().strip().upper() or "SPY"
        d["fetch_options"] = self.options.isChecked()
        d["alpha_vantage_key"] = self.av.text().strip()
        self.s.save()
        super().accept()


class UniverseDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Stock Universe")
        self.resize(560, 520)
        self.s = settings
        v = QVBoxLayout(self)
        box = QGroupBox("Which stocks should be analyzed?")
        bl = QVBoxLayout(box)
        self.grp = QButtonGroup(self)
        self.r_def = QRadioButton(f"Built-in list of {len(DEFAULT_TICKERS)} liquid, optionable US stocks")
        n_sp = len(settings.data.get("sp500_cache", []))
        self.r_sp = QRadioButton("S&&P 500" + (f" ({n_sp} stocks cached)" if n_sp else " (downloads the list from Wikipedia)"))
        self.r_cu = QRadioButton("My custom list (below)")
        for i, r in enumerate((self.r_def, self.r_sp, self.r_cu)):
            self.grp.addButton(r, i)
            bl.addWidget(r)
        {"default": self.r_def, "sp500": self.r_sp, "custom": self.r_cu}.get(settings["universe"], self.r_def).setChecked(True)
        v.addWidget(box)
        v.addWidget(QLabel("Custom tickers (comma, space or one per line). Your watchlist is always included."))
        self.text = QPlainTextEdit(" ".join(settings["custom_tickers"]))
        v.addWidget(self.text, 1)
        h = QHBoxLayout()
        b1 = QPushButton("Import from file (.txt / .csv)…"); b1.clicked.connect(self._import)
        b2 = QPushButton("Copy built-in list into custom"); b2.clicked.connect(
            lambda: self.text.setPlainText(" ".join(DEFAULT_TICKERS)))
        h.addWidget(b1); h.addWidget(b2); h.addStretch(1)
        v.addLayout(h)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import tickers", "", "Text/CSV (*.txt *.csv);;All files (*)")
        if path:
            try:
                self.text.setPlainText(" ".join(load_ticker_file(path)))
            except Exception as e:
                QMessageBox.warning(self, "Import failed", str(e))

    def accept(self):
        d = self.s.data
        d["custom_tickers"] = parse_ticker_text(self.text.toPlainText())
        choice = {0: "default", 1: "sp500", 2: "custom"}[self.grp.checkedId()]
        if choice == "sp500" and not d.get("sp500_cache"):
            try:
                d["sp500_cache"] = load_sp500()
            except Exception as e:
                QMessageBox.warning(self, "S&P 500", f"Could not download the S&P 500 list:\n{e}")
                return
        d["universe"] = choice
        self.s.save()
        super().accept()


def resolve_universe(settings) -> list[str]:
    u = settings["universe"]
    if u == "sp500" and settings.data.get("sp500_cache"):
        base = list(settings.data["sp500_cache"])
    elif u == "custom" and settings["custom_tickers"]:
        base = list(settings["custom_tickers"])
    else:
        base = list(DEFAULT_TICKERS)
    return sorted(set(base) | set(settings["watchlist"]))


class CustomWindowsDialog(QDialog):
    """Define your own buy/sell timing, e.g. buy 7 sessions before, sell at the open of the reaction day."""

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Custom Timeframes")
        self.resize(620, 460)
        self.s = settings
        self.items = list(settings["custom_windows"])
        v = QVBoxLayout(self)
        intro = QLabel("<b>Pre-earnings session</b> = last close before the report reaches the market. "
                       "<b>Reaction session</b> = first session trading on the news. "
                       "Offsets are in trading sessions (negative = before).")
        intro.setWordWrap(True)
        v.addWidget(intro)
        self.list = QListWidget()
        v.addWidget(self.list, 1)
        self._refresh()
        form = QFormLayout()
        self.name = QLineEdit(); self.name.setPlaceholderText("e.g. Buy 7 days before, sell at reaction open")
        form.addRow("Name:", self.name)

        def side():
            h = QHBoxLayout()
            a = QComboBox(); a.addItems(["Pre-earnings session", "Reaction session"])
            o = QSpinBox(); o.setRange(-60, 60)
            f = QComboBox(); f.addItems(["Close", "Open"])
            h.addWidget(a); h.addWidget(QLabel("offset")); h.addWidget(o); h.addWidget(QLabel("at")); h.addWidget(f)
            return h, a, o, f
        h1, self.ea, self.eo, self.ef = side()
        h2, self.xa, self.xo, self.xf = side()
        self.eo.setValue(-7)
        self.xa.setCurrentIndex(1); self.xf.setCurrentIndex(1)
        form.addRow("Buy:", h1)
        form.addRow("Sell:", h2)
        v.addLayout(form)
        h = QHBoxLayout()
        add = QPushButton("Add timeframe"); add.clicked.connect(self._add)
        rm = QPushButton("Remove selected"); rm.clicked.connect(self._remove)
        h.addWidget(add); h.addWidget(rm); h.addStretch(1)
        v.addLayout(h)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def _refresh(self):
        self.list.clear()
        for d in self.items:
            w = Window.from_dict({**d, "group": "Custom"})
            self.list.addItem(f"{w.label}  —  {w.describe()}")

    def _add(self):
        anchor = lambda cb: "pre" if cb.currentIndex() == 0 else "react"
        ea, xa = anchor(self.ea), anchor(self.xa)
        e_pos = self.eo.value() + (1 if ea == "react" else 0)
        x_pos = self.xo.value() + (1 if xa == "react" else 0)
        if x_pos < e_pos or (x_pos == e_pos and not (self.ef.currentText() == "Open" and self.xf.currentText() == "Close")):
            QMessageBox.warning(self, "Invalid", "The sell point must come after the buy point.")
            return
        label = self.name.text().strip() or f"Custom {len(self.items) + 1}"
        key = "c_" + "".join(ch for ch in label.lower() if ch.isalnum())[:24] + f"_{len(self.items)}"
        self.items.append({"key": key, "label": label, "group": "Custom",
                           "entry_anchor": ea, "entry_off": self.eo.value(), "entry_field": self.ef.currentText(),
                           "exit_anchor": xa, "exit_off": self.xo.value(), "exit_field": self.xf.currentText()})
        self.name.clear()
        self._refresh()

    def _remove(self):
        r = self.list.currentRow()
        if r >= 0:
            self.items.pop(r)
            self._refresh()

    def accept(self):
        self.s["custom_windows"] = self.items
        super().accept()
