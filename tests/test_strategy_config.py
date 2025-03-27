import pytest

from src.config.config_parser import ConfigParser
from src.config.strategy_config import StrategyConfig, StrategyMode


def test_strategy_config_initialization(mock_config_parser):
    """Test basic StrategyConfig initialization"""
    # Test with DEFAULT mode
    config = StrategyConfig(mode=StrategyMode.DEFAULT, config_parser=mock_config_parser)

    # Check that timeframe was set correctly
    assert config.timeframe == '15m'

    # Check that some core attributes exist
    assert hasattr(config, 'min_stoploss')
    assert hasattr(config, 'max_stoploss')
    assert hasattr(config, 'fast_length')
    assert hasattr(config, 'slow_length')


def test_strategy_config_with_different_timeframes(mock_config_parser):
    """Test StrategyConfig with different timeframe modes"""
    # Test with different timeframes if they exist in the mock config
    for mode in [StrategyMode.TIMEFRAME_5M, StrategyMode.TIMEFRAME_15M]:
        try:
            config = StrategyConfig(mode=mode, config_parser=mock_config_parser)
            assert config.timeframe == mode.value
        except ValueError:
            # Skip if this timeframe isn't properly configured in the mock
            pass


def test_strategy_config_with_auto_mode(mock_config_parser):
    """Test StrategyConfig with AUTO mode"""
    # Create a parser with FreqTrade config for auto-detection
    freqtrade_config = {'timeframe': '15m'}
    auto_parser = ConfigParser(config_path=mock_config_parser.config_path, freqtrade_config=freqtrade_config)

    # Test with AUTO mode
    config = StrategyConfig(mode=StrategyMode.AUTO, config_parser=auto_parser)
    assert config.timeframe == '15m'


@pytest.mark.parametrize('timeframe,mode', [
    ("5m", StrategyMode.TIMEFRAME_5M),
    ("1m", StrategyMode.TIMEFRAME_1M)
])
def test_strategy_config_with_macd_preset(mock_config_file, timeframe, mode):
    """Test StrategyConfig initialization with MACD preset configurations"""
    parser = ConfigParser(config_path=mock_config_file)

    # Use explicit mode instead of AUTO
    config = StrategyConfig(mode=mode, config_parser=parser)

    # Verify timeframe matches the specified mode
    assert config.timeframe == timeframe

    # Verify MACD preset parameters were correctly applied
    assert hasattr(config, 'fast_length')
    assert hasattr(config, 'slow_length')
    assert hasattr(config, 'signal_length')

    # Verify preset name was stored
    assert hasattr(config, 'macd_preset_str')

    if timeframe == "5m":
        # Check classic preset values for 5m
        assert config.fast_length == 12
        assert config.slow_length == 26
        assert config.signal_length == 9
        assert config.macd_preset_str == "classic"
    elif timeframe == "1m":
        # Check responsive preset values for 1m
        assert config.fast_length == 5
        assert config.slow_length == 13
        assert config.signal_length == 3
        assert config.macd_preset_str == "responsive"


def test_strategy_config_summary(mock_config_parser):
    """Test StrategyConfig.get_config_summary includes MACD preset information"""
    # Test with 5m mode (uses MACD preset)
    config = StrategyConfig(mode=StrategyMode.TIMEFRAME_5M, config_parser=mock_config_parser)
    summary = config.get_config_summary()

    # Check that summary contains key sections including MACD preset info
    assert config.timeframe in summary
    assert "ROI:" in summary
    assert "Stoploss:" in summary

    # Verify MACD preset information is included
    preset_info = f"MACD: {config.macd_preset_str} ({config.fast_length}/{config.slow_length}/{config.signal_length})"
    assert preset_info in summary

    # Test with 15m mode (uses explicit MACD parameters)
    config = StrategyConfig(mode=StrategyMode.TIMEFRAME_15M, config_parser=mock_config_parser)
    summary = config.get_config_summary()

    # Check the summary format for explicit parameters
    explicit_info = f"MACD: Custom ({config.fast_length}/{config.slow_length}/{config.signal_length})"
    assert explicit_info in summary


def test_strategy_config_with_override(mock_config_parser):
    """Test StrategyConfig handles preset with parameter overrides"""
    # Test with 30m mode (has preset with one parameter override)
    config = StrategyConfig(mode=StrategyMode.TIMEFRAME_30M, config_parser=mock_config_parser)

    # Verify the override took effect
    assert config.fast_length == 10  # Overridden value

    # But other parameters from the preset were applied
    assert config.slow_length == 34  # From delayed preset
    assert config.signal_length == 8  # From delayed preset

    # Verify preset name is stored
    assert config.macd_preset_str == "delayed"

    # Check the summary
    summary = config.get_config_summary()
    override_info = f"MACD: {config.macd_preset_str} ({config.fast_length}/{config.slow_length}/{config.signal_length})"
    assert override_info in summary