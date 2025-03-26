import logging
from enum import Enum

from .config_parser import ConfigParser

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
    Container for strategy configuration values loaded from YAML files.
    This class simply holds the values parsed by ConfigParser.
    """

    def __init__(self, mode: 'StrategyMode' = None, config_path: str = None, freqtrade_config: dict = None):
        """
        Initialize strategy configuration

        Args:
            mode: Strategy mode (timeframe) to use
            config_path: Path to config YAML file
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

        # Load the configuration using the ConfigParser
        # ConfigParser will raise ValueError if the file doesn't exist or has validation errors
        config_values = ConfigParser.load_config(config_path, self.timeframe)

        # Set all configuration values as attributes of this object
        for key, value in config_values.items():
            setattr(self, key, value)

        # Log configuration summary
        logger.info(self.get_config_summary())

    def get_config_summary(self) -> str:
        """Get a summary of the configuration for logging"""

        # Helper function to get ADX description
        def get_adx_description():
            if not hasattr(self, 'adx_threshold'):
                return "Unknown"

            # Use stored string value if available
            if hasattr(self, 'adx_threshold_str'):
                adx_str = self.adx_threshold_str.capitalize()
                adx_value = self.adx_threshold
                return f"{adx_str} ({adx_value})"

            # Otherwise determine description from numeric value
            adx_value = self.adx_threshold
            if adx_value <= 25:
                return f"Weak ({adx_value})"
            elif adx_value <= 50:
                return f"Normal ({adx_value})"
            elif adx_value <= 75:
                return f"Strong ({adx_value})"
            else:
                return f"Extreme ({adx_value})"

        # Build the configuration summary
        return (
            f"Strategy Configuration for {self.timeframe}:\n"
            f"- R:R ratio: {self.risk_reward_ratio_str} ({self.risk_reward_ratio:.3f})\n"
            f"- ROI: Min={self.min_roi:.2%}, Max={self.max_roi:.2%}, Base={self.base_roi:.2%}\n"
            f"- Stoploss: Min={self.min_stoploss:.2%}, Max={self.max_stoploss:.2%}\n"
            f"- MACD: Fast={self.fast_length}, Slow={self.slow_length}, Signal={self.signal_length}\n"
            f"- Trend: ADX Threshold={get_adx_description()}, EMA Fast={self.ema_fast}, EMA Slow={self.ema_slow}\n"
            f"- Factors: Counter={self.counter_trend_factor:.2f}, Aligned={self.aligned_trend_factor:.2f}, "
            f"Counter SL={self.counter_trend_stoploss_factor:.2f}, Aligned SL={self.aligned_trend_stoploss_factor:.2f}\n"
        )