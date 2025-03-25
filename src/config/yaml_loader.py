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
    file_ext = os.path.splitext(config_path)[1].lower()
    if file_ext not in ['.yaml', '.yml']:
        raise ValueError(f"Configuration file must have a .yaml or .yml extension, got: {file_ext}")

    try:
        # Load YAML content
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
            logger.info(f"Loaded YAML configuration from {config_path}")

        # Basic validation
        if not isinstance(config_data, dict):
            raise ValueError(f"Configuration file {config_path} must contain a dictionary")

        # Get valid timeframes from StrategyMode
        from .strategy_config import StrategyMode
        valid_timeframes = [mode.value for mode in StrategyMode if mode.value != "auto"]

        # Check for at least one timeframe section or global section
        timeframes = [tf for tf in config_data.keys() if tf in valid_timeframes]
        if not timeframes and "global" not in config_data:
            raise ValueError(
                f"Configuration file {config_path} must contain at least one timeframe section {valid_timeframes} or a global section")

        return config_data

    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in configuration file {config_path}: {e}")
    except Exception as e:
        raise ValueError(f"Failed to load configuration from {config_path}: {e}")