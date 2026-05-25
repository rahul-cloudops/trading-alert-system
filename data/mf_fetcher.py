"""
mf_fetcher.py
-------------
Fetches NAV history for Indian Mutual Funds using the free mfapi.in API.
No API key required. Data is updated daily by AMFI.

API base: https://api.mfapi.in
  GET /mf/{scheme_code}         -> full NAV history
  GET /mf/{scheme_code}/latest  -> latest NAV only
"""

import requests
import pandas as pd
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scheme codes from mfapi.in  (verified against AMFI registry)
# To find a code for any fund: https://api.mfapi.in/mf/search?q=<fund+name>
# ---------------------------------------------------------------------------
FUND_REGISTRY = {
    # ── Your current holdings ──────────────────────────────────────────────
    "HDFC_MIDCAP": {
        "scheme_code": 118989,
        "name": "HDFC Mid Cap Fund - Growth Option - Direct Plan",
        "category": "Mid Cap",
        "benchmark_index": "NIFTY_MIDCAP150",
        "correction_threshold_pct": 15,   # trigger lumpsum alert at 15% dip
    },
    "NIPPON_LARGECAP": {
        "scheme_code": 118632,
        "name": "Nippon India Large Cap Fund - Direct Plan Growth Plan - Growth Option",
        "category": "Large Cap",
        "benchmark_index": "NIFTY50",
        "correction_threshold_pct": 10,
    },
    "HDFC_FLEXICAP": {
        "scheme_code": 118955,
        "name": "HDFC Flexi Cap Fund - Growth Option - Direct Plan",
        "category": "Flexi Cap",
        "benchmark_index": "NIFTY500",
        "correction_threshold_pct": 12,
    },
    "BANDHAN_SMALLCAP": {
        "scheme_code": 147946,
        "name": "BANDHAN SMALL CAP FUND - DIRECT PLAN GROWTH",
        "category": "Small Cap",
        "benchmark_index": "NIFTY_SMALLCAP250",
        "correction_threshold_pct": 20,   # small caps need deeper correction
    },

    # ── Watchlist / recommended funds ─────────────────────────────────────
    "PARAG_FLEXICAP": {
        "scheme_code": 122639,
        "name": "Parag Parikh Flexi Cap Fund - Direct Plan - Growth",
        "category": "Flexi Cap",
        "benchmark_index": "NIFTY500",
        "correction_threshold_pct": 12,
    },
    "MIRAE_LARGECAP": {
        "scheme_code": 118825,
        "name": "Mirae Asset Large Cap Fund - Direct Plan - Growth",
        "category": "Large Cap",
        "benchmark_index": "NIFTY50",
        "correction_threshold_pct": 10,
    },
    "SBI_SMALLCAP": {
        "scheme_code": 125497,
        "name": "SBI Small Cap Fund - Direct Plan - Growth",
        "category": "Small Cap",
        "benchmark_index": "NIFTY_SMALLCAP250",
        "correction_threshold_pct": 20,
    },
}

BASE_URL = "https://api.mfapi.in"
TIMEOUT  = 15   # seconds


class MFDataFetcher:
    """Fetches and processes NAV data from mfapi.in."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "TradingAlertBot/1.0"})

    # ------------------------------------------------------------------ #
    #  Core fetch methods                                                  #
    # ------------------------------------------------------------------ #

    def fetch_latest_nav(self, scheme_code: int) -> Optional[dict]:
        """Return the latest NAV dict: {date, nav}."""
        url = f"{BASE_URL}/mf/{scheme_code}/latest"
        try:
            resp = self.session.get(url, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") == "SUCCESS" and data.get("data"):
                entry = data["data"][0]
                return {
                    "date": entry["date"],
                    "nav":  float(entry["nav"]),
                }
        except Exception as e:
            logger.error(f"Failed latest NAV for {scheme_code}: {e}")
        return None

    def fetch_nav_history(
        self,
        scheme_code: int,
        lookback_days: int = 365,
    ) -> pd.DataFrame:
        """
        Return a DataFrame with columns [date, nav] sorted ascending.
        lookback_days controls how far back we go (default 1 year).
        """
        url = f"{BASE_URL}/mf/{scheme_code}"
        try:
            resp = self.session.get(url, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()

            if data.get("status") != "SUCCESS" or not data.get("data"):
                logger.warning(f"No history data for scheme {scheme_code}")
                return pd.DataFrame()

            df = pd.DataFrame(data["data"])              # columns: date, nav
            df["date"] = pd.to_datetime(df["date"], format="%d-%m-%Y")
            df["nav"]  = pd.to_numeric(df["nav"], errors="coerce")
            df.dropna(subset=["nav"], inplace=True)
            df.sort_values("date", inplace=True)
            df.reset_index(drop=True, inplace=True)

            # Trim to lookback window
            cutoff = datetime.today() - timedelta(days=lookback_days)
            df = df[df["date"] >= cutoff].copy()

            logger.info(
                f"Fetched {len(df)} NAV records for scheme {scheme_code}"
            )
            return df

        except Exception as e:
            logger.error(f"Failed NAV history for {scheme_code}: {e}")
            return pd.DataFrame()

    # ------------------------------------------------------------------ #
    #  Convenience batch fetch                                             #
    # ------------------------------------------------------------------ #

    def fetch_all_funds(self, lookback_days: int = 365) -> dict:
        """
        Fetch NAV history for every fund in FUND_REGISTRY.
        Returns {fund_key: DataFrame}.
        """
        results = {}
        for key, meta in FUND_REGISTRY.items():
            logger.info(f"Fetching NAV history: {meta['name']}")
            df = self.fetch_nav_history(meta["scheme_code"], lookback_days)
            if not df.empty:
                results[key] = df
            else:
                logger.warning(f"Skipping {key} — no data returned")
        return results
