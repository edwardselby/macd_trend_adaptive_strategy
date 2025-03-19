import logging

from .mode_enum import StrategyMode
from .timeframe_config import TimeframeConfig

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
      - Should be < 1.0 to reduce ROI target (take profits sooner)
      - Example: If base ROI is 5% and factor is 0.6, counter-trend ROI = 3%

    - **aligned_trend_factor**: Applied to ROI for aligned trades
      - Should be > 1.0 to increase ROI target (allow more room for profit)
      - Example: If base ROI is 5% and factor is 1.2, aligned-trend ROI = 6%

    ### Stoploss Factors:
    - **counter_trend_stoploss_factor**: Applied to stoploss for counter-trend trades
      - Should be < 1.0 to make stoploss less negative (tighter protection)
      - Example: If base stoploss is -3% and factor is 0.7, counter-trend stoploss = -2.1%

    - **aligned_trend_stoploss_factor**: Applied to stoploss for aligned trades
      - Should be > 1.0 to make stoploss more negative (looser protection)
      - Example: If base stoploss is -3% and factor is 1.2, aligned-trend stoploss = -3.6%

    ## Risk Management Principles

    The strategy applies these fundamental principles:

    1. **Counter-trend trades** have:
       - Lower ROI targets (take profits earlier)
       - Tighter stoplosses (exit losing trades faster)

    2. **Aligned trades** have:
       - Higher ROI targets (let profits run longer)
       - Looser stoplosses (give trades more room to develop)

    3. **Win rate adaptation**:
       - ROI targets scale dynamically based on recent win rates
       - Higher win rates increase ROI targets
       - Lower win rates decrease ROI targets

    4. **Risk-reward ratio**:
       - Stoploss values are calculated using ROI targets and risk_reward_ratio
       - Default risk_reward_ratio of 0.67 gives 1:1.5 risk:reward
       - Example: With ROI = 3% and ratio = 0.67, stoploss = -2%
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
        self.counter_trend_stoploss_factor = 0.8
        self.aligned_trend_stoploss_factor = 1.2

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

        # Validate risk factors
        self._validate_risk_factors()

    def _apply_config(self, mode: StrategyMode):
        """Apply specific parameter set based on the selected mode/timeframe"""

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

            # 1m-specific strategy parameters with improved risk-reward
            # For 1:1.5 risk-reward with 10x leverage
            self.base_roi = 0.03  # 3% price movement = ~30% profit with leverage
            self.min_roi = 0.02  # Minimum 2% price movement
            self.max_roi = 0.04  # Maximum 4% price movement

            # Stoploss settings
            self.static_stoploss = -0.02  # 2% price movement = ~20% loss with leverage
            self.risk_reward_ratio = 0.67  # 1:1.5 risk:reward
            self.min_stoploss = -0.015  # Tightest stoploss (1.5% price movement)
            self.max_stoploss = -0.025  # Widest stoploss (2.5% price movement)

            # Adjustment factors
            self.counter_trend_factor = 0.7  # Take profits faster for counter-trend
            self.aligned_trend_factor = 1.3  # Allow more room for profit in aligned trends
            self.counter_trend_stoploss_factor = 0.8  # Tighter stoploss for counter-trend
            self.aligned_trend_stoploss_factor = 1.1  # Slightly looser stoploss for aligned trend

            # Win rate settings
            self.min_win_rate = 0.4
            self.max_win_rate = 0.7
            self.min_recent_trades_per_direction = 5
            self.regime_win_rate_diff = 0.1
            self.max_recent_trades = 20

            # Default ROI settings
            self.default_roi = 0.025  # Default ROI target
            self.long_roi_boost = 0.0  # Small boost for long trades
            self.use_default_roi_exit = False
            self.use_dynamic_stoploss = True

        # 5-minute timeframe config
        # 5-minute timeframe config with original technical setup
        elif mode == StrategyMode.TIMEFRAME_5M:
            # Set timeframe
            self.timeframe = '5m'

            # Get timeframe-specific indicator settings from TimeframeConfig
            indicator_settings = TimeframeConfig.get_indicator_settings('5m')

            # Keep original technical parameters from TimeframeConfig
            self.fast_length = indicator_settings['fast_length']  # 8
            self.slow_length = indicator_settings['slow_length']  # 21
            self.signal_length = indicator_settings['signal_length']  # 6
            self.adx_period = indicator_settings['adx_period']  # 10
            self.adx_threshold = indicator_settings['adx_threshold']  # 18
            self.ema_fast = indicator_settings['ema_fast']  # 5
            self.ema_slow = indicator_settings['ema_slow']  # 15
            self.startup_candle_count = indicator_settings['startup_candle_count']  # 25
            self.roi_cache_update_interval = indicator_settings['roi_cache_update_interval']  # 30

            # Adjust risk/reward parameters for 5m
            # ROI settings - higher for 5m to allow more room for profit
            self.base_roi = 0.035  # 3.5% base ROI (higher than 1m)
            self.min_roi = 0.025  # Minimum 2.5% ROI
            self.max_roi = 0.045  # Maximum 4.5% ROI

            # Stoploss settings - more room since 5m has higher volatility
            self.static_stoploss = -0.022  # 2.2% static stoploss
            self.risk_reward_ratio = 0.5  # 1:2 risk-reward ratio
            self.min_stoploss = -0.016  # Minimum 1.6% stoploss
            self.max_stoploss = -0.028  # Maximum 2.8% stoploss
            self.use_dynamic_stoploss = True

            # Trend factors - adjusted for 5m
            self.counter_trend_factor = 0.6  # Take profits at 60% of target for counter-trend
            self.aligned_trend_factor = 1.2  # Allow 20% higher target for aligned trend
            self.counter_trend_stoploss_factor = 0.7  # Tighter stoploss for counter-trend
            self.aligned_trend_stoploss_factor = 1.15  # Slightly looser stoploss for aligned trend

            # Win rate and regime settings
            self.min_win_rate = 0.4
            self.max_win_rate = 0.7
            self.min_recent_trades_per_direction = 4  # Require fewer trades to detect regime
            self.regime_win_rate_diff = 0.12  # 12% difference to detect regime change
            self.max_recent_trades = 12

            # Default ROI settings
            self.default_roi = 0.028  # Default 2.8% ROI
            self.long_roi_boost = 0.004  # Small boost for long trades
            self.use_default_roi_exit = False
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

    def _validate_risk_factors(self):
        """
        Validate that risk factors maintain proper relationships:

        For ROI factors:
        - Counter-trend trades should have lower ROI targets (take profits faster)
        - Counter-trend factor should be < 1.0
        - Aligned-trend factor should be > 1.0

        For stoploss factors:
        - Counter-trend trades should have tighter stoploss (less negative)
        - Counter-trend factor should be < 1.0 to make the stoploss less negative
        - Aligned-trend factor should be > 1.0 to make the stoploss more negative
        """
        # Validate ROI factors
        if self.counter_trend_factor >= 1.0:
            logger.warning(
                f"Counter-trend ROI factor ({self.counter_trend_factor}) should be less than 1.0 "
                f"for faster profit taking. Adjusting to 0.7."
            )
            self.counter_trend_factor = 0.7

        if self.aligned_trend_factor <= 1.0:
            logger.warning(
                f"Aligned-trend ROI factor ({self.aligned_trend_factor}) should be greater than 1.0 "
                f"for higher profit targets. Adjusting to 1.2."
            )
            self.aligned_trend_factor = 1.2

        if self.counter_trend_factor >= self.aligned_trend_factor:
            logger.warning(
                f"Counter-trend ROI factor ({self.counter_trend_factor}) should be lower than "
                f"aligned-trend factor ({self.aligned_trend_factor}). Adjusting."
            )
            # Set counter-trend to 60% of aligned-trend
            self.counter_trend_factor = self.aligned_trend_factor * 0.6

        # For stoploss factors, we need to consider that stoplosses are negative values
        # Counter-trend trades should have tighter (less negative) stoploss

        # For stoploss, there are two ways to implement the factors:
        # 1. Like ROI, where counter_trend_factor < 1.0 makes stoploss smaller (tighter)
        # 2. Opposite of ROI, where counter_trend_factor > 1.0 makes stoploss smaller (tighter)

        # Based on the implementation in StoplossCalculator.calculate_dynamic_stoploss,
        # it seems approach #1 is used, where the factor is directly multiplied with the stoploss

        # Adjusted validation based on stoploss implementation in the code
        if self.counter_trend_stoploss_factor >= 1.0:
            logger.warning(
                f"Counter-trend stoploss factor ({self.counter_trend_stoploss_factor}) should be less "
                f"than 1.0 for tighter stoploss. Adjusting to 0.7."
            )
            self.counter_trend_stoploss_factor = 0.7

        if self.aligned_trend_stoploss_factor <= 1.0:
            logger.warning(
                f"Aligned-trend stoploss factor ({self.aligned_trend_stoploss_factor}) should be "
                f"greater than 1.0 for looser stoploss. Adjusting to 1.2."
            )
            self.aligned_trend_stoploss_factor = 1.2

        if self.counter_trend_stoploss_factor >= self.aligned_trend_stoploss_factor:
            logger.warning(
                f"Counter-trend stoploss factor ({self.counter_trend_stoploss_factor}) should be "
                f"lower than aligned-trend factor ({self.aligned_trend_stoploss_factor}) "
                f"for tighter stoploss. Adjusting."
            )
            # Set counter-trend to 60% of aligned-trend for tighter stoploss
            self.counter_trend_stoploss_factor = self.aligned_trend_stoploss_factor * 0.6