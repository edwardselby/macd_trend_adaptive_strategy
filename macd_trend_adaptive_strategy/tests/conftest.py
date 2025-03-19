from datetime import datetime, timedelta
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from macd_trend_adaptive_strategy.config import StrategyConfig, StrategyMode


@pytest.fixture
def strategy_config():
    """Return a strategy configuration object with test settings"""
    return StrategyConfig(StrategyMode.DEFAULT)


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
def mock_db_handler():
    """Create a mock database handler"""
    handler = MagicMock()
    handler.load_performance_data.return_value = {
        'long': {'wins': 10, 'losses': 5, 'consecutive_wins': 2,
                 'consecutive_losses': 0, 'last_trades': [1, 0, 1, 1], 'total_profit': 0.8},
        'short': {'wins': 8, 'losses': 7, 'consecutive_wins': 0,
                  'consecutive_losses': 1, 'last_trades': [0, 1, 0, 1], 'total_profit': 0.3}
    }
    return handler


@pytest.fixture
def performance_tracker(mock_db_handler):
    """Create a performance tracker with mock data"""
    from macd_trend_adaptive_strategy.performance.tracker import PerformanceTracker

    tracker = PerformanceTracker(mock_db_handler, max_recent_trades=10)
    return tracker


@pytest.fixture
def regime_detector(performance_tracker, strategy_config):
    """Create a regime detector with mock data"""
    from macd_trend_adaptive_strategy.regime.detector import RegimeDetector

    detector = RegimeDetector(performance_tracker, strategy_config)
    return detector


@pytest.fixture
def roi_calculator(performance_tracker, regime_detector, strategy_config):
    """Create an ROI calculator with mock data"""
    from macd_trend_adaptive_strategy.risk_management.roi_calculator import ROICalculator

    calculator = ROICalculator(performance_tracker, regime_detector, strategy_config)
    return calculator


@pytest.fixture
def stoploss_calculator(regime_detector, strategy_config):
    """Create a stoploss calculator with mock data"""
    from macd_trend_adaptive_strategy.risk_management.stoploss_calculator import StoplossCalculator

    calculator = StoplossCalculator(regime_detector, strategy_config)
    return calculator


@pytest.fixture
def strategy(mock_db_handler, performance_tracker, regime_detector, roi_calculator, stoploss_calculator,
             strategy_config):
    """
    Create a strategy instance with mock components for integration testing.
    This fixture sets up a strategy that closely mimics how it would interact with FreqTrade.
    """
    from strategy import MACDTrendAdaptiveStrategy

    # Create a base strategy with FreqTrade-like config
    config = {
        'user_data_dir': '/tmp',
        'runmode': 'dry_run',
        # Add any FreqTrade settings that might affect stoploss behavior
        'stoploss': -0.03,  # FreqTrade's global stoploss setting
        'stoploss_on_exchange': False,
        'trailing_stop': False,
    }

    strategy = MACDTrendAdaptiveStrategy(config)

    # Replace components with our test fixtures
    strategy.db_handler = mock_db_handler
    strategy.performance_tracker = performance_tracker
    strategy.regime_detector = regime_detector
    strategy.roi_calculator = roi_calculator
    strategy.stoploss_calculator = stoploss_calculator
    strategy.strategy_config = strategy_config

    # Initialize trade cache
    strategy.trade_cache = {
        'active_trades': {}
    }

    # Log key parameters for debugging
    print(f"Strategy initialized with:")
    print(f"- Default stoploss: {strategy.stoploss}")
    print(f"- Static stoploss from config: {strategy.strategy_config.static_stoploss}")
    print(f"- Dynamic stoploss enabled: {strategy.strategy_config.use_dynamic_stoploss}")
    print(f"- Min stoploss: {strategy.strategy_config.min_stoploss}")

    return strategy


@pytest.fixture
def strategy_config():
    """Return a strategy configuration object with test settings"""
    # Use the new StrategyConfig class with the default mode
    config = StrategyConfig(StrategyMode.DEFAULT)

    # Make sure risk_reward_ratio is properly set to float
    if not isinstance(config.risk_reward_ratio, float):
        # Parse the R:R ratio to float if it's still a string
        try:
            risk, reward = config.risk_reward_ratio_str.split(':')
            config.risk_reward_ratio = float(risk.strip()) / float(reward.strip())
        except:
            # Fallback
            config.risk_reward_ratio = 0.5  # Default 1:2 ratio

    return config
