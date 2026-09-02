class RiskManager:
    def __init__(self, capital: float, risk_per_trade_pct: float = 2.0, max_positions: int = 5):
        self.capital = capital
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_positions = max_positions
        self.is_bull_market = True  # Defaults to True until checked

    def set_market_regime(self, is_bull_market: bool):
        """Update the macro market regime before scanning."""
        self.is_bull_market = is_bull_market

    def calculate_levels(self, current_price: float, atr: float, signal: str) -> dict:
        """
        ATR-based dynamic Stop Loss and Take Profit.
        """
        atr_multiplier_sl = 1.5   
        atr_multiplier_tp1 = 2.0  
        atr_multiplier_tp2 = 3.5  

        if signal == "BUY":
            stop_loss    = round(current_price - (atr * atr_multiplier_sl), 2)
            take_profit1 = round(current_price + (atr * atr_multiplier_tp1), 2)
            take_profit2 = round(current_price + (atr * atr_multiplier_tp2), 2)
        else:  
            stop_loss    = round(current_price + (atr * atr_multiplier_sl), 2)
            take_profit1 = round(current_price - (atr * atr_multiplier_tp1), 2)
            take_profit2 = round(current_price - (atr * atr_multiplier_tp2), 2)

        risk_per_share = abs(current_price - stop_loss)
        
        # Dynamic Risk Allocation: Cut risk in half during bear markets
        actual_risk_pct = self.risk_per_trade_pct if self.is_bull_market else (self.risk_per_trade_pct / 2)
        position_size   = self.calculate_position_size(risk_per_share, actual_risk_pct)
        
        risk_reward = round(abs(take_profit2 - current_price) / risk_per_share, 2) if risk_per_share > 0 else 0

        return {
            "entry_price": current_price,
            "stop_loss": stop_loss,
            "take_profit_1": take_profit1,  
            "take_profit_2": take_profit2,  
            "risk_per_share": round(risk_per_share, 2),
            "position_size_units": position_size,
            "capital_at_risk": round(risk_per_share * position_size, 2),
            "risk_reward_ratio": risk_reward,
            "sl_percent": round((risk_per_share / current_price) * 100, 2) if current_price > 0 else 0,
        }

    def calculate_position_size(self, risk_per_share: float, actual_risk_pct: float) -> int:
        """Position sizing based on dynamically adjusted % capital risk."""
        if risk_per_share <= 0:
            return 0
        max_loss = self.capital * (actual_risk_pct / 100)
        units = int(max_loss / risk_per_share)
        max_single_position = int(self.capital * 0.20 / risk_per_share)
        return min(units, max_single_position)

    def apply_filters(self, signal_data: dict) -> tuple[bool, str, str]:
        """Returns (approved, reason, downgrade_signal)"""
        score  = signal_data.get("score", 0)
        rr     = signal_data.get("risk_reward_ratio", 0)
        adx    = signal_data.get("adx", 0)
        is_etf = signal_data.get("is_etf", False)

        if score < 55 and signal_data.get("signal") == "BUY":
            return False, f"Score too low ({score})", None

        if rr < 1.5:
            return False, f"Risk/Reward too low ({rr})", None

        if signal_data.get("signal") == "BUY":
            # 1. Macro Regime Check (Protect capital in downtrends)
            if not self.is_bull_market and score < 65:
                return False, f"Bear market regime & borderline score ({score}) — downgraded to WATCH", "WATCH"

            # 2. Asset-Specific Trend Strength
            if adx is not None:
                if not is_etf and adx < 20:
                    return False, f"Weak equity trend (ADX {adx:.2f}) — downgraded to WATCH", "WATCH"
                elif is_etf and adx < 15:
                    return False, f"Flat ETF trend (ADX {adx:.2f}) — downgraded to WATCH", "WATCH"

        return True, "Passed all filters", None