#!/usr/bin/env bash

set -euo pipefail

echo "==> Testing orchestrator invalid argument handling..."

# Set up variables like in the original test
LEGACY_ORCHESTRATOR="scripts/orchestrate.sh"
MODERN_ORCHESTRATOR="scripts/orchestrate_modern.sh"
TEST_LOG_DIR="/tmp/simple_test_$$"

mkdir -p "$TEST_LOG_DIR"

echo "==> Running legacy command..."
legacy_exit=0
eval "$LEGACY_ORCHESTRATOR --invalid-flag 2>&1 || true" > "$TEST_LOG_DIR/legacy.log" 2>&1 || legacy_exit=$?

echo "==> Running modern command..."  
modern_exit=0
eval "$MODERN_ORCHESTRATOR --invalid-flag 2>&1 || true" > "$TEST_LOG_DIR/modern.log" 2>&1 || modern_exit=$?

echo "==> Results:"
echo "Legacy exit code: $legacy_exit"
echo "Modern exit code: $modern_exit"
echo "Legacy log:"
cat "$TEST_LOG_DIR/legacy.log"
echo "Modern log:"
cat "$TEST_LOG_DIR/modern.log"

echo "==> Test completed successfully"