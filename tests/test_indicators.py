import pytest

from src.config.config_parser import ConfigParser
from src.config.strategy_config import StrategyConfig, StrategyMode
from src.indicators.technical import calculate_indicators, populate_entry_signals


def test_calculate_indicators(sample_dataframe, strategy_config):
    """Test that indicators are correctly calculated"""
    df = calculate_indicators(sample_dataframe, strategy_config)

    # Check that all expected columns are present
    expected_columns = [
        'macd', 'macdsignal', 'macd_prev', 'macdsignal_prev',
        'ema_fast', 'ema_slow', 'adx', 'plus_di', 'minus_di',
        'uptrend', 'downtrend'
    ]

    for col in expected_columns:
        assert col in df.columns, f"Expected column {col} not found in dataframe"

    # Calculate a more appropriate startup period
    # MACD typically needs slowperiod + signalperiod + 1 (for shift)
    # ADX now uses static period of 14
    min_startup = max(
        strategy_config.slow_length + strategy_config.signal_length + 1,
        14 + 1,  # ADX now uses static period of 14
        strategy_config.startup_candle_count
    )

    # Check that indicator calculations don't produce NaN values after adjusted startup period
    for col in expected_columns:
        # Skip boolean columns for NaN check
        if col not in ['uptrend', 'downtrend']:
            assert not df[col].iloc[
                       min_startup:].isna().any(), f"Column {col} contains NaN values after adjusted startup period"


@pytest.mark.parametrize('mode,expected_fast,expected_slow,expected_signal', [
    (StrategyMode.TIMEFRAME_5M, 12, 26, 9),  # 5m uses "classic" preset
    (StrategyMode.TIMEFRAME_1M, 5, 13, 3),  # 1m uses "responsive" preset
    (StrategyMode.TIMEFRAME_30M, 10, 34, 8)  # 30m uses "delayed" preset with fast_length override
])
def test_calculate_indicators_with_macd_presets(sample_dataframe, mock_config_file, mode, expected_fast, expected_slow,
                                                expected_signal):
    """Test that indicators are correctly calculated using MACD preset parameters"""
    # Create config parser and strategy config with the specified mode
    config_parser = ConfigParser(config_path=mock_config_file)
    strategy_config = StrategyConfig(mode=mode, config_parser=config_parser)

    # Verify the strategy config has the expected MACD parameters from the preset
    assert strategy_config.fast_length == expected_fast
    assert strategy_config.slow_length == expected_slow
    assert strategy_config.signal_length == expected_signal

    # Verify the preset name is stored
    assert hasattr(strategy_config, 'macd_preset_str')

    # Calculate indicators
    df = calculate_indicators(sample_dataframe, strategy_config)

    # Check that MACD columns are present
    assert 'macd' in df.columns
    assert 'macdsignal' in df.columns

    # Additional verification that MACD is calculated correctly
    # We can't directly check values without mocking talib, but we can check
    # for consistency and that values aren't all identical (a common error)
    assert not df['macd'].iloc[strategy_config.startup_candle_count:].equals(
        df['macdsignal'].iloc[strategy_config.startup_candle_count:])

    # Verify there are some crossovers (another sanity check)
    macd_above_signal = df['macd'] > df['macdsignal']
    crossover_count = (macd_above_signal != macd_above_signal.shift(1)).sum()
    assert crossover_count > 0, "No MACD crossovers found; indicator calculation may be incorrect"


def test_populate_entry_signals(sample_dataframe, strategy_config):
    """Test that entry signals are correctly generated"""
    # First calculate indicators
    df = calculate_indicators(sample_dataframe, strategy_config)

    # Then generate entry signals
    df = populate_entry_signals(df)

    # Check that signal columns are present
    assert 'enter_long' in df.columns
    assert 'enter_short' in df.columns
    assert 'enter_tag' in df.columns

    # Check that signals are binary (0 or 1)
    assert set(df['enter_long'].unique()).issubset({0, 1})
    assert set(df['enter_short'].unique()).issubset({0, 1})

    # Check that long signals have the correct tag
    assert all(df.loc[df['enter_long'] == 1, 'enter_tag'] == 'macd_uptrend_long')

    # Check that short signals have the correct tag
    assert all(df.loc[df['enter_short'] == 1, 'enter_tag'] == 'macd_downtrend_short')