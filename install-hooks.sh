#!/bin/bash

# Script to install Git hooks for the MACD Trend Adaptive Strategy
# This sets up the post-checkout and post-merge hooks to copy the strategy wrapper

SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
HOOK_CONTENT='#!/bin/bash
# Copy strategy_wrapper.py to the correct location for FreqTrade
REPO_ROOT=$(git rev-parse --show-toplevel)
SAMPLE_PATH="$REPO_ROOT/samples/strategy_wrapper.py"
TARGET_DIR="$(dirname "$REPO_ROOT")/../strategies"

if [ -f "$SAMPLE_PATH" ]; then
    # Create strategies directory if it doesn't exist
    mkdir -p "$TARGET_DIR"

    # Copy the wrapper to strategies directory
    cp "$SAMPLE_PATH" "$TARGET_DIR/macd_trend_adaptive_strategy.py"
    echo "✅ Copied strategy wrapper to FreqTrade strategies directory"
else
    echo "❌ Error: strategy_wrapper.py not found in samples directory"
    echo "Path checked: $SAMPLE_PATH"
fi'

# Detect Git repository root
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
if [ $? -ne 0 ]; then
    echo "❌ Error: This does not appear to be a Git repository."
    echo "Please run this script from within the MACD Trend Adaptive Strategy Git repository."
    exit 1
fi

# Install post-checkout hook
echo "Installing post-checkout hook..."
echo "$HOOK_CONTENT" > "$REPO_ROOT/.git/hooks/post-checkout"
chmod +x "$REPO_ROOT/.git/hooks/post-checkout"

# Install post-merge hook (runs after git pull)
echo "Installing post-merge hook..."
echo "$HOOK_CONTENT" > "$REPO_ROOT/.git/hooks/post-merge"
chmod +x "$REPO_ROOT/.git/hooks/post-merge"

# Run the hook once to copy the file immediately
echo "Running initial copy..."
REPO_ROOT=$(git rev-parse --show-toplevel)
SAMPLE_PATH="$REPO_ROOT/samples/strategy_wrapper.py"
TARGET_DIR="$(dirname "$REPO_ROOT")/../strategies"

if [ -f "$SAMPLE_PATH" ]; then
    # Create strategies directory if it doesn't exist
    mkdir -p "$TARGET_DIR"

    # Copy the wrapper to strategies directory
    cp "$SAMPLE_PATH" "$TARGET_DIR/macd_trend_adaptive_strategy.py"
    echo "✅ Copied strategy wrapper to FreqTrade strategies directory"
else
    echo "❌ Error: strategy_wrapper.py not found in samples directory"
    echo "Path checked: $SAMPLE_PATH"
fi

echo "✅ Git hooks successfully installed"
echo "The strategy wrapper will now be automatically copied when you clone or pull this repository."