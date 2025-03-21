import logging

from ..regime import RegimeDetector
from ..utils import log_stoploss_calculation, log_stoploss_price

logger = logging.getLogger(__name__)


class StoplossCalculator:
    """Calculates dynamic stoploss values based on ROI and risk parameters"""

    def __init__(self, regime_detector: RegimeDetector, config):
        """
        Initialize with regime detector and configuration

        Args:
            regime_detector: For market regime information
            config: Strategy configuration with stoploss parameters
        """
        self.regime_detector = regime_detector
        self.config = config

    def calculate_dynamic_stoploss(self, roi: float, direction: str) -> float:
        """
        Calculate dynamic stoploss based on ROI and risk-reward ratio.

        Args:
            roi: The target ROI value for this trade
            direction: Trade direction ('long' or 'short')

        Returns:
            float: The calculated stoploss value (negative number representing percentage)
        """
        # Check if use_dynamic_stoploss is set and is False
        if hasattr(self.config, 'use_dynamic_stoploss') and not self.config.use_dynamic_stoploss:
            # Use static_stoploss if available, otherwise calculate a backstop stoploss
            if hasattr(self.config, 'static_stoploss'):
                return self.config.static_stoploss
            else:
                # Calculate a fallback stoploss that's more negative than max_stoploss
                return self.config.max_stoploss * 1.2

        # Base stoploss calculation using risk_reward_ratio
        # If ROI is 3% and risk_reward_ratio is 0.67 (1:1.5), stoploss would be -2%
        base_stoploss = -1 * roi * self.config.risk_reward_ratio
        is_counter_trend = self.regime_detector.is_counter_trend(direction)
        is_aligned_trend = self.regime_detector.is_aligned_trend(direction)

        factor = 1.0
        if is_counter_trend:
            factor = self.config.counter_trend_stoploss_factor
            adjusted_stoploss = base_stoploss * factor
        elif is_aligned_trend:
            factor = self.config.aligned_trend_stoploss_factor
            adjusted_stoploss = base_stoploss * factor
        else:
            adjusted_stoploss = base_stoploss

        # IMPORTANT: Ensure stoploss is always negative regardless of direction
        if adjusted_stoploss >= 0:
            adjusted_stoploss = self.config.min_stoploss  # Use minimum stoploss as fallback

        # For stoploss (negative values):
        # -0.01 (min_stoploss) is the smallest loss allowed (closest to zero)
        # -0.05 (max_stoploss) is the largest loss allowed (furthest from zero)

        # Bound the stoploss within min and max limits
        if adjusted_stoploss > self.config.min_stoploss:
            # If stoploss is too small (closer to zero than min allows)
            final_stoploss = self.config.min_stoploss
        elif adjusted_stoploss < self.config.max_stoploss:
            # If stoploss is too large (further from zero than max allows)
            final_stoploss = self.config.max_stoploss
        else:
            # Within acceptable range
            final_stoploss = adjusted_stoploss

        log_stoploss_calculation(
            direction=direction,
            roi=roi,
            risk_ratio=self.config.risk_reward_ratio,
            base_sl=base_stoploss,
            is_counter_trend=is_counter_trend,
            is_aligned_trend=is_aligned_trend,
            factor=factor,
            adjusted_sl=adjusted_stoploss,
            min_sl=self.config.min_stoploss,
            max_sl=self.config.max_stoploss,
            final_sl=final_stoploss
        )

        return final_stoploss

    def calculate_stoploss_price(self, entry_rate: float, stoploss: float, is_short: bool) -> float:
        """
        Calculate the absolute stoploss price based on entry rate and stoploss percentage

        Args:
            entry_rate: Entry price of the trade
            stoploss: Stoploss value as a negative decimal (e.g., -0.05 for 5%)
            is_short: Whether this is a short trade

        Returns:
            float: Absolute price level for the stoploss
        """
        if is_short:
            # For short trades, stoploss is reached when price goes UP
            # If entry is 100 and stoploss is -0.05 (5%), stoploss price is 105
            stoploss_price = entry_rate * (1 - stoploss)  # Note the subtraction of negative number = addition
        else:
            # For long trades, stoploss is reached when price goes DOWN
            # If entry is 100 and stoploss is -0.05 (5%), stoploss price is 95
            stoploss_price = entry_rate * (1 + stoploss)

        direction = "short" if is_short else "long"

        log_stoploss_price(
            direction=direction,
            entry_price=entry_rate,
            stoploss_pct=stoploss,
            stoploss_price=stoploss_price
        )

        return stoploss_price

    def calculate_fallback_stoploss_price(self, entry_rate: float, stoploss: float, is_short: bool) -> float:
        """
        Calculate a fallback stoploss price when normal calculation fails.

        Args:
            entry_rate: Entry price of the trade
            stoploss: Stoploss value as a negative decimal (e.g., -0.05 for 5%)
            is_short: Whether this is a short trade

        Returns:
            float: Absolute price level for the stoploss
        """
        try:
            # Convert entry_rate to float, handling potential invalid inputs
            if not isinstance(entry_rate, (int, float)):
                try:
                    entry_rate = float(entry_rate)
                except (ValueError, TypeError):
                    logger.error(f"Invalid entry rate: {entry_rate}. Using 0 as fallback.")
                    entry_rate = 0.0

            # Use the existing method's logic for calculating stoploss price
            return self.calculate_stoploss_price(entry_rate, stoploss, is_short)
        except Exception as e:
            logger.error(f"Error calculating fallback stoploss price: {e}")

            # Use static_stoploss if available, otherwise use max_stoploss * 1.2
            # This ensures the fallback is always a backstop value
            fallback_stoploss = getattr(self.config, 'static_stoploss', self.config.max_stoploss * 1.2)

            if is_short:
                # For shorts, calculate a price above entry using the fallback stoploss
                return entry_rate * (1 - fallback_stoploss)
            else:
                # For longs, calculate a price below entry using the fallback stoploss
                return entry_rate * (1 + fallback_stoploss)