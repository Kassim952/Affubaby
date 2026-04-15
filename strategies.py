import numpy as np
from .indicators import (
    calc_rsi, calc_bollinger_bands, calc_ema, calc_vwap,
    detect_rsi_divergence, is_consolidating, detect_breakout
)
from .config import RSI_PERIOD, BB_PERIOD, BB_STD, EMA_FAST, EMA_SLOW, VWAP_PERIOD


class Signal:
    def __init__(self, direction, strategy, confidence, sl_points, tp_points):
        self.direction = direction
        self.strategy = strategy
        self.confidence = confidence
        self.sl_points = sl_points
        self.tp_points = tp_points

    def __repr__(self):
        return f"Signal({self.direction}, {self.strategy}, conf={self.confidence})"


def get_trend(closes_5m):
    if len(closes_5m) < EMA_SLOW + 1:
        return "sideways"
    ema_fast = calc_ema(closes_5m, EMA_FAST)
    ema_slow = calc_ema(closes_5m, EMA_SLOW)

    if ema_fast[-1] == 0 or ema_slow[-1] == 0:
        return "sideways"

    diff = abs(ema_fast[-1] - ema_slow[-1]) / closes_5m[-1]
    if diff < 0.0001:
        return "sideways"

    if ema_fast[-1] > ema_slow[-1] and ema_fast[-2] > ema_slow[-2]:
        return "bullish"
    elif ema_fast[-1] < ema_slow[-1] and ema_fast[-2] < ema_slow[-2]:
        return "bearish"
    return "sideways"


def strategy_rsi_divergence_bb(closes_1m, volumes_1m, symbol_config):
    rsi = calc_rsi(closes_1m, RSI_PERIOD)
    upper, middle, lower = calc_bollinger_bands(closes_1m, BB_PERIOD, BB_STD)

    if len(rsi) < 10 or len(upper) < 10:
        return None

    divergence = detect_rsi_divergence(closes_1m, rsi)
    current_price = closes_1m[-1]
    prev_price = closes_1m[-2]

    if divergence == "bullish" and current_price <= lower[-1] and prev_price < current_price:
        sl = symbol_config["sl_max"]
        tp = int(sl * 1.5)
        tp = min(tp, symbol_config["tp_max"])
        return Signal("buy", "RSI Divergence + BB", 85, sl, tp)

    if divergence == "bearish" and current_price >= upper[-1] and prev_price > current_price:
        sl = symbol_config["sl_max"]
        tp = int(sl * 1.5)
        tp = min(tp, symbol_config["tp_max"])
        return Signal("sell", "RSI Divergence + BB", 85, sl, tp)

    return None


def strategy_rsi_vwap(closes_1m, volumes_1m, symbol_config):
    rsi = calc_rsi(closes_1m, RSI_PERIOD)
    vwap = calc_vwap(closes_1m, volumes_1m, VWAP_PERIOD)

    if len(rsi) < 5 or len(vwap) < 5 or vwap[-1] == 0:
        return None

    current_price = closes_1m[-1]
    prev_price = closes_1m[-2]

    if rsi[-1] < 35 and current_price > vwap[-1] and prev_price <= vwap[-2] and prev_price < current_price:
        sl = symbol_config["sl_min"] + (symbol_config["sl_max"] - symbol_config["sl_min"]) // 2
        tp = int(sl * 1.5)
        tp = min(tp, symbol_config["tp_max"])
        return Signal("buy", "RSI + VWAP", 80, sl, tp)

    if rsi[-1] > 65 and current_price < vwap[-1] and prev_price >= vwap[-2] and prev_price > current_price:
        sl = symbol_config["sl_min"] + (symbol_config["sl_max"] - symbol_config["sl_min"]) // 2
        tp = int(sl * 1.5)
        tp = min(tp, symbol_config["tp_max"])
        return Signal("sell", "RSI + VWAP", 80, sl, tp)

    return None


def strategy_consolidation_breakout(closes_1m, volumes_1m, symbol_config):
    if not is_consolidating(closes_1m[:-1], threshold_pct=0.002, lookback=10):
        return None

    breakout = detect_breakout(closes_1m, lookback=10)
    prev_price = closes_1m[-2]
    current_price = closes_1m[-1]

    if breakout == "bullish" and current_price > prev_price:
        sl = symbol_config["sl_min"]
        tp = int(sl * 1.5)
        tp = max(tp, symbol_config["tp_min"])
        return Signal("buy", "Consolidation Breakout", 75, sl, tp)

    if breakout == "bearish" and current_price < prev_price:
        sl = symbol_config["sl_min"]
        tp = int(sl * 1.5)
        tp = max(tp, symbol_config["tp_min"])
        return Signal("sell", "Consolidation Breakout", 75, sl, tp)

    return None


def strategy_ema_scalping(closes_1m, volumes_1m, symbol_config):
    ema_fast = calc_ema(closes_1m, EMA_FAST)
    ema_slow = calc_ema(closes_1m, EMA_SLOW)

    if len(ema_fast) < EMA_SLOW + 2 or ema_fast[-1] == 0 or ema_slow[-1] == 0:
        return None

    current_price = closes_1m[-1]
    prev_price = closes_1m[-2]

    fast_crossed_above = ema_fast[-2] <= ema_slow[-2] and ema_fast[-1] > ema_slow[-1]
    fast_crossed_below = ema_fast[-2] >= ema_slow[-2] and ema_fast[-1] < ema_slow[-1]

    if fast_crossed_above and current_price > ema_fast[-1] and current_price > prev_price:
        sl = symbol_config["sl_min"]
        tp = sl
        return Signal("buy", "EMA Scalping", 70, sl, tp)

    if fast_crossed_below and current_price < ema_fast[-1] and current_price < prev_price:
        sl = symbol_config["sl_min"]
        tp = sl
        return Signal("sell", "EMA Scalping", 70, sl, tp)

    return None


def evaluate_all_strategies(closes_1m, volumes_1m, closes_5m, symbol_config):
    trend = get_trend(closes_5m)

    if trend == "sideways":
        return None, trend

    strategies = [
        strategy_rsi_divergence_bb,
        strategy_rsi_vwap,
        strategy_consolidation_breakout,
        strategy_ema_scalping,
    ]

    best_signal = None
    for strat in strategies:
        signal = strat(closes_1m, volumes_1m, symbol_config)
        if signal is None:
            continue
        if trend == "bullish" and signal.direction != "buy":
            continue
        if trend == "bearish" and signal.direction != "sell":
            continue
        if best_signal is None or signal.confidence > best_signal.confidence:
            best_signal = signal

    return best_signal, trend
  
