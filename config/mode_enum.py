from enum import Enum


class StrategyMode(str, Enum):
    DEFAULT = "default"  # Default configuration (15m timeframe)
    TIMEFRAME_1M = "1m"  # Optimized for 1-minute timeframe
    TIMEFRAME_5M = "5m"  # Optimized for 5-minute timeframe
    TIMEFRAME_30M = "30m"  # Optimized for 30-minute timeframe
    TIMEFRAME_1H = "1h"  # Optimized for 1-hour timeframe