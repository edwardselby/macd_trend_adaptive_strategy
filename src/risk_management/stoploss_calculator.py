import logging

logger = logging.getLogger(__name__)


class StoplossCalculator:
    """Calculates dynamic stoploss values based on win rates and risk parameters"""

    def __init__(self, config):
        """
        Initialize with configuration only

        Args:
            config: Strategy configuration with stoploss parameters
        """
        self.config = config

    def calculate_dynamic_stoploss(self, win_rate: float, is_counter_trend: bool, is_aligned_trend: bool) -> float:
        """
        Calculate dynamic stoploss based on win rate and trend alignment.

        Args:
            win_rate: Current win rate for the trade direction
            is_counter_trend: Whether the trade is counter to market regime
            is_aligned_trend: Whether the trade aligns with market regime

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

        # Normalize win rate to 0-1 range for scaling
        normalized_wr = max(0, min(1, (win_rate - self.config.min_win_rate) /
                                   (self.config.max_win_rate - self.config.min_win_rate)))

        # Higher win rate = closer to max_stoploss (more negative, wider)
        # Lower win rate = closer to min_stoploss (less negative, tighter)
        base_stoploss = self.config.min_stoploss + normalized_wr * (
                self.config.max_stoploss - self.config.min_stoploss)

        # Apply trend alignment factors
        factor = 1.0
        if is_counter_trend:
            factor = self.config.counter_trend_stoploss_factor
            adjusted_stoploss = base_stoploss * factor
        elif is_aligned_trend:
            factor = self.config.aligned_trend_stoploss_factor
            adjusted_stoploss = base_stoploss * factor
        else:
            adjusted_stoploss = base_stoploss

        # IMPORTANT: Ensure stoploss is always negative
        if adjusted_stoploss >= 0:
            adjusted_stoploss = self.config.min_stoploss  # Use minimum stoploss as fallback

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

        return final_stoploss

    def calculate_stoploss_price(self, entry_rate: float, stoploss: float, is_short: bool) -> float:
        """Original calculate_stoploss_price method - unchanged"""
        if is_short:
            # For short trades, stoploss is reached when price goes UP
            stoploss_price = entry_rate * (1 - stoploss)  # Note the subtraction of negative number = addition
        else:
            # For long trades, stoploss is reached when price goes DOWN
            stoploss_price = entry_rate * (1 + stoploss)

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
