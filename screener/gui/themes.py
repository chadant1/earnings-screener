"""Colour themes: Light, Dark, Midnight, Classic, and System (follows Windows light/dark setting).

Every colour used anywhere in the UI (stylesheet, palette, table cells, charts, rich-text labels)
comes from the active theme's token dict, so switching themes recolours everything live.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from functools import lru_cache
from string import Template

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette


@dataclass(frozen=True)
class Theme:
    name: str
    dark: bool
    c: dict

    def __getitem__(self, k: str) -> str:
        return self.c[k]


_COMMON_RATINGS_LIGHT = {
    "r_strong_bg": "#0f7a34", "r_strong_fg": "#ffffff",
    "r_buy_bg": "#b9e6c6", "r_buy_fg": "#0b4d22",
    "r_neutral_bg": "#eceff3", "r_neutral_fg": "#44505c",
    "r_avoid_bg": "#f8d4d4", "r_avoid_fg": "#8a1c1c",
    "r_bear_bg": "#e57373", "r_bear_fg": "#ffffff",
    "r_low_bg": "#f4f4f4", "r_low_fg": "#9aa4ad",
}

LIGHT = Theme("Light", False, {
    "bg": "#f4f6f9", "surface": "#ffffff", "alt": "#f6f9fc", "border": "#d5dce4", "input_border": "#b9c4cf",
    "text": "#24313d", "text_soft": "#33414e", "muted": "#6b7884",
    "toolbar": "#17324d", "toolbar_text": "#ffffff", "toolbar_hover": "#24496d", "toolbar_hover_border": "#35618c",
    "toolbar_disabled": "#7f93a8", "toolbar_label": "#d7e2ec",
    "header": "#17324d", "header_text": "#ffffff", "header_hover": "#24496d", "header_divider": "#2c4d6e",
    "title": "#17324d", "tab_bg": "#e6ebf0", "tab_text": "#4a5866",
    "accent": "#1f6fb2", "accent_hover": "#185a91", "accent_disabled": "#8fb3d3", "accent_text": "#ffffff",
    "active": "#f07f24", "active_bg": "#fffaf5",
    "selection": "#cfe3f7", "selection_text": "#17324d",
    "saved_bar": "#dceaf7", "saved_border": "#c5d8ea",
    "banner_bg": "#fff8e6", "banner_border": "#f0d58c", "banner_text": "#6b5200",
    "summary_bg": "#f7f9fb", "button_hover": "#f2f6fa", "progress": "#3fae6b",
    "up": "#1b8a3a", "down": "#c62828", "warn": "#a06a00", "strong_text": "#333333", "star": "#e0a800",
    "score_pos": "#afe6af", "score_neg": "#ffb9b9",
    "chart_bg": "#ffffff", "chart_ink": "#24313d", "chart_grid": "#e3e8ee", "chart_spine": "#b8c2cc",
    "chart_faint": "#c9d3dd", "chart_zero": "#9aa4ad", "chart_label": "#5a6773",
    "chart_up": "#2e9e55", "chart_down": "#d64545", "chart_accent": "#1f5f99", "chart_accent2": "#e08a1e",
    **_COMMON_RATINGS_LIGHT,
})

CLASSIC = Theme("Classic", False, {
    **LIGHT.c,
    "bg": "#eef1ee", "alt": "#f3f7f4",
    "toolbar": "#24493f", "toolbar_hover": "#2f5c50", "toolbar_hover_border": "#3f7465", "toolbar_label": "#d5e6df",
    "toolbar_disabled": "#86a49a",
    "header": "#2b5246", "header_hover": "#356456", "header_divider": "#3c6a5c", "title": "#24493f",
    "tab_bg": "#e1e8e3", "accent": "#2f7d5c", "accent_hover": "#25664a", "accent_disabled": "#9dc4b2",
    "selection": "#d3eadf", "selection_text": "#1d3d33",
    "saved_bar": "#cfe3f5", "saved_border": "#b5cfe6",
    "chart_accent": "#2b6e55",
})

DARK = Theme("Dark", True, {
    "bg": "#15191e", "surface": "#1d232a", "alt": "#222932", "border": "#313a45", "input_border": "#414c59",
    "text": "#e3e8ee", "text_soft": "#c5ced8", "muted": "#8b97a4",
    "toolbar": "#0f1a26", "toolbar_text": "#e8eef4", "toolbar_hover": "#1f3246", "toolbar_hover_border": "#2d4762",
    "toolbar_disabled": "#5b6b7c", "toolbar_label": "#aebdcc",
    "header": "#243447", "header_text": "#e8eef4", "header_hover": "#2e4259", "header_divider": "#34485e",
    "title": "#9cc8f2", "tab_bg": "#1a2027", "tab_text": "#9aa6b2",
    "accent": "#3d8fd6", "accent_hover": "#5aa3e3", "accent_disabled": "#2b4a66", "accent_text": "#ffffff",
    "active": "#f0913a", "active_bg": "#2a2218",
    "selection": "#2b4a6b", "selection_text": "#ffffff",
    "saved_bar": "#1c2a38", "saved_border": "#2b3d50",
    "banner_bg": "#3a3018", "banner_border": "#6b5a20", "banner_text": "#f0d58c",
    "summary_bg": "#1a2027", "button_hover": "#27303a", "progress": "#3fae6b",
    "up": "#4cc777", "down": "#ef6b6b", "warn": "#e8b04a", "strong_text": "#dfe5eb", "star": "#f2c230",
    "score_pos": "#2c6e44", "score_neg": "#7a3030",
    "chart_bg": "#1d232a", "chart_ink": "#dfe5eb", "chart_grid": "#2c343e", "chart_spine": "#4a5562",
    "chart_faint": "#3a4552", "chart_zero": "#6b7684", "chart_label": "#9aa6b2",
    "chart_up": "#4cc777", "chart_down": "#ef6b6b", "chart_accent": "#5aa3e3", "chart_accent2": "#f0a040",
    "r_strong_bg": "#1e8a45", "r_strong_fg": "#ffffff",
    "r_buy_bg": "#1f4d32", "r_buy_fg": "#9fe3b5",
    "r_neutral_bg": "#2a313a", "r_neutral_fg": "#b8c2cc",
    "r_avoid_bg": "#4d2424", "r_avoid_fg": "#f2a5a5",
    "r_bear_bg": "#a83a3a", "r_bear_fg": "#ffffff",
    "r_low_bg": "#23282e", "r_low_fg": "#6f7a86",
})

MIDNIGHT = Theme("Midnight", True, {
    **DARK.c,
    "bg": "#0b1220", "surface": "#101a2c", "alt": "#13203a", "border": "#1f2e48", "input_border": "#2a3d5c",
    "text": "#dbe6f5", "text_soft": "#b9c8dd", "muted": "#7d8fab",
    "toolbar": "#070d18", "toolbar_hover": "#16284a", "toolbar_hover_border": "#24406b", "toolbar_label": "#9fb3cf",
    "header": "#16284a", "header_hover": "#1f3660", "header_divider": "#24406b",
    "title": "#8cc0ff", "tab_bg": "#0e1728", "tab_text": "#7d8fab",
    "accent": "#2f7de1", "accent_hover": "#4b93ee", "accent_disabled": "#1e3a63",
    "active": "#ffa630", "active_bg": "#241c10",
    "selection": "#1d3a66", "saved_bar": "#0f1c33", "saved_border": "#1f3358",
    "summary_bg": "#0e1728", "button_hover": "#17253f",
    "up": "#34d399", "down": "#f87171", "star": "#fbbf24",
    "score_pos": "#155e46", "score_neg": "#6b2330",
    "chart_bg": "#101a2c", "chart_grid": "#1c2a44", "chart_spine": "#33476a", "chart_faint": "#26385a",
    "chart_up": "#34d399", "chart_down": "#f87171", "chart_accent": "#60a5fa", "chart_accent2": "#fbbf24",
    "r_strong_bg": "#0f8a5f", "r_buy_bg": "#123f35", "r_buy_fg": "#7ee8c0",
    "r_neutral_bg": "#18243a", "r_neutral_fg": "#a9b8cf", "r_avoid_bg": "#43202a", "r_bear_bg": "#b4434f",
    "r_low_bg": "#121c2e", "r_low_fg": "#5d6f8c",
})

THEMES = {t.name: t for t in (LIGHT, DARK, MIDNIGHT, CLASSIC)}
CHOICES = ["System", "Light", "Dark", "Midnight", "Classic"]

_current: list[Theme] = [LIGHT]


def current() -> Theme:
    return _current[0]


@lru_cache(maxsize=512)
def _qcolor(theme_name: str, value: str) -> QColor:
    return QColor(value)


def qc(key: str) -> QColor:
    t = current()
    return _qcolor(t.name, t.c[key])


def blend(a: str, b: str, f: float) -> QColor:
    ca, cb = QColor(a), QColor(b)
    f = max(0.0, min(1.0, f))
    return QColor(int(ca.red() + (cb.red() - ca.red()) * f), int(ca.green() + (cb.green() - ca.green()) * f),
                  int(ca.blue() + (cb.blue() - ca.blue()) * f))


def rating_colors(rating: str) -> tuple[QColor, QColor]:
    key = {"Strong Buy": "strong", "Buy": "buy", "Neutral": "neutral", "Avoid": "avoid",
           "Avoid (Bearish)": "bear", "Low Data": "low"}.get(rating, "neutral")
    return qc(f"r_{key}_bg"), qc(f"r_{key}_fg")


def system_is_dark() -> bool:
    try:
        return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
    except Exception:
        return False


def resolve(name: str) -> Theme:
    if name == "System" or name not in THEMES:
        return DARK if system_is_dark() else LIGHT
    return THEMES[name]


# --------------------------------------------------------------------- QSS
QSS_TEMPLATE = Template("""
* { font-family: "Segoe UI", "Inter", "Helvetica Neue", Arial; font-size: 9.5pt; color: $text; }
QMainWindow, QDialog, QMessageBox { background: $bg; }
QToolBar { background: $toolbar; border: none; padding: 4px 6px; spacing: 6px; }
QToolBar QToolButton { color: $toolbar_text; background: transparent; border: 1px solid transparent;
    border-radius: 4px; padding: 5px 10px; font-weight: 600; }
QToolBar QToolButton:hover { background: $toolbar_hover; border-color: $toolbar_hover_border; }
QToolBar QToolButton:disabled { color: $toolbar_disabled; }
QToolBar QLabel { color: $toolbar_label; }
QToolBar QComboBox { background: $toolbar_hover; color: $toolbar_text; border: 1px solid $toolbar_hover_border;
    border-radius: 4px; padding: 2px 8px; min-width: 96px; }
QToolBar QComboBox QAbstractItemView { background: $surface; color: $text; selection-background-color: $selection;
    selection-color: $selection_text; border: 1px solid $border; }
QToolBar QProgressBar { background: $toolbar_hover; border: none; border-radius: 3px; color: $toolbar_text;
    max-height: 14px; text-align: center; font-size: 8pt; }
QToolBar QProgressBar::chunk { background: $progress; border-radius: 3px; }
QTabWidget::pane { border: 1px solid $border; background: $surface; top: -1px; }
QTabBar::tab { background: $tab_bg; border: 1px solid $border; padding: 7px 16px; margin-right: 2px;
    border-top-left-radius: 5px; border-top-right-radius: 5px; color: $tab_text; }
QTabBar::tab:selected { background: $surface; color: $title; font-weight: 700; border-bottom-color: $surface; }
QTabBar::tab:hover:!selected { color: $text; }
QLabel#SectionHeader { background: $header; color: $header_text; font-weight: 700; padding: 4px; }
QLabel#FilterLabel { color: $text_soft; }
QLabel#SubHeader { font-weight: 700; color: $title; padding: 4px 2px; }
QLabel#CountLabel, QLabel#Muted { color: $muted; padding-right: 8px; }
QLabel#DetailHeader { padding: 4px 10px; }
QLabel#Banner { background: $banner_bg; border: 1px solid $banner_border; border-radius: 4px; padding: 8px;
    color: $banner_text; }
QLabel#Intro { color: $muted; padding: 2px 2px 6px 2px; }
QLabel#SummaryBox { background: $summary_bg; border: 1px solid $border; border-radius: 6px; padding: 10px; }
QFrame#FilterBody { background: $surface; border: 1px solid $border; }
QFrame#SavedBar { background: $saved_bar; border: 1px solid $saved_border; border-top: none; }
QPushButton { background: $surface; border: 1px solid $input_border; border-radius: 4px; padding: 4px 12px; }
QPushButton:hover { border-color: $accent; background: $button_hover; }
QPushButton#Primary { background: $accent; color: $accent_text; border-color: $accent; font-weight: 700;
    padding: 6px 14px; }
QPushButton#Primary:hover { background: $accent_hover; }
QPushButton#Primary:disabled { background: $accent_disabled; border-color: $accent_disabled; }
QPushButton#FilterToggle { border: none; font-weight: 700; color: $title; padding: 4px 6px; background: transparent; }
QComboBox, QLineEdit, QPlainTextEdit { background: $surface; border: 1px solid $input_border;
    border-radius: 3px; padding: 2px 6px; min-height: 20px; }
QComboBox QAbstractItemView { background: $surface; color: $text; selection-background-color: $selection;
    selection-color: $selection_text; border: 1px solid $border; }
QComboBox[active="true"] { border: 2px solid $active; background: $active_bg; }
QComboBox:focus, QLineEdit:focus, QPlainTextEdit:focus { border-color: $accent; }
QTableView { background: $surface; alternate-background-color: $alt; gridline-color: $border;
    selection-background-color: $selection; selection-color: $selection_text; border: 1px solid $border; }
QTableView QTableCornerButton::section { background: $header; border: none; }
QHeaderView { background: $header; }
QHeaderView::section { background: $header; color: $header_text; font-weight: 600; padding: 5px 6px;
    border: none; border-right: 1px solid $header_divider; }
QHeaderView::section:hover { background: $header_hover; }
QGroupBox { font-weight: 700; color: $title; border: 1px solid $border; border-radius: 6px; margin-top: 10px;
    padding-top: 8px; background: $surface; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QStatusBar { background: $tab_bg; color: $muted; }
QSplitter::handle { background: $tab_bg; }
QListWidget { border: 1px solid $border; background: $surface; }
QListWidget::item:selected { background: $selection; color: $selection_text; }
QMenu { background: $surface; border: 1px solid $border; padding: 4px; }
QMenu::item { padding: 4px 18px 4px 24px; }
QMenu::item:selected { background: $selection; color: $selection_text; }
QToolTip { background: $surface; color: $text; border: 1px solid $border; padding: 4px; }
QCheckBox, QRadioButton { background: transparent; spacing: 6px; }
QCheckBox::indicator, QAbstractItemView::indicator { width: 14px; height: 14px; border: 1px solid $check_border;
    border-radius: 3px; background: $surface; }
QCheckBox::indicator:hover, QAbstractItemView::indicator:hover { border-color: $accent; }
QCheckBox::indicator:checked, QAbstractItemView::indicator:checked { background: $accent; border-color: $accent;
    image: url($check_img); }
QRadioButton::indicator { width: 14px; height: 14px; border: 1px solid $check_border; border-radius: 8px;
    background: $surface; }
QRadioButton::indicator:checked { border-color: $accent; background: qradialgradient(cx:0.5, cy:0.5, radius:0.5,
    fx:0.5, fy:0.5, stop:0 $accent, stop:0.45 $accent, stop:0.55 $surface, stop:1 $surface); }
""")


def _asset_path(name: str) -> str:
    from pathlib import Path
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return (base / "assets" / name).as_posix()


def build_qss(t: Theme) -> str:
    tokens = dict(t.c)
    tokens["check_img"] = _asset_path("check.png")
    tokens.setdefault("check_border", "#8a96a3" if not t.dark else "#5d6a79")
    return QSS_TEMPLATE.substitute(tokens)


def build_palette(t: Theme) -> QPalette:
    c = t.c
    p = QPalette()
    roles = {
        QPalette.Window: c["bg"], QPalette.WindowText: c["text"], QPalette.Base: c["surface"],
        QPalette.AlternateBase: c["alt"], QPalette.Text: c["text"], QPalette.Button: c["surface"],
        QPalette.ButtonText: c["text"], QPalette.Highlight: c["accent"], QPalette.HighlightedText: c["accent_text"],
        QPalette.ToolTipBase: c["surface"], QPalette.ToolTipText: c["text"], QPalette.PlaceholderText: c["muted"],
        QPalette.Link: c["accent"], QPalette.BrightText: c["down"], QPalette.Light: c["alt"],
        QPalette.Midlight: c["border"], QPalette.Mid: c["input_border"], QPalette.Dark: c["input_border"],
        QPalette.Shadow: "#000000",
    }
    for role, col in roles.items():
        p.setColor(role, QColor(col))
    for role in (QPalette.Text, QPalette.WindowText, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, QColor(c["muted"]))
    return p


def apply(app, name: str) -> Theme:
    """Apply a theme (or 'System') to the whole application and return the resolved Theme."""
    hints = app.styleHints()
    if hasattr(hints, "setColorScheme"):  # Qt 6.8+: also switches native title bars / dialogs
        try:
            if name == "System":
                hints.unsetColorScheme() if hasattr(hints, "unsetColorScheme") else \
                    hints.setColorScheme(Qt.ColorScheme.Unknown)
        except Exception:
            pass
    t = resolve(name)
    if hasattr(hints, "setColorScheme") and name != "System":
        try:
            hints.setColorScheme(Qt.ColorScheme.Dark if t.dark else Qt.ColorScheme.Light)
        except Exception:
            pass
    _current[0] = t
    app.setPalette(build_palette(t))
    app.setStyleSheet(build_qss(t))
    return t


def set_title_bar_dark(widget, dark: bool) -> None:
    """Windows 10/11: make the native title bar match the theme (no-op elsewhere)."""
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes
        hwnd = int(widget.winId())
        value = ctypes.c_int(1 if dark else 0)
        for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (Win11 / older Win10 builds)
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)) == 0:
                break
    except Exception:
        pass
