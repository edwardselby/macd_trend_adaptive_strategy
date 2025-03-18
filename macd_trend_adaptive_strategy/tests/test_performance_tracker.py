def test_win_rate_calculation(performance_tracker):
    """Test win rate calculation methods"""
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


def test_update_performance(performance_tracker, mock_trade, mock_short_trade, mock_db_handler):
    """Test performance update logic"""
    # Starting state
    initial_long_wins = performance_tracker.performance_tracking['long']['wins']
    initial_short_wins = performance_tracker.performance_tracking['short']['wins']

    # Update with winning long trade
    performance_tracker.update_performance(mock_trade, 0.05)

    # Check long wins increased
    assert performance_tracker.performance_tracking['long']['wins'] == initial_long_wins + 1
    # Check consecutive wins increased
    assert performance_tracker.performance_tracking['long']['consecutive_wins'] == 3
    # Check last_trades was updated
    assert performance_tracker.performance_tracking['long']['last_trades'][-1] == 1

    # Test with losing short trade
    mock_short_trade.calc_profit_ratio = lambda x: -0.02
    performance_tracker.update_performance(mock_short_trade, -0.02)

    # Check short losses increased
    assert performance_tracker.performance_tracking['short']['losses'] == 8
    # Check consecutive losses increased
    assert performance_tracker.performance_tracking['short']['consecutive_losses'] == 2
    # Check consecutive wins reset
    assert performance_tracker.performance_tracking['short']['consecutive_wins'] == 0
    # Check last_trades was updated
    assert performance_tracker.performance_tracking['short']['last_trades'][-1] == 0

    # Check that save method was called
    assert mock_db_handler.save_performance_data.call_count == 2
