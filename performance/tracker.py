import logging
from typing import Dict, Any

from freqtrade.persistence import Trade

from performance import DBHandler

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

        # Log trade result
        logger.info(f"Trade exit - {direction} - {'WIN' if is_win else 'LOSS'} - {profit_ratio:.2%}")

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

        # Save updated tracking data
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
        long_wr = self.get_recent_win_rate('long')
        short_wr = self.get_recent_win_rate('short')

        total_trades = (self.performance_tracking['long']['wins'] +
                        self.performance_tracking['long']['losses'] +
                        self.performance_tracking['short']['wins'] +
                        self.performance_tracking['short']['losses'])

        logger.info(f"Performance stats after {total_trades} trades - "
                    f"Long: Win Rate {long_wr:.2f}, Total {self.performance_tracking['long']['wins'] + self.performance_tracking['long']['losses']} | "
                    f"Short: Win Rate {short_wr:.2f}, Total {self.performance_tracking['short']['wins'] + self.performance_tracking['short']['losses']}")