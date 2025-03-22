from macd_trend_adaptive_strategy import MACDTrendAdaptiveStrategy as Strategy


# This re-exports the strategy so FreqTrade can find it
# You can use this class name when running FreqTrade
class MACDTrendAdaptiveStrategy(Strategy):
    """
    Wrapper for MACD Trend Adaptive Strategy
    """
    pass
