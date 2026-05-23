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