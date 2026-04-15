import asyncio
import logging
import signal
import sys
from datetime import datetime, timezone
from trader import ForexTrader
from config import BOT_LOOP_INTERVAL
from telegram_alert import send_telegram

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger("trading_bot")

for noisy in ["socketio", "engineio", "httpx", "websockets", "urllib3"]:
    logging.getLogger(noisy).setLevel(logging.WARNING)


class TradingBot:
    def __init__(self):
        self.trader = ForexTrader()
        self.running = False
        self.last_summary_hour = -1

    async def start(self):
        logger.info("=" * 50)
        logger.info("  FOREX SCALPING BOT STARTING")
        logger.info("  Symbols: XAUUSD, EURUSD")
        logger.info("  Strategy: Multi-strategy scalping")
        logger.info("=" * 50)

        try:
            await self.trader.connect()
            self.running = True
            await self.run_loop()
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        except Exception as e:
            logger.error(f"Bot error: {e}")
            send_telegram(f"🚨 *Bot Error*: {e}")
        finally:
            await self.shutdown()

    async def run_loop(self):
        logger.info("Bot loop started, scanning every %d seconds", BOT_LOOP_INTERVAL)

        while self.running:
            try:
                now = datetime.now(timezone.utc)

                if now.hour == 0 and self.last_summary_hour != 0:
                    self.trader.get_daily_summary()
                    self.last_summary_hour = 0

                if now.hour != 0:
                    self.last_summary_hour = now.hour

                position = await self.trader.check_open_positions()

                if position:
                    await self.trader.manage_open_trade()
                else:
                    await self.trader.scan_and_trade()

                await asyncio.sleep(BOT_LOOP_INTERVAL)

            except Exception as e:
                logger.error(f"Loop error: {e}")
                send_telegram(f"⚠️ Loop error: {e}")
                await asyncio.sleep(30)

    async def shutdown(self):
        logger.info("Shutting down bot...")
        self.running = False
        summary = self.trader.get_daily_summary()
        logger.info(f"Final summary: {summary}")
        await self.trader.disconnect()
        send_telegram("🛑 *Trading Bot Stopped*")
        logger.info("Bot shutdown complete")


def run():
    bot = TradingBot()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def handle_signal(sig, frame):
        logger.info(f"Received signal {sig}, stopping...")
        bot.running = False

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        loop.run_until_complete(bot.start())
    except KeyboardInterrupt:
        bot.running = False
        loop.run_until_complete(bot.shutdown())
    finally:
        loop.close()
