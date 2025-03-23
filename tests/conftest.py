import json
import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import numpy as np
import pandas as pd
import pytest

from src.config.strategy_config import StrategyConfig, StrategyMode
from src.performance.db_handler import DBHandler
from src.performance.tracker import PerformanceTracker
from src.regime.detector import RegimeDetector
from src.risk_management.roi_calculator import ROICalculator
from src.risk_management.stoploss_calculator import StoplossCalculator


@pytest.fixture
def mock_config_file():
    """Create a temporary config file for testing"""
    config_data = {
        "1m": {
            "risk_reward_ratio": "1:1.5",
            "min_roi": 0.015,
            "max_roi": 0.035,
            "fast_length": 6,
            "slow_length": 14,
            "signal_length": 4,
            "adx_period": 8,
            "adx_threshold": 15,
            "ema_fast": 3,
            "ema_slow": 10
        },
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
            "ema_slow": 21
        },
        "15m": {
            "risk_reward_ratio": "1:2",
            "min_roi": 0.025,
            "max_roi": 0.055,
            "fast_length": 12,
            "slow_length": 26,
            "signal_length": 9,
            "adx_period": 14,
            "adx_threshold": 25,
            "ema_fast": 8,
            "ema_slow": 21
        },
        "global": {
            "counter_trend_factor": 0.5,
            "aligned_trend_factor": 1.0,
            "counter_trend_stoploss_factor": 0.5,
            "aligned_trend_stoploss_factor": 1.0,
            "use_dynamic_stoploss": True,
            "min_win_rate": 0.2,
            "max_win_rate": 0.8,
            "regime_win_rate_diff": 0.2,
            "min_recent_trades_per_direction": 5,
            "max_recent_trades": 10,
            "startup_candle_count": 30
        }
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
        json.dump(config_data, temp_file)
        temp_file_path = temp_file.name

    yield temp_file_path

    # Clean up the temporary file
    os.unlink(temp_file_path)


@pytest.fixture
def strategy_config(mock_config_file):
    """Create a StrategyConfig instance for testing"""
    return StrategyConfig(mode=StrategyMode.DEFAULT, config_path=mock_config_file)


@pytest.fixture
def db_handler():
    """Create a mock DBHandler for testing"""
    mock_db = MagicMock(spec=DBHandler)

    # Set up default performance data for tests
    mock_db.load_performance_data.return_value = {
        'long': {'wins': 10, 'losses': 5, 'consecutive_wins': 2,
                 'consecutive_losses': 0, 'last_trades': [1, 0, 1, 1], 'total_profit': 0.8},
        'short': {'wins': 8, 'losses': 7, 'consecutive_wins': 0,
                  'consecutive_losses': 1, 'last_trades': [0, 1, 0, 1], 'total_profit': 0.3}
    }

    return mock_db


@pytest.fixture
def performance_tracker(db_handler):
    """Create a real PerformanceTracker with a mocked DB handler"""
    tracker = PerformanceTracker(db_handler, max_recent_trades=5)

    # Initialize with known data for predictable test results
    tracker.performance_tracking = {
        'long': {'wins': 10, 'losses': 5, 'consecutive_wins': 2,
                 'consecutive_losses': 0, 'last_trades': [1, 0, 1, 1], 'total_profit': 0.8},
        'short': {'wins': 8, 'losses': 7, 'consecutive_wins': 0,
                  'consecutive_losses': 1, 'last_trades': [0, 1, 0, 1], 'total_profit': 0.3}
    }

    return tracker


@pytest.fixture
def regime_detector(performance_tracker, strategy_config):
    """Create a real RegimeDetector instance for testing"""
    # Create a real RegimeDetector instance
    detector = RegimeDetector(performance_tracker, strategy_config)

    return detector


@pytest.fixture
def roi_calculator(strategy_config):
    """Create a real ROICalculator for testing"""
    calculator = ROICalculator(strategy_config)

    # Initialize roi_cache with known values for predictable tests
    calculator.roi_cache = {'long': 0.03, 'short': 0.02, 'last_updated': 0}

    return calculator


@pytest.fixture
def stoploss_calculator(strategy_config):
    """Create a real StoplossCalculator for testing"""
    calculator = StoplossCalculator(strategy_config)
    return calculator


@pytest.fixture
def sample_dataframe():
    """Create a sample dataframe for testing indicators"""
    # Create a sample dataframe with OHLCV data
    dates = pd.date_range(start='2020-01-01', periods=100, freq='15min')
    df = pd.DataFrame({
        'date': dates,
        'open': np.random.normal(100, 5, 100),
        'high': np.random.normal(102, 5, 100),
        'low': np.random.normal(98, 5, 100),
        'close': np.random.normal(100, 5, 100),
        'volume': np.random.normal(1000, 200, 100).astype(int)
    })

    # Ensure high is always >= open, close, low
    df['high'] = df[['high', 'open', 'close']].max(axis=1) + 1

    # Ensure low is always <= open, close, high
    df['low'] = df[['low', 'open', 'close']].min(axis=1) - 1

    # Set the index to the date column
    df.set_index('date', inplace=True)

    return df


@pytest.fixture
def mock_trade():
    """Create a mock trade object for testing"""
    trade = MagicMock()
    trade.pair = "BTC/USDT"
    trade.stake_amount = 100
    trade.open_rate = 20000
    trade.open_date_utc = datetime.now() - timedelta(hours=1)
    trade.is_short = False
    trade.calc_profit_ratio = MagicMock(return_value=0.05)  # 5% profit
    # Add leverage attribute for testing
    trade.leverage = 1.0
    return trade


@pytest.fixture
def mock_short_trade():
    """Create a mock short trade object for testing"""
    trade = MagicMock()
    trade.pair = "BTC/USDT"
    trade.stake_amount = 100
    trade.open_rate = 20000
    trade.open_date_utc = datetime.now() - timedelta(hours=1)
    trade.is_short = True
    trade.calc_profit_ratio = MagicMock(return_value=0.05)  # 5% profit
    # Add leverage attribute for testing
    trade.leverage = 1.0
    return trade


@pytest.fixture
def bullish_market(regime_detector):
    """Fixture that sets up a bullish market regime with appropriate trend alignment"""
    with patch.object(regime_detector, 'detect_regime', return_value="bullish") as detect_mock:
        with patch.object(regime_detector, 'is_counter_trend',
                         side_effect=lambda direction: direction == "short") as counter_mock:
            with patch.object(regime_detector, 'is_aligned_trend',
                             side_effect=lambda direction: direction == "long") as aligned_mock:
                yield {
                    'detect_regime': detect_mock,
                    'is_counter_trend': counter_mock,
                    'is_aligned_trend': aligned_mock
                }


@pytest.fixture
def bearish_market(regime_detector):
    """Fixture that sets up a bearish market regime with appropriate trend alignment"""
    with patch.object(regime_detector, 'detect_regime', return_value="bearish") as detect_mock:
        with patch.object(regime_detector, 'is_counter_trend',
                         side_effect=lambda direction: direction == "long") as counter_mock:
            with patch.object(regime_detector, 'is_aligned_trend',
                             side_effect=lambda direction: direction == "short") as aligned_mock:
                yield {
                    'detect_regime': detect_mock,
                    'is_counter_trend': counter_mock,
                    'is_aligned_trend': aligned_mock
                }


@pytest.fixture
def neutral_market(regime_detector):
    """Fixture that sets up a neutral market regime"""
    with patch.object(regime_detector, 'detect_regime', return_value="neutral") as detect_mock:
        with patch.object(regime_detector, 'is_counter_trend', return_value=False) as counter_mock:
            with patch.object(regime_detector, 'is_aligned_trend', return_value=False) as aligned_mock:
                yield {
                    'detect_regime': detect_mock,
                    'is_counter_trend': counter_mock,
                    'is_aligned_trend': aligned_mock
                }


def set_market_state(regime_detector, regime, aligned_direction=None):
    """Helper function to set market state with specific regime and alignment

    Args:
        regime_detector: RegimeDetector to patch
        regime: "bullish", "bearish", or "neutral"
        aligned_direction: Direction ("long" or "short") that aligns with the trend, or None for neutral

    Returns:
        Dictionary of patchers that should be stopped after use
    """
    patchers = {}
    patchers['detect_regime'] = patch.object(regime_detector, 'detect_regime', return_value=regime)
    detect_mock = patchers['detect_regime'].start()

    if aligned_direction:
        # Set counter_trend for the opposite direction of aligned_direction
        counter_trend_side_effect = lambda direction: direction != aligned_direction
        aligned_trend_side_effect = lambda direction: direction == aligned_direction
    else:
        # For neutral market, nothing is counter or aligned
        counter_trend_side_effect = lambda direction: False
        aligned_trend_side_effect = lambda direction: False

    patchers['is_counter_trend'] = patch.object(
        regime_detector, 'is_counter_trend', side_effect=counter_trend_side_effect)
    patchers['is_aligned_trend'] = patch.object(
        regime_detector, 'is_aligned_trend', side_effect=aligned_trend_side_effect)

    counter_mock = patchers['is_counter_trend'].start()
    aligned_mock = patchers['is_aligned_trend'].start()

    return patchers


# Helper to clean up patchers
def cleanup_patchers(patchers):
    """Cleanup patchers by stopping them all"""
    for patcher in patchers.values():
        patcher.stop()
