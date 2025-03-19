import json
import logging
import os
from typing import Dict, Any

logger = logging.getLogger(__name__)


class SimplifiedConfig:
    """
    Simplified configuration for MACD Trend Adaptive Strategy with just 3 parameters per timeframe:
    - risk_reward_ratio: Express as "R:R" (e.g. "1:1.5")
    - min_roi: Minimum ROI target (e.g. 0.02 for 2%)
    - max_roi: Maximum ROI target (e.g. 0.05 for 5%)

    All other parameters are derived from these three inputs.
    """

    def __init__(self, config_path: str = None, timeframe: str = '15m'):
        """
        Initialize with default values or load from config file if provided

        Args:
            config_path: Path to JSON configuration file (optional)
            timeframe: Trading timeframe ('1m', '5m', '15m', '30m', '1h', etc.)
        """
        self.timeframe = timeframe

        # Default configurations for different timeframes
        self.default_configs = {
            # 1-minute default
            '1m': {
                'risk_reward_ratio': "1:1.5",
                'min_roi': 0.015,
                'max_roi': 0.035
            },
            # 5-minute default
            '5m': {
                'risk_reward_ratio': "1:2",
                'min_roi': 0.02,
                'max_roi': 0.045
            },
            # 15-minute default (standard)
            '15m': {
                'risk_reward_ratio': "1:2",
                'min_roi': 0.025,
                'max_roi': 0.055
            },
            # 30-minute default
            '30m': {
                'risk_reward_ratio': "1:2.5",
                'min_roi': 0.03,
                'max_roi': 0.065
            },
            # 1-hour default
            '1h': {
                'risk_reward_ratio': "1:3",
                'min_roi': 0.035,
                'max_roi': 0.075
            }
        }

        # Set current timeframe's default values
        if timeframe in self.default_configs:
            self.risk_reward_ratio_str = self.default_configs[timeframe]['risk_reward_ratio']
            self.min_roi = self.default_configs[timeframe]['min_roi']
            self.max_roi = self.default_configs[timeframe]['max_roi']
        else:
            # If timeframe not found, use 15m defaults
            logger.warning(f"No default configuration for timeframe {timeframe}, using 15m defaults")
            self.risk_reward_ratio_str = self.default_configs['15m']['risk_reward_ratio']
            self.min_roi = self.default_configs['15m']['min_roi']
            self.max_roi = self.default_configs['15m']['max_roi']

        # Load from file if provided, which may override the defaults
        if config_path and os.path.exists(config_path):
            self._load_from_file(config_path)

        # Parse risk:reward ratio string to numeric value
        self.risk_reward_ratio = self._parse_risk_reward(self.risk_reward_ratio_str)

        # Calculate derived parameters
        self._calculate_derived_parameters()

    def _load_from_file(self, config_path: str) -> None:
        """Load configuration from JSON file with support for timeframe-specific settings"""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)

            # First check if there's a timeframe-specific section
            if self.timeframe in config:
                timeframe_config = config[self.timeframe]
                logger.info(f"Found specific configuration for timeframe {self.timeframe}")

                # Load the three configurable parameters
                if 'risk_reward_ratio' in timeframe_config:
                    self.risk_reward_ratio_str = timeframe_config['risk_reward_ratio']
                if 'min_roi' in timeframe_config:
                    self.min_roi = float(timeframe_config['min_roi'])
                if 'max_roi' in timeframe_config:
                    self.max_roi = float(timeframe_config['max_roi'])

            # If no timeframe-specific section, check for global settings
            else:
                # For backward compatibility, check for top-level parameters
                if 'risk_reward_ratio' in config:
                    self.risk_reward_ratio_str = config['risk_reward_ratio']
                if 'min_roi' in config:
                    self.min_roi = float(config['min_roi'])
                if 'max_roi' in config:
                    self.max_roi = float(config['max_roi'])

            logger.info(f"Loaded configuration for {self.timeframe}: "
                        f"R:R ratio: {self.risk_reward_ratio_str}, "
                        f"Min ROI: {self.min_roi}, Max ROI: {self.max_roi}")

        except Exception as e:
            logger.error(f"Error loading configuration from {config_path}: {e}")
            logger.info(f"Using default configuration values for timeframe {self.timeframe}")

    def _parse_risk_reward(self, risk_reward_str: str) -> float:
        """
        Parse risk:reward ratio string (e.g. "1:1.5") to numeric value

        Returns:
            float: Risk/Reward as a decimal (e.g. 0.667 for "1:1.5")
        """
        try:
            risk, reward = risk_reward_str.split(':')
            risk_value = float(risk.strip())
            reward_value = float(reward.strip())

            # Calculate risk/reward ratio as a decimal
            # This is what the strategy code actually uses
            return risk_value / reward_value

        except Exception as e:
            logger.error(f"Error parsing risk:reward ratio '{risk_reward_str}': {e}")
            logger.info("Using default risk:reward ratio of 1:2 (0.5)")
            return 0.5  # Default 1:2

    def _calculate_derived_parameters(self) -> None:
        """Calculate all derived parameters from the three base parameters"""

        # Base ROI is the average of min and max ROI
        self.base_roi = (self.min_roi + self.max_roi) / 2

        # Stoploss calculations based on ROI and risk:reward ratio
        # Stoploss values are negative
        self.min_stoploss = -1 * self.min_roi * self.risk_reward_ratio
        self.max_stoploss = -1 * self.max_roi * self.risk_reward_ratio

        # Static stoploss is based on base ROI
        self.static_stoploss = -1 * self.base_roi * self.risk_reward_ratio

        # Fixed values for simplified configuration
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
        self.default_roi = 1.0  # Very high, effectively disabled
        self.long_roi_boost = 0.0  # Disabled
        self.use_default_roi_exit = False
        self.use_dynamic_stoploss = True

    def get_config_summary(self) -> str:
        """Get a summary of the configuration for logging"""
        return (
            f"Simplified Configuration for {self.timeframe}:\n"
            f"- R:R ratio: {self.risk_reward_ratio_str} ({self.risk_reward_ratio:.3f})\n"
            f"- Min ROI: {self.min_roi:.2%}\n"
            f"- Max ROI: {self.max_roi:.2%}\n"
            f"- Base ROI: {self.base_roi:.2%}\n"
            f"- Min Stoploss: {self.min_stoploss:.2%}\n"
            f"- Max Stoploss: {self.max_stoploss:.2%}\n"
            f"- Static Stoploss: {self.static_stoploss:.2%}\n"
        )

    @staticmethod
    def get_sample_config() -> Dict[str, Any]:
        """
        Returns a sample configuration with settings for all timeframes
        to help users create their own configuration file
        """
        return {
            "1m": {
                "risk_reward_ratio": "1:1.5",
                "min_roi": 0.015,
                "max_roi": 0.035
            },
            "5m": {
                "risk_reward_ratio": "1:2",
                "min_roi": 0.02,
                "max_roi": 0.045
            },
            "15m": {
                "risk_reward_ratio": "1:2",
                "min_roi": 0.025,
                "max_roi": 0.055
            },
            "30m": {
                "risk_reward_ratio": "1:2.5",
                "min_roi": 0.03,
                "max_roi": 0.065
            },
            "1h": {
                "risk_reward_ratio": "1:3",
                "min_roi": 0.035,
                "max_roi": 0.075
            }
        }

    def save_sample_config(self, config_path: str) -> None:
        """Save a sample configuration file with all timeframes"""
        try:
            with open(config_path, 'w') as f:
                json.dump(self.get_sample_config(), f, indent=4)
            logger.info(f"Sample configuration saved to {config_path}")
        except Exception as e:
            logger.error(f"Error saving sample configuration to {config_path}: {e}")
