from .mode_enum import StrategyMode
from .timeframe_config import TimeframeConfig


class StrategyConfig:
    """Configuration class to store and manage strategy parameters"""

    def __init__(self, mode: StrategyMode = StrategyMode.DEFAULT, timeframe: str = '15m'):
        # Store the timeframe
        self.timeframe = timeframe

        # Get timeframe-specific indicator settings
        indicator_settings = TimeframeConfig.get_indicator_settings(timeframe)

        # Store indicator settings
        self.fast_length = indicator_settings['fast_length']
        self.slow_length = indicator_settings['slow_length']
        self.signal_length = indicator_settings['signal_length']
        self.adx_period = indicator_settings['adx_period']
        self.adx_threshold = indicator_settings['adx_threshold']
        self.ema_fast = indicator_settings['ema_fast']
        self.ema_slow = indicator_settings['ema_slow']
        self.startup_candle_count = indicator_settings['startup_candle_count']
        self.roi_cache_update_interval = indicator_settings['roi_cache_update_interval']

        # The baseline ROI target used for calculating adaptive ROI values
        self.base_roi = 0.075
        self.min_roi = 0.05
        self.max_roi = 0.10

        # Risk to reward ratio settings
        self.risk_reward_ratio = 0.67
        self.min_stoploss = -0.02
        self.max_stoploss = -0.1
        self.use_dynamic_stoploss = True
        self.static_stoploss = -0.05

        # Trend factor settings
        self.counter_trend_factor = 0.6
        self.aligned_trend_factor = 1.2
        self.counter_trend_stoploss_factor = 1.2
        self.aligned_trend_stoploss_factor = 0.8

        # Win rate and regime settings
        self.min_win_rate = 0.4
        self.max_win_rate = 0.8
        self.min_recent_trades_per_direction = 5
        self.regime_win_rate_diff = 0.15
        self.max_recent_trades = 10

        # Default ROI settings
        self.default_roi = self.max_roi + self.min_roi
        self.long_roi_boost = 0.0
        self.use_default_roi_exit = True

        # Apply specific configuration based on mode
        self._apply_config(mode)

    def _apply_config(self, mode: StrategyMode):
        """Apply specific parameter set based on the selected mode/timeframe"""

        # Default 15m config - already set by default in __init__
        if mode == StrategyMode.DEFAULT:
            pass  # Use default values

        # 1-minute timeframe config
        elif mode == StrategyMode.TIMEFRAME_1M:
            # Set timeframe
            self.timeframe = '1m'

            # Update indicator settings
            indicator_settings = TimeframeConfig.get_indicator_settings('1m')
            self.fast_length = indicator_settings['fast_length']
            self.slow_length = indicator_settings['slow_length']
            self.signal_length = indicator_settings['signal_length']
            self.adx_period = indicator_settings['adx_period']
            self.adx_threshold = indicator_settings['adx_threshold']
            self.ema_fast = indicator_settings['ema_fast']
            self.ema_slow = indicator_settings['ema_slow']
            self.startup_candle_count = indicator_settings['startup_candle_count']
            self.roi_cache_update_interval = indicator_settings['roi_cache_update_interval']

            # 1m-specific strategy parameters
            self.base_roi = 0.02  # Lower ROI targets for shorter timeframe
            self.min_roi = 0.01
            self.max_roi = 0.04
            self.static_stoploss = -0.02  # Tighter stoploss
            self.risk_reward_ratio = 0.5  # 1:2 risk:reward for faster timeframe
            self.min_stoploss = -0.01
            self.max_stoploss = -0.05
            self.counter_trend_factor = 0.4
            self.aligned_trend_factor = 0.7
            self.counter_trend_stoploss_factor = 1.5
            self.aligned_trend_stoploss_factor = 0.7
            self.min_win_rate = 0.35
            self.max_win_rate = 0.75
            self.min_recent_trades_per_direction = 5
            self.regime_win_rate_diff = 0.1
            self.max_recent_trades = 20
            self.default_roi = 0.1
            self.long_roi_boost = 0.005
            self.use_default_roi_exit = True
            self.use_dynamic_stoploss = True

        # 5-minute timeframe config
        elif mode == StrategyMode.TIMEFRAME_5M:
            # Similar implementation as 1m with 5m values
            # ... (implementation code here)
            pass

        # 30-minute timeframe config
        elif mode == StrategyMode.TIMEFRAME_30M:
            # Similar implementation as 1m with 30m values
            # ... (implementation code here)
            pass

        # 1-hour timeframe config
        elif mode == StrategyMode.TIMEFRAME_1H:
            # Similar implementation as 1m with 1h values
            # ... (implementation code here)
            pass