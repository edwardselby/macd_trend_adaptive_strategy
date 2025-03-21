from unittest.mock import patch


def test_detect_regime(regime_detector, performance_tracker):
    """Test that market regime is correctly detected based on win rates"""
    # Configure threshold
    regime_detector.config.regime_win_rate_diff = 0.2
    regime_detector.config.min_recent_trades_per_direction = 4

    # Patch the methods in performance_tracker that get called by detect_regime
    # This avoids testing the mock but instead tests how detect_regime uses these methods

    # Scenario 1: Bullish regime (long win rate significantly higher)
    with patch.object(performance_tracker, 'get_recent_win_rate',
                      side_effect=lambda direction: 0.75 if direction == "long" else 0.45):
        with patch.object(performance_tracker, 'get_recent_trades_count', return_value=10):
            # Call the actual implementation
            regime = regime_detector.detect_regime()

            # Long win rate - short win rate = 0.3, which > 0.2 threshold
            assert regime == "bullish", f"Expected bullish regime, got {regime}"

    # Scenario 2: Bearish regime (short win rate significantly higher)
    with patch.object(performance_tracker, 'get_recent_win_rate',
                      side_effect=lambda direction: 0.4 if direction == "long" else 0.7):
        with patch.object(performance_tracker, 'get_recent_trades_count', return_value=10):
            # Call the actual implementation
            regime = regime_detector.detect_regime()

            # Short win rate - long win rate = 0.3, which > 0.2 threshold
            assert regime == "bearish", f"Expected bearish regime, got {regime}"

    # Scenario 3: Neutral regime (win rates are close)
    with patch.object(performance_tracker, 'get_recent_win_rate',
                      side_effect=lambda direction: 0.55 if direction == "long" else 0.45):
        with patch.object(performance_tracker, 'get_recent_trades_count', return_value=10):
            # Call the actual implementation
            regime = regime_detector.detect_regime()

            # Difference = 0.1, which < 0.2 threshold
            assert regime == "neutral", f"Expected neutral regime, got {regime}"

    # Scenario 4: Not enough trades
    with patch.object(performance_tracker, 'get_recent_win_rate',
                      side_effect=lambda direction: 0.75 if direction == "long" else 0.45):
        with patch.object(performance_tracker, 'get_recent_trades_count', return_value=2):
            # Call the actual implementation
            regime = regime_detector.detect_regime()

            # Should default to neutral when not enough trades
            assert regime == "neutral", f"Expected neutral regime when not enough trades, got {regime}"


def test_is_counter_trend(regime_detector):
    """Test counter-trend detection logic"""
    # Patch the detect_regime method to return controlled values
    # This tests the actual is_counter_trend method against known regime values

    # Test in bullish regime
    with patch.object(regime_detector, 'detect_regime', return_value="bullish"):
        # In bullish regime, short is counter-trend, long is not
        assert regime_detector.is_counter_trend("short") == True
        assert regime_detector.is_counter_trend("long") == False

    # Test in bearish regime
    with patch.object(regime_detector, 'detect_regime', return_value="bearish"):
        # In bearish regime, long is counter-trend, short is not
        assert regime_detector.is_counter_trend("long") == True
        assert regime_detector.is_counter_trend("short") == False

    # Test in neutral regime
    with patch.object(regime_detector, 'detect_regime', return_value="neutral"):
        # In neutral regime, nothing is counter-trend
        assert regime_detector.is_counter_trend("long") == False
        assert regime_detector.is_counter_trend("short") == False


def test_is_aligned_trend(regime_detector):
    """Test aligned-trend detection logic"""
    # Test in bullish regime
    with patch.object(regime_detector, 'detect_regime', return_value="bullish"):
        # In bullish regime, long is aligned, short is not
        assert regime_detector.is_aligned_trend("long") == True
        assert regime_detector.is_aligned_trend("short") == False

    # Test in bearish regime
    with patch.object(regime_detector, 'detect_regime', return_value="bearish"):
        # In bearish regime, short is aligned, long is not
        assert regime_detector.is_aligned_trend("short") == True
        assert regime_detector.is_aligned_trend("long") == False

    # Test in neutral regime
    with patch.object(regime_detector, 'detect_regime', return_value="neutral"):
        # In neutral regime, nothing is aligned
        assert regime_detector.is_aligned_trend("long") == False
        assert regime_detector.is_aligned_trend("short") == False