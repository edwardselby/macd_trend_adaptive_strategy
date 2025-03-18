from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from freqtrade.enums.exittype import ExitType

from macd_trend_adaptive_strategy.utils import create_trade_id
from strategy import MACDTrendAdaptiveStrategy


@pytest.fixture
def strategy_config():
    return {
        'user_data_dir': '/tmp',
        'runmode': 'dry_run'
    }


@pytest.fixture
def strategy(strategy_config):
    return MACDTrendAdaptiveStrategy(strategy_config)


def test_strategy_initialization(strategy):
    """Test that strategy initializes correctly with all components"""
    assert strategy.strategy_config is not None
    assert strategy.db_handler is not None
    assert strategy.performance_tracker is not None
    assert strategy.regime_detector is not None
    assert strategy.roi_calculator is not None
    assert strategy.stoploss_calculator is not None
    assert strategy.trade_cache is not None

    # Check that strategy configurations are correctly applied
    assert strategy.timeframe == strategy.strategy_config.timeframe
    assert strategy.stoploss == strategy.strategy_config.static_stoploss
    assert strategy.startup_candle_count == strategy.strategy_config.startup_candle_count


def test_populate_indicators(strategy, sample_dataframe):
    """Test that indicators are correctly populated in the dataframe"""
    df = strategy.populate_indicators(sample_dataframe, {})

    # Check that all required indicator columns are present
    required_indicators = [
        'macd', 'macdsignal', 'ema_fast', 'ema_slow', 'adx',
        'uptrend', 'downtrend'
    ]

    for indicator in required_indicators:
        assert indicator in df.columns


def test_populate_entry_trend(strategy, sample_dataframe):
    """Test that entry signals are correctly generated"""
    # First populate indicators
    df = strategy.populate_indicators(sample_dataframe, {})

    # Then generate entry signals
    df = strategy.populate_entry_trend(df, {})

    # Check that signal columns are present
    assert 'enter_long' in df.columns
    assert 'enter_short' in df.columns
    assert 'enter_tag' in df.columns


def test_confirm_trade_entry(strategy, mock_db_handler):
    """Test confirm_trade_entry method"""
    # Setup
    pair = "BTC/USDT"
    order_type = "limit"
    amount = 0.1
    rate = 20000
    time_in_force = "GTC"
    current_time = datetime.now()
    entry_tag = "macd_uptrend_long"
    side = "buy"  # Long trade

    # Call method
    result = strategy.confirm_trade_entry(
        pair, order_type, amount, rate, time_in_force,
        current_time, entry_tag, side
    )

    # Verify result is True
    assert result is True

    # Check trade was added to cache
    trade_id = f"{pair}_{current_time.timestamp()}"
    assert trade_id in strategy.trade_cache['active_trades']

    # Check cache entry has correct values
    cache_entry = strategy.trade_cache['active_trades'][trade_id]
    assert cache_entry['direction'] == 'long'
    assert cache_entry['entry_rate'] == rate
    assert cache_entry['roi'] > 0
    assert cache_entry['stoploss'] < 0
    assert cache_entry['regime'] in ["bullish", "bearish", "neutral"]


def test_should_exit_stoploss_hit(strategy, mock_trade):
    """Test custom_stoploss method when stoploss is hit"""
    # Setup
    mock_trade.pair = "BTC/USDT"
    mock_trade.open_rate = 20000
    mock_trade.open_date_utc = datetime.now()
    mock_trade.is_short = False

    # Configure calc_profit_ratio to return specific values based on rate
    def calc_profit_ratio(rate):
        if rate == 19400:
            return -0.03  # 3% loss at stoploss price
        elif rate == 19500:
            return -0.025  # 2.5% loss at price above stoploss - still below ROI target
        else:
            return (rate - mock_trade.open_rate) / mock_trade.open_rate

    mock_trade.calc_profit_ratio = calc_profit_ratio

    # Add trade to cache
    trade_id = f"{mock_trade.pair}_{mock_trade.open_date_utc.timestamp()}"
    strategy.trade_cache['active_trades'][trade_id] = {
        'direction': 'long',
        'entry_rate': mock_trade.open_rate,
        'roi': 0.05,
        'stoploss': -0.03,
        'stoploss_price': 19400,  # 3% below entry
        'is_counter_trend': False,
        'is_aligned_trend': True,
        'regime': 'bullish',
        'last_updated': int(datetime.now().timestamp())
    }

    # Test the stoploss value from custom_stoploss
    current_time = datetime.now()
    current_profit = -0.03
    stoploss = strategy.custom_stoploss(mock_trade.pair, mock_trade, current_time, 19400, current_profit)

    # Should return the correct stoploss value
    assert stoploss == -0.03

    # Confirm that should_exit doesn't return a stoploss signal
    exit_signals = strategy.should_exit(mock_trade, 19400, current_time)
    assert len(exit_signals) == 0


def test_should_exit_roi_hit(strategy, mock_trade):
    """Test should_exit method when ROI target is hit"""
    # Setup
    mock_trade.pair = "BTC/USDT"
    mock_trade.open_rate = 20000
    mock_trade.open_date_utc = datetime.now()
    mock_trade.is_short = False

    # Add trade to cache
    trade_id = f"{mock_trade.pair}_{mock_trade.open_date_utc.timestamp()}"
    target_roi = 0.05  # 5% ROI target
    strategy.trade_cache['active_trades'][trade_id] = {
        'direction': 'long',
        'entry_rate': mock_trade.open_rate,
        'roi': target_roi,
        'stoploss': -0.03,
        'stoploss_price': 19400,  # 3% below entry
        'is_counter_trend': False,
        'is_aligned_trend': True,
        'regime': 'bullish',
        'last_updated': int(datetime.now().timestamp())
    }

    # Mock profit ratio to be at ROI target
    mock_trade.calc_profit_ratio = lambda x: target_roi

    # Test with price at ROI target
    exit_signals = strategy.should_exit(mock_trade, 21000, datetime.now())

    # Should return an ROI exit signal
    assert len(exit_signals) == 1
    assert exit_signals[0].exit_type == ExitType.ROI
    assert "adaptive_roi" in exit_signals[0].exit_reason

    # Test with price below ROI target
    mock_trade.calc_profit_ratio = lambda x: target_roi - 0.01  # 4% profit
    exit_signals = strategy.should_exit(mock_trade, 20800, datetime.now())

    # Should not exit
    assert len(exit_signals) == 0


def test_should_exit_default_roi(strategy, mock_trade):
    """Test should_exit method when default ROI is hit"""
    # Setup
    mock_trade.pair = "BTC/USDT"
    mock_trade.open_rate = 20000
    mock_trade.open_date_utc = datetime.now()
    mock_trade.is_short = False

    # Make sure default ROI exit is enabled
    strategy.strategy_config.use_default_roi_exit = True

    # Set the default ROI to a value below the adaptive ROI
    strategy.strategy_config.default_roi = 0.04

    # Add trade to cache
    trade_id = f"{mock_trade.pair}_{mock_trade.open_date_utc.timestamp()}"
    strategy.trade_cache['active_trades'][trade_id] = {
        'direction': 'long',
        'entry_rate': mock_trade.open_rate,
        'roi': 0.05,  # Adaptive ROI at 5%
        'stoploss': -0.03,
        'stoploss_price': 19400,
        'is_counter_trend': False,
        'is_aligned_trend': True,
        'regime': 'bullish',
        'last_updated': int(datetime.now().timestamp())
    }

    # Mock profit ratio to be above default ROI but below adaptive ROI
    # Default ROI is 4%, adaptive ROI is 5%, so let's set profit at 4.5%
    mock_trade.calc_profit_ratio = lambda x: 0.045

    # Test with price at default ROI target
    exit_signals = strategy.should_exit(mock_trade, 21000, datetime.now())

    # Should exit with default_roi reason
    assert len(exit_signals) == 1
    assert exit_signals[0].exit_type == ExitType.ROI
    assert exit_signals[0].exit_reason == "default_roi"

    # Now test with default ROI exit disabled
    strategy.strategy_config.use_default_roi_exit = False
    exit_signals = strategy.should_exit(mock_trade, 21000, datetime.now())

    # Should not exit
    assert len(exit_signals) == 0


def test_confirm_trade_exit(strategy, mock_trade):
    """Test confirm_trade_exit method"""
    # Setup
    pair = "BTC/USDT"
    order_type = "limit"
    amount = 0.1
    rate = 21000  # 5% profit
    time_in_force = "GTC"
    exit_reason = "roi"
    current_time = datetime.now()

    # Add trade to cache
    trade_id = f"{pair}_{mock_trade.open_date_utc.timestamp()}"
    strategy.trade_cache['active_trades'][trade_id] = {
        'direction': 'long',
        'entry_rate': mock_trade.open_rate,
        'roi': 0.05,
        'stoploss': -0.03,
        'stoploss_price': 19400,
        'is_counter_trend': False,
        'is_aligned_trend': True,
        'regime': 'bullish',
        'last_updated': int(datetime.now().timestamp())
    }

    # Set up performance tracker to track the update
    strategy.performance_tracker.update_performance = MagicMock()

    # Call method
    result = strategy.confirm_trade_exit(
        pair, mock_trade, order_type, amount, rate,
        time_in_force, exit_reason, current_time
    )

    # Verify result is True
    assert result is True

    # Check performance tracker was updated
    strategy.performance_tracker.update_performance.assert_called_once()

    # Check trade was removed from cache
    assert trade_id not in strategy.trade_cache['active_trades']


def test_custom_stoploss(strategy, mock_trade):
    """Test custom_stoploss method"""
    # Setup
    pair = "BTC/USDT"
    current_time = datetime.now()
    current_rate = 20500
    current_profit = 0.025

    # Add trade to cache
    trade_id = f"{pair}_{mock_trade.open_date_utc.timestamp()}"
    expected_stoploss = -0.03
    strategy.trade_cache['active_trades'][trade_id] = {
        'direction': 'long',
        'entry_rate': mock_trade.open_rate,
        'roi': 0.05,
        'stoploss': expected_stoploss,
        'stoploss_price': 19400,
        'is_counter_trend': False,
        'is_aligned_trend': True,
        'regime': 'bullish',
        'last_updated': int(current_time.timestamp())
    }

    # Call method with trade in cache
    stoploss = strategy.custom_stoploss(
        pair, mock_trade, current_time, current_rate, current_profit
    )

    # Verify stoploss value for cached trade
    assert stoploss == expected_stoploss

    # Test with trade not in cache
    strategy.trade_cache['active_trades'] = {}

    # Should calculate a fresh stoploss value
    stoploss = strategy.custom_stoploss(
        pair, mock_trade, current_time, current_rate, current_profit
    )

    # Verify calculated stoploss is reasonable
    assert stoploss < 0  # Should be negative
    assert strategy.strategy_config.max_stoploss <= stoploss <= strategy.strategy_config.min_stoploss

    # Verify trade added to cache
    recalculated_trade_id = create_trade_id(pair, mock_trade.open_date_utc)
    assert recalculated_trade_id in strategy.trade_cache['active_trades']
    assert 'stoploss' in strategy.trade_cache['active_trades'][recalculated_trade_id]


def test_custom_stoploss_long(strategy, mock_trade):
    """Test custom_stoploss method for long positions"""
    # Setup
    pair = "BTC/USDT"
    current_time = datetime.now()
    current_rate = 20500
    current_profit = 0.025

    # Configure as a long trade
    mock_trade.is_short = False

    # Clear cache to force recalculation
    strategy.trade_cache['active_trades'] = {}

    # Calculate stoploss
    stoploss = strategy.custom_stoploss(
        pair, mock_trade, current_time, current_rate, current_profit
    )

    # Verify bounds
    assert strategy.strategy_config.max_stoploss <= stoploss <= strategy.strategy_config.min_stoploss

    # Verify stoploss price is calculated correctly
    stoploss_price = strategy.stoploss_calculator.calculate_stoploss_price(
        mock_trade.open_rate, stoploss, mock_trade.is_short
    )
    assert stoploss_price < mock_trade.open_rate  # For longs, stoploss price should be below entry


def test_custom_stoploss_short(strategy, mock_short_trade):
    """Test custom_stoploss method for short positions"""
    # Setup
    pair = "BTC/USDT"
    current_time = datetime.now()
    current_rate = 20500
    current_profit = 0.025

    # Configure as a short trade
    mock_short_trade.is_short = True

    # Clear cache to force recalculation
    strategy.trade_cache['active_trades'] = {}

    # Calculate stoploss
    stoploss = strategy.custom_stoploss(
        pair, mock_short_trade, current_time, current_rate, current_profit
    )

    # Verify bounds
    assert strategy.strategy_config.max_stoploss <= stoploss <= strategy.strategy_config.min_stoploss

    # Verify stoploss price is calculated correctly
    stoploss_price = strategy.stoploss_calculator.calculate_stoploss_price(
        mock_short_trade.open_rate, stoploss, mock_short_trade.is_short
    )
    assert stoploss_price > mock_short_trade.open_rate  # For shorts, stoploss price should be above entry


def test_leverage(strategy):
    """Test leverage method"""
    # Call the method with various parameters
    leverage = strategy.leverage(
        "BTC/USDT", datetime.now(), 20000, 1.0, 10.0, "entry_tag", "buy"
    )

    # Should return fixed leverage value
    assert leverage == 10.0


def test_custom_stake_amount(strategy):
    """Test custom_stake_amount method"""
    # Setup
    pair = "BTC/USDT"
    current_time = datetime.now()
    current_rate = 20000
    proposed_stake = 100
    min_stake = 10
    max_stake = 1000
    entry_tag = "entry_tag"
    side = "buy"

    # Call method
    stake = strategy.custom_stake_amount(
        pair, current_time, current_rate, proposed_stake,
        min_stake, max_stake, entry_tag, side
    )

    # Should return the proposed stake
    assert stake == proposed_stake


def test_stoploss_values_in_cache(strategy, mock_trade, mock_short_trade):
    """
    Test that stoploss values are correctly calculated and stored in cache
    when new trades are initialized.
    """
    # Setup test parameters
    pair = "BTC/USDT"
    entry_rate = 20000
    current_time = datetime.now()

    # Configure mock trades
    mock_trade.pair = pair
    mock_trade.open_rate = entry_rate
    mock_trade.open_date_utc = current_time
    mock_trade.is_short = False

    mock_short_trade.pair = pair
    mock_short_trade.open_rate = entry_rate
    # Use a different time for the short trade to avoid key collisions
    short_time = current_time + timedelta(seconds=1)
    mock_short_trade.open_date_utc = short_time
    mock_short_trade.is_short = True

    # Initialize trades in strategy
    strategy.confirm_trade_entry(
        pair, "limit", 0.1, entry_rate, "GTC",
        current_time, "test_entry", "buy"
    )

    strategy.confirm_trade_entry(
        pair, "limit", 0.1, entry_rate, "GTC",
        short_time, "test_entry", "sell"
    )

    # Get trade IDs and retrieve cache entries
    long_trade_id = create_trade_id(pair, current_time)
    short_trade_id = create_trade_id(pair, short_time)

    assert long_trade_id in strategy.trade_cache['active_trades'], "Long trade not in cache"
    assert short_trade_id in strategy.trade_cache['active_trades'], "Short trade not in cache"

    long_cache = strategy.trade_cache['active_trades'][long_trade_id]
    short_cache = strategy.trade_cache['active_trades'][short_trade_id]

    # Verify stoploss is correctly calculated
    assert long_cache['stoploss'] < 0, "Long stoploss should be negative"
    assert short_cache['stoploss'] < 0, "Short stoploss should be negative"

    # Verify stoploss prices are calculated correctly
    assert long_cache['stoploss_price'] < entry_rate, "Long stoploss price should be below entry"
    assert short_cache['stoploss_price'] > entry_rate, "Short stoploss price should be above entry"

    # Verify stoploss percentage and price correlate correctly
    expected_long_price = entry_rate * (1 + long_cache['stoploss'])
    expected_short_price = entry_rate * (1 - short_cache['stoploss'])

    assert abs(long_cache['stoploss_price'] - expected_long_price) < 0.01, "Long stoploss price calculation mismatch"
    assert abs(short_cache['stoploss_price'] - expected_short_price) < 0.01, "Short stoploss price calculation mismatch"


def test_custom_stoploss_returns_correct_values(strategy, mock_trade, mock_short_trade):
    """
    Test that custom_stoploss method returns the correct stoploss values from cache
    and correctly calculates stoploss at the actual stoploss price.
    """
    # Setup test parameters
    pair = "BTC/USDT"
    entry_rate = 20000
    current_time = datetime.now()

    # Configure mock trades
    mock_trade.pair = pair
    mock_trade.open_rate = entry_rate
    mock_trade.open_date_utc = current_time
    mock_trade.is_short = False

    mock_short_trade.pair = pair
    mock_short_trade.open_rate = entry_rate
    short_time = current_time + timedelta(seconds=1)
    mock_short_trade.open_date_utc = short_time
    mock_short_trade.is_short = True

    # Configure profit calculation
    def long_profit(rate):
        return (rate - entry_rate) / entry_rate

    def short_profit(rate):
        return (entry_rate - rate) / entry_rate

    mock_trade.calc_profit_ratio = long_profit
    mock_short_trade.calc_profit_ratio = short_profit

    # Initialize trades in strategy
    strategy.confirm_trade_entry(
        pair, "limit", 0.1, entry_rate, "GTC",
        current_time, "test_entry", "buy"
    )

    strategy.confirm_trade_entry(
        pair, "limit", 0.1, entry_rate, "GTC",
        short_time, "test_entry", "sell"
    )

    # Get trade IDs and cache entries
    long_trade_id = create_trade_id(pair, current_time)
    short_trade_id = create_trade_id(pair, short_time)

    long_cache = strategy.trade_cache['active_trades'][long_trade_id]
    short_cache = strategy.trade_cache['active_trades'][short_trade_id]

    # Test long trade at stoploss price
    long_sl_price = long_cache['stoploss_price']
    current_profit_at_sl = long_profit(long_sl_price)

    # Verify custom_stoploss returns the expected value at the stoploss price
    long_sl_value = strategy.custom_stoploss(
        pair, mock_trade, current_time, long_sl_price, current_profit_at_sl
    )

    # The returned stoploss value should match what's in the cache
    assert abs(long_sl_value - long_cache['stoploss']) < 0.0001, \
        f"Returned stoploss value ({long_sl_value:.4f}) should match cached value ({long_cache['stoploss']:.4f})"

    # Verify that profit at stoploss price matches the expected stoploss percentage
    assert abs(current_profit_at_sl - long_cache['stoploss']) < 0.0001, \
        f"Profit at SL price ({current_profit_at_sl:.4f}) should match stoploss value ({long_cache['stoploss']:.4f})"

    # Test short trade at stoploss price
    short_sl_price = short_cache['stoploss_price']
    current_profit_at_sl = short_profit(short_sl_price)

    # Verify custom_stoploss returns the expected value at the stoploss price
    short_sl_value = strategy.custom_stoploss(
        pair, mock_short_trade, short_time, short_sl_price, current_profit_at_sl
    )

    # The returned stoploss value should match what's in the cache
    assert abs(short_sl_value - short_cache['stoploss']) < 0.0001, \
        f"Returned stoploss value ({short_sl_value:.4f}) should match cached value ({short_cache['stoploss']:.4f})"

    # Verify that profit at stoploss price matches the expected stoploss percentage
    assert abs(current_profit_at_sl - short_cache['stoploss']) < 0.0001, \
        f"Profit at SL price ({current_profit_at_sl:.4f}) should match stoploss value ({short_cache['stoploss']:.4f})"


def test_stoploss_in_neutral_regime(strategy, mock_trade, mock_short_trade):
    """
    Test that stoploss values are symmetric for long and short trades in a neutral regime.
    """
    # Setup test parameters
    pair = "BTC/USDT"
    entry_rate = 20000
    current_time = datetime.now()

    # Force regime detector to return neutral to eliminate alignment factors
    strategy.regime_detector.detect_regime = lambda: "neutral"
    strategy.regime_detector.is_counter_trend = lambda x: False
    strategy.regime_detector.is_aligned_trend = lambda x: False

    # Ensure ROI calculations are symmetrical by disabling any long_roi_boost
    strategy.strategy_config.long_roi_boost = 0.0

    # Configure mock trades
    mock_trade.pair = pair
    mock_trade.open_rate = entry_rate
    mock_trade.open_date_utc = current_time
    mock_trade.is_short = False

    mock_short_trade.pair = pair
    mock_short_trade.open_rate = entry_rate
    short_time = current_time + timedelta(seconds=1)
    mock_short_trade.open_date_utc = short_time
    mock_short_trade.is_short = True

    # Initialize trades in strategy
    strategy.trade_cache['active_trades'] = {}
    strategy.confirm_trade_entry(
        pair, "limit", 0.1, entry_rate, "GTC",
        current_time, "test_entry", "buy"
    )

    strategy.confirm_trade_entry(
        pair, "limit", 0.1, entry_rate, "GTC",
        short_time, "test_entry", "sell"
    )

    # Get trade IDs and cache entries
    long_trade_id = create_trade_id(pair, current_time)
    short_trade_id = create_trade_id(pair, short_time)

    long_cache = strategy.trade_cache['active_trades'][long_trade_id]
    short_cache = strategy.trade_cache['active_trades'][short_trade_id]

    # In neutral regime, long and short stoploss should be identical
    assert abs(abs(long_cache['stoploss']) - abs(short_cache['stoploss'])) < 0.0001, \
        f"Long and short stoploss should be identical in neutral regime, but got " \
        f"long: {long_cache['stoploss']:.4f}, short: {short_cache['stoploss']:.4f}"

    # Verify stoploss prices reflect the opposite directions
    assert long_cache['stoploss_price'] < entry_rate, "Long stoploss price should be below entry"
    assert short_cache['stoploss_price'] > entry_rate, "Short stoploss price should be above entry"

    # Calculate percentage distance from entry to stoploss price
    long_distance = (entry_rate - long_cache['stoploss_price']) / entry_rate
    short_distance = (short_cache['stoploss_price'] - entry_rate) / entry_rate

    # The percentage distance should be very close for both directions
    assert abs(long_distance - short_distance) < 0.0001, \
        f"Percentage distance to stoploss should be similar, but got " \
        f"long: {long_distance:.4f}, short: {short_distance:.4f}"

def test_stoploss_for_counter_and_aligned_trends(strategy, mock_trade, mock_short_trade):
    """
    Test that stoploss values are adjusted correctly based on trend alignment.

    Counter-trend trades should have tighter stoploss (less negative/closer to zero)
    Aligned-trend trades should have looser stoploss (more negative/further from zero)
    """
    # Setup test parameters
    pair = "BTC/USDT"
    entry_rate = 20000
    current_time = datetime.now()

    # === FORCE CONFIG VALUES FOR THIS TEST ===
    # Override the factor values directly in the config for this test
    # This ensures the test uses the intended values regardless of what's in the config
    strategy.strategy_config.counter_trend_stoploss_factor = 0.8
    strategy.strategy_config.aligned_trend_stoploss_factor = 1.2

    # Get the actual factor values for validation and logging
    counter_factor = strategy.strategy_config.counter_trend_stoploss_factor
    aligned_factor = strategy.strategy_config.aligned_trend_stoploss_factor

    # For this test to work reliably, counter_factor should be < aligned_factor
    assert counter_factor < aligned_factor, \
        f"For tighter counter-trend stoploss, counter_factor ({counter_factor}) " \
        f"should be less than aligned_factor ({aligned_factor})"

    # ========== TEST BULLISH REGIME ==========
    # Force a bullish regime
    strategy.regime_detector.detect_regime = lambda: "bullish"
    # In bullish regime, long trades are aligned, short trades are counter-trend
    strategy.regime_detector.is_counter_trend = lambda direction: direction == "short"
    strategy.regime_detector.is_aligned_trend = lambda direction: direction == "long"

    # Configure mock trades
    mock_trade.pair = pair
    mock_trade.open_rate = entry_rate
    mock_trade.open_date_utc = current_time
    mock_trade.is_short = False

    mock_short_trade.pair = pair
    mock_short_trade.open_rate = entry_rate
    short_time = current_time + timedelta(seconds=1)
    mock_short_trade.open_date_utc = short_time
    mock_short_trade.is_short = True

    # Initialize trades in strategy
    strategy.trade_cache['active_trades'] = {}
    strategy.confirm_trade_entry(
        pair, "limit", 0.1, entry_rate, "GTC",
        current_time, "test_entry", "buy"
    )

    strategy.confirm_trade_entry(
        pair, "limit", 0.1, entry_rate, "GTC",
        short_time, "test_entry", "sell"
    )

    # Get trade IDs and cache entries
    long_trade_id = create_trade_id(pair, current_time)
    short_trade_id = create_trade_id(pair, short_time)

    long_cache = strategy.trade_cache['active_trades'][long_trade_id]
    short_cache = strategy.trade_cache['active_trades'][short_trade_id]

    # Verify stoploss values for each direction
    long_stoploss = abs(long_cache['stoploss'])  # Long/aligned should be larger/more negative
    short_stoploss = abs(short_cache['stoploss'])  # Short/counter should be smaller/less negative

    # Counter-trend should have tighter stoploss (less negative) than aligned-trend
    assert short_stoploss < long_stoploss, \
        f"Counter-trend stoploss should be tighter than aligned-trend stoploss, but got " \
        f"counter (short): {short_cache['stoploss']:.4f}, aligned (long): {long_cache['stoploss']:.4f}"

    # Verify stoploss prices are correctly calculated based on the percentages
    long_sl_price = long_cache['stoploss_price']
    short_sl_price = short_cache['stoploss_price']

    # Long stoploss price should be below entry price
    assert long_sl_price < entry_rate, \
        f"Long stoploss price ({long_sl_price}) should be below entry price ({entry_rate})"

    # Short stoploss price should be above entry price
    assert short_sl_price > entry_rate, \
        f"Short stoploss price ({short_sl_price}) should be above entry price ({entry_rate})"

    # ========== TEST BEARISH REGIME ==========
    # Now force a bearish regime and test the opposite
    strategy.regime_detector.detect_regime = lambda: "bearish"
    # In bearish regime, short trades are aligned, long trades are counter-trend
    strategy.regime_detector.is_counter_trend = lambda direction: direction == "long"
    strategy.regime_detector.is_aligned_trend = lambda direction: direction == "short"

    # Initialize trades in strategy
    strategy.trade_cache['active_trades'] = {}
    strategy.confirm_trade_entry(
        pair, "limit", 0.1, entry_rate, "GTC",
        current_time, "test_entry", "buy"
    )

    strategy.confirm_trade_entry(
        pair, "limit", 0.1, entry_rate, "GTC",
        short_time, "test_entry", "sell"
    )

    # Get updated cache entries
    long_cache = strategy.trade_cache['active_trades'][long_trade_id]
    short_cache = strategy.trade_cache['active_trades'][short_trade_id]

    # Verify stoploss values for each direction
    long_stoploss = abs(long_cache['stoploss'])  # Long/counter should be smaller/less negative
    short_stoploss = abs(short_cache['stoploss'])  # Short/aligned should be larger/more negative

    # Now long is counter-trend, short is aligned
    assert long_stoploss < short_stoploss, \
        f"Counter-trend stoploss should be tighter than aligned-trend stoploss, but got " \
        f"counter (long): {long_cache['stoploss']:.4f}, aligned (short): {short_cache['stoploss']:.4f}"

    # Verify stoploss prices are correctly calculated based on the percentages
    long_sl_price = long_cache['stoploss_price']
    short_sl_price = short_cache['stoploss_price']

    # Long stoploss price should be below entry price (but closer than in bullish regime)
    assert long_sl_price < entry_rate, \
        f"Long stoploss price ({long_sl_price}) should be below entry price ({entry_rate})"

    # Short stoploss price should be above entry price (but further than in bullish regime)
    assert short_sl_price > entry_rate, \
        f"Short stoploss price ({short_sl_price}) should be above entry price ({entry_rate})"

def test_stoploss_recalculation_on_cache_miss(strategy, mock_trade):
    """
    Test that stoploss is correctly recalculated when a trade is not in the cache.
    """
    # Setup test parameters
    pair = "BTC/USDT"
    entry_rate = 20000
    current_time = datetime.now()

    # Configure mock trade
    mock_trade.pair = pair
    mock_trade.open_rate = entry_rate
    mock_trade.open_date_utc = current_time
    mock_trade.is_short = False

    # Configure profit calculation
    mock_trade.calc_profit_ratio = lambda rate: (rate - entry_rate) / entry_rate

    # Clear the cache to force recalculation
    strategy.trade_cache['active_trades'] = {}

    # Call custom_stoploss with a specific profit level
    test_profit = -0.02
    test_price = entry_rate * (1 + test_profit)  # Price that would give -2% profit

    recalculated_sl = strategy.custom_stoploss(
        pair, mock_trade, current_time, test_price, test_profit
    )

    # The stoploss should be recalculated and returned
    assert recalculated_sl < 0, "Recalculated stoploss should be negative"

    # Verify trade was added back to cache
    trade_id = create_trade_id(pair, mock_trade.open_date_utc)
    assert trade_id in strategy.trade_cache['active_trades'], "Trade should be recreated in cache"
    assert strategy.trade_cache['active_trades'][trade_id]['stoploss'] == recalculated_sl, \
        "Cached stoploss should match returned value"

    # Verify stoploss price is correctly calculated
    stoploss_price = strategy.trade_cache['active_trades'][trade_id]['stoploss_price']
    expected_price = entry_rate * (1 + recalculated_sl)

    assert abs(stoploss_price - expected_price) < 0.01, \
        f"Stoploss price ({stoploss_price}) should match calculation from percentage ({expected_price})"

    # Call custom_stoploss again with the same trade - should use cached value
    cached_sl = strategy.custom_stoploss(
        pair, mock_trade, current_time, test_price, test_profit
    )

    # Should return the same value as before
    assert cached_sl == recalculated_sl, \
        f"Subsequent call should return cached value ({recalculated_sl}), but got {cached_sl}"


def test_strategy_backtest_initialization():
    """Test that strategy properly clears performance data when initializing in backtest mode"""
    from strategy import MACDTrendAdaptiveStrategy

    # Create a mock config with backtest mode
    config = {
        'user_data_dir': '/tmp',
        'runmode': 'backtest'
    }

    # Mock the DBHandler to verify it's called correctly
    with patch('strategy.DBHandler') as mock_db_handler_class:
        # Create mock instances
        mock_db_handler = MagicMock()
        mock_db_handler_class.return_value = mock_db_handler

        # Create the strategy instance
        strategy = MACDTrendAdaptiveStrategy(config)

        # Verify DBHandler was initialized
        mock_db_handler_class.assert_called_once_with(config)

        # Verify set_strategy_name was called with correct name
        mock_db_handler.set_strategy_name.assert_called_once_with('MACDTrendAdaptiveStrategy')

        # Verify clear_performance_data was called
        mock_db_handler.clear_performance_data.assert_called_once()
