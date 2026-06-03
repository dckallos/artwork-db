#!/usr/bin/env bash

set -euo pipefail

echo "Starting debug test..."

# Test the specific command that might be hanging
legacy_command="scripts/orchestrate.sh --invalid-flag 2>&1 || true"
modern_command="scripts/orchestrate_modern.sh --invalid-flag 2>&1 || true"

echo "Testing legacy command..."
legacy_exit=0
eval "$legacy_command" > /tmp/legacy_test.log 2>&1 || legacy_exit=$?
echo "Legacy exit code: $legacy_exit"
echo "Legacy output:"
cat /tmp/legacy_test.log

echo ""
echo "Testing modern command..."
modern_exit=0
eval "$modern_command" > /tmp/modern_test.log 2>&1 || modern_exit=$?
echo "Modern exit code: $modern_exit"
echo "Modern output:"
cat /tmp/modern_test.log

echo ""
echo "Both tests completed successfully"