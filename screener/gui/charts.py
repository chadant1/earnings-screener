"""Matplotlib charts embedded in Qt (colours follow the active theme)."""
from __future__ import annotations

import functools

import matplotlib

matplotlib.use("QtAgg")
import matplotlib.dates as mdates  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

from . import themes  # noqa: E402

pct_fmt = FuncFormatter(lambda v, _: f"{v * 100:.0f}%")


def _remember(fn):
    """Record the last drawing call so the chart can be redrawn after a theme change."""
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        self._last = (fn, args, kwargs)
        return fn(self, *args, **kwargs)
    return wrapper


class Chart(FigureCanvasQTAgg):
    def __init__(self, parent=None, height=3.2):
        self.fig = Figure(figsize=(6, height), dpi=100, layout="constrained")
        super().__init__(self.fig)
        self.setParent(parent)
        self._last = None

    def redraw(self):
        if self._last:
            fn, args, kwargs = self._last
            fn(self, *args, **kwargs)

    @staticmethod
    def _c(key: str) -> str:
        return themes.current()[key]

    def _ax(self):
        c = self._c
        self.fig.clear()
        self.fig.set_facecolor(c("chart_bg"))
        ax = self.fig.add_subplot(111)
        ax.set_facecolor(c("chart_bg"))
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color(c("chart_spine"))
        ax.tick_params(colors=c("chart_ink"), labelsize=8)
        ax.grid(axis="y", color=c("chart_grid"), linewidth=0.8)
        ax.set_axisbelow(True)
        return ax

    def _title(self, ax, text):
        ax.set_title(text, fontsize=10, color=self._c("chart_ink"), loc="left", fontweight="bold")

    def _legend(self, ax, loc="upper left"):
        leg = ax.legend(frameon=True, framealpha=0.85, edgecolor="none", fontsize=8, loc=loc,
                        facecolor=self._c("chart_bg"))
        for t in leg.get_texts():
            t.set_color(self._c("chart_ink"))

    def _xlabel(self, ax, text):
        ax.set_xlabel(text, fontsize=8, color=self._c("chart_label"))

    @_remember
    def message(self, text: str):
        ax = self._ax()
        ax.axis("off")
        ax.text(0.5, 0.5, text, ha="center", va="center", color=self._c("chart_label"), fontsize=10,
                transform=ax.transAxes)
        self.draw_idle()

    # ------------------------------------------------------------- charts
    @_remember
    def event_bars(self, wr: pd.DataFrame, title: str):
        if wr is None or wr.empty:
            return self.message("No events for this timeframe")
        c = self._c
        ax = self._ax()
        r = wr["ret"].values
        x = np.arange(len(r))
        ax.bar(x, r, color=[c("chart_up") if v > 0 else c("chart_down") for v in r], width=0.75)
        ax.axhline(0, color=c("chart_zero"), linewidth=0.8)
        ax.axhline(r.mean(), color=c("chart_accent"), linewidth=1.2, linestyle="--", label=f"Avg {r.mean() * 100:+.2f}%")
        labels = pd.to_datetime(wr["event_date"]).dt.strftime("%b '%y")
        step = max(1, len(x) // 12)
        ax.set_xticks(x[::step])
        ax.set_xticklabels(labels.values[::step], rotation=0, fontsize=7.5)
        ax.yaxis.set_major_formatter(pct_fmt)
        self._title(ax, title)
        self._legend(ax, "best")
        self.draw_idle()

    @_remember
    def avg_path(self, paths: pd.DataFrame, title: str):
        if paths is None or paths.empty:
            return self.message("No events")
        c = self._c
        ax = self._ax()
        x = paths.index.values
        for col in paths.columns:
            ax.plot(x, paths[col].values, color=c("chart_faint"), linewidth=0.6, alpha=0.7)
        ax.plot(x, paths.mean(axis=1).values, color=c("chart_accent"), linewidth=2.2, label="Average")
        ax.plot(x, paths.median(axis=1).values, color=c("chart_accent2"), linewidth=1.8, linestyle="--", label="Median")
        ax.axvline(0, color=c("chart_ink"), linewidth=0.8, linestyle=":")
        ax.axvline(1, color=c("chart_down"), linewidth=0.8, linestyle=":")
        ax.axhline(0, color=c("chart_zero"), linewidth=0.8)
        q = np.nanpercentile(paths.values, [5, 95])
        ax.set_ylim(q[0] * 1.3, q[1] * 1.3)
        ax.yaxis.set_major_formatter(pct_fmt)
        self._xlabel(ax, "Sessions relative to last close before the report (0)  ·  1 = reaction day")
        self._title(ax, title)
        self._legend(ax)
        self.draw_idle()

    @_remember
    def price(self, prices: pd.DataFrame, events: pd.DataFrame, title: str, years: float = 3):
        if prices is None or prices.empty:
            return self.message("No price data")
        c = self._c
        ax = self._ax()
        start = prices.index[-1] - pd.Timedelta(days=int(365 * years))
        p = prices[prices.index >= start]
        ax.plot(p.index, p["Close"], color=c("chart_accent"), linewidth=1.2)
        if events is not None and len(events):
            ev = events[events["react_date"] >= start]
            y = p["Close"].reindex(ev["react_date"]).values
            ax.scatter(ev["react_date"], y, color=c("chart_accent2"), s=22, zorder=3, label="Earnings reaction day")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
        self._title(ax, title)
        self._legend(ax)
        self.draw_idle()

    @_remember
    def equity(self, curves: dict[str, pd.DataFrame], title: str):
        c = self._c
        ax = self._ax()
        colors = [c("chart_accent"), c("chart_zero"), c("chart_accent2")]
        drawn = False
        for (name, cv), col in zip(curves.items(), colors):
            if cv is None or cv.empty:
                continue
            ax.plot(pd.to_datetime(cv["date"]), cv["cum"], label=name, color=col, linewidth=1.8)
            drawn = True
        if not drawn:
            return self.message("No trades matched these rules")
        ax.axhline(0, color=c("chart_zero"), linewidth=0.8)
        ax.yaxis.set_major_formatter(pct_fmt)
        ax.set_ylabel("Cumulative return (sum of trades)", fontsize=8, color=c("chart_label"))
        self._title(ax, title)
        self._legend(ax)
        self.draw_idle()

    @_remember
    def buckets(self, df: pd.DataFrame, title: str):
        if df is None or df.empty:
            return self.message("No data")
        c = self._c
        ax = self._ax()
        x = np.arange(len(df))
        v = df["avg"].fillna(0).values
        ax.bar(x, v, color=[c("chart_up") if a > 0 else c("chart_down") for a in v], width=0.6)
        for i, (a, n, w) in enumerate(zip(v, df["trades"], df["win_rate"])):
            if n:
                ax.text(i, a, f"{w * 100:.0f}% win\n{n} trades", ha="center",
                        va="bottom" if a >= 0 else "top", fontsize=7.5, color=c("chart_ink"))
        lo, hi = min(0, v.min()), max(0, v.max())
        pad = (hi - lo) * 0.18 or 0.01
        ax.set_ylim(lo - pad, hi + pad)
        ax.set_xticks(x)
        ax.set_xticklabels(df["bucket"].astype(str), fontsize=8)
        ax.axhline(0, color=c("chart_zero"), linewidth=0.8)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda val, _: f"{val * 100:.1f}%"))
        self._xlabel(ax, "Score at time of entry (computed with prior data only)")
        self._title(ax, title)
        self.draw_idle()
