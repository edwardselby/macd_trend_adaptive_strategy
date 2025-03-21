from datetime import datetime


def create_trade_id(pair: str, time: datetime) -> str:
    """Create a unique identifier for a trade"""
    return f"{pair}_{time.timestamp()}"


def get_direction(is_short: bool) -> str:
    """Get the string direction from a boolean is_short flag"""
    return 'short' if is_short else 'long'
