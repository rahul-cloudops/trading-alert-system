# AI-Assisted Automated Trading Alert System
### Blueprint for NSE/BSE & US Markets | Swing Trading Focus

---

## TABLE OF CONTENTS
1. [System Architecture](#1-system-architecture)
2. [Recommended Tech Stack](#2-recommended-tech-stack)
3. [Data Sources & APIs](#3-data-sources--apis)
4. [Step-by-Step Implementation Guide](#4-step-by-step-implementation-guide)
5. [Core Module Code](#5-core-module-code)
6. [Risk Management Framework](#6-risk-management-framework)
7. [Alert System Setup](#7-alert-system-setup)
8. [Scheduling & Deployment](#8-scheduling--deployment)
9. [Limitations & Workarounds](#9-limitations--workarounds)
10. [Roadmap](#10-roadmap)

---

## 1. SYSTEM ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────────┐
│                    AI TRADING ALERT SYSTEM                          │
│                                                                     │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐  │
│  │ DATA LAYER   │───▶│  AI ENGINE   │───▶│  ALERT DISPATCHER    │  │
│  │              │    │              │    │                      │  │
│  │ • NSE/BSE    │    │ • Technical  │    │ • Telegram Bot       │  │
│  │   (yfinance, │    │   Analysis   │    │ • Email (optional)   │  │
│  │   NSEpy)     │    │   (TA-Lib)   │    │                      │  │
│  │ • US Stocks  │    │ • Sentiment  │    │ Alert Format:        │  │
│  │   (yfinance, │    │   Analysis   │    │  BUY/SELL/HOLD       │  │
│  │   Alpha      │    │   (NLP)      │    │  Entry Price         │  │
│  │   Vantage)   │    │ • ML Signal  │    │  Stop Loss           │  │
│  │ • News APIs  │    │   Scoring    │    │  Take Profit         │  │
│  │ • Financials │    │ • Risk Calc  │    │  Confidence %        │  │
│  └──────────────┘    └──────────────┘    └──────────────────────┘  │
│         │                   │                        │              │
│  ┌──────▼───────────────────▼────────────────────────▼───────────┐  │
│  │                    ORCHESTRATOR (scheduler.py)                │  │
│  │     Runs on cron/APScheduler — 9:15 AM & 3:00 PM IST daily   │  │
│  └───────────────────────────────────────────────────────────────┘  │
│         │                                                            │
│  ┌──────▼──────────────────────────────────────────────────────┐    │
│  │              LOCAL STORAGE / DATABASE                        │    │
│  │    SQLite (trade log) + CSV/Parquet (OHLCV cache)           │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Flow (Step by Step)
```
[Market Opens]
      │
      ▼
[Fetch OHLCV + News]          ← yfinance, Alpha Vantage, NewsAPI
      │
      ▼
[Compute Technical Indicators] ← TA-Lib (RSI, MACD, EMA, BB, ATR)
      │
      ▼
[Run Sentiment Analysis]       ← FinBERT / VADER on news headlines
      │
      ▼
[Score & Rank Signals]         ← Composite scoring (weighted model)
      │
      ▼
[Apply Risk Filters]           ← Stop-loss, position sizing, filters
      │
      ▼
[Generate Alert Payload]
      │
      ▼
[Send Telegram / Email Alert]
      │
      ▼
[Log to SQLite]                ← For backtesting and review
```

---

## 2. RECOMMENDED TECH STACK

| Layer | Tool / Library | Purpose |
|---|---|---|
| Language | Python 3.11+ | Core language |
| Data Fetching | `yfinance`, `nsepython`, `alpha_vantage` | Market data |
| Technical Analysis | `ta-lib`, `pandas-ta`, `ta` | Indicators |
| Sentiment | `transformers` (FinBERT), `vaderSentiment` | News NLP |
| ML / Scoring | `scikit-learn`, `xgboost` | Signal scoring |
| News | `newsapi-python`, `feedparser` | RSS/News |
| Alerts | `python-telegram-bot` | Push notifications |
| Scheduling | `APScheduler` | Cron-like jobs |
| Storage | `SQLite3`, `pandas`, `pyarrow` | Data persistence |
| Config | `python-dotenv` | Secrets management |
| Backtesting | `backtrader` or `vectorbt` | Strategy validation |
| Visualization | `plotly`, `matplotlib` | Charts in alerts |
| Environment | `venv` + Windows Task Scheduler | Local deployment |

---

## 3. DATA SOURCES & APIS

### Indian Markets (NSE/BSE)

| Source | Data Type | Cost | Library |
|---|---|---|---|
| `yfinance` | OHLCV, daily/weekly | Free | `yfinance` |
| `nsepython` | NSE live data, F&O | Free | `nsepython` |
| `jugaad-trader` | NSE historical, live | Free | `jugaad_trader` |
| NSE Official RSS | Market news | Free | `feedparser` |
| Screener.in | Fundamentals | Free (scrape) | `requests+bs4` |
| Ticker by Finology | Fundamentals | Free | API/scrape |

### US Markets

| Source | Data Type | Cost | Library |
|---|---|---|---|
| `yfinance` | OHLCV, daily | Free | `yfinance` |
| Alpha Vantage | OHLCV + fundamentals | Free (25 calls/day) | `alpha_vantage` |
| Polygon.io | Real-time + historical | Free tier (limited) | `requests` |
| SEC EDGAR | Financial statements | Free | `requests` |
| NewsAPI | Financial news | Free (100 req/day) | `newsapi-python` |

### Recommended Free Tier Strategy
- Use **yfinance** as primary OHLCV source (unlimited, reliable for EOD)
- Use **Alpha Vantage** for fundamentals (P/E, EPS)
- Use **NewsAPI** for sentiment (100 free requests/day is sufficient for swing trading)
- Use **nsepython** for NSE-specific data (circuit limits, delivery %)

---

## 4. STEP-BY-STEP IMPLEMENTATION GUIDE

### Step 1: Environment Setup

```bash
# Create project structure
mkdir trading_alert_system
cd trading_alert_system
mkdir -p {data,logs,alerts,models,config,backtest}

# Create virtual environment
python -m venv venv
venv\Scripts\activate   # Windows

# Install dependencies
pip install yfinance pandas numpy ta-lib pandas-ta \
            scikit-learn xgboost transformers vaderSentiment \
            python-telegram-bot newsapi-python feedparser \
            APScheduler python-dotenv requests beautifulsoup4 \
            plotly matplotlib sqlalchemy nsepython
```

### Step 2: Configuration File

Create `config/.env`:
```env
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# APIs
ALPHA_VANTAGE_KEY=your_key_here
NEWS_API_KEY=your_key_here

# Trading Preferences
RISK_PER_TRADE_PERCENT=2.0
MAX_POSITIONS=5
SWING_LOOKBACK_DAYS=90
```

Create `config/watchlist.yaml`:
```yaml
indian_stocks:
  - "RELIANCE.NS"
  - "INFY.NS"
  - "TCS.NS"
  - "HDFCBANK.NS"
  - "ICICIBANK.NS"
  - "WIPRO.NS"
  - "LT.NS"
  - "BAJFINANCE.NS"
  - "TITAN.NS"
  - "ADANIENT.NS"

us_stocks:
  - "AAPL"
  - "MSFT"
  - "NVDA"
  - "GOOGL"
  - "META"
  - "AMZN"
  - "TSLA"
  - "AMD"

portfolio_capital_inr: 500000
portfolio_capital_usd: 5000
```

---

## 5. CORE MODULE CODE

### Module 1: Data Fetcher (`data/fetcher.py`)

```python
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class MarketDataFetcher:
    def __init__(self, lookback_days: int = 90):
        self.lookback_days = lookback_days
        self.end_date = datetime.today()
        self.start_date = self.end_date - timedelta(days=lookback_days)

    def fetch_ohlcv(self, ticker: str) -> pd.DataFrame:
        """Fetch OHLCV data for a given ticker."""
        try:
            df = yf.download(
                ticker,
                start=self.start_date.strftime("%Y-%m-%d"),
                end=self.end_date.strftime("%Y-%m-%d"),
                interval="1d",
                progress=False
            )
            if df.empty:
                logger.warning(f"No data for {ticker}")
                return pd.DataFrame()
            df.dropna(inplace=True)
            logger.info(f"Fetched {len(df)} rows for {ticker}")
            return df
        except Exception as e:
            logger.error(f"Error fetching {ticker}: {e}")
            return pd.DataFrame()

    def fetch_fundamentals(self, ticker: str) -> dict:
        """Fetch key fundamental data."""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            return {
                "pe_ratio": info.get("trailingPE", None),
                "pb_ratio": info.get("priceToBook", None),
                "debt_to_equity": info.get("debtToEquity", None),
                "roe": info.get("returnOnEquity", None),
                "revenue_growth": info.get("revenueGrowth", None),
                "market_cap": info.get("marketCap", None),
                "52w_high": info.get("fiftyTwoWeekHigh", None),
                "52w_low": info.get("fiftyTwoWeekLow", None),
            }
        except Exception as e:
            logger.error(f"Fundamentals error for {ticker}: {e}")
            return {}

    def fetch_batch(self, tickers: list) -> dict:
        """Fetch data for multiple tickers."""
        results = {}
        for ticker in tickers:
            results[ticker] = {
                "ohlcv": self.fetch_ohlcv(ticker),
                "fundamentals": self.fetch_fundamentals(ticker)
            }
        return results
```

### Module 2: Technical Analysis Engine (`data/technical.py`)

```python
import pandas as pd
import pandas_ta as ta
import numpy as np

class TechnicalAnalyzer:
    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute all technical indicators for swing trading."""
        if df.empty or len(df) < 26:
            return df

        # --- Trend Indicators ---
        df['EMA_20']  = ta.ema(df['Close'], length=20)
        df['EMA_50']  = ta.ema(df['Close'], length=50)
        df['EMA_200'] = ta.ema(df['Close'], length=200)
        df['SMA_20']  = ta.sma(df['Close'], length=20)

        # --- Momentum ---
        df['RSI'] = ta.rsi(df['Close'], length=14)
        macd = ta.macd(df['Close'], fast=12, slow=26, signal=9)
        df['MACD']        = macd['MACD_12_26_9']
        df['MACD_Signal'] = macd['MACDs_12_26_9']
        df['MACD_Hist']   = macd['MACDh_12_26_9']

        # --- Volatility ---
        bb = ta.bbands(df['Close'], length=20, std=2)
        df['BB_Upper'] = bb['BBU_20_2.0']
        df['BB_Middle'] = bb['BBM_20_2.0']
        df['BB_Lower'] = bb['BBL_20_2.0']
        df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)

        # --- Volume ---
        df['Volume_MA20'] = df['Volume'].rolling(20).mean()
        df['Volume_Ratio'] = df['Volume'] / df['Volume_MA20']

        # --- Stochastic ---
        stoch = ta.stoch(df['High'], df['Low'], df['Close'])
        df['STOCH_K'] = stoch['STOCHk_14_3_3']
        df['STOCH_D'] = stoch['STOCHd_14_3_3']

        # --- ADX (Trend Strength) ---
        adx = ta.adx(df['High'], df['Low'], df['Close'], length=14)
        df['ADX'] = adx['ADX_14']

        return df

    def generate_signal(self, df: pd.DataFrame) -> dict:
        """Score the stock based on indicator confluence."""
        if df.empty or len(df) < 50:
            return {"signal": "INSUFFICIENT_DATA", "score": 0, "reasons": []}

        last = df.iloc[-1]
        prev = df.iloc[-2]
        score = 0
        reasons = []

        # --- Trend Checks ---
        if last['EMA_20'] > last['EMA_50'] > last['EMA_200']:
            score += 25
            reasons.append("✅ Bullish EMA stack (20>50>200)")
        elif last['EMA_20'] < last['EMA_50'] < last['EMA_200']:
            score -= 25
            reasons.append("🔴 Bearish EMA stack")

        if last['Close'] > last['EMA_20']:
            score += 10
            reasons.append("✅ Price above EMA20")
        else:
            score -= 10
            reasons.append("🔴 Price below EMA20")

        # --- RSI ---
        if 40 <= last['RSI'] <= 60:
            score += 5
            reasons.append(f"✅ RSI neutral ({last['RSI']:.1f})")
        elif last['RSI'] < 35:
            score += 15
            reasons.append(f"✅ RSI oversold ({last['RSI']:.1f}) - potential bounce")
        elif last['RSI'] > 70:
            score -= 15
            reasons.append(f"🔴 RSI overbought ({last['RSI']:.1f})")

        # --- MACD ---
        if last['MACD'] > last['MACD_Signal'] and prev['MACD'] <= prev['MACD_Signal']:
            score += 20
            reasons.append("✅ MACD bullish crossover")
        elif last['MACD'] > last['MACD_Signal']:
            score += 10
            reasons.append("✅ MACD above signal")
        elif last['MACD'] < last['MACD_Signal']:
            score -= 10
            reasons.append("🔴 MACD below signal")

        # --- Volume Confirmation ---
        if last['Volume_Ratio'] > 1.5:
            score += 15
            reasons.append(f"✅ High volume ({last['Volume_Ratio']:.1f}x avg)")
        elif last['Volume_Ratio'] < 0.5:
            score -= 10
            reasons.append("🔴 Low volume (weak move)")

        # --- ADX Trend Strength ---
        if last['ADX'] > 25:
            score += 10
            reasons.append(f"✅ Strong trend (ADX {last['ADX']:.1f})")

        # --- Bollinger Band Position ---
        if last['Close'] <= last['BB_Lower']:
            score += 15
            reasons.append("✅ Price at/below lower Bollinger Band")
        elif last['Close'] >= last['BB_Upper']:
            score -= 15
            reasons.append("🔴 Price at/above upper Bollinger Band")

        # --- Signal Classification ---
        if score >= 55:
            signal = "BUY"
        elif score <= -30:
            signal = "SELL"
        elif score >= 30:
            signal = "WATCH"
        else:
            signal = "HOLD"

        return {
            "signal": signal,
            "score": score,
            "reasons": reasons,
            "rsi": round(last['RSI'], 2),
            "macd_hist": round(last['MACD_Hist'], 4),
            "adx": round(last['ADX'], 2),
            "close": round(last['Close'], 2),
            "atr": round(last['ATR'], 2),
        }
```

### Module 3: Sentiment Analyzer (`data/sentiment.py`)

```python
from newsapi import NewsApiClient
import feedparser
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import os

class SentimentAnalyzer:
    def __init__(self):
        self.vader = SentimentIntensityAnalyzer()
        self.newsapi_key = os.getenv("NEWS_API_KEY")
        if self.newsapi_key:
            self.newsapi = NewsApiClient(api_key=self.newsapi_key)

    def fetch_news_headlines(self, company_name: str, market: str = "US") -> list:
        """Fetch news headlines for a given company."""
        headlines = []
        if market == "US" and self.newsapi_key:
            try:
                articles = self.newsapi.get_everything(
                    q=company_name,
                    language='en',
                    sort_by='publishedAt',
                    page_size=10
                )
                headlines = [a['title'] for a in articles.get('articles', [])]
            except Exception as e:
                print(f"NewsAPI error: {e}")
        
        # Fallback: Google News RSS
        try:
            rss_url = f"https://news.google.com/rss/search?q={company_name}+stock&hl=en-IN"
            feed = feedparser.parse(rss_url)
            headlines += [entry.title for entry in feed.entries[:10]]
        except Exception:
            pass

        return headlines[:15]

    def analyze_sentiment(self, headlines: list) -> dict:
        """Compute aggregate sentiment score."""
        if not headlines:
            return {"score": 0.0, "label": "NEUTRAL", "count": 0}

        scores = []
        for headline in headlines:
            vs = self.vader.polarity_scores(headline)
            scores.append(vs['compound'])

        avg_score = sum(scores) / len(scores)
        label = "POSITIVE" if avg_score > 0.05 else "NEGATIVE" if avg_score < -0.05 else "NEUTRAL"

        return {
            "score": round(avg_score, 3),
            "label": label,
            "count": len(headlines),
            "headlines_sample": headlines[:3]
        }

    def get_stock_sentiment(self, ticker: str, company_name: str, market: str = "US") -> dict:
        headlines = self.fetch_news_headlines(company_name, market)
        return self.analyze_sentiment(headlines)
```

### Module 4: Risk Manager (`data/risk.py`)

```python
class RiskManager:
    def __init__(self, capital: float, risk_per_trade_pct: float = 2.0, max_positions: int = 5):
        self.capital = capital
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_positions = max_positions

    def calculate_levels(self, current_price: float, atr: float, signal: str) -> dict:
        """
        ATR-based dynamic Stop Loss and Take Profit.
        Swing trade targets: 2:1 or 3:1 Risk/Reward ratio.
        """
        atr_multiplier_sl = 1.5   # SL = 1.5x ATR below entry
        atr_multiplier_tp1 = 2.0  # TP1 = 2x ATR above (partial exit)
        atr_multiplier_tp2 = 3.5  # TP2 = 3.5x ATR above (full exit)

        if signal == "BUY":
            stop_loss   = round(current_price - (atr * atr_multiplier_sl), 2)
            take_profit1 = round(current_price + (atr * atr_multiplier_tp1), 2)
            take_profit2 = round(current_price + (atr * atr_multiplier_tp2), 2)
        else:  # SELL/SHORT (informational only for retail)
            stop_loss   = round(current_price + (atr * atr_multiplier_sl), 2)
            take_profit1 = round(current_price - (atr * atr_multiplier_tp1), 2)
            take_profit2 = round(current_price - (atr * atr_multiplier_tp2), 2)

        risk_per_share = abs(current_price - stop_loss)
        position_size  = self.calculate_position_size(risk_per_share)
        risk_reward    = round(abs(take_profit2 - current_price) / risk_per_share, 2)

        return {
            "entry_price": current_price,
            "stop_loss": stop_loss,
            "take_profit_1": take_profit1,  # Partial exit (50%)
            "take_profit_2": take_profit2,  # Full exit
            "risk_per_share": round(risk_per_share, 2),
            "position_size_units": position_size,
            "capital_at_risk": round(risk_per_share * position_size, 2),
            "risk_reward_ratio": risk_reward,
            "sl_percent": round((risk_per_share / current_price) * 100, 2),
        }

    def calculate_position_size(self, risk_per_share: float) -> int:
        """Position sizing based on fixed % capital risk."""
        if risk_per_share <= 0:
            return 0
        max_loss = self.capital * (self.risk_per_trade_pct / 100)
        units = int(max_loss / risk_per_share)
        max_single_position = int(self.capital * 0.20 / risk_per_share)
        return min(units, max_single_position)  # Never >20% in one stock

    def apply_filters(self, signal_data: dict) -> tuple[bool, str]:
        """Gate-keeping filters before issuing an alert."""
        score = signal_data.get("score", 0)
        rr    = signal_data.get("risk_reward_ratio", 0)
        adx   = signal_data.get("adx", 0)

        if score < 55 and signal_data.get("signal") == "BUY":
            return False, f"Score too low ({score})"
        if rr < 1.5:
            return False, f"Risk/Reward too low ({rr})"
        if signal_data.get("signal") == "BUY" and adx < 20:
            return False, f"Weak trend (ADX {adx})"

        return True, "Passed all filters"
```

### Module 5: Alert Dispatcher (`alerts/telegram_bot.py`)

```python
import asyncio
import telegram
import os
from datetime import datetime

class TelegramAlerter:
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id   = os.getenv("TELEGRAM_CHAT_ID")
        self.bot = telegram.Bot(token=self.bot_token)

    def format_alert(self, ticker: str, signal_data: dict, risk_data: dict,
                     sentiment: dict, market: str) -> str:
        signal = signal_data['signal']
        emoji  = "🟢" if signal == "BUY" else "🔴" if signal == "SELL" else "🟡"
        sent_emoji = "😊" if sentiment['label'] == "POSITIVE" else "😟" if sentiment['label'] == "NEGATIVE" else "😐"

        msg = f"""
{emoji} *TRADING ALERT — {signal}*
━━━━━━━━━━━━━━━━━━━━━━━━
📊 *Stock:* `{ticker}` ({market})
📅 *Date:* {datetime.now().strftime('%d %b %Y, %H:%M IST')}
💰 *Entry Price:* ₹{risk_data['entry_price'] if market == 'IN' else '$'}{risk_data['entry_price']}

🎯 *TRADE LEVELS*
  • Stop Loss:    {risk_data['stop_loss']} ({risk_data['sl_percent']}% risk)
  • Take Profit 1: {risk_data['take_profit_1']} (50% exit)
  • Take Profit 2: {risk_data['take_profit_2']} (full exit)
  • Risk/Reward:  {risk_data['risk_reward_ratio']}:1

📦 *POSITION SIZING*
  • Units to buy: {risk_data['position_size_units']}
  • Capital at risk: {risk_data['capital_at_risk']}

📈 *TECHNICAL SIGNALS* (Score: {signal_data['score']}/100)
"""
        for reason in signal_data.get('reasons', [])[:5]:
            msg += f"  {reason}\n"

        msg += f"""
🗞️ *SENTIMENT:* {sent_emoji} {sentiment['label']} ({sentiment['score']})
  _{sentiment.get('headlines_sample', ['N/A'])[0][:80]}_

⚠️ *ACTION REQUIRED:*
  Open {'Groww' if market == 'IN' else 'IndMoney'} and execute manually.
  Set SL immediately after entry.

_This is an AI advisory alert. Trade at your own risk._
        """
        return msg.strip()

    async def send_alert_async(self, message: str):
        async with self.bot:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='Markdown'
            )

    def send_alert(self, message: str):
        asyncio.run(self.send_alert_async(message))

    def send_daily_summary(self, results: list):
        """Send EOD summary of all scanned stocks."""
        buys   = [r for r in results if r['signal'] == 'BUY']
        sells  = [r for r in results if r['signal'] == 'SELL']
        watches = [r for r in results if r['signal'] == 'WATCH']

        msg = f"""
📋 *DAILY MARKET SCAN SUMMARY*
📅 {datetime.now().strftime('%d %b %Y')}
━━━━━━━━━━━━━━━━━━━━━━━━
🟢 BUY Signals:  {len(buys)}
🔴 SELL Signals: {len(sells)}
🟡 WATCH:        {len(watches)}

🏆 *Top BUY Opportunities:*
"""
        for r in sorted(buys, key=lambda x: x['score'], reverse=True)[:3]:
            msg += f"  • {r['ticker']} — Score: {r['score']}, RR: {r.get('risk_reward_ratio','N/A')}:1\n"

        self.send_alert(msg)
```

### Module 6: Main Orchestrator (`main.py`)

```python
import yaml
import logging
import sqlite3
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

from data.fetcher import MarketDataFetcher
from data.technical import TechnicalAnalyzer
from data.sentiment import SentimentAnalyzer
from data.risk import RiskManager
from alerts.telegram_bot import TelegramAlerter

load_dotenv("config/.env")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler("logs/trading.log"), logging.StreamHandler()])
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

    fetcher   = MarketDataFetcher(lookback_days=90)
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
```

### Module 7: Scheduler (`scheduler.py`)

```python
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
from main import run_scan

logging.basicConfig(level=logging.INFO)
scheduler = BlockingScheduler(timezone="Asia/Kolkata")

# Indian market: Run at 9:20 AM and 3:10 PM IST (Mon-Fri)
scheduler.add_job(run_scan, CronTrigger(day_of_week='mon-fri', hour=9, minute=20))
scheduler.add_job(run_scan, CronTrigger(day_of_week='mon-fri', hour=15, minute=10))

# US market close scan: 1:30 AM IST (US market EOD)
scheduler.add_job(run_scan, CronTrigger(day_of_week='mon-fri', hour=1, minute=30))

print("Scheduler running. Press Ctrl+C to exit.")
scheduler.start()
```

---

## 6. RISK MANAGEMENT FRAMEWORK

### The 5 Hard Rules (Never Break These)

| Rule | Detail |
|---|---|
| **2% Rule** | Never risk more than 2% of total capital on a single trade |
| **20% Concentration** | No single stock > 20% of portfolio |
| **ATR-based SL** | Stop loss always set at 1.5x ATR — not emotional levels |
| **2:1 Min R:R** | Only take trades where TP2 ≥ 2x the risk amount |
| **Max 5 Positions** | At any time, hold ≤ 5 open positions across both markets |

### Trade Management Protocol
```
Entry → Set SL immediately on Groww/IndMoney
      → At TP1 (2x ATR): exit 50% of position, move SL to breakeven
      → At TP2 (3.5x ATR): exit remaining 50%
      → If stock falls to SL before TP: exit all, log the trade
```

### Market Regime Filter
Before any BUY signal, check:
- Nifty 50 / S&P 500 must be above its 50-day SMA (don't buy in bear markets)
- VIX (India: India VIX) < 20 preferred. If VIX > 25: reduce position size by 50%

---

## 7. ALERT SYSTEM SETUP

### Setting Up Telegram Bot
1. Open Telegram, search for `@BotFather`
2. Send `/newbot`, follow prompts → get your **Bot Token**
3. Start a chat with your bot
4. Visit: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
5. Copy the `chat.id` from the JSON response
6. Add both to your `.env` file

### Sample Telegram Alert Output
```
🟢 TRADING ALERT — BUY
━━━━━━━━━━━━━━━━━━━━━━━━
📊 Stock: INFY.NS (IN)
📅 Date: 15 Jul 2025, 09:22 IST
💰 Entry Price: ₹1,847.50

🎯 TRADE LEVELS
  • Stop Loss:     ₹1,798.20 (2.67% risk)
  • Take Profit 1: ₹1,921.80 (50% exit)
  • Take Profit 2: ₹2,014.60 (full exit)
  • Risk/Reward:   3.1:1

📦 POSITION SIZING
  • Units to buy: 20
  • Capital at risk: ₹986.00

📈 TECHNICAL SIGNALS (Score: 72/100)
  ✅ Bullish EMA stack (20>50>200)
  ✅ MACD bullish crossover
  ✅ RSI neutral (48.3)
  ✅ High volume (2.1x avg)
  ✅ Strong trend (ADX 28.4)

🗞️ SENTIMENT: 😊 POSITIVE (0.412)
  "Infosys wins $1.5bn deal with UK retailer..."

⚠️ ACTION REQUIRED:
  Open Groww and execute manually.
  Set SL immediately after entry.
```

---

## 8. SCHEDULING & DEPLOYMENT

### Option A: Windows Task Scheduler (Recommended for your laptop)

1. Create `run_scanner.bat`:
```bat
@echo off
cd C:\Users\YourName\trading_alert_system
call venv\Scripts\activate
python main.py >> logs\scheduler.log 2>&1
```

2. Open Task Scheduler → Create Basic Task
3. Trigger: Daily, weekdays, 9:20 AM
4. Action: Run `run_scanner.bat`
5. Repeat for 3:10 PM IST and 1:30 AM IST (US market)

### Option B: Always-On Cloud (Free)
- **Oracle Cloud Free Tier** (1 AMD VM, free forever) — run the scheduler 24/7
- **PythonAnywhere** — free tier supports scheduled tasks
- **Railway.app** — free tier with GitHub deploy

### Option C: Keep Laptop Always On
- Change Windows power settings: "Never" sleep when plugged in
- Enable Wake-on-Timer in BIOS for morning scans

---

## 9. LIMITATIONS & WORKAROUNDS

### Critical Limitation: No Direct API Access on Groww/IndMoney

| Challenge | Impact | Workaround |
|---|---|---|
| No order API | Can't auto-execute | Use as advisory — alerts tell you exactly what to do |
| Manual execution delay | 1–5 min latency after alert | For swing trades (days/weeks), this is acceptable |
| Price slippage | Entry may differ slightly | Use limit orders, not market orders |
| After-hours alerts | US market closes at 1:30 AM IST | Set phone notifications; check at 7 AM before Indian open |

### Data Limitations

| Limitation | Workaround |
|---|---|
| yfinance rate limits | Cache data locally in SQLite/CSV; re-fetch only on market days |
| Alpha Vantage 25 calls/day | Use for fundamentals only (monthly refresh) |
| NewsAPI 100 calls/day | Batch sentiment for top 5 signals only |
| No real-time tick data | Swing trading on EOD data is fine — doesn't need tick data |

### System Reliability
- **Internet drops** → APScheduler will miss jobs; use Windows Task Scheduler as fallback
- **yfinance API changes** → Pin `yfinance==0.2.x` and test after upgrades
- **False signals** → Always apply all 3 layers (technical + sentiment + risk filter) before alerting

### Psychological Discipline
> The system will generate signals. You must still exercise discipline:
> - Don't override Stop Losses manually
> - Don't chase stocks after you miss the entry
> - Log every trade (the SQLite DB does this automatically)
> - Review weekly: which signals worked and which didn't

---

## 10. ROADMAP

### Phase 1 (Week 1–2): Foundation
- [ ] Set up project structure and virtual environment
- [ ] Configure API keys and watchlist
- [ ] Test data fetching for 5 stocks (IN + US)
- [ ] Set up Telegram bot and test alert sending

### Phase 2 (Week 3–4): Core Engine
- [ ] Implement TechnicalAnalyzer and validate indicators visually
- [ ] Implement RiskManager and validate SL/TP calculations
- [ ] Run main.py manually for 5 trading days — compare alerts to actual market moves

### Phase 3 (Week 5–6): Sentiment + Automation
- [ ] Add SentimentAnalyzer
- [ ] Set up scheduler (Windows Task Scheduler)
- [ ] Run fully automated for 2 weeks — track all signals in DB

### Phase 4 (Month 2): Backtesting
- [ ] Use `vectorbt` to backtest the scoring logic on 2 years of data
- [ ] Tune indicator weights based on results
- [ ] Add market regime filter (Nifty50 / SPX above 50-DMA)

### Phase 5 (Month 3+): Enhancement
- [ ] Add FinBERT (better than VADER for financial text) via HuggingFace
- [ ] Add fundamental scoring layer (P/E, ROE, Debt/Equity)
- [ ] Build a simple Streamlit dashboard for visual review
- [ ] Consider migrating to Zerodha Kite (has full API access) for automated execution

---

## QUICK START CHECKLIST

```
☐ 1. Clone/create project structure
☐ 2. pip install all dependencies
☐ 3. Set up .env with API keys
☐ 4. Add stocks to watchlist.yaml
☐ 5. Create Telegram bot, get token + chat_id
☐ 6. Run: python main.py (manual test)
☐ 7. Verify Telegram message received
☐ 8. Set up Windows Task Scheduler
☐ 9. Monitor logs/ folder daily
☐ 10. Paper trade for 30 days before using real money
```

---

*Built for swing trading on NSE/BSE and US markets | Advisory mode only | Always use Stop Losses*
