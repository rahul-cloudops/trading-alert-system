import yfinance as yf
import pandas_ta as ta
import pandas as pd

df = yf.download("AAPL", period="3mo", interval="1d", progress=False)

# Flatten MultiIndex columns if present (common yfinance v0.2.x issue)
if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)

print("Columns after flatten:", df.columns.tolist())
print("Shape:", df.shape)
print("Close sample:\n", df['Close'].tail(3))

# Test each indicator one by one
print("\n--- Testing EMA ---")
ema = ta.ema(df['Close'], length=20)
print("EMA result:", type(ema), "None?", ema is None)

print("\n--- Testing MACD ---")
macd = ta.macd(df['Close'], fast=12, slow=26, signal=9)
print("MACD result:", type(macd))
if macd is not None:
    print("MACD columns:", macd.columns.tolist())
else:
    print("MACD is None!")

print("\n--- Testing RSI ---")
rsi = ta.rsi(df['Close'], length=14)
print("RSI result:", type(rsi), "None?", rsi is None)