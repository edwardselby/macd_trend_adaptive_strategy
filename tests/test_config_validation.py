import json
import os
import tempfile

import pytest

from config.config_validator import ConfigValidator
from config.strategy_config import StrategyConfig, StrategyMode


class TestConfigValidator:
    """Test class for ConfigValidator"""

    @pytest.fixture
    def sample_config_file(self):
        """Create a temporary config file with minimal valid settings"""
        config_data = {
            "15m": {
                "risk_reward_ratio": "1:2",
                "min_roi": 0.025,
                "max_roi": 0.055,
                "fast_length": 12,
                "slow_length": 26,
                "signal_length": 9,
                "adx_period": 14,
                "adx_threshold": 25,
                "ema_fast": 8,
                "ema_slow": 21
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            json.dump(config_data, temp_file)
            temp_file_path = temp_file.name

        yield temp_file_path

        # Clean up the temporary file
        os.unlink(temp_file_path)

    def test_validate_required_parameters(self, sample_config_file):
        """Test that required parameters are validated"""
        config = StrategyConfig(mode=StrategyMode.DEFAULT, config_path=sample_config_file)

        # Test with all required parameters present
        errors, fixes = ConfigValidator.validate_and_fix(config)
        assert len(errors) == 0, "No errors should be found with valid config"

        # Test with a missing parameter by temporarily removing it
        original_fast_length = config.fast_length
        delattr(config, 'fast_length')

        errors, fixes = ConfigValidator.validate_and_fix(config)
        # Check for the actual error message format
        assert any("Missing required parameter: fast_length" in error for error in errors)

        # Restore the parameter
        config.fast_length = original_fast_length

    def test_validate_parameter_types(self, sample_config_file):
        """Test that parameter types are validated"""
        config = StrategyConfig(mode=StrategyMode.DEFAULT, config_path=sample_config_file)

        # Test with correct parameter types
        errors, fixes = ConfigValidator.validate_and_fix(config)
        assert len(errors) == 0, "No errors should be found with valid config"

        # Test with incorrect parameter types
        config.min_roi = "0.025"  # Should be float
        config.fast_length = "12"  # Should be int

        errors, fixes = ConfigValidator.validate_and_fix(config)

        # Check that type errors are reported
        assert any("min_roi has incorrect type" in error for error in errors)
        assert any("fast_length has incorrect type" in error for error in errors)

        # Check that fixes were applied
        assert any("min_roi" in fix for fix in fixes)
        assert any("fast_length" in fix for fix in fixes)

        # Verify the values were corrected
        assert isinstance(config.min_roi, float)
        assert isinstance(config.fast_length, int)

    def test_validate_value_constraints(self, sample_config_file):
        """Test that parameter value constraints are validated"""
        config = StrategyConfig(mode=StrategyMode.DEFAULT, config_path=sample_config_file)

        # Set values outside of constraints
        config.min_roi = 0.5  # Above max (0.2)
        config.fast_length = 1  # Below min (2)
        config.counter_trend_factor = 2.0  # Above max (1.0)

        errors, fixes = ConfigValidator.validate_and_fix(config)

        # Check that the fixes were applied - more reliable than checking specific error messages
        assert config.min_roi <= 0.2, "min_roi should be clamped to max allowed value"
        assert config.fast_length >= 2, "fast_length should be clamped to min allowed value"
        assert config.counter_trend_factor <= 1.0, "counter_trend_factor should be clamped to max allowed value"

        # Check that fixes contained entries about the adjusted parameters
        assert any("min_roi" in fix for fix in fixes), "Should contain fix for min_roi"
        assert any("fast_length" in fix for fix in fixes), "Should contain fix for fast_length"
        assert any("counter_trend_factor" in fix for fix in fixes), "Should contain fix for counter_trend_factor"

    def test_validate_logical_consistency(self, sample_config_file):
        """Test that logical consistency between parameters is validated"""
        config = StrategyConfig(mode=StrategyMode.DEFAULT, config_path=sample_config_file)

        # Create logical inconsistencies
        config.min_roi = 0.06
        config.max_roi = 0.04  # min_roi should be less than max_roi
        config.fast_length = 30
        config.slow_length = 20  # fast_length should be less than slow_length
        config.ema_fast = 25
        config.ema_slow = 15  # ema_fast should be less than ema_slow

        # Apply fixes
        errors, fixes = ConfigValidator.validate_and_fix(config)

        # Instead of checking exact values (which are implementation-dependent),
        # just check the relationship was fixed
        assert config.min_roi <= config.max_roi, "min_roi should be less than or equal to max_roi"
        assert config.fast_length < config.slow_length, "fast_length should be less than slow_length"
        assert config.ema_fast < config.ema_slow, "ema_fast should be less than ema_slow"

        # Check that fixes mention the parameters
        assert any(("roi" in fix.lower() or "min_" in fix.lower() or "max_" in fix.lower()) for fix in fixes), \
            "Should mention ROI parameters in fixes"
        assert any(("length" in fix.lower() or "fast_" in fix.lower() or "slow_" in fix.lower()) for fix in fixes), \
            "Should mention length parameters in fixes"
        assert any(("ema" in fix.lower()) for fix in fixes), \
            "Should mention EMA parameters in fixes"

    def test_parameter_info(self):
        """Test getting parameter information"""
        info = ConfigValidator.get_parameter_info()

        # Check that info contains key parameters
        assert 'min_roi' in info
        assert 'max_roi' in info
        assert 'risk_reward_ratio' in info
        assert 'fast_length' in info
        assert 'slow_length' in info

        # Check that each parameter has complete info
        for param_name, param_info in info.items():
            assert 'type' in param_info
            assert 'required' in param_info
            assert 'min_value' in param_info
            assert 'max_value' in param_info
            assert 'default' in param_info