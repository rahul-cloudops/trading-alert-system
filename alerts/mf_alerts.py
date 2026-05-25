"""
mf_alerts.py
------------
Formats and sends Mutual Fund dip alerts via Telegram.
Reuses the same bot token / chat ID already in your .env.
"""

import asyncio
import os
import logging
import telegram
from datetime import datetime

logger = logging.getLogger(__name__)

# Signal emoji + labels
SIGNAL_META = {
    "STRONG_BUY_DIP": ("🟢", "STRONG BUY DIP"),
    "BUY_DIP":        ("🟡", "BUY DIP"),
    "WATCH":          ("🔵", "WATCH"),
    "HOLD":           ("⚪", "HOLD — no dip yet"),
}

VIX_EMOJI = {
    "LOW":      "😴",
    "MODERATE": "😐",
    "HIGH":     "😟",
    "EXTREME":  "🚨",
}


class MFAlerter:
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id   = os.getenv("TELEGRAM_CHAT_ID")

    # ------------------------------------------------------------------ #
    #  Individual fund alert                                               #
    # ------------------------------------------------------------------ #

    def format_fund_alert(self, analysis: dict, regime: dict) -> str:
        signal   = analysis.get("signal", "HOLD")
        emoji, label = SIGNAL_META.get(signal, ("⚪", signal))
        score    = analysis.get("score", 0)
        vix      = regime.get("india_vix", "N/A")
        vix_sig  = regime.get("vix_signal", "")
        vix_e    = VIX_EMOJI.get(vix_sig, "")
        bull     = regime.get("bull_market")
        market_phase = (
            "Bull market (Nifty > 200-DMA)"
            if bull
            else "Bear phase (Nifty < 200-DMA)"
            if bull is False
            else "Unknown"
        )

        nav      = analysis.get("current_nav", "N/A")
        high     = analysis.get("52w_high", "N/A")
        low      = analysis.get("52w_low", "N/A")
        drawdown = analysis.get("drawdown_pct", "N/A")
        thresh   = analysis.get("threshold", "N/A")
        c1m      = analysis.get("change_1m_pct", "N/A")
        c3m      = analysis.get("change_3m_pct", "N/A")
        c1y      = analysis.get("change_1y_pct", "N/A")
        nav_date = analysis.get("last_nav_date", "")

        reasons_text = "\n".join(
            f"  {r}" for r in analysis.get("reasons", [])[:6]
        )

        lumpsum_action = (
            "*ACTION: Deploy lump sum now via IndMoney / Groww*"
            if signal in ("STRONG_BUY_DIP", "BUY_DIP")
            else "_No action needed. Continue monitoring._"
        )

        msg = f"""
{emoji} *MUTUAL FUND DIP ALERT — {label}*
━━━━━━━━━━━━━━━━━━━━━━━━━━
*Fund:* {analysis.get('fund_name', 'N/A')}
*Category:* {analysis.get('category', 'N/A')}
*Date:* {datetime.now().strftime('%d %b %Y, %H:%M IST')}

*NAV SNAPSHOT* (as of {nav_date})
  Current NAV : {nav}
  52W High    : {high}
  52W Low     : {low}
  Drawdown    : {drawdown}% from peak (trigger: {thresh}%)

*RETURNS*
  1 Month : {c1m}%
  3 Months: {c3m}%
  1 Year  : {c1y}%

*MARKET CONDITIONS*
  Nifty 50  : {market_phase}
  India VIX : {vix_e} {vix} ({vix_sig})
  Nifty from 52w high: {regime.get('nifty_drawdown_pct', 'N/A')}%

*DIP SCORE: {score}/100*
{reasons_text}

{lumpsum_action}

_AI advisory only. Not SEBI advice. Invest at your own risk._
""".strip()
        return msg

    # ------------------------------------------------------------------ #
    #  Daily summary (all funds at once)                                   #
    # ------------------------------------------------------------------ #

    def format_daily_summary(
        self,
        all_analyses: list[dict],
        regime: dict,
    ) -> str:
        vix     = regime.get("india_vix", "N/A")
        vix_sig = regime.get("vix_signal", "")
        bull    = regime.get("bull_market")
        nifty_dd = regime.get("nifty_drawdown_pct", "N/A")

        strong  = [a for a in all_analyses if a["signal"] == "STRONG_BUY_DIP"]
        buy     = [a for a in all_analyses if a["signal"] == "BUY_DIP"]
        watch   = [a for a in all_analyses if a["signal"] == "WATCH"]
        hold    = [a for a in all_analyses if a["signal"] == "HOLD"]

        def fund_line(a):
            e, _ = SIGNAL_META.get(a["signal"], ("", ""))
            return (
                f"  {e} {a['fund_name'][:40]}\n"
                f"     NAV: {a.get('current_nav','?')} | "
                f"Dip: {a.get('drawdown_pct','?')}% | "
                f"Score: {a.get('score',0)}/100"
            )

        sections = []
        if strong:
            sections.append("*STRONG BUY DIP opportunities:*\n" +
                            "\n".join(fund_line(a) for a in strong))
        if buy:
            sections.append("*BUY DIP opportunities:*\n" +
                            "\n".join(fund_line(a) for a in buy))
        if watch:
            sections.append("*Watch list (approaching dip):*\n" +
                            "\n".join(fund_line(a) for a in watch))
        if hold:
            sections.append("*No action needed:*\n" +
                            "\n".join(fund_line(a) for a in hold))

        market_line = (
            "Bull market" if bull else "Bear phase" if bull is False else "N/A"
        )

        msg = f"""
*MUTUAL FUND DAILY DIP REPORT*
{datetime.now().strftime('%d %b %Y, %H:%M IST')}
━━━━━━━━━━━━━━━━━━━━━━━━━━
*Market Pulse*
  Nifty 50  : {market_line} | {nifty_dd}% from 52w high
  India VIX : {VIX_EMOJI.get(vix_sig,'')} {vix} — {vix_sig}

{chr(10).join(sections)}

_Lump sum into IndMoney only when score >= 50 AND you have spare capital._
_SEBI disclaimer: This is AI-generated advisory, not registered investment advice._
""".strip()
        return msg

    # ------------------------------------------------------------------ #
    #  Send methods                                                        #
    # ------------------------------------------------------------------ #

    async def _send_async(self, message: str):
        bot = telegram.Bot(token=self.bot_token)
        async with bot:
            # Telegram has a 4096-char limit per message
            if len(message) <= 4096:
                await bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                    parse_mode="Markdown",
                )
            else:
                # Split and send in parts
                for i in range(0, len(message), 4000):
                    chunk = message[i : i + 4000]
                    await bot.send_message(
                        chat_id=self.chat_id,
                        text=chunk,
                        parse_mode="Markdown",
                    )

    def send(self, message: str):
        asyncio.run(self._send_async(message))
