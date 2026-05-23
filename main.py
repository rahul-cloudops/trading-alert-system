import os
import yaml
import logging
import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

from data.fetcher import MarketDataFetcher
from data.technical import TechnicalAnalyzer
from data.sentiment import SentimentAnalyzer
from data.risk import RiskManager
from alerts.telegram_bot import TelegramAlerter

# Load .env if it exists (local dev) — on GitHub Actions this is skipped
env_path = Path(__file__).parent / "config" / ".env"
if env_path.exists():
    load_dotenv(env_path)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/trading.log", encoding="utf-8"),
        logging.StreamHandler(stream=open(
            __import__('sys').stdout.fileno(),
            mode='w', encoding='utf-8', buffering=1, closefd=False
        ))
    ]
)
logger = logging.getLogger(__name__)

# --- Ticker to Company Name mapping for sentiment ---
TICKER_NAMES = {
    "RELIANCE.NS": "Reliance Industries",
    "INFY.NS": "Infosys",
    "TCS.NS": "Tata Consultancy Services",
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "NVDA": "Nvidia",
    # Add more as needed
}

def init_db():
    conn = sqlite3.connect("data/trade_log.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT, ticker TEXT, market TEXT,
            signal TEXT, score INTEGER, entry_price REAL,
            stop_loss REAL, take_profit_1 REAL, take_profit_2 REAL,
            risk_reward REAL, sentiment_score REAL, sentiment_label TEXT
        )
    """)
    conn.commit()
    return conn

def log_alert(conn, ticker, market, signal_data, risk_data, sentiment):
    conn.execute("""
        INSERT INTO alerts VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(), ticker, market,
        signal_data['signal'], signal_data['score'], risk_data['entry_price'],
        risk_data['stop_loss'], risk_data['take_profit_1'], risk_data['take_profit_2'],
        risk_data['risk_reward_ratio'], sentiment['score'], sentiment['label']
    ))
    conn.commit()

def run_scan():
    logger.info("=" * 60)
    logger.info("Starting market scan...")

    with open("config/watchlist.yaml") as f:
        config = yaml.safe_load(f)

    fetcher   = MarketDataFetcher(lookback_days=365)
    ta_engine = TechnicalAnalyzer()
    sentiment = SentimentAnalyzer()
    alerter   = TelegramAlerter()
    db_conn   = init_db()

    risk_mgr_in = RiskManager(capital=config['portfolio_capital_inr'],
                               risk_per_trade_pct=2.0, max_positions=5)
    risk_mgr_us = RiskManager(capital=config['portfolio_capital_usd'],
                               risk_per_trade_pct=2.0, max_positions=5)

    all_results = []

    for market, tickers, risk_mgr in [
        ("IN", config['indian_stocks'], risk_mgr_in),
        ("US", config['us_stocks'], risk_mgr_us)
    ]:
        logger.info(f"Scanning {market} market — {len(tickers)} stocks")
        for ticker in tickers:
            logger.info(f"  Processing {ticker}...")
            try:
                df = fetcher.fetch_ohlcv(ticker)
                if df.empty:
                    continue

                df = ta_engine.compute_indicators(df)
                signal_data = ta_engine.generate_signal(df)

                if signal_data['signal'] in ('HOLD', 'INSUFFICIENT_DATA'):
                    continue

                risk_data = risk_mgr.calculate_levels(
                    current_price=signal_data['close'],
                    atr=signal_data['atr'],
                    signal=signal_data['signal']
                )
                signal_data.update(risk_data)

                approved, reason = risk_mgr.apply_filters(signal_data)
                if not approved:
                    logger.info(f"    Filtered out: {reason}")
                    continue

                company = TICKER_NAMES.get(ticker, ticker.replace(".NS", ""))
                sent_data = sentiment.get_stock_sentiment(ticker, company, market)

                # Boost/reduce score based on sentiment
                if sent_data['label'] == 'POSITIVE' and signal_data['signal'] == 'BUY':
                    signal_data['score'] = min(100, signal_data['score'] + 10)
                elif sent_data['label'] == 'NEGATIVE' and signal_data['signal'] == 'BUY':
                    signal_data['score'] = max(0, signal_data['score'] - 10)

                all_results.append({**signal_data, "ticker": ticker, "market": market})

                if signal_data['signal'] in ('BUY', 'SELL'):
                    message = alerter.format_alert(ticker, signal_data, risk_data, sent_data, market)
                    alerter.send_alert(message)
                    log_alert(db_conn, ticker, market, signal_data, risk_data, sent_data)
                    logger.info(f"    ✅ Alert sent for {ticker}: {signal_data['signal']}")

            except Exception as e:
                logger.error(f"    ❌ Error processing {ticker}: {e}")

    alerter.send_daily_summary(all_results)
    logger.info("Scan complete.")
    db_conn.close()

if __name__ == "__main__":
    run_scan()