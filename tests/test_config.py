import yaml  # Add this import
import os
import tempfile
from unittest.mock import patch, mock_open

import pytest

from src.config.strategy_config import StrategyConfig, StrategyMode


def test_strategy_config_requires_config_file():
    """Test that StrategyConfig raises an error when no config file is provided"""
    with pytest.raises(ValueError) as excinfo:
        StrategyConfig(mode=StrategyMode.DEFAULT, config_path=None)

    assert "Configuration file not found" in str(excinfo.value)
    assert "A YAML configuration file is required" in str(excinfo.value)


def test_strategy_config_requires_valid_file_path():
    """Test that StrategyConfig raises an error when an invalid config file path is provided"""
    with pytest.raises(ValueError) as excinfo:
        StrategyConfig(mode=StrategyMode.DEFAULT, config_path="nonexistent_file.yaml")

    assert "Configuration file not found" in str(excinfo.value)
    assert "A YAML configuration file is required" in str(excinfo.value)


def test_strategy_config_from_valid_file(mock_config_file):
    """Test that StrategyConfig loads configuration from a valid file"""
    # Test with DEFAULT/15m mode
    config = StrategyConfig(mode=StrategyMode.DEFAULT, config_path=mock_config_file)

    # Check that values were loaded correctly
    assert config.timeframe == '15m'
    assert config.risk_reward_ratio_str == "1:2"

    # Check stoploss values (primary parameters)
    assert config.min_stoploss == -0.0125
    assert config.max_stoploss == -0.0275

    # Check derived ROI values
    expected_min_roi = abs(config.min_stoploss) * 2.0  # Using risk_reward_ratio 1:2
    expected_max_roi = abs(config.max_stoploss) * 2.0  # Using risk_reward_ratio 1:2
    assert abs(config.min_roi - expected_min_roi) < 0.0001
    assert abs(config.max_roi - expected_max_roi) < 0.0001
    assert config.fast_length == 12
    assert config.slow_length == 26
    assert config.signal_length == 9
    assert config.adx_period == 14
    assert config.adx_threshold == 25
    assert config.ema_fast == 8
    assert config.ema_slow == 21


def test_strategy_config_timeframe_specific_settings(mock_config_file):
    """Test that StrategyConfig loads timeframe-specific settings"""
    # Test with 5m mode
    config_5m = StrategyConfig(mode=StrategyMode.TIMEFRAME_5M, config_path=mock_config_file)

    # Check that 5m values were loaded correctly
    assert config_5m.timeframe == '5m'
    assert config_5m.risk_reward_ratio_str == "1:2"
    assert config_5m.min_stoploss == -0.0125
    assert config_5m.max_stoploss == -0.0275

    # Check derived ROI values
    expected_min_roi = abs(config_5m.min_stoploss) * 2.0  # risk_reward_ratio 1:2
    expected_max_roi = abs(config_5m.max_stoploss) * 2.0  # risk_reward_ratio 1:2
    assert abs(config_5m.min_roi - expected_min_roi) < 0.0001
    assert abs(config_5m.max_roi - expected_max_roi) < 0.0001

    # Test with 1m mode
    config_1m = StrategyConfig(mode=StrategyMode.TIMEFRAME_1M, config_path=mock_config_file)

    # Check that 1m values were loaded correctly
    assert config_1m.timeframe == '1m'
    assert config_1m.risk_reward_ratio_str == "1:1.5"
    assert config_1m.min_stoploss == -0.01
    assert config_1m.max_stoploss == -0.03

    # Check derived ROI values
    expected_min_roi = abs(config_1m.min_stoploss) * 1.5  # risk_reward_ratio 1:1.5
    expected_max_roi = abs(config_1m.max_stoploss) * 1.5  # risk_reward_ratio 1:1.5
    assert abs(config_1m.min_roi - expected_min_roi) < 0.0001
    assert abs(config_1m.max_roi - expected_max_roi) < 0.0001


def test_strategy_config_global_settings(mock_config_file):
    """Test that global settings apply to all timeframes"""
    # Test with 5m mode - should have timeframe settings plus global settings
    config = StrategyConfig(mode=StrategyMode.TIMEFRAME_5M, config_path=mock_config_file)

    # Check that both 5m-specific and global values were loaded correctly
    assert config.timeframe == '5m'
    assert config.fast_length == 12
    assert config.slow_length == 26
    assert config.counter_trend_factor == 0.5  # From global
    assert config.aligned_trend_factor == 1.0  # From global
    assert config.startup_candle_count == 30  # From global


def test_config_load_failure():
    """Test error handling when config file can't be loaded properly"""
    # First, we need to patch os.path.exists to return True
    # so that the code proceeds to try to open the file
    with patch("os.path.exists", return_value=True):
        # Then we mock the open call to return invalid YAML
        with patch("builtins.open", mock_open(read_data="invalid: yaml: - content")):
            with pytest.raises(ValueError) as excinfo:
                StrategyConfig(mode=StrategyMode.DEFAULT, config_path="fake_path.yaml")

    # Now check for the correct error message
    assert "Failed to load configuration" in str(excinfo.value)


def test_config_derived_params(mock_config_file):
    """Test that derived parameters are calculated correctly"""
    # Create a config with specific timeframe settings for 15m
    config = StrategyConfig(mode=StrategyMode.TIMEFRAME_15M, config_path=mock_config_file)

    # Check derived parameters
    risk_reward_float = float(config.risk_reward_ratio_str.split(':')[1])
    assert config.risk_reward_ratio_float == risk_reward_float

    # Base stoploss should be the average of min and max
    expected_base_stoploss = (config.min_stoploss + config.max_stoploss) / 2
    assert abs(config.base_stoploss - expected_base_stoploss) < 0.0001, \
        f"Expected base_stoploss {expected_base_stoploss}, got {config.base_stoploss}"

    # ROI values should be derived from stoploss * risk_reward_ratio
    expected_min_roi = abs(config.min_stoploss) * config.risk_reward_ratio_float
    assert abs(config.min_roi - expected_min_roi) < 0.0001, \
        f"Expected min_roi {expected_min_roi}, got {config.min_roi}"

    expected_max_roi = abs(config.max_stoploss) * config.risk_reward_ratio_float
    assert abs(config.max_roi - expected_max_roi) < 0.0001, \
        f"Expected max_roi {expected_max_roi}, got {config.max_roi}"

    # Check fallback values
    assert config.static_stoploss <= config.max_stoploss * 1.2, \
        "static_stoploss should be more negative than max_stoploss"
    assert config.default_roi >= config.max_roi * 1.2, \
        "default_roi should be higher than max_roi"


def test_config_extension_validation():
    """Test that configuration files must have a .yaml or .yml extension"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
        yaml.dump({"15m": {"risk_reward_ratio": "1:2"}}, temp_file)
        invalid_ext_path = temp_file.name

    try:
        with pytest.raises(ValueError) as excinfo:
            StrategyConfig(mode=StrategyMode.DEFAULT, config_path=invalid_ext_path)

        assert "must have a .yaml or .yml extension" in str(excinfo.value)
    finally:
        os.unlink(invalid_ext_path)