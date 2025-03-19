import logging
from typing import Any, Dict, List, Tuple, Union, Optional

logger = logging.getLogger(__name__)


class ConfigValidator:
    """
    Validation system for strategy configuration parameters.
    Ensures all required parameters are present and have appropriate values.
    """

    # Parameter definitions with types and validation constraints
    PARAMETER_DEFINITIONS = {
        # Format: 'parameter_name': (type, required, min_value, max_value, default)
        # Core parameters
        'timeframe': (str, True, None, None, '15m'),
        'risk_reward_ratio_str': (str, True, None, None, '1:2'),
        'risk_reward_ratio': (float, True, 0.1, 2.0, 0.5),
        'min_roi': (float, True, 0.005, 0.2, 0.025),
        'max_roi': (float, True, 0.01, 0.3, 0.055),

        # MACD parameters
        'fast_length': (int, True, 2, 50, 12),
        'slow_length': (int, True, 5, 100, 26),
        'signal_length': (int, True, 2, 20, 9),

        # Trend detection parameters
        'adx_period': (int, True, 5, 50, 14),
        'adx_threshold': (float, True, 5.0, 50.0, 20.0),
        'ema_fast': (int, True, 2, 50, 8),
        'ema_slow': (int, True, 5, 100, 21),

        # Risk management factors
        'counter_trend_factor': (float, True, 0.1, 1.0, 0.5),
        'aligned_trend_factor': (float, True, 0.5, 2.0, 1.0),
        'counter_trend_stoploss_factor': (float, True, 0.1, 1.0, 0.5),
        'aligned_trend_stoploss_factor': (float, True, 0.5, 2.0, 1.0),

        # Other parameters
        'use_dynamic_stoploss': (bool, True, None, None, True),
        'use_default_roi_exit': (bool, False, None, None, False),
        'default_roi': (float, False, 0.01, 0.1, 0.04),
        'long_roi_boost': (float, False, 0.0, 0.05, 0.0),
        'min_win_rate': (float, True, 0.1, 0.5, 0.2),
        'max_win_rate': (float, True, 0.5, 0.9, 0.8),
        'regime_win_rate_diff': (float, True, 0.05, 0.5, 0.2),
        'min_recent_trades_per_direction': (int, True, 2, 20, 5),
        'max_recent_trades': (int, True, 5, 100, 10),
        'startup_candle_count': (int, True, 10, 200, 30),
        'roi_cache_update_interval': (int, True, 10, 3600, 60),

        # Derived parameters (calculated, not directly configured)
        'base_roi': (float, False, None, None, None),
        'min_stoploss': (float, False, None, None, None),
        'max_stoploss': (float, False, None, None, None),
        'static_stoploss': (float, False, None, None, None),
    }

    @classmethod
    def validate_config(cls, config_obj: Any) -> List[str]:
        """
        Validate a configuration object against parameter definitions.

        Args:
            config_obj: Configuration object to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Check for missing required parameters
        for param_name, (param_type, required, min_val, max_val, default) in cls.PARAMETER_DEFINITIONS.items():
            if required and not hasattr(config_obj, param_name):
                errors.append(f"Missing required parameter: {param_name}")

        # Check parameter types and value constraints
        for param_name, (param_type, required, min_val, max_val, default) in cls.PARAMETER_DEFINITIONS.items():
            if hasattr(config_obj, param_name):
                value = getattr(config_obj, param_name)

                # Check type
                if value is not None and not isinstance(value, param_type):
                    errors.append(
                        f"Parameter {param_name} has incorrect type: expected {param_type.__name__}, "
                        f"got {type(value).__name__}")

                # Check value constraints for numeric types
                if value is not None and param_type in (int, float) and not cls._check_numeric_constraints(
                        value, min_val, max_val, param_name, errors):
                    # Error already added in _check_numeric_constraints
                    pass

        # Check for logical consistency across parameters
        cls._check_logical_consistency(config_obj, errors)

        return errors

    @staticmethod
    def _check_numeric_constraints(
            value: Union[int, float],
            min_val: Optional[Union[int, float]],
            max_val: Optional[Union[int, float]],
            param_name: str,
            errors: List[str]
    ) -> bool:
        """
        Check if a numeric value is within specified constraints.

        Args:
            value: The value to check
            min_val: Minimum allowed value (None if no minimum)
            max_val: Maximum allowed value (None if no maximum)
            param_name: Parameter name for error messages
            errors: List to append error messages to

        Returns:
            True if valid, False otherwise
        """
        if min_val is not None and value < min_val:
            errors.append(f"Parameter {param_name} value {value} is below minimum {min_val}")
            return False

        if max_val is not None and value > max_val:
            errors.append(f"Parameter {param_name} value {value} is above maximum {max_val}")
            return False

        return True

    @classmethod
    def _check_logical_consistency(cls, config_obj: Any, errors: List[str]) -> None:
        """
        Check logical consistency between related parameters.

        Args:
            config_obj: Configuration object to check
            errors: List to append error messages to
        """
        # Check min_roi < max_roi
        if (hasattr(config_obj, 'min_roi') and hasattr(config_obj, 'max_roi') and
                config_obj.min_roi >= config_obj.max_roi):
            errors.append(
                f"Inconsistent ROI values: min_roi ({config_obj.min_roi}) must be less than "
                f"max_roi ({config_obj.max_roi})")

        # Check fast_length < slow_length for MACD
        if (hasattr(config_obj, 'fast_length') and hasattr(config_obj, 'slow_length') and
                config_obj.fast_length >= config_obj.slow_length):
            errors.append(
                f"Inconsistent MACD parameters: fast_length ({config_obj.fast_length}) must be less than "
                f"slow_length ({config_obj.slow_length})")

        # Check ema_fast < ema_slow for trend detection
        if (hasattr(config_obj, 'ema_fast') and hasattr(config_obj, 'ema_slow') and
                config_obj.ema_fast >= config_obj.ema_slow):
            errors.append(
                f"Inconsistent EMA parameters: ema_fast ({config_obj.ema_fast}) must be less than "
                f"ema_slow ({config_obj.ema_slow})")

        # Check min_win_rate < max_win_rate
        if (hasattr(config_obj, 'min_win_rate') and hasattr(config_obj, 'max_win_rate') and
                config_obj.min_win_rate >= config_obj.max_win_rate):
            errors.append(
                f"Inconsistent win rate parameters: min_win_rate ({config_obj.min_win_rate}) must be less than "
                f"max_win_rate ({config_obj.max_win_rate})")

        # Verify min_recent_trades_per_direction <= max_recent_trades
        if (hasattr(config_obj, 'min_recent_trades_per_direction') and
                hasattr(config_obj, 'max_recent_trades') and
                config_obj.min_recent_trades_per_direction > config_obj.max_recent_trades):
            errors.append(
                f"Inconsistent recent trades parameters: min_recent_trades_per_direction "
                f"({config_obj.min_recent_trades_per_direction}) must be less than or equal to "
                f"max_recent_trades ({config_obj.max_recent_trades})")

    @classmethod
    def validate_and_fix(cls, config_obj: Any) -> Tuple[List[str], List[str]]:
        """
        Validate configuration and attempt to fix issues when possible.

        Args:
            config_obj: Configuration object to validate and fix

        Returns:
            Tuple of (error_messages, fix_messages)
        """
        errors = []
        fixes = []

        # First, validate to collect all errors
        validation_errors = cls.validate_config(config_obj)

        # Handle missing required parameters by setting defaults
        for param_name, (param_type, required, min_val, max_val, default) in cls.PARAMETER_DEFINITIONS.items():
            if required and not hasattr(config_obj, param_name) and default is not None:
                setattr(config_obj, param_name, default)
                fixes.append(f"Set missing parameter {param_name} to default value: {default}")

        # Fix value constraints for numeric types
        for param_name, (param_type, required, min_val, max_val, default) in cls.PARAMETER_DEFINITIONS.items():
            if hasattr(config_obj, param_name):
                value = getattr(config_obj, param_name)

                # Fix type if possible
                if value is not None and not isinstance(value, param_type):
                    try:
                        if param_type == bool and isinstance(value, str):
                            # Handle boolean string conversion
                            new_value = value.lower() in ('true', 'yes', '1', 'y')
                        else:
                            # Standard type conversion
                            new_value = param_type(value)

                        setattr(config_obj, param_name, new_value)
                        fixes.append(
                            f"Converted parameter {param_name} from {type(value).__name__} to {param_type.__name__}")
                    except (ValueError, TypeError):
                        errors.append(
                            f"Could not convert parameter {param_name} from {type(value).__name__} "
                            f"to {param_type.__name__}")

                # Fix value constraints if needed
                if value is not None and param_type in (int, float):
                    if min_val is not None and value < min_val:
                        setattr(config_obj, param_name, min_val)
                        fixes.append(
                            f"Adjusted parameter {param_name} from {value} to minimum value {min_val}")
                    elif max_val is not None and value > max_val:
                        setattr(config_obj, param_name, max_val)
                        fixes.append(
                            f"Adjusted parameter {param_name} from {value} to maximum value {max_val}")

        # Let validation run again to see if any errors remain
        remaining_errors = cls.validate_config(config_obj)

        # Return unique errors and fixes
        return list(set(remaining_errors)), list(set(fixes))

    @classmethod
    def get_parameter_info(cls) -> Dict[str, Dict[str, Any]]:
        """
        Get detailed information about all configuration parameters.

        Returns:
            Dictionary with parameter details
        """
        info = {}
        for param_name, (param_type, required, min_val, max_val, default) in cls.PARAMETER_DEFINITIONS.items():
            info[param_name] = {
                'type': param_type.__name__,
                'required': required,
                'min_value': min_val,
                'max_value': max_val,
                'default': default
            }
        return info
