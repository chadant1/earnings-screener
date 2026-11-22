"""Stock universes: built-in list, market indexes (S&P 500, Nasdaq-100, Dow 30, S&P 400/600,
Russell 1000/2000), and custom lists.  Also provides index *membership* for screening.

Index constituents are downloaded from public sources (Wikipedia tables, iShares ETF holdings
files, Nasdaq's website) with automatic fallback, validated against the index's expected size,
and cached in settings so the app works offline.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

# ~250 liquid, optionable US large/mid caps across sectors (edit freely in the app).
DEFAULT_TICKERS = sorted(set("""
AAPL MSFT NVDA AMZN GOOGL META TSLA AVGO ORCL AMD INTC QCOM TXN MU AMAT LRCX KLAC ADI MRVL NXPI
ON MCHP SMCI ARM CRM ADBE NOW INTU SNOW PLTR PANW CRWD ZS FTNT NET DDOG MDB OKTA TEAM WDAY
SHOP UBER LYFT ABNB DASH PYPL XYZ COIN HOOD AFRM SOFI NFLX DIS ROKU SPOT PINS SNAP RBLX EA TTWO
IBM CSCO DELL HPQ HPE ANET WDC STX ACN CTSH EPAM
JPM BAC WFC C GS MS SCHW BLK AXP COF USB PNC TFC MET PRU AIG ALL TRV PGR CB V MA FI FIS
UNH JNJ PFE MRK ABBV LLY BMY AMGN GILD REGN VRTX BIIB MRNA ISRG MDT ABT TMO DHR SYK BSX ZBH
CVS CI HUM ELV HCA MCK CAH DXCM ILMN IDXX
WMT COST TGT HD LOW BBY DG DLTR KR KO PEP PG CL KMB MDLZ GIS HSY KHC MO PM STZ TAP
MCD SBUX CMG YUM DPZ DRI NKE LULU TJX ROST GAP ANF AEO URBN DECK CROX ULTA EL ETSY EBAY W CHWY
F GM RIVN LCID TM HMC APTV BWA
XOM CVX COP OXY EOG DVN MPC VLO PSX SLB HAL BKR FANG APA
BA LMT RTX NOC GD GE HON CAT DE MMM EMR ETN PH ITW UPS FDX DAL UAL AAL LUV CSX UNP NSC
LIN APD DOW DD NEM FCX AA CLF NUE STLD
NEE DUK SO D AEP EXC
AMT PLD CCI EQIX SPG O
T VZ TMUS CMCSA CHTR
MAR HLT CCL RCL NCLH EXPE BKNG
ZM DOCU TWLO U PATH S AI SNPS CDNS ADSK
""".split()))


# ----------------------------------------------------------------- indexes
@dataclass(frozen=True)
class IndexDef:
    key: str
    label: str          # shown in lists/dialogs
    short: str          # shown in the Indexes column / filters
    size: int           # expected number of members (used to validate downloads)
    sources: tuple      # tried in order: ("wiki", url) | ("ishares", product_path, fund) | ("nasdaq", list_type)


_W = "https://en.wikipedia.org/wiki/"
INDEXES: list[IndexDef] = [
    IndexDef("sp500", "S&P 500", "S&P 500", 503,
             (("wiki", _W + "List_of_S%26P_500_companies"), ("ishares", "239726/ishares-core-sp-500-etf", "IVV"))),
    IndexDef("nasdaq100", "Nasdaq-100", "Nasdaq-100", 101,
             (("wiki", _W + "Nasdaq-100"), ("nasdaq", "nasdaq100"))),
    IndexDef("dow30", "Dow Jones Industrial Average (30)", "Dow 30", 30,
             (("wiki", _W + "Dow_Jones_Industrial_Average"),)),
    IndexDef("sp400", "S&P MidCap 400", "S&P 400", 400,
             (("wiki", _W + "List_of_S%26P_400_companies"), ("ishares", "239763/ishares-core-sp-midcap-etf", "IJH"))),
    IndexDef("sp600", "S&P SmallCap 600", "S&P 600", 600,
             (("wiki", _W + "List_of_S%26P_600_companies"), ("ishares", "239774/ishares-core-sp-smallcap-etf", "IJR"))),
    IndexDef("russell1000", "Russell 1000", "Russell 1000", 1005,
             (("ishares", "239707/ishares-russell-1000-etf", "IWB"), ("wiki", _W + "Russell_1000_Index"))),
    IndexDef("russell2000", "Russell 2000", "Russell 2000", 1975,
             (("ishares", "239710/ishares-russell-2000-etf", "IWM"),)),
]
INDEX_BY_KEY = {i.key: i for i in INDEXES}

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/130.0 Safari/537.36 EarningsScreener",
      "Accept-Language": "en-US,en;q=0.9"}
_TICKER_RE = re.compile(r"^[A-Z]{1,5}(-[A-Z]{1,2})?$")
# iShares writes share classes without separators
_ISHARES_FIX = {"BRKB": "BRK-B", "BFB": "BF-B", "BFA": "BF-A", "HEIA": "HEI-A", "LENB": "LEN-B",
                "MOGA": "MOG-A", "GEFB": "GEF-B", "CWENA": "CWEN-A", "UHALB": "UHAL-B", "LGFA": "LGF-A",
                "LGFB": "LGF-B", "BIOB": "BIO-B", "CRDA": "CRD-A", "CRDB": "CRD-B", "FOXA": "FOXA",
                "NWSA": "NWSA", "GOOGL": "GOOGL"}


def clean_symbol(raw) -> str | None:
    s = str(raw).strip().upper()
    s = re.sub(r"\[.*?\]", "", s)             # wikipedia footnotes
    if ":" in s:                                # "NYSE: MMM"
        s = s.split(":")[-1].strip()
    s = s.replace(".", "-").replace("/", "-").replace(" ", "")
    return s if _TICKER_RE.match(s) else None


def _valid_size(n: int, idx: IndexDef) -> bool:
    lo = int(idx.size * 0.85) if idx.size > 40 else idx.size - 4
    hi = int(idx.size * 1.15) + 2
    return lo <= n <= hi


def parse_wiki_tables(html: str, idx: IndexDef) -> list[str]:
    """Find the constituents table: the one with a Symbol/Ticker column closest to the expected size."""
    import pandas as pd
    best: list[str] = []
    for t in pd.read_html(StringIO(html)):
        cols = [" ".join(map(str, c)) if isinstance(c, tuple) else str(c) for c in t.columns]
        t.columns = cols
        for col in cols:
            cl = col.lower()
            if "symbol" in cl or "ticker" in cl:
                syms = [x for x in (clean_symbol(v) for v in t[col].dropna()) if x]
                syms = sorted(set(syms))
                if _valid_size(len(syms), idx) and abs(len(syms) - idx.size) < abs(len(best) - idx.size):
                    best = syms
    return best


def parse_ishares_csv(text: str) -> list[str]:
    """iShares holdings CSV: ~9 lines of fund info, a header row starting with Ticker, then holdings."""
    import pandas as pd
    lines = text.lstrip("\ufeff").splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.replace('"', "").startswith("Ticker,")), None)
    if start is None:
        return []
    df = pd.read_csv(StringIO("\n".join(lines[start:])), on_bad_lines="skip", dtype=str)
    if "Asset Class" in df.columns:
        df = df[df["Asset Class"].astype(str).str.strip().eq("Equity")]
    out = []
    for v in df["Ticker"].dropna():
        v = str(v).strip().upper()
        v = _ISHARES_FIX.get(v, v)
        c = clean_symbol(v)
        if c:
            out.append(c)
    return sorted(set(out))


def parse_nasdaq_json(js: dict) -> list[str]:
    data = (js or {}).get("data") or {}
    rows = data.get("data", {}).get("rows") if isinstance(data.get("data"), dict) else data.get("rows")
    rows = rows or []
    return sorted({c for c in (clean_symbol(r.get("symbol")) for r in rows) if c})


def fetch_index(key: str, timeout: int = 15) -> tuple[list[str], str]:
    """Download an index's constituents. Returns (tickers, source). Raises RuntimeError if all sources fail."""
    import requests
    idx = INDEX_BY_KEY[key]
    errors = []
    for src in idx.sources:
        kind = src[0]
        try:
            if kind == "wiki":
                html = requests.get(src[1], headers=UA, timeout=timeout).text
                syms, name = parse_wiki_tables(html, idx), "Wikipedia"
            elif kind == "ishares":
                url = (f"https://www.ishares.com/us/products/{src[1]}/1467271812596.ajax"
                       f"?fileType=csv&fileName={src[2]}_holdings&dataType=fund")
                syms, name = parse_ishares_csv(requests.get(url, headers=UA, timeout=timeout).text), f"iShares {src[2]}"
            elif kind == "nasdaq":
                r = requests.get(f"https://api.nasdaq.com/api/quote/list-type/{src[1]}",
                                 headers={**UA, "Accept": "application/json"}, timeout=timeout)
                syms, name = parse_nasdaq_json(r.json()), "Nasdaq.com"
            else:
                continue
            if _valid_size(len(syms), idx):
                return syms, name
            errors.append(f"{kind}: got {len(syms)} symbols, expected about {idx.size}")
        except Exception as e:
            errors.append(f"{kind}: {e}"[:160])
    raise RuntimeError("; ".join(errors) or "no sources")


# ------------------------------------------------- settings-backed helpers
def index_cache(settings) -> dict:
    """{key: {"tickers": [...], "updated": iso, "source": str}} (migrates the old sp500_cache)."""
    cache = settings.data.setdefault("index_cache", {})
    old = settings.data.get("sp500_cache")
    if old and "sp500" not in cache:
        cache["sp500"] = {"tickers": list(old), "updated": "", "source": "Wikipedia"}
    return cache


def selected_sets(settings) -> list[str]:
    """Which lists make up the universe: 'builtin', 'custom' and/or index keys."""
    sets = settings.data.get("universe_sets")
    if sets is None:  # migrate from the original single-choice setting
        sets = {"default": ["builtin"], "sp500": ["sp500"], "custom": ["custom"]}.get(settings["universe"], ["builtin"])
    return list(sets)


def refresh_indexes(settings, keys=None, max_age_days: int = 30, force: bool = False) -> dict[str, str]:
    """Download index lists that are missing or older than max_age_days. Returns {key: error}."""
    cache = index_cache(settings)
    attempts = settings.data.setdefault("index_failed_at", {})
    errors = {}
    for key in (keys or [i.key for i in INDEXES]):
        if not force and key in attempts:  # don't hammer a failing source: retry at most daily
            try:
                if (dt.datetime.now() - dt.datetime.fromisoformat(attempts[key])).total_seconds() < 86400:
                    continue
            except ValueError:
                pass
        ent = cache.get(key)
        if ent and not force and ent.get("updated"):
            try:
                age = (dt.datetime.now() - dt.datetime.fromisoformat(ent["updated"])).days
                if age < max_age_days:
                    continue
            except ValueError:
                pass
        try:
            syms, src = fetch_index(key)
            cache[key] = {"tickers": syms, "updated": dt.datetime.now().isoformat(timespec="seconds"), "source": src}
            attempts.pop(key, None)
        except Exception as e:
            errors[key] = str(e)
            attempts[key] = dt.datetime.now().isoformat(timespec="seconds")
    return errors


def resolve_universe(settings) -> list[str]:
    sets = selected_sets(settings)
    cache = index_cache(settings)
    out: set[str] = set(settings["watchlist"])
    if "builtin" in sets:
        out |= set(DEFAULT_TICKERS)
    if "custom" in sets:
        out |= set(settings["custom_tickers"])
    for k in sets:
        if k in cache:
            out |= set(cache[k]["tickers"])
    if out == set(settings["watchlist"]):  # nothing usable selected/cached yet
        out |= set(DEFAULT_TICKERS)
    return sorted(out)


def memberships(settings) -> dict[str, list[str]]:
    """ticker -> list of index short names, for every index list that has been downloaded."""
    res: dict[str, list[str]] = {}
    cache = index_cache(settings)
    for idx in INDEXES:
        for t in cache.get(idx.key, {}).get("tickers", []):
            res.setdefault(t, []).append(idx.short)
    return res


def load_sp500() -> list[str]:
    """Backwards-compatible helper."""
    return fetch_index("sp500")[0]


def parse_ticker_text(text: str) -> list[str]:
    """Accept tickers separated by commas, spaces, or newlines; or a CSV with a Symbol/Ticker column."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if lines and any(h in lines[0].lower() for h in ("symbol", "ticker")):
        import pandas as pd
        df = pd.read_csv(StringIO(text))
        col = next(c for c in df.columns if c.strip().lower() in ("symbol", "ticker"))
        raw = df[col].astype(str).tolist()
    else:
        raw = text.replace(",", " ").replace(";", " ").split()
    out = []
    for t in raw:
        t = t.strip().upper().replace(".", "-")
        if t and t.replace("-", "").isalnum() and len(t) <= 10:
            out.append(t)
    return sorted(set(out))


def load_ticker_file(path: str | Path) -> list[str]:
    return parse_ticker_text(Path(path).read_text(encoding="utf-8", errors="ignore"))
