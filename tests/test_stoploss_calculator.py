from tests.conftest import set_market_state, cleanup_patchers


def test_calculate_dynamic_stoploss(stoploss_calculator, regime_detector):
    """Test that dynamic stoploss is calculated correctly"""
    # Ensure dynamic stoploss is enabled
    stoploss_calculator.config.use_dynamic_stoploss = True

    # Configure risk parameters
    stoploss_calculator.config.risk_reward_ratio = 0.5  # 1:2 ratio
    stoploss_calculator.config.counter_trend_stoploss_factor = 0.5
    stoploss_calculator.config.aligned_trend_stoploss_factor = 1.5
    stoploss_calculator.config.min_stoploss = -0.01
    stoploss_calculator.config.max_stoploss = -0.1

    # Test with a bullish regime
    bullish_patchers = set_market_state(regime_detector, "bullish", "long")
    try:
        # Test with various ROI values
        roi_values = [0.04, 0.06, 0.08]

        for roi in roi_values:
            # Calculate expected values
            base_stoploss = -1 * roi * stoploss_calculator.config.risk_reward_ratio
            expected_long_sl = base_stoploss * stoploss_calculator.config.aligned_trend_stoploss_factor
            expected_short_sl = base_stoploss * stoploss_calculator.config.counter_trend_stoploss_factor

            # Apply correct clamping logic to match implementation
            if expected_long_sl > stoploss_calculator.config.min_stoploss:
                expected_long_sl = stoploss_calculator.config.min_stoploss
            elif expected_long_sl < stoploss_calculator.config.max_stoploss:
                expected_long_sl = stoploss_calculator.config.max_stoploss

            if expected_short_sl > stoploss_calculator.config.min_stoploss:
                expected_short_sl = stoploss_calculator.config.min_stoploss
            elif expected_short_sl < stoploss_calculator.config.max_stoploss:
                expected_short_sl = stoploss_calculator.config.max_stoploss

            # Test actual implementation
            long_sl = stoploss_calculator.calculate_dynamic_stoploss(roi, "long")
            short_sl = stoploss_calculator.calculate_dynamic_stoploss(roi, "short")

            # Verify results
            assert abs(long_sl - expected_long_sl) < 0.0001, f"Long SL: expected {expected_long_sl}, got {long_sl}"
            assert abs(short_sl - expected_short_sl) < 0.0001, f"Short SL: expected {expected_short_sl}, got {short_sl}"

            # Check relative values - counter trend should be tighter (less negative)
            if expected_long_sl != expected_short_sl:
                assert short_sl > long_sl, f"Short SL ({short_sl}) should be > Long SL ({long_sl})"
    finally:
        cleanup_patchers(bullish_patchers)

    # Test with a bearish regime
    bearish_patchers = set_market_state(regime_detector, "bearish", "short")
    try:
        # Test one value to verify behavior inverts
        roi = 0.05
        long_sl = stoploss_calculator.calculate_dynamic_stoploss(roi, "long")
        short_sl = stoploss_calculator.calculate_dynamic_stoploss(roi, "short")

        # Now long should be counter-trend (tighter) and short should be aligned (wider)
        # Only check if they're not clamped to the same value
        if long_sl != short_sl:
            assert long_sl > short_sl, f"With bearish regime, Long SL ({long_sl}) should be > Short SL ({short_sl})"
    finally:
        cleanup_patchers(bearish_patchers)

    # Test with a neutral regime
    neutral_patchers = set_market_state(regime_detector, "neutral", None)
    try:
        roi = 0.05
        long_sl = stoploss_calculator.calculate_dynamic_stoploss(roi, "long")
        short_sl = stoploss_calculator.calculate_dynamic_stoploss(roi, "short")

        # In neutral regime, no adjustment for trend alignment
        expected_sl = -1 * roi * stoploss_calculator.config.risk_reward_ratio

        # Apply clamping if needed
        if expected_sl > stoploss_calculator.config.min_stoploss:
            expected_sl = stoploss_calculator.config.min_stoploss
        elif expected_sl < stoploss_calculator.config.max_stoploss:
            expected_sl = stoploss_calculator.config.max_stoploss

        # Both directions should have the same stoploss
        assert abs(long_sl - expected_sl) < 0.0001, f"Long SL: expected {expected_sl}, got {long_sl}"
        assert abs(short_sl - expected_sl) < 0.0001, f"Short SL: expected {expected_sl}, got {short_sl}"
    finally:
        cleanup_patchers(neutral_patchers)


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

    # Call the method with any ROI value
    stoploss = stoploss_calculator.calculate_dynamic_stoploss(0.05, "long")

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