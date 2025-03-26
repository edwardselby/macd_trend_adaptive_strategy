import logging
import os
from typing import Dict, Any


try:
    import yaml
except ImportError:
    raise ImportError(
        "PyYAML is required for this strategy. Please install it using 'pip install pyyaml'\n"
        "Or if using Docker, run: docker exec -it your-freqtrade-container pip install pyyaml\n"
        "Or simply add pyyaml to freqtrade's requirements.txt and rebuild the container"
    )

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

        return config_data

    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in configuration file {config_path}: {e}")
    except Exception as e:
        raise ValueError(f"Failed to load configuration from {config_path}: {e}")