"""
mf_analyser.py
--------------
Analyses NAV history to detect:
  1. Correction depth  — how far the fund has fallen from its 52-week high
  2. Market regime     — is Nifty 50 above/below its 200-DMA?
  3. India VIX level   — fear gauge (fetched via yfinance ^INDIAVIX)
  4. Composite DIP score — combines all signals into an actionable score

Dip trigger thresholds per category
  Large Cap  : 10% from 52-week high
  Flexi Cap  : 12% from 52-week high
  Mid Cap    : 15% from 52-week high
  Small Cap  : 20% from 52-week high
"""

import pandas as pd
import numpy as np
import yfinance as yf
import logging
from datetime import datetime, timedelta
from data.mf_fetcher import FUND_REGISTRY

logger = logging.getLogger(__name__)


# ── Index tickers on yfinance ──────────────────────────────────────────────
INDEX_TICKERS = {
    "NIFTY50":          "^NSEI",
    "NIFTY_MIDCAP150":  "^CRSMID",      # Nifty Midcap 150
    "NIFTY_SMALLCAP250":"^CRSLDX",      # Nifty Smallcap 250
    "NIFTY500":         "^CRSLDX",      # proxy — Nifty 500 not on yfinance
    "INDIA_VIX":        "^INDIAVIX",
}


class MFAnalyser:
    """Converts raw NAV data into actionable dip signals."""

    # ------------------------------------------------------------------ #
    #  NAV-based metrics                                                   #
    # ------------------------------------------------------------------ #

    def compute_nav_metrics(self, df: pd.DataFrame) -> dict:
        """
        Given a NAV history DataFrame, return key stats:
          - current_nav
          - 52w_high_nav, 52w_low_nav
          - drawdown_pct  (how far below 52w high, as positive %)
          - nav_1m_change_pct
          - nav_3m_change_pct
          - nav_6m_change_pct
          - nav_1y_change_pct (CAGR approx for 1 year)
          - nav_ema_50d  (50-day EMA of NAV — smoothed trend)
          - above_ema50  (bool)
        """
        if df.empty or len(df) < 10:
            return {}

        today       = df.iloc[-1]["nav"]
        dates       = df["date"]
        navs        = df["nav"]
        now         = dates.iloc[-1]

        def nav_on_or_before(days_ago: int) -> float | None:
            target = now - timedelta(days=days_ago)
            subset = df[df["date"] <= target]
            return float(subset.iloc[-1]["nav"]) if not subset.empty else None

        high_52w = float(navs[dates >= now - timedelta(days=365)].max())
        low_52w  = float(navs[dates >= now - timedelta(days=365)].min())
        drawdown = round((high_52w - today) / high_52w * 100, 2)

        nav_1m  = nav_on_or_before(30)
        nav_3m  = nav_on_or_before(90)
        nav_6m  = nav_on_or_before(180)
        nav_1y  = nav_on_or_before(365)

        def pct_change(old, new):
            if old and old > 0:
                return round((new - old) / old * 100, 2)
            return None

        # 50-day EMA of NAV (smoothed momentum)
        ema50 = navs.ewm(span=50, adjust=False).mean().iloc[-1]

        return {
            "current_nav":       round(today, 4),
            "52w_high":          round(high_52w, 4),
            "52w_low":           round(low_52w, 4),
            "drawdown_pct":      drawdown,           # positive = below peak
            "change_1m_pct":     pct_change(nav_1m, today),
            "change_3m_pct":     pct_change(nav_3m, today),
            "change_6m_pct":     pct_change(nav_6m, today),
            "change_1y_pct":     pct_change(nav_1y, today),
            "nav_ema_50d":       round(float(ema50), 4),
            "above_ema50":       today >= float(ema50),
            "last_nav_date":     str(df.iloc[-1]["date"].date()),
        }

    # ------------------------------------------------------------------ #
    #  Market regime (Nifty 50 vs its 200-DMA)                            #
    # ------------------------------------------------------------------ #

    def get_market_regime(self) -> dict:
        """
        Returns:
          bull_market : bool   (Nifty 50 > 200-DMA)
          nifty_drawdown_pct   (from 52w high)
          india_vix            (current VIX level)
          vix_signal           ("LOW" / "MODERATE" / "HIGH" / "EXTREME")
        """
        result = {
            "bull_market":        None,
            "nifty_drawdown_pct": None,
            "india_vix":          None,
            "vix_signal":         None,
        }

        # Nifty 50
        try:
            nifty = yf.download(
                "^NSEI", period="1y", interval="1d", progress=False
            )
            if isinstance(nifty.columns, pd.MultiIndex):
                nifty.columns = nifty.columns.get_level_values(0)

            if not nifty.empty:
                close        = nifty["Close"].squeeze()
                current      = float(close.iloc[-1])
                ma200        = float(close.rolling(200).mean().iloc[-1])
                high_52w     = float(close.max())
                result["bull_market"]        = current > ma200
                result["nifty_drawdown_pct"] = round(
                    (high_52w - current) / high_52w * 100, 2
                )
        except Exception as e:
            logger.warning(f"Nifty regime fetch failed: {e}")

        # India VIX
        try:
            vix_df = yf.download(
                "^INDIAVIX", period="5d", interval="1d", progress=False
            )
            if isinstance(vix_df.columns, pd.MultiIndex):
                vix_df.columns = vix_df.columns.get_level_values(0)

            if not vix_df.empty:
                vix = float(vix_df["Close"].squeeze().dropna().iloc[-1])
                result["india_vix"] = round(vix, 2)
                if vix < 15:
                    result["vix_signal"] = "LOW"
                elif vix < 20:
                    result["vix_signal"] = "MODERATE"
                elif vix < 25:
                    result["vix_signal"] = "HIGH"
                else:
                    result["vix_signal"] = "EXTREME"
        except Exception as e:
            logger.warning(f"India VIX fetch failed: {e}")

        return result

    # ------------------------------------------------------------------ #
    #  Composite dip score                                                 #
    # ------------------------------------------------------------------ #

    def compute_dip_score(
        self,
        fund_key: str,
        nav_metrics: dict,
        regime: dict,
    ) -> dict:
        """
        Scores the lump-sum opportunity on a 0–100 scale.

        Component weights:
          40 pts — NAV drawdown vs fund-specific threshold
          20 pts — Nifty 50 market regime (bear market = better entry)
          20 pts — India VIX (high fear = better entry)
          10 pts — NAV below 50-day EMA (momentum dip confirmation)
          10 pts — 3-month NAV decline (short-term weakness = opportunity)

        Signal tiers:
          >= 70  : STRONG BUY DIP
          >= 50  : BUY DIP
          >= 35  : WATCH
          <  35  : HOLD (no correction yet)
        """
        meta      = FUND_REGISTRY.get(fund_key, {})
        threshold = meta.get("correction_threshold_pct", 15)
        drawdown  = nav_metrics.get("drawdown_pct", 0) or 0
        score     = 0
        reasons   = []

        # 1. Drawdown vs threshold (40 pts)
        if drawdown >= threshold:
            pts = min(40, int(40 * (drawdown / threshold)))
            score += pts
            reasons.append(
                f"[+{pts}] NAV down {drawdown:.1f}% from peak "
                f"(threshold {threshold}%)"
            )
        elif drawdown >= threshold * 0.7:
            pts = 15
            score += pts
            reasons.append(
                f"[+{pts}] NAV approaching threshold "
                f"({drawdown:.1f}% / {threshold}%)"
            )
        else:
            reasons.append(
                f"[ 0] NAV only {drawdown:.1f}% from peak "
                f"— no meaningful correction yet"
            )

        # 2. Market regime (20 pts)
        nifty_dd = regime.get("nifty_drawdown_pct") or 0
        if regime.get("bull_market") is False:
            score += 20
            reasons.append("[+20] Nifty 50 in bear phase (below 200-DMA)")
        elif nifty_dd >= 8:
            score += 12
            reasons.append(f"[+12] Nifty 50 down {nifty_dd:.1f}% from 52w high")
        elif nifty_dd >= 5:
            score += 6
            reasons.append(f"[ +6] Nifty 50 moderately down ({nifty_dd:.1f}%)")
        else:
            reasons.append("[ 0] Market is near highs — limited macro dip")

        # 3. India VIX (20 pts)
        vix = regime.get("india_vix") or 0
        vix_sig = regime.get("vix_signal", "")
        if vix_sig == "EXTREME":
            score += 20
            reasons.append(f"[+20] India VIX EXTREME ({vix}) — peak fear")
        elif vix_sig == "HIGH":
            score += 14
            reasons.append(f"[+14] India VIX HIGH ({vix}) — elevated fear")
        elif vix_sig == "MODERATE":
            score += 6
            reasons.append(f"[ +6] India VIX moderate ({vix})")
        else:
            reasons.append(f"[ 0] India VIX low ({vix}) — complacent market")

        # 4. Below 50-day EMA (10 pts)
        if nav_metrics.get("above_ema50") is False:
            score += 10
            reasons.append("[+10] NAV below 50-day EMA — momentum dip confirmed")
        else:
            reasons.append("[ 0] NAV above 50-day EMA — still in uptrend")

        # 5. 3-month decline (10 pts)
        change_3m = nav_metrics.get("change_3m_pct") or 0
        if change_3m <= -10:
            score += 10
            reasons.append(f"[+10] NAV fell {change_3m:.1f}% in 3 months")
        elif change_3m <= -5:
            score += 5
            reasons.append(f"[ +5] NAV fell {change_3m:.1f}% in 3 months")
        else:
            reasons.append(f"[ 0] 3-month NAV change: {change_3m:.1f}%")

        # Signal tier
        if score >= 70:
            signal = "STRONG_BUY_DIP"
        elif score >= 50:
            signal = "BUY_DIP"
        elif score >= 35:
            signal = "WATCH"
        else:
            signal = "HOLD"

        return {
            "fund_key":  fund_key,
            "fund_name": meta.get("name", fund_key),
            "category":  meta.get("category", ""),
            "signal":    signal,
            "score":     score,
            "drawdown":  drawdown,
            "threshold": threshold,
            "reasons":   reasons,
            **nav_metrics,
        }
