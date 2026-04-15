import numpy as np


def calc_rsi(closes, period=14):
    if len(closes) < period + 1:
        return np.array([])
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = np.zeros(len(deltas))
    avg_loss = np.zeros(len(deltas))
    avg_gain[period - 1] = np.mean(gains[:period])
    avg_loss[period - 1] = np.mean(losses[:period])

    for i in range(period, len(deltas)):
        avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gains[i]) / period
        avg_loss[i] = (avg_loss[i - 1] * (period - 1) + losses[i]) / period

    rs = np.where(avg_loss != 0, avg_gain / avg_loss, 100.0)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi


def calc_bollinger_bands(closes, period=20, std_dev=2):
    if len(closes) < period:
        return np.array([]), np.array([]), np.array([])
    middle = np.array([np.mean(closes[max(0, i - period + 1):i + 1]) for i in range(len(closes))])
    std = np.array([np.std(closes[max(0, i - period + 1):i + 1]) for i in range(len(closes))])
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    return upper, middle, lower


def calc_ema(closes, period):
    if len(closes) < period:
        return np.array([])
    ema = np.zeros(len(closes))
    ema[period - 1] = np.mean(closes[:period])
    multiplier = 2.0 / (period + 1)
    for i in range(period, len(closes)):
        ema[i] = (closes[i] - ema[i - 1]) * multiplier + ema[i - 1]
    return ema


def calc_vwap(closes, volumes, period=20):
    if len(closes) < period or len(volumes) < period:
        return np.array([])
    typical_price = closes.copy()
    vwap = np.zeros(len(closes))
    for i in range(period - 1, len(closes)):
        start = max(0, i - period + 1)
        tp_slice = typical_price[start:i + 1]
        vol_slice = volumes[start:i + 1]
        total_vol = np.sum(vol_slice)
        if total_vol > 0:
            vwap[i] = np.sum(tp_slice * vol_slice) / total_vol
        else:
            vwap[i] = closes[i]
    return vwap


def detect_rsi_divergence(closes, rsi, lookback=5):
    if len(closes) < lookback + 2 or len(rsi) < lookback + 2:
        return "none"
    price_recent = closes[-lookback:]
    rsi_recent = rsi[-lookback:]

    price_prev = closes[-(lookback * 2):-lookback] if len(closes) >= lookback * 2 else closes[:lookback]
    rsi_prev = rsi[-(lookback * 2):-lookback] if len(rsi) >= lookback * 2 else rsi[:lookback]

    if len(price_prev) == 0 or len(rsi_prev) == 0:
        return "none"

    if np.min(price_recent) < np.min(price_prev) and np.min(rsi_recent) > np.min(rsi_prev):
        return "bullish"

    if np.max(price_recent) > np.max(price_prev) and np.max(rsi_recent) < np.max(rsi_prev):
        return "bearish"

    return "none"


def is_consolidating(closes, threshold_pct=0.002, lookback=10):
    if len(closes) < lookback:
        return False
    recent = closes[-lookback:]
    price_range = (np.max(recent) - np.min(recent)) / np.mean(recent)
    return price_range < threshold_pct


def detect_breakout(closes, lookback=10):
    if len(closes) < lookback + 2:
        return "none"
    consolidation_range = closes[-(lookback + 1):-1]
    high = np.max(consolidation_range)
    low = np.min(consolidation_range)
    current = closes[-1]

    if current > high:
        return "bullish"
    elif current < low:
        return "bearish"
    return "none"
  
