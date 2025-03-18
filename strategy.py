import logging
from datetime import datetime
from typing import List, Optional

import pandas as pd
from freqtrade.enums.exittype import ExitType
from freqtrade.persistence import Trade
from freqtrade.strategy.interface import IStrategy, ExitCheckTuple

from macd_trend_adaptive_strategy.config.mode_enum import StrategyMode
from macd_trend_adaptive_strategy.config.strategy_config import StrategyConfig
from macd_trend_adaptive_strategy.indicators.technical import calculate_indicators, populate_entry_signals
from macd_trend_adaptive_strategy.performance.db_handler import DBHandler
from macd_trend_adaptive_strategy.performance.tracker import PerformanceTracker
from macd_trend_adaptive_strategy.regime.detector import RegimeDetector
from macd_trend_adaptive_strategy.risk_management.roi_calculator import ROICalculator
from macd_trend_adaptive_strategy.risk_management.stoploss_calculator import StoplossCalculator
from macd_trend_adaptive_strategy.utils import log_messages
from macd_trend_adaptive_strategy.utils.helpers import create_trade_id, get_direction

# Set up strategy-wide logging
logger = logging.getLogger(__name__)

# For detailed debug messages (only when needed)
# logger.setLevel(logging.DEBUG)

logger.setLevel(logging.INFO)


class MACDTrendAdaptiveStrategy(IStrategy):
    """
    Enhanced MACD Strategy with Trend Detection, Market Regime Detection,
    Fully Adaptive ROI and Dynamic Stoploss

    Core strategy logic:
    - Uses MACD crossovers filtered by trend indicators for entry signals
    - Implements dynamic regime detection based on recent trade performance
    - Applies fully adaptive take-profit levels based on win rate performance
    - Dynamic stoploss calculation based on ROI and configurable risk-reward ratio
    - Adjusts both ROI and stoploss based on whether trades align with or counter the trend

    Available modes:
    - default: Balanced configuration with moderate risk/reward
    - 1m: Optimized for 1-minute timeframe with faster signals and tighter risk controls
    - 5m: Optimized for 5-minute timeframe
    - 30m: Optimized for 30-minute timeframe
    - 1h: Optimized for 1-hour timeframe with more conservative parameters
    """

    # Version 3 API - required for proper leverage
    INTERFACE_VERSION = 3

    # ===== CONFIGURABLE PARAMETER SET =====
    # Change this to select a different parameter set
    STRATEGY_MODE = StrategyMode.TIMEFRAME_1M
    # =====================================

    # Strategy Parameters - Setting minimal_roi to empty dict to ensure we only use custom_exit logic
    minimal_roi = {}  # Disable standard ROI table - we'll use custom_exit exclusively

    # Set the timeframe for this strategy
    timeframe = '1m'

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
    use_custom_stoploss = True  # Enable custom stoploss mechanism
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

        # Initialize strategy configuration with selected mode
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
        self.is_backtest = config.get('runmode') in ('backtest', 'hyperopt')

        # Clear performance data at the start of each backtest
        if self.is_backtest:
            self.db_handler.clear_performance_data()

        # Initialize performance tracker
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

        logger.info(f"Strategy initialized with mode: {self.STRATEGY_MODE}")

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: Optional[str],
                            side: str, **kwargs) -> bool:
        """
        Called right before placing a buy order.
        This is where we register a new trade in our tracking system and calculate
        its initial dynamic stoploss.
        """
        trade_id = create_trade_id(pair, current_time)
        direction = get_direction(side == 'sell')

        # Get current regime
        regime = self.regime_detector.detect_regime()

        # Determine if this trade is counter-trend or aligned with trend
        is_counter_trend = self.regime_detector.is_counter_trend(direction)
        is_aligned_trend = self.regime_detector.is_aligned_trend(direction)

        # Calculate dynamic ROI for this trade
        roi = self.roi_calculator.get_trade_roi(direction)

        # Calculate dynamic stoploss for this trade
        stoploss = self.stoploss_calculator.calculate_dynamic_stoploss(roi, direction)

        # Calculate stoploss price
        stoploss_price = self.stoploss_calculator.calculate_stoploss_price(
            rate, stoploss, side == 'sell'
        )

        # Create cache entry
        cache_entry = {
            'direction': direction,
            'entry_rate': rate,
            'roi': roi,
            'stoploss': stoploss,
            'stoploss_price': stoploss_price,
            'is_counter_trend': is_counter_trend,
            'is_aligned_trend': is_aligned_trend,
            'regime': regime,
            'last_updated': int(current_time.timestamp())
        }

        # Store trade info in our cache
        self.trade_cache['active_trades'][trade_id] = cache_entry

        # Replace the existing log message with:
        log_messages.log_new_trade(
            pair=pair,
            direction=direction,
            regime=regime,
            roi=roi,
            stoploss=stoploss,
            is_counter_trend=is_counter_trend,
            is_aligned_trend=is_aligned_trend,
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

        log_messages.log_trade_exit(
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
        Override should_exit to use our adaptive ROI and stoploss logic
        for every trade check
        """
        # Get current profit
        current_profit = trade.calc_profit_ratio(rate)

        # Get trade details from cache if possible
        trade_id = create_trade_id(trade.pair, trade.open_date_utc)

        # If we don't have this trade in our cache, we need to recreate its parameters
        if trade_id not in self.trade_cache['active_trades']:
            # Get trade direction
            direction = get_direction(trade.is_short)

            # Update ROI cache if needed
            current_timestamp = int(date.timestamp())
            self.roi_calculator.update_roi_cache(current_timestamp)

            # Get ROI for this trade
            roi = self.roi_calculator.get_trade_roi(direction)

            # Calculate dynamic stoploss
            stoploss = self.stoploss_calculator.calculate_dynamic_stoploss(roi, direction)

            # Calculate stoploss price
            stoploss_price = self.stoploss_calculator.calculate_stoploss_price(
                trade.open_rate, stoploss, trade.is_short
            )

            # Get regime info
            regime = self.regime_detector.detect_regime()
            is_counter_trend = self.regime_detector.is_counter_trend(direction)
            is_aligned_trend = self.regime_detector.is_aligned_trend(direction)

            # Add trade to cache
            self.trade_cache['active_trades'][trade_id] = {
                'direction': direction,
                'entry_rate': trade.open_rate,
                'roi': roi,
                'stoploss': stoploss,
                'stoploss_price': stoploss_price,
                'is_counter_trend': is_counter_trend,
                'is_aligned_trend': is_aligned_trend,
                'regime': regime,
                'last_updated': current_timestamp
            }

            log_messages.log_trade_cache_recreated(
                trade_id=trade_id,
                direction=direction,
                regime=regime,
                roi=roi,
                stoploss=stoploss
            )

        # Get trade parameters from cache
        trade_params = self.trade_cache['active_trades'][trade_id]

        # First check stoploss
        if trade.is_short:
            # For shorts, price increasing (rate > stoploss_price) triggers stoploss
            if rate >= trade_params['stoploss_price']:
                log_messages.log_stoploss_hit(
                    pair=trade.pair,
                    direction=trade_params['direction'],
                    current_price=rate,
                    stoploss_price=trade_params['stoploss_price'],
                    entry_price=trade_params['entry_rate'],
                    profit_ratio=current_profit,
                    regime=trade_params['regime']
                )
                return [ExitCheckTuple(exit_type=ExitType.STOP_LOSS, exit_reason="dynamic_stoploss")]
        else:
            # For longs, price decreasing (rate < stoploss_price) triggers stoploss
            if rate <= trade_params['stoploss_price']:
                log_messages.log_stoploss_hit(
                    pair=trade.pair,
                    direction=trade_params['direction'],
                    current_price=rate,
                    stoploss_price=trade_params['stoploss_price'],
                    entry_price=trade_params['entry_rate'],
                    profit_ratio=current_profit,
                    regime=trade_params['regime']
                )
                return [ExitCheckTuple(exit_type=ExitType.STOP_LOSS, exit_reason="dynamic_stoploss")]

        # Check for ROI exit
        if current_profit >= trade_params['roi']:
            trade_type = ("countertrend" if trade_params['is_counter_trend']
                          else "aligned" if trade_params['is_aligned_trend']
            else "neutral")

            log_messages.log_roi_exit(
                pair=trade.pair,
                direction=trade_params['direction'],
                trend_type=trade_type,
                target_roi=trade_params['roi'],
                actual_profit=current_profit,
                regime=trade_params['regime']
            )

            return [ExitCheckTuple(exit_type=ExitType.ROI,
                                   exit_reason=f"adaptive_roi_{trade_type}_{trade_params['regime']}")]

        # Apply default ROI if enabled
        if (self.strategy_config.use_default_roi_exit and
                current_profit >= self.strategy_config.default_roi):
            logger.info(f"Default ROI exit - Profit: {current_profit:.2%}")
            return [ExitCheckTuple(exit_type=ExitType.ROI, exit_reason="default_roi")]

        # Otherwise, continue holding
        return []

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime, current_rate: float,
                        current_profit: float, **kwargs) -> float:
        """
        Custom stoploss logic, returning the new stoploss percentage.

        This is required by FreqTrade's API but we actually handle the stoploss logic
        in should_exit for more control.
        """
        # Get trade ID
        trade_id = create_trade_id(pair, trade.open_date_utc)

        # If we don't have this trade in our cache, return the default stoploss
        if trade_id not in self.trade_cache['active_trades']:
            return self.stoploss

        # Otherwise return the cached stoploss value
        return self.trade_cache['active_trades'][trade_id]['stoploss']

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