# Earnings Pattern Screener

A standalone Windows desktop app that studies how stocks have traded around their past earnings reports and **rates whether buying a set number of days before the next report has had the odds in your favor**.

It does what classic earnings-pattern screeners do (win rate, average, median, best, worst, standard deviation and Sharpe for windows like *1 Week Before* or *Day of Earnings Opening Gap*), and adds checks against false patterns:

| Classic screener | This app adds |
|---|---|
| Win rate | **Normal win rate**: how often the stock is up over the same number of days on *any* day. A 65% earnings win rate means nothing if the stock is up 65% of the time anyway. |
| Avg return | **Return vs SPY** over the exact same dates, so a strong market doesn't count as an earnings edge. |
| # of observations | **Small-sample penalty**: a conservative (Wilson) win rate, and a score pulled toward neutral when there are few events. |
| – | **Luck filter (q-value)**: corrects for testing thousands of stock/timeframe combinations, where some will look great by chance. |
| – | **Score 0–100 and Rating** (Strong Buy / Buy / Neutral / Avoid / Avoid (Bearish) / Low Data). |
| – | **Trade plan**: exact buy and sell dates for the *next* report on the NYSE trading calendar. |
| – | **Walk-forward backtest**: re-scores every past report using only data available at the time, so you can check whether the ratings actually predicted anything. |
| – | **Average drawdown while holding (MAE)**, profit factor, results over the last 4 reports, implied vs. historical move. |
| – | **Custom timeframes**: e.g. buy 7 sessions before and sell at the open of the reaction day. |

> ⚠️ **Not financial advice.** Historical patterns can and do stop working. Always confirm the earnings date and size each position for the worst case.

---

## Quick start (Windows)

1. Install **Python 3.10–3.13** from <https://www.python.org/downloads/>. During setup, tick **"Add python.exe to PATH"**.
2. Download this repo (green **Code** button → *Download ZIP*) and unzip it, or `git clone` it.
3. Double-click **`run.bat`**. The first launch sets up a private Python environment, which takes a few minutes.
4. In the app, click **⟳ Update Data**. The first download for about 260 stocks takes roughly 5–15 minutes. After that, only stale data is refreshed.

Want to try it without internet first? Run `run.bat --demo` to load simulated data.

### Make it a real desktop app (.exe)

After `run.bat` has worked once, double-click **`build_exe.bat`**. It creates `dist\EarningsScreener\EarningsScreener.exe` and a **Desktop shortcut**. The `dist\EarningsScreener` folder runs on its own without Python, so you can move it anywhere.

---

## Using the app

### Opportunities tab
Buy-rated setups whose **entry date for the next report** falls within the next *N* trading sessions (default 10). Each row has a plain-English **Trade Plan**, e.g. `Buy close Mon Nov 23 → Sell close Tue Dec 01`. Options:
- *Best timeframe per stock*: show only the strongest window for each stock.
- *Include hold-through timeframes*: by default, only trades that exit **before** the report are listed.
- *Confirmed dates only* and *Watchlist only*.

### Screener tab
Laid out like the screener you're used to, with Descriptive and Statistics filters. Active filters are outlined in orange. You can also:
- Search by ticker or company name; tick *Best timeframe per stock only*.
- Use **saved filters**, including built-in presets: *Pre-earnings run-up candidates*, *Actionable this week* and *High-confidence (low luck)*.
- Click a column header to sort. **Right-click a header** to show or hide columns, such as Abs Low/High, p-value, Short Score and Implied/Hist.
- Click ☆ to add a stock to your watchlist. Double-click a row to open the stock's detail view.

### Stock Detail tab
Every timeframe for one stock, plus:
- **Returns by Event** bar chart for the selected timeframe.
- **Average Path Around Earnings**: mean and median price path from 20 sessions before to 10 sessions after the report, drawn over each individual report.
- **Price History** with earnings reaction days marked.
- **Earnings history**: date, before/after market, EPS estimate/actual/surprise, 5-day run-up, gap, open→close, day move and 5-day drift.

### Backtest tab
Pick timeframes and rules (minimum score, minimum prior events, lookback, long or short, costs). Each past report is **re-scored using only reports that had already closed before entry**. Results compare *Selected by rules* against *Every event*, and include:
- An equity curve.
- A **Score Calibration** chart: if higher score buckets don't show better future returns, don't trust the scores.
- A by-year table and the full trade list (exportable).

### Toolbar
- **Universe…**: the built-in list of about 260 liquid, optionable stocks, the S&P 500 (downloaded from Wikipedia), or your own list (paste or import a .txt/.csv). Your watchlist is always included.
- **Custom Timeframes…**: build your own buy and sell rules.
- **Settings…**: years of history (default 10), minimum events for a rating, round-trip trading cost (default 10 bps), opportunity horizon, refresh age, parallel downloads, benchmark, **option data** (option volume and implied earnings move, slower), and an optional **Alpha Vantage** key.
- **Export…**: saves the current table to Excel or CSV.
- **Theme**: **System** (follows your Windows light/dark setting, including when it changes), **Light**, **Dark**, **Midnight** (dark navy, trading-terminal style) or **Classic** (green headers like traditional screeners). The switch is instant, recolors tables, charts, dialogs and the Windows title bar, and is remembered. **Ctrl+Shift+T** cycles through themes.

---

## How the analysis works

**1. Lining up each report.** Each report gets two sessions:
- The **pre-earnings session**: the last close before the news. For a before-open report, that's the day before; for an after-close report, it's the same day.
- The **reaction session**: the first session that trades on the news.

Report times come from Yahoo. When the time is missing, the app infers it from which session had the bigger opening gap. The *Time Inferred* column shows when that happened.

**2. Timeframes** (all counted in trading sessions):

| Group | Timeframes | Trade |
|---|---|---|
| Before | 1, 2, 3 days; 1, 2, 3, 4 weeks before | Buy at the close N sessions before the pre-earnings session; sell at the pre-earnings close. **You are out before the report.** |
| Earnings | Opening Gap, Open→Close, Day Move | The reaction itself |
| Hold Through | 1 day, 1 week, 2 weeks before | Buy before, hold through the report, sell at the reaction-day close |
| After | 1, 2, 3 days; 1, 2, 4 weeks after | Post-earnings drift from the reaction-day close |
| Custom | yours | any entry/exit anchor, offset and open/close |

**3. Score (0–100, 50 = no edge)**, after your trading-cost setting:

| Weight | Component |
|---|---|
| 25% | Win rate shrunk toward 50% for small samples |
| 15% | Win rate edge over the stock's normal win rate for that holding length |
| 20% | t-stat of return in excess of SPY |
| 15% | Profit factor (log scale) |
| 15% | Consistency over the last 4 and 8 reports |
| 10% | Reward/risk (Sharpe per trade) |

With fewer than 12 events, the score is pulled toward 50. Ratings: **Strong Buy ≥ 75 · Buy ≥ 62 · Neutral ≥ 40 · Avoid < 40**. **Avoid (Bearish)** means the short side scores ≥ 62. A stock with fewer events than your minimum (default 8) shows **Low Data**.

**4. Luck filter.** Each pattern gets a one-sided p-value: could returns this good come from the stock's normal drift? Benjamini-Hochberg **q-values** then adjust for screening everything at once. A q-value below 0.10 means the pattern is unlikely to be pure luck.

---

## Data sources and limitations
- **Yahoo Finance** via [`yfinance`](https://github.com/ranaroussi/yfinance): split- and dividend-adjusted daily prices, earnings dates with report time and EPS, next earnings date, market cap, and options. It's free and needs no key, but it is unofficial. If downloads start failing after Yahoo changes something, run `run.bat --update` to upgrade yfinance.
- Yahoo returns up to about 100 past report dates per stock, which is plenty for the default 10 years.
- **Confirmed?** is a heuristic: Yahoo shows a single date when a report date is confirmed and a date range when it's estimated.
- **Alpha Vantage** (optional free key) is only used as a fallback when Yahoo has fewer than 4 earnings dates for a stock. The free tier allows about 25 calls per day.
- Daily data only, so intraday entries are limited to open and close. Survivorship bias applies: the universe is today's stocks.
- All data is cached in `%APPDATA%\EarningsScreener\cache.sqlite`, so the app works offline after the first download. Settings, watchlist and saved filters live in `settings.json` in the same folder, and errors go to `app.log`.

## Project layout
```
main.py                     entry point (python main.py [--demo])
screener/
  config.py                 settings + app data folder
  market_calendar.py        NYSE trading days/holidays (for future entry dates)
  universe.py               built-in tickers, S&P 500 download, custom lists
  providers.py              yfinance + Alpha Vantage download
  data_store.py             SQLite cache
  windows.py                timeframe definitions
  engine.py                 event alignment, returns, stats, score, ratings
  backtest.py               walk-forward backtest
  demo_data.py              simulated data with planted patterns
  gui/                      PySide6 interface (tabs, filters, charts, dialogs)
tests/test_engine.py        unit tests (pip install pytest; python -m pytest)
run.bat / build_exe.bat     Windows launcher and .exe builder
```

## Development
```bash
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt pytest
python -m pytest -q
python main.py --demo
```
