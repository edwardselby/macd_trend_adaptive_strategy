from tests.conftest import set_market_state, cleanup_patchers

import pytest


@pytest.mark.parametrize(
    "win_rate, regime, aligned_dir, test_dir, expected_min, expected_max", [
        # win_rate, regime, aligned_direction, direction_to_test, min_value, max_value
        (0.2, "neutral", None, "long", -0.011, -0.01),  # Min win rate, neutral regime
        (0.8, "neutral", None, "long", -0.051, -0.05),  # Max win rate, neutral regime
        (0.5, "neutral", None, "long", -0.031, -0.03),  # Mid win rate, neutral regime
        (0.5, "bullish", "long", "short", -0.016, -0.015),  # Counter trend (short in bullish)
        (0.5, "bullish", "long", "long", -0.046, -0.045),  # Aligned trend (long in bullish)
        (0.5, "bearish", "short", "long", -0.016, -0.015),  # Counter trend (long in bearish)
        (0.5, "bearish", "short", "short", -0.046, -0.045),  # Aligned trend (short in bearish)
    ]
)
def test_calculate_dynamic_stoploss(
        stoploss_calculator, regime_detector, win_rate, regime, aligned_dir, test_dir, expected_min, expected_max
):
    """Test that dynamic stoploss is calculated correctly based on market regime"""
    # Ensure dynamic stoploss is enabled
    stoploss_calculator.config.use_dynamic_stoploss = True

    # Set boundary parameters
    stoploss_calculator.config.min_stoploss = -0.01  # Closer to zero (tighter)
    stoploss_calculator.config.max_stoploss = -0.05  # Further from zero (wider)

    # Set min and max win rates for normalization
    stoploss_calculator.config.min_win_rate = 0.2
    stoploss_calculator.config.max_win_rate = 0.8

    # Configure trend alignment factors
    stoploss_calculator.config.counter_trend_stoploss_factor = 0.5  # Makes stoploss tighter
    stoploss_calculator.config.aligned_trend_stoploss_factor = 1.5  # Makes stoploss wider

    # Set up market state
    patchers = set_market_state(regime_detector, regime, aligned_dir)
    try:
        # Check if this direction is counter or aligned trend
        is_counter = regime_detector.is_counter_trend(test_dir)
        is_aligned = regime_detector.is_aligned_trend(test_dir)

        # Calculate stoploss
        result = stoploss_calculator.calculate_dynamic_stoploss(win_rate, is_counter, is_aligned)

        # Check if result is within expected range
        assert expected_min <= result <= expected_max, \
            f"With win_rate={win_rate}, regime={regime}, direction={test_dir}: " \
            f"expected range [{expected_min}, {expected_max}], got {result}"

        # Verify behavior based on trend alignment
        if is_counter:
            assert result > -0.03, f"Counter-trend stoploss ({result}) should be tighter (closer to zero)"
        elif is_aligned:
            assert result < -0.03, f"Aligned-trend stoploss ({result}) should be wider (further from zero)"

    finally:
        # Clean up patchers
        cleanup_patchers(patchers)


def test_calculate_stoploss_price(stoploss_calculator):
    """Test that stoploss price is calculated correctly"""
    entry_rate = 20000
    stoploss_percentage = -0.05  # 5% stoploss

    # Test actual implementation for long trade
    long_sl_price = stoploss_calculator.calculate_stoploss_price(entry_rate, stoploss_percentage, False)

    # For long trade: stoploss_price = entry_rate * (1 + stoploss_percentage)
    expected_long_sl_price = entry_rate * (1 + stoploss_percentage)
    assert abs(long_sl_price - expected_long_sl_price) < 0.01
    assert long_sl_price < entry_rate

    # Test actual implementation for short trade
    short_sl_price = stoploss_calculator.calculate_stoploss_price(entry_rate, stoploss_percentage, True)

    # For short trade: stoploss_price = entry_rate * (1 - stoploss_percentage)
    expected_short_sl_price = entry_rate * (1 - stoploss_percentage)
    assert abs(short_sl_price - expected_short_sl_price) < 0.01
    assert short_sl_price > entry_rate


def test_fallback_stoploss(stoploss_calculator):
    """Test fallback behavior when dynamic stoploss is disabled"""
    # Disable dynamic stoploss
    stoploss_calculator.config.use_dynamic_stoploss = False
    stoploss_calculator.config.static_stoploss = -0.06

    # Call the method with all three required arguments
    stoploss = stoploss_calculator.calculate_dynamic_stoploss(0.05, False, False)

    # Should return the static stoploss
    assert stoploss == stoploss_calculator.config.static_stoploss


def test_calculate_fallback_stoploss_price(stoploss_calculator):
    """Test the fallback stoploss price calculation with error handling"""
    # Test for long trade with normal input
    long_entry_rate = 20000
    stoploss_percentage = -0.05  # 5% stoploss
    long_sl_price = stoploss_calculator.calculate_fallback_stoploss_price(
        long_entry_rate, stoploss_percentage, False
    )

    # Should calculate normally in this case
    expected_long_sl_price = long_entry_rate * (1 + stoploss_percentage)
    assert abs(long_sl_price - expected_long_sl_price) < 0.01
    assert long_sl_price < long_entry_rate

    # Test error handling with invalid input
    # Should not raise an exception
    invalid_entry_rate = "invalid"
    try:
        result = stoploss_calculator.calculate_fallback_stoploss_price(
            invalid_entry_rate, stoploss_percentage, False
        )
        # Should return some fallback value, exact value depends on implementation
        assert isinstance(result, (int, float))
    except Exception as e:
        assert False, f"Should handle invalid input gracefully, but raised {e}"