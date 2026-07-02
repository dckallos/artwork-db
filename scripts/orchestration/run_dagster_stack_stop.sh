#!/usr/bin/env bash
# =============================================================================
# run_dagster_stack_stop.sh -- stop the background stack started by run_dagster_stack.sh.
# =============================================================================
# Reads the PID files written under $DAGSTER_HOME, terminates the webserver and
# daemon (SIGTERM, then SIGKILL if they linger), and removes the PID files.
#
# Usage:
#   scripts/orchestration/run_dagster_stack_stop.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=_dagster_env.sh
source "$SCRIPT_DIR/_dagster_env.sh"

log() { echo "==> [dagster-stack-stop] $*"; }

# Resolve DAGSTER_HOME the same way the launcher does (no seeding needed to stop).
export DAGSTER_HOME="${DAGSTER_HOME:-$REPO_ROOT/orchestration/dagster_home}"
WEB_PID_FILE="$DAGSTER_HOME/webserver.pid"
DAEMON_PID_FILE="$DAGSTER_HOME/daemon.pid"

stop_one() {
  local name="$1" pid_file="$2" pid
  if [[ ! -f "$pid_file" ]]; then
    log "$name: no PID file ($pid_file); skipping"
    return
  fi
  pid="$(cat "$pid_file")"
  if ! kill -0 "$pid" 2>/dev/null; then
    log "$name: PID $pid not running; removing stale $pid_file"
    rm -f "$pid_file"
    return
  fi
  log "$name: sending SIGTERM to PID $pid"
  kill "$pid" 2>/dev/null || true
  # Give it a few seconds to shut down cleanly, then force-kill.
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    kill -0 "$pid" 2>/dev/null || break
    sleep 1
  done
  if kill -0 "$pid" 2>/dev/null; then
    log "$name: still alive; sending SIGKILL to PID $pid"
    kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$pid_file"
  log "$name: stopped"
}

# Stop the webserver first (front door), then the daemon.
stop_one "webserver" "$WEB_PID_FILE"
stop_one "daemon" "$DAEMON_PID_FILE"
log "Done."
