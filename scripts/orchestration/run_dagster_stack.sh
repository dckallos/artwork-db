#!/usr/bin/env bash
# =============================================================================
# run_dagster_stack.sh -- start webserver + daemon together in ONE terminal.
# =============================================================================
# Convenience launcher for the production-style split: starts both the LAN
# webserver and the daemon as BACKGROUND processes, then returns your prompt.
# Logs and PID files land in $DAGSTER_HOME/logs so you can close the terminal
# and the stack keeps running. Stop it with run_dagster_stack_stop.sh.
#
# For a foreground, one-Ctrl-C experience use the two per-process scripts in
# separate tabs instead (run_dagster_webserver.sh + run_dagster_daemon.sh).
#
# Usage:
#   scripts/orchestration/run_dagster_stack.sh
# Same overrides as the webserver script:
#   DAGSTER_WEBSERVER_HOST / DAGSTER_WEBSERVER_PORT / DAGSTER_ADVERTISE_IP
#
# SECURITY: binding 0.0.0.0 exposes an UNAUTHENTICATED UI to the whole LAN.
# Only run this on a trusted network.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=_dagster_env.sh
source "$SCRIPT_DIR/_dagster_env.sh"

log() { echo "==> [dagster-stack] $*"; }

dagster_env_setup

LOG_DIR="$DAGSTER_HOME/logs"
mkdir -p "$LOG_DIR"
WEB_PID_FILE="$DAGSTER_HOME/webserver.pid"
DAEMON_PID_FILE="$DAGSTER_HOME/daemon.pid"

# Refuse to double-start: a live PID in either file means the stack is running.
for f in "$WEB_PID_FILE" "$DAEMON_PID_FILE"; do
  if [[ -f "$f" ]] && kill -0 "$(cat "$f")" 2>/dev/null; then
    log "ERROR: already running (PID $(cat "$f") in $f). Stop it first with run_dagster_stack_stop.sh"
    exit 1
  fi
done

# Build the manifest ONCE here (authoritative), so neither background child races
# the other on `dbt parse` (see resources.py dbt-fusion note).
dagster_dbt_parse

HOST="${DAGSTER_WEBSERVER_HOST:-0.0.0.0}"
PORT="${DAGSTER_WEBSERVER_PORT:-3000}"
WORKSPACE="$DAGSTER_HOME/workspace.yaml"

# Only ONE daemon per deployment; start it first so queued runs can launch.
log "Starting daemon -> $LOG_DIR/daemon.log"
dagster-daemon run -w "$WORKSPACE" >"$LOG_DIR/daemon.log" 2>&1 &
echo $! >"$DAEMON_PID_FILE"

log "Starting webserver on $HOST:$PORT -> $LOG_DIR/webserver.log"
dagster-webserver -h "$HOST" -p "$PORT" -w "$WORKSPACE" >"$LOG_DIR/webserver.log" 2>&1 &
echo $! >"$WEB_PID_FILE"

log "DAGSTER_HOME=$DAGSTER_HOME"
log "daemon PID=$(cat "$DAEMON_PID_FILE")  webserver PID=$(cat "$WEB_PID_FILE")"

LAN_IP="$(detect_lan_ip)"
if [[ -n "$LAN_IP" ]]; then
  log "Open from another Mac: http://$LAN_IP:$PORT   (local: http://localhost:$PORT)"
else
  log "UI on http://$HOST:$PORT  (could not auto-detect LAN IP)"
fi
CANDIDATES="$(list_lan_ip_candidates)"
if [[ -n "$CANDIDATES" ]]; then
  log "LAN IPv4 candidates (set DAGSTER_ADVERTISE_IP to pin one):"
  echo "$CANDIDATES"
fi

log "Tail logs:  tail -f \"$LOG_DIR/webserver.log\" \"$LOG_DIR/daemon.log\""
log "Stop both:  scripts/orchestration/run_dagster_stack_stop.sh"
