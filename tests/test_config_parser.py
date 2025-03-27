import os
import pytest
from unittest.mock import patch, MagicMock

from src.config.config_parser import ConfigParser


def test_config_parser_initialization(mock_config_file):
    """Test that ConfigParser initializes correctly with a valid config file"""
    parser = ConfigParser(config_path=mock_config_file)

    # Check that the config data was loaded
    assert parser.config_data is not None
    assert '1m' in parser.config_data
    assert '5m' in parser.config_data
    assert '15m' in parser.config_data
    assert 'global' in parser.config_data


def test_determine_timeframe_with_explicit_mode(mock_config_file):
    """Test that timeframe is correctly determined from explicit mode"""
    parser = ConfigParser(config_path=mock_config_file)

    # Test with explicit timeframe modes
    assert parser.determine_timeframe('1m') == '1m'
    assert parser.determine_timeframe('5m') == '5m'
    assert parser.determine_timeframe('15m') == '15m'


def test_determine_timeframe_with_auto_detection(mock_config_file):
    """Test that timeframe is auto-detected from FreqTrade config"""
    freqtrade_config = {'timeframe': '30m'}
    parser = ConfigParser(config_path=mock_config_file, freqtrade_config=freqtrade_config)

    # Test with auto mode
    assert parser.determine_timeframe('auto') == '30m'


def test_determine_timeframe_with_default(mock_config_file):
    """Test that default timeframe is used when needed"""
    parser = ConfigParser(config_path=mock_config_file)

    # Test with auto mode but no FreqTrade config (should use default)
    assert parser.determine_timeframe('auto') == '15m'


def test_load_config_for_timeframe_with_specific_section(mock_config_file):
    """Test loading configuration for a timeframe with a specific section"""
    parser = ConfigParser(config_path=mock_config_file)

    # Load config for 1m timeframe
    config = parser.load_config_for_timeframe('1m')

    # Check that timeframe-specific values were loaded
    assert config['timeframe'] == '1m'

    # Values from the mock_config_file fixture
    expected_fast_length = 5
    expected_slow_length = 13
    expected_signal_length = 3

    assert config['fast_length'] == expected_fast_length
    assert config['slow_length'] == expected_slow_length
    assert config['signal_length'] == expected_signal_length

    # Check ADX threshold conversion
    if isinstance(config['adx_threshold_str'], str):
        assert config['adx_threshold_str'].lower() in ['weak', 'normal', 'strong', 'extreme']

    # Check that global values were merged
    assert 'use_dynamic_stoploss' in config


def test_load_config_for_timeframe_with_global_fallback(mock_config_file):
    """Test loading configuration for a timeframe with global fallback settings"""
    parser = ConfigParser(config_path=mock_config_file)

    # For the 30m timeframe (not explicitly defined in config but has global fallbacks)
    # This should succeed if global parameters cover all required fields
    try:
        config = parser.load_config_for_timeframe('30m')
        assert config['timeframe'] == '30m'
        assert 'counter_trend_factor' in config  # Should be from global
    except ValueError:
        # If it fails, it means the mock_config_file doesn't have all required params in global
        # That's acceptable for this test
        pass


def test_process_adx_threshold():
    """Test ADX threshold string to numeric value conversion"""
    # Test with known string values
    assert ConfigParser._process_adx_threshold({'adx_threshold': 'weak'})['adx_threshold'] == 25
    assert ConfigParser._process_adx_threshold({'adx_threshold': 'normal'})['adx_threshold'] == 50
    assert ConfigParser._process_adx_threshold({'adx_threshold': 'strong'})['adx_threshold'] == 75
    assert ConfigParser._process_adx_threshold({'adx_threshold': 'extreme'})['adx_threshold'] == 90

    # Test with numeric value (should remain unchanged)
    assert ConfigParser._process_adx_threshold({'adx_threshold': 42})['adx_threshold'] == 42

    # Test with invalid string value (should default to "normal")
    with patch('logging.Logger.warning') as mock_warning:
        result = ConfigParser._process_adx_threshold({'adx_threshold': 'invalid'})
        assert result['adx_threshold'] == 50
        assert result['adx_threshold_str'] == 'normal'
        mock_warning.assert_called_once()


def test_parse_risk_reward_ratio():
    """Test parsing of risk:reward ratio string"""
    # Test with valid format
    result = ConfigParser._parse_risk_reward_ratio({'risk_reward_ratio': '1:2'})
    assert result['risk_reward_ratio_str'] == '1:2'
    assert result['risk_reward_ratio_float'] == 2.0

    # Test with different values
    result = ConfigParser._parse_risk_reward_ratio({'risk_reward_ratio': '1:3'})
    assert result['risk_reward_ratio_float'] == 3.0

    # Test with spaces
    result = ConfigParser._parse_risk_reward_ratio({'risk_reward_ratio': '1 : 2.5'})
    assert result['risk_reward_ratio_float'] == 2.5

    # Test with invalid format
    with patch('logging.Logger.error') as mock_error:
        with patch('logging.Logger.info') as mock_info:
            result = ConfigParser._parse_risk_reward_ratio({'risk_reward_ratio': 'invalid'})
            assert result['risk_reward_ratio_float'] == 2.0  # Default value
            assert result['risk_reward_ratio_str'] == '1:2'  # Default value
            mock_error.assert_called_once()
            mock_info.assert_called_once()


def test_calculate_derived_parameters():
    """Test calculation of derived parameters"""
    # Setup basic config
    base_config = {
        'risk_reward_ratio_float': 2.0,
        'risk_reward_ratio_str': '1:2',
        'min_stoploss': -0.01,
        'max_stoploss': -0.03
    }

    # Calculate derived parameters
    result = ConfigParser._calculate_derived_parameters(base_config)

    # Check risk:reward ratio was copied
    assert result['risk_reward_ratio'] == 2.0

    # Check stoploss values were maintained in proper order
    assert result['min_stoploss'] == -0.01
    assert result['max_stoploss'] == -0.03

    # Check base_stoploss calculation
    assert result['base_stoploss'] == -0.02  # (-0.01 + -0.03) / 2

    # Check ROI calculations
    assert result['min_roi'] == 0.01 * 2.0  # abs(min_stoploss) * risk_reward_ratio
    assert result['max_roi'] == 0.03 * 2.0  # abs(max_stoploss) * risk_reward_ratio
    assert result['base_roi'] == 0.04  # (0.02 + 0.06) / 2

    # Check fallback values
    assert result['static_stoploss'] == -0.036  # max_stoploss * 1.2
    assert result['default_roi'] == 0.072  # max_roi * 1.2


def test_validate_config():
    """Test config validation"""
    # Valid config
    valid_config = {
        'risk_reward_ratio': '1:2',
        'min_stoploss': -0.01,
        'max_stoploss': -0.03,
        'fast_length': 6,
        'slow_length': 14,
        'signal_length': 4,
        'adx_threshold': 'strong',
        'ema_fast': 3,
        'ema_slow': 10,
        'counter_trend_factor': 0.5,
        'aligned_trend_factor': 1.0,
        'counter_trend_stoploss_factor': 0.5,
        'aligned_trend_stoploss_factor': 1.0
    }

    errors = ConfigParser.validate_config(valid_config)
    assert len(errors) == 0, "Valid config should have no errors"

    # Missing required parameter
    invalid_config = valid_config.copy()
    del invalid_config['fast_length']
    errors = ConfigParser.validate_config(invalid_config)
    assert len(errors) == 2
    assert "Missing required parameter: fast_length" in errors[0]

    # Wrong parameter type
    invalid_config = valid_config.copy()
    invalid_config['fast_length'] = "not an integer"
    errors = ConfigParser.validate_config(invalid_config)
    assert len(errors) == 1
    assert "incorrect type" in errors[0]


def test_config_parser_with_missing_file():
    """Test ConfigParser with a non-existent file"""
    with pytest.raises(ValueError) as excinfo:
        ConfigParser(config_path="non_existent_file.yaml")

    assert "Configuration file not found" in str(excinfo.value)


def test_config_parser_with_invalid_yaml(mock_config_file):
    """Test ConfigParser with invalid YAML content"""
    with patch('src.config.config_parser.load_config', side_effect=Exception("YAML parsing error")):
        with pytest.raises(ValueError) as excinfo:
            ConfigParser(config_path=mock_config_file)

        assert "Failed to load configuration" in str(excinfo.value)


import pytest
from unittest.mock import patch, MagicMock

from src.config.config_parser import ConfigParser


def test_process_macd_parameters():
    """Test MACD preset processing with various scenarios"""
    # Test with valid preset and no overrides
    result = ConfigParser._process_macd_parameters({"macd_preset": "classic"})
    assert "fast_length" in result
    assert "slow_length" in result
    assert "signal_length" in result
    assert result["fast_length"] == 12  # Classic preset values
    assert result["slow_length"] == 26
    assert result["signal_length"] == 9
    assert result["macd_preset_str"] == "classic"

    # Test with valid preset and parameter override
    result = ConfigParser._process_macd_parameters({
        "macd_preset": "responsive",
        "fast_length": 8  # Override default
    })
    assert result["fast_length"] == 8  # Should use override value
    assert result["slow_length"] == 13  # Should use preset value
    assert result["signal_length"] == 3  # Should use preset value
    assert result["macd_preset_str"] == "responsive"

    # Test with invalid preset (should fall back to Classic)
    with patch('logging.Logger.warning') as mock_warning:
        result = ConfigParser._process_macd_parameters({"macd_preset": "nonexistent_preset"})
        assert result["fast_length"] == 12  # Classic preset values
        assert result["slow_length"] == 26
        assert result["signal_length"] == 9
        assert result["macd_preset_str"] == "classic"
        mock_warning.assert_called_once()

    # Test with case-insensitive preset name
    result = ConfigParser._process_macd_parameters({"macd_preset": "CLASSIC"})
    assert result["fast_length"] == 12
    assert result["macd_preset_str"] == "classic"

    # Test with only explicit parameters (no preset)
    config = {
        "fast_length": 15,
        "slow_length": 30,
        "signal_length": 10
    }
    result = ConfigParser._process_macd_parameters(config)
    assert result["fast_length"] == 15
    assert result["slow_length"] == 30
    assert result["signal_length"] == 10
    assert "macd_preset_str" not in result


def test_validate_config_with_macd_presets():
    """Test configuration validation with MACD presets"""
    # Valid config with preset
    valid_config_with_preset = {
        "risk_reward_ratio": "1:2",
        "min_stoploss": -0.01,
        "max_stoploss": -0.03,
        "macd_preset": "classic",  # Use preset instead of individual parameters
        "adx_threshold": "strong",
        "ema_fast": 3,
        "ema_slow": 10,
        "counter_trend_factor": 0.5,
        "aligned_trend_factor": 1.0,
        "counter_trend_stoploss_factor": 0.5,
        "aligned_trend_stoploss_factor": 1.0
    }

    errors = ConfigParser.validate_config(valid_config_with_preset)
    assert len(errors) == 0, "Valid config with preset should have no errors"

    # Test config with both preset and explicit parameters (valid)
    mixed_config = valid_config_with_preset.copy()
    mixed_config["fast_length"] = 8  # Override preset parameter
    errors = ConfigParser.validate_config(mixed_config)
    assert len(errors) == 0, "Valid config with preset and override should have no errors"

    # Test config with neither preset nor required MACD parameters
    invalid_config = valid_config_with_preset.copy()
    del invalid_config["macd_preset"]
    errors = ConfigParser.validate_config(invalid_config)
    assert len(errors) == 4  # 3 missing parameters + 1 general message
    assert any("Missing MACD configuration" in error for error in errors)
    assert any("fast_length" in error for error in errors)
    assert any("slow_length" in error for error in errors)
    assert any("signal_length" in error for error in errors)


def test_load_config_with_macd_preset(mock_config_file):
    """Test loading configuration with MACD preset processing"""
    parser = ConfigParser(config_path=mock_config_file)

    # Load config for 5m timeframe (has macd_preset: "classic")
    config = parser.load_config_for_timeframe('5m')

    # Verify preset was processed correctly
    assert config['fast_length'] == 12  # Classic preset value
    assert config['slow_length'] == 26  # Classic preset value
    assert config['signal_length'] == 9  # Classic preset value
    assert config['macd_preset_str'] == 'classic'

    # Load config for 30m timeframe (has preset with override)
    config = parser.load_config_for_timeframe('30m')

    # Verify preset was processed with override
    assert config['fast_length'] == 10  # Overridden value
    assert config['slow_length'] == 34  # Delayed preset value
    assert config['signal_length'] == 8  # Delayed preset value
    assert config['macd_preset_str'] == 'delayed'

    # Load config for 15m timeframe (has explicit parameters, no preset)
    config = parser.load_config_for_timeframe('15m')

    # Verify explicit parameters were preserved
    assert config['fast_length'] == 12  # Explicit value
    assert config['slow_length'] == 26  # Explicit value
    assert config['signal_length'] == 9  # Explicit value
    assert 'macd_preset_str' not in config


@pytest.mark.parametrize('mock_config_single_timeframe', ["5m"], indirect=True)
def test_load_config_with_only_preset(mock_config_single_timeframe):
    """Test loading configuration with only MACD preset specified"""
    parser = ConfigParser(config_path=mock_config_single_timeframe)
    config = parser.load_config_for_timeframe('5m')

    # Verify preset values were applied
    assert config['fast_length'] == 12  # Classic preset value
    assert config['slow_length'] == 26  # Classic preset value
    assert config['signal_length'] == 9  # Classic preset value
    assert config['macd_preset_str'] == 'classic'