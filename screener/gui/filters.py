"""Filter panel (modelled on classic screener layouts) + saved filters."""
from __future__ import annotations

import re

import pandas as pd
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout, QInputDialog, QLabel,
                               QLineEdit, QMessageBox, QPushButton, QSizePolicy, QVBoxLayout, QWidget)

ANY = "-Any-"


def _opts(*items):
    return [(ANY, None, None)] + list(items)


# key, label, section, column, options [(label, op, value)]
SPECS = [
    ("watchlist", "In My Watchlist", "D", None, _opts(("Yes", "watch", True), ("No", "watch", False))),
    ("market_cap", "Market Cap", "D", "market_cap", _opts(
        ("Mega (over $200B)", ">=", 200e9), ("Large (over $10B)", ">=", 10e9), ("Over $2 Billion", ">=", 2e9),
        ("Over $1 Billion", ">=", 1e9), ("Over $300 Million", ">=", 3e8), ("Small (under $2B)", "<", 2e9))),
    ("sector", "Sector", "D", "sector", _opts()),
    ("index", "Index", "D", "indexes", _opts()),
    ("exchange", "Exchange", "D", "exchange", _opts(
        ("Nasdaq", "==", "Nasdaq"), ("NYSE", "==", "NYSE"), ("NYSE American / Arca / other", "notin", ["Nasdaq", "NYSE"]))),
    ("timeframe", "Timeframe", "D", "window", _opts()),
    ("earn_date", "Earnings Date", "D", "days_to_earnings", _opts(
        ("Next 7 days", "between", (0, 7)), ("Next 14 days", "between", (0, 14)),
        ("Next 30 days", "between", (0, 30)), ("Next 60 days", "between", (0, 60)),
        ("Has upcoming date", "notna", None))),
    ("earn_time", "Earnings Time", "D", "next_timing", _opts(
        ("Before Open (BMO)", "==", "BMO"), ("After Close (AMC)", "==", "AMC"))),
    ("confirmed", "Next Earnings Confirmed?", "D", "confirmed", _opts(("Yes", "==", True), ("No", "==", False))),
    ("entry", "Entry Window", "D", "days_to_entry", _opts(
        ("Enter today / next session", "between", (0, 0)), ("Within 2 sessions", "between", (0, 2)),
        ("Within 5 sessions", "between", (0, 5)), ("Within 10 sessions", "between", (0, 10)),
        ("Within 20 sessions", "between", (0, 20)), ("Not yet passed", ">=", 0))),
    ("avg_volume", "Avg Volume", "D", "avg_volume", _opts(
        ("Above 500K", ">=", 5e5), ("Above 1M", ">=", 1e6), ("Above 5M", ">=", 5e6))),
    ("option_volume", "Avg Option Volume", "D", "option_volume", _opts(
        ("Above 1K", ">=", 1e3), ("Above 5K", ">=", 5e3), ("Above 10K", ">=", 1e4), ("Above 50K", ">=", 5e4))),
    ("n", "# of Observations", "S", "n", _opts(
        ("Above 8", ">=", 8), ("Above 12", ">=", 12), ("Above 20", ">=", 20), ("Above 30", ">=", 30))),
    ("win_rate", "Win Rate %", "S", "win_rate", _opts(
        ("Above 50%", ">", 0.5), ("Above 60%", ">=", 0.6), ("Above 70%", ">=", 0.7), ("Above 80%", ">=", 0.8),
        ("Below 40%", "<=", 0.4), ("Below 30%", "<=", 0.3))),
    ("avg", "Avg Return", "S", "avg", _opts(
        ("Positive", ">", 0), ("Above 0.5%", ">=", 0.005), ("Above 1%", ">=", 0.01), ("Above 2%", ">=", 0.02),
        ("Above 3%", ">=", 0.03), ("Negative", "<", 0))),
    ("median", "Median Return", "S", "median", _opts(
        ("Positive", ">", 0), ("Above 0.5%", ">=", 0.005), ("Above 1%", ">=", 0.01), ("Negative", "<", 0))),
    ("best", "Best Return", "S", "best", _opts(("Above 5%", ">=", 0.05), ("Above 10%", ">=", 0.10),
                                               ("Above 20%", ">=", 0.20))),
    ("worst", "Worst Return", "S", "worst", _opts(
        ("Better than -3%", ">=", -0.03), ("Better than -5%", ">=", -0.05), ("Better than -10%", ">=", -0.10),
        ("Better than -20%", ">=", -0.20))),
    ("std", "Return Std Dev", "S", "std", _opts(
        ("Below 3%", "<=", 0.03), ("Below 5%", "<=", 0.05), ("Below 10%", "<=", 0.10))),
    ("sharpe", "Sharpe Ratio", "S", "sharpe", _opts(
        ("Above 0.2", ">=", 0.2), ("Above 0.3", ">=", 0.3), ("Above 0.5", ">=", 0.5), ("Above 1.0", ">=", 1.0))),
    ("win_edge", "Win Edge vs Normal", "S", "win_edge", _opts(
        ("Positive", ">", 0), ("Above +5 pts", ">=", 0.05), ("Above +10 pts", ">=", 0.10),
        ("Above +20 pts", ">=", 0.20))),
    ("beat_bench", "Beat SPY %", "S", "beat_bench", _opts(
        ("Above 55%", ">=", 0.55), ("Above 60%", ">=", 0.6), ("Above 70%", ">=", 0.7))),
    ("q_value", "Luck Filter (q-value)", "S", "q_value", _opts(
        ("Below 0.50", "<", 0.5), ("Below 0.25", "<", 0.25), ("Below 0.10", "<", 0.10))),
    ("score", "Score", "S", "score", _opts(
        ("55+", ">=", 55), ("62+ (Buy)", ">=", 62), ("75+ (Strong Buy)", ">=", 75), ("Below 40", "<", 40))),
    ("rating", "Rating", "S", "rating", _opts(
        ("Strong Buy", "in", ["Strong Buy"]), ("Buy or better", "in", ["Buy", "Strong Buy"]),
        ("Neutral", "in", ["Neutral"]), ("Avoid (any)", "in", ["Avoid", "Avoid (Bearish)"]),
        ("Exclude Low Data", "notin", ["Low Data"]))),
    ("last4", "Last 4 Events Win %", "S", "last4", _opts(
        ("At least 50%", ">=", 0.5), ("At least 75%", ">=", 0.75), ("All 4 won", ">=", 1.0))),
]


def apply_rule(df: pd.DataFrame, col: str | None, op: str, val, watchlist: set) -> pd.DataFrame:
    if op is None:
        return df
    if op == "watch":
        m = df["ticker"].isin(watchlist)
        return df[m] if val else df[~m]
    if col not in df.columns:
        return df
    s = df[col]
    if op == "group":
        return df[df["group"] == val]
    if op == ">=":
        return df[s >= val]
    if op == ">":
        return df[s > val]
    if op == "<=":
        return df[s <= val]
    if op == "<":
        return df[s < val]
    if op == "==":
        return df[s == val]
    if op == "in":
        return df[s.isin(val)]
    if op == "notin":
        return df[~s.isin(val)]
    if op == "between":
        lo, hi = val
        return df[(s >= lo) & (s <= hi)]
    if op == "notna":
        return df[s.notna()]
    if op == "member":   # value is one name inside a " · "-separated list
        pat = r"(?:^| · )" + re.escape(val) + r"(?:$| · )"
        return df[s.fillna("").astype(str).str.contains(pat, regex=True)]
    if op == "nonempty":
        return df[s.fillna("").astype(str).str.len() > 0]
    if op == "empty":
        return df[s.fillna("").astype(str).str.len() == 0]
    return df


class FilterPanel(QWidget):
    changed = Signal()

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.combos: dict[str, QComboBox] = {}
        self.options: dict[str, list] = {k: list(o) for k, _, _, _, o in SPECS}
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # top row: toggle + search + clear
        top = QHBoxLayout()
        self.toggle_btn = QPushButton("▼ Filters")
        self.toggle_btn.setObjectName("FilterToggle")
        self.toggle_btn.setFlat(True)
        self.toggle_btn.clicked.connect(self._toggle)
        top.addWidget(self.toggle_btn)
        top.addSpacing(12)
        top.addWidget(QLabel("Search:"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Symbols or company name (e.g. AAPL, MSFT)")
        self.search.setClearButtonEnabled(True)
        self.search.setMaximumWidth(320)
        self.search.textChanged.connect(self.changed)
        top.addWidget(self.search)
        self.best_only = QCheckBox("Best timeframe per stock only")
        self.best_only.setToolTip("Keep only the highest-scoring timeframe for each stock after filtering")
        self.best_only.toggled.connect(self.changed)
        top.addSpacing(12)
        top.addWidget(self.best_only)
        top.addStretch(1)
        self.count_lbl = QLabel("")
        self.count_lbl.setObjectName("CountLabel")
        top.addWidget(self.count_lbl)
        clear = QPushButton("Clear")
        clear.clicked.connect(self.clear)
        top.addWidget(clear)
        outer.addLayout(top)

        self.body = QFrame()
        self.body.setObjectName("FilterBody")
        grid = QGridLayout(self.body)
        grid.setContentsMargins(6, 4, 6, 6)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)
        hd = QLabel("Descriptive")
        hs = QLabel("Statistics")
        for h in (hd, hs):
            h.setObjectName("SectionHeader")
            h.setAlignment(Qt.AlignCenter)
        grid.addWidget(hd, 0, 0, 1, 4)
        grid.addWidget(hs, 0, 4, 1, 4)
        counters = {"D": 0, "S": 0}
        per_row = 2
        for key, label, section, col, opts in SPECS:
            i = counters[section]
            counters[section] += 1
            r = 1 + i // per_row
            c = (i % per_row) * 2 + (0 if section == "D" else 4)
            lbl = QLabel(label)
            lbl.setObjectName("FilterLabel")
            cb = QComboBox()
            cb.setMinimumWidth(150)
            cb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            for o in opts:
                cb.addItem(o[0])
            cb.currentIndexChanged.connect(lambda _=0, k=key: self._on_combo(k))
            self.combos[key] = cb
            grid.addWidget(lbl, r, c)
            grid.addWidget(cb, r, c + 1)
        outer.addWidget(self.body)

        # saved filters bar
        bar = QFrame()
        bar.setObjectName("SavedBar")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(6, 4, 6, 4)
        self.saved = QComboBox()
        self.saved.setMinimumWidth(200)
        self._refresh_saved()
        self.saved.activated.connect(self._load_selected)
        bl.addWidget(self.saved)
        for text, fn in (("Reload Filter", self._load_selected), ("Save Changes", self._save_changes),
                         ("Delete Filter", self._delete)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            bl.addWidget(b)
        bl.addStretch(1)
        b = QPushButton("▸ Save New Filter")
        b.clicked.connect(self._save_new)
        bl.addWidget(b)
        outer.addWidget(bar)
        self._install_presets()

    # ---------------------------------------------------------------- setup
    def _install_presets(self):
        sf = dict(self.settings["saved_filters"])
        if "_presets_installed" in self.settings.data:
            return
        sf.setdefault("Pre-earnings run-up candidates", {
            "timeframe": "All 'Before' timeframes", "n": "Above 8", "rating": "Buy or better",
            "market_cap": "Over $1 Billion", "earn_date": "Has upcoming date", "best_only": True})
        sf.setdefault("Actionable this week", {
            "timeframe": "All 'Before' timeframes", "entry": "Within 5 sessions", "rating": "Buy or better",
            "n": "Above 8", "best_only": True})
        sf.setdefault("High-confidence (low luck)", {
            "n": "Above 12", "q_value": "Below 0.25", "win_edge": "Above +10 pts", "score": "62+ (Buy)"})
        self.settings.data["_presets_installed"] = True
        self.settings["saved_filters"] = sf
        self._refresh_saved()

    def set_choices(self, sectors: list[str], windows: list[tuple[str, str]], indexes: list[str] | None = None):
        """Populate data-driven options (sectors and timeframes)."""
        def fill(key, items):
            cb = self.combos[key]
            cur = cb.currentText()
            cb.blockSignals(True)
            cb.clear()
            self.options[key] = [(ANY, None, None)] + items
            for o in self.options[key]:
                cb.addItem(o[0])
            i = cb.findText(cur)
            cb.setCurrentIndex(max(i, 0))
            cb.blockSignals(False)
        fill("sector", [(s, "==", s) for s in sorted(set(sectors)) if s])
        idx_items = [(i, "member", i) for i in (indexes or [])]
        if idx_items:
            idx_items += [("In any of these indexes", "nonempty", None), ("Not in any index", "empty", None)]
        fill("index", idx_items)
        groups = []
        for g, lbl in (("Before", "All 'Before' timeframes"), ("Earnings", "All earnings-day timeframes"),
                       ("Hold Through", "All hold-through timeframes"), ("After", "All 'After' timeframes"),
                       ("Custom", "All custom timeframes")):
            if any(w[1] == g for w in windows):
                groups.append((lbl, "group", g))
        fill("timeframe", groups + [(lbl, "==", lbl) for lbl, _ in windows])

    def _on_combo(self, key):
        cb = self.combos[key]
        cb.setProperty("active", cb.currentIndex() > 0)
        cb.style().unpolish(cb)
        cb.style().polish(cb)
        self.changed.emit()

    def _toggle(self):
        vis = not self.body.isVisible()
        self.body.setVisible(vis)
        self.toggle_btn.setText(("▼" if vis else "▶") + " Filters")

    # ---------------------------------------------------------------- state
    def state(self) -> dict:
        st = {k: cb.currentText() for k, cb in self.combos.items() if cb.currentIndex() > 0}
        if self.search.text().strip():
            st["search"] = self.search.text().strip()
        if self.best_only.isChecked():
            st["best_only"] = True
        return st

    def set_state(self, st: dict):
        for k, cb in self.combos.items():
            cb.blockSignals(True)
            i = cb.findText(st.get(k, ANY))
            cb.setCurrentIndex(max(i, 0))
            cb.setProperty("active", cb.currentIndex() > 0)
            cb.style().unpolish(cb)
            cb.style().polish(cb)
            cb.blockSignals(False)
        self.search.blockSignals(True)
        self.search.setText(st.get("search", ""))
        self.search.blockSignals(False)
        self.best_only.blockSignals(True)
        self.best_only.setChecked(bool(st.get("best_only")))
        self.best_only.blockSignals(False)
        self.changed.emit()

    def clear(self):
        self.set_state({})
        self.saved.setCurrentIndex(0)

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return df
        wl = set(self.settings["watchlist"])
        out = df
        for key, label, section, col, _ in SPECS:
            cb = self.combos[key]
            if cb.currentIndex() <= 0:
                continue
            _, op, val = self.options[key][cb.currentIndex()]
            out = apply_rule(out, col, op, val, wl)
        q = self.search.text().strip()
        if q:
            toks = [t.strip().upper() for t in q.replace(",", " ").split() if t.strip()]
            m = out["ticker"].isin(toks)
            if not m.any():  # fall back to a phrase match on name, or ticker prefix
                m = (out["name"].astype(str).str.contains(q, case=False, regex=False)
                     | out["ticker"].str.startswith(q.upper()))
            out = out[m]
        if self.best_only.isChecked() and len(out):
            out = out.sort_values("score", ascending=False, na_position="last").drop_duplicates("ticker")
        return out

    # --------------------------------------------------------- saved filters
    def _refresh_saved(self, select: str | None = None):
        self.saved.blockSignals(True)
        self.saved.clear()
        self.saved.addItem("-Saved Filters-")
        for name in sorted(self.settings["saved_filters"]):
            self.saved.addItem(name)
        if select:
            self.saved.setCurrentIndex(max(0, self.saved.findText(select)))
        self.saved.blockSignals(False)

    def _load_selected(self, *_):
        name = self.saved.currentText()
        st = self.settings["saved_filters"].get(name)
        if st is not None:
            self.set_state(st)

    def _save_new(self):
        name, ok = QInputDialog.getText(self, "Save filter", "Filter name:")
        if ok and name.strip():
            sf = dict(self.settings["saved_filters"])
            sf[name.strip()] = self.state()
            self.settings["saved_filters"] = sf
            self._refresh_saved(name.strip())

    def _save_changes(self):
        name = self.saved.currentText()
        if self.saved.currentIndex() <= 0:
            return self._save_new()
        sf = dict(self.settings["saved_filters"])
        sf[name] = self.state()
        self.settings["saved_filters"] = sf

    def _delete(self):
        name = self.saved.currentText()
        if self.saved.currentIndex() <= 0:
            return
        if QMessageBox.question(self, "Delete filter", f"Delete saved filter '{name}'?") == QMessageBox.Yes:
            sf = dict(self.settings["saved_filters"])
            sf.pop(name, None)
            self.settings["saved_filters"] = sf
            self._refresh_saved()
