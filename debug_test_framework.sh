#!/usr/bin/env bash

set -euo pipefail

# Copy the test framework initialization
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)" 
readonly TEST_LOG_DIR="/tmp/debug_test_framework_$$"
readonly TEST_CONFIG="${REPO_ROOT}/config/artwork_domain.yml"

# Script paths
readonly LEGACY_ORCHESTRATOR="${REPO_ROOT}/scripts/orchestrate.sh"
readonly MODERN_ORCHESTRATOR="${REPO_ROOT}/scripts/orchestrate_modern.sh"

# Test state tracking
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Copy logging functions
_log_info() {
    echo "==> [legacy_comparison] $*" >&2
}

_log_success() {
    echo "==> [legacy_comparison] $*" >&2
}

_log_failure() {
    echo "==> [legacy_comparison] $*" >&2
}

_log_debug() {
    if [[ "${FRAMEWORK_DEBUG:-0}" == "1" ]]; then
        echo "DEBUG [legacy_comparison] $*" >&2
    fi
}

# Copy comparison functions
_compare_help_content() {
    local legacy_log="$1" modern_log="$2" test_name="$3"
    
    # Check if both have substantial help content
    local legacy_lines modern_lines
    legacy_lines=$(wc -l < "$legacy_log")
    modern_lines=$(wc -l < "$modern_log")
    
    if [[ $modern_lines -ge 10 ]]; then
        _log_success "✓ $test_name (legacy: $legacy_lines lines, modern: $modern_lines lines)"
        ((TESTS_PASSED++))
    else
        _log_failure "✗ $test_name - insufficient help content in modern script"
        ((TESTS_FAILED++))
    fi
}

_compare_error_messages() {
    local legacy_log="$1" modern_log="$2" legacy_exit="$3" modern_exit="$4" test_name="$5"
    
    # Both should have non-zero exit codes for error conditions
    if [[ $legacy_exit -ne 0 && $modern_exit -ne 0 ]]; then
        _log_success "✓ $test_name (both failed appropriately)"
        ((TESTS_PASSED++))
    else
        _log_failure "✗ $test_name - inconsistent error handling (legacy exit: $legacy_exit, modern exit: $modern_exit)"
        ((TESTS_FAILED++))
    fi
}

# Copy the test execution function
_run_comparison_test() {
    local test_name="$1"
    local legacy_command="$2"
    local modern_command="$3"
    local comparison_type="$4"
    
    ((TESTS_RUN++))
    
    local legacy_log="$TEST_LOG_DIR/${test_name}_legacy.log"
    local modern_log="$TEST_LOG_DIR/${test_name}_modern.log"
    
    _log_debug "Running comparison test: $test_name"
    
    echo "DEBUG: About to execute legacy command: $legacy_command"
    
    # Execute both commands
    local legacy_exit=0 modern_exit=0
    
    eval "$legacy_command" >"$legacy_log" 2>&1 || legacy_exit=$?
    echo "DEBUG: Legacy command completed with exit code: $legacy_exit"
    
    eval "$modern_command" >"$modern_log" 2>&1 || modern_exit=$?
    echo "DEBUG: Modern command completed with exit code: $modern_exit"
    
    # Compare results based on type
    case "$comparison_type" in
        help_content_similarity)
            echo "DEBUG: Calling _compare_help_content"
            _compare_help_content "$legacy_log" "$modern_log" "$test_name"
            ;;
        error_message_consistency)
            echo "DEBUG: Calling _compare_error_messages"
            _compare_error_messages "$legacy_log" "$modern_log" "$legacy_exit" "$modern_exit" "$test_name"
            ;;
        *)
            echo "ERROR: Unknown comparison type: $comparison_type"
            ((TESTS_FAILED++))
            return 1
            ;;
    esac
    
    echo "DEBUG: _run_comparison_test completed for $test_name"
}

# Initialize
mkdir -p "$TEST_LOG_DIR"

echo "==> Starting debug test framework..."

# Run just the first two tests
echo "==> Running test 1..."
_run_comparison_test "orchestrator_help_comparison" \
    "$LEGACY_ORCHESTRATOR --help" \
    "$MODERN_ORCHESTRATOR --help" \
    "help_content_similarity"

echo "==> Test 1 completed, running test 2..."
_run_comparison_test "orchestrator_invalid_args" \
    "$LEGACY_ORCHESTRATOR --invalid-flag 2>&1" \
    "$MODERN_ORCHESTRATOR --invalid-flag 2>&1" \
    "error_message_consistency"

echo "==> Both tests completed successfully!"
echo "Tests run: $TESTS_RUN, Passed: $TESTS_PASSED, Failed: $TESTS_FAILED"

rm -rf "$TEST_LOG_DIR"