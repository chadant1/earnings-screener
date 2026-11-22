"""Backwards-compatible alias: the stylesheet now comes from themes.py."""
from .themes import LIGHT, build_qss

QSS = build_qss(LIGHT)
