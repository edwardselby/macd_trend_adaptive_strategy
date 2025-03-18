import logging

from ..performance import PerformanceTracker
from ..regime import RegimeDetector

logger = logging.getLogger(__name__)


class ROICalculator:
    """Calculates adaptive ROI values based on performance and market regime"""

    def __init__(self, performance_tracker: PerformanceTracker, regime_detector: RegimeDetector, config):
        """
        Initialize with needed components and configuration

        Args:
            performance_tracker: For win rate information
            regime_detector: For market regime information
            config: Strategy configuration with ROI parameters
        """
        self.performance_tracker = performance_tracker
        self.regime_detector = regime_detector
        self.config = config

        # Cache for ROI values to reduce recalculation frequency
        self.roi_cache = {
            'long': self.config.default_roi,
            'short': self.config.default_roi,
            'last_updated': 0
        }

    def _calculate_adaptive_roi(self, direction: str) -> float:
        """
        Calculate adaptive ROI based on recent win rate for a direction.

        The ROI scales linearly between min_roi and max_roi based on the win rate
        between min_win_rate and max_win_rate.

        Args:
            direction: Trade direction ('long' or 'short')

        Returns:
            float: Calculated ROI target as a decimal (e.g., 0.05 for 5%)
        """
        win_rate = self.performance_tracker.get_recent_win_rate(direction)

        # Normalize win rate to 0-1 range for scaling
        normalized_wr = max(0, min(1, (win_rate - self.config.min_win_rate) /
                                   (self.config.max_win_rate - self.config.min_win_rate)))

        # Calculate ROI based on normalized win rate
        adaptive_roi = self.config.min_roi + normalized_wr * (
                self.config.max_roi - self.config.min_roi)

        # Apply direction-specific boost if configured
        if direction == 'long' and self.config.long_roi_boost > 0:
            adaptive_roi += self.config.long_roi_boost

        # Ensure ROI stays within bounds
        return max(self.config.min_roi, min(self.config.max_roi, adaptive_roi))

    def update_roi_cache(self, current_timestamp: int) -> None:
        """
        Update cached ROI values if needed

        Args:
            current_timestamp: Current time as unix timestamp
        """
        # Check if cache needs updating
        if (current_timestamp - self.roi_cache['last_updated']) > self.config.roi_cache_update_interval:
            # Update ROI values
            self.roi_cache['long'] = self._calculate_adaptive_roi('long')
            self.roi_cache['short'] = self._calculate_adaptive_roi('short')
            self.roi_cache['last_updated'] = current_timestamp

            # Log the updated values
            logger.debug(
                f"Updated ROI cache - "
                f"Long: {self.roi_cache['long']:.2%}, "
                f"Short: {self.roi_cache['short']:.2%}"
            )

    def get_trade_roi(self, direction: str) -> float:
        """
        Calculate the appropriate ROI target for a specific trade based on:
        1. Direction-specific win rate
        2. Whether the trade is counter-trend or aligned with the market regime

        Args:
            direction: Trade direction ('long' or 'short')

        Returns:
            float: ROI target for this trade
        """
        # Get base ROI from cache
        base_roi = self.roi_cache[direction]

        # Apply factors based on trend alignment
        is_counter_trend = self.regime_detector.is_counter_trend(direction)
        is_aligned_trend = self.regime_detector.is_aligned_trend(direction)

        if is_counter_trend:
            # Take profits more quickly on counter-trend trades
            return base_roi * self.config.counter_trend_factor
        elif is_aligned_trend:
            # Let profits run longer on aligned-trend trades
            return base_roi * self.config.aligned_trend_factor
        else:
            # Neutral market regime or not enough data - use standard ROI
            return base_roi