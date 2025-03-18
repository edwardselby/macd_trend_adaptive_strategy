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
        if not self.config.use_dynamic_stoploss:
            return self.config.static_stoploss

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

        final_stoploss = max(
            self.config.min_stoploss,
            min(adjusted_stoploss, self.config.max_stoploss)
        )

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
            stoploss_price = entry_rate * (1 - stoploss)
        else:
            stoploss_price = entry_rate * (1 + stoploss)

        direction = "short" if is_short else "long"

        log_stoploss_price(
            direction=direction,
            entry_price=entry_rate,
            stoploss_pct=stoploss,
            stoploss_price=stoploss_price
        )

        return stoploss_price
