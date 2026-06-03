#!/usr/bin/env bash

set -euo pipefail

echo "Testing eval patterns..."

TEST_LOG_DIR="/tmp/simple_eval_test_$$" 
mkdir -p "$TEST_LOG_DIR"

LEGACY_ORCHESTRATOR="scripts/orchestrate.sh"
MODERN_ORCHESTRATOR="scripts/orchestrate_modern.sh"

# Test the exact pattern from the test framework
echo "==> Test 1: Legacy help with eval"
legacy_exit=0
eval "$LEGACY_ORCHESTRATOR --help" >"$TEST_LOG_DIR/legacy_help.log" 2>&1 || legacy_exit=$?
echo "Legacy help completed with exit: $legacy_exit"

echo "==> Test 2: Modern help with eval"
modern_exit=0
eval "$MODERN_ORCHESTRATOR --help" >"$TEST_LOG_DIR/modern_help.log" 2>&1 || modern_exit=$?
echo "Modern help completed with exit: $modern_exit"

echo "==> Test 3: Legacy invalid with eval"
legacy_exit=0
eval "$LEGACY_ORCHESTRATOR --invalid-flag 2>&1" >"$TEST_LOG_DIR/legacy_invalid.log" 2>&1 || legacy_exit=$?
echo "Legacy invalid completed with exit: $legacy_exit"

echo "==> Test 4: Modern invalid with eval"
modern_exit=0
eval "$MODERN_ORCHESTRATOR --invalid-flag 2>&1" >"$TEST_LOG_DIR/modern_invalid.log" 2>&1 || modern_exit=$?
echo "Modern invalid completed with exit: $modern_exit"

echo "==> All eval tests completed"
rm -rf "$TEST_LOG_DIR"