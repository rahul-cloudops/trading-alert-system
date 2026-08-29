import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import logging
import time
from functools import wraps

logger = logging.getLogger(__name__)

def retry_on_failure(max_retries=3, backoff_factor=2):
    """Exponential backoff decorator for transient yfinance API failures."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries <= max_retries:
                try:
                    result = func(*args, **kwargs)
                    # yfinance often returns an empty DF instead of raising an error on failure
                    if isinstance(result, pd.DataFrame) and result.empty:
                        raise ValueError("yfinance returned an empty DataFrame.")
                    return result
                except Exception as e:
                    if retries == max_retries:
                        logger.error(f"❌ Failed {func.__name__} after {max_retries} attempts: {e}")
                        return pd.DataFrame() if func.__name__ == 'fetch_ohlcv' else {}
                    
                    sleep_time = backoff_factor ** (retries + 1)
                    logger.warning(f"⚠️ {func.__name__} failed: {e}. Retrying in {sleep_time}s ({retries + 1}/{max_retries})...")
                    time.sleep(sleep_time)
                    retries += 1
        return wrapper
    return decorator

class MarketDataFetcher:
    def __init__(self, lookback_days: int = 90):
        self.lookback_days = lookback_days
        self.end_date = datetime.today()
        self.start_date = self.end_date - timedelta(days=lookback_days)

    @retry_on_failure(max_retries=3, backoff_factor=2)
    def fetch_ohlcv(self, ticker: str) -> pd.DataFrame:
        """Fetch OHLCV data for a given ticker."""
        df = yf.download(
            ticker,
            start=self.start_date.strftime("%Y-%m-%d"),
            end=self.end_date.strftime("%Y-%m-%d"),
            interval="1d",
            progress=False,
            auto_adjust=True
        )

        # Flatten MultiIndex columns returned by yfinance 0.2.x+
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Ensure standard column names exist
        required = ['Open', 'High', 'Low', 'Close', 'Volume']
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"Missing columns for {ticker}: {missing}")

        df.dropna(inplace=True)
        logger.info(f"✅ Fetched {len(df)} rows for {ticker}")
        return df

    @retry_on_failure(max_retries=3, backoff_factor=2)
    def fetch_fundamentals(self, ticker: str) -> dict:
        """Fetch key fundamental data."""
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # Validate that we actually got data back
        if not info or 'trailingPE' not in info and 'marketCap' not in info:
             raise ValueError("Incomplete fundamental data received.")

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

    def fetch_batch(self, tickers: list) -> dict:
        """Fetch data for multiple tickers."""
        results = {}
        for ticker in tickers:
            results[ticker] = {
                "ohlcv": self.fetch_ohlcv(ticker),
                "fundamentals": self.fetch_fundamentals(ticker)
            }
        return results