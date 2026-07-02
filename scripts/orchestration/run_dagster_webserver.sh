#!/usr/bin/env bash
# =============================================================================
# run_dagster_webserver.sh -- launch dagster-webserver on the LAN (0.0.0.0).
# =============================================================================
# Production-style split: this runs ONLY the webserver/UI, bound to 0.0.0.0 so
# the Dagster dashboard is reachable from other machines on the local network.
# Run the daemon separately (run_dagster_daemon.sh).
#
# IMPORTANT: dagster.yaml uses the QueuedRunCoordinator, so the webserver only
# ENQUEUES runs -- the daemon dequeues and launches them. Nothing executes until
# run_dagster_daemon.sh is also running.
#
# Usage:
#   scripts/orchestration/run_dagster_webserver.sh
# Override host/port (defaults 0.0.0.0:3000):
#   DAGSTER_WEBSERVER_HOST=0.0.0.0 DAGSTER_WEBSERVER_PORT=3000 \
#     scripts/orchestration/run_dagster_webserver.sh
# Pin the advertised IP if auto-detection picks the wrong interface:
#   DAGSTER_ADVERTISE_IP=192.168.1.50 scripts/orchestration/run_dagster_webserver.sh
#
# SECURITY: binding 0.0.0.0 exposes an UNAUTHENTICATED UI to the whole LAN.
# Only run this on a trusted network.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=_dagster_env.sh
source "$SCRIPT_DIR/_dagster_env.sh"

log() { echo "==> [dagster-webserver] $*"; }

dagster_env_setup

# This launcher is the authoritative manifest builder: always parse so dbt model
# edits are picked up on restart. The daemon parses only if the manifest is
# missing, so the two parent processes never run `dbt parse` at the same time.
dagster_dbt_parse

HOST="${DAGSTER_WEBSERVER_HOST:-0.0.0.0}"
PORT="${DAGSTER_WEBSERVER_PORT:-3000}"

log "DAGSTER_HOME=$DAGSTER_HOME"
LAN_IP="$(detect_lan_ip)"
if [[ -n "$LAN_IP" ]]; then
  log "Serving UI on http://$HOST:$PORT  (from other machines: http://$LAN_IP:$PORT)"
else
  log "Serving UI on http://$HOST:$PORT  (could not auto-detect LAN IP)"
fi
CANDIDATES="$(list_lan_ip_candidates)"
if [[ -n "$CANDIDATES" ]]; then
  log "LAN IPv4 candidates (set DAGSTER_ADVERTISE_IP to pin one):"
  echo "$CANDIDATES"
fi
log "Reminder: also start scripts/orchestration/run_dagster_daemon.sh, or queued runs will not launch."

exec dagster-webserver -h "$HOST" -p "$PORT" -w "$DAGSTER_HOME/workspace.yaml"
