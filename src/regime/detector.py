import logging
from typing import Literal

from ..performance.tracker import PerformanceTracker
from ..utils.log_messages import log_regime_detection

logger = logging.getLogger(__name__)


class RegimeDetector:
    """Detects market regime based on performance metrics"""

    NEUTRAL = "neutral"
    BULLISH = "bullish"
    BEARISH = "bearish"

    def __init__(self, performance_tracker: PerformanceTracker, config):
        """
        Initialize with performance tracker and configuration

        Args:
            performance_tracker: Performance tracker for win rate analysis
            config: Strategy configuration with regime parameters
        """
        self.performance_tracker = performance_tracker
        self.config = config

    def detect_regime(self) -> Literal["bullish", "bearish", "neutral"]:
        """
        Detect current market regime based on recent performance.

        The regime is determined by comparing the win rates of long vs short trades:
        - "bullish": Long trades significantly outperform short trades
        - "bearish": Short trades significantly outperform long trades
        - "neutral": No significant difference in performance

        Returns:
            str: Current market regime ("bullish", "bearish", or "neutral")
        """
        # Get win rates based on recent trades only
        long_win_rate = self.performance_tracker.get_recent_win_rate('long')
        short_win_rate = self.performance_tracker.get_recent_win_rate('short')

        # Check if we have enough recent trades
        long_recent_trades = self.performance_tracker.get_recent_trades_count('long')
        short_recent_trades = self.performance_tracker.get_recent_trades_count('short')

        # Default to neutral if we don't have enough recent data
        if (
            long_recent_trades < self.config.min_recent_trades_per_direction or
            short_recent_trades < self.config.min_recent_trades_per_direction
        ):
            log_regime_detection(
                long_wr=long_win_rate,
                short_wr=short_win_rate,
                long_trades=long_recent_trades,
                short_trades=short_recent_trades,
                win_rate_diff=0,
                threshold=self.config.min_recent_trades_per_direction,
                regime=self.NEUTRAL
            )
            return self.NEUTRAL

        # Calculate win rate difference
        win_rate_difference = long_win_rate - short_win_rate

        # Determine regime based on relative performance
        regime = self.NEUTRAL
        if win_rate_difference > self.config.regime_win_rate_diff:
            regime = self.BULLISH
        elif win_rate_difference < -self.config.regime_win_rate_diff:
            regime = self.BEARISH

        log_regime_detection(
            long_wr=long_win_rate,
            short_wr=short_win_rate,
            long_trades=long_recent_trades,
            short_trades=short_recent_trades,
            win_rate_diff=win_rate_difference,
            threshold=self.config.regime_win_rate_diff,
            regime=regime
        )

        return regime

    def is_counter_trend(self, direction: str) -> bool:
        """
        Determine if a trade is counter to the current market regime

        Args:
            direction: Trade direction ('long' or 'short')

        Returns:
            bool: True if the trade is counter-trend, False otherwise
        """
        regime = self.detect_regime()
        return (regime == self.BEARISH and direction == 'long') or (regime == self.BULLISH and direction == 'short')

    def is_aligned_trend(self, direction: str) -> bool:
        """
        Determine if a trade aligns with the current market regime

        Args:
            direction: Trade direction ('long' or 'short')

        Returns:
            bool: True if the trade aligns with the trend, False otherwise
        """
        regime = self.detect_regime()
        return (regime == self.BULLISH and direction == 'long') or (regime == self.BEARISH and direction == 'short')