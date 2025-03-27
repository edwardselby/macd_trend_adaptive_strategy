import talib.abstract as ta
from pandas import DataFrame


def calculate_indicators(dataframe: DataFrame, config) -> DataFrame:
    """Calculate all technical indicators needed for the strategy"""

    # Calculate MACD
    macd = ta.MACD(
        dataframe,
        fastperiod=config.fast_length,
        slowperiod=config.slow_length,
        signalperiod=config.signal_length
    )

    # Store MACD components and previous values
    dataframe['macd'] = macd['macd']
    dataframe['macdsignal'] = macd['macdsignal']
    dataframe['macd_prev'] = dataframe['macd'].shift(1)
    dataframe['macdsignal_prev'] = dataframe['macdsignal'].shift(1)

    # Add Trend Detection Indicators
    dataframe['ema_fast'] = ta.EMA(dataframe, timeperiod=config.ema_fast)
    dataframe['ema_slow'] = ta.EMA(dataframe, timeperiod=config.ema_slow)

    # Use adx_period from config (which defaults to 14 if not specified)
    adx_period = getattr(config, 'adx_period', 14)  # Fallback to 14 if not found
    dataframe['adx'] = ta.ADX(dataframe, timeperiod=adx_period)
    dataframe['plus_di'] = ta.PLUS_DI(dataframe, timeperiod=adx_period)
    dataframe['minus_di'] = ta.MINUS_DI(dataframe, timeperiod=adx_period)

    # Determine trend conditions
    dataframe['uptrend'] = (
        ((dataframe['adx'] > config.adx_threshold) & (dataframe['plus_di'] > dataframe['minus_di'])) &
        (dataframe['ema_fast'] > dataframe['ema_slow'])
    )

    dataframe['downtrend'] = (
        ((dataframe['adx'] > config.adx_threshold) & (dataframe['minus_di'] > dataframe['plus_di'])) &
        (dataframe['ema_fast'] < dataframe['ema_slow'])
    )

    return dataframe


def populate_entry_signals(dataframe: DataFrame) -> DataFrame:
    """Define entry signals based on MACD crossovers and trend detection"""

    # Initialize signal columns
    dataframe['enter_long'] = 0
    dataframe['enter_short'] = 0
    dataframe['enter_tag'] = ''

    # LONG: MACD crosses above signal AND in uptrend
    long_condition = (
        (dataframe['macd_prev'] < dataframe['macdsignal_prev']) &
        (dataframe['macd'] > dataframe['macdsignal']) &
        (dataframe['uptrend']) &
        (dataframe['volume'] > 0)
    )

    # SHORT: MACD crosses below signal AND in downtrend
    short_condition = (
        (dataframe['macd_prev'] > dataframe['macdsignal_prev']) &
        (dataframe['macd'] < dataframe['macdsignal']) &
        (dataframe['downtrend']) &
        (dataframe['volume'] > 0)
    )

    # Apply conditions
    dataframe.loc[long_condition, 'enter_long'] = 1
    dataframe.loc[long_condition, 'enter_tag'] = 'macd_uptrend_long'

    dataframe.loc[short_condition, 'enter_short'] = 1
    dataframe.loc[short_condition, 'enter_tag'] = 'macd_downtrend_short'

    return dataframe