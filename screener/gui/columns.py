"""Column definitions shared by the tables (header, format, tooltip)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Col:
    key: str
    header: str
    kind: str = "text"   # text pct pctp num int cap vol date bool rating score watch pval plan
    tip: str = ""
    hidden: bool = False


C = {c.key: c for c in [
    Col("watch", "★", "watch", "Click to add/remove from your watchlist"),
    Col("ticker", "Symbol", "text"),
    Col("name", "Company", "text"),
    Col("sector", "Sector", "text"),
    Col("indexes", "Indexes", "text", "Index memberships (from downloaded index lists)"),
    Col("exchange", "Exchange", "text", "Primary listing exchange", hidden=True),
    Col("market_cap", "Mkt Cap", "cap"),
    Col("avg_volume", "Avg Vol", "vol", "3-month average daily share volume"),
    Col("window", "Timeframe", "text", "Trade window relative to the earnings report"),
    Col("n", "# Obs", "int", "Number of past earnings events measured"),
    Col("win_rate", "Win %", "pctp", "Share of events where the window return was positive"),
    Col("avg", "Avg", "pct", "Average window return"),
    Col("median", "Median", "pct", "Median window return (less affected by outliers)"),
    Col("best", "Best", "pct"),
    Col("worst", "Worst", "pct"),
    Col("abs_avg", "Abs Avg", "pctp", "Average size of the move, ignoring direction"),
    Col("abs_low", "Abs Low", "pctp", hidden=True),
    Col("abs_high", "Abs High", "pctp", hidden=True),
    Col("std", "Std Dev", "pctp", "Standard deviation of window returns"),
    Col("sharpe", "Sharpe", "num", "Average return / standard deviation (per trade)"),
    Col("wilson_lb", "Win % Low", "pctp",
        "Conservative win rate: 95% one-sided lower bound (Wilson). Small samples get pulled down."),
    Col("base_win", "Normal Win %", "pctp",
        "How often this stock is up over the same holding length on ANY day. The pattern needs to beat this."),
    Col("win_edge", "Win Edge", "pct", "Win % minus Normal Win % (earnings-specific edge)"),
    Col("avg_edge", "Avg Edge", "pct", "Average return minus the stock's normal return for this holding length", hidden=True),
    Col("beat_bench", "Beat SPY %", "pctp", "How often the window beat SPY over the exact same dates"),
    Col("avg_excess", "Avg vs SPY", "pct", "Average return in excess of SPY over the same dates"),
    Col("profit_factor", "Profit Factor", "num", "Sum of gains / sum of losses"),
    Col("avg_mae", "Avg Drawdown", "pct", "Average worst intraperiod dip from entry while holding (MAE)"),
    Col("last4", "Last 4 Win", "pctp", "Win rate over the most recent 4 events"),
    Col("last_ret", "Last", "pct", "Return in the most recent event", hidden=True),
    Col("t_stat", "t-stat", "num", "t-statistic of returns vs the stock's normal drift", hidden=True),
    Col("p_value", "p-value", "pval", "Chance of a result this good from normal drift alone (one-sided)", hidden=True),
    Col("q_value", "q-value", "pval",
        "False-discovery-rate adjusted p-value across everything screened. Lower = less likely to be luck."),
    Col("score", "Score", "score", "0-100 composite. 50 = no edge. 62+ Buy, 75+ Strong Buy."),
    Col("short_score", "Short Score", "score", "Same score for the short side", hidden=True),
    Col("rating", "Rating", "rating"),
    Col("next_earnings", "Next Earnings", "date"),
    Col("next_timing", "Time", "text", "BMO = before market open, AMC = after market close"),
    Col("confirmed", "Confirmed", "bool", "Yahoo shows a single date (confirmed) vs a date range (estimated)"),
    Col("days_to_earnings", "Days to Earn", "int", "Calendar days until the next report"),
    Col("entry_date", "Entry Date", "date", "When this window would be entered for the next report"),
    Col("exit_date", "Exit Date", "date"),
    Col("days_to_entry", "Sessions to Entry", "int", "Trading sessions from today until entry (0 = today/next session)"),
    Col("hist_move", "Hist Move", "pctp", "Average absolute earnings-day move historically"),
    Col("implied_move", "Implied Move", "pctp", "Options-implied earnings move (ATM straddle). Needs 'Fetch options data'."),
    Col("implied_vs_hist", "Implied/Hist", "num", "Below 1 = options pricing a smaller move than history", hidden=True),
    Col("option_volume", "Opt Vol", "vol", "Option volume (nearest expiry). Needs 'Fetch options data'."),
    Col("plan", "Trade Plan", "plan"),
]}

SCREENER_COLS = ["watch", "ticker", "name", "sector", "indexes", "exchange", "market_cap", "window", "n", "win_rate", "avg", "median",
                 "best", "worst", "abs_avg", "abs_low", "abs_high", "std", "sharpe", "wilson_lb", "base_win",
                 "win_edge", "avg_edge", "beat_bench", "avg_excess", "profit_factor", "avg_mae", "last4",
                 "last_ret", "t_stat", "p_value", "q_value", "score", "short_score", "rating", "next_earnings",
                 "next_timing", "confirmed", "days_to_earnings", "entry_date", "exit_date", "days_to_entry",
                 "hist_move", "implied_move", "implied_vs_hist", "option_volume", "avg_volume"]

OPPORTUNITY_COLS = ["watch", "ticker", "name", "rating", "score", "window", "plan", "days_to_entry", "entry_date",
                    "exit_date", "next_earnings", "next_timing", "confirmed", "n", "win_rate", "wilson_lb",
                    "base_win", "avg", "median", "worst", "avg_mae", "beat_bench", "q_value", "market_cap", "indexes",
                    "hist_move", "implied_move"]

DETAIL_COLS = ["window", "n", "win_rate", "avg", "median", "best", "worst", "std", "sharpe", "wilson_lb", "base_win",
               "win_edge", "beat_bench", "avg_excess", "profit_factor", "avg_mae", "last4", "q_value", "score",
               "short_score", "rating", "entry_date", "exit_date"]

EVENT_COLS = [
    Col("date", "Report Date", "date"), Col("timing", "Time", "text"),
    Col("inferred", "Time Inferred", "bool", "Timing missing from data and inferred from which session gapped"),
    Col("eps_est", "EPS Est", "num"), Col("eps_act", "EPS Actual", "num"), Col("surprise", "Surprise %", "num"),
    Col("run_up_5d", "Run-up 5d", "pct"), Col("gap", "Gap", "pct"), Col("open_to_close", "Open→Close", "pct"),
    Col("day_move", "Day Move", "pct"), Col("drift_5d", "Drift 5d", "pct"),
]

TRADE_COLS = [
    Col("ticker", "Symbol"), Col("window", "Timeframe"), Col("event_date", "Report", "date"),
    Col("entry_date", "Entry", "date"), Col("exit_date", "Exit", "date"), Col("ret", "Net Return", "pct"),
    Col("excess", "vs SPY", "pct"), Col("score", "Score at Entry", "score"), Col("prior_n", "Prior Obs", "int"),
    Col("prior_win", "Prior Win %", "pctp"),
]
