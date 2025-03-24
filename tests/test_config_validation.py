import json
import os
import tempfile

import pytest

from src.config.config_validator import ConfigValidator
from src.config.strategy_config import StrategyConfig, StrategyMode


@pytest.fixture
def sample_config_file():
    """Create a temporary config file with minimal valid settings"""
    config_data = {
        "15m": {
            "risk_reward_ratio": "1:2",
            "min_stoploss": -0.0125,  # Closer to zero (tighter)
            "max_stoploss": -0.0275,  # Further from zero (wider)
            "fast_length": 12,
            "slow_length": 26,
            "signal_length": 9,
            "adx_period": 14,
            "adx_threshold": 25,
            "ema_fast": 8,
            "ema_slow": 21
        }
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
        json.dump(config_data, temp_file)
        temp_file_path = temp_file.name

    yield temp_file_path

    # Clean up the temporary file
    os.unlink(temp_file_path)


def test_validate_required_parameters(sample_config_file):
    """Test that required parameters are validated"""
    config = StrategyConfig(mode=StrategyMode.DEFAULT, config_path=sample_config_file)

    # Test with all required parameters present
    errors, fixes = ConfigValidator.validate_and_fix(config)
    assert len(errors) == 0, "No errors should be found with valid config"

    # Test with a missing parameter by temporarily removing it
    original_fast_length = config.fast_length
    delattr(config, 'fast_length')

    errors, fixes = ConfigValidator.validate_and_fix(config)
    # Check for the actual error message format
    assert any("Missing required parameter: fast_length" in error for error in errors)

    # Restore the parameter
    config.fast_length = original_fast_length


def test_validate_parameter_types(sample_config_file):
    """Test that parameter types are validated"""
    config = StrategyConfig(mode=StrategyMode.DEFAULT, config_path=sample_config_file)

    # Test with correct parameter types
    errors, fixes = ConfigValidator.validate_and_fix(config)
    assert len(errors) == 0, "No errors should be found with valid config"

    # Test with incorrect parameter types
    config.min_stoploss = "-0.0125"  # Should be float
    config.fast_length = "12"  # Should be int

    errors, fixes = ConfigValidator.validate_and_fix(config)

    # Check that type errors are reported
    assert any("min_stoploss has incorrect type" in error for error in errors)
    assert any("fast_length has incorrect type" in error for error in errors)

    # Check that fixes were applied
    assert any("min_stoploss" in fix for fix in fixes)
    assert any("fast_length" in fix for fix in fixes)

    # Verify the values were corrected
    assert isinstance(config.min_stoploss, float)
    assert isinstance(config.fast_length, int)


def test_validate_value_constraints(sample_config_file):
    """Test that parameter value constraints are validated"""
    # TODO: Refactor this test and the underlying validation system for better separation of concerns
    # The complexity of testing suggests the validation approach could be simplified

    config = StrategyConfig(mode=StrategyMode.DEFAULT, config_path=sample_config_file)

    # Test basic boundary constraints that we know should work
    config.fast_length = 1  # Below min (2)
    config.counter_trend_factor = 2.0  # Above max (1.0)

    # Run validation
    errors, fixes = ConfigValidator.validate_and_fix(config)

    # Check for successful fixes
    assert config.fast_length >= 2, "fast_length should be adjusted to at least 2"
    assert config.counter_trend_factor <= 1.0, "counter_trend_factor should be adjusted to at most 1.0"

    # Verify fixes were logged
    assert len(fixes) > 0, "There should be fix messages for validation issues"

    # Note about stoploss handling (as a comment for future reference)
    # The ordering of min_stoploss and max_stoploss appears to be handled in
    # StrategyConfig._calculate_derived_parameters() rather than in ConfigValidator


def test_validate_logical_consistency(sample_config_file):
    """Test that logical consistency between parameters is validated"""
    config = StrategyConfig(mode=StrategyMode.DEFAULT, config_path=sample_config_file)

    # Test logical consistency for length parameters
    config.fast_length = 30
    config.slow_length = 20  # fast_length should be less than slow_length
    config.ema_fast = 25
    config.ema_slow = 15  # ema_fast should be less than ema_slow

    # Apply fixes
    errors, fixes = ConfigValidator.validate_and_fix(config)

    # Verify the relationships were fixed
    assert config.fast_length < config.slow_length, "fast_length should be less than slow_length"
    assert config.ema_fast < config.ema_slow, "ema_fast should be less than ema_slow"

    # Check that fixes mention the parameters
    assert any(("length" in fix.lower() or "fast_" in fix.lower() or "slow_" in fix.lower()) for fix in fixes), \
        "Should mention length parameters in fixes"
    assert any(("ema" in fix.lower()) for fix in fixes), "Should mention EMA parameters in fixes"


def test_stoploss_ordering_in_strategy_config():
    """Test that min_stoploss and max_stoploss are correctly ordered in StrategyConfig"""
    # Create a config with deliberately reversed stoploss values
    config_data = {
        "15m": {
            "risk_reward_ratio": "1:2",
            "min_stoploss": -0.06,  # More negative (wrong - should be closer to zero)
            "max_stoploss": -0.02  # Less negative (wrong - should be further from zero)
        }
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
        json.dump(config_data, temp_file)
        temp_file_path = temp_file.name

    try:
        # Creating the config should trigger the fix during initialization
        config = StrategyConfig(mode=StrategyMode.TIMEFRAME_15M, config_path=temp_file_path)

        # Verify the values were swapped to the correct order
        assert config.min_stoploss == -0.02, "min_stoploss should be -0.02 (less negative, closer to zero)"
        assert config.max_stoploss == -0.06, "max_stoploss should be -0.06 (more negative, further from zero)"

        # Verify ROI values were calculated correctly after swapping
        assert config.min_roi == 0.04, "min_roi should be 0.02 × 2 = 0.04"
        assert config.max_roi == 0.12, "max_roi should be 0.06 × 2 = 0.12"

    finally:
        os.unlink(temp_file_path)


def test_parameter_info():
    """Test getting parameter information"""
    info = ConfigValidator.get_parameter_info()

    # Check that info contains key parameters
    assert 'min_roi' in info
    assert 'max_roi' in info
    assert 'risk_reward_ratio' in info
    assert 'fast_length' in info
    assert 'slow_length' in info

    # Check that each parameter has complete info
    for param_name, param_info in info.items():
        assert 'type' in param_info
        assert 'required' in param_info
        assert 'min_value' in param_info
        assert 'max_value' in param_info
        assert 'default' in param_info