"""
mf_main.py
----------
Orchestrator for the Mutual Fund Dip Alert System.

Run standalone:
    python mf_main.py

Or import and call from your existing main.py:
    from mf_main import run_mf_scan
    run_mf_scan()

Schedule: Run once daily at 7:00 PM IST (after AMFI publishes NAVs at 6 PM).
"""

import os
import sys
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# ── Path setup ─────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

# Load .env (local dev only — GitHub Actions uses real env vars)
env_path = BASE_DIR / "config" / ".env"
if env_path.exists():
    load_dotenv(env_path)

# ── Logging ────────────────────────────────────────────────────────────────
os.makedirs(BASE_DIR / "logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(BASE_DIR / "logs" / "mf_alerts.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# ── Internal imports (after path setup) ───────────────────────────────────
from data.mf_fetcher  import MFDataFetcher, FUND_REGISTRY
from data.mf_analyser import MFAnalyser
from alerts.mf_alerts import MFAlerter


# ── Database ───────────────────────────────────────────────────────────────

def init_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mf_alerts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT,
            fund_key    TEXT,
            fund_name   TEXT,
            signal      TEXT,
            score       INTEGER,
            current_nav REAL,
            drawdown_pct REAL,
            india_vix   REAL,
            nifty_drawdown REAL,
            bull_market INTEGER
        )
    """)
    conn.commit()
    return conn


def log_to_db(conn: sqlite3.Connection, analysis: dict, regime: dict):
    conn.execute("""
        INSERT INTO mf_alerts VALUES
        (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(),
        analysis.get("fund_key"),
        analysis.get("fund_name"),
        analysis.get("signal"),
        analysis.get("score"),
        analysis.get("current_nav"),
        analysis.get("drawdown_pct"),
        regime.get("india_vix"),
        regime.get("nifty_drawdown_pct"),
        1 if regime.get("bull_market") else 0,
    ))
    conn.commit()


# ── Main scan ──────────────────────────────────────────────────────────────

def run_mf_scan():
    logger.info("=" * 60)
    logger.info("Starting Mutual Fund Dip Alert Scan")
    logger.info(f"Funds in scope: {len(FUND_REGISTRY)}")

    fetcher  = MFDataFetcher()
    analyser = MFAnalyser()
    alerter  = MFAlerter()
    db_conn  = init_db(BASE_DIR / "data" / "mf_alerts.db")

    os.makedirs(BASE_DIR / "data", exist_ok=True)

    # 1. Market regime (fetched once for all funds)
    logger.info("Fetching market regime (Nifty 50 / India VIX)...")
    regime = analyser.get_market_regime()
    logger.info(
        f"  Nifty: {'Bull' if regime.get('bull_market') else 'Bear'} | "
        f"  VIX: {regime.get('india_vix')} ({regime.get('vix_signal')}) | "
        f"  Nifty drawdown: {regime.get('nifty_drawdown_pct')}%"
    )

    # 2. Analyse each fund
    all_analyses = []
    alert_funds  = []  # funds that hit BUY_DIP or STRONG_BUY_DIP

    for fund_key, meta in FUND_REGISTRY.items():
        logger.info(f"Processing: {meta['name']}")
        df = fetcher.fetch_nav_history(meta["scheme_code"], lookback_days=400)

        if df.empty:
            logger.warning(f"  Skipping {fund_key} — no NAV data")
            continue

        nav_metrics = analyser.compute_nav_metrics(df)
        analysis    = analyser.compute_dip_score(fund_key, nav_metrics, regime)
        all_analyses.append(analysis)

        logger.info(
            f"  Signal: {analysis['signal']} | "
            f"Score: {analysis['score']}/100 | "
            f"Drawdown: {analysis['drawdown_pct']}%"
        )

        # 3. Send individual alerts for actionable signals
        if analysis["signal"] in ("STRONG_BUY_DIP", "BUY_DIP"):
            msg = alerter.format_fund_alert(analysis, regime)
            alerter.send(msg)
            alert_funds.append(fund_key)
            logger.info(f"  [ALERT SENT] {fund_key}")

        # 4. Log to database
        log_to_db(db_conn, analysis, regime)

    # 5. Send daily summary (always, even if no dips)
    if all_analyses:
        summary = alerter.format_daily_summary(all_analyses, regime)
        alerter.send(summary)
        logger.info("Daily MF summary sent to Telegram.")

    logger.info(
        f"MF scan complete. "
        f"Funds scanned: {len(all_analyses)} | "
        f"Alerts triggered: {len(alert_funds)}"
    )
    db_conn.close()


if __name__ == "__main__":
    run_mf_scan()
