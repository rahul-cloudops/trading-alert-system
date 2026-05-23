import pandas as pd
import pandas_ta as ta
import numpy as np
import logging

logger = logging.getLogger(__name__)

class TechnicalAnalyzer:

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or len(df) < 30:
            return df

        close = df['Close'].squeeze()
        high  = df['High'].squeeze()
        low   = df['Low'].squeeze()
        vol   = df['Volume'].squeeze()

        # --- Trend ---
        df['EMA_20']  = ta.ema(close, length=20)
        df['EMA_50']  = ta.ema(close, length=50)
        df['EMA_200'] = ta.ema(close, length=200)
        df['SMA_20']  = ta.sma(close, length=20)

        # --- MACD (safe extraction) ---
        macd = ta.macd(close, fast=12, slow=26, signal=9)
        if macd is not None and not macd.empty:
            macd_col   = next((c for c in macd.columns if c.startswith('MACD_') and not c.startswith('MACDs') and not c.startswith('MACDh')), None)
            signal_col = next((c for c in macd.columns if c.startswith('MACDs_')), None)
            hist_col   = next((c for c in macd.columns if c.startswith('MACDh_')), None)
            df['MACD']        = macd[macd_col]   if macd_col   else np.nan
            df['MACD_Signal'] = macd[signal_col] if signal_col else np.nan
            df['MACD_Hist']   = macd[hist_col]   if hist_col   else np.nan
        else:
            logger.warning("MACD returned None — computing manually")
            ema12 = close.ewm(span=12, adjust=False).mean()
            ema26 = close.ewm(span=26, adjust=False).mean()
            df['MACD']        = ema12 - ema26
            df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
            df['MACD_Hist']   = df['MACD'] - df['MACD_Signal']

        # --- RSI ---
        rsi = ta.rsi(close, length=14)
        df['RSI'] = rsi if rsi is not None else close.diff().pipe(
            lambda d: 100 - 100 / (1 + d.clip(lower=0).rolling(14).mean() /
                                       (-d.clip(upper=0)).rolling(14).mean()))

        # --- Bollinger Bands ---
        bb = ta.bbands(close, length=20, std=2)
        if bb is not None and not bb.empty:
            df['BB_Upper']  = bb.iloc[:, 0]
            df['BB_Middle'] = bb.iloc[:, 1]
            df['BB_Lower']  = bb.iloc[:, 2]
        else:
            sma = close.rolling(20).mean()
            std = close.rolling(20).std()
            df['BB_Upper']  = sma + 2 * std
            df['BB_Middle'] = sma
            df['BB_Lower']  = sma - 2 * std

        # --- ATR ---
        atr = ta.atr(high, low, close, length=14)
        if atr is not None:
            df['ATR'] = atr
        else:
            tr = pd.concat([
                high - low,
                (high - close.shift()).abs(),
                (low  - close.shift()).abs()
            ], axis=1).max(axis=1)
            df['ATR'] = tr.rolling(14).mean()

        # --- Volume ---
        df['Volume_MA20'] = vol.rolling(20).mean()
        df['Volume_Ratio'] = vol / df['Volume_MA20'].replace(0, np.nan)

        # --- Stochastic ---
        stoch = ta.stoch(high, low, close)
        if stoch is not None and not stoch.empty:
            df['STOCH_K'] = stoch.iloc[:, 0]
            df['STOCH_D'] = stoch.iloc[:, 1]
        else:
            low14  = low.rolling(14).min()
            high14 = high.rolling(14).max()
            df['STOCH_K'] = 100 * (close - low14) / (high14 - low14).replace(0, np.nan)
            df['STOCH_D'] = df['STOCH_K'].rolling(3).mean()

        # --- ADX ---
        adx_result = ta.adx(high, low, close, length=14)
        if adx_result is not None and not adx_result.empty:
            adx_col = next((c for c in adx_result.columns if c.startswith('ADX_')), None)
            df['ADX'] = adx_result[adx_col] if adx_col else np.nan
        else:
            df['ADX'] = np.nan

        return df

    def generate_signal(self, df: pd.DataFrame) -> dict:
        if df.empty or len(df) < 50:
            return {"signal": "INSUFFICIENT_DATA", "score": 0, "reasons": []}

        last = df.iloc[-1]
        prev = df.iloc[-2]
        score = 0
        reasons = []

        def safe(val):
            """Return float or None if NaN/missing."""
            try:
                return float(val) if pd.notna(val) else None
            except Exception:
                return None

        close   = safe(last.get('Close'))
        ema20   = safe(last.get('EMA_20'))
        ema50   = safe(last.get('EMA_50'))
        ema200  = safe(last.get('EMA_200'))
        rsi     = safe(last.get('RSI'))
        macd    = safe(last.get('MACD'))
        macd_s  = safe(last.get('MACD_Signal'))
        macd_h  = safe(last.get('MACD_Hist'))
        p_macd  = safe(prev.get('MACD'))
        p_macd_s= safe(prev.get('MACD_Signal'))
        vol_r   = safe(last.get('Volume_Ratio'))
        adx     = safe(last.get('ADX'))
        bb_u    = safe(last.get('BB_Upper'))
        bb_l    = safe(last.get('BB_Lower'))
        atr     = safe(last.get('ATR'))

        if close is None or atr is None:
            return {"signal": "INSUFFICIENT_DATA", "score": 0, "reasons": ["Missing close/ATR"]}

        # EMA trend stack
        if all(v is not None for v in [ema20, ema50, ema200]):
            if ema20 > ema50 > ema200:
                score += 25
                reasons.append("[+] Bullish EMA stack (20>50>200)")
            elif ema20 < ema50 < ema200:
                score -= 25
                reasons.append("[-] Bearish EMA stack")

        if ema20 is not None:
            if close > ema20:
                score += 10
                reasons.append("[+] Price above EMA20")
            else:
                score -= 10
                reasons.append("[-] Price below EMA20")

        # RSI
        if rsi is not None:
            if rsi < 35:
                score += 15
                reasons.append(f"[+] RSI oversold ({rsi:.1f})")
            elif rsi > 70:
                score -= 15
                reasons.append(f"[-] RSI overbought ({rsi:.1f})")
            else:
                score += 5
                reasons.append(f"[~] RSI neutral ({rsi:.1f})")

        # MACD
        if all(v is not None for v in [macd, macd_s, p_macd, p_macd_s]):
            if macd > macd_s and p_macd <= p_macd_s:
                score += 20
                reasons.append("[+] MACD bullish crossover")
            elif macd > macd_s:
                score += 10
                reasons.append("[+] MACD above signal")
            elif macd < macd_s:
                score -= 10
                reasons.append("[-] MACD below signal")

        # Volume
        if vol_r is not None:
            if vol_r > 1.5:
                score += 15
                reasons.append(f"[+] High volume ({vol_r:.1f}x avg)")
            elif vol_r < 0.5:
                score -= 10
                reasons.append("[-] Low volume")

        # ADX
        if adx is not None and adx > 25:
            score += 10
            reasons.append(f"[+] Strong trend (ADX {adx:.1f})")

        # Bollinger Bands
        if all(v is not None for v in [bb_l, bb_u]):
            if close <= bb_l:
                score += 15
                reasons.append("[+] Price at lower Bollinger Band")
            elif close >= bb_u:
                score -= 15
                reasons.append("[-] Price at upper Bollinger Band")

        # Signal classification
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
            "rsi":      round(rsi, 2)   if rsi  is not None else None,
            "macd_hist": round(macd_h, 4) if macd_h is not None else None,
            "adx":      round(adx, 2)   if adx  is not None else None,
            "close":    round(close, 2),
            "atr":      round(atr, 2),
        }