"""pandas-backed Qt table model with formatting, colouring and sorting."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QBrush, QColor, QFont

from .columns import Col

GREEN = QColor("#1b8a3a")
RED = QColor("#c62828")
MUTED = QColor("#7a8794")
RATING_COLORS = {
    "Strong Buy": ("#0f7a34", "#ffffff"),
    "Buy": ("#b9e6c6", "#0b4d22"),
    "Neutral": ("#eceff3", "#44505c"),
    "Avoid": ("#f8d4d4", "#8a1c1c"),
    "Avoid (Bearish)": ("#e57373", "#ffffff"),
    "Low Data": ("#f4f4f4", "#9aa4ad"),
}


def _isnan(v) -> bool:
    try:
        return v is None or (isinstance(v, float) and math.isnan(v)) or v is pd.NaT or pd.isna(v)
    except (TypeError, ValueError):
        return False


def fmt_value(v, kind: str) -> str:
    if kind == "watch":
        return "★" if v else "☆"
    if _isnan(v):
        return "–"
    try:
        if kind == "pct":
            return f"{v * 100:+.1f}%"
        if kind == "pctp":
            return f"{v * 100:.1f}%"
        if kind == "num":
            if np.isinf(v):
                return "∞"
            return f"{v:.2f}"
        if kind == "int":
            return f"{int(v)}"
        if kind == "score":
            return f"{v:.0f}"
        if kind == "pval":
            return f"{v:.3f}" if v >= 0.001 else "<0.001"
        if kind == "cap":
            v = float(v)
            for div, suf in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
                if abs(v) >= div:
                    return f"{v / div:.1f} {suf}"
            return f"{v:,.0f}"
        if kind == "vol":
            v = float(v)
            for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
                if abs(v) >= div:
                    return f"{v / div:.1f}{suf}"
            return f"{v:,.0f}"
        if kind == "date":
            return pd.Timestamp(v).strftime("%a %b %d, %Y")
        if kind == "bool":
            return "Yes" if bool(v) else "No"
    except (TypeError, ValueError, OverflowError):
        return str(v)
    return str(v)


class DataFrameModel(QAbstractTableModel):
    def __init__(self, cols: list[Col], parent=None, watchlist_getter=None):
        super().__init__(parent)
        self.cols = cols
        self.df = pd.DataFrame()
        self._watch = watchlist_getter or (lambda: set())
        self._bold = QFont()
        self._bold.setBold(True)

    # ---------------------------------------------------------------- data
    def set_df(self, df: pd.DataFrame | None) -> None:
        self.beginResetModel()
        self.df = (df if df is not None else pd.DataFrame()).reset_index(drop=True)
        self.endResetModel()

    def row(self, r: int) -> pd.Series:
        return self.df.iloc[r]

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.df)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.cols)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal:
            c = self.cols[section]
            if role == Qt.DisplayRole:
                return c.header
            if role == Qt.ToolTipRole and c.tip:
                return c.tip
        return None

    def _value(self, r: int, c: Col):
        if c.kind == "watch":
            return self.df.at[r, "ticker"] in self._watch() if "ticker" in self.df else False
        return self.df.at[r, c.key] if c.key in self.df.columns else None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        c = self.cols[index.column()]
        v = self._value(index.row(), c)
        if role == Qt.DisplayRole:
            return fmt_value(v, c.kind)
        if role == Qt.TextAlignmentRole:
            if c.kind in ("text", "plan"):
                return int(Qt.AlignLeft | Qt.AlignVCenter)
            return int(Qt.AlignCenter)
        if role == Qt.ForegroundRole:
            if c.kind == "watch":
                return QBrush(QColor("#e0a800")) if v else QBrush(MUTED)
            if _isnan(v):
                return QBrush(MUTED)
            if c.kind == "pct" and isinstance(v, (int, float, np.floating)):
                return QBrush(GREEN if v > 0 else RED if v < 0 else MUTED)
            if c.key in ("win_rate", "wilson_lb", "beat_bench", "last4", "prior_win"):
                return QBrush(GREEN if v >= 0.6 else RED if v < 0.45 else QColor("#333"))
            if c.kind == "rating":
                return QBrush(QColor(RATING_COLORS.get(v, ("#fff", "#333"))[1]))
            if c.key == "q_value":
                return QBrush(GREEN if v < 0.1 else QColor("#333") if v < 0.5 else MUTED)
            if c.key == "days_to_entry" and v is not None:
                return QBrush(GREEN if 0 <= v <= 2 else MUTED if v < 0 else QColor("#333"))
        if role == Qt.BackgroundRole:
            if c.kind == "rating" and not _isnan(v):
                return QBrush(QColor(RATING_COLORS.get(v, ("#fff", "#333"))[0]))
            if c.kind == "score" and not _isnan(v):
                x = max(0.0, min(1.0, (float(v) - 50) / 40))
                y = max(0.0, min(1.0, (50 - float(v)) / 40))
                if x > 0:
                    return QBrush(QColor(int(255 - 80 * x), int(255 - 25 * x), int(255 - 80 * x)))
                if y > 0:
                    return QBrush(QColor(255, int(255 - 70 * y), int(255 - 70 * y)))
        if role == Qt.FontRole and c.kind in ("rating", "score") or (role == Qt.FontRole and c.key == "ticker"):
            return self._bold
        if role == Qt.ToolTipRole:
            if c.key == "window" and "window_desc" in self.df.columns:
                return self.df.at[index.row(), "window_desc"]
            if c.kind == "plan":
                return fmt_value(v, "text")
        if role == Qt.UserRole:
            return v
        return None

    # ---------------------------------------------------------------- sort
    def sort(self, column: int, order=Qt.AscendingOrder) -> None:
        if self.df.empty:
            return
        c = self.cols[column]
        key = {"rating": "rating_rank", "watch": None}.get(c.kind, c.key)
        if c.kind == "watch":
            wl = self._watch()
            s = self.df["ticker"].isin(wl)
            idx = s.sort_values(ascending=(order == Qt.AscendingOrder), kind="stable").index
        elif key in self.df.columns:
            idx = self.df[key].sort_values(ascending=(order == Qt.AscendingOrder), na_position="last",
                                           kind="stable").index
        else:
            return
        self.layoutAboutToBeChanged.emit()
        self.df = self.df.loc[idx].reset_index(drop=True)
        self.layoutChanged.emit()
