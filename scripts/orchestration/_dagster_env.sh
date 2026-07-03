# shellcheck shell=bash
# =============================================================================
# _dagster_env.sh -- shared environment setup for the split Dagster launchers.
# =============================================================================
# Sourced by run_dagster_webserver.sh and run_dagster_daemon.sh so that
# DAGSTER_HOME resolution, config/workspace seeding, .env sourcing, and venv
# activation stay byte-for-byte identical across both processes (they must share
# one instance to share the run queue + storage).
#
# This file is meant to be `source`d, not executed directly:
#   SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
#   source "$SCRIPT_DIR/_dagster_env.sh"
#   dagster_env_setup
#
# After dagster_env_setup runs, these are available to the caller:
#   REPO_ROOT, VENV, DBT_PROJECT_DIR, DBT_MANIFEST_PATH, DAGSTER_HOME (exported)
# Provided functions: dagster_env_setup, dagster_dbt_parse, detect_lan_ip,
#                      list_lan_ip_candidates
# =============================================================================

# Resolve this helper's own location so paths hold regardless of the caller's CWD.
_DAGSTER_ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$_DAGSTER_ENV_DIR/../.." && pwd)"
VENV="$REPO_ROOT/.venv"
DBT_PROJECT_DIR="$REPO_ROOT/artwork_pipeline"
# The compiled manifest is always <project>/target/manifest.json (see dbt_manifest.py).
DBT_MANIFEST_PATH="$DBT_PROJECT_DIR/target/manifest.json"

_env_log() { echo "==> [dagster-env] $*"; }

# Prepare DAGSTER_HOME, seed instance + workspace config, source .env, activate venv.
dagster_env_setup() {
  cd "$REPO_ROOT"

  # Persistent instance home (SQLite storage + run queue live here). Both the
  # webserver and daemon MUST point at the same DAGSTER_HOME.
  export DAGSTER_HOME="${DAGSTER_HOME:-$REPO_ROOT/orchestration/dagster_home}"
  mkdir -p "$DAGSTER_HOME"

  if [[ ! -f "$DAGSTER_HOME/dagster.yaml" ]]; then
    _env_log "Seeding $DAGSTER_HOME/dagster.yaml from example"
    cp "$REPO_ROOT/orchestration/dagster_home/dagster.yaml.example" "$DAGSTER_HOME/dagster.yaml"
  fi

  # dagster-webserver and dagster-daemon both discover the code location from a
  # workspace file (unlike `dagster dev -m`, which takes the module directly).
  # Seed it and pass it explicitly with -w from each launcher.
  if [[ ! -f "$DAGSTER_HOME/workspace.yaml" ]]; then
    _env_log "Seeding $DAGSTER_HOME/workspace.yaml from example"
    cp "$REPO_ROOT/orchestration/dagster_home/workspace.yaml.example" "$DAGSTER_HOME/workspace.yaml"
  fi

  # Load Snowflake / dbt env vars if present (dbt dev target uses key-pair auth).
  if [[ -f "$REPO_ROOT/.env" ]]; then
    _env_log "Sourcing .env"
    set -a; source "$REPO_ROOT/.env"; set +a
  else
    _env_log "WARNING: no .env found; dbt runs will fail without SNOWFLAKE_* vars."
  fi

  if [[ -d "$VENV" ]]; then
    # shellcheck disable=SC1091
    source "$VENV/bin/activate"
  fi
}

# Build the dbt manifest in this parent process. A present manifest stops each
# run-worker subprocess from re-running `dbt deps` concurrently (which races under
# dbt-fusion -> IoError dbt1001; see orchestration/.../resources.py). Also refreshes
# the manifest so dbt model edits are picked up on restart.
dagster_dbt_parse() {
  _env_log "Building dbt manifest (dbt parse)"
  dbt parse --project-dir "$DBT_PROJECT_DIR" --profiles-dir "$DBT_PROJECT_DIR" --target dev \
    || _env_log "WARNING: dbt parse failed; Dagster will try to prepare the manifest on load"
}

# Best-effort LAN IPv4 (macOS), so a launcher can print a network-reachable URL.
# Honors an explicit DAGSTER_ADVERTISE_IP override (use when auto-detection picks
# the wrong interface, e.g. VPN or Wi-Fi on en1). Prints an empty string if it
# cannot be determined.
detect_lan_ip() {
  if [[ -n "${DAGSTER_ADVERTISE_IP:-}" ]]; then
    echo "$DAGSTER_ADVERTISE_IP"
    return
  fi
  local ip=""
  if command -v ipconfig >/dev/null 2>&1; then
    ip="$(ipconfig getifaddr en0 2>/dev/null || true)"
    [[ -z "$ip" ]] && ip="$(ipconfig getifaddr en1 2>/dev/null || true)"
  fi
  echo "$ip"
}

# List every interface with a LAN IPv4 (macOS), one "  <iface>: <ip>" per line.
# Helps the user pick the right value for DAGSTER_ADVERTISE_IP when a Mac has
# several active interfaces. Prints nothing if none are found.
list_lan_ip_candidates() {
  local ifc ip
  if command -v ipconfig >/dev/null 2>&1; then
    for ifc in en0 en1 en2 en3 en4; do
      ip="$(ipconfig getifaddr "$ifc" 2>/dev/null || true)"
      [[ -n "$ip" ]] && echo "  $ifc: $ip"
    done
  fi
}
