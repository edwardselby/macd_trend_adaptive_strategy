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
    min_startup = max(
        strategy_config.slow_length + strategy_config.signal_length + 1,
        strategy_config.adx_period + 1,  # ADX also needs a period
        strategy_config.startup_candle_count
    )

    # Check that indicator calculations don't produce NaN values after adjusted startup period
    for col in expected_columns:
        # Skip boolean columns for NaN check
        if col not in ['uptrend', 'downtrend']:
            assert not df[col].iloc[
                       min_startup:].isna().any(), f"Column {col} contains NaN values after adjusted startup period"


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