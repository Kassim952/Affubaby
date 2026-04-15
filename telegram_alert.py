import requests
import logging
from .config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger("trading_bot.telegram")


def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram credentials not set, skipping alert")
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown",
        }
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            logger.info("Telegram alert sent")
            return True
        else:
            logger.error(f"Telegram error: {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")
        return False


def format_trade_alert(signal_type, symbol, entry, sl, tp, strategy, confidence):
    return (
        f"🔔 *TRADE SIGNAL*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📊 Signal: *{signal_type.upper()}*\n"
        f"💱 Pair: `{symbol}`\n"
        f"📍 Entry: `{entry}`\n"
        f"🛑 SL: `{sl}`\n"
        f"🎯 TP: `{tp}`\n"
        f"🧠 Strategy: _{strategy}_\n"
        f"📈 Confidence: *{confidence}%*\n"
        f"━━━━━━━━━━━━━━━"
    )


def format_trade_close_alert(symbol, direction, profit, reason):
    emoji = "✅" if profit >= 0 else "❌"
    return (
        f"{emoji} *TRADE CLOSED*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💱 Pair: `{symbol}`\n"
        f"📊 Direction: *{direction.upper()}*\n"
        f"💰 Profit: `{profit}`\n"
        f"📝 Reason: _{reason}_\n"
        f"━━━━━━━━━━━━━━━"
    )


def format_daily_summary(total_trades, wins, losses, total_profit):
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    return (
        f"📋 *DAILY SUMMARY*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📊 Total Trades: {total_trades}\n"
        f"✅ Wins: {wins}\n"
        f"❌ Losses: {losses}\n"
        f"📈 Win Rate: {win_rate:.1f}%\n"
        f"💰 Total P/L: `{total_profit}`\n"
        f"━━━━━━━━━━━━━━━"
    )
  
