from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from freqtrade.enums.exittype import ExitType
from freqtrade.persistence import Trade

from macd_trend_adaptive_strategy.utils import create_trade_id, get_direction
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


def test_should_exit_roi_hit(strategy, mock_trade):
    """Test should_exit method when ROI target is hit"""
    # Setup
    mock_trade.pair = "BTC/USDT"
    mock_trade.open_rate = 20000
    mock_trade.open_date_utc = datetime.now()
    mock_trade.is_short = False
    # Set the leverage attribute to 1.0 for testing
    mock_trade.leverage = 1.0

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

    # Configure profit calculation for this test
    def calc_profit_ratio(rate):
        return (rate - mock_trade.open_rate) / mock_trade.open_rate

    mock_trade.calc_profit_ratio = calc_profit_ratio

    # Test with price at ROI target
    roi_price = 21000  # 5% above entry
    exit_signals = strategy.should_exit(mock_trade, roi_price, datetime.now())

    # Should return an ROI exit signal
    assert len(exit_signals) == 1
    assert exit_signals[0].exit_type == ExitType.ROI
    assert "adaptive_roi" in exit_signals[0].exit_reason

    # Test with price below ROI target
    below_roi_price = 20800  # 4% above entry
    exit_signals = strategy.should_exit(mock_trade, below_roi_price, datetime.now())

    # Should not exit
    assert len(exit_signals) == 0


def test_should_exit_default_roi(strategy, mock_trade):
    """Test should_exit method when default ROI is hit"""
    # Setup
    mock_trade.pair = "BTC/USDT"
    mock_trade.open_rate = 20000
    mock_trade.open_date_utc = datetime.now()
    mock_trade.is_short = False
    mock_trade.leverage = 1.0  # Set leverage for testing

    # Make sure default ROI exit is enabled - MANUALLY ENABLE FOR THIS TEST
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

    # Configure profit calculation to be above default ROI but below adaptive ROI
    def calc_profit_ratio(rate):
        if rate == 20800:
            return 0.04  # Exactly at default ROI
        else:
            return (rate - mock_trade.open_rate) / mock_trade.open_rate

    mock_trade.calc_profit_ratio = calc_profit_ratio

    # Test with price at default ROI target
    exit_signals = strategy.should_exit(mock_trade, 20800, datetime.now())

    # Should exit with default_roi reason
    assert len(exit_signals) == 1
    assert exit_signals[0].exit_type == ExitType.ROI
    assert exit_signals[0].exit_reason == "default_roi"

    # Now test with default ROI exit disabled
    strategy.strategy_config.use_default_roi_exit = False
    exit_signals = strategy.should_exit(mock_trade, 20800, datetime.now())

    # Should not exit
    assert len(exit_signals) == 0

def test_should_exit_stoploss_hit(strategy, mock_trade):
    """Test should_exit method when stoploss is hit"""
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

    # Test at stoploss price (3% loss)
    current_time = datetime.now()
    stoploss_rate = 19400  # This price should trigger stoploss
    exit_signals = strategy.should_exit(mock_trade, stoploss_rate, current_time)

    # Should return stoploss exit signal
    assert len(exit_signals) == 1
    assert exit_signals[0].exit_type == ExitType.STOP_LOSS
    assert "stoploss_long" in exit_signals[0].exit_reason

    # Test with price slightly above stoploss (2.5% loss)
    better_price = 19500  # Price above stoploss
    exit_signals = strategy.should_exit(mock_trade, better_price, current_time)

    # Should not exit since we're not at stoploss yet and not at ROI
    assert len(exit_signals) == 0


def test_should_exit_short_stoploss_hit(strategy, mock_short_trade):
    """Test should_exit method for short trade stoploss"""
    # Setup
    mock_short_trade.pair = "BTC/USDT"
    mock_short_trade.open_rate = 20000
    mock_short_trade.open_date_utc = datetime.now()
    mock_short_trade.is_short = True

    # Configure profit calculation for short trade
    def calc_profit_ratio(rate):
        if rate == 20600:
            return -0.03  # 3% loss at stoploss price (price went up)
        else:
            # For shorts: profit = (entry - current) / entry
            return (mock_short_trade.open_rate - rate) / mock_short_trade.open_rate

    mock_short_trade.calc_profit_ratio = calc_profit_ratio

    # Add trade to cache
    trade_id = f"{mock_short_trade.pair}_{mock_short_trade.open_date_utc.timestamp()}"
    strategy.trade_cache['active_trades'][trade_id] = {
        'direction': 'short',
        'entry_rate': mock_short_trade.open_rate,
        'roi': 0.05,  # 5% ROI target for short
        'stoploss': -0.03,  # 3% stoploss
        'stoploss_price': 20600,  # 3% above entry for short
        'is_counter_trend': False,
        'is_aligned_trend': True,
        'regime': 'bearish',
        'last_updated': int(datetime.now().timestamp())
    }

    # Test at stoploss price (3% loss for short)
    current_time = datetime.now()
    stoploss_rate = 20600  # This price should trigger stoploss
    exit_signals = strategy.should_exit(mock_short_trade, stoploss_rate, current_time)

    # Should return stoploss exit signal
    assert len(exit_signals) == 1
    assert exit_signals[0].exit_type == ExitType.STOP_LOSS
    assert "stoploss_short" in exit_signals[0].exit_reason


def test_should_exit_short_roi_hit(strategy, mock_short_trade):
    """Test should_exit method for short trade ROI"""
    # Setup
    mock_short_trade.pair = "BTC/USDT"
    mock_short_trade.open_rate = 20000
    mock_short_trade.open_date_utc = datetime.now()
    mock_short_trade.is_short = True

    # Configure profit calculation for short trade
    def calc_profit_ratio(rate):
        # For shorts: profit = (entry - current) / entry
        return (mock_short_trade.open_rate - rate) / mock_short_trade.open_rate

    mock_short_trade.calc_profit_ratio = calc_profit_ratio

    # Add trade to cache
    trade_id = f"{mock_short_trade.pair}_{mock_short_trade.open_date_utc.timestamp()}"
    strategy.trade_cache['active_trades'][trade_id] = {
        'direction': 'short',
        'entry_rate': mock_short_trade.open_rate,
        'roi': 0.05,  # 5% ROI target for short
        'stoploss': -0.03,  # 3% stoploss
        'stoploss_price': 20600,
        'is_counter_trend': False,
        'is_aligned_trend': True,
        'regime': 'bearish',
        'last_updated': int(datetime.now().timestamp())
    }

    # Test at ROI price (5% profit for short)
    roi_price = 19000  # 5% below entry
    exit_signals = strategy.should_exit(mock_short_trade, roi_price, datetime.now())

    # Should return ROI exit signal
    assert len(exit_signals) == 1
    assert exit_signals[0].exit_type == ExitType.ROI
    assert "adaptive_roi" in exit_signals[0].exit_reason


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
        current_time, "test_entry", "long"
    )

    strategy.confirm_trade_entry(
        pair, "limit", 0.1, entry_rate, "GTC",
        short_time, "test_entry", "short"
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
        current_time, "test_entry", "long"
    )

    strategy.confirm_trade_entry(
        pair, "limit", 0.1, entry_rate, "GTC",
        short_time, "test_entry", "short"
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
        current_time, "test_entry", "long"
    )

    strategy.confirm_trade_entry(
        pair, "limit", 0.1, entry_rate, "GTC",
        short_time, "test_entry", "short"
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
        current_time, "test_entry", "long"
    )

    strategy.confirm_trade_entry(
        pair, "limit", 0.1, entry_rate, "GTC",
        short_time, "test_entry", "short"
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


def test_stoploss_vs_roi_precedence(strategy, mock_trade):
    """Test that stoploss has precedence over ROI when price is ambiguous"""
    # Setup a scenario where price would trigger both stoploss and ROI
    # This is an edge case that shouldn't happen in real trading
    mock_trade.pair = "BTC/USDT"
    mock_trade.open_rate = 20000
    mock_trade.open_date_utc = datetime.now()
    mock_trade.is_short = False

    # Configure a profit calculation function that would trigger both stoploss and ROI
    # This is artificial but helps test the precedence
    def calc_profit_ratio(rate):
        # Return a value exactly matching stoploss threshold
        return -0.03

    mock_trade.calc_profit_ratio = calc_profit_ratio

    # Add trade to cache with stoploss and ROI at same value
    # Again, this is artificial but helps test the logic
    trade_id = f"{mock_trade.pair}_{mock_trade.open_date_utc.timestamp()}"
    strategy.trade_cache['active_trades'][trade_id] = {
        'direction': 'long',
        'entry_rate': mock_trade.open_rate,
        'roi': -0.03,  # Set ROI equal to stoploss for testing precedence
        'stoploss': -0.03,
        'stoploss_price': 19400,
        'is_counter_trend': False,
        'is_aligned_trend': True,
        'regime': 'bullish',
        'last_updated': int(datetime.now().timestamp())
    }

    # Test exit logic
    exit_signals = strategy.should_exit(mock_trade, 19400, datetime.now())

    # Verify stoploss has precedence (it should be checked first in the code)
    assert len(exit_signals) == 1
    assert exit_signals[0].exit_type == ExitType.STOP_LOSS
    assert "stoploss" in exit_signals[0].exit_reason


def test_trade_cache_on_exit(strategy, mock_trade):
    """Test that trade cache is properly updated after an exit"""
    # Setup
    mock_trade.pair = "BTC/USDT"
    mock_trade.open_rate = 20000
    mock_trade.open_date_utc = datetime.now()
    mock_trade.is_short = False

    # Add trade to cache
    trade_id = f"{mock_trade.pair}_{mock_trade.open_date_utc.timestamp()}"
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

    # Mock the performance tracker update method
    strategy.performance_tracker.update_performance = MagicMock()

    # Call confirm_trade_exit
    result = strategy.confirm_trade_exit(
        pair=mock_trade.pair,
        trade=mock_trade,
        order_type="limit",
        amount=0.1,
        rate=21000,  # 5% profit
        time_in_force="GTC",
        exit_reason="roi",
        current_time=datetime.now()
    )

    # Verify result
    assert result is True

    # Verify performance tracker was updated
    strategy.performance_tracker.update_performance.assert_called_once()

    # Verify trade was removed from cache
    assert trade_id not in strategy.trade_cache['active_trades']


@pytest.fixture
def mock_trades():
    """Create mock trades for testing"""
    trade1 = MagicMock(spec=Trade)
    trade1.pair = "BTC/USDT"
    trade1.open_rate = 20000
    trade1.open_date_utc = datetime.now() - timedelta(hours=2)
    trade1.is_short = False

    trade2 = MagicMock(spec=Trade)
    trade2.pair = "ETH/USDT"
    trade2.open_rate = 1500
    trade2.open_date_utc = datetime.now() - timedelta(hours=1)
    trade2.is_short = True

    return [trade1, trade2]


def test_bot_start_no_trades():
    """Test bot_start with no existing trades"""
    # Config for non-backtest mode
    config = {
        'user_data_dir': '/tmp',
        'runmode': 'dry_run'
    }

    # Create strategy instance
    strategy = MACDTrendAdaptiveStrategy(config)

    # Patch the Trade.get_trades_proxy to return empty list
    with patch('strategy.Trade.get_trades_proxy', return_value=[]) as mock_get_trades:
        with patch('strategy.logger') as mock_logger:
            # Call bot_start
            strategy.bot_start()

            # Verify Trade.get_trades_proxy was called with is_open=True
            mock_get_trades.assert_called_once_with(is_open=True)

            # Verify log message
            mock_logger.info.assert_any_call("No open trades found to recover")

            # Verify trade_cache is empty (no trades recovered)
            assert len(strategy.trade_cache['active_trades']) == 0


def test_bot_start_with_existing_trades(mock_trades):
    """Test bot_start with existing trades that need recovery"""
    # Config for non-backtest mode
    config = {
        'user_data_dir': '/tmp',
        'runmode': 'dry_run'
    }

    # Create strategy instance
    strategy = MACDTrendAdaptiveStrategy(config)

    # Patch the necessary methods/functions
    with patch('strategy.Trade.get_trades_proxy', return_value=mock_trades) as mock_get_trades:
        with patch('strategy.logger') as mock_logger:
            with patch.object(strategy, '_handle_missing_trade') as mock_handle_missing:
                # Call bot_start
                strategy.bot_start()

                # Verify Trade.get_trades_proxy was called
                mock_get_trades.assert_called_once_with(is_open=True)

                # Verify _handle_missing_trade was called for each trade
                assert mock_handle_missing.call_count == len(mock_trades)

                # Verify log messages
                mock_logger.info.assert_any_call("Strategy starting - checking for existing trades to recover")
                mock_logger.info.assert_any_call(f"Found {len(mock_trades)} open trades to recover")


def test_handle_missing_trade_recovery():
    """Test the _handle_missing_trade method directly"""
    # Config for non-backtest mode
    config = {
        'user_data_dir': '/tmp',
        'runmode': 'dry_run'
    }

    # Create strategy instance
    strategy = MACDTrendAdaptiveStrategy(config)

    # Create a mock trade
    trade = MagicMock(spec=Trade)
    trade.pair = "BTC/USDT"
    trade.open_rate = 20000
    trade.open_date_utc = datetime.datetime.now() - datetime.timedelta(hours=2)
    trade.is_short = False

    # Patch _get_or_create_trade_cache to verify it's called correctly
    with patch.object(strategy, '_get_or_create_trade_cache',
                      return_value={'direction': 'long', 'entry_rate': 20000}) as mock_get_create:
        with patch('strategy.logger') as mock_logger:
            # Call _handle_missing_trade
            result = strategy._handle_missing_trade(trade, datetime.datetime.now())

            # Verify _get_or_create_trade_cache was called with correct arguments
            mock_get_create.assert_called_once_with(
                f"{trade.pair}_{trade.open_date_utc.timestamp()}",
                trade.pair,
                trade.open_rate,
                trade.open_date_utc,
                trade.is_short
            )

            # Verify warning was logged
            mock_logger.warning.assert_called_once()

            # Verify result is the cache entry
            assert result == {'direction': 'long', 'entry_rate': 20000}


def test_handle_missing_trade_error_handling():
    """Test error handling in _handle_missing_trade method"""
    # Config for non-backtest mode
    config = {
        'user_data_dir': '/tmp',
        'runmode': 'dry_run'
    }

    # Create strategy instance
    strategy = MACDTrendAdaptiveStrategy(config)

    # Create a mock trade with all required attributes
    valid_trade = MagicMock(spec=Trade)
    valid_trade.pair = "BTC/USDT"
    valid_trade.open_rate = 20000
    valid_trade.open_date_utc = datetime.now() - timedelta(hours=2)
    valid_trade.is_short = False

    # Test case 1: _get_or_create_trade_cache raises an exception
    with patch.object(strategy, '_get_or_create_trade_cache',
                      side_effect=Exception("Test exception")) as mock_get_create:
        with patch('strategy.logger') as mock_logger:
            # Call _handle_missing_trade
            result = strategy._handle_missing_trade(valid_trade, datetime.now())

            # Verify _get_or_create_trade_cache was called
            mock_get_create.assert_called_once()

            # Verify error was logged
            mock_logger.error.assert_called()

            # Verify fallback values were returned
            assert result['error'].startswith('Error:')
            assert result['direction'] == 'long'
            assert result['roi'] == strategy.strategy_config.default_roi
            assert result['stoploss'] == strategy.strategy_config.static_stoploss
            assert result['regime'] == 'neutral'

            # Verify fallback stoploss price is calculated correctly for long trade
            assert result['stoploss_price'] < valid_trade.open_rate

    # Create a mock short trade
    valid_short_trade = MagicMock(spec=Trade)
    valid_short_trade.pair = "BTC/USDT"
    valid_short_trade.open_rate = 20000
    valid_short_trade.open_date_utc = datetime.now() - timedelta(hours=2)
    valid_short_trade.is_short = True

    # Test case 2: Test fallback stoploss price calculation for short trade
    with patch.object(strategy, '_get_or_create_trade_cache',
                      side_effect=Exception("Test exception")) as mock_get_create:
        # Call _handle_missing_trade for short trade
        result = strategy._handle_missing_trade(valid_short_trade, datetime.now())

        # Verify fallback stoploss price is above entry for short
        assert result['stoploss_price'] > valid_short_trade.open_rate

    # Test case 3: Missing attribute in trade object
    incomplete_trade = MagicMock(spec=Trade)
    # Missing open_rate
    incomplete_trade.pair = "BTC/USDT"
    incomplete_trade.open_date_utc = datetime.now() - timedelta(hours=2)
    incomplete_trade.is_short = False

    # Remove the open_rate attribute
    del incomplete_trade.open_rate

    with patch('strategy.logger') as mock_logger:
        # Call _handle_missing_trade with incomplete trade
        result = strategy._handle_missing_trade(incomplete_trade, datetime.now())

        # Verify error about missing attribute was logged
        mock_logger.error.assert_called_once()
        assert 'missing attributes' in mock_logger.error.call_args[0][0].lower()

        # Verify conservative default values were used
        assert result['direction'] == 'unknown'
        assert result['entry_rate'] == 0
        assert 'error' in result
        assert 'Missing trade attributes' in result['error']

    # Test case 4: Unexpected outer exception
    with patch.object(strategy, '_get_or_create_trade_cache') as mock_get_create:
        # Make _get_direction raise an exception
        with patch('strategy.get_direction', side_effect=Exception("Unexpected error")):
            with patch('strategy.logger') as mock_logger:
                # Call _handle_missing_trade
                result = strategy._handle_missing_trade(valid_trade, datetime.now())

                # Verify error was logged
                mock_logger.error.assert_called_once()
                assert 'Unexpected error' in mock_logger.error.call_args[0][0]

                # Verify minimal safe values were returned
                assert result['direction'] == 'unknown'
                assert result['roi'] == 0.05  # Conservative ROI
                assert result['stoploss'] == -0.05  # Conservative stoploss
                assert 'error' in result
                assert 'Unexpected error' in result['error']


def test_calculate_fallback_stoploss_price():
    """Test the _calculate_fallback_stoploss_price helper method"""
    # Config for non-backtest mode
    config = {
        'user_data_dir': '/tmp',
        'runmode': 'dry_run'
    }

    # Create strategy instance
    strategy = MACDTrendAdaptiveStrategy(config)

    # Test for long trade
    long_entry_rate = 20000
    stoploss_percentage = -0.05  # 5% stoploss
    long_sl_price = strategy._calculate_fallback_stoploss_price(
        long_entry_rate, stoploss_percentage, False
    )

    # Expected: 20000 * (1 - 0.05) = 19000
    assert long_sl_price == long_entry_rate * (1 + stoploss_percentage)
    assert long_sl_price < long_entry_rate

    # Test for short trade
    short_entry_rate = 20000
    short_sl_price = strategy._calculate_fallback_stoploss_price(
        short_entry_rate, stoploss_percentage, True
    )

    # Expected: 20000 * (1 + 0.05) = 21000
    assert short_sl_price == short_entry_rate * (1 - stoploss_percentage)
    assert short_sl_price > short_entry_rate

    # Test error handling
    with patch('strategy.logger') as mock_logger:
        # Test with invalid entry rate causing an exception
        result = strategy._calculate_fallback_stoploss_price(
            "invalid", stoploss_percentage, False  # Invalid entry rate
        )

        # Verify error was logged
        mock_logger.error.assert_called_once()

        # Verify a default stoploss price was returned
        assert result == 0.9 * 0  # 0 * 0.9 since entry rate is 0 after failure


def test_bot_start_in_backtest_mode():
    """Test bot_start in backtest mode (should be a no-op)"""
    # Config for backtest mode
    config = {
        'user_data_dir': '/tmp',
        'runmode': 'backtest'
    }

    # Create strategy instance
    strategy = MACDTrendAdaptiveStrategy(config)

    # Patch Trade.get_trades_proxy to ensure it's not called in backtest mode
    with patch('strategy.Trade.get_trades_proxy') as mock_get_trades:
        with patch('strategy.logger') as mock_logger:
            # Call bot_start
            strategy.bot_start()

            # Verify Trade.get_trades_proxy was NOT called
            mock_get_trades.assert_not_called()

            # Verify no relevant log messages
            for call in mock_logger.info.call_args_list:
                args = call[0]
                assert "trades to recover" not in args[0]


@patch('strategy.Trade.get_trades_proxy')
@patch.object(MACDTrendAdaptiveStrategy, 'roi_calculator')
@patch.object(MACDTrendAdaptiveStrategy, 'stoploss_calculator')
@patch.object(MACDTrendAdaptiveStrategy, 'regime_detector')
def test_integration_bot_restart_recovery(
        mock_regime_detector,
        mock_stoploss_calculator,
        mock_roi_calculator,
        mock_get_trades_proxy,
        mock_trades,
        strategy
):
    """
    Integration test for the entire trade recovery flow.
    Tests that trades are properly recovered and initialized in the cache.
    """
    # Set up the mocks
    mock_get_trades_proxy.return_value = mock_trades
    mock_roi_calculator.get_trade_roi.return_value = 0.05
    mock_stoploss_calculator.calculate_dynamic_stoploss.return_value = -0.03
    mock_stoploss_calculator.calculate_stoploss_price.return_value = 19400
    mock_regime_detector.detect_regime.return_value = "bullish"
    mock_regime_detector.is_counter_trend.return_value = False
    mock_regime_detector.is_aligned_trend.return_value = True

    # Call bot_start
    strategy.bot_start()

    # Verify trades were added to cache
    assert len(strategy.trade_cache['active_trades']) == len(mock_trades)

    # Check that trade info was properly initialized
    for trade in mock_trades:
        trade_id = f"{trade.pair}_{trade.open_date_utc.timestamp()}"
        assert trade_id in strategy.trade_cache['active_trades']

        cache_entry = strategy.trade_cache['active_trades'][trade_id]
        direction = 'short' if trade.is_short else 'long'

        assert cache_entry['direction'] == direction
        assert cache_entry['entry_rate'] == trade.open_rate
        assert cache_entry['roi'] == 0.05
        assert cache_entry['stoploss'] == -0.03
        assert cache_entry['regime'] == "bullish"
