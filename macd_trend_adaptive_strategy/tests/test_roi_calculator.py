from datetime import datetime


def test_calculate_adaptive_roi(roi_calculator):
    """Test that adaptive ROI is calculated correctly"""
    # Use the same win rate for both directions to isolate the boost effect
    roi_calculator.performance_tracker.get_recent_win_rate = lambda direction: 0.6

    # Set min/max win rates to make normalization predictable
    roi_calculator.config.min_win_rate = 0.4
    roi_calculator.config.max_win_rate = 0.8

    # Set min/max ROI values
    roi_calculator.config.min_roi = 0.05
    roi_calculator.config.max_roi = 0.10

    # Set a specific boost value
    roi_calculator.config.long_roi_boost = 0.02

    # Test ROI calculation for long
    long_roi = roi_calculator._calculate_adaptive_roi("long")

    # Test ROI calculation for short
    short_roi = roi_calculator._calculate_adaptive_roi("short")

    # With the same win rate, the only difference should be the boost
    assert short_roi >= roi_calculator.config.min_roi
    assert long_roi > short_roi

    # Long ROI should be exactly the boost amount higher than short ROI
    assert abs((long_roi - short_roi) - roi_calculator.config.long_roi_boost) < 0.001


def test_get_trade_roi(roi_calculator, regime_detector):
    """Test that trade-specific ROI considers trend alignment"""
    # Force a bullish regime
    regime_detector.detect_regime = lambda: "bullish"

    # Update the cache
    roi_calculator.update_roi_cache(int(datetime.now().timestamp()))

    # Get ROI for aligned trend (long in bullish)
    long_roi = roi_calculator.get_trade_roi("long")

    # Get ROI for counter trend (short in bullish)
    short_roi = roi_calculator.get_trade_roi("short")

    # Counter trend ROI should be lower to take profits quicker
    assert short_roi < long_roi

    # Check that the factors are correctly applied
    base_long_roi = roi_calculator.roi_cache["long"]
    base_short_roi = roi_calculator.roi_cache["short"]

    # Long in bullish = aligned trend factor
    expected_long_roi = base_long_roi * roi_calculator.config.aligned_trend_factor
    # Short in bullish = counter trend factor
    expected_short_roi = base_short_roi * roi_calculator.config.counter_trend_factor

    assert abs(long_roi - expected_long_roi) < 0.0001
    assert abs(short_roi - expected_short_roi) < 0.0001