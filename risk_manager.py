import logging
from datetime import datetime, timezone
from .config import MAX_DAILY_TRADES, MAX_CONSECUTIVE_LOSSES, NEWS_AVOID_HOURS, NEWS_WINDOW_MINUTES

logger = logging.getLogger("trading_bot.risk")


class RiskManager:
    def __init__(self):
        self.daily_trades = 0
        self.consecutive_losses = 0
        self.wins = 0
        self.losses = 0
        self.total_profit = 0.0
        self.last_reset_date = None
        self.has_open_position = False

    def reset_daily(self):
        today = datetime.now(timezone.utc).date()
        if self.last_reset_date != today:
            logger.info(f"Resetting daily counters for {today}")
            self.daily_trades = 0
            self.consecutive_losses = 0
            self.wins = 0
            self.losses = 0
            self.total_profit = 0.0
            self.last_reset_date = today

    def can_trade(self):
        self.reset_daily()

        if self.has_open_position:
            logger.info("Skipping: already have an open position")
            return False

        if self.daily_trades >= MAX_DAILY_TRADES:
            logger.warning(f"Max daily trades reached ({MAX_DAILY_TRADES})")
            return False

        if self.consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
            logger.warning(f"Max consecutive losses reached ({MAX_CONSECUTIVE_LOSSES}), stopping for today")
            return False

        if self._is_news_time():
            logger.info("Avoiding trade during news time")
            return False

        return True

    def record_trade_open(self):
        self.daily_trades += 1
        self.has_open_position = True

    def record_trade_close(self, profit):
        self.has_open_position = False
        self.total_profit += profit
        if profit >= 0:
            self.wins += 1
            self.consecutive_losses = 0
        else:
            self.losses += 1
            self.consecutive_losses += 1

    def _is_news_time(self):
        now = datetime.now(timezone.utc)
        current_minutes = now.hour * 60 + now.minute
        for hour, minute in NEWS_AVOID_HOURS:
            news_minutes = hour * 60 + minute
            if abs(current_minutes - news_minutes) <= NEWS_WINDOW_MINUTES:
                return True
        return False

    def get_summary(self):
        return {
            "daily_trades": self.daily_trades,
            "wins": self.wins,
            "losses": self.losses,
            "consecutive_losses": self.consecutive_losses,
            "total_profit": self.total_profit,
        }
