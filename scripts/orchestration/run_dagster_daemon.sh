#!/usr/bin/env bash
# =============================================================================
# run_dagster_daemon.sh -- launch the Dagster daemon (run queue, schedules, sensors).
# =============================================================================
# The other half of the production-style split (pairs with run_dagster_webserver.sh).
# The daemon dequeues runs from the QueuedRunCoordinator (see dagster.yaml) and
# launches them, and it ticks schedules and sensors. Runs enqueued by the webserver
# stay QUEUED until this process is running.
#
# Only ONE daemon may run per deployment (multiple webservers are fine). It must
# share the same DAGSTER_HOME as the webserver -- the shared _dagster_env.sh helper
# guarantees that.
#
# Usage:
#   scripts/orchestration/run_dagster_daemon.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=_dagster_env.sh
source "$SCRIPT_DIR/_dagster_env.sh"

log() { echo "==> [dagster-daemon] $*"; }

dagster_env_setup

# Parse ONLY if the manifest is missing. The webserver launcher is the authoritative
# parser; two parents running `dbt parse` at once could re-introduce the dbt-fusion
# race documented in resources.py. This still keeps the daemon self-sufficient when
# started on its own.
if [[ ! -f "$DBT_MANIFEST_PATH" ]]; then
  log "dbt manifest missing at $DBT_MANIFEST_PATH -- building it"
  dagster_dbt_parse
else
  log "Reusing existing dbt manifest at $DBT_MANIFEST_PATH"
fi

log "DAGSTER_HOME=$DAGSTER_HOME"
log "Starting Dagster daemon: run queue + schedules + sensors. Ctrl-C to stop."
log "Note: run only ONE daemon per deployment."

exec dagster-daemon run -w "$DAGSTER_HOME/workspace.yaml"
