#!/usr/bin/env bash

set -euo pipefail

echo "==> Direct test of the exact commands that should run..."

# Replicate the exact execution that happens in the test framework
LEGACY_ORCHESTRATOR="scripts/orchestrate.sh"
MODERN_ORCHESTRATOR="scripts/orchestrate_modern.sh"
TEST_LOG_DIR="/tmp/direct_test_$$"

mkdir -p "$TEST_LOG_DIR"

legacy_command="$LEGACY_ORCHESTRATOR --invalid-flag 2>&1"
modern_command="$MODERN_ORCHESTRATOR --invalid-flag 2>&1"

echo "==> Testing legacy command: $legacy_command"
legacy_exit=0
eval "$legacy_command" >"$TEST_LOG_DIR/legacy.log" 2>&1 || legacy_exit=$?
echo "Legacy exit code: $legacy_exit"

echo "==> Testing modern command: $modern_command" 
modern_exit=0
eval "$modern_command" >"$TEST_LOG_DIR/modern.log" 2>&1 || modern_exit=$?
echo "Modern exit code: $modern_exit"

echo "==> Both commands completed"
echo "Legacy output:"
cat "$TEST_LOG_DIR/legacy.log"
echo ""
echo "Modern output:"  
cat "$TEST_LOG_DIR/modern.log"

rm -rf "$TEST_LOG_DIR"
echo "==> Test completed successfully"