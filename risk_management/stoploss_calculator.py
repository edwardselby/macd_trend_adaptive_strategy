import logging

from regime import RegimeDetector

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
        if not self.config.use_dynamic_stoploss:
            return self.config.static_stoploss

        # Base stoploss calculation using risk_reward_ratio
        # If ROI is 3% and risk_reward_ratio is 0.67 (1:1.5), stoploss would be -2%
        base_stoploss = -1 * roi * self.config.risk_reward_ratio

        # Apply adjustment factors based on trend alignment
        is_counter_trend = self.regime_detector.is_counter_trend(direction)
        is_aligned_trend = self.regime_detector.is_aligned_trend(direction)

        if is_counter_trend:
            # Tighter stoploss for counter-trend trades (more aggressive protection)
            adjusted_stoploss = base_stoploss * self.config.counter_trend_stoploss_factor
        elif is_aligned_trend:
            # Wider stoploss for aligned-trend trades (more room to breathe)
            adjusted_stoploss = base_stoploss * self.config.aligned_trend_stoploss_factor
        else:
            # No adjustment for neutral regime
            adjusted_stoploss = base_stoploss

        # Ensure stoploss is within allowed bounds
        final_stoploss = max(
            self.config.min_stoploss,  # Don't allow stoploss smaller than min_stoploss
            min(adjusted_stoploss, self.config.max_stoploss)  # Don't allow stoploss larger than max_stoploss
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
            # For shorts, stoploss price should be ABOVE entry price
            return entry_rate * (1 - stoploss)  # stoploss is negative, so this raises the price
        else:
            # For longs, stoploss price should be BELOW entry price
            return entry_rate * (1 + stoploss)  # stoploss is negative, so this lowers the price