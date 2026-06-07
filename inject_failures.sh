#!/usr/bin/env bash
# =============================================================================
# inject_failures.sh -- End-to-end fixture generation for dbt-diagnostics
# =============================================================================
# Injects a failure, runs dbt to trigger it, captures the artifacts, and reverts.
#
# Usage:
#   ./inject_failures.sh 3              # Run scenario 3, save fixture
#   ./inject_failures.sh 3 --dry-run    # Show what would happen without executing
#   ./inject_failures.sh --all          # Run ALL scenarios sequentially
#   ./inject_failures.sh --all --dry-run
#   ./inject_failures.sh --list         # List all scenarios
#
# Prerequisites:
#   - Run from the repo root (where artwork_pipeline/ and inject_failures.py live)
#   - dbt venv activated (dbt command available)
#   - Snowflake connection configured (profiles.yml / env vars)
#
# Compatible with bash 3.2+ (macOS default) -- no associative arrays.
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INJECT_PY="${SCRIPT_DIR}/inject_failures.py"
DBT_PROJECT="${SCRIPT_DIR}/artwork_pipeline"
FIXTURES_DIR="${SCRIPT_DIR}/dbt_diagnostics/fixtures"

ALL_SCENARIOS="1 2 3 4 5 6 7 8 9 10 11 12"

# ---------------------------------------------------------------------------
# Lookup functions (bash 3.2 compatible -- no associative arrays)
# ---------------------------------------------------------------------------

fixture_name() {
    case "$1" in
        1)  echo "real_compilation_source_not_found" ;;
        2)  echo "real_compilation_ref_not_found" ;;
        3)  echo "real_syntax_error_001003" ;;
        4)  echo "real_division_by_zero_100035" ;;
        5)  echo "real_numeric_overflow_100132" ;;
        6)  echo "real_string_too_long_100078" ;;
        7)  echo "real_object_not_exist_002003" ;;
        8)  echo "real_privileges_003001" ;;
        9)  echo "real_invalid_identifier_000904" ;;
        10) echo "real_invalid_identifier_lateral_000904" ;;
        11) echo "real_contract_violation_extra_column" ;;
        12) echo "real_schema_change_missing_column" ;;
        *)  echo "" ;;
    esac
}

trigger_cmd() {
    case "$1" in
        1)  echo "dbt compile --select stg_met__artworks" ;;
        2)  echo "dbt compile --select stg_met__artists" ;;
        3)  echo "dbt run --select stg_met__images" ;;
        4)  echo "dbt run --select stg_met__images" ;;
        5)  echo "dbt run --select stg_met__artworks" ;;
        6)  echo "dbt run --select stg_met__artworks" ;;
        7)  echo "dbt run --select stg_met__artworks" ;;
        8)  echo "dbt run --select stg_met__enrichment_status" ;;
        9)  echo "dbt run --select stg_met__artworks" ;;
        10) echo "dbt run --select stg_met__artists" ;;
        11) echo "dbt run --select stg_met__artworks+" ;;
        12) echo "dbt run --select stg_met__artworks" ;;
        *)  echo "" ;;
    esac
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

usage() {
    echo "Usage: $0 <scenario_number> [--dry-run]"
    echo "       $0 --all [--dry-run]"
    echo "       $0 --list"
    echo ""
    echo "Runs the full inject -> trigger -> capture -> revert cycle."
    echo ""
    echo "Options:"
    echo "  <N>         Run a single scenario (1-12)"
    echo "  --all       Run ALL scenarios sequentially"
    echo "  --dry-run   Print commands without executing (works with <N> or --all)"
    echo "  --list      Show available scenarios (delegates to inject_failures.py)"
    echo ""
    echo "Output: dbt_diagnostics/fixtures/<fixture_name>.json"
}

die() {
    echo "ERROR: $1" >&2
    exit 1
}

# ---------------------------------------------------------------------------
# Run one scenario (core logic)
# ---------------------------------------------------------------------------

run_scenario() {
    local scenario="$1"
    local dry_run="$2"

    local name
    name="$(fixture_name "$scenario")"
    if [ -z "$name" ]; then
        echo "WARNING: Unknown scenario $scenario, skipping." >&2
        return 1
    fi

    local cmd
    cmd="$(trigger_cmd "$scenario")"
    local fixture_file="${FIXTURES_DIR}/${name}.json"

    echo ""
    echo "============================================================"
    echo "  Scenario $scenario: $name"
    echo "  Trigger:  $cmd"
    echo "  Output:   $fixture_file"
    echo "============================================================"
    echo ""

    if [ "$dry_run" = "true" ]; then
        echo "[dry-run] python3 $INJECT_PY --change $scenario"
        echo "[dry-run] cd $DBT_PROJECT && $cmd"
        echo "[dry-run] cp $DBT_PROJECT/target/run_results.json $fixture_file"
        echo "[dry-run] cp $DBT_PROJECT/target/manifest.json ${FIXTURES_DIR}/${name}_manifest.json"
        echo "[dry-run] python3 $INJECT_PY --discard-change $scenario"
        return 0
    fi

    # Step 1: Inject
    echo ">>> Step 1/4: Injecting failure..."
    python3 "$INJECT_PY" --change "$scenario"
    echo ""

    # Step 2: Trigger the failure via dbt
    echo ">>> Step 2/4: Running dbt to trigger the failure..."
    echo "    (Failures are expected -- that's the point)"
    echo ""
    set +e
    (cd "$DBT_PROJECT" && eval "$cmd")
    local dbt_exit=$?
    set -e
    echo ""
    echo "    dbt exited with code $dbt_exit"
    echo ""

    # Step 3: Capture artifacts
    echo ">>> Step 3/4: Capturing artifacts..."
    local run_results="$DBT_PROJECT/target/run_results.json"
    local manifest="$DBT_PROJECT/target/manifest.json"

    if [ -f "$run_results" ]; then
        cp "$run_results" "$fixture_file"
        echo "    Saved: $fixture_file"
    else
        echo "    WARNING: run_results.json not found (compile-only failures don't produce it)"
        if [ $dbt_exit -ne 0 ]; then
            echo "    dbt failed (exit $dbt_exit) but no run_results.json was produced."
            echo "    This is expected for compilation errors (scenarios 1-2)."
        fi
    fi

    if [ -f "$manifest" ]; then
        cp "$manifest" "${FIXTURES_DIR}/${name}_manifest.json"
        echo "    Saved: ${name}_manifest.json"
    fi
    echo ""

    # Step 4: Revert
    echo ">>> Step 4/4: Reverting injection..."
    python3 "$INJECT_PY" --discard-change "$scenario"
    echo ""

    echo "  DONE scenario $scenario."
    if [ -f "$fixture_file" ]; then
        echo "  File: $fixture_file ($(wc -c < "$fixture_file") bytes)"
    fi
    return 0
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

# Handle --list
if [ "${1:-}" = "--list" ]; then
    python3 "$INJECT_PY" --list
    exit 0
fi

# Handle no args
if [ $# -lt 1 ]; then
    usage
    exit 1
fi

# Parse flags
DRY_RUN=false
RUN_ALL=false
SCENARIO_NUM=""

for arg in "$@"; do
    case "$arg" in
        --all) RUN_ALL=true ;;
        --dry-run) DRY_RUN=true ;;
        --list) python3 "$INJECT_PY" --list; exit 0 ;;
        --help|-h) usage; exit 0 ;;
        [0-9]*) SCENARIO_NUM="$arg" ;;
    esac
done

# Preflight checks (skip for dry-run)
if [ "$DRY_RUN" = "false" ]; then
    [ -f "$INJECT_PY" ] || die "inject_failures.py not found at $INJECT_PY"
    [ -d "$DBT_PROJECT" ] || die "artwork_pipeline/ not found at $DBT_PROJECT"
    command -v dbt >/dev/null 2>&1 || die "dbt command not found. Activate your venv."
    mkdir -p "$FIXTURES_DIR"
fi

if [ "$RUN_ALL" = "true" ]; then
    echo "============================================================"
    echo "  RUNNING ALL 12 SCENARIOS"
    echo "============================================================"

    PASSED=0
    FAILED=0

    for scenario in $ALL_SCENARIOS; do
        if run_scenario "$scenario" "$DRY_RUN"; then
            PASSED=$((PASSED + 1))
        else
            FAILED=$((FAILED + 1))
        fi
    done

    echo ""
    echo "============================================================"
    echo "  ALL SCENARIOS COMPLETE"
    echo "  Passed: $PASSED  Failed/Skipped: $FAILED"
    echo "============================================================"
    echo ""
    echo "Fixtures saved to: $FIXTURES_DIR/"
    if [ "$DRY_RUN" = "false" ]; then
        echo ""
        echo "Files generated:"
        ls -1 "$FIXTURES_DIR"/real_*.json 2>/dev/null || echo "  (none)"
    fi
else
    if [ -z "$SCENARIO_NUM" ]; then
        die "No scenario number provided. Use --all or pass a number (1-12)."
    fi

    name="$(fixture_name "$SCENARIO_NUM")"
    if [ -z "$name" ]; then
        die "Unknown scenario: $SCENARIO_NUM. Valid: 1-12. Run '$0 --list' to see all."
    fi

    run_scenario "$SCENARIO_NUM" "$DRY_RUN"
fi
