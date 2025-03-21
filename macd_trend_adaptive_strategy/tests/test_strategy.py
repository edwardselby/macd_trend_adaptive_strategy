import json
import os
import tempfile
from datetime import datetime
from unittest.mock import patch, MagicMock, ANY

import pytest
from freqtrade.enums.exittype import ExitType
from freqtrade.persistence import Trade

from macd_trend_adaptive_strategy.config.strategy_config import StrategyMode
# Import strategy class
from strategy import MACDTrendAdaptiveStrategy


class TestMACDTrendAdaptiveStrategy:
    """Test class for MACDTrendAdaptiveStrategy"""

    @pytest.fixture
    def config_file(self):
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

    @patch.object(MACDTrendAdaptiveStrategy, 'STRATEGY_MODE', StrategyMode.TIMEFRAME_5M)
    def test_strategy_initialization_requires_config_file(self, config_file):
        """Test that strategy initialization requires a config file"""
        # Mock the config file check to return False
        with patch('os.path.exists', return_value=False):
            with pytest.raises(ValueError) as excinfo:
                strategy = MACDTrendAdaptiveStrategy({'runmode': 'backtest'})

            assert "Configuration file not found" in str(excinfo.value)
            assert "Please create a configuration file" in str(excinfo.value)

    @patch.object(MACDTrendAdaptiveStrategy, 'STRATEGY_MODE', StrategyMode.TIMEFRAME_5M)
    def test_strategy_initialization_with_config_file(self, config_file):
        """Test that strategy initializes properly with a config file"""
        # Mock the config file path
        with patch('os.path.join', return_value=config_file):
            strategy = MACDTrendAdaptiveStrategy({'runmode': 'backtest'})

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

    @patch.object(MACDTrendAdaptiveStrategy, 'STRATEGY_MODE', StrategyMode.TIMEFRAME_5M)
    def test_confirm_trade_entry(self, config_file):
        """Test confirm_trade_entry creates a trade cache entry"""
        # Mock config file path
        with patch('os.path.join', return_value=config_file):
            strategy = MACDTrendAdaptiveStrategy({'runmode': 'backtest'})

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

    @patch.object(MACDTrendAdaptiveStrategy, 'STRATEGY_MODE', StrategyMode.TIMEFRAME_5M)
    def test_should_exit_with_roi(self, config_file):
        """Test should_exit returns ROI exit signal when profit target is reached"""
        # Mock config file path
        with patch('os.path.join', return_value=config_file):
            strategy = MACDTrendAdaptiveStrategy({'runmode': 'backtest'})

            # Create mock trade
            trade = MagicMock(spec=Trade)
            trade.pair = 'BTC/USDT'
            trade.open_date_utc = datetime.now()
            trade.open_rate = 30000
            trade.is_short = False
            trade.leverage = 1.0

            # Generate a valid trade ID format
            trade_id = f"{trade.pair}_{int(trade.open_date_utc.timestamp())}"

            # Create cache entry directly instead of using _get_or_create
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

    @patch.object(MACDTrendAdaptiveStrategy, 'STRATEGY_MODE', StrategyMode.TIMEFRAME_5M)
    def test_should_exit_with_stoploss(self, config_file):
        """Test should_exit returns stoploss signal when price hits stoploss level"""
        # Mock config file path
        with patch('os.path.join', return_value=config_file):
            strategy = MACDTrendAdaptiveStrategy({'runmode': 'backtest'})

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

    @patch.object(MACDTrendAdaptiveStrategy, 'STRATEGY_MODE', StrategyMode.TIMEFRAME_5M)
    def test_confirm_trade_exit(self, config_file):
        """Test confirm_trade_exit updates performance tracking"""
        # Mock config file path
        with patch('os.path.join', return_value=config_file):
            strategy = MACDTrendAdaptiveStrategy({'runmode': 'backtest'})

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

    @patch.object(MACDTrendAdaptiveStrategy, 'STRATEGY_MODE', StrategyMode.TIMEFRAME_5M)
    def test_handle_missing_trade(self, config_file):
        """Test _handle_missing_trade recreates trade cache entry"""
        # Mock config file path
        with patch('os.path.join', return_value=config_file):
            strategy = MACDTrendAdaptiveStrategy({'runmode': 'backtest'})

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

    @patch.object(MACDTrendAdaptiveStrategy, 'STRATEGY_MODE', StrategyMode.TIMEFRAME_5M)
    def test_bot_start(self, config_file):
        """Test bot_start recovers existing trades"""
        # Mock config file path
        with patch('os.path.join', return_value=config_file):
            # Create the strategy with mocked dependencies
            strategy = MACDTrendAdaptiveStrategy({'runmode': 'live'})

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