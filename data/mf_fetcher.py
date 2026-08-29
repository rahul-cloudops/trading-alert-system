"""
mf_fetcher.py
-------------
Fetches NAV history for Indian Mutual Funds using the free mfapi.in API.
Includes a seamless yfinance fallback for massive datasets that cause 502 timeouts.
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pandas as pd
import yfinance as yf
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

FUND_REGISTRY = {
    # ── Your current holdings ──────────────────────────────────────────────
    "HDFC_MIDCAP": {
        "scheme_code": 118989,
        "yfinance_ticker": "0P0000XVUR.BO", # Fallback for 502 errors
        "name": "HDFC Mid Cap Fund - Growth Option - Direct Plan",
        "category": "Mid Cap",
        "benchmark_index": "NIFTY_MIDCAP150",
        "correction_threshold_pct": 15,   
    },
    "NIPPON_LARGECAP": {
        "scheme_code": 118632,
        "yfinance_ticker": "0P0000XWAA.BO",
        "name": "Nippon India Large Cap Fund - Direct Plan Growth Plan - Growth Option",
        "category": "Large Cap",
        "benchmark_index": "NIFTY50",
        "correction_threshold_pct": 10,
    },
    "HDFC_FLEXICAP": {
        "scheme_code": 118955,
        "yfinance_ticker": "0P0000XVU3.BO",
        "name": "HDFC Flexi Cap Fund - Growth Option - Direct Plan",
        "category": "Flexi Cap",
        "benchmark_index": "NIFTY500",
        "correction_threshold_pct": 12,
    },
    "BANDHAN_SMALLCAP": {
        "scheme_code": 147946,
        "yfinance_ticker": "0P0001LQY1.BO",
        "name": "BANDHAN SMALL CAP FUND - DIRECT PLAN GROWTH",
        "category": "Small Cap",
        "benchmark_index": "NIFTY_SMALLCAP250",
        "correction_threshold_pct": 20,   
    },

    # ── Watchlist / recommended funds ─────────────────────────────────────
    "PARAG_FLEXICAP": {
        "scheme_code": 122639,
        "yfinance_ticker": "0P0000YWL1.BO",
        "name": "Parag Parikh Flexi Cap Fund - Direct Plan - Growth",
        "category": "Flexi Cap",
        "benchmark_index": "NIFTY500",
        "correction_threshold_pct": 12,
    },
    "MIRAE_LARGECAP": {
        "scheme_code": 118825,
        "yfinance_ticker": "0P0000XVWX.BO",
        "name": "Mirae Asset Large Cap Fund - Direct Plan - Growth",
        "category": "Large Cap",
        "benchmark_index": "NIFTY50",
        "correction_threshold_pct": 10,
    },
    "SBI_SMALLCAP": {
        "scheme_code": 125497,
        "yfinance_ticker": "0P0000YWOP.BO",
        "name": "SBI Small Cap Fund - Direct Plan - Growth",
        "category": "Small Cap",
        "benchmark_index": "NIFTY_SMALLCAP250",
        "correction_threshold_pct": 20,
    },
}

BASE_URL = "https://api.mfapi.in"
TIMEOUT  = 15   # seconds

class MFDataFetcher:
    """Fetches and processes NAV data from mfapi.in with yfinance fallback."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/json"
        })
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _fetch_yfinance_fallback(self, ticker: str, lookback_days: int) -> pd.DataFrame:
        """Fallback method to fetch NAV data using yfinance if mfapi.in fails."""
        try:
            logger.info(f"🔄 Triggering yfinance fallback for {ticker}...")
            df = yf.download(ticker, period=f"{lookback_days}d", interval="1d", progress=False)
            
            if df.empty:
                return pd.DataFrame()
                
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
                
            df = df.reset_index()
            # Yfinance uses 'Date' and 'Close' (which represents the NAV for MFs)
            df = df[['Date', 'Close']].rename(columns={'Date': 'date', 'Close': 'nav'})
            df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None)
            df.dropna(subset=['nav'], inplace=True)
            
            logger.info(f"✅ Fallback successful: Fetched {len(df)} records via yfinance")
            return df
        except Exception as e:
            logger.error(f"❌ Fallback yfinance fetch failed for {ticker}: {e}")
            return pd.DataFrame()

    def fetch_nav_history(self, scheme_code: int, yf_ticker: str, lookback_days: int = 365) -> pd.DataFrame:
        """Return a DataFrame with columns [date, nav] sorted ascending."""
        url = f"{BASE_URL}/mf/{scheme_code}"
        try:
            resp = self.session.get(url, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()

            if data.get("status") != "SUCCESS" or not data.get("data"):
                logger.warning(f"⚠️ No history data on mfapi for scheme {scheme_code}")
                return self._fetch_yfinance_fallback(yf_ticker, lookback_days)

            df = pd.DataFrame(data["data"])
            df["date"] = pd.to_datetime(df["date"], format="%d-%m-%Y")
            df["nav"]  = pd.to_numeric(df["nav"], errors="coerce")
            df.dropna(subset=["nav"], inplace=True)
            df.sort_values("date", inplace=True)
            df.reset_index(drop=True, inplace=True)

            cutoff = datetime.today() - timedelta(days=lookback_days)
            df = df[df["date"] >= cutoff].copy()

            logger.info(f"✅ Fetched {len(df)} NAV records for scheme {scheme_code} via mfapi")
            return df

        except Exception as e:
            logger.warning(f"⚠️ mfapi.in failed for {scheme_code} ({e}).")
            # If mfapi throws a 502/Timeout, pivot to the yfinance fallback
            return self._fetch_yfinance_fallback(yf_ticker, lookback_days)

    def fetch_all_funds(self, lookback_days: int = 365) -> dict:
        """Fetch NAV history for every fund in FUND_REGISTRY."""
        results = {}
        for key, meta in FUND_REGISTRY.items():
            logger.info(f"Processing: {meta['name']}")
            df = self.fetch_nav_history(meta["scheme_code"], meta["yfinance_ticker"], lookback_days)
            if not df.empty:
                results[key] = df
            else:
                logger.warning(f"❌ Skipping {key} — no data returned from primary or fallback")
        return results