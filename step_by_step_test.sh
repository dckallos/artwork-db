#!/usr/bin/env bash

set -euo pipefail

echo "==> Step-by-step test to find hanging point"

TEST_LOG_DIR="/tmp/step_test_$$"
mkdir -p "$TEST_LOG_DIR"

echo "==> Step 1: Run legacy orchestrator help"
timeout 10s scripts/orchestrate.sh --help > "$TEST_LOG_DIR/legacy_help.log" 2>&1
echo "Legacy help completed, lines: $(wc -l < "$TEST_LOG_DIR/legacy_help.log")"

echo "==> Step 2: Run modern orchestrator help"  
timeout 10s scripts/orchestrate_modern.sh --help > "$TEST_LOG_DIR/modern_help.log" 2>&1
echo "Modern help completed, lines: $(wc -l < "$TEST_LOG_DIR/modern_help.log")"

echo "==> Step 3: Run legacy invalid flag"
legacy_exit=0
timeout 10s bash -c 'scripts/orchestrate.sh --invalid-flag 2>&1' > "$TEST_LOG_DIR/legacy_invalid.log" || legacy_exit=$?
echo "Legacy invalid flag completed, exit: $legacy_exit, lines: $(wc -l < "$TEST_LOG_DIR/legacy_invalid.log")"

echo "==> Step 4: Run modern invalid flag"
modern_exit=0
timeout 10s bash -c 'scripts/orchestrate_modern.sh --invalid-flag 2>&1' > "$TEST_LOG_DIR/modern_invalid.log" || modern_exit=$?
echo "Modern invalid flag completed, exit: $modern_exit, lines: $(wc -l < "$TEST_LOG_DIR/modern_invalid.log")"

echo "==> Step 5: Run the actual eval commands like the test does"
legacy_exit=0
timeout 10s bash -c 'eval "scripts/orchestrate.sh --invalid-flag 2>&1"' > "$TEST_LOG_DIR/eval_legacy.log" || legacy_exit=$?
echo "Eval legacy completed, exit: $legacy_exit"

modern_exit=0  
timeout 10s bash -c 'eval "scripts/orchestrate_modern.sh --invalid-flag 2>&1"' > "$TEST_LOG_DIR/eval_modern.log" || modern_exit=$?
echo "Eval modern completed, exit: $modern_exit"

echo "==> All steps completed successfully!"

echo "Legacy help output (first 5 lines):"
head -5 "$TEST_LOG_DIR/legacy_help.log"

echo "Modern help output (first 5 lines):"  
head -5 "$TEST_LOG_DIR/modern_help.log"

rm -rf "$TEST_LOG_DIR"