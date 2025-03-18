import pytest
from datetime import datetime
from unittest.mock import MagicMock

from macd_trend_adaptive_strategy.utils.helpers import create_trade_id


@pytest.mark.skip(reason="debugging test ignored")
def test_freqtrade_stoploss_override_diagnostic(strategy):
    """
    Diagnostic test specifically designed to detect if FreqTrade is overriding
    the strategy's dynamic stoploss for short trades.

    This test directly mirrors behavior from the logs showing shorts exiting at -3%.
    """
    # Setup test parameters to match the observed behavior in logs
    pair = "BTC/USDT"
    entry_rate = 92000  # Similar to values in logs
    current_time = datetime.now()

    # Create a mock trade (simpler than using actual Trade class)
    mock_short_trade = MagicMock()
    mock_short_trade.pair = pair
    mock_short_trade.open_rate = entry_rate
    mock_short_trade.open_date_utc = current_time
    mock_short_trade.is_short = True

    # Override calc_profit_ratio to behave like FreqTrade
    def short_profit(rate):
        return (entry_rate - rate) / entry_rate

    mock_short_trade.calc_profit_ratio = short_profit

    # Initialize the trade in the strategy
    strategy.confirm_trade_entry(
        pair, "limit", 0.01, entry_rate, "GTC",
        current_time, "macd_downtrend_short", "sell"
    )

    # Get trade ID and cached values
    trade_id = create_trade_id(pair, current_time)
    assert trade_id in strategy.trade_cache['active_trades'], "Trade not in cache"

    trade_cache = strategy.trade_cache['active_trades'][trade_id]
    cached_stoploss = trade_cache['stoploss']
    stoploss_price = trade_cache['stoploss_price']

    # Print diagnostic info
    print(f"\nDiagnostic Information:")
    print(f"- Strategy default stoploss: {strategy.stoploss}")
    print(f"- Strategy config static stoploss: {strategy.strategy_config.static_stoploss}")
    print(f"- Strategy min stoploss: {strategy.strategy_config.min_stoploss}")
    print(f"- Calculated stoploss for this trade: {cached_stoploss:.4f}")
    print(f"- Stoploss price: {stoploss_price:.2f} (Entry: {entry_rate:.2f})")

    # If -1% stoploss is what we expect (based on logs)
    if abs(cached_stoploss - (-0.01)) < 0.001:
        print(f"✓ Correct: Calculated stoploss is -1% as expected")
    else:
        print(f"✗ Problem: Calculated stoploss is {cached_stoploss:.4f}, not -1% as expected")

    # Calculate what the stoploss price should be at -1% and -3%
    expected_sl_price_at_1_percent = entry_rate * 1.01
    expected_sl_price_at_3_percent = entry_rate * 1.03

    print(f"- Expected -1% SL price: {expected_sl_price_at_1_percent:.2f}")
    print(f"- Expected -3% SL price: {expected_sl_price_at_3_percent:.2f}")
    print(f"- Actual SL price in cache: {stoploss_price:.2f}")

    # Test what happens at -1% loss (our expected stoploss)
    price_at_1_percent_loss = expected_sl_price_at_1_percent
    exit_at_1_percent = strategy.should_exit(
        mock_short_trade, price_at_1_percent_loss, current_time
    )

    print(f"\nBehavior at -1% loss (price: {price_at_1_percent_loss:.2f}):")
    if len(exit_at_1_percent) > 0:
        print(f"✓ Correct: Strategy triggers stoploss at -1% as expected")
    else:
        print(f"✗ Problem: Strategy does NOT trigger stoploss at -1%")

    # Test what happens at -3% loss (the observed behavior in logs)
    price_at_3_percent_loss = expected_sl_price_at_3_percent
    exit_at_3_percent = strategy.should_exit(
        mock_short_trade, price_at_3_percent_loss, current_time
    )

    print(f"\nBehavior at -3% loss (price: {price_at_3_percent_loss:.2f}):")
    print(f"- Should exit based on our -1% stoploss: {'No' if cached_stoploss > -0.03 else 'Yes'}")
    print(f"- Does exit in practice: {'Yes' if len(exit_at_3_percent) > 0 else 'No'}")

    if cached_stoploss > -0.03 and len(exit_at_3_percent) > 0:
        print(
            f"✗ ISSUE DETECTED: Strategy triggers stoploss at -3% even though stoploss is set to {cached_stoploss:.4f}")
        print(f"  This matches the behavior seen in the logs and indicates FreqTrade is overriding the stoploss")

    # Also check the custom_stoploss method
    custom_sl = strategy.custom_stoploss(
        pair, mock_short_trade, current_time, price_at_1_percent_loss, -0.01
    )

    print(f"\nCustom stoploss behavior:")
    print(f"- custom_stoploss returns: {custom_sl:.4f}")
    print(f"- cached stoploss value: {cached_stoploss:.4f}")

    if abs(custom_sl - cached_stoploss) < 0.0001:
        print(f"✓ Correct: custom_stoploss returns the expected cached value")
    else:
        print(f"✗ Problem: custom_stoploss returns {custom_sl:.4f} but cache has {cached_stoploss:.4f}")

    # The test passes if the behavior matches our expectations - that FreqTrade may be overriding our stoploss
    # This is diagnostic, so we don't necessarily assert anything - we're just gathering information
    # But we could add assertions based on what we find