from datetime import datetime
from unittest.mock import patch

from macd_trend_adaptive_strategy.tests.conftest import cleanup_patchers, set_market_state


def test_calculate_adaptive_roi(roi_calculator, performance_tracker):
    """Test that adaptive ROI is calculated based on win rates"""
    # Configure win rate boundaries
    roi_calculator.config.min_win_rate = 0.2
    roi_calculator.config.max_win_rate = 0.8

    # Configure ROI boundaries
    roi_calculator.config.min_roi = 0.03
    roi_calculator.config.max_roi = 0.09

    # Test cases with different win rates
    test_cases = [
        {"win_rate": 0.2, "expected_roi": 0.03},  # Minimum win rate -> minimum ROI
        {"win_rate": 0.8, "expected_roi": 0.09},  # Maximum win rate -> maximum ROI
        {"win_rate": 0.5, "expected_roi": 0.06},  # Middle win rate -> middle ROI (linear scaling)
        {"win_rate": 0.1, "expected_roi": 0.03},  # Below min win rate -> clamped to min ROI
        {"win_rate": 0.9, "expected_roi": 0.09},  # Above max win rate -> clamped to max ROI
    ]

    for case in test_cases:
        # Patch performance_tracker.get_recent_win_rate to return our test win rate
        with patch.object(performance_tracker, 'get_recent_win_rate', return_value=case["win_rate"]):
            # Call the actual implementation we're testing
            result = roi_calculator._calculate_adaptive_roi("long")  # Direction doesn't matter for this test

            # Verify result (with small tolerance for floating point)
            assert abs(result - case["expected_roi"]) < 0.0001, \
                f"With win rate {case['win_rate']}, expected ROI {case['expected_roi']}, got {result}"


def test_get_trade_roi(roi_calculator, regime_detector):
    """Test that trade-specific ROI applies correct factors based on regime"""
    # Configure the ROI cache
    roi_calculator.roi_cache = {
        'long': 0.05,  # Base ROI for long
        'short': 0.04,  # Base ROI for short
        'last_updated': int(datetime.now().timestamp())
    }

    # Configure factors
    roi_calculator.config.counter_trend_factor = 0.5
    roi_calculator.config.aligned_trend_factor = 1.5

    # Test with bullish regime
    bullish_patchers = set_market_state(regime_detector, "bullish", "long")
    try:
        # Call the actual implementation
        long_roi = roi_calculator.get_trade_roi("long")
        short_roi = roi_calculator.get_trade_roi("short")

        # Check expected results
        # Long is aligned: 0.05 * 1.5 = 0.075
        expected_long_roi = 0.05 * 1.5
        # Short is counter: 0.04 * 0.5 = 0.02
        expected_short_roi = 0.04 * 0.5

        assert abs(long_roi - expected_long_roi) < 0.0001, \
            f"Expected aligned long ROI {expected_long_roi}, got {long_roi}"
        assert abs(short_roi - expected_short_roi) < 0.0001, \
            f"Expected counter short ROI {expected_short_roi}, got {short_roi}"
    finally:
        cleanup_patchers(bullish_patchers)

    # Test with bearish regime
    bearish_patchers = set_market_state(regime_detector, "bearish", "short")
    try:
        # Call the actual implementation again
        long_roi = roi_calculator.get_trade_roi("long")
        short_roi = roi_calculator.get_trade_roi("short")

        # Check expected results are inverted
        # Long is now counter: 0.05 * 0.5 = 0.025
        expected_long_roi = 0.05 * 0.5
        # Short is now aligned: 0.04 * 1.5 = 0.06
        expected_short_roi = 0.04 * 1.5

        assert abs(long_roi - expected_long_roi) < 0.0001, \
            f"Expected counter long ROI {expected_long_roi}, got {long_roi}"
        assert abs(short_roi - expected_short_roi) < 0.0001, \
            f"Expected aligned short ROI {expected_short_roi}, got {short_roi}"
    finally:
        cleanup_patchers(bearish_patchers)

    # Test with neutral regime
    neutral_patchers = set_market_state(regime_detector, "neutral", None)
    try:
        # Call the actual implementation
        long_roi = roi_calculator.get_trade_roi("long")
        short_roi = roi_calculator.get_trade_roi("short")

        # In neutral regime, no factors are applied
        expected_long_roi = 0.05  # Base ROI
        expected_short_roi = 0.04  # Base ROI

        assert abs(long_roi - expected_long_roi) < 0.0001, \
            f"Expected neutral long ROI {expected_long_roi}, got {long_roi}"
        assert abs(short_roi - expected_short_roi) < 0.0001, \
            f"Expected neutral short ROI {expected_short_roi}, got {short_roi}"
    finally:
        cleanup_patchers(neutral_patchers)


def test_update_roi_cache(roi_calculator, performance_tracker):
    """Test that ROI cache is updated when needed"""
    # Set up initial state
    old_timestamp = 100  # Very old timestamp
    roi_calculator.roi_cache = {
        'long': 0.03,
        'short': 0.03,
        'last_updated': old_timestamp
    }
    roi_calculator.config.roi_cache_update_interval = 50  # Short interval for testing

    # Mock _calculate_adaptive_roi to return controlled values
    with patch.object(roi_calculator, '_calculate_adaptive_roi',
                      side_effect=lambda direction: 0.045 if direction == "long" else 0.035):
        # Current timestamp that will trigger an update (more than 50 seconds passed)
        current_timestamp = old_timestamp + 60

        # Call the method to update the cache
        roi_calculator.update_roi_cache(current_timestamp)

        # Verify cache was updated
        assert roi_calculator.roi_cache['last_updated'] == current_timestamp, \
            "Cache timestamp should be updated"
        assert roi_calculator.roi_cache['long'] == 0.045, \
            f"Long ROI should be updated to 0.045, got {roi_calculator.roi_cache['long']}"
        assert roi_calculator.roi_cache['short'] == 0.035, \
            f"Short ROI should be updated to 0.035, got {roi_calculator.roi_cache['short']}"

        # Now test when update is not needed
        previous_cache = roi_calculator.roi_cache.copy()  # Save current state
        new_timestamp = current_timestamp + 10  # Not enough time passed

        # Call update again
        roi_calculator.update_roi_cache(new_timestamp)

        # Verify cache was NOT updated
        assert roi_calculator.roi_cache['last_updated'] == current_timestamp, \
            "Cache timestamp should not change"
        assert roi_calculator.roi_cache['long'] == previous_cache['long'], \
            "Long ROI should not change"
        assert roi_calculator.roi_cache['short'] == previous_cache['short'], \
            "Short ROI should not change"