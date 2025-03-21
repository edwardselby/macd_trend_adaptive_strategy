from unittest.mock import patch, MagicMock


def test_win_rate_calculation(performance_tracker):
    """Test win rate calculation methods"""
    # Set up test data
    performance_tracker.performance_tracking = {
        'long': {'wins': 10, 'losses': 5, 'consecutive_wins': 0,
                 'consecutive_losses': 0, 'last_trades': [1, 0, 1, 1], 'total_profit': 0.8},
        'short': {'wins': 8, 'losses': 7, 'consecutive_wins': 0,
                  'consecutive_losses': 0, 'last_trades': [0, 1, 0, 1], 'total_profit': 0.3}
    }

    # Test overall win rate
    long_wr = performance_tracker.get_win_rate("long")
    # Expected: 10 / (10 + 5) = 0.6667
    assert abs(long_wr - 0.6667) < 0.01

    short_wr = performance_tracker.get_win_rate("short")
    # Expected: 8 / (8 + 7) = 0.5333
    assert abs(short_wr - 0.5333) < 0.01

    # Test recent win rate
    long_recent_wr = performance_tracker.get_recent_win_rate("long")
    # Expected: (1 + 0 + 1 + 1) / 4 = 0.75
    assert abs(long_recent_wr - 0.75) < 0.01

    short_recent_wr = performance_tracker.get_recent_win_rate("short")
    # Expected: (0 + 1 + 0 + 1) / 4 = 0.5
    assert abs(short_recent_wr - 0.5) < 0.01


def test_update_performance(performance_tracker, db_handler):
    """Test update_performance method"""
    # Set up test data
    performance_tracker.performance_tracking = {
        'long': {'wins': 5, 'losses': 3, 'consecutive_wins': 2,
                 'consecutive_losses': 0, 'last_trades': [1, 0, 1], 'total_profit': 0.2},
        'short': {'wins': 4, 'losses': 4, 'consecutive_wins': 0,
                  'consecutive_losses': 1, 'last_trades': [0, 0, 1], 'total_profit': 0.1}
    }

    # Create a mock Trade object for long position
    long_trade = MagicMock()
    long_trade.pair = "BTC/USDT"
    long_trade.is_short = False  # Long trade

    # Test with winning long trade
    performance_tracker.update_performance(long_trade, 0.05)  # 5% profit

    # Verify state was updated correctly
    assert performance_tracker.performance_tracking['long']['wins'] == 6
    assert performance_tracker.performance_tracking['long']['consecutive_wins'] == 3
    assert performance_tracker.performance_tracking['long']['consecutive_losses'] == 0
    assert performance_tracker.performance_tracking['long']['last_trades'][-1] == 1
    assert abs(performance_tracker.performance_tracking['long']['total_profit'] - 0.25) < 0.01

    # Verify db_handler.save_performance_data was called
    db_handler.save_performance_data.assert_called_with(performance_tracker.performance_tracking)

    # Reset the mock
    db_handler.save_performance_data.reset_mock()

    # Create a mock Trade object for short position
    short_trade = MagicMock()
    short_trade.pair = "BTC/USDT"
    short_trade.is_short = True

    # Test with losing short trade
    performance_tracker.update_performance(short_trade, -0.02)  # 2% loss

    # Verify state was updated correctly
    assert performance_tracker.performance_tracking['short']['losses'] == 5
    assert performance_tracker.performance_tracking['short']['consecutive_losses'] == 2
    assert performance_tracker.performance_tracking['short']['consecutive_wins'] == 0
    assert performance_tracker.performance_tracking['short']['last_trades'][-1] == 0

    # Verify db_handler.save_performance_data was called
    db_handler.save_performance_data.assert_called_with(performance_tracker.performance_tracking)


def test_get_recent_trades_count(performance_tracker):
    """Test get_recent_trades_count method"""
    # Set up test data
    performance_tracker.performance_tracking = {
        'long': {'last_trades': [1, 0, 1, 1]},
        'short': {'last_trades': [0, 1, 0, 1, 0]}
    }

    # Test the method
    assert performance_tracker.get_recent_trades_count('long') == 4
    assert performance_tracker.get_recent_trades_count('short') == 5


def test_max_recent_trades_limit(performance_tracker, db_handler):
    """Test that last_trades list is limited to max_recent_trades"""
    # Set up test data with max_recent_trades = 5
    performance_tracker.max_recent_trades = 5
    performance_tracker.performance_tracking = {
        'long': {'wins': 5, 'losses': 3, 'consecutive_wins': 0,
                 'consecutive_losses': 0, 'last_trades': [1, 1, 1, 1], 'total_profit': 0.2},
    }

    # Create a mock Trade
    trade = MagicMock()
    trade.pair = "BTC/USDT"
    trade.is_short = False

    # Add 3 more trades (current length is 4)
    for i in range(3):
        performance_tracker.update_performance(trade, 0.01)

    # Check that length is capped at 5
    assert len(performance_tracker.performance_tracking['long']['last_trades']) == 5

    # Check that the oldest trade was removed (should be all 1's)
    assert performance_tracker.performance_tracking['long']['last_trades'] == [1, 1, 1, 1, 1]


def test_log_performance_stats(performance_tracker):
    """Test log_performance_stats method"""
    # Set up test data
    performance_tracker.performance_tracking = {
        'long': {'wins': 10, 'losses': 5, 'total_profit': 0.5},
        'short': {'wins': 7, 'losses': 8, 'total_profit': 0.2}
    }

    # FIXED: Use the correct import path for patching
    # Based on the imports in tracker.py: from ..utils import log_performance_update, log_performance_summary
    with patch('performance.tracker.log_performance_summary') as mock_log:
        # Call the method
        performance_tracker.log_performance_stats()

        # Verify it was called with correct arguments
        mock_log.assert_called_once()

        # Check some key arguments
        args, kwargs = mock_log.call_args
        assert kwargs['total_trades'] == 30
        assert kwargs['long_wins'] == 10
        assert kwargs['long_losses'] == 5
        assert kwargs['short_wins'] == 7
        assert kwargs['short_losses'] == 8
        assert abs(kwargs['long_wr'] - 0.6667) < 0.01
        assert abs(kwargs['short_wr'] - 0.4667) < 0.01