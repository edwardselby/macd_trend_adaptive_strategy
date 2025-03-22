import json
import os
import tempfile
import pytest
from unittest.mock import patch, mock_open

from src.config.strategy_config import StrategyConfig, StrategyMode


def test_strategy_config_requires_config_file():
    """Test that StrategyConfig raises an error when no config file is provided"""
    with pytest.raises(ValueError) as excinfo:
        StrategyConfig(mode=StrategyMode.DEFAULT, config_path=None)

    assert "Configuration file not found" in str(excinfo.value)
    assert "A configuration file is required" in str(excinfo.value)


def test_strategy_config_requires_valid_file_path():
    """Test that StrategyConfig raises an error when an invalid config file path is provided"""
    with pytest.raises(ValueError) as excinfo:
        StrategyConfig(mode=StrategyMode.DEFAULT, config_path="nonexistent_file.json")

    assert "Configuration file not found" in str(excinfo.value)
    assert "A configuration file is required" in str(excinfo.value)


def test_strategy_config_from_valid_file():
    """Test that StrategyConfig loads configuration from a valid file"""
    # Create a temporary config file
    config_data = {
        "15m": {
            "risk_reward_ratio": "1:2",
            "min_roi": 0.025,
            "max_roi": 0.055,
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

    try:
        # Test with DEFAULT/15m mode
        config = StrategyConfig(mode=StrategyMode.DEFAULT, config_path=temp_file_path)

        # Check that values were loaded correctly
        assert config.timeframe == '15m'
        assert config.risk_reward_ratio_str == "1:2"
        assert config.min_roi == 0.025
        assert config.max_roi == 0.055
        assert config.fast_length == 12
        assert config.slow_length == 26
        assert config.signal_length == 9
        assert config.adx_period == 14
        assert config.adx_threshold == 25
        assert config.ema_fast == 8
        assert config.ema_slow == 21

    finally:
        # Clean up the temporary file
        os.unlink(temp_file_path)


def test_strategy_config_timeframe_specific_settings():
    """Test that StrategyConfig loads timeframe-specific settings"""
    # Create a temporary config file with multiple timeframes
    config_data = {
        "5m": {
            "risk_reward_ratio": "1:3",
            "min_roi": 0.03,
            "max_roi": 0.06
        },
        "15m": {
            "risk_reward_ratio": "1:2",
            "min_roi": 0.025,
            "max_roi": 0.055
        }
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
        json.dump(config_data, temp_file)
        temp_file_path = temp_file.name

    try:
        # Test with 5m mode
        config_5m = StrategyConfig(mode=StrategyMode.TIMEFRAME_5M, config_path=temp_file_path)

        # Check that 5m values were loaded correctly
        assert config_5m.timeframe == '5m'
        assert config_5m.risk_reward_ratio_str == "1:3"
        assert config_5m.min_roi == 0.03
        assert config_5m.max_roi == 0.06

        # Test with 15m mode
        config_15m = StrategyConfig(mode=StrategyMode.TIMEFRAME_15M, config_path=temp_file_path)

        # Check that 15m values were loaded correctly
        assert config_15m.timeframe == '15m'
        assert config_15m.risk_reward_ratio_str == "1:2"
        assert config_15m.min_roi == 0.025
        assert config_15m.max_roi == 0.055

    finally:
        # Clean up the temporary file
        os.unlink(temp_file_path)


def test_strategy_config_global_settings():
    """Test that global settings apply to all timeframes"""
    # Create a temporary config file with global settings
    config_data = {
        "5m": {
            "fast_length": 5,
            "slow_length": 15
        },
        "global": {
            "risk_reward_ratio": "1:2",
            "min_roi": 0.025,
            "max_roi": 0.055,
            "counter_trend_factor": 0.5,
            "aligned_trend_factor": 1.0
        }
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
        json.dump(config_data, temp_file)
        temp_file_path = temp_file.name

    try:
        # Test with 5m mode - should have timeframe settings plus global settings
        config = StrategyConfig(mode=StrategyMode.TIMEFRAME_5M, config_path=temp_file_path)

        # Check that both 5m-specific and global values were loaded correctly
        assert config.timeframe == '5m'
        assert config.fast_length == 5
        assert config.slow_length == 15
        assert config.risk_reward_ratio_str == "1:2"
        assert config.min_roi == 0.025
        assert config.max_roi == 0.055
        assert config.counter_trend_factor == 0.5
        assert config.aligned_trend_factor == 1.0

    finally:
        # Clean up the temporary file
        os.unlink(temp_file_path)


def test_config_load_failure():
    """Test error handling when config file can't be loaded properly"""
    # First, we need to patch os.path.exists to return True
    # so that the code proceeds to try to open the file
    with patch("os.path.exists", return_value=True):
        # Then we mock the open call to return invalid JSON
        with patch("builtins.open", mock_open(read_data="invalid json content")):
            with pytest.raises(ValueError) as excinfo:
                StrategyConfig(mode=StrategyMode.DEFAULT, config_path="fake_path.json")

    # Now check for the correct error message
    assert "Failed to load configuration" in str(excinfo.value)


def test_config_derived_params():
    """Test that derived parameters are calculated correctly"""
    # Create a temporary config file
    config_data = {
        "15m": {
            "risk_reward_ratio": "1:2",
            "min_roi": 0.03,
            "max_roi": 0.06
        }
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
        json.dump(config_data, temp_file)
        temp_file_path = temp_file.name

    try:
        config = StrategyConfig(mode=StrategyMode.TIMEFRAME_15M, config_path=temp_file_path)

        # Check derived parameters
        assert config.base_roi == 0.045  # (0.03 + 0.06) / 2
        assert config.risk_reward_ratio_float == 0.5  # 1:2 as float
        assert config.min_stoploss == -0.015  # -1 * 0.03 * 0.5
        assert config.max_stoploss == -0.03  # -1 * 0.06 * 0.5

        # Check fallback values
        assert config.static_stoploss <= config.max_stoploss * 1.2
        assert config.default_roi >= config.max_roi * 1.2

    finally:
        # Clean up the temporary file
        os.unlink(temp_file_path)