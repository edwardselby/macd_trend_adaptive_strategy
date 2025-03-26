import logging
import os
from typing import Dict, Any, List

from .yaml_loader import load_config

logger = logging.getLogger(__name__)


class ConfigParser:
    """
    Configuration parser for loading, parsing, and validating strategy configuration.
    Handles YAML loading, parameter type validation, and calculation of derived parameters.
    """

    # Define required parameters and their expected types
    PARAMETER_SCHEMA = {
        # Format: 'parameter_name': (expected_type, description)
        # Risk parameters
        'risk_reward_ratio': (str, "Risk to reward ratio (e.g. '1:2')"),
        'min_stoploss': (float, "Minimum stoploss value (closer to zero, tighter)"),
        'max_stoploss': (float, "Maximum stoploss value (further from zero, wider)"),

        # MACD parameters
        'fast_length': (int, "Fast EMA period for MACD"),
        'slow_length': (int, "Slow EMA period for MACD"),
        'signal_length': (int, "Signal line period for MACD"),

        # Trend detection parameters
        'adx_threshold': ((str, int, float), "ADX threshold for trend detection"),
        'ema_fast': (int, "Fast EMA period for trend detection"),
        'ema_slow': (int, "Slow EMA period for trend detection"),

        # Risk management factors
        'counter_trend_factor': (float, "Factor applied to ROI for counter-trend trades"),
        'aligned_trend_factor': (float, "Factor applied to ROI for trend-aligned trades"),
        'counter_trend_stoploss_factor': (float, "Factor applied to stoploss for counter-trend trades"),
        'aligned_trend_stoploss_factor': (float, "Factor applied to stoploss for trend-aligned trades"),
    }

    # Optional parameters with their types
    OPTIONAL_PARAMETERS = {
        'adx_period': (int, "ADX period (default: 14)"),
        'static_stoploss': (float, "Fallback stoploss value"),
        'default_roi': (float, "Fallback ROI value"),
        'use_dynamic_stoploss': (bool, "Whether to use dynamic stoploss"),
        'min_win_rate': (float, "Minimum win rate for ROI normalization"),
        'max_win_rate': (float, "Maximum win rate for ROI normalization"),
        'regime_win_rate_diff': (float, "Win rate difference for market regime detection"),
        'min_recent_trades_per_direction': (int, "Minimum trades needed for market regime detection"),
        'max_recent_trades': (int, "Maximum number of recent trades to track"),
        'startup_candle_count': (int, "Number of warmup candles required"),
        'roi_cache_update_interval': (int, "Seconds between ROI cache updates"),
    }

    # ADX strength constants for converting string to numeric values
    ADX_STRENGTH = {
        "weak": 25,  # Minimum trend requirement
        "normal": 50,  # Medium trend strength
        "strong": 75,  # Strong trend strength
        "extreme": 90  # Maximum trend strength
    }

    @classmethod
    def load_config(cls, config_path: str, timeframe: str) -> Dict[str, Any]:
        """
        Load and validate configuration from YAML file

        Args:
            config_path: Path to YAML configuration file
            timeframe: Timeframe to load configuration for (e.g. '1m', '5m', '15m')

        Returns:
            Dict containing configuration parameters

        Raises:
            ValueError: If configuration is invalid or missing required parameters
        """
        # Check if file exists
        if not os.path.exists(config_path):
            raise ValueError(f"Configuration file not found: {config_path}")

        # Load YAML config
        try:
            config_data = load_config(config_path)
        except Exception as e:
            raise ValueError(f"Failed to load configuration from {config_path}: {e}")

        # Get timeframe configuration
        timeframe_config = {}

        # First check if there's a timeframe-specific section
        if timeframe in config_data:
            timeframe_config.update(config_data[timeframe])
            logger.info(f"Loaded specific configuration for timeframe {timeframe}")

        # Then check for global settings
        if "global" in config_data:
            # Only update keys that don't already exist
            for key, value in config_data["global"].items():
                if key not in timeframe_config:
                    timeframe_config[key] = value
            logger.info("Applied global configuration settings")

        # Validate required parameters
        errors = cls.validate_config(timeframe_config)

        if errors:
            error_message = f"Configuration errors for timeframe {timeframe}:\n" + "\n".join(errors)
            raise ValueError(error_message)

        # Process string-based adx_threshold
        processed_config = cls._process_adx_threshold(timeframe_config)

        # Parse risk-reward ratio and calculate derived parameters
        parsed_config = cls._parse_risk_reward_ratio(processed_config)
        final_config = cls._calculate_derived_parameters(parsed_config)

        return final_config

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> List[str]:
        """
        Validate configuration parameters against schema

        Args:
            config: Configuration dictionary to validate

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Check required parameters
        for param_name, (param_type, description) in cls.PARAMETER_SCHEMA.items():
            if param_name not in config:
                errors.append(f"Missing required parameter: {param_name} - {description}")
                continue

            # Check parameter type
            value = config[param_name]
            if not cls._validate_type(value, param_type):
                if isinstance(param_type, tuple):
                    type_names = [t.__name__ for t in param_type]
                    errors.append(
                        f"Parameter {param_name} has incorrect type: expected one of {type_names}, got {type(value).__name__}")
                else:
                    errors.append(
                        f"Parameter {param_name} has incorrect type: expected {param_type.__name__}, got {type(value).__name__}")

        # Check optional parameters if present
        for param_name, (param_type, _) in cls.OPTIONAL_PARAMETERS.items():
            if param_name in config:
                value = config[param_name]
                if not cls._validate_type(value, param_type):
                    if isinstance(param_type, tuple):
                        type_names = [t.__name__ for t in param_type]
                        errors.append(
                            f"Parameter {param_name} has incorrect type: expected one of {type_names}, got {type(value).__name__}")
                    else:
                        errors.append(
                            f"Parameter {param_name} has incorrect type: expected {param_type.__name__}, got {type(value).__name__}")

        return errors

    @staticmethod
    def _validate_type(value: Any, expected_type: Any) -> bool:
        """
        Validate that a value matches the expected type

        Args:
            value: Value to validate
            expected_type: Expected type or tuple of types

        Returns:
            True if type is valid, False otherwise
        """
        if isinstance(expected_type, tuple):
            return any(isinstance(value, t) for t in expected_type)
        return isinstance(value, expected_type)

    @classmethod
    def _process_adx_threshold(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process string-based ADX threshold values

        Args:
            config: Configuration dictionary

        Returns:
            Updated configuration with processed ADX values
        """
        result = config.copy()

        # Process ADX threshold if it's a string
        if 'adx_threshold' in result and isinstance(result['adx_threshold'], str):
            adx_str = result['adx_threshold'].lower()

            # Store original string value
            result['adx_threshold_str'] = adx_str

            # Convert to numeric value
            if adx_str in cls.ADX_STRENGTH:
                result['adx_threshold'] = cls.ADX_STRENGTH[adx_str]
            else:
                # Invalid string value, log warning and use Normal
                logger.warning(f"Invalid ADX threshold '{adx_str}', using 'normal' (50)")
                result['adx_threshold'] = cls.ADX_STRENGTH['normal']
                result['adx_threshold_str'] = 'normal'

        return result

    @staticmethod
    def _parse_risk_reward_ratio(config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse risk:reward ratio string (e.g. "1:2") to numeric value

        Args:
            config: Configuration dictionary

        Returns:
            Updated configuration dictionary with parsed values
        """
        result = config.copy()

        try:
            risk_reward_str = config['risk_reward_ratio']
            risk, reward = risk_reward_str.split(':')
            risk_value = float(risk.strip())
            reward_value = float(reward.strip())

            # Store the original string
            result['risk_reward_ratio_str'] = risk_reward_str

            # Calculate risk/reward ratio as a decimal
            # INVERTED: Now reward to risk (used to multiply stoploss to get ROI)
            result['risk_reward_ratio_float'] = reward_value / risk_value

        except Exception as e:
            logger.error(f"Error parsing risk:reward ratio '{config.get('risk_reward_ratio', 'unknown')}': {e}")
            logger.info("Using default risk:reward ratio of 1:2 (2.0)")
            result['risk_reward_ratio_float'] = 2.0  # Default 1:2 but inverted
            result['risk_reward_ratio_str'] = "1:2"

        return result

    @staticmethod
    def _calculate_derived_parameters(config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate derived parameters from base configuration

        Args:
            config: Configuration dictionary with base parameters

        Returns:
            Updated configuration with derived parameters
        """
        result = config.copy()

        # Store risk_reward_ratio as float in the traditional attribute for compatibility
        result['risk_reward_ratio'] = result['risk_reward_ratio_float']

        # Ensure stoploss values are properly ordered (min should be less negative than max)
        if result['min_stoploss'] < result['max_stoploss']:
            # Swap them if they're reversed
            result['min_stoploss'], result['max_stoploss'] = result['max_stoploss'], result['min_stoploss']
            logger.warning("Swapped min_stoploss and max_stoploss to maintain correct ordering")

        # Base stoploss is the average
        result['base_stoploss'] = (result['min_stoploss'] + result['max_stoploss']) / 2

        # Calculate ROI values based on stoploss and risk:reward ratio
        # Stoploss values are negative, so we take the absolute value
        result['min_roi'] = abs(result['min_stoploss']) * result['risk_reward_ratio_float']
        result['max_roi'] = abs(result['max_stoploss']) * result['risk_reward_ratio_float']
        result['base_roi'] = (result['min_roi'] + result['max_roi']) / 2

        # For backward compatibility with existing code
        # Make static_stoploss more negative than max_stoploss (20% more negative)
        if 'static_stoploss' not in result:
            result['static_stoploss'] = result['max_stoploss'] * 1.2

        # Make default_roi higher than max_roi (20% higher)
        if 'default_roi' not in result:
            result['default_roi'] = result['max_roi'] * 1.2

        return result