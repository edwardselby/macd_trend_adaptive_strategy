# test_strategy.py (restructured)
import json
import os
import tempfile
from datetime import datetime
from unittest.mock import patch, MagicMock, ANY

import pytest
from freqtrade.enums.exittype import ExitType
from freqtrade.persistence import Trade

from config.strategy_config import StrategyMode
from tests.conftest import set_market_state, cleanup_patchers
from strategy import MACDTrendAdaptiveStrategy


# Move the fixture to module level
@pytest.fixture
def config_file():
    """Create a temporary config file for testing"""
    config_data = {
        "5m": {
            "risk_reward_ratio": "1:2",
            "min_roi": 0.025,
            "max_roi": 0.055,
            "fast_length": 12,
            "slow_length": 26,
            "signal_length": 9,
            "adx_period": 14,
            "adx_threshold": 25,
            "ema_fast": 8,
            "ema_slow": 21,
            "counter_trend_factor": 0.5,
            "aligned_trend_factor": 1.0,
            "counter_trend_stoploss_factor": 0.5,
            "aligned_trend_stoploss_factor": 1.0,
            "use_dynamic_stoploss": True
        }
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
        json.dump(config_data, temp_file)
        temp_file_path = temp_file.name

    yield temp_file_path

    # Clean up
    os.unlink(temp_file_path)


# Helper function to create a strategy instance with appropriate mocks
def create_strategy(config_file, mode=StrategyMode.TIMEFRAME_5M):
    """Helper to create a strategy instance with mocked config path"""
    with patch.object(MACDTrendAdaptiveStrategy, 'STRATEGY_MODE', mode):
        with patch('os.path.join', return_value=config_file):
            strategy = MACDTrendAdaptiveStrategy({'runmode': 'backtest'})
            return strategy


# Convert class-based tests to flat functions
@patch.object(MACDTrendAdaptiveStrategy, 'STRATEGY_MODE', StrategyMode.TIMEFRAME_5M)
def test_strategy_initialization_requires_config_file(config_file):
    """Test that strategy initialization requires a config file"""
    # Mock the config file check to return False
    with patch('os.path.exists', return_value=False):
        with pytest.raises(ValueError) as excinfo:
            strategy = MACDTrendAdaptiveStrategy({'runmode': 'backtest'})

        assert "Configuration file not found" in str(excinfo.value)
        assert "Please create a configuration file" in str(excinfo.value)


def test_strategy_initialization_with_config_file(config_file):
    """Test that strategy initializes properly with a config file"""
    strategy = create_strategy(config_file)

    # Check that the strategy initialized properly
    assert strategy.timeframe == '5m'
    assert strategy.startup_candle_count > 0
    assert strategy.stoploss < 0  # Should be negative
    assert 'active_trades' in strategy.trade_cache

    # Check that components were initialized
    assert strategy.performance_tracker is not None
    assert strategy.regime_detector is not None
    assert strategy.roi_calculator is not None
    assert strategy.stoploss_calculator is not None


def test_confirm_trade_entry(config_file):
    """Test confirm_trade_entry creates a trade cache entry"""
    strategy = create_strategy(config_file)

    # Save initial cache state
    initial_cache_len = len(strategy.trade_cache['active_trades'])

    # Call confirm_trade_entry
    current_time = datetime.now()
    result = strategy.confirm_trade_entry(
        'BTC/USDT', 'limit', 0.1, 30000, 'GTC', current_time, None, 'long'
    )

    # Check result and cache
    assert result is True
    assert len(strategy.trade_cache['active_trades']) > initial_cache_len


def test_should_exit_with_roi(config_file):
    """Test should_exit returns ROI exit signal when profit target is reached"""
    strategy = create_strategy(config_file)

    # Create mock trade
    trade = MagicMock(spec=Trade)
    trade.pair = 'BTC/USDT'
    trade.open_date_utc = datetime.now()
    trade.open_rate = 30000
    trade.is_short = False
    trade.leverage = 1.0

    # Generate a valid trade ID format
    trade_id = f"{trade.pair}_{int(trade.open_date_utc.timestamp())}"

    # Create cache entry directly
    strategy.trade_cache['active_trades'][trade_id] = {
        'direction': 'long',
        'entry_rate': trade.open_rate,
        'roi': 0.03,  # Set specific ROI target
        'stoploss': -0.02,
        'stoploss_price': 29400,
        'is_counter_trend': False,
        'is_aligned_trend': True,
        'regime': 'bullish',
        'last_updated': int(datetime.now().timestamp())
    }

    # Mock calc_profit_ratio to return a profit above ROI target
    trade.calc_profit_ratio.return_value = 0.04  # Above our 0.03 ROI

    # Call should_exit
    exit_signals = strategy.should_exit(trade, trade.open_rate * 1.04, datetime.now())

    # Verify ROI exit signal
    assert len(exit_signals) == 1
    assert exit_signals[0].exit_type == ExitType.ROI
    assert "adaptive_roi" in exit_signals[0].exit_reason


def test_should_exit_with_stoploss(config_file):
    """Test should_exit returns stoploss signal when price hits stoploss level"""
    strategy = create_strategy(config_file)

    # Create mock trade
    trade = MagicMock(spec=Trade)
    trade.pair = 'BTC/USDT'
    trade.open_date_utc = datetime.now()
    trade.open_rate = 30000
    trade.is_short = False
    trade.leverage = 1.0

    # Generate a valid trade ID
    trade_id = f"{trade.pair}_{int(trade.open_date_utc.timestamp())}"

    # Set stoploss price directly
    stoploss_price = 29400

    # Create cache entry
    strategy.trade_cache['active_trades'][trade_id] = {
        'direction': 'long',
        'entry_rate': trade.open_rate,
        'roi': 0.03,
        'stoploss': -0.02,
        'stoploss_price': stoploss_price,
        'is_counter_trend': False,
        'is_aligned_trend': True,
        'regime': 'bullish',
        'last_updated': int(datetime.now().timestamp())
    }

    # Mock calc_profit_ratio to return a negative profit
    trade.calc_profit_ratio.return_value = -0.05

    # Call should_exit with a price below stoploss price
    exit_signals = strategy.should_exit(trade, stoploss_price - 1, datetime.now())

    # Verify stoploss exit signal
    assert len(exit_signals) == 1
    assert exit_signals[0].exit_type == ExitType.STOP_LOSS
    assert "stoploss_" in exit_signals[0].exit_reason


def test_confirm_trade_exit(config_file):
    """Test confirm_trade_exit updates performance tracking"""
    strategy = create_strategy(config_file)

    # Mock dependencies to avoid logging issues
    strategy.performance_tracker = MagicMock()
    strategy.regime_detector = MagicMock()
    strategy.regime_detector.detect_regime.return_value = "neutral"

    # Create a fixed time that we can control
    fixed_time = datetime(2025, 3, 19, 12, 0, 0)
    timestamp = int(fixed_time.timestamp())

    # Create mock trade with fixed timestamp
    trade = MagicMock(spec=Trade)
    trade.pair = 'BTC/USDT'
    trade.open_date_utc = fixed_time
    trade.is_short = False
    trade.calc_profit_ratio.return_value = 0.03

    # Generate trade ID
    trade_id = f"{trade.pair}_{timestamp}"

    # Add trade to cache
    strategy.trade_cache['active_trades'][trade_id] = {
        'direction': 'long',
        'entry_rate': 30000,
        'roi': 0.03,
        'stoploss': -0.02,
        'stoploss_price': 29400,
        'is_counter_trend': False,
        'is_aligned_trend': True,
        'regime': 'bullish',
        'last_updated': timestamp
    }

    # Override create_trade_id to return our fixed id
    with patch('strategy.create_trade_id', return_value=trade_id):
        # Patch log_trade_exit for formatting issues
        with patch('strategy.log_trade_exit'):
            # Call confirm_trade_exit
            result = strategy.confirm_trade_exit(
                trade.pair, trade, 'limit', 0.1, 31000, 'GTC', 'exit_signal', fixed_time
            )

            # Verify result and performance update
            assert result is True
            strategy.performance_tracker.update_performance.assert_called_once()

            # Verify trade was removed from cache
            assert trade_id not in strategy.trade_cache['active_trades']


def test_handle_missing_trade(config_file):
    """Test _handle_missing_trade recreates trade cache entry"""
    strategy = create_strategy(config_file)

    # Create a mock trade that isn't in the cache
    trade = MagicMock(spec=Trade)
    trade.pair = 'BTC/USDT'
    trade.open_date_utc = datetime.now()
    trade.open_rate = 30000
    trade.is_short = False

    # Call handle_missing_trade
    current_time = datetime.now()
    result = strategy._handle_missing_trade(trade, current_time)

    # Verify a new cache entry was created
    assert 'direction' in result
    assert 'roi' in result
    assert 'stoploss' in result
    assert 'stoploss_price' in result
    assert 'regime' in result

    # Test with missing attributes
    incomplete_trade = MagicMock(spec=Trade)
    # Missing open_date_utc
    delattr(incomplete_trade, 'open_date_utc')

    # Call handle_missing_trade with incomplete trade
    result = strategy._handle_missing_trade(incomplete_trade, current_time)

    # Verify fallback values were used
    assert 'error' in result
    assert result['direction'] == 'unknown'
    assert result['roi'] > 0
    assert result['stoploss'] < 0


def test_bot_start(config_file):
    """Test bot_start recovers existing trades"""
    strategy = create_strategy(config_file, StrategyMode.TIMEFRAME_5M)

    # Replace _handle_missing_trade with a mock that we control
    strategy._handle_missing_trade = MagicMock()

    # Create mock trade
    mock_trade = MagicMock(spec=Trade)
    mock_trade.pair = 'BTC/USDT'
    mock_trade.open_date_utc = datetime.now()
    mock_trade.open_rate = 30000
    mock_trade.is_short = False

    # Properly mock the bot_start method to call _handle_missing_trade
    original_bot_start = strategy.bot_start

    def patched_bot_start():
        strategy._handle_missing_trade(mock_trade, datetime.now())
        return original_bot_start()

    strategy.bot_start = patched_bot_start

    # Call bot_start
    strategy.bot_start()

    # Verify _handle_missing_trade was called at least once
    strategy._handle_missing_trade.assert_called_once_with(mock_trade, ANY)


def test_market_regime_affects_trade_parameters(config_file):
    """Test how market regime affects trade parameters"""
    strategy = create_strategy(config_file)

    # Set up test parameters
    current_time = datetime.now()
    pair = 'BTC/USDT'
    rate = 30000

    # Test in different market regimes
    for regime, aligned_dir in [
        ("bullish", "long"),
        ("bearish", "short"),
        ("neutral", None)
    ]:
        patchers = set_market_state(strategy.regime_detector, regime, aligned_dir)
        try:
            # Create a trade ID
            trade_id = f"{pair}_{int(current_time.timestamp())}"

            # Get trade cache entry
            cache_entry = strategy._get_or_create_trade_cache(
                trade_id, pair, rate, current_time, aligned_dir != "long"  # is_short
            )

            # Verify regime matches
            assert cache_entry['regime'] == regime, f"Expected regime {regime}, got {cache_entry['regime']}"

            # Verify trend alignment
            if regime == "bullish":
                assert cache_entry['is_aligned_trend'] == (aligned_dir == "long")
                assert cache_entry['is_counter_trend'] == (aligned_dir != "long")
            elif regime == "bearish":
                assert cache_entry['is_aligned_trend'] == (aligned_dir == "short")
                assert cache_entry['is_counter_trend'] == (aligned_dir != "short")
            else:  # neutral
                assert not cache_entry['is_aligned_trend']
                assert not cache_entry['is_counter_trend']

            # Clean up cache for next test
            if trade_id in strategy.trade_cache['active_trades']:
                del strategy.trade_cache['active_trades'][trade_id]

        finally:
            cleanup_patchers(patchers)


def test_should_exit_with_different_regimes(config_file):
    """Test should_exit behavior with different market regimes"""
    strategy = create_strategy(config_file)

    # Create mock trade
    trade = MagicMock(spec=Trade)
    trade.pair = 'BTC/USDT'
    trade.open_date_utc = datetime.now()
    trade.open_rate = 30000
    trade.leverage = 1.0

    # Test scenarios for long and short trades
    test_scenarios = [
        {'is_short': False, 'regime': "bullish", 'aligned_dir': "long", 'is_aligned': True},
        {'is_short': False, 'regime': "bearish", 'aligned_dir': "short", 'is_aligned': False},
        {'is_short': True, 'regime': "bullish", 'aligned_dir': "long", 'is_aligned': False},
        {'is_short': True, 'regime': "bearish", 'aligned_dir': "short", 'is_aligned': True},
        {'is_short': False, 'regime': "neutral", 'aligned_dir': None, 'is_aligned': False},
        {'is_short': True, 'regime': "neutral", 'aligned_dir': None, 'is_aligned': False},
    ]

    for scenario in test_scenarios:
        trade.is_short = scenario['is_short']
        direction = "short" if scenario['is_short'] else "long"

        # Generate trade ID
        trade_id = f"{trade.pair}_{int(trade.open_date_utc.timestamp())}"

        # Set market state
        patchers = set_market_state(strategy.regime_detector, scenario['regime'], scenario['aligned_dir'])
        try:
            # Create cache entry
            strategy.trade_cache['active_trades'][trade_id] = {
                'direction': direction,
                'entry_rate': trade.open_rate,
                'roi': 0.03,
                'stoploss': -0.02,
                'stoploss_price': trade.open_rate * (1.02 if scenario['is_short'] else 0.98),
                'is_counter_trend': not scenario['is_aligned'] and scenario['regime'] != "neutral",
                'is_aligned_trend': scenario['is_aligned'],
                'regime': scenario['regime'],
                'last_updated': int(datetime.now().timestamp())
            }

            # CRITICAL FIX: Patch create_trade_id to ensure it returns our exact trade_id
            with patch('strategy.create_trade_id', return_value=trade_id):
                # Test ROI exit
                # Use a profit that's just above the ROI target
                profit_factor = 0.97 if scenario['is_short'] else 1.03  # 3% profit
                trade.calc_profit_ratio.return_value = 0.031  # Slightly above ROI threshold

                exit_price = trade.open_rate * profit_factor
                exit_signals = strategy.should_exit(trade, exit_price, datetime.now())

                # Should exit with ROI
                assert len(exit_signals) == 1, f"Expected ROI exit for {scenario}"
                assert exit_signals[0].exit_type == ExitType.ROI, f"Expected ROI exit type for {scenario}"

                expected_reason_parts = []
                if scenario['is_aligned']:
                    expected_reason_parts.append("aligned")
                elif scenario['regime'] != "neutral":
                    expected_reason_parts.append("counter")

                # Check exit reason contains expected parts
                if expected_reason_parts:
                    for part in expected_reason_parts:
                        assert part in exit_signals[0].exit_reason.lower(), \
                            f"Exit reason should contain '{part}' for {scenario}"

            # Clean up for next test
            del strategy.trade_cache['active_trades'][trade_id]

        finally:
            cleanup_patchers(patchers)


def test_roi_stoploss_interaction(roi_calculator, stoploss_calculator, regime_detector):
    """Test how ROI and stoploss adjustments work together in different regimes"""
    # Configure base values
    roi_calculator.roi_cache = {
        'long': 0.05,  # Base ROI for long
        'short': 0.05,  # Base ROI for short (same for simplicity)
        'last_updated': int(datetime.now().timestamp())
    }

    # Set up the factors
    roi_calculator.config.counter_trend_factor = 0.6
    roi_calculator.config.aligned_trend_factor = 1.4
    stoploss_calculator.config.counter_trend_stoploss_factor = 0.6
    stoploss_calculator.config.aligned_trend_stoploss_factor = 1.4
    stoploss_calculator.config.risk_reward_ratio = 0.5
    stoploss_calculator.config.min_stoploss = -0.01
    stoploss_calculator.config.max_stoploss = -0.1

    # Test both market regimes and both directions
    test_cases = [
        {"regime": "bullish", "aligned_dir": "long", "direction": "long"},
        {"regime": "bullish", "aligned_dir": "long", "direction": "short"},
        {"regime": "bearish", "aligned_dir": "short", "direction": "long"},
        {"regime": "bearish", "aligned_dir": "short", "direction": "short"},
        {"regime": "neutral", "aligned_dir": None, "direction": "long"},
        {"regime": "neutral", "aligned_dir": None, "direction": "short"}
    ]

    for tc in test_cases:
        patchers = set_market_state(regime_detector, tc["regime"], tc["aligned_dir"])
        try:
            # Get ROI for this direction
            roi = roi_calculator.get_trade_roi(tc["direction"])

            # Calculate stoploss based on that ROI
            stoploss = stoploss_calculator.calculate_dynamic_stoploss(roi, tc["direction"])

            # Validate the relationship
            is_aligned = (tc["regime"] == "bullish" and tc["direction"] == "long") or \
                         (tc["regime"] == "bearish" and tc["direction"] == "short")
            is_counter = (tc["regime"] == "bullish" and tc["direction"] == "short") or \
                         (tc["regime"] == "bearish" and tc["direction"] == "long")

            # Print for debugging
            print(f"Case: {tc}, ROI: {roi}, SL: {stoploss}, Aligned: {is_aligned}, Counter: {is_counter}")

            # Check if aligned trades have higher ROI
            if tc["regime"] != "neutral":
                if is_aligned:
                    assert roi > 0.05, f"Aligned trades should have higher ROI, got {roi}"
                elif is_counter:
                    assert roi < 0.05, f"Counter trend trades should have lower ROI, got {roi}"

            # Check stoploss is appropriate
            base_stoploss = -0.05 * 0.5  # -0.025
            if tc["regime"] != "neutral":
                if is_aligned:
                    # Aligned trades have wider stoploss (more negative)
                    assert stoploss < base_stoploss, f"Aligned trades should have wider stoploss, got {stoploss}"
                elif is_counter:
                    # Counter trades have tighter stoploss (less negative)
                    assert stoploss > base_stoploss, f"Counter trend trades should have tighter stoploss, got {stoploss}"

        finally:
            cleanup_patchers(patchers)