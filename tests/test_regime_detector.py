from unittest.mock import patch


def test_detect_regime(regime_detector, performance_tracker):
    """Test that market regime is correctly detected based on win rates"""
    # Configure threshold
    regime_detector.config.regime_win_rate_diff = 0.2
    regime_detector.config.min_recent_trades_per_direction = 4

    # Test scenarios
    scenarios = [
        # win_rates, trade_counts, expected_regime
        {"long_wr": 0.75, "short_wr": 0.45, "trades": 10, "expected": "bullish"},
        {"long_wr": 0.40, "short_wr": 0.70, "trades": 10, "expected": "bearish"},
        {"long_wr": 0.55, "short_wr": 0.45, "trades": 10, "expected": "neutral"},
        {"long_wr": 0.75, "short_wr": 0.45, "trades": 2, "expected": "neutral"}  # Not enough trades
    ]

    for scenario in scenarios:
        # Patch win rate and trade count methods
        with patch.object(performance_tracker, 'get_recent_win_rate',
                          side_effect=lambda direction: scenario["long_wr"] if direction == "long" else scenario[
                              "short_wr"]):
            with patch.object(performance_tracker, 'get_recent_trades_count', return_value=scenario["trades"]):
                # Call the actual implementation
                regime = regime_detector.detect_regime()

                # Check result
                assert regime == scenario["expected"], \
                    f"Expected {scenario['expected']} regime with long WR {scenario['long_wr']}, " \
                    f"short WR {scenario['short_wr']}, trades {scenario['trades']}, got {regime}"


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