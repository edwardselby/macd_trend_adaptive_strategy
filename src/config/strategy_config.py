import json
import logging
import os
from enum import Enum
from typing import Any

from .config_validator import ConfigValidator

logger = logging.getLogger(__name__)


class StrategyMode(str, Enum):
    """Strategy modes that directly use timeframe strings as values"""
    DEFAULT = "15m"  # Default is 15m
    TIMEFRAME_1M = "1m"
    TIMEFRAME_5M = "5m"
    TIMEFRAME_15M = "15m"
    TIMEFRAME_30M = "30m"
    TIMEFRAME_1H = "1h"
    AUTO = "auto"


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

    def __init__(self, mode: 'StrategyMode' = None, config_path: str = None, freqtrade_config: dict = None):
        """
        Initialize strategy configuration

        Args:
            mode: Strategy mode (timeframe) to use
            config_path: Path to config JSON file
            freqtrade_config: FreqTrade configuration for auto-detection
        """
        # Determine which timeframe to use
        if mode is not None and mode != StrategyMode.AUTO:
            # Use explicitly provided mode
            self.timeframe = mode.value
        elif freqtrade_config is not None:
            # Auto-detect from FreqTrade config
            self.timeframe = freqtrade_config.get('timeframe', '15m')
            logger.info(f"Auto-detected timeframe: {self.timeframe}")
        else:
            # Default to 15m
            self.timeframe = StrategyMode.DEFAULT.value

        # Configuration file is required
        if not config_path or not os.path.exists(config_path):
            raise ValueError(
                f"Configuration file not found: {config_path}. A configuration file is required to use this strategy.")

        # Initialize placeholder attributes
        self._initialize_placeholder_attributes()

        # Load configuration
        self._load_user_config(config_path)

        # Validate and fix configuration
        errors, fixes = ConfigValidator.validate_and_fix(self)

        if errors:
            logger.warning(f"Configuration validation errors: {errors}")
        if fixes:
            logger.info(f"Configuration fixes applied: {fixes}")

        # Parse risk:reward ratio and calculate derived parameters
        self._parse_risk_reward_ratio()
        self._calculate_derived_parameters()

        # Log configuration summary
        logger.info(self.get_config_summary())

    def _initialize_placeholder_attributes(self):
        """Initialize placeholder attributes to avoid attribute errors"""
        # Risk factor settings with defaults
        self.counter_trend_factor = 0.5
        self.aligned_trend_factor = 1.0
        self.counter_trend_stoploss_factor = 0.5
        self.aligned_trend_stoploss_factor = 1.0

        # Win rate settings
        self.min_win_rate = 0.2
        self.max_win_rate = 0.8
        self.regime_win_rate_diff = 0.2
        self.min_recent_trades_per_direction = 5
        self.max_recent_trades = 10

        # Other settings
        self.use_dynamic_stoploss = True
        self.startup_candle_count = 30
        self.roi_cache_update_interval = 60

        # Core settings - these will be overridden by config
        self.risk_reward_ratio = "1:2"
        self.risk_reward_ratio_str = "1:2"
        # Invert the primary parameters to be stoploss first
        self.min_stoploss = -0.015  # Less negative, tighter stoploss
        self.max_stoploss = -0.03  # More negative, wider stoploss

    def _load_user_config(self, config_path: str) -> bool:
        """
        Load user configuration from JSON file with support for timeframe-specific settings

        Args:
            config_path: Path to JSON configuration file

        Returns:
            bool: True if configuration was loaded successfully
        """
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)

            # First check if there's a timeframe-specific section
            if self.timeframe in config:
                timeframe_config = config[self.timeframe]
                logger.info(f"Found specific configuration for timeframe {self.timeframe}")

                # Load all parameters from the timeframe section
                for key, value in timeframe_config.items():
                    self._set_config_value(key, value)

            # Check for global settings and apply them
            if "global" in config:
                global_config = config["global"]
                logger.info(f"Found global configuration settings")

                # Load all parameters from the global section
                for key, value in global_config.items():
                    self._set_config_value(key, value)

            # If no timeframe-specific or global section, check for top-level parameters
            elif any(key for key in config if key not in ['1m', '5m', '15m', '30m', '1h', 'global']):
                # For backward compatibility, check for top-level parameters
                for key, value in config.items():
                    if key not in ['1m', '5m', '15m', '30m', '1h', 'global']:
                        self._set_config_value(key, value)

            logger.info(f"Loaded user configuration for {self.timeframe}")
            return True

        except Exception as e:
            logger.error(f"Error loading configuration from {config_path}: {e}")
            raise ValueError(f"Failed to load configuration from {config_path}: {e}")

    def _set_config_value(self, key: str, value: Any) -> None:
        """
        Set a configuration value with appropriate type conversion

        Args:
            key: Configuration parameter name
            value: Parameter value from config file
        """
        try:
            # Convert numeric values to float if needed
            if key in ['min_roi', 'max_roi', 'adx_threshold']:
                value = float(value)
            elif key in ['fast_length', 'slow_length', 'signal_length',
                         'adx_period', 'ema_fast', 'ema_slow',
                         'startup_candle_count', 'roi_cache_update_interval']:
                value = int(value)

            # Set the attribute
            setattr(self, key, value)
            logger.debug(f"Set configuration parameter {key} = {value}")

        except Exception as e:
            logger.error(f"Error setting configuration parameter {key}: {e}")

    def _parse_risk_reward_ratio(self) -> None:
        """Parse risk:reward ratio string (e.g. "1:2") to numeric value"""
        try:
            risk, reward = self.risk_reward_ratio.split(':')
            risk_value = float(risk.strip())
            reward_value = float(reward.strip())

            # Store the original string
            self.risk_reward_ratio_str = self.risk_reward_ratio

            # Calculate risk/reward ratio as a decimal
            # INVERTED: Now reward to risk (this will be used to multiply stoploss to get ROI)
            self.risk_reward_ratio_float = reward_value / risk_value

        except Exception as e:
            logger.error(f"Error parsing risk:reward ratio '{self.risk_reward_ratio}': {e}")
            logger.info("Using default risk:reward ratio of 1:2 (2.0)")
            self.risk_reward_ratio_float = 2.0  # Default 1:2 but inverted

    def _calculate_derived_parameters(self) -> None:
        """Calculate all derived parameters from the base parameters"""
        # Store risk_reward_ratio as float in the traditional attribute for compatibility
        self.risk_reward_ratio = self.risk_reward_ratio_float

        # Ensure stoploss values are properly ordered (min should be less negative than max)
        if self.min_stoploss < self.max_stoploss:
            # Swap them if they're reversed
            self.min_stoploss, self.max_stoploss = self.max_stoploss, self.min_stoploss
            logger.warning("Swapped min_stoploss and max_stoploss to maintain correct ordering")

        # Base stoploss is the average
        self.base_stoploss = (self.min_stoploss + self.max_stoploss) / 2

        # Calculate ROI values based on stoploss and risk:reward ratio
        # Stoploss values are negative, so we take the absolute value
        self.min_roi = abs(self.min_stoploss) * self.risk_reward_ratio_float
        self.max_roi = abs(self.max_stoploss) * self.risk_reward_ratio_float
        self.base_roi = (self.min_roi + self.max_roi) / 2

        # For backward compatibility with existing code
        # Make static_stoploss more negative than max_stoploss (20% more negative)
        if not hasattr(self, 'static_stoploss'):
            self.static_stoploss = self.max_stoploss * 1.2

        # Make default_roi higher than max_roi (20% higher)
        if not hasattr(self, 'default_roi'):
            self.default_roi = self.max_roi * 1.2

    def get_config_summary(self) -> str:
        """Get a summary of the configuration for logging"""
        return (
            f"Strategy Configuration for {self.timeframe}:\n"
            f"- R:R ratio: {self.risk_reward_ratio_str} ({self.risk_reward_ratio:.3f})\n"
            f"- ROI: Min={self.min_roi:.2%}, Max={self.max_roi:.2%}, Base={self.base_roi:.2%}\n"
            f"- Stoploss: Min={self.min_stoploss:.2%}, Max={self.max_stoploss:.2%}\n"
            f"- MACD: Fast={self.fast_length}, Slow={self.slow_length}, Signal={self.signal_length}\n"
            f"- Trend: ADX Period={self.adx_period}, Threshold={self.adx_threshold}, EMA Fast={self.ema_fast}, EMA Slow={self.ema_slow}\n"
            f"- Factors: Counter={self.counter_trend_factor:.2f}, Aligned={self.aligned_trend_factor:.2f}, "
            f"Counter SL={self.counter_trend_stoploss_factor:.2f}, Aligned SL={self.aligned_trend_stoploss_factor:.2f}\n"
        )