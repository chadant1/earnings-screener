"""Ticker universes: a bundled list of liquid, optionable US stocks, S&P 500 download, or custom."""
from __future__ import annotations

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


def load_sp500() -> list[str]:
    """Download current S&P 500 constituents from Wikipedia (needs internet)."""
    import pandas as pd
    import requests

    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    html = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0 EarningsScreener"}).text
    tables = pd.read_html(StringIO(html))
    syms = tables[0]["Symbol"].astype(str).str.replace(".", "-", regex=False).tolist()
    return sorted(set(syms))


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
