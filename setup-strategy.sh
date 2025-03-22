#!/bin/bash

# Direct solution to install the MACD Trend Adaptive Strategy
# This script handles everything needed to set up the strategy

# Find the paths we need
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
FREQTRADE_ROOT=$(realpath "$SCRIPT_DIR/../..")
STRATEGIES_DIR="$FREQTRADE_ROOT/strategies"
REPO_DIR="$SCRIPT_DIR"
SAMPLE_DIR="$REPO_DIR/samples"
WRAPPER_PATH="$SAMPLE_DIR/strategy_wrapper.py"

# Print debug info
echo "Setting up MACD Trend Adaptive Strategy..."
echo "Script directory: $SCRIPT_DIR"
echo "FreqTrade root: $FREQTRADE_ROOT"
echo "Strategies directory: $STRATEGIES_DIR"
echo "Strategy wrapper path: $WRAPPER_PATH"

# Check if we can find the strategy wrapper
if [ ! -f "$WRAPPER_PATH" ]; then
    echo "❌ Strategy wrapper not found at $WRAPPER_PATH"

    # Try to find it
    echo "Searching for strategy_wrapper.py..."
    FOUND_WRAPPER=$(find "$REPO_DIR" -name "strategy_wrapper.py" -type f | head -1)

    if [ -n "$FOUND_WRAPPER" ]; then
        echo "✅ Found wrapper at: $FOUND_WRAPPER"
        WRAPPER_PATH="$FOUND_WRAPPER"
    else
        echo "❌ Could not find strategy_wrapper.py anywhere in the repository."
        exit 1
    fi
fi

# Create the strategies directory if it doesn't exist
if [ ! -d "$STRATEGIES_DIR" ]; then
    echo "Creating strategies directory at $STRATEGIES_DIR"
    mkdir -p "$STRATEGIES_DIR"
fi

# Copy the wrapper to the strategies directory
echo "Copying strategy wrapper to $STRATEGIES_DIR/macd_trend_adaptive_strategy.py"
cp "$WRAPPER_PATH" "$STRATEGIES_DIR/macd_trend_adaptive_strategy.py"

if [ $? -eq 0 ]; then
    echo "✅ Strategy installed successfully!"
    echo "Strategy is now available as 'MACDTrendAdaptiveStrategy' in FreqTrade"
else
    echo "❌ Failed to copy strategy wrapper"
    exit 1
fi

# Set up Git hook for automatic updates
if [ -d "$REPO_DIR/.git" ]; then
    echo "Setting up Git hook for automatic updates..."

    HOOK_DIR="$REPO_DIR/.git/hooks"
    POST_MERGE_HOOK="$HOOK_DIR/post-merge"

    # Create hook content
    echo "#!/bin/bash" > "$POST_MERGE_HOOK"
    echo "# Auto-generated hook for MACD Trend Adaptive Strategy" >> "$POST_MERGE_HOOK"
    echo "cp '$WRAPPER_PATH' '$STRATEGIES_DIR/macd_trend_adaptive_strategy.py'" >> "$POST_MERGE_HOOK"
    echo "echo 'Updated MACD Trend Adaptive Strategy wrapper file'" >> "$POST_MERGE_HOOK"

    # Make it executable
    chmod +x "$POST_MERGE_HOOK"

    echo "✅ Git hook installed. Strategy will update automatically when you pull changes."
else
    echo "⚠️ Not a Git repository. Strategy will need to be manually updated."
fi

echo "Done! You can now use the MACD Trend Adaptive Strategy in FreqTrade."
echo "Update your config.json to include: \"strategy\": \"MACDTrendAdaptiveStrategy\""