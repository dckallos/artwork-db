#!/usr/bin/env bash
# =============================================================================
# run_dagster_dev.sh -- launch the local Dagster UI + daemon (`dagster dev`).
# =============================================================================
# Persists run history to a repo-local DAGSTER_HOME so it survives restarts
# (default `dagster dev` uses a temp dir that is wiped). Sources .env so dbt's
# key-pair env vars are available to the dbt CLI resource.
#
# Usage: scripts/orchestration/run_dagster_dev.sh
# Then open http://localhost:3000
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VENV="$REPO_ROOT/.venv"

log() { echo "==> [dagster-dev] $*"; }

cd "$REPO_ROOT"

# Persistent instance home (SQLite storage lives here). First run: seed config.
export DAGSTER_HOME="${DAGSTER_HOME:-$REPO_ROOT/orchestration/dagster_home}"
mkdir -p "$DAGSTER_HOME"
if [[ ! -f "$DAGSTER_HOME/dagster.yaml" ]]; then
  log "Seeding $DAGSTER_HOME/dagster.yaml from example"
  cp "$REPO_ROOT/orchestration/dagster_home/dagster.yaml.example" "$DAGSTER_HOME/dagster.yaml"
fi

# Load Snowflake / dbt env vars if present (dbt dev target uses key-pair auth).
if [[ -f "$REPO_ROOT/.env" ]]; then
  log "Sourcing .env"
  set -a; source "$REPO_ROOT/.env"; set +a
else
  log "WARNING: no .env found; dbt runs will fail without SNOWFLAKE_* vars."
fi

if [[ -d "$VENV" ]]; then
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
fi

# Build the dbt manifest ONCE here, in this single parent process, before launching
# Dagster. This is what keeps run-worker subprocesses from each re-running `dbt deps`
# concurrently (which races and, under dbt-fusion, fails with IoError dbt1001). With a
# manifest already present, resources.py skips prepare in every worker. Also refreshes the
# manifest so dbt model edits are picked up on each restart.
log "Building dbt manifest (dbt parse) once before launch"
dbt parse --project-dir "$REPO_ROOT/artwork_pipeline" --profiles-dir "$REPO_ROOT/artwork_pipeline" --target dev \
  || log "WARNING: dbt parse failed; Dagster will try to prepare the manifest on load"

log "DAGSTER_HOME=$DAGSTER_HOME"
log "Starting Dagster UI + daemon on http://localhost:3000 (Ctrl-C to stop)"
exec dagster dev -m artwork_orchestration.definitions
