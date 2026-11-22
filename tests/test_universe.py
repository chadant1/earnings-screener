import pandas as pd
import pytest

from screener import universe as U
from screener.config import Settings
from screener.gui.filters import apply_rule


def _wiki_html(n, col="Symbol", extra_small_table=True):
    rows = "".join(f"<tr><td>T{chr(65 + i // 26)}{chr(65 + i % 26)}</td><td>Co {i}</td></tr>" for i in range(n))
    main = f"<table><tr><th>{col}</th><th>Security</th></tr>{rows}</table>"
    # a "recent changes" style table with a ticker column that must NOT be chosen
    small = ("<table><tr><th>Date</th><th>Added Ticker</th></tr>"
             "<tr><td>2026</td><td>ZZZZ</td></tr></table>") if extra_small_table else ""
    return small + main


def test_wiki_parser_picks_constituents_table():
    idx = U.INDEX_BY_KEY["sp500"]
    syms = U.parse_wiki_tables(_wiki_html(503), idx)
    assert len(syms) == 503 and "ZZZZ" not in syms


def test_wiki_parser_ticker_column_and_cleanup():
    idx = U.INDEX_BY_KEY["dow30"]
    html = "<table><tr><th>Company</th><th>Exchange</th><th>Symbol</th></tr>" + "".join(
        f"<tr><td>C{i}</td><td>NYSE</td><td>NYSE: X{chr(65 + i // 26)}{chr(65 + i % 26)}[{i}]</td></tr>" for i in range(30)) + "</table>"
    syms = U.parse_wiki_tables(html, idx)
    assert len(syms) == 30 and syms[0] == "XAA"


def test_wiki_parser_rejects_wrong_size():
    assert U.parse_wiki_tables(_wiki_html(200), U.INDEX_BY_KEY["sp500"]) == []


def test_ishares_parser():
    head = 'iShares Russell 2000 ETF\nFund Holdings as of,"Nov 20, 2026"\nInception Date,"May 22, 2000"\n \n'
    hdr = 'Ticker,Name,Sector,Asset Class,Market Value,Weight (%)\n'
    rows = '"BRKB","BERKSHIRE","Financials","Equity","1","0.1"\n"AAPL","APPLE","IT","Equity","1","0.1"\n' \
           '"USD","USD CASH","Cash","Cash","1","0.1"\n"XTSLA","BLK CSH","Cash","Money Market","1","0.1"\n'
    foot = ' \n"The content contained herein is owned or licensed by BlackRock"\n'
    assert U.parse_ishares_csv(head + hdr + rows + foot) == ["AAPL", "BRK-B"]


def test_nasdaq_json_parser():
    js = {"data": {"data": {"rows": [{"symbol": "AAPL"}, {"symbol": "MSFT"}, {"symbol": "BAD SYMBOL!"}]}}}
    assert U.parse_nasdaq_json(js) == ["AAPL", "MSFT"]


def test_universe_and_memberships(tmp_path):
    s = Settings(tmp_path / "s.json")
    # old single-choice setting migrates
    s.data["universe"] = "sp500"
    s.data["sp500_cache"] = ["AAA", "BBB"]
    assert U.selected_sets(s) == ["sp500"]
    assert U.resolve_universe(s) == ["AAA", "BBB"]
    U.index_cache(s)["nasdaq100"] = {"tickers": ["BBB", "CCC"], "updated": "", "source": "test"}
    s.data["universe_sets"] = ["nasdaq100", "custom"]
    s.data["custom_tickers"] = ["ZZZ"]
    s.data["watchlist"] = ["WWW"]
    assert U.resolve_universe(s) == ["BBB", "CCC", "WWW", "ZZZ"]
    mem = U.memberships(s)
    assert mem["BBB"] == ["S&P 500", "Nasdaq-100"] and mem["AAA"] == ["S&P 500"]


def test_index_filter_member_matching():
    df = pd.DataFrame({"ticker": list("ABCD"),
                       "indexes": ["S&P 500 · Nasdaq-100", "S&P 400", "", "Russell 2000"]})
    assert apply_rule(df, "indexes", "member", "S&P 500", set())["ticker"].tolist() == ["A"]
    assert apply_rule(df, "indexes", "member", "Nasdaq-100", set())["ticker"].tolist() == ["A"]
    assert apply_rule(df, "indexes", "empty", None, set())["ticker"].tolist() == ["C"]
    assert apply_rule(df, "indexes", "nonempty", None, set())["ticker"].tolist() == ["A", "B", "D"]


def test_fetch_index_falls_back(monkeypatch):
    import requests

    class R:
        def __init__(self, text): self.text = text
        def json(self): return {}
    calls = []

    def fake_get(url, **kw):
        calls.append(url)
        if "wikipedia" in url:
            return R(_wiki_html(150))  # wrong size -> rejected
        hdr = "Ticker,Name,Asset Class\n"
        rows = "".join(f"T{chr(65 + i // 26)}{chr(65 + i % 26)},X,Equity\n" for i in range(400))
        return R("junk\n" + hdr + rows)
    monkeypatch.setattr(requests, "get", fake_get)
    syms, src = U.fetch_index("sp400")
    assert len(syms) == 400 and src == "iShares IJH" and len(calls) == 2


def test_failed_index_download_is_throttled(tmp_path, monkeypatch):
    s = Settings(tmp_path / "s.json")
    calls = []

    def boom(key, timeout=15):
        calls.append(key)
        raise RuntimeError("offline")
    monkeypatch.setattr(U, "fetch_index", boom)
    assert set(U.refresh_indexes(s, ["dow30"])) == {"dow30"}
    assert U.refresh_indexes(s, ["dow30"]) == {} and calls == ["dow30"]          # skipped within 24h
    assert set(U.refresh_indexes(s, ["dow30"], force=True)) == {"dow30"} and len(calls) == 2
