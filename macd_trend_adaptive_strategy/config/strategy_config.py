import json
import logging
import os
from enum import Enum
from typing import Dict, Any

from macd_trend_adaptive_strategy.config.config_validator import ConfigValidator

logger = logging.getLogger(__name__)


class StrategyMode(str, Enum):
    """
    Strategy modes that determine the timeframe and associated indicator settings
    """
    DEFAULT = "default"  # Default configuration (15m timeframe)
    TIMEFRAME_1M = "1m"  # Optimized for 1-minute timeframe
    TIMEFRAME_5M = "5m"  # Optimized for 5-minute timeframe
    TIMEFRAME_15M = "15m"  # Optimized for 15-minute timeframe (same as DEFAULT)
    TIMEFRAME_30M = "30m"  # Optimized for 30-minute timeframe
    TIMEFRAME_1H = "1h"  # Optimized for 1-hour timeframe


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

    # Default configurations for different timeframes
    DEFAULT_TIMEFRAME_CONFIGS = {
        # 1-minute default
        '1m': {
            'risk_reward_ratio': "1:1.5",
            'min_roi': 0.015,
            'max_roi': 0.035,
            # MACD parameters
            'fast_length': 6,
            'slow_length': 14,
            'signal_length': 4,
            # Trend detection parameters
            'adx_period': 8,
            'adx_threshold': 15,
            'ema_fast': 3,
            'ema_slow': 10,
            # Other settings
            'startup_candle_count': 20,
            'roi_cache_update_interval': 15,
        },
        # 5-minute default
        '5m': {
            'risk_reward_ratio': "1:2",
            'min_roi': 0.02,
            'max_roi': 0.045,
            # MACD parameters
            'fast_length': 8,
            'slow_length': 21,
            'signal_length': 6,
            # Trend detection parameters
            'adx_period': 10,
            'adx_threshold': 18,
            'ema_fast': 5,
            'ema_slow': 15,
            # Other settings
            'startup_candle_count': 25,
            'roi_cache_update_interval': 30,
        },
        # 15-minute default (standard)
        '15m': {
            'risk_reward_ratio': "1:2",
            'min_roi': 0.025,
            'max_roi': 0.055,
            # MACD parameters
            'fast_length': 12,
            'slow_length': 26,
            'signal_length': 9,
            # Trend detection parameters
            'adx_period': 14,
            'adx_threshold': 20,
            'ema_fast': 8,
            'ema_slow': 21,
            # Other settings
            'startup_candle_count': 30,
            'roi_cache_update_interval': 60,
        },
        # 30-minute default
        '30m': {
            'risk_reward_ratio': "1:2.5",
            'min_roi': 0.03,
            'max_roi': 0.065,
            # MACD parameters
            'fast_length': 14,
            'slow_length': 30,
            'signal_length': 10,
            # Trend detection parameters
            'adx_period': 18,
            'adx_threshold': 22,
            'ema_fast': 10,
            'ema_slow': 26,
            # Other settings
            'startup_candle_count': 35,
            'roi_cache_update_interval': 120,
        },
        # 1-hour default
        '1h': {
            'risk_reward_ratio': "1:3",
            'min_roi': 0.035,
            'max_roi': 0.075,
            # MACD parameters
            'fast_length': 16,
            'slow_length': 32,
            'signal_length': 12,
            # Trend detection parameters
            'adx_period': 20,
            'adx_threshold': 25,
            'ema_fast': 12,
            'ema_slow': 34,
            # Other settings
            'startup_candle_count': 40,
            'roi_cache_update_interval': 300,
        }
    }

    def __init__(self, mode: StrategyMode = StrategyMode.DEFAULT, config_path: str = None):
        # Determine the timeframe based on selected mode
        self.timeframe = self._get_timeframe_from_mode(mode)

        # Load default config for this timeframe
        self._load_default_config(self.timeframe)

        # Override with user config if provided
        if config_path:
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

    def _get_timeframe_from_mode(self, mode: StrategyMode) -> str:
        """Convert strategy mode to timeframe string"""
        if mode == StrategyMode.DEFAULT or mode == StrategyMode.TIMEFRAME_15M:
            return '15m'
        elif mode == StrategyMode.TIMEFRAME_1M:
            return '1m'
        elif mode == StrategyMode.TIMEFRAME_5M:
            return '5m'
        elif mode == StrategyMode.TIMEFRAME_30M:
            return '30m'
        elif mode == StrategyMode.TIMEFRAME_1H:
            return '1h'
        else:
            logger.warning(f"Unknown mode {mode}, defaulting to 15m")
            return '15m'

    def _load_default_config(self, timeframe: str) -> None:
        """
        Load default configuration for the specified timeframe

        Args:
            timeframe: Trading timeframe ('1m', '5m', '15m', '30m', '1h')
        """
        if timeframe not in self.DEFAULT_TIMEFRAME_CONFIGS:
            logger.warning(f"No default configuration for timeframe {timeframe}, using 15m defaults")
            timeframe = '15m'

        config = self.DEFAULT_TIMEFRAME_CONFIGS[timeframe]

        # Load all configuration parameters
        for key, value in config.items():
            setattr(self, key, value)

        # Store the timeframe
        self.timeframe = timeframe

    def _load_user_config(self, config_path: str) -> None:
        """
        Load user configuration from JSON file with support for timeframe-specific settings

        Args:
            config_path: Path to JSON configuration file
        """
        if not os.path.exists(config_path):
            logger.warning(f"Configuration file {config_path} not found, using defaults")
            return

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
            elif any(key for key in config if key not in self.DEFAULT_TIMEFRAME_CONFIGS):
                # For backward compatibility, check for top-level parameters
                for key, value in config.items():
                    if key not in self.DEFAULT_TIMEFRAME_CONFIGS:  # Skip timeframe sections
                        self._set_config_value(key, value)

            logger.info(f"Loaded user configuration for {self.timeframe}")

        except Exception as e:
            logger.error(f"Error loading configuration from {config_path}: {e}")
            logger.info(f"Using default configuration values for timeframe {self.timeframe}")

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
        """Parse risk:reward ratio string (e.g. "1:1.5") to numeric value"""
        try:
            risk, reward = self.risk_reward_ratio.split(':')
            risk_value = float(risk.strip())
            reward_value = float(reward.strip())

            # Calculate risk/reward ratio as a decimal
            # Store both the string and float versions
            self.risk_reward_ratio_str = self.risk_reward_ratio  # Save the original string
            self.risk_reward_ratio_float = risk_value / reward_value

        except Exception as e:
            logger.error(f"Error parsing risk:reward ratio '{self.risk_reward_ratio}': {e}")
            logger.info("Using default risk:reward ratio of 1:2 (0.5)")
            self.risk_reward_ratio_float = 0.5  # Default 1:2

    def _calculate_derived_parameters(self) -> None:
        """Calculate all derived parameters from the base parameters"""

        # Base ROI is the average of min and max ROI
        self.base_roi = (self.min_roi + self.max_roi) / 2

        # Stoploss calculations based on ROI and risk:reward ratio
        # Stoploss values are negative
        self.min_stoploss = -1 * self.min_roi * self.risk_reward_ratio_float
        self.max_stoploss = -1 * self.max_roi * self.risk_reward_ratio_float

        # Static stoploss is based on base ROI
        self.static_stoploss = -1 * self.base_roi * self.risk_reward_ratio_float

        # Store risk_reward_ratio as float in the traditional attribute name for compatibility
        self.risk_reward_ratio = self.risk_reward_ratio_float

        # Set default values for parameters not in the config file
        self._set_default_values()


    def _set_default_values(self) -> None:
        """Set default values for parameters not in the configuration file"""

        # Risk factor settings with defaults
        if not hasattr(self, 'counter_trend_factor'):
            self.counter_trend_factor = 0.5
        if not hasattr(self, 'aligned_trend_factor'):
            self.aligned_trend_factor = 1.0
        if not hasattr(self, 'counter_trend_stoploss_factor'):
            self.counter_trend_stoploss_factor = 0.5
        if not hasattr(self, 'aligned_trend_stoploss_factor'):
            self.aligned_trend_stoploss_factor = 1.0

        # Win rate settings
        if not hasattr(self, 'min_win_rate'):
            self.min_win_rate = 0.2
        if not hasattr(self, 'max_win_rate'):
            self.max_win_rate = 0.8
        if not hasattr(self, 'regime_win_rate_diff'):
            self.regime_win_rate_diff = 0.2
        if not hasattr(self, 'min_recent_trades_per_direction'):
            self.min_recent_trades_per_direction = 5
        if not hasattr(self, 'max_recent_trades'):
            self.max_recent_trades = 10

        # Other settings
        if not hasattr(self, 'long_roi_boost'):
            self.long_roi_boost = 0.0
        if not hasattr(self, 'use_dynamic_stoploss'):
            self.use_dynamic_stoploss = True

        # Default exits
        if not hasattr(self, 'use_default_roi_exit'):
            self.use_default_roi_exit = False
        if not hasattr(self, 'use_default_stoploss_exit'):
            self.use_default_stoploss_exit = False
        if not hasattr(self, 'default_roi'):
            self.default_roi = 0.04
        if not hasattr(self, 'default_stoploss'):
            self.default_stoploss = -0.04


    def get_config_summary(self) -> str:
        """Get a summary of the configuration for logging"""
        return (
            f"Strategy Configuration for {self.timeframe}:\n"
            f"- R:R ratio: {self.risk_reward_ratio_str} ({self.risk_reward_ratio:.3f})\n"
            f"- ROI: Min={self.min_roi:.2%}, Max={self.max_roi:.2%}, Base={self.base_roi:.2%}\n"
            f"- Stoploss: Min={self.min_stoploss:.2%}, Max={self.max_stoploss:.2%}, Static={self.static_stoploss:.2%}\n"
            f"- MACD: Fast={self.fast_length}, Slow={self.slow_length}, Signal={self.signal_length}\n"
            f"- Trend: ADX Period={self.adx_period}, Threshold={self.adx_threshold}, EMA Fast={self.ema_fast}, EMA Slow={self.ema_slow}\n"
            f"- Factors: Counter={self.counter_trend_factor:.2f}, Aligned={self.aligned_trend_factor:.2f}, "
            f"Counter SL={self.counter_trend_stoploss_factor:.2f}, Aligned SL={self.aligned_trend_stoploss_factor:.2f}\n"
        )


    @staticmethod
    def generate_sample_config() -> Dict[str, Any]:
        """
        Generate a sample configuration file with settings for all timeframes

        Returns:
            dict: Sample configuration dictionary
        """
        # Start with the default timeframe configs
        config = StrategyConfig.DEFAULT_TIMEFRAME_CONFIGS.copy()

        # Only keep the essential parameters for simplicity
        simplified_config = {}
        for timeframe, settings in config.items():
            simplified_config[timeframe] = {
                "risk_reward_ratio": settings["risk_reward_ratio"],
                "min_roi": settings["min_roi"],
                "max_roi": settings["max_roi"],
                # Add optional indicator parameters
                "fast_length": settings["fast_length"],
                "slow_length": settings["slow_length"],
                "signal_length": settings["signal_length"],
                "adx_period": settings["adx_period"],
                "adx_threshold": settings["adx_threshold"],
                "ema_fast": settings["ema_fast"],
                "ema_slow": settings["ema_slow"]
            }

        # Add global settings section
        simplified_config["global"] = {
            "counter_trend_factor": 0.5,
            "aligned_trend_factor": 1.0,
            "counter_trend_stoploss_factor": 0.5,
            "aligned_trend_stoploss_factor": 1.0,
            "use_dynamic_stoploss": True
        }

        return simplified_config

    @staticmethod
    def save_sample_config(file_path: str) -> None:
        """
        Save a sample configuration file

        Args:
            file_path: Path to save the configuration file
        """
        try:
            config = StrategyConfig.generate_sample_config()
            with open(file_path, 'w') as f:
                json.dump(config, f, indent=4)
            logger.info(f"Sample configuration saved to {file_path}")
        except Exception as e:
            logger.error(f"Error saving sample configuration to {file_path}: {e}")