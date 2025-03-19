import pytest

from macd_trend_adaptive_strategy.config.config_validator import ConfigValidator


class MockConfig:
    """A mock config object for testing validation"""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def test_config_validator_basic():
    """Test basic configuration validation"""
    # Valid configuration
    valid_config = MockConfig(
        timeframe='5m',
        risk_reward_ratio_str='1:2',
        risk_reward_ratio=0.5,
        min_roi=0.02,
        max_roi=0.05,
        fast_length=8,
        slow_length=21,
        signal_length=6,
        adx_period=10,
        adx_threshold=18.0,
        ema_fast=5,
        ema_slow=15,
        counter_trend_factor=0.5,
        aligned_trend_factor=1.0,
        counter_trend_stoploss_factor=0.5,
        aligned_trend_stoploss_factor=1.0,
        use_dynamic_stoploss=True,
        min_win_rate=0.2,
        max_win_rate=0.8,
        regime_win_rate_diff=0.2,
        min_recent_trades_per_direction=5,
        max_recent_trades=10,
        startup_candle_count=25,
        roi_cache_update_interval=30
    )

    errors = ConfigValidator.validate_config(valid_config)
    assert len(errors) == 0, f"Unexpected errors for valid config: {errors}"


def test_config_validator_missing_params():
    """Test validation with missing required parameters"""
    # Missing required parameters
    missing_params_config = MockConfig(
        timeframe='5m',
        min_roi=0.02,
        max_roi=0.05
        # Missing many required parameters
    )

    errors = ConfigValidator.validate_config(missing_params_config)
    assert len(errors) > 0, "Should have detected missing parameters"

    # Check that some specific errors are reported
    missing_param_errors = [e for e in errors if "Missing required parameter:" in e]
    assert len(missing_param_errors) > 0, "Should report missing required parameters"


def test_config_validator_invalid_types():
    """Test validation with incorrect parameter types"""
    # Invalid parameter types
    invalid_types_config = MockConfig(
        timeframe='5m',
        risk_reward_ratio_str='1:2',
        risk_reward_ratio="0.5",  # String instead of float
        min_roi="0.02",  # String instead of float
        max_roi=0.05,
        fast_length="8",  # String instead of int
        slow_length=21,
        signal_length=6,
        adx_period=10,
        adx_threshold=18.0,
        ema_fast=5,
        ema_slow=15,
        counter_trend_factor=0.5,
        aligned_trend_factor=1.0,
        counter_trend_stoploss_factor=0.5,
        aligned_trend_stoploss_factor=1.0,
        use_dynamic_stoploss="true",  # String instead of bool
        min_win_rate=0.2,
        max_win_rate=0.8,
        regime_win_rate_diff=0.2,
        min_recent_trades_per_direction=5,
        max_recent_trades=10,
        startup_candle_count=25,
        roi_cache_update_interval=30
    )

    errors = ConfigValidator.validate_config(invalid_types_config)
    assert len(errors) > 0, "Should have detected invalid parameter types"

    # Check that type errors are reported
    type_errors = [e for e in errors if "has incorrect type:" in e]
    assert len(type_errors) > 0, "Should report type mismatch errors"


def test_config_validator_value_constraints():
    """Test validation with values outside allowed constraints"""
    # Values outside constraints
    invalid_values_config = MockConfig(
        timeframe='5m',
        risk_reward_ratio_str='1:2',
        risk_reward_ratio=3.0,  # Above max (2.0)
        min_roi=0.3,  # Above max (0.2)
        max_roi=0.005,  # Below min (0.01)
        fast_length=1,  # Below min (2)
        slow_length=101,  # Above max (100)
        signal_length=6,
        adx_period=10,
        adx_threshold=18.0,
        ema_fast=5,
        ema_slow=15,
        counter_trend_factor=0.05,  # Below min (0.1)
        aligned_trend_factor=3.0,  # Above max (2.0)
        counter_trend_stoploss_factor=0.5,
        aligned_trend_stoploss_factor=1.0,
        use_dynamic_stoploss=True,
        min_win_rate=0.05,  # Below min (0.1)
        max_win_rate=0.95,  # Above max (0.9)
        regime_win_rate_diff=0.2,
        min_recent_trades_per_direction=5,
        max_recent_trades=10,
        startup_candle_count=25,
        roi_cache_update_interval=30
    )

    errors = ConfigValidator.validate_config(invalid_values_config)
    assert len(errors) > 0, "Should have detected values outside constraints"

    # Check that constraint errors are reported
    constraint_errors = [e for e in errors if "is below minimum" in e or "is above maximum" in e]
    assert len(constraint_errors) > 0, "Should report value constraint errors"


def test_config_validator_logical_consistency():
    """Test validation of logical consistency between parameters"""
    # Logically inconsistent config
    inconsistent_config = MockConfig(
        timeframe='5m',
        risk_reward_ratio_str='1:2',
        risk_reward_ratio=0.5,
        min_roi=0.05,  # Higher than max_roi
        max_roi=0.03,  # Lower than min_roi
        fast_length=25,  # Higher than slow_length
        slow_length=20,  # Lower than fast_length
        signal_length=6,
        adx_period=10,
        adx_threshold=18.0,
        ema_fast=20,  # Higher than ema_slow
        ema_slow=15,  # Lower than ema_fast
        counter_trend_factor=0.5,
        aligned_trend_factor=1.0,
        counter_trend_stoploss_factor=0.5,
        aligned_trend_stoploss_factor=1.0,
        use_dynamic_stoploss=True,
        min_win_rate=0.6,  # Higher than max_win_rate
        max_win_rate=0.5,  # Lower than min_win_rate
        regime_win_rate_diff=0.2,
        min_recent_trades_per_direction=15,  # Higher than max_recent_trades
        max_recent_trades=10,  # Lower than min_recent_trades_per_direction
        startup_candle_count=25,
        roi_cache_update_interval=30
    )

    errors = ConfigValidator.validate_config(inconsistent_config)
    assert len(errors) > 0, "Should have detected logical inconsistencies"

    # Check that specific consistency errors are reported
    assert any("min_roi" in e and "max_roi" in e for e in errors), "Should report min_roi/max_roi inconsistency"
    assert any("fast_length" in e and "slow_length" in e for e in errors), "Should report MACD parameters inconsistency"
    assert any("ema_fast" in e and "ema_slow" in e for e in errors), "Should report EMA parameters inconsistency"
    assert any("min_win_rate" in e and "max_win_rate" in e for e in errors), "Should report win rate inconsistency"
    assert any("min_recent_trades_per_direction" in e and "max_recent_trades" in e for e in errors), \
        "Should report recent trades inconsistency"


def test_config_validator_fix():
    """Test fixing configuration issues"""
    # Configuration with various issues
    problem_config = MockConfig(
        timeframe='5m',
        risk_reward_ratio_str='1:2',
        risk_reward_ratio="0.5",  # String instead of float
        min_roi=0.3,  # Above max (0.2)
        max_roi=0.25,  # Above max but still > min_roi
        fast_length=1,  # Below min (2)
        slow_length=21,
        signal_length=6,
        # Missing adx_period
        adx_threshold="18.0",  # String instead of float
        ema_fast=5,
        ema_slow=15,
        counter_trend_factor=0.05,  # Below min (0.1)
        aligned_trend_factor="1.0",  # String instead of float
        # Missing counter_trend_stoploss_factor
        aligned_trend_stoploss_factor=1.0,
        use_dynamic_stoploss=True
        # Many missing parameters
    )

    # Validate and attempt to fix
    errors, fixes = ConfigValidator.validate_and_fix(problem_config)

    # Some errors should be fixed
    assert len(fixes) > 0, "Should have applied fixes"

    # Check if specific fixes were applied
    assert hasattr(problem_config, 'risk_reward_ratio') and isinstance(problem_config.risk_reward_ratio, float), \
        "Should have fixed risk_reward_ratio type"

    assert hasattr(problem_config, 'min_roi') and problem_config.min_roi <= 0.2, \
        "Should have fixed min_roi constraint"

    assert hasattr(problem_config, 'fast_length') and problem_config.fast_length >= 2, \
        "Should have fixed fast_length constraint"

    assert hasattr(problem_config, 'counter_trend_factor') and problem_config.counter_trend_factor >= 0.1, \
        "Should have fixed counter_trend_factor constraint"

    # Some parameters should have been set to defaults
    if not hasattr(problem_config, 'adx_period'):
        assert any("adx_period" in fix for fix in fixes), \
            "Should have set default for missing adx_period"

    if not hasattr(problem_config, 'counter_trend_stoploss_factor'):
        assert any("counter_trend_stoploss_factor" in fix for fix in fixes), \
            "Should have set default for missing counter_trend_stoploss_factor"

    # Validate the fixed config
    final_errors = ConfigValidator.validate_config(problem_config)
    assert len(final_errors) < len(errors), "Should have fewer errors after fixing"


def test_parameter_info():
    """Test getting parameter information"""
    info = ConfigValidator.get_parameter_info()

    # Should include all parameters
    for param_name in ConfigValidator.PARAMETER_DEFINITIONS:
        assert param_name in info, f"Parameter {param_name} should be in info"

        # Each parameter should have complete info
        param_info = info[param_name]
        assert 'type' in param_info
        assert 'required' in param_info
        assert 'min_value' in param_info
        assert 'max_value' in param_info
        assert 'default' in param_info
