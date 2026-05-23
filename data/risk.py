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