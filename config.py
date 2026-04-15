import os

META_API_TOKEN = os.environ.get("META_API_TOKEN", "")
META_API_ACCOUNT_ID = os.environ.get("META_API_ACCOUNT_ID", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

SYMBOLS = ["XAUUSD", "EURUSD"]

LOT_SIZE = 0.01

SYMBOL_CONFIG = {
    "XAUUSD": {
        "sl_min": 30,
        "sl_max": 80,
        "tp_min": 50,
        "tp_max": 120,
        "point_value": 0.01,
        "digits": 2,
    },
    "EURUSD": {
        "sl_min": 5,
        "sl_max": 10,
        "tp_min": 8,
        "tp_max": 15,
        "point_value": 0.0001,
        "digits": 5,
    },
}

RSI_PERIOD = 14
BB_PERIOD = 20
BB_STD = 2
EMA_FAST = 9
EMA_SLOW = 21
VWAP_PERIOD = 20

ENTRY_TIMEFRAME = "1m"
TREND_TIMEFRAME = "5m"

MAX_DAILY_TRADES = 10
MAX_CONSECUTIVE_LOSSES = 3
BREAKEVEN_TRIGGER_RR = 0.5
TRAILING_STOP_STEP_RR = 0.3

RR_RATIO = 1.5

NEWS_AVOID_HOURS = [
    (13, 30), (14, 0), (14, 30),
    (8, 30), (10, 0),
    (15, 0), (15, 30),
]
NEWS_WINDOW_MINUTES = 15

BOT_LOOP_INTERVAL = 10
