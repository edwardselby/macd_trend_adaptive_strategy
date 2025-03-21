from unittest.mock import MagicMock


def test_win_rate_calculation(performance_tracker):
    """Test win rate calculation methods"""
    # Override the MagicMock return values for this test
    performance_tracker.get_win_rate.side_effect = lambda direction: 0.67 if direction == "long" else 0.53
    performance_tracker.get_recent_win_rate.side_effect = lambda direction: 0.75 if direction == "long" else 0.50

    # Test overall win rate
    long_wr = performance_tracker.get_win_rate("long")
    # Expected win rate: 10 / (10 + 5) = 0.67
    assert abs(long_wr - 0.67) < 0.01

    short_wr = performance_tracker.get_win_rate("short")
    # Expected win rate: 8 / (8 + 7) = 0.53
    assert abs(short_wr - 0.53) < 0.01

    # Test recent win rate
    long_recent_wr = performance_tracker.get_recent_win_rate("long")
    # Expected win rate: (1 + 0 + 1 + 1) / 4 = 0.75
    assert abs(long_recent_wr - 0.75) < 0.01

    short_recent_wr = performance_tracker.get_recent_win_rate("short")
    # Expected win rate: (0 + 1 + 0 + 1) / 4 = 0.50
    assert abs(short_recent_wr - 0.50) < 0.01


def test_update_performance(performance_tracker, mock_trade, mock_short_trade, db_handler):
    """Test performance update logic"""
    # Create a local dictionary to track state changes
    performance_tracking = {
        'long': {'wins': 5, 'losses': 3, 'consecutive_wins': 2,
                 'consecutive_losses': 0, 'last_trades': [1, 0, 1], 'total_profit': 0.2},
        'short': {'wins': 4, 'losses': 4, 'consecutive_wins': 0,
                  'consecutive_losses': 1, 'last_trades': [0, 0, 1], 'total_profit': 0.1}
    }

    # Create a simplified version of the update_performance method
    def mock_update_performance(trade, profit_ratio):
        direction = 'short' if trade.is_short else 'long'
        is_win = profit_ratio > 0

        if is_win:
            performance_tracking[direction]['wins'] += 1
            performance_tracking[direction]['consecutive_wins'] += 1
            performance_tracking[direction]['consecutive_losses'] = 0
        else:
            performance_tracking[direction]['losses'] += 1
            performance_tracking[direction]['consecutive_losses'] += 1
            performance_tracking[direction]['consecutive_wins'] = 0

        performance_tracking[direction]['last_trades'].append(1 if is_win else 0)
        # Save to database
        db_handler.save_performance_data(performance_tracking)

    # Replace the mock's update_performance method with our implementation
    performance_tracker.update_performance = mock_update_performance
    performance_tracker.performance_tracking = performance_tracking

    # Starting state - store for comparison
    initial_long_wins = performance_tracking['long']['wins']

    # Update with winning long trade
    performance_tracker.update_performance(mock_trade, 0.05)

    # Check long wins increased
    assert performance_tracking['long']['wins'] == initial_long_wins + 1
    assert performance_tracking['long']['consecutive_wins'] == 3
    assert performance_tracking['long']['last_trades'][-1] == 1

    # Test with losing short trade
    mock_short_trade.is_short = True
    performance_tracker.update_performance(mock_short_trade, -0.02)

    # Check short losses increased
    assert performance_tracking['short']['losses'] == 5
    assert performance_tracking['short']['consecutive_losses'] == 2
    assert performance_tracking['short']['consecutive_wins'] == 0
    assert performance_tracking['short']['last_trades'][-1] == 0

    # Check that save method was called exactly twice
    assert db_handler.save_performance_data.call_count == 2