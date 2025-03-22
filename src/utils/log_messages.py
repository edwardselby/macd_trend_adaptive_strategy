"""
Logging utilities for MACD Trend Adaptive Strategy.
Provides consistent, single-line log message templates.
"""
import logging

logger = logging.getLogger(__name__)

# Trade Entry/Exit Messages
def log_new_trade(pair, direction, regime, roi, stoploss, is_counter_trend, is_aligned_trend, rate):
    """Log a new trade entry with formatted single-line output"""
    trend_type = "Counter-Trend" if is_counter_trend else "Aligned" if is_aligned_trend else "Neutral"
    logger.info(f"NEW TRADE | {pair} | {direction} | {regime} regime | ROI: {roi:.2%} | SL: {stoploss:.2%} | {trend_type} | Entry: {rate}")

def log_trade_exit(pair, direction, profit_ratio, exit_reason, regime, long_wr, short_wr):
    """Log a trade exit with formatted single-line output"""
    result = "WIN" if profit_ratio > 0 else "LOSS"
    logger.info(f"TRADE EXIT | {pair} | {direction} | {result} | Profit: {profit_ratio:.2%} | Reason: {exit_reason} | Regime: {regime} | Long WR: {long_wr:.2f} | Short WR: {short_wr:.2f}")

def log_stoploss_hit(pair, direction, current_price, stoploss_price, entry_price, profit_ratio, regime):
    """Log a stoploss hit with formatted single-line output"""
    logger.info(f"STOPLOSS HIT | {pair} | {direction} | Current: {current_price} | SL Price: {stoploss_price} | Entry: {entry_price} | Loss: {profit_ratio:.2%} | Regime: {regime}")

def log_roi_exit(pair, direction, trend_type, target_roi, actual_profit, regime):
    """Log an ROI target hit with formatted single-line output"""
    logger.info(f"ROI EXIT | {pair} | {direction} | {trend_type} | Target: {target_roi:.2%} | Actual: {actual_profit:.2%} | Regime: {regime}")

# Performance Tracking Messages
def log_performance_update(pair, direction, is_win, profit_ratio, total_wins, total_losses, win_rate, recent_win_rate):
    """Log a performance update with formatted single-line output"""
    result = "WIN" if is_win else "LOSS"
    logger.info(f"PERF UPDATE | {pair} | {direction} | {result} | Profit: {profit_ratio:.2%} | W/L: {total_wins}/{total_losses} | WR: {win_rate:.2f} | Recent WR: {recent_win_rate:.2f}")

def log_performance_summary(total_trades, long_wins, long_losses, long_wr, short_wins, short_losses, short_wr, long_profit, short_profit):
    """Log a performance summary with formatted single-line output"""
    logger.info(f"PERF SUMMARY | Trades: {total_trades} | Long: {long_wins}/{long_losses} ({long_wr:.2f}) | Short: {short_wins}/{short_losses} ({short_wr:.2f}) | Long Profit: {long_profit:.2%} | Short Profit: {short_profit:.2%}")

# Regime Detection Messages
def log_regime_detection(long_wr, short_wr, long_trades, short_trades, win_rate_diff, threshold, regime):
    """Log regime detection with formatted single-line output"""
    logger.debug(f"REGIME DETECT | Long WR: {long_wr:.2f} ({long_trades} trades) | Short WR: {short_wr:.2f} ({short_trades} trades) | Diff: {win_rate_diff:.2f} | Threshold: {threshold} | Regime: {regime}")

# Risk Management Messages
def log_roi_calculation(direction, base_roi, is_counter_trend, is_aligned_trend, factor, final_roi):
    """Log ROI calculation with formatted single-line output"""
    trend_type = "Counter-Trend" if is_counter_trend else "Aligned" if is_aligned_trend else "Neutral"
    logger.debug(f"ROI CALC | {direction} | Base: {base_roi:.2%} | {trend_type} | Factor: {factor:.2f} | Final: {final_roi:.2%}")

def log_stoploss_calculation(direction, roi, risk_ratio, base_sl, is_counter_trend, is_aligned_trend, factor, adjusted_sl, min_sl, max_sl, final_sl):
    """Log stoploss calculation with formatted single-line output"""
    trend_type = "Counter-Trend" if is_counter_trend else "Aligned" if is_aligned_trend else "Neutral"
    logger.debug(f"SL CALC | {direction} | ROI: {roi:.2%} | Risk-Ratio: {risk_ratio} | Base: {base_sl:.2%} | {trend_type} | Factor: {factor:.2f} | Adjusted: {adjusted_sl:.2%} | Bounds: [{min_sl:.2%}, {max_sl:.2%}] | Final: {final_sl:.2%}")

def log_stoploss_price(direction, entry_price, stoploss_pct, stoploss_price):
    """Log stoploss price calculation with formatted single-line output"""
    price_move = ((stoploss_price / entry_price) - 1) * 100
    logger.debug(f"SL PRICE | {direction} | Entry: {entry_price} | SL%: {stoploss_pct:.2%} | SL Price: {stoploss_price} | Move: {price_move:.2f}%")

# Trade Cache Messages
def log_trade_cache_recreated(trade_id, direction, regime, roi, stoploss):
    """Log when a trade is recreated in cache with formatted single-line output"""
    logger.info(f"TRADE CACHE | Recreated {trade_id} | {direction} | {regime} regime | ROI: {roi:.2%} | SL: {stoploss:.2%}")


# Configuration and Initialization Messages
def log_strategy_initialization(mode, timeframe, indicators, roi_config, stoploss_config):
    """Log strategy initialization parameters"""
    logger.info(
        f"STRATEGY INIT | Mode: {mode} | Timeframe: {timeframe} | "
        f"MACD: {indicators['fast']}/{indicators['slow']}/{indicators['signal']} | "
        f"ROI: {roi_config['min']:.2%}-{roi_config['max']:.2%} | "
        f"SL: {stoploss_config['min']:.2%}-{stoploss_config['max']:.2%}"
    )


def log_parameter_override(param, old_value, new_value):
    """Log when a parameter is overridden from external config"""
    logger.info(f"CONFIG OVERRIDE | {param} | {old_value} → {new_value}")


def log_backtest_run_start(pairs_count, timeframe, timerange):
    """Log the start of a backtest run"""
    logger.info(f"BACKTEST START | Pairs: {pairs_count} | Timeframe: {timeframe} | Range: {timerange}")


def log_hyperopt_run_start(spaces, epochs, timerange):
    """Log the start of a hyperopt run"""
    logger.info(f"HYPEROPT START | Spaces: {spaces} | Epochs: {epochs} | Range: {timerange}")


# Regime Detection Extensions
def log_regime_transition(old_regime, new_regime, long_wr, short_wr):
    """Log when market regime changes"""
    if old_regime != new_regime:
        logger.info(
            f"REGIME CHANGE | {old_regime} → {new_regime} | "
            f"Long WR: {long_wr:.2f} | Short WR: {short_wr:.2f}"
        )


# Trade Management Extensions
def log_trade_cache_miss(trade_id, pair, direction):
    """Log when a trade is not found in cache"""
    logger.warning(f"TRADE CACHE MISS | {trade_id} | {pair} | {direction}")


def log_stoploss_adjustment(pair, direction, initial_sl, final_sl, reason):
    """Log when stoploss is adjusted after trade open"""
    logger.info(
        f"SL ADJUST | {pair} | {direction} | "
        f"{initial_sl:.2%} → {final_sl:.2%} | Reason: {reason}"
    )


def log_roi_adjustment(pair, direction, initial_roi, final_roi, reason):
    """Log when ROI is adjusted after trade open"""
    logger.info(
        f"ROI ADJUST | {pair} | {direction} | "
        f"{initial_roi:.2%} → {final_roi:.2%} | Reason: {reason}"
    )


# Performance and Statistics
def log_win_rate_changes(direction, old_wr, new_wr, trades_count):
    """Log significant changes in win rate"""
    if abs(new_wr - old_wr) > 0.1:  # Only log significant changes
        logger.info(
            f"WIN RATE CHANGE | {direction} | "
            f"{old_wr:.2f} → {new_wr:.2f} | Trades: {trades_count}"
        )


def log_backtest_progress(completed_pairs, total_pairs, trades_count, win_rate, profit):
    """Log backtest progress for long-running tests"""
    percent_complete = (completed_pairs / total_pairs) * 100 if total_pairs > 0 else 0
    logger.info(
        f"BACKTEST PROGRESS | {percent_complete:.1f}% | "
        f"Pairs: {completed_pairs}/{total_pairs} | Trades: {trades_count} | "
        f"Win Rate: {win_rate:.2f} | Profit: {profit:.2%}"
    )


def log_memory_usage():
    """Log memory usage for long-running processes"""
    import os
    import psutil

    process = psutil.Process(os.getpid())
    memory_mb = process.memory_info().rss / 1024 / 1024
    logger.info(f"MEMORY USAGE | {memory_mb:.1f} MB")


# Trade Analysis Messages
def log_trade_analysis(pair, direction, profit, duration_min, entry_reason, exit_reason):
    """Log detailed trade analysis"""
    logger.info(
        f"TRADE ANALYSIS | {pair} | {direction} | Profit: {profit:.2%} | "
        f"Duration: {duration_min}m | Entry: {entry_reason} | Exit: {exit_reason}"
    )


def log_failed_signal(pair, timeframe, direction, reason):
    """Log when a signal is generated but filtered out"""
    logger.debug(
        f"SIGNAL FILTERED | {pair} | {timeframe} | {direction} | Reason: {reason}"
    )
