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
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INJECT_PY="${SCRIPT_DIR}/inject_failures.py"
DBT_PROJECT="${SCRIPT_DIR}/artwork_pipeline"
FIXTURES_DIR="${SCRIPT_DIR}/dbt_diagnostics/fixtures"

# Fixture naming map: scenario number -> output filename
declare -A FIXTURE_NAMES=(
    [1]="real_compilation_source_not_found"
    [2]="real_compilation_ref_not_found"
    [3]="real_syntax_error_001003"
    [4]="real_division_by_zero_100035"
    [5]="real_numeric_overflow_100132"
    [6]="real_string_too_long_100078"
    [7]="real_object_not_exist_002003"
    [8]="real_privileges_003001"
    [9]="real_invalid_identifier_000904"
    [10]="real_invalid_identifier_lateral_000904"
    [11]="real_contract_violation_extra_column"
    [12]="real_schema_change_missing_column"
)

# dbt trigger command per scenario (must match inject_failures.py trigger_cmd)
declare -A TRIGGER_CMDS=(
    [1]="dbt compile --select stg_met__artworks"
    [2]="dbt compile --select stg_met__artists"
    [3]="dbt run --select stg_met__images"
    [4]="dbt run --select stg_met__images"
    [5]="dbt run --select stg_met__artworks"
    [6]="dbt run --select stg_met__artworks"
    [7]="dbt run --select stg_met__artworks"
    [8]="dbt run --select stg_met__enrichment_status"
    [9]="dbt run --select stg_met__artworks"
    [10]="dbt run --select stg_met__artists"
    [11]="dbt run --select stg_met__artworks+"
    [12]="dbt run --select stg_met__artworks"
)

# Conflict groups: scenarios sharing the same file cannot run back-to-back
# without a clean state. The sequential loop handles this by reverting each
# before moving to the next, so conflicts are not an issue in --all mode.

ALL_SCENARIOS=(1 2 3 4 5 6 7 8 9 10 11 12)

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
    echo "  --all       Run ALL scenarios sequentially (inject, trigger, capture, revert each)"
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
    local SCENARIO="$1"
    local DRY_RUN="$2"

    # Validate scenario number
    if [[ -z "${FIXTURE_NAMES[$SCENARIO]+x}" ]]; then
        echo "WARNING: Unknown scenario $SCENARIO, skipping." >&2
        return 1
    fi

    local FIXTURE_FILE="${FIXTURES_DIR}/${FIXTURE_NAMES[$SCENARIO]}.json"
    local TRIGGER_CMD="${TRIGGER_CMDS[$SCENARIO]}"

    echo ""
    echo "============================================================"
    echo "  Scenario $SCENARIO: ${FIXTURE_NAMES[$SCENARIO]}"
    echo "  Trigger:  $TRIGGER_CMD"
    echo "  Output:   $FIXTURE_FILE"
    echo "============================================================"
    echo ""

    if $DRY_RUN; then
        echo "[dry-run] python3 $INJECT_PY --change $SCENARIO"
        echo "[dry-run] cd $DBT_PROJECT && $TRIGGER_CMD"
        echo "[dry-run] cp $DBT_PROJECT/target/run_results.json $FIXTURE_FILE"
        echo "[dry-run] cp $DBT_PROJECT/target/manifest.json ${FIXTURES_DIR}/${FIXTURE_NAMES[$SCENARIO]}_manifest.json"
        echo "[dry-run] python3 $INJECT_PY --discard-change $SCENARIO"
        return 0
    fi

    # Step 1: Inject
    echo ">>> Step 1/4: Injecting failure..."
    python3 "$INJECT_PY" --change "$SCENARIO"
    echo ""

    # Step 2: Trigger the failure via dbt
    echo ">>> Step 2/4: Running dbt to trigger the failure..."
    echo "    (Failures are expected -- that's the point)"
    echo ""
    set +e
    (cd "$DBT_PROJECT" && $TRIGGER_CMD)
    local DBT_EXIT=$?
    set -e
    echo ""
    echo "    dbt exited with code $DBT_EXIT"
    echo ""

    # Step 3: Capture artifacts
    echo ">>> Step 3/4: Capturing artifacts..."
    local RUN_RESULTS="$DBT_PROJECT/target/run_results.json"
    local MANIFEST="$DBT_PROJECT/target/manifest.json"

    if [[ -f "$RUN_RESULTS" ]]; then
        cp "$RUN_RESULTS" "$FIXTURE_FILE"
        echo "    Saved: $FIXTURE_FILE"
    else
        echo "    WARNING: run_results.json not found (compile-only failures don't produce it)"
        if [[ $DBT_EXIT -ne 0 ]]; then
            echo "    dbt failed (exit $DBT_EXIT) but no run_results.json was produced."
            echo "    This is expected for compilation errors (scenarios 1-2)."
        fi
    fi

    if [[ -f "$MANIFEST" ]]; then
        cp "$MANIFEST" "${FIXTURES_DIR}/${FIXTURE_NAMES[$SCENARIO]}_manifest.json"
        echo "    Saved: ${FIXTURE_NAMES[$SCENARIO]}_manifest.json"
    fi
    echo ""

    # Step 4: Revert
    echo ">>> Step 4/4: Reverting injection..."
    python3 "$INJECT_PY" --discard-change "$SCENARIO"
    echo ""

    echo "  DONE scenario $SCENARIO."
    if [[ -f "$FIXTURE_FILE" ]]; then
        echo "  File: $FIXTURE_FILE ($(wc -c < "$FIXTURE_FILE") bytes)"
    fi
    return 0
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

# Handle --list
if [[ "${1:-}" == "--list" ]]; then
    python3 "$INJECT_PY" --list
    exit 0
fi

# Handle no args
if [[ $# -lt 1 ]]; then
    usage
    exit 1
fi

# Determine mode
DRY_RUN=false
RUN_ALL=false

for arg in "$@"; do
    case "$arg" in
        --all) RUN_ALL=true ;;
        --dry-run) DRY_RUN=true ;;
        --list) python3 "$INJECT_PY" --list; exit 0 ;;
        --help|-h) usage; exit 0 ;;
        *) ;; # scenario number handled below
    esac
done

# Preflight checks (skip for dry-run)
if ! $DRY_RUN; then
    [[ -f "$INJECT_PY" ]] || die "inject_failures.py not found at $INJECT_PY"
    [[ -d "$DBT_PROJECT" ]] || die "artwork_pipeline/ not found at $DBT_PROJECT"
    command -v dbt >/dev/null 2>&1 || die "dbt command not found. Activate your venv."
    mkdir -p "$FIXTURES_DIR"
fi

if $RUN_ALL; then
    # Run every scenario sequentially
    echo "============================================================"
    echo "  RUNNING ALL ${#ALL_SCENARIOS[@]} SCENARIOS"
    echo "============================================================"

    PASSED=0
    FAILED=0
    SKIPPED=0
    declare -a RESULTS=()

    for SCENARIO in "${ALL_SCENARIOS[@]}"; do
        if run_scenario "$SCENARIO" "$DRY_RUN"; then
            RESULTS+=("  [$SCENARIO] OK: ${FIXTURE_NAMES[$SCENARIO]}")
            PASSED=$((PASSED + 1))
        else
            RESULTS+=("  [$SCENARIO] SKIP/FAIL: ${FIXTURE_NAMES[$SCENARIO]}")
            FAILED=$((FAILED + 1))
        fi
    done

    echo ""
    echo "============================================================"
    echo "  ALL SCENARIOS COMPLETE"
    echo "  Passed: $PASSED  Failed/Skipped: $FAILED"
    echo "============================================================"
    echo ""
    echo "Results:"
    for line in "${RESULTS[@]}"; do
        echo "$line"
    done
    echo ""
    echo "Fixtures saved to: $FIXTURES_DIR/"
    if ! $DRY_RUN; then
        echo ""
        echo "Files generated:"
        ls -1 "$FIXTURES_DIR"/real_*.json 2>/dev/null || echo "  (none)"
    fi
else
    # Single scenario mode: first non-flag argument is the scenario number
    SCENARIO=""
    for arg in "$@"; do
        case "$arg" in
            --*) ;; # skip flags
            *) SCENARIO="$arg"; break ;;
        esac
    done

    if [[ -z "$SCENARIO" ]]; then
        die "No scenario number provided. Use --all or pass a number (1-12)."
    fi

    if [[ -z "${FIXTURE_NAMES[$SCENARIO]+x}" ]]; then
        die "Unknown scenario: $SCENARIO. Valid: 1-12. Run '$0 --list' to see all."
    fi

    run_scenario "$SCENARIO" "$DRY_RUN"
fi
