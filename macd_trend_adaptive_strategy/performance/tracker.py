import logging
from typing import Dict, Any

from freqtrade.persistence import Trade

from .db_handler import DBHandler
from ..utils import log_messages

logger = logging.getLogger(__name__)


class PerformanceTracker:
    """Tracks and manages trade performance metrics"""

    def __init__(self, db_handler: DBHandler, max_recent_trades: int = 10):
        """
        Initialize with a database handler and configuration

        Args:
            db_handler: Database handler for storing/retrieving performance data
            max_recent_trades: Maximum number of recent trades to track for win rate
        """
        self.db_handler = db_handler
        self.max_recent_trades = max_recent_trades
        self.performance_tracking = self._init_tracking()

    def _init_tracking(self) -> Dict[str, Dict[str, Any]]:
        """Initialize performance tracking with data from DB"""
        return self.db_handler.load_performance_data()

    def update_performance(self, trade: Trade, profit_ratio: float) -> None:
        """
        Update performance tracking when a trade exits

        Args:
            trade: The completed trade
            profit_ratio: Profit ratio of the trade
        """
        direction = 'short' if trade.is_short else 'long'
        is_win = profit_ratio > 0

        # Update stats
        if is_win:
            self.performance_tracking[direction]['wins'] += 1
            self.performance_tracking[direction]['consecutive_wins'] += 1
            self.performance_tracking[direction]['consecutive_losses'] = 0
        else:
            self.performance_tracking[direction]['losses'] += 1
            self.performance_tracking[direction]['consecutive_losses'] += 1
            self.performance_tracking[direction]['consecutive_wins'] = 0

        # Update last trades list
        self.performance_tracking[direction]['last_trades'].append(1 if is_win else 0)
        if len(self.performance_tracking[direction]['last_trades']) > self.max_recent_trades:
            self.performance_tracking[direction]['last_trades'].pop(0)

        # Update total profit
        self.performance_tracking[direction]['total_profit'] += profit_ratio

        # Get updated stats for logging
        total_wins = self.performance_tracking[direction]['wins']
        total_losses = self.performance_tracking[direction]['losses']
        win_rate = self.get_win_rate(direction)
        recent_win_rate = self.get_recent_win_rate(direction)

        # Log after all updates are complete
        log_messages.log_performance_update(
            pair=trade.pair,
            direction=direction,
            is_win=is_win,
            profit_ratio=profit_ratio,
            total_wins=total_wins,
            total_losses=total_losses,
            win_rate=win_rate,
            recent_win_rate=recent_win_rate
        )

        # Save updated tracking data - ONLY ONCE at the end
        self.db_handler.save_performance_data(self.performance_tracking)

    def get_win_rate(self, direction: str) -> float:
        """Calculate overall win rate for specified direction"""
        total = self.performance_tracking[direction]['wins'] + self.performance_tracking[direction]['losses']
        if total == 0:
            return 0.5
        return self.performance_tracking[direction]['wins'] / total

    def get_recent_win_rate(self, direction: str) -> float:
        """
        Calculate win rate for recent trades.
        Uses only the most recent trades (up to max_recent_trades).
        """
        trades = self.performance_tracking[direction]['last_trades']
        if not trades:
            return 0.5  # Default to 50% if no data
        return sum(trades) / len(trades)

    def get_recent_trades_count(self, direction: str) -> int:
        """Get number of recent trades for specified direction"""
        return len(self.performance_tracking[direction]['last_trades'])

    def log_performance_stats(self) -> None:
        """Log current performance statistics"""
        long_wr = self.get_win_rate('long')
        short_wr = self.get_win_rate('short')

        long_wins = self.performance_tracking['long']['wins']
        long_losses = self.performance_tracking['long']['losses']
        short_wins = self.performance_tracking['short']['wins']
        short_losses = self.performance_tracking['short']['losses']

        total_trades = long_wins + long_losses + short_wins + short_losses

        long_profit = self.performance_tracking['long']['total_profit']
        short_profit = self.performance_tracking['short']['total_profit']

        log_messages.log_performance_summary(
            total_trades=total_trades,
            long_wins=long_wins,
            long_losses=long_losses,
            long_wr=long_wr,
            short_wins=short_wins,
            short_losses=short_losses,
            short_wr=short_wr,
            long_profit=long_profit,
            short_profit=short_profit
        )
