from unittest.mock import patch, MagicMock

import pytest

from macd_trend_adaptive_strategy.performance.db_handler import DBHandler


@pytest.fixture
def mock_config():
    return {'user_data_dir': '/tmp'}


@pytest.fixture
def db_handler(mock_config):
    handler = DBHandler(mock_config)
    handler.set_strategy_name("TestStrategy")
    return handler


@patch('sqlite3.connect')
def test_setup_db_table(mock_connect, db_handler):
    """Test database table setup"""
    # Setup mock connection and cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    # Call the method
    db_handler._setup_db_table(mock_conn)

    # Verify the table creation SQL was executed
    mock_cursor.execute.assert_called_once()
    create_table_sql = mock_cursor.execute.call_args[0][0]
    assert "CREATE TABLE IF NOT EXISTS strategy_performance" in create_table_sql
    assert "PRIMARY KEY (strategy, direction, metric)" in create_table_sql

    # Verify commit was called
    mock_conn.commit.assert_called_once()


@patch('sqlite3.connect')
def test_clear_performance_data(mock_connect, db_handler):
    """Test clearing performance data"""
    # Setup mock connection and cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    # Mock fetchone to return a count
    mock_cursor.fetchone.return_value = [5]  # 5 records to be deleted

    # Call the method
    db_handler.clear_performance_data()

    # Verify the execute method was called twice
    assert mock_cursor.execute.call_count == 2

    # Verify the first call was the SELECT COUNT query
    select_call = mock_cursor.execute.call_args_list[0]
    assert "SELECT COUNT(*)" in select_call[0][0]
    assert select_call[0][1] == ("TestStrategy",)

    # Verify the second call was the DELETE query
    delete_call = mock_cursor.execute.call_args_list[1]
    assert "DELETE FROM strategy_performance" in delete_call[0][0]
    assert delete_call[0][1] == ("TestStrategy",)

    # Verify commit and close were called
    mock_conn.commit.assert_called_once()
    mock_conn.close.assert_called_once()


@patch('sqlite3.connect')
def test_save_load_performance_data(mock_connect, db_handler):
    """Test saving and loading performance data"""
    # Test data to save
    test_data = {
        'long': {'wins': 5, 'losses': 3, 'consecutive_wins': 2,
                 'consecutive_losses': 0, 'last_trades': [1, 0, 1], 'total_profit': 0.2},
        'short': {'wins': 4, 'losses': 4, 'consecutive_wins': 0,
                  'consecutive_losses': 1, 'last_trades': [0, 0, 1], 'total_profit': 0.1}
    }

    # Setup for save test
    mock_conn_save = MagicMock()
    mock_cursor_save = MagicMock()
    mock_connect.return_value = mock_conn_save
    mock_conn_save.cursor.return_value = mock_cursor_save

    # Call save method
    db_handler.save_performance_data(test_data)

    # Verify cursor.execute was called for each metric and direction
    assert mock_cursor_save.execute.call_count == 13  # 2 directions * 6 metrics + 1 initial connection

    # Setup for load test
    mock_conn_load = MagicMock()
    mock_cursor_load = MagicMock()
    mock_connect.return_value = mock_conn_load
    mock_conn_load.cursor.return_value = mock_cursor_load

    # Mock the fetchall result
    mock_cursor_load.fetchall.return_value = [
        ('long', 'wins', '5'),
        ('long', 'losses', '3'),
        ('long', 'consecutive_wins', '2'),
        ('long', 'consecutive_losses', '0'),
        ('long', 'last_trades', '1,0,1'),
        ('long', 'total_profit', '0.2'),
        ('short', 'wins', '4'),
        ('short', 'losses', '4'),
        ('short', 'consecutive_wins', '0'),
        ('short', 'consecutive_losses', '1'),
        ('short', 'last_trades', '0,0,1'),
        ('short', 'total_profit', '0.1')
    ]

    # Call load method
    loaded_data = db_handler.load_performance_data()

    # Verify both setup table and query were executed
    assert mock_cursor_load.execute.call_count == 2
    # Verify the second call was the SELECT query
    assert mock_cursor_load.execute.call_args_list[1][0][0].strip().startswith("SELECT direction, metric, value")

    select_sql = mock_cursor_load.execute.call_args[0][0]
    assert "SELECT direction, metric, value FROM strategy_performance WHERE strategy = ?" in select_sql

    # Verify data was loaded correctly
    assert loaded_data['long']['wins'] == 5
    assert loaded_data['long']['losses'] == 3
    assert loaded_data['long']['consecutive_wins'] == 2
    assert loaded_data['long']['consecutive_losses'] == 0
    assert loaded_data['long']['last_trades'] == [1, 0, 1]
    assert loaded_data['long']['total_profit'] == 0.2

    assert loaded_data['short']['wins'] == 4
    assert loaded_data['short']['losses'] == 4
    assert loaded_data['short']['consecutive_wins'] == 0
    assert loaded_data['short']['consecutive_losses'] == 1
    assert loaded_data['short']['last_trades'] == [0, 0, 1]
    assert loaded_data['short']['total_profit'] == 0.1


@patch('sqlite3.connect')
def test_backtest_performance_clearing(mock_connect, mock_config):
    """Test that performance data is cleared when in backtest mode"""
    # Create a backtest config
    backtest_config = mock_config.copy()
    backtest_config['runmode'] = 'backtest'

    # First, create a db_handler with backtest config
    handler = DBHandler(backtest_config)
    handler.set_strategy_name("TestStrategy")

    # Setup mock connection and cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = [10]  # 10 records to be deleted

    # Mock the in_memory_cache
    handler.in_memory_cache = {'test': 'data'}

    # Call clear_performance_data
    handler.clear_performance_data()

    # Verify the in_memory_cache was cleared
    assert handler.in_memory_cache == {}

    # Verify both SELECT and DELETE queries were executed
    assert mock_cursor.execute.call_count == 2

    # Verify commit was called
    mock_conn.commit.assert_called_once()

    # Now test the whole initialization flow by simulating strategy init
    # Reset mocks
    mock_cursor.reset_mock()
    mock_conn.reset_mock()
    mock_connect.reset_mock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = [5]

    # Create a new handler and load data (this would be part of PerformanceTracker init)
    new_handler = DBHandler(backtest_config)
    new_handler.set_strategy_name("TestStrategy")
    new_handler.clear_performance_data()

    # Now load data - this would normally be called by PerformanceTracker
    data = new_handler.load_performance_data()

    # Verify the returned data has empty/default values
    assert data['long']['wins'] == 0
    assert data['long']['losses'] == 0
    assert data['long']['last_trades'] == []
    assert data['short']['wins'] == 0
    assert data['short']['losses'] == 0
    assert data['short']['last_trades'] == []


@patch('sqlite3.connect')
def test_backtest_optimization(mock_connect):
    """Test the in-memory caching and optimization for backtests"""
    from datetime import datetime, timedelta
    from macd_trend_adaptive_strategy.performance.db_handler import DBHandler

    # Create a backtest config
    backtest_config = {'user_data_dir': '/tmp', 'runmode': 'backtest'}

    # Initialize db handler with backtest config
    handler = DBHandler(backtest_config)
    handler.set_strategy_name("TestStrategy")

    # Verify the in_memory_cache is initialized
    assert hasattr(handler, 'in_memory_cache')
    assert isinstance(handler.in_memory_cache, dict)
    assert handler.in_memory_cache == {}

    # Verify the save interval settings
    assert handler.backtest_save_interval > 0
    assert handler.backtest_trade_batch > 0

    # Mock the initial state for our test
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    # Initial performance data to test with
    test_data = {
        'long': {'wins': 5, 'losses': 3, 'consecutive_wins': 2,
                 'consecutive_losses': 0, 'last_trades': [1, 0, 1], 'total_profit': 0.2},
        'short': {'wins': 4, 'losses': 4, 'consecutive_wins': 0,
                  'consecutive_losses': 1, 'last_trades': [0, 0, 1], 'total_profit': 0.1}
    }

    # Reset the mock for testing
    mock_connect.reset_mock()

    # Test saving data - first save should update in-memory cache but not write to DB
    # due to optimization

    # Set a recent last_save_time
    current_time = int(datetime.now().timestamp())
    handler.last_save_time = current_time - 10  # 10 seconds ago
    handler.trades_since_last_save = 1  # Low count

    # Save data
    handler.save_performance_data(test_data)

    # Verify in-memory cache was updated
    assert handler.in_memory_cache == test_data

    # Verify that connect was NOT called (no DB write)
    mock_connect.assert_not_called()

    # Test save after trade batch threshold is reached
    handler.trades_since_last_save = handler.backtest_trade_batch
    handler.save_performance_data(test_data)

    # Now connect should be called
    mock_connect.assert_called_once()

    # Reset mocks for next test
    mock_connect.reset_mock()
    handler.trades_since_last_save = 1  # Reset counter

    # Test save after time interval is exceeded
    handler.last_save_time = current_time - (handler.backtest_save_interval + 10)  # Interval + 10 seconds ago
    handler.save_performance_data(test_data)

    # Connect should be called again
    mock_connect.assert_called_once()

    # Test that the time and counter are reset after a save
    assert handler.last_save_time >= current_time
    assert handler.trades_since_last_save == 0

    # Now test loading with in-memory cache
    new_data = {
        'long': {'wins': 10, 'losses': 5},
        'short': {'wins': 8, 'losses': 3}
    }

    # Set in-memory cache
    handler.in_memory_cache = new_data

    # Reset mock
    mock_connect.reset_mock()

    # Load data - should use in-memory cache without DB access
    loaded_data = handler.load_performance_data()

    # Verify connect was not called (used cache)
    mock_connect.assert_not_called()

    # Verify returned data matches cache
    assert loaded_data == new_data