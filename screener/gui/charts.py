"""Matplotlib charts embedded in Qt."""
from __future__ import annotations

import matplotlib

matplotlib.use("QtAgg")
import matplotlib.dates as mdates  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

UP = "#2e9e55"
DOWN = "#d64545"
INK = "#24313d"
GRID = "#e3e8ee"
ACCENT = "#1f5f99"
ACCENT2 = "#e08a1e"
pct_fmt = FuncFormatter(lambda v, _: f"{v * 100:.0f}%")


class Chart(FigureCanvasQTAgg):
    def __init__(self, parent=None, height=3.2):
        self.fig = Figure(figsize=(6, height), dpi=100, facecolor="white", layout="constrained")
        super().__init__(self.fig)
        self.setParent(parent)

    def _ax(self):
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color("#b8c2cc")
        ax.tick_params(colors=INK, labelsize=8)
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        return ax

    def message(self, text: str):
        ax = self._ax()
        ax.axis("off")
        ax.text(0.5, 0.5, text, ha="center", va="center", color="#7a8794", fontsize=10, transform=ax.transAxes)
        self.draw_idle()

    # ------------------------------------------------------------- charts
    def event_bars(self, wr: pd.DataFrame, title: str):
        if wr is None or wr.empty:
            return self.message("No events for this timeframe")
        ax = self._ax()
        r = wr["ret"].values
        x = np.arange(len(r))
        ax.bar(x, r, color=[UP if v > 0 else DOWN for v in r], width=0.75)
        ax.axhline(0, color="#9aa4ad", linewidth=0.8)
        ax.axhline(r.mean(), color=ACCENT, linewidth=1.2, linestyle="--", label=f"Avg {r.mean() * 100:+.2f}%")
        labels = pd.to_datetime(wr["event_date"]).dt.strftime("%b '%y")
        step = max(1, len(x) // 12)
        ax.set_xticks(x[::step])
        ax.set_xticklabels(labels.values[::step], rotation=0, fontsize=7.5)
        ax.yaxis.set_major_formatter(pct_fmt)
        ax.set_title(title, fontsize=10, color=INK, loc="left", fontweight="bold")
        ax.legend(frameon=True, framealpha=0.9, edgecolor="none", fontsize=8, loc="best")
        self.draw_idle()

    def avg_path(self, paths: pd.DataFrame, title: str):
        if paths is None or paths.empty:
            return self.message("No events")
        ax = self._ax()
        x = paths.index.values
        for c in paths.columns:
            ax.plot(x, paths[c].values, color="#c9d3dd", linewidth=0.6, alpha=0.7)
        ax.plot(x, paths.mean(axis=1).values, color=ACCENT, linewidth=2.2, label="Average")
        ax.plot(x, paths.median(axis=1).values, color=ACCENT2, linewidth=1.8, linestyle="--", label="Median")
        ax.axvline(0, color=INK, linewidth=0.8, linestyle=":")
        ax.axvline(1, color=DOWN, linewidth=0.8, linestyle=":")
        ax.axhline(0, color="#9aa4ad", linewidth=0.8)
        q = np.nanpercentile(paths.values, [5, 95])
        ax.set_ylim(q[0] * 1.3, q[1] * 1.3)
        ax.yaxis.set_major_formatter(pct_fmt)
        ax.set_xlabel("Sessions relative to last close before the report (0)  ·  1 = reaction day",
                      fontsize=8, color="#5a6773")
        ax.set_title(title, fontsize=10, color=INK, loc="left", fontweight="bold")
        ax.legend(frameon=False, fontsize=8, loc="upper left")
        self.draw_idle()

    def price(self, prices: pd.DataFrame, events: pd.DataFrame, title: str, years: float = 3):
        if prices is None or prices.empty:
            return self.message("No price data")
        ax = self._ax()
        start = prices.index[-1] - pd.Timedelta(days=int(365 * years))
        p = prices[prices.index >= start]
        ax.plot(p.index, p["Close"], color=ACCENT, linewidth=1.2)
        if events is not None and len(events):
            ev = events[events["react_date"] >= start]
            y = p["Close"].reindex(ev["react_date"]).values
            ax.scatter(ev["react_date"], y, color=ACCENT2, s=22, zorder=3, label="Earnings reaction day")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
        ax.set_title(title, fontsize=10, color=INK, loc="left", fontweight="bold")
        ax.legend(frameon=False, fontsize=8, loc="upper left")
        self.draw_idle()

    def equity(self, curves: dict[str, pd.DataFrame], title: str):
        ax = self._ax()
        colors = [ACCENT, "#9aa4ad", ACCENT2]
        drawn = False
        for (name, c), col in zip(curves.items(), colors):
            if c is None or c.empty:
                continue
            ax.plot(pd.to_datetime(c["date"]), c["cum"], label=name, color=col, linewidth=1.8)
            drawn = True
        if not drawn:
            return self.message("No trades matched these rules")
        ax.axhline(0, color="#9aa4ad", linewidth=0.8)
        ax.yaxis.set_major_formatter(pct_fmt)
        ax.set_ylabel("Cumulative return (sum of trades)", fontsize=8, color="#5a6773")
        ax.set_title(title, fontsize=10, color=INK, loc="left", fontweight="bold")
        ax.legend(frameon=False, fontsize=8, loc="upper left")
        self.draw_idle()

    def buckets(self, df: pd.DataFrame, title: str):
        if df is None or df.empty:
            return self.message("No data")
        ax = self._ax()
        x = np.arange(len(df))
        v = df["avg"].fillna(0).values
        ax.bar(x, v, color=[UP if a > 0 else DOWN for a in v], width=0.6)
        for i, (a, n, w) in enumerate(zip(v, df["trades"], df["win_rate"])):
            if n:
                ax.text(i, a, f"{w * 100:.0f}% win\n{n} trades", ha="center",
                        va="bottom" if a >= 0 else "top", fontsize=7.5, color=INK)
        lo, hi = min(0, v.min()), max(0, v.max())
        pad = (hi - lo) * 0.18 or 0.01
        ax.set_ylim(lo - pad, hi + pad)
        ax.set_xticks(x)
        ax.set_xticklabels(df["bucket"].astype(str), fontsize=8)
        ax.axhline(0, color="#9aa4ad", linewidth=0.8)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v * 100:.1f}%"))
        ax.set_xlabel("Score at time of entry (computed with prior data only)", fontsize=8, color="#5a6773")
        ax.set_title(title, fontsize=10, color=INK, loc="left", fontweight="bold")
        self.draw_idle()
