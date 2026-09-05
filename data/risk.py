class RiskManager:
    def __init__(self, capital: float, risk_per_trade_pct: float = 2.0, max_positions: int = 5):
        self.capital = capital
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_positions = max_positions
        self.is_bull_market = True

    def set_market_regime(self, is_bull_market: bool):
        """Update the macro market regime before scanning."""
        self.is_bull_market = is_bull_market

    def calculate_levels(self, current_price: float, atr: float, signal: str, is_etf: bool = False, leverage_factor: float = 1.0, allow_fractional: bool = False) -> dict:
        """ATR-based dynamic levels with ETF override and leverage scaling."""
        
        atr_multiplier_sl = 1.5 * leverage_factor
        atr_multiplier_tp1 = 2.0 * leverage_factor
        atr_multiplier_tp2 = 3.5 * leverage_factor

        if signal == "BUY":
            tech_sl = current_price - (atr * atr_multiplier_sl)
            take_profit1 = current_price + (atr * atr_multiplier_tp1)
            take_profit2 = current_price + (atr * atr_multiplier_tp2)
        else:  
            tech_sl = current_price + (atr * atr_multiplier_sl)
            take_profit1 = current_price - (atr * atr_multiplier_tp1)
            take_profit2 = current_price - (atr * atr_multiplier_tp2)

        risk_per_share = abs(current_price - tech_sl)
        actual_risk_pct = self.risk_per_trade_pct if self.is_bull_market else (self.risk_per_trade_pct / 2)
        
        # Pass the fractional flag to the sizing calculator
        position_size = self.calculate_position_size(risk_per_share, current_price, actual_risk_pct, allow_fractional)
        
        risk_reward = round(abs(take_profit2 - current_price) / risk_per_share, 2) if risk_per_share > 0 else 0

        if is_etf and leverage_factor == 1.0:
            final_sl = 0.0  
            sl_percent = 0.0
        else:
            final_sl = round(tech_sl, 2)
            sl_percent = round((risk_per_share / current_price) * 100, 2) if current_price > 0 else 0

        return {
            "entry_price": round(current_price, 2),
            "stop_loss": final_sl,
            "take_profit_1": round(take_profit1, 2),  
            "take_profit_2": round(take_profit2, 2),  
            "risk_per_share": round(risk_per_share, 2),
            "position_size_units": position_size,
            "capital_at_risk": round(risk_per_share * position_size, 2),
            "risk_reward_ratio": risk_reward,
            "sl_percent": sl_percent,
        }

    def calculate_position_size(self, risk_per_share: float, current_price: float, actual_risk_pct: float, allow_fractional: bool = False) -> float:
        """Position sizing based on dynamically adjusted % capital risk and 20% portfolio limits."""
        if risk_per_share <= 0 or current_price <= 0:
            return 0.0
            
        max_loss = self.capital * (actual_risk_pct / 100)
        units_by_risk = max_loss / risk_per_share
        
        max_position_value = self.capital * 0.20
        max_units_by_value = max_position_value / current_price
        
        raw_units = min(units_by_risk, max_units_by_value)
        
        # Return 4 decimal places for US stocks, or whole integers for Indian stocks
        if allow_fractional:
            return round(raw_units, 4)
        else:
            return float(int(raw_units))

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