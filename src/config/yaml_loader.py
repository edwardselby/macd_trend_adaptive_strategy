"""
YAML configuration loader for MACD Trend Adaptive Strategy.
Handles loading and basic validation of YAML configuration files.
"""
import logging
import os
from typing import Dict, Any

import yaml

logger = logging.getLogger(__name__)


def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load configuration from YAML file

    Args:
        config_path: Path to YAML configuration file

    Returns:
        dict: Loaded configuration data

    Raises:
        ValueError: If file doesn't exist or contains invalid YAML
    """
    # Check if file exists
    if not os.path.exists(config_path):
        raise ValueError(f"Configuration file not found: {config_path}")

    # Check file extension
    if not config_path.lower().endswith(('.yaml', '.yml')):
        logger.warning(f"File {config_path} does not have a .yaml or .yml extension")

    try:
        # Load YAML content
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)

        # Basic validation
        if not isinstance(config_data, dict):
            raise ValueError(f"Configuration file {config_path} must contain a YAML dictionary")

        # Check for at least one timeframe section
        timeframes = [tf for tf in config_data.keys() if tf in ["1m", "5m", "15m", "30m", "1h"]]
        if not timeframes:
            raise ValueError(f"Configuration file {config_path} must contain at least one timeframe section (1m, 5m, 15m, 30m, 1h)")

        return config_data

    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in configuration file {config_path}: {e}")
    except Exception as e:
        raise ValueError(f"Failed to load configuration from {config_path}: {e}")