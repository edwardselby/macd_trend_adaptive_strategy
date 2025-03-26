import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


class DBHandler:
    """Handles database operations for performance tracking"""

    def __init__(self, config: dict, is_backtest: bool = False) -> None:
        """Initialize with FreqTrade config"""
        self.config = config
        self.strategy_name = None  # Will be set by the strategy
        self.is_backtest = is_backtest

        # Add caching for backtest mode
        if self.is_backtest:
            self.in_memory_cache = {}
            self.last_save_time = int(datetime.now().timestamp())
            self.trades_since_last_save = 0
            self.backtest_save_interval = 300  # 5 minutes
            self.backtest_trade_batch = 100  # Save every 100 trades
            logger.info(f"DBHandler initialized in backtest mode with optimized saving")

    def set_strategy_name(self, name: str) -> None:
        """Set the strategy name for database operations"""
        self.strategy_name = name

    def _get_db_connection(self):
        """Get a connection to the FreqTrade database"""
        db_path = Path(self.config['user_data_dir']) / 'tradesv3.sqlite'
        return sqlite3.connect(db_path)

    def _setup_db_table(self, conn):
        """Ensure performance tracking table exists"""
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS strategy_performance (
            strategy TEXT,
            direction TEXT,
            metric TEXT,
            value TEXT,
            updated_at TIMESTAMP,
            PRIMARY KEY (strategy, direction, metric)
        )
        ''')
        conn.commit()

    def clear_performance_data(self) -> None:
        """Clear performance data when starting a backtest"""
        if not self.strategy_name:
            logger.error("Strategy name not set for DBHandler")
            return

        try:
            # Clear the in-memory cache first
            if self.is_backtest:
                self.in_memory_cache = {}
                logger.info(f"Cleared in-memory cache for {self.strategy_name}")

            # Then clear the database
            conn = self._get_db_connection()
            cursor = conn.cursor()

            # Check how many records exist
            cursor.execute(
                "SELECT COUNT(*) FROM strategy_performance WHERE strategy = ?",
                (self.strategy_name,)
            )
            count = cursor.fetchone()[0]

            # Delete the records
            cursor.execute(
                "DELETE FROM strategy_performance WHERE strategy = ?",
                (self.strategy_name,)
            )
            conn.commit()
            conn.close()

            logger.info(f"Cleared {count} performance records for {self.strategy_name} before backtest")

        except Exception as e:
            logger.error(f"Error clearing performance data: {e}")

    def load_performance_data(self) -> Dict[str, Dict[str, Any]]:
        """Load performance tracking data from database"""
        # Default tracking structure
        performance_tracking = {
            'long': {'wins': 0, 'losses': 0, 'consecutive_wins': 0,
                     'consecutive_losses': 0, 'last_trades': [], 'total_profit': 0.0},
            'short': {'wins': 0, 'losses': 0, 'consecutive_wins': 0,
                      'consecutive_losses': 0, 'last_trades': [], 'total_profit': 0.0}
        }

        if not self.strategy_name:
            logger.error("Strategy name not set for DBHandler")
            return performance_tracking

        # For backtest, check if we have in-memory cache
        if self.is_backtest and self.in_memory_cache:
            logger.debug("Using in-memory cache for performance data in backtest mode")
            return self.in_memory_cache

        try:
            conn = self._get_db_connection()
            self._setup_db_table(conn)
            cursor = conn.cursor()

            cursor.execute(
                "SELECT direction, metric, value FROM strategy_performance WHERE strategy = ?",
                (self.strategy_name,)
            )

            rows = cursor.fetchall()
            conn.close()

            if not rows:
                logger.info(f"No performance data found in database for {self.strategy_name}, using defaults")
                # Update in-memory cache for backtest mode with default values
                if self.is_backtest:
                    self.in_memory_cache = performance_tracking
                return performance_tracking

            # Process the data
            for direction, metric, value in rows:
                if metric in ['wins', 'losses', 'consecutive_wins', 'consecutive_losses']:
                    performance_tracking[direction][metric] = int(value)
                elif metric == 'total_profit':
                    performance_tracking[direction][metric] = float(value)
                elif metric == 'last_trades':
                    performance_tracking[direction][metric] = [int(x) for x in value.split(',') if x]

            logger.info(f"Loaded performance tracking from database: {performance_tracking}")

            # Update in-memory cache for backtest mode
            if self.is_backtest:
                self.in_memory_cache = performance_tracking

            return performance_tracking

        except Exception as e:
            logger.error(f"Error loading performance data from database: {e}")
            return performance_tracking

    def save_performance_data(self, performance_tracking: Dict[str, Dict[str, Any]]) -> None:
        """Save current performance metrics to database"""
        if not self.strategy_name:
            logger.error("Strategy name not set for DBHandler")
            return

        # For backtest mode, optimize saving frequency
        if self.is_backtest:
            self.in_memory_cache = performance_tracking
            self.trades_since_last_save += 1
            current_time = int(datetime.now().timestamp())

            # Only save periodically or after batch of trades
            if (current_time - self.last_save_time < self.backtest_save_interval and
                    self.trades_since_last_save < self.backtest_trade_batch):
                return

            logger.debug(f"Saving performance data after {self.trades_since_last_save} trades")
            self.last_save_time = current_time
            self.trades_since_last_save = 0

        try:
            conn = self._get_db_connection()
            self._setup_db_table(conn)
            cursor = conn.cursor()

            # Use a single transaction for better performance
            conn.execute("BEGIN TRANSACTION")

            now = datetime.now().isoformat()

            for direction in ['long', 'short']:
                for metric, value in performance_tracking[direction].items():
                    # Convert value to string for storage
                    if metric == 'last_trades':
                        db_value = ','.join([str(x) for x in value])
                    else:
                        db_value = str(value)

                    cursor.execute('''
                    INSERT OR REPLACE INTO strategy_performance 
                    (strategy, direction, metric, value, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ''', (self.strategy_name, direction, metric, db_value, now))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error saving performance data to database: {e}")