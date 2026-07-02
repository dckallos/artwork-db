#!/usr/bin/env bash
# =============================================================================
# ci_local.sh -- The single source of truth for CI checks (checks-only).
# =============================================================================
# Runs the exact same steps locally that .github/workflows/ci.yml runs on a PR.
# Scope (deliberately): compile + lint + unit tests. It does NOT run a full
# `dbt build`, because there is no dev/prod isolation yet -- a full build would
# write to the real SILVER/GOLD schemas. These checks require NO Bronze data.
#
# Usage:
#   scripts/ci/ci_local.sh                 # run all checks
#   DBT_TARGET=dev scripts/ci/ci_local.sh  # pick a profiles.yml target
#
# Exit non-zero on the first failing step.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DBT_DIR="$REPO_ROOT/artwork_pipeline"
DBT_TARGET="${DBT_TARGET:-dev}"

log()  { echo "==> [ci] $*"; }
fail() { echo "FAIL: $*" >&2; exit 1; }

cd "$REPO_ROOT"

# ---- 1. dbt deps (install packages referenced by packages.yml) --------------
log "1/5 dbt deps"
dbt deps --project-dir "$DBT_DIR" --profiles-dir "$DBT_DIR" \
  || fail "dbt deps failed"

# ---- 2. dbt parse (validates project structure, refs, macros, YAML) ---------
log "2/5 dbt parse"
dbt parse --project-dir "$DBT_DIR" --profiles-dir "$DBT_DIR" --target "$DBT_TARGET" \
  || fail "dbt parse failed (structural / ref / macro error)"

# ---- 3. sqlfluff lint (style + obvious SQL errors) --------------------------
log "3/5 sqlfluff lint"
if command -v sqlfluff >/dev/null 2>&1; then
  sqlfluff lint "$DBT_DIR/models" || fail "sqlfluff lint found violations"
else
  log "sqlfluff not installed; skipping (pip install sqlfluff sqlfluff-templater-dbt)"
fi

# ---- 4. dbt compile (renders every model to SQL against warehouse metadata) -
# Compile does not execute models or touch data; it validates that SQL is
# well-formed and that contracts are structurally satisfiable.
log "4/5 dbt compile"
dbt compile --project-dir "$DBT_DIR" --profiles-dir "$DBT_DIR" --target "$DBT_TARGET" \
  || fail "dbt compile failed"

# ---- 5. dbt unit tests (mock-input logic tests; no Bronze data needed) -------
# --empty builds zero-row parents so unit tests run without real data or cost.
log "5/5 dbt unit tests"
dbt build --project-dir "$DBT_DIR" --profiles-dir "$DBT_DIR" --target "$DBT_TARGET" \
  --select "unit_test:*" --empty \
  || fail "dbt unit tests failed"

log "All CI checks passed."
