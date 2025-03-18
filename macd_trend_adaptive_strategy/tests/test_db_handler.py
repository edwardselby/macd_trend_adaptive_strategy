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

    # Call the method
    db_handler.clear_performance_data()

    # Verify the DELETE SQL was executed with correct strategy name
    mock_cursor.execute.assert_called_once()
    delete_sql = mock_cursor.execute.call_args[0][0]
    assert "DELETE FROM strategy_performance WHERE strategy = ?" in delete_sql
    assert mock_cursor.execute.call_args[0][1] == ("TestStrategy",)

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
    assert mock_cursor_save.execute.call_count == 12  # 2 directions * 6 metrics

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

    # Verify query was executed
    mock_cursor_load.execute.assert_called_once()
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