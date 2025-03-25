import yaml
import os

import pytest

from src.config.config_validator import ConfigValidator


def test_validate_required_parameters(strategy_config):
    """Test that required parameters are validated"""
    # Test with all required parameters present
    errors, fixes = ConfigValidator.validate_and_fix(strategy_config)
    assert len(errors) == 0, "No errors should be found with valid config"

    # Test with a missing parameter by temporarily removing it
    original_fast_length = strategy_config.fast_length
    delattr(strategy_config, 'fast_length')

    errors, fixes = ConfigValidator.validate_and_fix(strategy_config)
    # Check for the actual error message format
    assert any("Missing required parameter: fast_length" in error for error in errors)

    # Restore the parameter
    strategy_config.fast_length = original_fast_length


def test_validate_parameter_types(strategy_config):
    """Test that parameter types are validated"""
    # Test with correct parameter types
    errors, fixes = ConfigValidator.validate_and_fix(strategy_config)
    assert len(errors) == 0, "No errors should be found with valid config"

    # Test with incorrect parameter types
    strategy_config.min_stoploss = "-0.0125"  # Should be float
    strategy_config.fast_length = "12"  # Should be int

    errors, fixes = ConfigValidator.validate_and_fix(strategy_config)

    # Check that type errors are reported
    assert any("min_stoploss has incorrect type" in error for error in errors)
    assert any("fast_length has incorrect type" in error for error in errors)

    # Check that fixes were applied
    assert any("min_stoploss" in fix for fix in fixes)
    assert any("fast_length" in fix for fix in fixes)

    # Verify the values were corrected
    assert isinstance(strategy_config.min_stoploss, float)
    assert isinstance(strategy_config.fast_length, int)


def test_validate_value_constraints(strategy_config):
    """Test that parameter value constraints are validated"""
    # Test basic boundary constraints that we know should work
    strategy_config.fast_length = 1  # Below min (2)
    strategy_config.counter_trend_factor = 2.0  # Above max (1.0)

    # Run validation
    errors, fixes = ConfigValidator.validate_and_fix(strategy_config)

    # Check for successful fixes
    assert strategy_config.fast_length >= 2, "fast_length should be adjusted to at least 2"
    assert strategy_config.counter_trend_factor <= 1.0, "counter_trend_factor should be adjusted to at most 1.0"

    # Verify fixes were logged
    assert len(fixes) > 0, "There should be fix messages for validation issues"


def test_validate_logical_consistency(strategy_config):
    """Test that logical consistency between parameters is validated"""
    # Test logical consistency for length parameters
    strategy_config.fast_length = 30
    strategy_config.slow_length = 20  # fast_length should be less than slow_length
    strategy_config.ema_fast = 25
    strategy_config.ema_slow = 15  # ema_fast should be less than ema_slow

    # Apply fixes
    errors, fixes = ConfigValidator.validate_and_fix(strategy_config)

    # Verify the relationships were fixed
    assert strategy_config.fast_length < strategy_config.slow_length, "fast_length should be less than slow_length"
    assert strategy_config.ema_fast < strategy_config.ema_slow, "ema_fast should be less than ema_slow"

    # Check that fixes mention the parameters
    assert any(("length" in fix.lower() or "fast_" in fix.lower() or "slow_" in fix.lower()) for fix in fixes), \
        "Should mention length parameters in fixes"
    assert any(("ema" in fix.lower()) for fix in fixes), "Should mention EMA parameters in fixes"


def test_stoploss_ordering_in_strategy_config(strategy_config):
    """Test that min_stoploss and max_stoploss are correctly ordered in StrategyConfig"""
    # First, save the original values
    original_min = strategy_config.min_stoploss
    original_max = strategy_config.max_stoploss

    # Manually set them in the wrong order (min more negative than max)
    strategy_config.min_stoploss = -0.06  # More negative (wrong)
    strategy_config.max_stoploss = -0.02  # Less negative (wrong)

    # Run the calculation that should fix the ordering
    strategy_config._calculate_derived_parameters()

    # Verify the values were swapped to the correct order
    assert strategy_config.min_stoploss == -0.02, "min_stoploss should be -0.02 (less negative, closer to zero)"
    assert strategy_config.max_stoploss == -0.06, "max_stoploss should be -0.06 (more negative, further from zero)"

    # Verify ROI values were calculated correctly after swapping
    expected_min_roi = abs(strategy_config.min_stoploss) * strategy_config.risk_reward_ratio_float
    expected_max_roi = abs(strategy_config.max_stoploss) * strategy_config.risk_reward_ratio_float

    assert abs(strategy_config.min_roi - expected_min_roi) < 0.0001, \
        f"Expected min_roi {expected_min_roi}, got {strategy_config.min_roi}"
    assert abs(strategy_config.max_roi - expected_max_roi) < 0.0001, \
        f"Expected max_roi {expected_max_roi}, got {strategy_config.max_roi}"

    # Restore the original values for other tests
    strategy_config.min_stoploss = original_min
    strategy_config.max_stoploss = original_max
    strategy_config._calculate_derived_parameters()


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