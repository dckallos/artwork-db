#!/usr/bin/env bash

set -euo pipefail

echo "==> Minimal test to isolate hanging issue..."

# Source the logging functions from the test script
_log_success() {
    echo "==> [legacy_comparison] $*" >&2
}

_log_failure() {
    echo "==> [legacy_comparison] $*" >&2
}

_compare_error_messages() {
    local legacy_log="$1" modern_log="$2" legacy_exit="$3" modern_exit="$4" test_name="$5"
    
    echo "==> In _compare_error_messages function"
    echo "Legacy exit: $legacy_exit, Modern exit: $modern_exit"
    
    # Both should have non-zero exit codes for error conditions
    if [[ $legacy_exit -ne 0 && $modern_exit -ne 0 ]]; then
        _log_success "✓ $test_name (both failed appropriately)"
        echo "TESTS_PASSED incremented"
    else
        _log_failure "✗ $test_name - inconsistent error handling (legacy exit: $legacy_exit, modern exit: $modern_exit)"
        echo "TESTS_FAILED incremented"
    fi
    
    echo "==> _compare_error_messages completed"
}

# Test the exact scenario
TEST_LOG_DIR="/tmp/minimal_test_$$"
mkdir -p "$TEST_LOG_DIR"

echo "==> Running legacy command..."
legacy_exit=0
eval "scripts/orchestrate.sh --invalid-flag 2>&1" >"$TEST_LOG_DIR/legacy.log" 2>&1 || legacy_exit=$?

echo "==> Running modern command..."
modern_exit=0  
eval "scripts/orchestrate_modern.sh --invalid-flag 2>&1" >"$TEST_LOG_DIR/modern.log" 2>&1 || modern_exit=$?

echo "==> Commands completed, calling comparison function..."
_compare_error_messages "$TEST_LOG_DIR/legacy.log" "$TEST_LOG_DIR/modern.log" "$legacy_exit" "$modern_exit" "orchestrator_invalid_args"

echo "==> All done!"
rm -rf "$TEST_LOG_DIR"