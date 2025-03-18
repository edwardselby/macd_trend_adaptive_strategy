from datetime import datetime, timedelta
from unittest.mock import MagicMock

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

    # Test with price at stoploss level
    exit_signals = strategy.should_exit(mock_trade, 19400, datetime.now())

    # Should return a stoploss exit signal
    assert len(exit_signals) == 1
    assert exit_signals[0].exit_type == ExitType.STOP_LOSS
    assert exit_signals[0].exit_reason == "dynamic_stoploss"

    # Test with price above stoploss level
    exit_signals = strategy.should_exit(mock_trade, 19500, datetime.now())

    # Should not exit
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
        'last_updated': int(datetime.now().timestamp())
    }

    # Call method
    stoploss = strategy.custom_stoploss(
        pair, mock_trade, current_time, current_rate, current_profit
    )

    # Verify stoploss value
    assert stoploss == expected_stoploss

    # Test with trade not in cache
    strategy.trade_cache['active_trades'] = {}

    # Should return the default stoploss
    stoploss = strategy.custom_stoploss(
        pair, mock_trade, current_time, current_rate, current_profit
    )
    assert stoploss == strategy.stoploss


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


def test_strategy_stoploss_integration(strategy, mock_trade, mock_short_trade):
    """
    Integration test to verify stoploss behavior between the strategy and FreqTrade.
    This test simulates how FreqTrade would interact with the strategy's stoploss logic.
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

    # Configure profit calculation (how FreqTrade would calculate it)
    def long_profit(rate):
        return (rate - entry_rate) / entry_rate

    def short_profit(rate):
        return (entry_rate - rate) / entry_rate

    mock_trade.calc_profit_ratio = long_profit
    mock_short_trade.calc_profit_ratio = short_profit

    # Initialize trades in strategy
    # This is what happens when FreqTrade creates a new trade
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

    # Log stoploss values for debugging
    print(f"Long stoploss: {long_cache['stoploss']:.4f}, price: {long_cache['stoploss_price']}")
    print(f"Short stoploss: {short_cache['stoploss']:.4f}, price: {short_cache['stoploss_price']}")

    # Verify stoploss is correctly calculated
    assert long_cache['stoploss'] < 0, "Long stoploss should be negative"
    assert short_cache['stoploss'] < 0, "Short stoploss should be negative"

    # Now test the stoploss triggering using should_exit
    # This is how FreqTrade would check for exit conditions

    # 1. Test long trade at stoploss price
    long_sl_price = long_cache['stoploss_price']
    long_exit = strategy.should_exit(mock_trade, long_sl_price, current_time)

    assert len(long_exit) == 1, "Long trade should exit at stoploss price"
    assert long_exit[0].exit_type == ExitType.STOP_LOSS, "Exit should be stoploss type"

    # Calculate actual profit at stoploss - should match stoploss percentage
    long_profit_at_sl = long_profit(long_sl_price)
    assert abs(long_profit_at_sl - long_cache['stoploss']) < 0.0001, \
        f"Long profit at SL ({long_profit_at_sl:.4f}) should match stoploss value ({long_cache['stoploss']:.4f})"

    # 2. Test short trade at stoploss price
    short_sl_price = short_cache['stoploss_price']
    short_exit = strategy.should_exit(mock_short_trade, short_sl_price, short_time)

    assert len(short_exit) == 1, "Short trade should exit at stoploss price"
    assert short_exit[0].exit_type == ExitType.STOP_LOSS, "Exit should be stoploss type"

    # Calculate actual profit at stoploss - should match stoploss percentage
    short_profit_at_sl = short_profit(short_sl_price)
    assert abs(short_profit_at_sl - short_cache['stoploss']) < 0.0001, \
        f"Short profit at SL ({short_profit_at_sl:.4f}) should match stoploss value ({short_cache['stoploss']:.4f})"

    # 3. Now test the actual issue - compare with real FreqTrade logs
    # Check if there's a difference between long and short stoploss behavior

    # First check if stoploss values are symmetric (should be for same regime)
    # Force regime detector to return neutral to eliminate alignment factors
    strategy.regime_detector.detect_regime = lambda: "neutral"
    strategy.regime_detector.is_counter_trend = lambda x: False
    strategy.regime_detector.is_aligned_trend = lambda x: False

    # Recreate trades with the same conditions
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
    long_cache = strategy.trade_cache['active_trades'][create_trade_id(pair, current_time)]
    short_cache = strategy.trade_cache['active_trades'][create_trade_id(pair, short_time)]

    # In neutral regime, long and short stoploss should be identical
    assert abs(abs(long_cache['stoploss']) - abs(short_cache['stoploss'])) < 0.0001, \
        f"Long and short stoploss should be identical in neutral regime, but got " \
        f"long: {long_cache['stoploss']:.4f}, short: {short_cache['stoploss']:.4f}"

    # Check behavior at -3% - the specific issue from logs
    # For a short trade, test what happens at a price that would give -3% loss
    three_percent_price = entry_rate * 1.03  # This would be a 3% loss for shorts

    # This is what FreqTrade would do - call should_exit at the current price
    exit_at_three_percent = strategy.should_exit(
        mock_short_trade, three_percent_price, short_time
    )

    # Calculate profit at this price
    profit_at_three_percent = short_profit(three_percent_price)
    assert abs(profit_at_three_percent - (-0.03)) < 0.0001, \
        f"Profit calculation incorrect, expected -0.03, got {profit_at_three_percent:.4f}"

    # This is the critical test for your issue
    # If FreqTrade overrides to -3%, this would exit even if your stoploss is set to -1%
    if short_cache['stoploss'] > -0.03:
        # If our stoploss is tighter than -3% (like -1%), we shouldn't exit at -3%
        expected_len = 0
        assertion_msg = "Short should NOT exit at -3% if stoploss is set tighter"
    else:
        # If our stoploss is looser than -3%, we should exit at -3%
        expected_len = 1
        assertion_msg = "Short should exit at -3% if stoploss is looser"

    assert len(exit_at_three_percent) == expected_len, assertion_msg
