import logging
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("trading_bot.market_data")

YAHOO_SYMBOLS = {
    "XAUUSD": "GC=F",
    "EURUSD": "EURUSD=X",
}

YAHOO_INTERVALS = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "1h": "1h",
}

LOOKBACK_PERIODS = {
    "1m": 1,
    "5m": 5,
    "15m": 7,
    "1h": 30,
}


def get_candles(symbol, timeframe="1m", count=100):
    yahoo_symbol = YAHOO_SYMBOLS.get(symbol)
    if not yahoo_symbol:
        logger.error(f"No Yahoo Finance symbol mapped for {symbol}")
        return None, None, None

    interval = YAHOO_INTERVALS.get(timeframe, "1m")
    days_back = LOOKBACK_PERIODS.get(timeframe, 1)

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days_back)

    try:
        ticker = yf.Ticker(yahoo_symbol)
        df = ticker.history(start=start, end=end, interval=interval, auto_adjust=True)

        if df is None or df.empty:
            logger.warning(f"No data returned from Yahoo Finance for {symbol} ({yahoo_symbol}) {timeframe}")
            return None, None, None

        df = df.dropna(subset=["Close"])
        df = df.tail(count)

        closes = df["Close"].to_numpy(dtype=float)
        volumes = df["Volume"].to_numpy(dtype=float)
        volumes = np.where(volumes == 0, 1, volumes)

        logger.debug(f"Fetched {len(closes)} candles for {symbol} ({yahoo_symbol}) {timeframe}")
        return closes, volumes, df

    except Exception as e:
        logger.error(f"Yahoo Finance error for {symbol} {timeframe}: {e}")
        return None, None, None


def get_current_price(symbol):
    yahoo_symbol = YAHOO_SYMBOLS.get(symbol)
    if not yahoo_symbol:
        return None
    try:
        ticker = yf.Ticker(yahoo_symbol)
        info = ticker.fast_info
        price = info.last_price
        if price and price > 0:
            return price
        df = ticker.history(period="1d", interval="1m", auto_adjust=True)
        if df is not None and not df.empty:
            return float(df["Close"].iloc[-1])
        return None
    except Exception as e:
        logger.error(f"Error getting current price for {symbol}: {e}")
        return None
