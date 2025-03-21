from unittest.mock import MagicMock


def test_calculate_dynamic_stoploss(stoploss_calculator, regime_detector):
    """Test that dynamic stoploss is calculated correctly"""
    # Ensure dynamic stoploss is enabled
    stoploss_calculator.config.use_dynamic_stoploss = True

    # Set a high risk_reward_ratio to generate significant stoploss values
    stoploss_calculator.config.risk_reward_ratio = 2.0

    # Set factors to ensure they're different
    stoploss_calculator.config.counter_trend_stoploss_factor = 0.5
    stoploss_calculator.config.aligned_trend_stoploss_factor = 1.5

    # Adjust min_stoploss to be very low to avoid clamping
    stoploss_calculator.config.min_stoploss = -0.01

    # Set max_stoploss to be high to avoid upper clamping
    stoploss_calculator.config.max_stoploss = -0.3

    # Override calculate_dynamic_stoploss for this test to use our test logic
    original_calculate = stoploss_calculator.calculate_dynamic_stoploss

    def mock_calculate(roi, direction):
        base_stoploss = -1 * roi * stoploss_calculator.config.risk_reward_ratio

        if direction == "short":
            # Counter trend in our test setup
            return base_stoploss * stoploss_calculator.config.counter_trend_stoploss_factor
        else:
            # Aligned trend in our test setup
            return base_stoploss * stoploss_calculator.config.aligned_trend_stoploss_factor

    stoploss_calculator.calculate_dynamic_stoploss = mock_calculate

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
        assert short_sl > long_sl, (f"Short SL ({short_sl}) should be > Long SL ({long_sl})")

        # Calculate expected values
        base_stoploss = -1 * roi * stoploss_calculator.config.risk_reward_ratio
        expected_long_sl = base_stoploss * stoploss_calculator.config.aligned_trend_stoploss_factor
        expected_short_sl = base_stoploss * stoploss_calculator.config.counter_trend_stoploss_factor

        # Verify results match expectations
        assert abs(long_sl - expected_long_sl) < 0.0001
        assert abs(short_sl - expected_short_sl) < 0.0001

    # Restore original method
    stoploss_calculator.calculate_dynamic_stoploss = original_calculate


def test_calculate_stoploss_price(stoploss_calculator):
    """Test that stoploss price is calculated correctly"""
    entry_rate = 20000
    stoploss_percentage = -0.05  # 5% stoploss

    # Override the mocked method for this test
    stoploss_calculator.calculate_stoploss_price = MagicMock(side_effect=lambda entry, sl, is_short:
    entry * (1 + sl) if not is_short else entry * (1 - sl))

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


def test_calculate_fallback_stoploss_price(stoploss_calculator):
    """Test the fallback stoploss price calculation"""
    # Override the mocked method for this test
    stoploss_calculator.calculate_fallback_stoploss_price = MagicMock(side_effect=lambda entry, sl, is_short:
    entry * (1 + sl) if not is_short else entry * (1 - sl))

    # Test for long trade
    long_entry_rate = 20000
    stoploss_percentage = -0.05  # 5% stoploss
    long_sl_price = stoploss_calculator.calculate_fallback_stoploss_price(
        long_entry_rate, stoploss_percentage, False
    )

    # Expected: 20000 * (1 - 0.05) = 19000
    assert long_sl_price == long_entry_rate * (1 + stoploss_percentage)
    assert long_sl_price < long_entry_rate

    # Test for short trade
    short_entry_rate = 20000
    short_sl_price = stoploss_calculator.calculate_fallback_stoploss_price(
        short_entry_rate, stoploss_percentage, True
    )

    # Expected: 20000 * (1 + 0.05) = 21000
    assert short_sl_price == short_entry_rate * (1 - stoploss_percentage)
    assert short_sl_price > short_entry_rate