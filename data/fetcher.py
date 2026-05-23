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
            # df = yf.download(
            #     ticker,
            #     start=self.start_date.strftime("%Y-%m-%d"),
            #     end=self.end_date.strftime("%Y-%m-%d"),
            #     interval="1d",
            #     progress=False
            # )
            # if df.empty:
            #     logger.warning(f"No data for {ticker}")
            #     return pd.DataFrame()
            # df.dropna(inplace=True)

            df = yf.download(
                ticker,
                start=self.start_date.strftime("%Y-%m-%d"),
                end=self.end_date.strftime("%Y-%m-%d"),
                interval="1d",
                progress=False,
                auto_adjust=True
            )
            if df.empty:
                logger.warning(f"No data for {ticker}")
                return pd.DataFrame()

            # Flatten MultiIndex columns returned by yfinance 0.2.x+
            # e.g. ('Close', 'AAPL') -> 'Close'
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            # Ensure standard column names exist
            required = ['Open', 'High', 'Low', 'Close', 'Volume']
            missing = [c for c in required if c not in df.columns]
            if missing:
                logger.warning(f"Missing columns for {ticker}: {missing}")
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