def test_calculate_dynamic_stoploss(stoploss_calculator, regime_detector):
    """Test that dynamic stoploss is calculated correctly"""
    # Test with various ROI values
    roi_values = [0.02, 0.05, 0.1]

    for roi in roi_values:
        # Force a bullish regime
        regime_detector.detect_regime = lambda: "bullish"

        # Get stoploss for aligned trend (long in bullish)
        long_sl = stoploss_calculator.calculate_dynamic_stoploss(roi, "long")

        # Get stoploss for counter trend (short in bullish)
        short_sl = stoploss_calculator.calculate_dynamic_stoploss(roi, "short")

        # Stoploss should be negative
        assert long_sl < 0
        assert short_sl < 0

        # Counter trend stoploss should be tighter (less negative)
        assert short_sl > long_sl

        # Check that stoploss is within bounds
        assert long_sl >= stoploss_calculator.config.min_stoploss
        assert long_sl <= stoploss_calculator.config.max_stoploss
        assert short_sl >= stoploss_calculator.config.min_stoploss
        assert short_sl <= stoploss_calculator.config.max_stoploss

        # Verify stoploss calculation
        base_stoploss = -1 * roi * stoploss_calculator.config.risk_reward_ratio

        # Long in bullish = aligned trend factor
        expected_long_sl = base_stoploss * stoploss_calculator.config.aligned_trend_stoploss_factor
        # Clamp to bounds
        expected_long_sl = max(
            stoploss_calculator.config.min_stoploss,
            min(expected_long_sl, stoploss_calculator.config.max_stoploss)
        )

        # Short in bullish = counter trend factor
        expected_short_sl = base_stoploss * stoploss_calculator.config.counter_trend_stoploss_factor
        # Clamp to bounds
        expected_short_sl = max(
            stoploss_calculator.config.min_stoploss,
            min(expected_short_sl, stoploss_calculator.config.max_stoploss)
        )

        assert abs(long_sl - expected_long_sl) < 0.0001
        assert abs(short_sl - expected_short_sl) < 0.0001


def test_calculate_stoploss_price(stoploss_calculator):
    """Test that stoploss price is calculated correctly"""
    entry_rate = 20000
    stoploss_percentage = -0.05  # 5% stoploss

    # For a long trade
    long_sl_price = stoploss_calculator.calculate_stoploss_price(entry_rate, stoploss_percentage, False)
    # Expected price: 20000 * (1 - 0.05) = 19000
    assert long_sl_price == entry_rate * (1 + stoploss_percentage)
    assert long_sl_price < entry_rate

    # For a short trade
    short_sl_price = stoploss_calculator.calculate_stoploss_price(entry_rate, stoploss_percentage, True)
    # Expected price: 20000 * (1 + 0.05) = 21000
    assert short_sl_price == entry_rate * (1 - stoploss_percentage)
    assert short_sl_price > entry_rate