import pytest


@pytest.mark.parametrize(
    "stoploss, is_counter, is_aligned, expected_min, expected_max", [
        # stoploss value, is_counter, is_aligned, min_expected, max_expected
        (-0.02, False, False, 0.0399, 0.0401),  # Base case: neutral trend
        (-0.02, True, False, 0.0199, 0.0201),  # Counter trend (reduces ROI)
        (-0.02, False, True, 0.0599, 0.0601),  # Aligned trend (increases ROI)
        (-0.04, False, False, 0.0799, 0.0801),  # Wider stoploss, neutral trend
        (-0.01, False, False, 0.0199, 0.0201),  # Tighter stoploss, neutral trend
    ]
)
def test_calculate_roi_from_stoploss(
        roi_calculator, stoploss, is_counter, is_aligned, expected_min, expected_max
):
    """Test that ROI is correctly calculated from stoploss value and trend alignment"""
    # Configure risk-reward ratio - this should determine how ROI scales from stoploss
    roi_calculator.config.risk_reward_ratio = 2.0  # 1:2 ratio

    # Configure trend factors
    roi_calculator.config.counter_trend_factor = 0.5
    roi_calculator.config.aligned_trend_factor = 1.5

    # Calculate ROI from stoploss
    result = roi_calculator.calculate_roi_from_stoploss(stoploss, is_counter, is_aligned)

    # Check if result is within expected range
    assert expected_min <= result <= expected_max, \
        f"With stoploss={stoploss}, counter={is_counter}, aligned={is_aligned}: " \
        f"expected range [{expected_min}, {expected_max}], got {result}"

    # Verify relationship between counter/aligned/neutral
    base_roi = roi_calculator.calculate_roi_from_stoploss(stoploss, False, False)

    if is_counter:
        assert result < base_roi, f"Counter-trend ROI ({result}) should be lower than neutral ({base_roi})"
    elif is_aligned:
        assert result > base_roi, f"Aligned-trend ROI ({result}) should be higher than neutral ({base_roi})"


def test_update_roi_cache(roi_calculator):
    """Test that ROI cache is updated correctly with function parameters"""
    # Set up initial state
    old_timestamp = 100  # Very old timestamp
    roi_calculator.roi_cache = {
        'long': 0.03,
        'short': 0.03,
        'last_updated': old_timestamp
    }
    roi_calculator.config.roi_cache_update_interval = 50  # Short interval for testing

    # Set expected risk-reward ratio and factors
    roi_calculator.config.risk_reward_ratio = 2.0
    roi_calculator.config.counter_trend_factor = 0.5
    roi_calculator.config.aligned_trend_factor = 1.5

    # Mock functions needed for the update_roi_cache method
    win_rates = {'long': 0.6, 'short': 0.4}
    is_counter_trend_fn = lambda direction: direction == 'short'  # Mock counter trend function
    is_aligned_trend_fn = lambda direction: direction == 'long'  # Mock aligned trend function

    # Mock stoploss values by direction
    stoploss_values = {'long': -0.025, 'short': -0.020}

    # Mock the calculate_dynamic_stoploss function - will be called with (win_rate, is_counter, is_aligned)
    def mock_calculate_stoploss(win_rate, is_counter, is_aligned):
        # For testing purposes, return the predetermined values based on if test is for long/short
        # We determine this from the is_counter and is_aligned values, since we set those up
        # to correspond to directions
        if is_aligned:  # We set is_aligned to be true only for 'long'
            return stoploss_values['long']
        elif is_counter:  # We set is_counter to be true only for 'short'
            return stoploss_values['short']
        else:
            return -0.023  # Default fallback value

    # Current timestamp that will trigger an update
    current_timestamp = old_timestamp + 60

    # Call the method to update the cache
    roi_calculator.update_roi_cache(
        current_timestamp,
        win_rates,
        is_counter_trend_fn,
        is_aligned_trend_fn,
        mock_calculate_stoploss
    )

    # Verify cache was updated
    assert roi_calculator.roi_cache['last_updated'] == current_timestamp, \
        "Cache timestamp should be updated"

    # Expected ROIs - apply the calculation manually as a verification
    # Long: aligned trend, stoploss -0.025, risk_reward 2.0, aligned factor 1.5
    expected_long_roi = abs(stoploss_values['long']) * 2.0 * 1.5
    # Short: counter trend, stoploss -0.020, risk_reward 2.0, counter factor 0.5
    expected_short_roi = abs(stoploss_values['short']) * 2.0 * 0.5

    assert abs(roi_calculator.roi_cache['long'] - expected_long_roi) < 0.0001, \
        f"Long ROI should be updated to {expected_long_roi}, got {roi_calculator.roi_cache['long']}"
    assert abs(roi_calculator.roi_cache['short'] - expected_short_roi) < 0.0001, \
        f"Short ROI should be updated to {expected_short_roi}, got {roi_calculator.roi_cache['short']}"

    # Test when update is not needed
    previous_cache = roi_calculator.roi_cache.copy()
    new_timestamp = current_timestamp + 10  # Not enough time passed

    # Call update again
    roi_calculator.update_roi_cache(
        new_timestamp,
        win_rates,
        is_counter_trend_fn,
        is_aligned_trend_fn,
        mock_calculate_stoploss
    )

    # Verify cache was NOT updated
    assert roi_calculator.roi_cache['last_updated'] == current_timestamp, \
        "Cache timestamp should not change"
    assert roi_calculator.roi_cache['long'] == previous_cache['long'], \
        "Long ROI should not change"
    assert roi_calculator.roi_cache['short'] == previous_cache['short'], \
        "Short ROI should not change"
