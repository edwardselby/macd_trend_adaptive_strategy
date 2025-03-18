
class TimeframeConfig:
    """Configuration class to store timeframe-specific indicator parameters"""

    @staticmethod
    def get_indicator_settings(timeframe: str) -> dict:
        """
        Returns optimized indicator settings for a specific timeframe.

        Args:
            timeframe: The selected timeframe ('1m', '5m', '15m', '30m', '1h', etc.)

        Returns:
            Dictionary with indicator parameter values appropriate for the timeframe
        """
        # Default settings (15m timeframe)
        settings = {
            # MACD parameters
            'fast_length': 12,
            'slow_length': 26,
            'signal_length': 9,

            # Trend detection parameters
            'adx_period': 14,
            'adx_threshold': 20,
            'ema_fast': 8,
            'ema_slow': 21,

            # Other settings
            'startup_candle_count': 30,
            'roi_cache_update_interval': 60,  # seconds
        }

        # 1-minute settings
        if timeframe == '1m':
            settings.update({
                # MACD parameters - shorter periods for faster signals
                'fast_length': 6,
                'slow_length': 14,
                'signal_length': 4,

                # Trend detection parameters - shorter for quicker trend detection
                'adx_period': 8,
                'adx_threshold': 15,  # Lower threshold due to more noise
                'ema_fast': 3,
                'ema_slow': 10,

                # Other settings
                'startup_candle_count': 20,
                'roi_cache_update_interval': 15,  # Update more frequently
            })

        # 5-minute settings
        elif timeframe == '5m':
            settings.update({
                # MACD parameters
                'fast_length': 8,
                'slow_length': 21,
                'signal_length': 6,

                # Trend detection parameters
                'adx_period': 10,
                'adx_threshold': 18,
                'ema_fast': 5,
                'ema_slow': 15,

                # Other settings
                'startup_candle_count': 25,
                'roi_cache_update_interval': 30,
            })

        # 30-minute settings
        elif timeframe == '30m':
            settings.update({
                # MACD parameters
                'fast_length': 14,
                'slow_length': 30,
                'signal_length': 10,

                # Trend detection parameters
                'adx_period': 18,
                'adx_threshold': 22,
                'ema_fast': 10,
                'ema_slow': 26,

                # Other settings
                'startup_candle_count': 35,
                'roi_cache_update_interval': 120,
            })

        # 1-hour settings
        elif timeframe == '1h':
            settings.update({
                # MACD parameters
                'fast_length': 16,
                'slow_length': 32,
                'signal_length': 12,

                # Trend detection parameters
                'adx_period': 20,
                'adx_threshold': 25,
                'ema_fast': 12,
                'ema_slow': 34,

                # Other settings
                'startup_candle_count': 40,
                'roi_cache_update_interval': 300,
            })

        return settings