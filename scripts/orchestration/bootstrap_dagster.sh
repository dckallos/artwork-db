#!/usr/bin/env bash
# =============================================================================
# bootstrap_dagster.sh -- one-time local setup for the orchestration layer.
# =============================================================================
# Creates/uses a venv, installs the orchestration package (which pulls in
# Dagster + dagster-dbt), installs the extraction/dbt requirements, and runs
# `dbt deps` so a manifest can be generated.
#
# Usage: scripts/orchestration/bootstrap_dagster.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VENV="$REPO_ROOT/.venv"

log() { echo "==> [bootstrap] $*"; }

cd "$REPO_ROOT"

if [[ ! -d "$VENV" ]]; then
  log "Creating venv at $VENV"
  python3 -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"

log "Upgrading pip"
python -m pip install --upgrade pip

log "Installing project requirements (extraction + dbt)"
pip install -r requirements.txt

log "Installing orchestration package (Dagster + dagster-dbt, with dev/test extras)"
pip install -e "$REPO_ROOT/orchestration[dev]"

log "Installing dbt packages (dbt deps)"
dbt deps --project-dir "$REPO_ROOT/artwork_pipeline" --profiles-dir "$REPO_ROOT/artwork_pipeline"

log "Done. Next: scripts/orchestration/run_dagster_dev.sh"
