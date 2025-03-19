import logging
import os

from .mode_enum import StrategyMode
from .timeframe_config import TimeframeConfig
from .simplified_config import SimplifiedConfig

logger = logging.getLogger(__name__)


class StrategyConfig:
    """
    # Risk Management Documentation for MACD Trend Adaptive Strategy

    ## Market Regime Detection

    The strategy detects market regimes based on the relative performance of long vs. short trades:

    - **Bullish Regime**: Long trades perform significantly better than short trades
    - **Bearish Regime**: Short trades perform significantly better than long trades
    - **Neutral Regime**: No significant difference in performance between long and short trades

    ## Trade Alignment

    Trades are classified based on their alignment with the detected market regime:

    - **Aligned Trades**: Long trades in bullish regime or short trades in bearish regime
    - **Counter-Trend Trades**: Short trades in bullish regime or long trades in bearish regime
    - **Neutral Trades**: Any trade during a neutral regime

    ## Risk Factor System

    The strategy applies different factors to ROI and stoploss based on trade alignment:

    ### ROI Factors:
    - **counter_trend_factor**: Applied to ROI for counter-trend trades
      - Value is 0.5 to reduce ROI target (take profits sooner)
      - Example: If base ROI is 5% and factor is 0.5, counter-trend ROI = 2.5%

    - **aligned_trend_factor**: Applied to ROI for aligned trades
      - Value is 1.0 (no change to ROI target)

    ### Stoploss Factors:
    - **counter_trend_stoploss_factor**: Applied to stoploss for counter-trend trades
      - Value is 0.5 to make stoploss less negative (tighter protection)
      - Example: If base stoploss is -3% and factor is 0.5, counter-trend stoploss = -1.5%

    - **aligned_trend_stoploss_factor**: Applied to stoploss for aligned trades
      - Value is 1.0 (no change to stoploss)

    ## Risk Management Principles

    The strategy applies these fundamental principles:

    1. **Counter-trend trades** have:
       - Lower ROI targets (take profits earlier)
       - Tighter stoplosses (exit losing trades faster)

    2. **Aligned trades** have:
       - Standard ROI targets
       - Standard stoplosses

    3. **Win rate adaptation**:
       - ROI targets scale dynamically based on recent win rates
       - Higher win rates increase ROI targets
       - Lower win rates decrease ROI targets

    4. **Risk-reward ratio**:
       - Stoploss values are calculated using ROI targets and risk_reward_ratio
       - Example: With ROI = 3% and ratio = 0.5 (1:2), stoploss = -1.5%
    """

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

        # Apply time-based indicator adjustments
        self._apply_indicator_config(mode)

        # Load simplified configuration parameters for this timeframe
        self._load_simplified_config(timeframe)

        # Log the configuration
        logger.info(self.simplified_config.get_config_summary())

    def _load_simplified_config(self, timeframe: str):
        """Load simplified configuration parameters for the specified timeframe"""
        # Look for configuration file in FreqTrade's user_data directory
        config_path = os.path.join('user_data', 'macd_config.json')

        # Create the simplified config with timeframe-specific settings
        self.simplified_config = SimplifiedConfig(config_path, timeframe)

        # Copy simplified parameters to strategy config
        self.base_roi = self.simplified_config.base_roi
        self.min_roi = self.simplified_config.min_roi
        self.max_roi = self.simplified_config.max_roi

        # Risk to reward ratio settings
        self.risk_reward_ratio = self.simplified_config.risk_reward_ratio
        self.min_stoploss = self.simplified_config.min_stoploss
        self.max_stoploss = self.simplified_config.max_stoploss
        self.static_stoploss = self.simplified_config.static_stoploss
        self.use_dynamic_stoploss = self.simplified_config.use_dynamic_stoploss

        # Trend factor settings - simplified
        self.counter_trend_factor = self.simplified_config.counter_trend_factor
        self.aligned_trend_factor = self.simplified_config.aligned_trend_factor
        self.counter_trend_stoploss_factor = self.simplified_config.counter_trend_stoploss_factor
        self.aligned_trend_stoploss_factor = self.simplified_config.aligned_trend_stoploss_factor

        # Win rate and regime settings - simplified
        self.min_win_rate = self.simplified_config.min_win_rate
        self.max_win_rate = self.simplified_config.max_win_rate
        self.min_recent_trades_per_direction = self.simplified_config.min_recent_trades_per_direction
        self.regime_win_rate_diff = self.simplified_config.regime_win_rate_diff
        self.max_recent_trades = self.simplified_config.max_recent_trades

        # Default ROI settings - simplified
        self.default_roi = self.simplified_config.default_roi
        self.long_roi_boost = self.simplified_config.long_roi_boost
        self.use_default_roi_exit = self.simplified_config.use_default_roi_exit

    def _apply_indicator_config(self, mode: StrategyMode):
        """Apply specific indicator settings based on the selected mode/timeframe"""

        # Default 15m config - already set by default in __init__
        if mode == StrategyMode.DEFAULT:
            pass  # Use default values

        # 1-minute timeframe config
        elif mode == StrategyMode.TIMEFRAME_1M:
            # Set timeframe
            self.timeframe = '1m'

            # Update indicator settings from TimeframeConfig
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

        # 5-minute timeframe config
        elif mode == StrategyMode.TIMEFRAME_5M:
            # Set timeframe
            self.timeframe = '5m'

            # Update indicator settings from TimeframeConfig
            indicator_settings = TimeframeConfig.get_indicator_settings('5m')
            self.fast_length = indicator_settings['fast_length']
            self.slow_length = indicator_settings['slow_length']
            self.signal_length = indicator_settings['signal_length']
            self.adx_period = indicator_settings['adx_period']
            self.adx_threshold = indicator_settings['adx_threshold']
            self.ema_fast = indicator_settings['ema_fast']
            self.ema_slow = indicator_settings['ema_slow']
            self.startup_candle_count = indicator_settings['startup_candle_count']
            self.roi_cache_update_interval = indicator_settings['roi_cache_update_interval']

        # 30-minute timeframe config
        elif mode == StrategyMode.TIMEFRAME_30M:
            # Set timeframe
            self.timeframe = '30m'

            # Update indicator settings from TimeframeConfig
            indicator_settings = TimeframeConfig.get_indicator_settings('30m')
            self.fast_length = indicator_settings['fast_length']
            self.slow_length = indicator_settings['slow_length']
            self.signal_length = indicator_settings['signal_length']
            self.adx_period = indicator_settings['adx_period']
            self.adx_threshold = indicator_settings['adx_threshold']
            self.ema_fast = indicator_settings['ema_fast']
            self.ema_slow = indicator_settings['ema_slow']
            self.startup_candle_count = indicator_settings['startup_candle_count']
            self.roi_cache_update_interval = indicator_settings['roi_cache_update_interval']

        # 1-hour timeframe config
        elif mode == StrategyMode.TIMEFRAME_1H:
            # Set timeframe
            self.timeframe = '1h'

            # Update indicator settings from TimeframeConfig
            indicator_settings = TimeframeConfig.get_indicator_settings('1h')
            self.fast_length = indicator_settings['fast_length']
            self.slow_length = indicator_settings['slow_length']
            self.signal_length = indicator_settings['signal_length']
            self.adx_period = indicator_settings['adx_period']
            self.adx_threshold = indicator_settings['adx_threshold']
            self.ema_fast = indicator_settings['ema_fast']
            self.ema_slow = indicator_settings['ema_slow']
            self.startup_candle_count = indicator_settings['startup_candle_count']
            self.roi_cache_update_interval = indicator_settings['roi_cache_update_interval']