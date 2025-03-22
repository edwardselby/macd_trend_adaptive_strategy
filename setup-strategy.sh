#!/bin/bash

# Direct solution to install the MACD Trend Adaptive Strategy
# This script handles everything needed to set up the strategy

# Also creates a Git "auto-restore" mechanism that will recreate the strategy file
# if it's deleted when you run git pull or checkout

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

# Set up Git hooks for automatic updates
if [ -d "$REPO_DIR/.git" ]; then
    echo "Setting up Git hooks for automatic updates..."

    HOOK_DIR="$REPO_DIR/.git/hooks"
    HOOK_CONTENT="#!/bin/bash
# Auto-generated hook for MACD Trend Adaptive Strategy
WRAPPER_PATH=\"$WRAPPER_PATH\"
STRATEGIES_DIR=\"$STRATEGIES_DIR\"

# Check if wrapper file exists
if [ -f \"\$WRAPPER_PATH\" ]; then
    # Ensure strategies directory exists
    mkdir -p \"\$STRATEGIES_DIR\"

    # Copy the file
    cp \"\$WRAPPER_PATH\" \"\$STRATEGIES_DIR/macd_trend_adaptive_strategy.py\"
    echo \"✅ MACD Trend Adaptive Strategy file updated in FreqTrade strategies directory\"
else
    echo \"⚠️ Strategy wrapper file not found at \$WRAPPER_PATH after Git operation\"
fi"

    # Create post-merge hook (runs after git pull)
    POST_MERGE_HOOK="$HOOK_DIR/post-merge"
    echo "$HOOK_CONTENT" > "$POST_MERGE_HOOK"
    chmod +x "$POST_MERGE_HOOK"

    # Create post-checkout hook (runs after git checkout, clone, etc.)
    POST_CHECKOUT_HOOK="$HOOK_DIR/post-checkout"
    echo "$HOOK_CONTENT" > "$POST_CHECKOUT_HOOK"
    chmod +x "$POST_CHECKOUT_HOOK"

    echo "✅ Git hooks installed. Strategy will update automatically when you pull changes or switch branches."
else
    echo "⚠️ Not a Git repository. Strategy will need to be manually updated."
fi

echo "Done! You can now use the MACD Trend Adaptive Strategy in FreqTrade."
echo "Update your config.json to include: \"strategy\": \"MACDTrendAdaptiveStrategy\""