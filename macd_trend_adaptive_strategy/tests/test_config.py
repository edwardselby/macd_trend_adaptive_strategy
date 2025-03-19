import json
import os
import tempfile
from unittest.mock import patch

import pytest

from macd_trend_adaptive_strategy.config.strategy_config import StrategyConfig, StrategyMode


@pytest.fixture
def temp_config_file():
    """Create a temporary config file for testing"""
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as temp_file:
        yield temp_file.name
    # Clean up the file after the test
    if os.path.exists(temp_file.name):
        os.remove(temp_file.name)


def test_load_valid_config_file(temp_config_file):
    """Test loading a valid configuration file with timeframe-specific settings"""
    # Create a valid config with timeframe-specific settings
    config_data = {
        "5m": {
            "risk_reward_ratio": "1:2.5",
            "min_roi": 0.025,
            "max_roi": 0.050,
            "fast_length": 10,
            "slow_length": 25
        },
        "global": {
            "counter_trend_factor": 0.6,
            "aligned_trend_factor": 1.2
        }
    }

    # Write to temp file
    with open(temp_config_file, 'w') as f:
        json.dump(config_data, f)

    # Load config with the temp file
    with patch('macd_trend_adaptive_strategy.config.strategy_config.logger') as mock_logger:
        config = StrategyConfig(StrategyMode.TIMEFRAME_5M, temp_config_file)

        # Verify the timeframe-specific settings were loaded
        assert config.timeframe == '5m'
        assert config.risk_reward_ratio_str == "1:2.5"
        assert config.min_roi == 0.025
        assert config.max_roi == 0.050
        assert config.fast_length == 10
        assert config.slow_length == 25

        # Verify log message for specific timeframe config
        mock_logger.info.assert_any_call("Found specific configuration for timeframe 5m")


def test_load_nonexistent_config_file():
    """Test loading a non-existent configuration file"""
    non_existent_file = "/path/to/nonexistent/config.json"

    with patch('macd_trend_adaptive_strategy.config.strategy_config.logger') as mock_logger:
        config = StrategyConfig(StrategyMode.TIMEFRAME_5M, non_existent_file)

        # Verify default values are used
        assert config.timeframe == '5m'
        assert hasattr(config, 'min_roi')
        assert hasattr(config, 'max_roi')

        # Verify warning was logged
        mock_logger.warning.assert_called_with(
            f"Configuration file {non_existent_file} not found, using defaults")


def test_load_malformed_json_config(temp_config_file):
    """Test handling of malformed JSON configuration file"""
    # Write invalid JSON to temp file
    with open(temp_config_file, 'w') as f:
        f.write("{ This is not valid JSON")

    with patch('macd_trend_adaptive_strategy.config.strategy_config.logger') as mock_logger:
        config = StrategyConfig(StrategyMode.TIMEFRAME_15M, temp_config_file)

        # Verify default values are used
        assert config.timeframe == '15m'
        assert hasattr(config, 'min_roi')
        assert hasattr(config, 'max_roi')

        # Verify error was logged
        mock_logger.error.assert_called_once()
        mock_logger.info.assert_any_call(
            f"Using default configuration values for timeframe 15m")


def test_load_config_different_timeframe(temp_config_file):
    """Test loading a config with settings for a different timeframe"""
    # Create config with settings for 1h but request 5m
    config_data = {
        "1h": {
            "risk_reward_ratio": "1:3",
            "min_roi": 0.04,
            "max_roi": 0.08
        }
    }

    # Write to temp file
    with open(temp_config_file, 'w') as f:
        json.dump(config_data, f)

    with patch('macd_trend_adaptive_strategy.config.strategy_config.logger') as mock_logger:
        config = StrategyConfig(StrategyMode.TIMEFRAME_5M, temp_config_file)

        # Should use defaults for 5m since no 5m config is provided
        assert config.timeframe == '5m'
        # Verify defaults are used, not 1h values
        default_5m = StrategyConfig.DEFAULT_TIMEFRAME_CONFIGS['5m']
        assert config.risk_reward_ratio_str == default_5m['risk_reward_ratio']
        assert config.min_roi == default_5m['min_roi']
        assert config.max_roi == default_5m['max_roi']


def test_load_partial_timeframe_config(temp_config_file):
    """Test loading a config with partial settings for a timeframe"""
    # Create config with only some settings for 5m
    config_data = {
        "5m": {
            "risk_reward_ratio": "1:3",
            # min_roi and max_roi not specified
        }
    }

    # Write to temp file
    with open(temp_config_file, 'w') as f:
        json.dump(config_data, f)

    config = StrategyConfig(StrategyMode.TIMEFRAME_5M, temp_config_file)

    # Should use specified value for risk_reward_ratio
    assert config.risk_reward_ratio_str == "1:3"

    # Should use defaults for unspecified values
    default_5m = StrategyConfig.DEFAULT_TIMEFRAME_CONFIGS['5m']
    assert config.min_roi == default_5m['min_roi']
    assert config.max_roi == default_5m['max_roi']


def test_type_conversion_config_values(temp_config_file):
    """Test that config values are properly type-converted"""
    # Create config with string values that should be converted
    config_data = {
        "5m": {
            "min_roi": "0.035",  # String that should be converted to float
            "fast_length": "12",  # String that should be converted to int
            "adx_threshold": "22.5"  # String that should be converted to float
        }
    }

    # Write to temp file
    with open(temp_config_file, 'w') as f:
        json.dump(config_data, f)

    config = StrategyConfig(StrategyMode.TIMEFRAME_5M, temp_config_file)

    # Verify type conversion
    assert isinstance(config.min_roi, float)
    assert config.min_roi == 0.035

    assert isinstance(config.fast_length, int)
    assert config.fast_length == 12

    assert isinstance(config.adx_threshold, float)
    assert config.adx_threshold == 22.5


def test_global_settings_override(temp_config_file):
    """Test that global settings override timeframe-specific settings when both are present"""
    # Create config with both timeframe-specific and global settings
    config_data = {
        "5m": {
            "risk_reward_ratio": "1:2",
            "min_roi": 0.02,
            "max_roi": 0.045
        },
        "global": {
            "counter_trend_factor": 0.7,
            "aligned_trend_factor": 1.3,
            "counter_trend_stoploss_factor": 0.6,
            "aligned_trend_stoploss_factor": 1.2,
            "use_dynamic_stoploss": True,
            "min_win_rate": 0.25,
            "max_win_rate": 0.85,
            "regime_win_rate_diff": 0.25
        }
    }

    # Write to temp file
    with open(temp_config_file, 'w') as f:
        json.dump(config_data, f)

    # Load config
    config = StrategyConfig(StrategyMode.TIMEFRAME_5M, temp_config_file)

    # Verify timeframe settings are loaded correctly
    assert config.timeframe == '5m'
    assert config.risk_reward_ratio_str == "1:2"
    assert config.min_roi == 0.02
    assert config.max_roi == 0.045

    # Verify global settings override defaults
    assert config.counter_trend_factor == 0.7
    assert config.aligned_trend_factor == 1.3
    assert config.counter_trend_stoploss_factor == 0.6
    assert config.aligned_trend_stoploss_factor == 1.2
    assert config.use_dynamic_stoploss is True
    assert config.min_win_rate == 0.25
    assert config.max_win_rate == 0.85
    assert config.regime_win_rate_diff == 0.25


def test_global_settings_without_timeframe(temp_config_file):
    """Test that global settings are applied even if no timeframe-specific settings exist"""
    # Create config with only global settings
    config_data = {
        "global": {
            "counter_trend_factor": 0.8,
            "aligned_trend_factor": 1.5,
            "counter_trend_stoploss_factor": 0.4,
            "aligned_trend_stoploss_factor": 1.4,
            "long_roi_boost": 0.01
        }
    }

    # Write to temp file
    with open(temp_config_file, 'w') as f:
        json.dump(config_data, f)

    # Load config for 15m timeframe
    config = StrategyConfig(StrategyMode.TIMEFRAME_15M, temp_config_file)

    # Verify timeframe settings are defaults
    assert config.timeframe == '15m'
    default_15m = StrategyConfig.DEFAULT_TIMEFRAME_CONFIGS['15m']
    assert config.risk_reward_ratio_str == default_15m['risk_reward_ratio']
    assert config.min_roi == default_15m['min_roi']
    assert config.max_roi == default_15m['max_roi']

    # Verify global settings are applied
    assert config.counter_trend_factor == 0.8
    assert config.aligned_trend_factor == 1.5
    assert config.counter_trend_stoploss_factor == 0.4
    assert config.aligned_trend_stoploss_factor == 1.4
    assert config.long_roi_boost == 0.01


def test_global_settings_partial_override(temp_config_file):
    """Test that global settings partially override defaults"""
    # Create config with just a few global settings
    config_data = {
        "global": {
            "counter_trend_factor": 0.9,
            # Other global settings not specified
        }
    }

    # Write to temp file
    with open(temp_config_file, 'w') as f:
        json.dump(config_data, f)

    # Load config for 30m timeframe
    config = StrategyConfig(StrategyMode.TIMEFRAME_30M, temp_config_file)

    # Verify the specified global setting is applied
    assert config.counter_trend_factor == 0.9

    # Verify other global settings use defaults
    assert config.aligned_trend_factor == 1.0  # Default value
    assert config.counter_trend_stoploss_factor == 0.5  # Default value
    assert config.aligned_trend_stoploss_factor == 1.0  # Default value


def test_config_mode_mapping():
    """Test that strategy modes map to correct timeframes"""
    # Test all mode mappings
    mode_timeframe_map = {
        StrategyMode.DEFAULT: '15m',
        StrategyMode.TIMEFRAME_1M: '1m',
        StrategyMode.TIMEFRAME_5M: '5m',
        StrategyMode.TIMEFRAME_15M: '15m',
        StrategyMode.TIMEFRAME_30M: '30m',
        StrategyMode.TIMEFRAME_1H: '1h'
    }

    for mode, expected_timeframe in mode_timeframe_map.items():
        config = StrategyConfig(mode)
        assert config.timeframe == expected_timeframe


def test_top_level_config_backwards_compatibility(temp_config_file):
    """Test backwards compatibility with top-level config parameters"""
    # Create an old-style config with top-level parameters
    config_data = {
        "counter_trend_factor": 0.65,
        "aligned_trend_factor": 1.25,
        "use_dynamic_stoploss": False
    }

    # Write to temp file
    with open(temp_config_file, 'w') as f:
        json.dump(config_data, f)

    # Load config
    config = StrategyConfig(StrategyMode.TIMEFRAME_15M, temp_config_file)

    # Verify top-level parameters are loaded correctly
    assert config.counter_trend_factor == 0.65
    assert config.aligned_trend_factor == 1.25
    assert config.use_dynamic_stoploss is False

    # Verify other parameters use defaults
    default_15m = StrategyConfig.DEFAULT_TIMEFRAME_CONFIGS['15m']
    assert config.risk_reward_ratio_str == default_15m['risk_reward_ratio']
    assert config.min_roi == default_15m['min_roi']
    assert config.max_roi == default_15m['max_roi']

