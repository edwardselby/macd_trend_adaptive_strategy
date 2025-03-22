"""
MACD Trend Adaptive Strategy for FreqTrade
A sophisticated trading strategy with dynamic risk management, adaptive ROI, and market regime detection.
"""

# Explicitly import the strategy class to make it available
from src.strategy import MACDTrendAdaptiveStrategy

# This tells Python what to export when someone does "from macd_trend_adaptive_strategy import *"
__all__ = ['MACDTrendAdaptiveStrategy']
