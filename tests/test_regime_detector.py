def test_detect_regime(regime_detector, performance_tracker):
    """Test that market regime is correctly detected"""
    # With the mock data provided, we should detect a bullish regime
    # Because long win rate (10/15 = 0.67) - short win rate (8/15 = 0.53) > threshold
    regime = regime_detector.detect_regime()
    assert regime in ["bullish", "bearish", "neutral"]

    # We expect bullish with our mock data
    assert regime == "bullish"

    # Test with not enough trades
    # Modify the tracker to simulate not enough trades
    original_last_trades = performance_tracker.performance_tracking['long']['last_trades'].copy()
    performance_tracker.performance_tracking['long']['last_trades'] = []

    # Should return neutral when not enough trades
    assert regime_detector.detect_regime() == "neutral"

    # Restore original data
    performance_tracker.performance_tracking['long']['last_trades'] = original_last_trades


def test_trend_alignment(regime_detector):
    """Test the trend alignment detection methods"""
    # Force a specific regime for testing
    regime_detector.detect_regime = lambda: "bullish"

    # Test counter trend
    assert regime_detector.is_counter_trend("short") == True
    assert regime_detector.is_counter_trend("long") == False

    # Test aligned trend
    assert regime_detector.is_aligned_trend("long") == True
    assert regime_detector.is_aligned_trend("short") == False

    # Change the regime
    regime_detector.detect_regime = lambda: "bearish"

    # Test counter trend with bearish regime
    assert regime_detector.is_counter_trend("long") == True
    assert regime_detector.is_counter_trend("short") == False

    # Test aligned trend with bearish regime
    assert regime_detector.is_aligned_trend("short") == True
    assert regime_detector.is_aligned_trend("long") == False