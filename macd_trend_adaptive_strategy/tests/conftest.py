import json
import os
import tempfile
import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from macd_trend_adaptive_strategy.config.strategy_config import StrategyConfig, StrategyMode
from macd_trend_adaptive_strategy.performance.tracker import PerformanceTracker
from macd_trend_adaptive_strategy.regime.detector import RegimeDetector
from macd_trend_adaptive_strategy.risk_management.roi_calculator import ROICalculator
from macd_trend_adaptive_strategy.risk_management.stoploss_calculator import StoplossCalculator
from macd_trend_adaptive_strategy.performance.db_handler import DBHandler


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
    mock_db = MagicMock()  # Use MagicMock without spec to avoid attribute errors

    # Add required methods
    mock_db.load_performance_data.return_value = {
        'long': {'wins': 10, 'losses': 5, 'consecutive_wins': 2,
                 'consecutive_losses': 0, 'last_trades': [1, 0, 1, 1], 'total_profit': 0.8},
        'short': {'wins': 8, 'losses': 7, 'consecutive_wins': 0,
                  'consecutive_losses': 1, 'last_trades': [0, 1, 0, 1], 'total_profit': 0.3}
    }

    mock_db.save_performance_data = MagicMock()
    mock_db.set_strategy_name = MagicMock()
    mock_db.clear_performance_data = MagicMock()

    return mock_db


@pytest.fixture
def performance_tracker(db_handler):
    """Create a PerformanceTracker for testing"""
    tracker = MagicMock()

    # Initialize performance tracking for testing
    tracker.performance_tracking = {
        'long': {'wins': 5, 'losses': 5, 'last_trades': [1, 0, 1, 1]},
        'short': {'wins': 5, 'losses': 5, 'last_trades': [0, 1, 0, 1]}
    }

    # Mock methods and ensure they return values that can be formatted
    tracker.get_recent_win_rate = MagicMock(return_value=0.5)
    tracker.get_recent_trades_count = MagicMock(return_value=4)
    tracker.get_win_rate = MagicMock(return_value=0.5)

    # Fix for the log_trade_exit formatting issue
    tracker.update_performance = MagicMock()
    tracker.log_performance_stats = MagicMock()

    return tracker


@pytest.fixture
def regime_detector(performance_tracker, strategy_config):
    """Create a RegimeDetector for testing"""
    detector = MagicMock(spec=RegimeDetector)

    # Add missing config attribute
    detector.config = strategy_config

    # Mock methods with proper return values
    detector.detect_regime = MagicMock(return_value='neutral')
    detector.is_counter_trend = MagicMock(side_effect=lambda direction: direction == "short")
    detector.is_aligned_trend = MagicMock(side_effect=lambda direction: direction == "long")

    return detector


@pytest.fixture
def roi_calculator(performance_tracker, regime_detector, strategy_config):
    """Create a ROICalculator for testing"""
    calculator = MagicMock(spec=ROICalculator)

    # Add missing attributes
    calculator.performance_tracker = performance_tracker
    calculator.config = strategy_config
    calculator.roi_cache = {'long': 0.03, 'short': 0.02, 'last_updated': 0}

    # Mock methods with proper return values
    calculator.update_roi_cache = MagicMock()
    calculator._calculate_adaptive_roi = MagicMock(return_value=0.045)
    calculator.get_trade_roi = MagicMock(side_effect=lambda direction:
    0.03 if direction == 'long' else 0.02)

    return calculator


@pytest.fixture
def stoploss_calculator(regime_detector, strategy_config):
    """Create a StoplossCalculator for testing"""
    calculator = MagicMock(spec=StoplossCalculator)

    # Add missing attributes
    calculator.config = strategy_config

    # Mock methods with proper return values
    calculator.calculate_dynamic_stoploss = MagicMock(return_value=-0.02)
    calculator.calculate_stoploss_price = MagicMock(side_effect=lambda entry, sl, is_short:
    entry * (1 + sl) if not is_short else entry * (1 - sl))
    calculator.calculate_fallback_stoploss_price = MagicMock(side_effect=lambda entry, sl, is_short:
    entry * (1 + sl) if not is_short else entry * (1 - sl))

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