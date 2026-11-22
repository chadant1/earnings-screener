"""Trade windows around an earnings event.

Every event has two anchor sessions:
  * "pre"   - the last regular session that closes BEFORE the report hits the market
              (day before for a before-open report, same day for an after-close report)
  * "react" - the first session that trades on the news

A window buys at (anchor + offset, Open|Close) and sells at (anchor + offset, Open|Close),
offsets counted in trading sessions.  Users can add their own windows in the app.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Window:
    key: str
    label: str
    group: str            # Before | Earnings | After | Hold Through | Custom
    entry_anchor: str     # pre | react
    entry_off: int
    entry_field: str      # Open | Close
    exit_anchor: str
    exit_off: int
    exit_field: str
    order: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Window":
        return Window(**{k: d[k] for k in Window.__dataclass_fields__ if k in d})

    @property
    def is_pre_earnings(self) -> bool:
        """Can be entered AND exited before the report (pure run-up trade)."""
        return self.exit_anchor == "pre"

    def describe(self) -> str:
        def side(anchor, off, field):
            a = "pre-earnings session" if anchor == "pre" else "reaction session"
            if off == 0:
                return f"{field.lower()} of {a}"
            return f"{field.lower()} {abs(off)} session{'s' if abs(off) != 1 else ''} {'before' if off < 0 else 'after'} {a}"
        return f"Buy at {side(self.entry_anchor, self.entry_off, self.entry_field)}, " \
               f"sell at {side(self.exit_anchor, self.exit_off, self.exit_field)}"


def _before(n, label, order):
    return Window(f"pre{n}", label, "Before", "pre", -n, "Close", "pre", 0, "Close", order)


def _after(n, label, order):
    return Window(f"post{n}", label, "After", "react", 0, "Close", "react", n, "Close", order)


def _hold(n, label, order):
    return Window(f"hold{n}", label, "Hold Through", "pre", -n, "Close", "react", 0, "Close", order)


DEFAULT_WINDOWS: list[Window] = [
    _before(20, "4 Weeks Before", 1),
    _before(15, "3 Weeks Before", 2),
    _before(10, "2 Weeks Before", 3),
    _before(5, "1 Week Before", 4),
    _before(3, "3 Days Before", 5),
    _before(2, "2 Days Before", 6),
    _before(1, "1 Day Before", 7),
    Window("gap", "Earnings Opening Gap", "Earnings", "pre", 0, "Close", "react", 0, "Open", 10),
    Window("oc", "Earnings Day Open to Close", "Earnings", "react", 0, "Open", "react", 0, "Close", 11),
    Window("move", "Earnings Day Move", "Earnings", "pre", 0, "Close", "react", 0, "Close", 12),
    _hold(1, "Hold Through: 1 Day Before", 20),
    _hold(5, "Hold Through: 1 Week Before", 21),
    _hold(10, "Hold Through: 2 Weeks Before", 22),
    _after(1, "1 Day After", 30),
    _after(2, "2 Days After", 31),
    _after(3, "3 Days After", 32),
    _after(5, "1 Week After", 33),
    _after(10, "2 Weeks After", 34),
    _after(20, "4 Weeks After", 35),
]


def all_windows(custom: list[dict] | None = None) -> list[Window]:
    ws = list(DEFAULT_WINDOWS)
    for i, d in enumerate(custom or []):
        try:
            w = Window.from_dict({**d, "group": "Custom", "order": 100 + i})
            ws.append(w)
        except Exception:
            continue
    return ws
