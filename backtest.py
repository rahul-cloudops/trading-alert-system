"""
backtest.py
-----------
Discrete-event walk-forward backtester for the AI Trading Alert System.
Simulates bar-by-bar execution matching production scoring and risk models.
"""

import yaml
import logging
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from data.fetcher import MarketDataFetcher
from data.technical import TechnicalAnalyzer
from data.risk import RiskManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("Backtester")

LEVERAGE_MAP = {
    "SOXL": 3.0,
    "USD": 2.0,
    "TQQQ": 3.0,
    "UPRO": 3.0
}

ETF_KEYWORDS = ['GOLD', 'SILV', 'BEES', 'ETF', 'MON100', 'VOO', 'SCHD', 'USD', 'SOXL']


class Position:
    def __init__(self, ticker: str, market: str, entry_date: pd.Timestamp, 
                 entry_price: float, units: int, stop_loss: float, 
                 tp1: float, tp2: float, risk_per_share: float, is_etf: bool = False):
        self.ticker = ticker
        self.market = market
        self.entry_date = entry_date
        self.entry_price = entry_price
        self.total_units = units
        self.remaining_units = units
        self.stop_loss = stop_loss
        self.tp1 = tp1
        self.tp2 = tp2
        self.risk_per_share = risk_per_share
        self.is_etf = is_etf
        self.tp1_hit = False
        self.realized_pnl = 0.0
        self.closed = False
        self.exit_date = None
        self.exit_reason = None


class BacktestEngine:
    def __init__(self, config_path: str = "config/watchlist.yaml", lookback_days: int = 730):
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        self.lookback_days = lookback_days
        self.fetcher = MarketDataFetcher(lookback_days=lookback_days)
        self.ta = TechnicalAnalyzer()
        self.max_positions = 5

    def run(self, market: str = "IN") -> dict:
        tickers = self.config['indian_stocks'] if market == "IN" else self.config['us_stocks']
        initial_capital = float(self.config['portfolio_capital_inr'] if market == "IN" else self.config['portfolio_capital_usd'])
        
        # 1. Fetch & prep Macro Benchmark for walk-forward regime check
        index_ticker = "^NSEI" if market == "IN" else "^GSPC"
        logger.info(f"Loading Macro Index ({index_ticker}) for regime detection...")
        idx_df = self.fetcher.fetch_ohlcv(index_ticker)
        if not idx_df.empty:
            idx_df['SMA_50'] = idx_df['Close'].rolling(50).mean()

        # 2. Fetch & prep OHLCV data for watchlist assets
        logger.info(f"Loading {len(tickers)} assets for {market} backtest over {self.lookback_days} days...")
        data_store = {}
        for ticker in tickers:
            df = self.fetcher.fetch_ohlcv(ticker)
            if not df.empty and len(df) > 60:
                df = self.ta.compute_indicators(df)
                data_store[ticker] = df

        if not data_store:
            logger.error("No valid historical data retrieved.")
            return {}

        # 3. Synchronize chronological date index across assets
        all_dates = sorted(list(set(d for df in data_store.values() for d in df.index)))
        
        cash = initial_capital
        active_positions: list[Position] = []
        trade_history: list[dict] = []
        portfolio_equity_curve = []

        # Market-specific risk configuration (2% IN, 10% US due to micro-capital limits)
        risk_pct = 2.0 if market == "IN" else 10.0
        risk_mgr = RiskManager(
            capital=initial_capital,
            risk_per_trade_pct=risk_pct,
            max_positions=self.max_positions
        )

        logger.info(f"Running simulation from {all_dates[50].date()} to {all_dates[-1].date()}...")

        # 4. Bar-by-bar walk-forward simulation
        for i in range(50, len(all_dates)):
            current_date = all_dates[i]

            # --- Update Macro Regime Bar-by-Bar ---
            if not idx_df.empty and current_date in idx_df.index:
                idx_bar = idx_df.loc[current_date]
                if pd.notna(idx_bar.get('Close')) and pd.notna(idx_bar.get('SMA_50')):
                    is_bull = bool(idx_bar['Close'] > idx_bar['SMA_50'])
                    risk_mgr.set_market_regime(is_bull)
            
            # --- Portfolio Mark-to-Market ---
            current_equity = cash
            for pos in active_positions:
                df = data_store[pos.ticker]
                if current_date in df.index:
                    current_equity += pos.remaining_units * df.loc[current_date, 'Close']
                else:
                    current_equity += pos.remaining_units * pos.entry_price

            portfolio_equity_curve.append({
                "date": current_date,
                "equity": current_equity,
                "cash": cash,
                "open_positions": len(active_positions)
            })

            # Sync risk manager capital dynamically
            risk_mgr.capital = current_equity

            # --- Check Exits on Open Positions ---
            still_active = []
            for pos in active_positions:
                df = data_store[pos.ticker]
                if current_date not in df.index:
                    still_active.append(pos)
                    continue

                bar = df.loc[current_date]
                high = bar['High']
                low = bar['Low']

                # 1. Stop Loss Evaluation (bypassed if stop_loss == 0.0 for accumulation ETFs)
                if pos.stop_loss > 0.0 and low <= pos.stop_loss:
                    exit_price = pos.stop_loss
                    pnl = (exit_price - pos.entry_price) * pos.remaining_units
                    cash += pos.remaining_units * exit_price
                    pos.realized_pnl += pnl
                    pos.closed = True
                    pos.exit_date = current_date
                    pos.exit_reason = "SL (Breakeven)" if pos.tp1_hit else "SL"
                    
                    trade_history.append(self._record_trade(pos))
                    continue

                # 2. Take Profit 1 (Scale out 50% + Move SL to Entry for non-ETFs)
                if not pos.tp1_hit and high >= pos.tp1:
                    units_to_sell = pos.remaining_units // 2
                    if units_to_sell > 0:
                        pnl = (pos.tp1 - pos.entry_price) * units_to_sell
                        cash += units_to_sell * pos.tp1
                        pos.realized_pnl += pnl
                        pos.remaining_units -= units_to_sell
                        pos.tp1_hit = True
                        
                        # Only move SL to breakeven if the position actively uses a stop-loss
                        if pos.stop_loss > 0.0:
                            pos.stop_loss = pos.entry_price

                # 3. Take Profit 2 (Close remaining 50%)
                if pos.tp1_hit and high >= pos.tp2:
                    pnl = (pos.tp2 - pos.entry_price) * pos.remaining_units
                    cash += pos.remaining_units * pos.tp2
                    pos.realized_pnl += pnl
                    pos.remaining_units = 0
                    pos.closed = True
                    pos.exit_date = current_date
                    pos.exit_reason = "TP2 (Target Met)"
                    
                    trade_history.append(self._record_trade(pos))
                    continue

                still_active.append(pos)

            active_positions = still_active

            # --- Evaluate New Entry Signals ---
            if len(active_positions) < self.max_positions:
                for ticker, df in data_store.items():
                    if current_date not in df.index:
                        continue
                    
                    if any(pos.ticker == ticker for pos in active_positions):
                        continue

                    sub_df = df.loc[:current_date]
                    if len(sub_df) < 50:
                        continue

                    is_etf = any(kw in ticker.upper() for kw in ETF_KEYWORDS)
                    lev_factor = LEVERAGE_MAP.get(ticker, 1.0)

                    # Generate signal with production logic
                    signal_data = self.ta.generate_signal(sub_df, ticker=ticker, fundamentals={})

                    if signal_data['signal'] == 'BUY':
                        # 3. Calculate Risk Levels
                        risk_data = risk_mgr.calculate_levels(
                            current_price=signal_data['close'],
                            atr=signal_data['atr'],
                            signal=signal_data['signal'],
                            is_etf=signal_data.get('is_etf', False),
                            leverage_factor=lev_factor,
                            allow_fractional=(market == "US")  # <--- Add this flag
                        )
                        signal_data.update(risk_data)
                        
                        approved, _, _ = risk_mgr.apply_filters(signal_data)
                        units = risk_data['position_size_units']
                        cost = units * risk_data['entry_price']

                        if approved and units > 0 and cash >= cost:
                            cash -= cost
                            new_pos = Position(
                                ticker=ticker,
                                market=market,
                                entry_date=current_date,
                                entry_price=risk_data['entry_price'],
                                units=units,
                                stop_loss=risk_data['stop_loss'],
                                tp1=risk_data['take_profit_1'],
                                tp2=risk_data['take_profit_2'],
                                risk_per_share=risk_data['risk_per_share'],
                                is_etf=is_etf
                            )
                            active_positions.append(new_pos)
                            
                            if len(active_positions) >= self.max_positions:
                                break

        last_date = all_dates[-1]
        for pos in active_positions:
            df = data_store[pos.ticker]
            
            # Fetch the final available closing price
            if last_date in df.index:
                last_price = df.loc[last_date, 'Close']
            else:
                last_price = pos.entry_price
            
            # Calculate final unrealized PnL and add to any partially realized PnL (from TP1)
            pnl = (last_price - pos.entry_price) * pos.remaining_units
            pos.realized_pnl += pnl
            pos.remaining_units = 0
            pos.closed = True
            pos.exit_date = last_date
            pos.exit_reason = "Open Position (Mark-to-Market)"
            
            trade_history.append(self._record_trade(pos))
            
        active_positions.clear()

        return self._generate_report(initial_capital, portfolio_equity_curve, trade_history, market)

    def _record_trade(self, pos: Position) -> dict:
        total_invested = pos.total_units * pos.entry_price
        return {
            "ticker": pos.ticker,
            "entry_date": pos.entry_date.strftime("%Y-%m-%d"),
            "exit_date": pos.exit_date.strftime("%Y-%m-%d"),
            "entry_price": pos.entry_price,
            "units": pos.total_units,
            "pnl": round(pos.realized_pnl, 2),
            "return_pct": round((pos.realized_pnl / total_invested) * 100, 2) if total_invested > 0 else 0,
            "reason": pos.exit_reason
        }

    def _generate_report(self, initial_capital: float, equity_curve: list, trades: list, market: str) -> dict:
        if not equity_curve:
            return {}

        eq_df = pd.DataFrame(equity_curve).set_index("date")
        final_equity = eq_df['equity'].iloc[-1]
        net_profit = final_equity - initial_capital
        total_return_pct = (net_profit / initial_capital) * 100

        eq_df['peak'] = eq_df['equity'].cummax()
        eq_df['drawdown'] = (eq_df['equity'] - eq_df['peak']) / eq_df['peak']
        max_drawdown_pct = abs(eq_df['drawdown'].min()) * 100

        total_trades = len(trades)
        wins = [t for t in trades if t['pnl'] > 0]
        losses = [t for t in trades if t['pnl'] <= 0]
        win_rate = (len(wins) / total_trades * 100) if total_trades > 0 else 0

        gross_profit = sum(t['pnl'] for t in wins)
        gross_loss = abs(sum(t['pnl'] for t in losses))
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else np.inf

        currency = "₹" if market == "IN" else "$"

        print("\n" + "=" * 60)
        print(f"       STRATEGY BACKTEST RESULTS ({market} MARKET)")
        print("=" * 60)
        print(f"Initial Capital   : {currency}{initial_capital:,.2f}")
        print(f"Final Capital     : {currency}{final_equity:,.2f}")
        print(f"Net Profit / Loss : {currency}{net_profit:,.2f} ({total_return_pct:+.2f}%)")
        print(f"Max Drawdown      : {max_drawdown_pct:.2f}%")
        print("-" * 60)
        print(f"Total Closed Trades : {total_trades}")
        print(f"Win Rate            : {win_rate:.2f}% ({len(wins)}W / {len(losses)}L)")
        print(f"Profit Factor       : {profit_factor}")
        print("=" * 60)

        if trades:
            print("\nRecent Sample Trades:")
            print(f"{'Ticker':<14} {'Entry':<12} {'Exit':<12} {'PnL ('+currency+')':<12} {'Return %':<10} Reason")
            print("-" * 70)
            for t in trades[-8:]:
                print(f"{t['ticker']:<14} {t['entry_date']:<12} {t['exit_date']:<12} {t['pnl']:<12.2f} {t['return_pct']:<10.2f} {t['reason']}")
            print("-" * 70 + "\n")

        return {
            "initial_capital": initial_capital,
            "final_equity": final_equity,
            "net_profit": net_profit,
            "total_return_pct": total_return_pct,
            "max_drawdown_pct": max_drawdown_pct,
            "total_trades": total_trades,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "trade_log": trades
        }


if __name__ == "__main__":
    engine = BacktestEngine(lookback_days=730)
    
    # Run Indian market backtest
    engine.run(market="IN")
    
    # Run US market backtest
    engine.run(market="US")