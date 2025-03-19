import logging
import os
from datetime import datetime
from typing import List, Optional

import pandas as pd
from freqtrade.enums.exittype import ExitType
from freqtrade.persistence import Trade
from freqtrade.strategy.interface import IStrategy, ExitCheckTuple

from macd_trend_adaptive_strategy.config.strategy_config import StrategyConfig, StrategyMode
from macd_trend_adaptive_strategy.indicators.technical import calculate_indicators, populate_entry_signals
from macd_trend_adaptive_strategy.performance.db_handler import DBHandler
from macd_trend_adaptive_strategy.performance.tracker import PerformanceTracker
from macd_trend_adaptive_strategy.regime.detector import RegimeDetector
from macd_trend_adaptive_strategy.risk_management.roi_calculator import ROICalculator
from macd_trend_adaptive_strategy.risk_management.stoploss_calculator import StoplossCalculator
from macd_trend_adaptive_strategy.utils import (
    get_direction, create_trade_id,
    log_new_trade, log_trade_exit, log_roi_exit,
    log_trade_cache_recreated, log_strategy_initialization, log_stoploss_hit,
)

# Set up strategy-wide logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class MACDTrendAdaptiveStrategy(IStrategy):
    """
    Enhanced MACD Strategy with Trend Detection, Market Regime Detection,
    Fully Adaptive ROI and Dynamic Stoploss - Simplified Configuration Version

    This strategy uses just three configurable parameters:
    - risk_reward_ratio (expressed as "1:2") - risk-to-reward ratio for calculating stoplosses
    - min_roi (e.g., 0.02) - minimum target ROI
    - max_roi (e.g., 0.05) - maximum target ROI

    Configure the strategy by creating a file at: user_data/strategy_config.json

    Core strategy logic:
    - Uses MACD crossovers filtered by trend indicators for entry signals
    - Implements dynamic regime detection based on recent trade performance
    - Applies fully adaptive take-profit levels based on win rate performance
    - Dynamic stoploss calculation based on ROI and configurable risk-reward ratio
    - Adjusts both ROI and stoploss based on whether trades align with or counter the trend
    """

    # Version 3 API - required for proper leverage
    INTERFACE_VERSION = 3

    # ===== CONFIGURABLE PARAMETER SET =====
    # Change this to select a different parameter set
    STRATEGY_MODE = StrategyMode.TIMEFRAME_5M
    # =====================================

    # Strategy Parameters - Setting minimal_roi to empty dict to ensure we only use custom_exit logic
    minimal_roi = {}  # Disable standard ROI table - we'll use custom_exit exclusively

    # Futures and leverage settings
    can_short = True
    leverage_config = {"*": {"*": 10.0}}

    # Order configuration
    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "limit",
        "stoploss_on_exchange": False
    }
    entry_pricing = {"price_side": "same", "use_order_book": False, "order_book_top": 1}
    exit_pricing = {"price_side": "same", "use_order_book": False, "order_book_top": 1}

    # Required settings
    process_only_new_candles = True
    use_custom_stoploss = True
    position_adjustment_enable = False
    use_exit_signal = True
    ignore_roi_if_entry_signal = False

    def __init__(self, config: dict) -> None:
        """
        Initialize the strategy with all required components

        Args:
            config: FreqTrade configuration
        """
        super().__init__(config)

        # Path to the strategy configuration file
        config_path = "user_data/strategy_config.json"

        # Check if the config file exists, otherwise don't pass it
        if os.path.exists(config_path):
            # Initialize strategy configuration with selected mode and configuration file
            self.strategy_config = StrategyConfig(self.STRATEGY_MODE, config_path)
        else:
            # Use default configuration without file
            self.strategy_config = StrategyConfig(self.STRATEGY_MODE)

        # Set a realistic stoploss value (still used as the initial/base stoploss)
        self.stoploss = self.strategy_config.static_stoploss

        # Apply startup candle count setting
        self.startup_candle_count = self.strategy_config.startup_candle_count

        # Initialize timeframe
        self.timeframe = self.strategy_config.timeframe

        # Set up database handler
        self.db_handler = DBHandler(config)
        self.db_handler.set_strategy_name(self.__class__.__name__)

        # Check if we're in backtest mode
        self.is_backtest = (
                config.get('runmode') in ('backtest', 'hyperopt') or
                config.get('backtest', False) or  # This parameter exists in backtest config
                'timerange' in config or  # Timerange is set for backtests
                'export' in config  # Export is typically set for backtests
        )

        # Clear performance data at the start of each backtest
        if self.is_backtest:
            self.db_handler.clear_performance_data()

        # Initialize performance tracker AFTER clearing data
        self.performance_tracker = PerformanceTracker(
            self.db_handler,
            max_recent_trades=self.strategy_config.max_recent_trades
        )

        # Initialize regime detector
        self.regime_detector = RegimeDetector(
            self.performance_tracker,
            self.strategy_config
        )

        # Initialize ROI calculator
        self.roi_calculator = ROICalculator(
            self.performance_tracker,
            self.regime_detector,
            self.strategy_config
        )

        # Initialize stoploss calculator
        self.stoploss_calculator = StoplossCalculator(
            self.regime_detector,
            self.strategy_config
        )

        # Initialize trade cache for active trades
        self.trade_cache = {
            'active_trades': {}
        }

        # Log strategy initialization details
        log_strategy_initialization(
            mode=self.STRATEGY_MODE,
            timeframe=self.timeframe,
            indicators={
                'fast': self.strategy_config.fast_length,
                'slow': self.strategy_config.slow_length,
                'signal': self.strategy_config.signal_length
            },
            roi_config={
                'min': self.strategy_config.min_roi,
                'max': self.strategy_config.max_roi
            },
            stoploss_config={
                'min': self.strategy_config.min_stoploss,
                'max': self.strategy_config.max_stoploss
            }
        )

        # Override freqtrade's stoploss setting with our derived value
        self.stoploss = self.strategy_config.static_stoploss

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: Optional[str],
                            side: str, **kwargs) -> bool:
        """
        Called right before placing a buy order.
        This is where we register a new trade in our tracking system and calculate
        its initial dynamic stoploss.
        """
        trade_id = create_trade_id(pair, current_time)
        is_short = side == 'short'

        # Get or create trade cache entry
        cache_entry = self._get_or_create_trade_cache(
            trade_id, pair, rate, current_time, is_short
        )

        # Log new trade
        log_new_trade(
            pair=pair,
            direction=cache_entry['direction'],
            regime=cache_entry['regime'],
            roi=cache_entry['roi'],
            stoploss=cache_entry['stoploss'],
            is_counter_trend=cache_entry['is_counter_trend'],
            is_aligned_trend=cache_entry['is_aligned_trend'],
            rate=rate
        )

        return True

    def confirm_trade_exit(self, pair: str, trade: Trade, order_type: str, amount: float,
                           rate: float, time_in_force: str, exit_reason: str,
                           current_time: datetime, **kwargs) -> bool:
        """
        Update performance tracking when a trade exits.
        """
        # Calculate profit ratio
        profit_ratio = trade.calc_profit_ratio(rate)

        # Update performance tracking
        self.performance_tracker.update_performance(trade, profit_ratio)

        # Remove trade from active_trades cache
        trade_id = create_trade_id(pair, trade.open_date_utc)
        if trade_id in self.trade_cache['active_trades']:
            del self.trade_cache['active_trades'][trade_id]

        # Log current market regime and win rates after updating
        direction = get_direction(trade.is_short)
        profit_ratio = trade.calc_profit_ratio(rate)
        regime = self.regime_detector.detect_regime()
        long_wr = self.performance_tracker.get_recent_win_rate('long')
        short_wr = self.performance_tracker.get_recent_win_rate('short')

        log_trade_exit(
            pair=pair,
            direction=direction,
            profit_ratio=profit_ratio,
            exit_reason=exit_reason,
            regime=regime,
            long_wr=long_wr,
            short_wr=short_wr
        )

        return True

    def should_exit(self, trade: Trade, rate: float, date: datetime, **kwargs) -> List:
        """
        Combined logic for both ROI (take profit) and stoploss.
        This replaces both the old should_exit and custom_stoploss methods.
        """
        # Get current profit
        current_profit = trade.calc_profit_ratio(rate)

        # Get trade details from cache or handle missing trade
        trade_id = create_trade_id(trade.pair, trade.open_date_utc)
        if trade_id not in self.trade_cache['active_trades']:
            self._handle_missing_trade(trade, date)

        # Get or create trade cache entry
        trade_params = self._get_or_create_trade_cache(
            trade_id, trade.pair, trade.open_rate, trade.open_date_utc, trade.is_short
        )

        # Check for stoploss hit - using price-based comparison instead of profit ratio
        if (not trade.is_short and rate <= trade_params['stoploss_price']) or \
                (trade.is_short and rate >= trade_params['stoploss_price']):
            direction = trade_params['direction']

            # Log additional debugging info
            logger.debug(
                f"Stoploss hit: Direction={direction}, is_short={trade.is_short}, "
                f"Current price={rate}, Stoploss price={trade_params['stoploss_price']}, "
                f"Entry price={trade.open_rate}, Profit ratio={current_profit:.4%}"
            )

            # Use the appropriate log function for stoploss hit
            log_stoploss_hit(
                pair=trade.pair,
                direction=direction,
                current_price=rate,
                stoploss_price=trade_params['stoploss_price'],
                entry_price=trade.open_rate,
                profit_ratio=current_profit,
                regime=trade_params['regime']
            )

            return [ExitCheckTuple(exit_type=ExitType.STOP_LOSS,
                                   exit_reason=f"stoploss_{direction}_{trade_params['regime']}")]

        # De-leverage for correct comparison with profit targets
        # Handle both real Trade objects and mocks in tests
        try:
            leverage = float(trade.leverage)
            if leverage <= 0:  # Safeguard against invalid leverage values
                leverage = 1.0
        except (TypeError, ValueError, AttributeError):
            # Default to leverage 1.0 if attribute doesn't exist or can't be converted
            leverage = 1.0

        adjusted_profit = float(current_profit) / leverage

        # Check for default ROI exit if enabled
        if (self.strategy_config.use_default_roi_exit and
                adjusted_profit >= self.strategy_config.default_roi and
                adjusted_profit < trade_params['roi']):

            # If profit is above default_roi but below adaptive ROI, exit with default_roi reason
            logger.debug(
                f"Default ROI exit: {trade.pair}, profit={adjusted_profit:.2%}, "
                f"default_roi={self.strategy_config.default_roi:.2%}, "
                f"adaptive_roi={trade_params['roi']:.2%}"
            )

            return [ExitCheckTuple(exit_type=ExitType.ROI, exit_reason="default_roi")]

        # Check for adaptive ROI exit (take profit)
        if adjusted_profit >= trade_params['roi']:
            trade_type = ("countertrend" if trade_params['is_counter_trend']
                          else "aligned" if trade_params['is_aligned_trend']
            else "neutral")

            log_roi_exit(
                pair=trade.pair,
                direction=trade_params['direction'],
                trend_type=trade_type,
                target_roi=trade_params['roi'],
                actual_profit=current_profit,
                regime=trade_params['regime']
            )

            return [ExitCheckTuple(exit_type=ExitType.ROI,
                                   exit_reason=f"adaptive_roi_{trade_type}_{trade_params['regime']}")]

        # Otherwise, continue holding
        return []

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        """Log performance stats periodically during backtesting"""

        if self.is_backtest:
            # Get total trades count
            total_trades = (self.performance_tracker.performance_tracking['long']['wins'] +
                            self.performance_tracker.performance_tracking['long']['losses'] +
                            self.performance_tracker.performance_tracking['short']['wins'] +
                            self.performance_tracker.performance_tracking['short']['losses'])

            # Log stats every 100 trades
            if total_trades > 0 and total_trades % 100 == 0:
                self.performance_tracker.log_performance_stats()

        return proposed_stake

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """Calculate technical indicators using our indicator module"""
        return calculate_indicators(dataframe, self.strategy_config)

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """Define entry signals based on MACD crossovers and trend detection"""
        return populate_entry_signals(dataframe)

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """Required by FreqTrade API but we use custom_exit for exits"""
        dataframe['exit_long'] = 0
        dataframe['exit_short'] = 0
        dataframe['exit_tag'] = ''
        return dataframe

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str],
                 side: str, **kwargs) -> float:
        """Return fixed leverage for all trades"""
        return 10.0

    def _get_or_create_trade_cache(self, trade_id: str, pair: str, entry_rate: float,
                                   open_date: datetime, is_short: bool) -> dict:
        """
        Get trade info from cache or create if not exists

        Args:
            trade_id: Unique trade identifier
            pair: Trading pair
            entry_rate: Entry price
            open_date: Trade open datetime
            is_short: Whether this is a short trade

        Returns:
            dict: Trade cache entry
        """
        # If trade exists in cache, return it
        if trade_id in self.trade_cache['active_trades']:
            return self.trade_cache['active_trades'][trade_id]

        # Otherwise, create new cache entry
        direction = get_direction(is_short)

        # Update ROI cache if needed
        current_timestamp = int(open_date.timestamp())
        self.roi_calculator.update_roi_cache(current_timestamp)

        # Get ROI for this trade
        roi = self.roi_calculator.get_trade_roi(direction)

        # Calculate dynamic stoploss
        stoploss = self.stoploss_calculator.calculate_dynamic_stoploss(roi, direction)

        # Get regime info
        regime = self.regime_detector.detect_regime()
        is_counter_trend = self.regime_detector.is_counter_trend(direction)
        is_aligned_trend = self.regime_detector.is_aligned_trend(direction)

        # Calculate stoploss price
        stoploss_price = self.stoploss_calculator.calculate_stoploss_price(
            entry_rate, stoploss, is_short
        )

        # Create cache entry
        cache_entry = {
            'direction': direction,
            'entry_rate': entry_rate,
            'roi': roi,
            'stoploss': stoploss,
            'stoploss_price': stoploss_price,
            'is_counter_trend': is_counter_trend,
            'is_aligned_trend': is_aligned_trend,
            'regime': regime,
            'last_updated': current_timestamp
        }

        # Store in cache
        self.trade_cache['active_trades'][trade_id] = cache_entry

        # Log cache creation/recreation
        log_trade_cache_recreated(
            trade_id=trade_id,
            direction=direction,
            regime=regime,
            roi=roi,
            stoploss=stoploss
        )

        return cache_entry

    def _handle_missing_trade(self, trade: Trade, current_time: datetime) -> dict:
        """
        Handle case where a trade is not found in cache.
        This can happen after bot restarts or when handling existing trades.

        Args:
            trade: The trade object
            current_time: Current datetime

        Returns:
            dict: New cache entry
        """
        trade_id = create_trade_id(trade.pair, trade.open_date_utc)
        direction = get_direction(trade.is_short)

        logger.warning(
            f"Trade {trade_id} not found in cache, reconstructing parameters. "
            f"Pair: {trade.pair}, Direction: {direction}, "
            f"Open rate: {trade.open_rate}, Open date: {trade.open_date_utc}"
        )

        # Create new cache entry
        cache_entry = self._get_or_create_trade_cache(
            trade_id,
            trade.pair,
            trade.open_rate,
            trade.open_date_utc,
            trade.is_short
        )

        # Log additional information about the reconstructed trade
        logger.info(
            f"Reconstructed trade {trade_id}: "
            f"ROI: {cache_entry['roi']:.2%}, SL: {cache_entry['stoploss']:.2%}, "
            f"Regime: {cache_entry['regime']}, "
            f"{'Counter-trend' if cache_entry['is_counter_trend'] else 'Aligned' if cache_entry['is_aligned_trend'] else 'Neutral'}"
        )

        return cache_entry

    def bot_start(self) -> None:
        """
        Called at the start of the bot to handle any initialization tasks.
        We'll use this to recover any existing trades from FreqTrade's state.
        """
        # Check if we need to recover trades from FreqTrade state
        if not self.is_backtest:
            logger.info("Strategy starting - checking for existing trades to recover")
            if hasattr(self, 'dp') and hasattr(self.dp, 'get_trades_for_order'):
                # Get all currently open trades
                trades = Trade.get_trades_proxy(is_open=True)

                if trades:
                    logger.info(f"Found {len(trades)} open trades to recover")
                    current_time = datetime.now()

                    # Recover each trade's parameters
                    for trade in trades:
                        self._handle_missing_trade(trade, current_time)
                else:
                    logger.info("No open trades found to recover")