#!/usr/bin/env bash
# =============================================================================
# doctor_orchestration.sh -- sanity-check the local orchestration setup.
# =============================================================================
# Non-destructive. Verifies the venv, key tools, dbt connectivity, the dbt
# manifest, and that the Dagster definitions import cleanly.
#
# Usage: scripts/orchestration/doctor_orchestration.sh
# =============================================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VENV="$REPO_ROOT/.venv"
DBT_DIR="$REPO_ROOT/artwork_pipeline"

ok()   { echo "  [ok]   $*"; }
warn() { echo "  [warn] $*"; }
bad()  { echo "  [FAIL] $*"; FAILED=1; }
FAILED=0

cd "$REPO_ROOT"
[[ -d "$VENV" ]] && { source "$VENV/bin/activate"; ok "venv active: $VENV"; } || warn "no venv at $VENV (run bootstrap_dagster.sh)"

echo "Tools:"
command -v dbt     >/dev/null 2>&1 && ok "dbt: $(dbt --version 2>/dev/null | head -1)" || bad "dbt not found"
command -v dagster >/dev/null 2>&1 && ok "dagster present"                             || bad "dagster not found"

echo "dbt project:"
[[ -f "$DBT_DIR/target/manifest.json" ]] && ok "manifest.json present" || warn "manifest missing (run: dbt parse)"
if [[ -f "$REPO_ROOT/.env" ]]; then
  set -a; source "$REPO_ROOT/.env"; set +a
  dbt debug --project-dir "$DBT_DIR" --profiles-dir "$DBT_DIR" --target dev >/dev/null 2>&1 \
    && ok "dbt debug (dev target) connected" || warn "dbt debug failed (check .env / key-pair)"
else
  warn "no .env; skipping dbt debug"
fi

echo "Dagster definitions:"
python -c "import artwork_orchestration.definitions as d; print('   assets:', len(d.defs.get_asset_graph().all_asset_keys))" 2>/dev/null \
  && ok "definitions import cleanly" || bad "failed to import artwork_orchestration.definitions"

echo ""
[[ "$FAILED" -eq 0 ]] && echo "doctor: PASS" || { echo "doctor: FAIL (see above)"; exit 1; }
