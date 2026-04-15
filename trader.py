import asyncio
import logging
import numpy as np
from metaapi_cloud_sdk import MetaApi
from config import (
    META_API_TOKEN, META_API_ACCOUNT_ID, SYMBOLS, LOT_SIZE,
    SYMBOL_CONFIG, ENTRY_TIMEFRAME, TREND_TIMEFRAME,
    BREAKEVEN_TRIGGER_RR, TRAILING_STOP_STEP_RR, BROKER_TO_BASE
)
from .strategies import evaluate_all_strategies
from .risk_manager import RiskManager
from .market_data import get_candles, get_current_price
from .telegram_alert import (
    send_telegram, format_trade_alert,
    format_trade_close_alert, format_daily_summary
)

logger = logging.getLogger("trading_bot.trader")


class ForexTrader:
    def __init__(self):
        self.api = None
        self.account = None
        self.connection = None
        self.risk_manager = RiskManager()
        self.current_trade = None
        self.current_symbol = None

    async def connect(self):
        logger.info("Connecting to MetaAPI for trade execution...")
        self.api = MetaApi(META_API_TOKEN)
        self.account = await self.api.metatrader_account_api.get_account(META_API_ACCOUNT_ID)

        if self.account.state not in ("DEPLOYED", "DEPLOYING"):
            logger.info("Deploying account...")
            await self.account.deploy()

        logger.info("Waiting for API server connection...")
        await self.account.wait_connected()

        self.connection = self.account.get_rpc_connection()
        await self.connection.connect()
        await self.connection.wait_synchronized()
        logger.info("Connected to MetaAPI successfully")
        logger.info("Market analysis powered by Yahoo Finance")
        send_telegram(
            "🤖 *Trading Bot Connected*\n"
            "Trade execution: MetaAPI (MT5)\n"
            "Market analysis: Yahoo Finance\n"
            "Monitoring: XAUUSD & EURUSD"
        )

    async def disconnect(self):
        if self.connection:
            await self.connection.close()
        logger.info("Disconnected from MetaAPI")

    async def check_open_positions(self):
        try:
            positions = await self.connection.get_positions()
            broker_symbols = {cfg["broker_symbol"] for cfg in SYMBOL_CONFIG.values()}
            for pos in positions:
                broker_sym = pos.get("symbol")
                if broker_sym in broker_symbols:
                    base_sym = BROKER_TO_BASE.get(broker_sym, broker_sym)
                    self.risk_manager.has_open_position = True
                    self.current_trade = pos
                    self.current_symbol = base_sym
                    return pos
            self.risk_manager.has_open_position = False
            self.current_trade = None
            self.current_symbol = None
            return None
        except Exception as e:
            logger.error(f"Error checking positions: {e}")
            return None

    async def manage_open_trade(self):
        if not self.current_trade:
            return

        try:
            broker_symbol = self.current_trade["symbol"]
            symbol = self.current_symbol or BROKER_TO_BASE.get(broker_symbol, broker_symbol)
            config = SYMBOL_CONFIG[symbol]
            point = config["point_value"]
            position_id = self.current_trade["id"]
            open_price = self.current_trade["openPrice"]
            current_sl = self.current_trade.get("stopLoss", 0)
            tp = self.current_trade.get("takeProfit", 0)
            trade_type = self.current_trade["type"]

            current_price = await asyncio.get_event_loop().run_in_executor(
                None, get_current_price, symbol
            )
            if not current_price:
                price_info = await self.connection.get_symbol_price(broker_symbol)
                if price_info:
                    current_price = price_info["bid"] if trade_type == "POSITION_TYPE_BUY" else price_info["ask"]
                else:
                    return

            if trade_type == "POSITION_TYPE_BUY":
                profit_points = (current_price - open_price) / point
            else:
                profit_points = (open_price - current_price) / point

            sl_distance = abs(open_price - current_sl) / point if current_sl else config["sl_max"]
            breakeven_target = sl_distance * BREAKEVEN_TRIGGER_RR

            if profit_points >= breakeven_target and current_sl != open_price:
                new_sl = open_price + (2 * point if trade_type == "POSITION_TYPE_BUY" else -2 * point)
                try:
                    await self.connection.modify_position(position_id, stop_loss=new_sl, take_profit=tp)
                    logger.info(f"Moved SL to breakeven for {symbol} (profit={profit_points:.1f} pts)")
                except Exception as e:
                    logger.error(f"Error moving to breakeven: {e}")

            trailing_target = sl_distance * (BREAKEVEN_TRIGGER_RR + TRAILING_STOP_STEP_RR)
            if profit_points >= trailing_target:
                trail_distance = config["sl_min"] * point
                if trade_type == "POSITION_TYPE_BUY":
                    new_sl = current_price - trail_distance
                    if new_sl > current_sl:
                        try:
                            await self.connection.modify_position(position_id, stop_loss=new_sl, take_profit=tp)
                            logger.info(f"Trailing stop updated for {symbol}: {new_sl:.5f}")
                        except Exception as e:
                            logger.error(f"Error trailing stop: {e}")
                else:
                    new_sl = current_price + trail_distance
                    if current_sl == 0 or new_sl < current_sl:
                        try:
                            await self.connection.modify_position(position_id, stop_loss=new_sl, take_profit=tp)
                            logger.info(f"Trailing stop updated for {symbol}: {new_sl:.5f}")
                        except Exception as e:
                            logger.error(f"Error trailing stop: {e}")

            closes_1m, volumes_1m, _ = await asyncio.get_event_loop().run_in_executor(
                None, get_candles, symbol, ENTRY_TIMEFRAME, 50
            )
            closes_5m, _, _ = await asyncio.get_event_loop().run_in_executor(
                None, get_candles, symbol, TREND_TIMEFRAME, 50
            )

            if closes_1m is not None and closes_5m is not None:
                signal, trend = evaluate_all_strategies(closes_1m, volumes_1m, closes_5m, config)
                if signal:
                    opposite = (trade_type == "POSITION_TYPE_BUY" and signal.direction == "sell") or \
                               (trade_type == "POSITION_TYPE_SELL" and signal.direction == "buy")
                    if opposite:
                        logger.info(f"Opposite signal detected ({signal.strategy}), closing {symbol}")
                        await self.close_trade(position_id, symbol, f"Opposite signal: {signal.strategy}")

        except Exception as e:
            logger.error(f"Error managing trade: {e}")

    async def close_trade(self, position_id, symbol, reason):
        try:
            await self.connection.close_position(position_id)
            profit = self.current_trade.get("profit", 0)
            trade_type = self.current_trade["type"]
            broker_symbol = self.current_trade.get("symbol", symbol)
            self.risk_manager.record_trade_close(profit)
            direction = "BUY" if trade_type == "POSITION_TYPE_BUY" else "SELL"
            alert = format_trade_close_alert(broker_symbol, direction, profit, reason)
            send_telegram(alert)
            logger.info(f"Trade closed: {broker_symbol} {direction} profit={profit} reason={reason}")
            self.current_trade = None
            self.current_symbol = None
        except Exception as e:
            logger.error(f"Error closing trade: {e}")

    async def scan_and_trade(self):
        if not self.risk_manager.can_trade():
            return

        best_signal = None
        best_symbol = None

        for symbol in SYMBOLS:
            config = SYMBOL_CONFIG[symbol]

            logger.info(f"Analyzing {symbol} via Yahoo Finance...")

            closes_1m, volumes_1m, _ = await asyncio.get_event_loop().run_in_executor(
                None, get_candles, symbol, ENTRY_TIMEFRAME, 100
            )
            closes_5m, _, _ = await asyncio.get_event_loop().run_in_executor(
                None, get_candles, symbol, TREND_TIMEFRAME, 50
            )

            if closes_1m is None or closes_5m is None:
                logger.warning(f"Could not get candle data for {symbol}, skipping")
                continue

            logger.info(f"{symbol}: {len(closes_1m)} x 1m candles, {len(closes_5m)} x 5m candles | Last close: {closes_1m[-1]:.5f}")

            signal, trend = evaluate_all_strategies(closes_1m, volumes_1m, closes_5m, config)

            logger.info(f"{symbol}: Trend={trend}, Signal={signal}")

            if signal:
                if best_signal is None or signal.confidence > best_signal.confidence:
                    best_signal = signal
                    best_symbol = symbol

        if best_signal and best_symbol:
            await self.execute_trade(best_symbol, best_signal)
        else:
            logger.info("No high-confidence signal found this cycle")

    async def execute_trade(self, symbol, signal):
        try:
            config = SYMBOL_CONFIG[symbol]
            broker_symbol = config["broker_symbol"]
            point = config["point_value"]

            price_info = await self.connection.get_symbol_price(broker_symbol)
            if not price_info:
                logger.error(f"Could not get live price for {broker_symbol} from MetaAPI")
                return

            if signal.direction == "buy":
                entry_price = price_info["ask"]
                sl = round(entry_price - signal.sl_points * point, config["digits"])
                tp = round(entry_price + signal.tp_points * point, config["digits"])
            else:
                entry_price = price_info["bid"]
                sl = round(entry_price + signal.sl_points * point, config["digits"])
                tp = round(entry_price - signal.tp_points * point, config["digits"])

            logger.info(
                f"Executing {signal.direction.upper()} {broker_symbol} | "
                f"Entry={entry_price} SL={sl} TP={tp} | "
                f"Strategy={signal.strategy} Confidence={signal.confidence}%"
            )

            if signal.direction == "buy":
                result = await self.connection.create_market_buy_order(
                    broker_symbol, LOT_SIZE, sl, tp,
                    options={"comment": f"Bot:{signal.strategy[:20]}"}
                )
            else:
                result = await self.connection.create_market_sell_order(
                    broker_symbol, LOT_SIZE, sl, tp,
                    options={"comment": f"Bot:{signal.strategy[:20]}"}
                )

            if result and result.get("stringCode") == "TRADE_RETCODE_DONE":
                self.risk_manager.record_trade_open()
                alert = format_trade_alert(
                    signal.direction, broker_symbol, entry_price, sl, tp,
                    signal.strategy, signal.confidence
                )
                send_telegram(alert)
                logger.info(f"Trade placed successfully on {broker_symbol}")
            else:
                logger.error(f"Trade execution failed for {broker_symbol}: {result}")
                send_telegram(f"⚠️ Trade failed for {broker_symbol}: {result}")

        except Exception as e:
            logger.error(f"Error executing trade for {symbol}: {e}")
            send_telegram(f"⚠️ Trade error: {e}")

    def get_daily_summary(self):
        summary = self.risk_manager.get_summary()
        msg = format_daily_summary(
            summary["daily_trades"], summary["wins"],
            summary["losses"], summary["total_profit"]
        )
        send_telegram(msg)
        return summary
