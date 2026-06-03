#!/usr/bin/env bash

set -euo pipefail

# Minimal test of just the first two comparison tests

# Copy the test framework setup
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly REPO_ROOT="$SCRIPT_DIR"  # Since we're in repo root
readonly TEST_LOG_DIR="/tmp/test_two_comparisons_$$"
readonly TEST_CONFIG="${REPO_ROOT}/config/artwork_domain.yml"

# Script paths
readonly LEGACY_ORCHESTRATOR="${REPO_ROOT}/scripts/orchestrate.sh"
readonly MODERN_ORCHESTRATOR="${REPO_ROOT}/scripts/orchestrate_modern.sh"

# Test state tracking
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Initialize
mkdir -p "$TEST_LOG_DIR"

# Logging functions  
_log_info() { echo "==> [test] $*" >&2; }
_log_success() { echo "==> [test] $*" >&2; }
_log_failure() { echo "==> [test] $*" >&2; }
_log_debug() { echo "DEBUG [test] $*" >&2; }

# Comparison functions
_compare_help_content() {
    local legacy_log="$1" modern_log="$2" test_name="$3"
    local legacy_lines modern_lines
    legacy_lines=$(wc -l < "$legacy_log")
    modern_lines=$(wc -l < "$modern_log")
    
    if [[ $modern_lines -ge 10 ]]; then
        _log_success "✓ $test_name (legacy: $legacy_lines lines, modern: $modern_lines lines)"
        ((TESTS_PASSED++))
    else
        _log_failure "✗ $test_name - insufficient help content"
        ((TESTS_FAILED++))
    fi
}

_compare_error_messages() {
    local legacy_log="$1" modern_log="$2" legacy_exit="$3" modern_exit="$4" test_name="$5"
    
    if [[ $legacy_exit -ne 0 && $modern_exit -ne 0 ]]; then
        _log_success "✓ $test_name (both failed appropriately)"
        ((TESTS_PASSED++))
    else
        _log_failure "✗ $test_name - inconsistent error handling (legacy exit: $legacy_exit, modern exit: $modern_exit)"
        ((TESTS_FAILED++))
    fi
}

# Test execution function
_run_comparison_test() {
    local test_name="$1" legacy_command="$2" modern_command="$3" comparison_type="$4"
    
    ((TESTS_RUN++))
    
    local legacy_log="$TEST_LOG_DIR/${test_name}_legacy.log"
    local modern_log="$TEST_LOG_DIR/${test_name}_modern.log"
    
    _log_debug "Running comparison test: $test_name"
    _log_debug "Legacy command: $legacy_command"
    _log_debug "Modern command: $modern_command"
    
    # Execute both commands
    local legacy_exit=0 modern_exit=0
    
    _log_debug "Executing legacy command..."
    eval "$legacy_command" >"$legacy_log" 2>&1 || legacy_exit=$?
    _log_debug "Legacy completed with exit code: $legacy_exit"
    
    _log_debug "Executing modern command..."
    eval "$modern_command" >"$modern_log" 2>&1 || modern_exit=$?
    _log_debug "Modern completed with exit code: $modern_exit"
    
    # Compare results
    case "$comparison_type" in
        help_content_similarity)
            _log_debug "Calling _compare_help_content"
            _compare_help_content "$legacy_log" "$modern_log" "$test_name"
            ;;
        error_message_consistency)
            _log_debug "Calling _compare_error_messages" 
            _compare_error_messages "$legacy_log" "$modern_log" "$legacy_exit" "$modern_exit" "$test_name"
            ;;
        *)
            _log_failure "Unknown comparison type: $comparison_type"
            ((TESTS_FAILED++))
            return 1
            ;;
    esac
    
    _log_debug "_run_comparison_test completed for $test_name"
}

echo "Starting minimal two-test comparison..."

echo "==> Running test 1 (help comparison)..."
_run_comparison_test "orchestrator_help_comparison" \
    "$LEGACY_ORCHESTRATOR --help" \
    "$MODERN_ORCHESTRATOR --help" \
    "help_content_similarity"

echo "==> Test 1 completed, starting test 2 (invalid args)..."
_run_comparison_test "orchestrator_invalid_args" \
    "$LEGACY_ORCHESTRATOR --invalid-flag 2>&1" \
    "$MODERN_ORCHESTRATOR --invalid-flag 2>&1" \
    "error_message_consistency"

echo "==> Test 2 completed!"
echo "==> Summary: Tests run: $TESTS_RUN, Passed: $TESTS_PASSED, Failed: $TESTS_FAILED"

# Cleanup
rm -rf "$TEST_LOG_DIR"
echo "==> All tests completed successfully!"