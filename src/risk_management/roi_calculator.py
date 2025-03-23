class ROICalculator:
    """Calculates adaptive ROI values based on stoploss and market regime"""

    def __init__(self, config):
        """
        Initialize with configuration only

        Args:
            config: Strategy configuration with ROI parameters
        """
        self.config = config

        # Get default ROI from config or calculate a fallback value
        default_roi = getattr(self.config, 'default_roi',
                              abs(self.config.max_stoploss) * self.config.risk_reward_ratio * 1.2)

        # Cache for ROI values to reduce recalculation frequency
        self.roi_cache = {
            'long': default_roi,
            'short': default_roi,
            'last_updated': 0
        }

    def calculate_roi_from_stoploss(self, stoploss: float, is_counter_trend: bool, is_aligned_trend: bool) -> float:
        """
        Calculate ROI based on stoploss value and trend alignment

        Args:
            stoploss: The calculated stoploss value (negative number)
            is_counter_trend: Whether this trade counters the market regime
            is_aligned_trend: Whether this trade aligns with market regime

        Returns:
            float: Target ROI value
        """
        # Calculate base ROI from stoploss using risk-reward ratio
        # Stoploss is negative, so take absolute value
        base_roi = abs(stoploss) * self.config.risk_reward_ratio

        # Apply trend alignment factors to ROI
        factor = 1.0
        if is_counter_trend:
            factor = self.config.counter_trend_factor
            final_roi = base_roi * factor
        elif is_aligned_trend:
            factor = self.config.aligned_trend_factor
            final_roi = base_roi * factor
        else:
            final_roi = base_roi

        return final_roi

    def update_roi_cache(self, current_timestamp: int, win_rates: dict,
                         is_counter_trend_fn, is_aligned_trend_fn, calculate_dynamic_stoploss_fn) -> None:
        """
        Update cached ROI values if needed

        Args:
            current_timestamp: Current time as unix timestamp
            win_rates: Dictionary with win rates for 'long' and 'short'
            is_counter_trend_fn: Function to check if trade is counter-trend
            is_aligned_trend_fn: Function to check if trade is aligned with trend
            calculate_dynamic_stoploss_fn: Function to calculate dynamic stoploss
        """
        # Check if cache needs updating
        if (current_timestamp - self.roi_cache['last_updated']) > self.config.roi_cache_update_interval:
            # Update ROI values for both directions
            for direction in ['long', 'short']:
                # Calculate stoploss based on win rate and trend alignment
                win_rate = win_rates[direction]
                is_counter_trend = is_counter_trend_fn(direction)
                is_aligned_trend = is_aligned_trend_fn(direction)

                stoploss = calculate_dynamic_stoploss_fn(win_rate, is_counter_trend, is_aligned_trend)

                # Calculate ROI from stoploss
                self.roi_cache[direction] = self.calculate_roi_from_stoploss(
                    stoploss, is_counter_trend, is_aligned_trend)

            # Update timestamp
            self.roi_cache['last_updated'] = current_timestamp
