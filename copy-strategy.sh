#!/bin/bash

# Simple script to manually copy the strategy wrapper to the FreqTrade strategies directory
# This can be used if you don't want to use Git hooks

# Get the absolute path of the directory this script is in
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")

# Define paths
SAMPLE_PATH="$SCRIPT_DIR/samples/strategy_wrapper.py"
TARGET_DIR="$SCRIPT_DIR/../strategies"

# Check if the sample file exists
if [ ! -f "$SAMPLE_PATH" ]; then
    echo "❌ Error: strategy_wrapper.py not found in samples directory"
    echo "Path checked: $SAMPLE_PATH"
    exit 1
fi

# Create strategies directory if it doesn't exist
mkdir -p "$TARGET_DIR"

# Copy the file
cp "$SAMPLE_PATH" "$TARGET_DIR/macd_trend_adaptive_strategy.py"

echo "✅ Successfully copied strategy wrapper to FreqTrade strategies directory"
echo "Location: $TARGET_DIR/macd_trend_adaptive_strategy.py"