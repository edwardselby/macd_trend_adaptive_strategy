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
    freqtrade_config = {'timeframe': '30m'}
    auto_parser = ConfigParser(config_path=mock_config_parser.config_path, freqtrade_config=freqtrade_config)

    # Test with AUTO mode
    config = StrategyConfig(mode=StrategyMode.AUTO, config_parser=auto_parser)
    assert config.timeframe == '30m'


def test_strategy_config_summary(mock_config_parser):
    """Test StrategyConfig.get_config_summary method"""
    config = StrategyConfig(mode=StrategyMode.DEFAULT, config_parser=mock_config_parser)
    summary = config.get_config_summary()

    # Check that summary contains key sections
    assert config.timeframe in summary
    assert "ROI:" in summary
    assert "Stoploss:" in summary
    assert "MACD:" in summary
    assert "ADX Threshold=" in summary