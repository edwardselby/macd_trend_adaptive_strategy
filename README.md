# MACD Trend Adaptive Strategy

A sophisticated trading strategy for FreqTrade with dynamic risk management, adaptive ROI, and market regime detection.

## Overview

This MACD Trend Adaptive Strategy is built for FreqTrade and includes several advanced features:

- **Market Regime Detection**: Automatically identifies bullish, bearish, or neutral market conditions
- **Adaptive ROI**: Dynamically adjusts take-profit targets based on recent performance
- **Dynamic Stoploss**: Risk-reward based stoploss that adapts to market conditions
- **Trend Detection**: Combines MACD crossovers with trend detection for higher-quality signals
- **Performance Tracking**: Monitors and analyzes win rates to optimize future trades

The strategy uses the MACD indicator for entry signals, but enhances it with trend filters, market regime detection, and adaptive risk management to improve overall performance.

## How the Adaptive Strategy Works

The MACD Trend Adaptive Strategy incorporates multiple layers of adaptation that work together to optimize performance across varying market conditions. This section explains the adaptive mechanisms in detail.

### 1. Performance-Based Adaptation

At the core of the strategy's adaptive nature is a sophisticated performance tracking system that:

- **Tracks win/loss history**: Maintains a record of recent trade outcomes for both long and short directions
- **Calculates win rates**: Continuously updates win rates based on recent trading performance
- **Adjusts parameters**: Uses performance metrics to influence ROI targets and stoploss levels

The `PerformanceTracker` class maintains performance metrics including:
- Overall win rates for long and short trades
- Recent win rates (based on last N trades)
- Consecutive wins/losses
- Total profit accumulation

These metrics are stored in a database, allowing the strategy to maintain performance history between bot restarts and trading sessions.

### 2. Market Regime Detection

The strategy adapts to changing market conditions through its regime detection mechanism:

- **Automatic regime identification**: The `RegimeDetector` class analyzes recent performance to classify the current market as bullish, bearish, or neutral
- **Win rate comparison**: Determines regime by comparing the performance difference between long and short trades
- **Threshold-based decisions**: Uses `regime_win_rate_diff` parameter to determine how large the win rate gap must be to declare a non-neutral regime

For example, if long trades have a 75% win rate while short trades have a 45% win rate, and the `regime_win_rate_diff` is set to 0.2 (20%), the market would be classified as "bullish" since the 30% difference exceeds the threshold.

The regime detection code works as follows:
```python
def detect_regime(self) -> Literal["bullish", "bearish", "neutral"]:
    # Get win rates based on recent trades only
    long_win_rate = self.performance_tracker.get_recent_win_rate('long')
    short_win_rate = self.performance_tracker.get_recent_win_rate('short')
    
    # Calculate win rate difference
    win_rate_difference = long_win_rate - short_win_rate
    
    # Determine regime based on relative performance
    regime = "neutral"
    if win_rate_difference > self.config.regime_win_rate_diff:
        regime = "bullish"
    elif win_rate_difference < -self.config.regime_win_rate_diff:
        regime = "bearish"
        
    return regime
```

### 3. Adaptive ROI (Take-Profit) System

The strategy dynamically adjusts ROI (take-profit) targets based on:

- **Recent win rates**: Higher win rates lead to higher ROI targets, allowing profitable strategies to aim for larger gains
- **Performance normalization**: Win rates are normalized between `min_win_rate` and `max_win_rate` to scale ROI between `min_roi` and `max_roi`
- **Market regime alignment**: ROI is further adjusted based on whether a trade aligns with or counters the current market regime
- **Direction-specific boost**: Optional `long_roi_boost` parameter can provide additional ROI for long trades when appropriate

The ROI calculation follows this process:

1. **Base ROI calculation**: Win rate is normalized and used to scale between min and max ROI
   ```python
   normalized_wr = max(0, min(1, (win_rate - self.config.min_win_rate) / 
                              (self.config.max_win_rate - self.config.min_win_rate)))
   adaptive_roi = self.config.min_roi + normalized_wr * (self.config.max_roi - self.config.min_roi)
   ```

2. **Regime-based adjustment**: Apply multipliers based on trend alignment
   ```python
   if is_counter_trend:
       factor = self.config.counter_trend_factor
       final_roi = base_roi * factor
   elif is_aligned_trend:
       factor = self.config.aligned_trend_factor
       final_roi = base_roi * factor
   ```

This system ensures that ROI targets adapt to both recent performance and market conditions, with counter-trend trades taking profits earlier (lower ROI) and trend-aligned trades allowing for larger profits (higher ROI).
### 4. Dynamic Stoploss Calculation

The strategy implements a fully dynamic stoploss system that adapts to:

- **ROI targets**: Stoploss is calculated relative to the ROI using the risk-reward ratio
- **Market regimes**: Stoploss is adjusted based on whether trades align with or counter the current regime
- **Safety boundaries**: Final stoploss values are clamped between `min_stoploss` and `max_stoploss` configurations

The stoploss calculation process:

1. **Base stoploss calculation**: Derived from ROI and risk-reward ratio
   ```python
   base_stoploss = -1 * roi * self.config.risk_reward_ratio
   ```

2. **Regime-based adjustment**: Apply factors based on trend alignment
   ```python
   if is_counter_trend:
       factor = self.config.counter_trend_stoploss_factor
       adjusted_stoploss = base_stoploss * factor
   elif is_aligned_trend:
       factor = self.config.aligned_trend_stoploss_factor
       adjusted_stoploss = base_stoploss * factor
   ```

3. **Boundary application**: Ensure stoploss stays within configured limits
   ```python
   if adjusted_stoploss > self.config.min_stoploss:
       # If stoploss is too small (closer to zero than min allows)
       final_stoploss = self.config.min_stoploss
   elif adjusted_stoploss < self.config.max_stoploss:
       # If stoploss is too large (further from zero than max allows)
       final_stoploss = self.config.max_stoploss
   else:
       # Within acceptable range
       final_stoploss = adjusted_stoploss
   ```

This system makes counter-trend trades use tighter stoploss values (closer to zero) for better protection, while trend-aligned trades can use wider stoploss values (further from zero) to avoid premature exits during normal market fluctuations.

### 5. Trade-Specific Parameter Caching

The strategy maintains a cache of parameters for each active trade, allowing it to:

- **Remember trade-specific parameters**: Each trade's ROI and stoploss values are stored in memory
- **Recover after restarts**: The strategy can reconstruct trade parameters if the bot restarts
- **Ensure consistency**: Trade parameters remain consistent throughout the trade's lifecycle

Each trade cache entry contains:
- Direction (long/short)
- Entry price
- ROI target
- Stoploss value and price
- Market regime information
- Trend alignment status

```python
cache_entry = {
    'direction': direction,
    'entry_rate': entry_rate,
    'roi': roi,
    'stoploss': stoploss,
    'stoploss_price': stoploss_price,
    'is_counter_trend': is_counter_trend,
    'is_aligned_trend': is_aligned_trend,
    'regime': regime,
    'last_updated': current_timestamp
}
```

### 6. Adaptive Indicators Configuration

The strategy allows different timeframes to use optimized indicator parameters through the `StrategyMode` selection:

- **Timeframe-specific settings**: Each timeframe (1m, 5m, 15m, 30m, 1h) has optimized MACD, ADX, and EMA parameters
- **Configuration inheritance**: Settings cascade from defaults to timeframe-specific to user-provided values
- **Validation system**: The `ConfigValidator` ensures all parameters are within acceptable ranges and logically consistent

This allows the strategy to adapt its indicator sensitivity to the characteristics of different timeframes.

### Practical Example

To illustrate the adaptive nature of the strategy, consider these scenarios:

**Scenario 1: Bullish Market**
- The strategy detects a bullish regime (long trades outperforming shorts)
- For a long trade:
  - ROI is increased via `aligned_trend_factor` (e.g., 1.2)
  - Stoploss is widened via `aligned_trend_stoploss_factor` (e.g., 1.2)
  - This allows the long trade to target higher profits and avoid premature exits
- For a short trade:
  - ROI is decreased via `counter_trend_factor` (e.g., 0.6)
  - Stoploss is tightened via `counter_trend_stoploss_factor` (e.g., 0.6)
  - This protects capital by taking profits sooner and cutting losses faster

**Scenario 2: Performance-Based Adaptation**
- Initially, short trades have a 50% win rate
- Short trade ROI is calculated as the midpoint between `min_roi` and `max_roi`
- After several successful short trades, short win rate increases to 75%
- The strategy recalculates ROI, now targeting a value closer to `max_roi`
- This adjustment allows the strategy to capitalize on its successful short pattern by seeking higher profits

By constantly adapting to market regimes and learning from trade performance, the strategy can optimize its parameters in real-time without manual intervention.

# Installation

### Prerequisites

- FreqTrade 2025.2 or higher
- Python 3.10+
- TA-Lib
- Recommended: Poetry for dependency management

### Setup

There are two ways to install this strategy:

#### Option 1: Automatic Installation (Recommended)

Use the included installation script to automatically set up the strategy in your FreqTrade environment:

```bash
# Navigate to the strategy repository
cd macd_trend_adaptive_strategy

# Run the setup script
bash setup-strategy.sh
```

The script will:
1. Copy the strategy to your FreqTrade strategies directory
2. Set up Git hooks to automatically update the strategy when you pull changes
3. Copy the sample YAML configuration file to the correct location
4. Configure everything needed to use the strategy immediately

#### Option 2: Manual Installation

1. Clone this repository into your FreqTrade `user_data/strategies` folder:

```bash
cd user_data/strategies
git clone https://github.com/yourusername/macd_trend_adaptive_strategy.git
```

2. Install dependencies:

```bash
# If using Poetry
cd macd_trend_adaptive_strategy
poetry install

# If using pip
pip install -r requirements.txt
```

3. **IMPORTANT**: Create a configuration file

This strategy requires a YAML configuration file to work properly. A sample configuration file is provided in the repository. You need to:

```bash
# Copy the sample config to the correct location
mkdir -p config
cp samples/strategy_config.sample.yaml config/strategy_config.yaml

# Then edit the file to customize it for your needs
nano config/strategy_config.yaml
```

# Configuration

The strategy requires configuration via the `strategy_config.yaml` file. Different parameter sets should be provided for various timeframes (1m, 5m, 15m, 30m, 1h).

### Basic Configuration

To use the strategy with FreqTrade, add it to your configuration:

```json
"strategy": "macd_trend_adaptive_strategy",
"strategy_path": "user_data/strategies/macd_trend_adaptive_strategy",
```

### Timeframe Selection

You can choose which timeframe parameters to use by modifying the `STRATEGY_MODE` in the strategy.py file:

```python
# Change this to select a different parameter set
STRATEGY_MODE = StrategyMode.TIMEFRAME_5M  # Options: TIMEFRAME_1M, TIMEFRAME_5M, TIMEFRAME_15M, TIMEFRAME_30M, TIMEFRAME_1H
```

The strategy will use the corresponding section from your `strategy_config.yaml` file.

### Configuration File Structure

The `strategy_config.yaml` file should have the following structure:

```yaml
# 1-minute timeframe configuration
1m:
  risk_reward_ratio: "1:1.5"
  min_stoploss: -0.01
  max_stoploss: -0.023
  fast_length: 6
  slow_length: 14
  signal_length: 4
  # Additional parameters...

# 5-minute timeframe configuration
5m:
  risk_reward_ratio: "1:4"
  min_stoploss: -0.0088
  max_stoploss: -0.0175
  fast_length: 5
  slow_length: 26
  # Additional parameters...

# Global settings (applied to all timeframes unless overridden)
global:
  counter_trend_factor: 0.5
  aligned_trend_factor: 1.0
  counter_trend_stoploss_factor: 0.5
  aligned_trend_stoploss_factor: 1.0
  # Additional global parameters...
```

Each timeframe section should contain parameters specific to that timeframe, while the "global" section contains parameters that apply to all timeframes.

### Configuration Parameters

The strategy configuration includes the following parameter categories:

#### Core Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `risk_reward_ratio` | Ratio of risk to reward for stoploss calculation (as "1:X" string) | "1:2.5" |
| `min_roi` | Minimum target ROI (used in dynamic ROI calculation) | 0.028 |
| `max_roi` | Maximum target ROI (used in dynamic ROI calculation) | 0.06 |
| `default_roi` | Fallback ROI value when adaptive calculation fails | 0.07 |
| `static_stoploss` | Fallback stoploss value when dynamic calculation fails | -0.055 |
| `min_stoploss` | Minimum (closest to zero) stoploss value | -0.02 |
| `max_stoploss` | Maximum (furthest from zero) stoploss value | -0.045 |

### Simplified ADX Configuration

To make the strategy more user-friendly, the ADX configuration has been simplified:
- No need to set `adx_period` anymore (fixed at standard value of 14)
- `adx_threshold` now accepts human-readable values:
  - `slight`: Barely trending market (value: 10)
  - `weak`: Mild trend strength (value: 30)
  - `moderate`: Medium trend strength (value: 50)
  - `strong`: Strong trend momentum (value: 70)
  - `extreme`: Very strong trending market (value: 90)

Example configuration:
```yaml
adx_threshold: "moderate"  # Medium trend strength requirement
```
### Simplified MACD Configuration

The strategy offers predefined MACD parameter sets to simplify configuration:
- `rapid`: Ultra-fast response for very short timeframes (fast: 3, slow: 8, signal: 2)
- `responsive`: Quick response for short timeframes (fast: 5, slow: 13, signal: 3)
- `classic`: Standard MACD settings (fast: 12, slow: 26, signal: 9)
- `conservative`: Reduced noise for medium timeframes (fast: 8, slow: 21, signal: 5)
- `delayed`: Slower response for higher timeframes (fast: 13, slow: 34, signal: 8)

Example configuration:
```yaml
# Use a preset
macd_preset: "classic"

# Or override specific parameters
macd_preset: "delayed"
fast_length: 10  # Override just the fast length
```

### Simplified EMA Configuration

The strategy offers predefined EMA parameter sets for trend detection:
- `ultra_short`: Very fast response for scalping (Fast: 3, Slow: 10)
- `short`: Quick response for short timeframes (Fast: 5, Slow: 20)
- `medium`: Balanced settings for medium timeframes (Fast: 8, Slow: 30)
- `long`: Longer term trend detection (Fast: 12, Slow: 50)
- `ultra_long`: Very long term trend detection (Fast: 20, Slow: 100)

Example configuration:
```yaml
# Use a preset
ema_preset: "medium"

# Or override specific parameters
ema_preset: "long"
ema_fast: 15  # Override just the fast length
```

## Strategy Logic

### Entry Signals

The strategy enters trades on MACD crossovers with trend confirmation:

- **Long Entry**: MACD crosses above signal line AND uptrend is detected
- **Short Entry**: MACD crosses below signal line AND downtrend is detected

### Exit Logic

Trades exit based on:

1. **Dynamic ROI**: Target profit based on win rate, adjusted for trend alignment
2. **Adaptive Stoploss**: Loss limit based on ROI target and risk-reward ratio
3. **Backstop Values**: Failsafe stoploss and ROI values

### Market Regime Detection

The strategy detects market regimes by comparing win rates:

- **Bullish Regime**: Long trades significantly outperform short trades
- **Bearish Regime**: Short trades significantly outperform long trades
- **Neutral Regime**: No significant performance difference

The `regime_win_rate_diff` parameter determines how large the performance gap must be to declare a non-neutral regime.

## Testing and Optimization

### Backtesting

Run backtesting with FreqTrade:

```bash
freqtrade backtesting --strategy MACDTrendAdaptiveStrategy --timerange 20230101-20231231
```

### Hyperoptimization

The strategy is designed to work with FreqTrade's hyperopt functionality. Suggested hyperopt spaces:

```json
"spaces": ["buy", "roi", "stoploss"],
```

Key parameters to optimize:

- `fast_length`, `slow_length`, `signal_length`
- `adx_threshold`
- `risk_reward_ratio`
- `min_roi` and `max_roi`

## Performance Tracking

The strategy includes a sophisticated performance tracking system that:

1. Monitors win rates for both long and short trades
2. Detects changes in market regime
3. Adapts ROI and stoploss dynamically based on performance

Performance data is saved to the FreqTrade database for persistence between bot restarts.

## Common Issues and Solutions

### Issue: Strategy not taking trades
- Check that `startup_candle_count` is sufficient for calculating all indicators
- Verify that the MACD parameters are appropriate for your timeframe

### Issue: Too many trades (overtrading)
- Increase `adx_threshold` to require stronger trends
- Increase the gap between `fast_length` and `slow_length`

### Issue: Trades stop too early (ROI too low)
- Increase `min_roi` and `max_roi`
- Increase `aligned_trend_factor` to allow trend-following trades to run longer

### Issue: Frequent stoploss hits
- Adjust `risk_reward_ratio` to allow wider stoplosses
- Increase `counter_trend_stoploss_factor` to give counter-trend trades more room

## TODO:


## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## Disclaimer

Trading cryptocurrencies involves significant risk and can result in loss of funds. This strategy is provided as-is with no guarantees of profitability. Always test thoroughly before using with real funds.