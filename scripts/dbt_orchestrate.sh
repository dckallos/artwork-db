#!/usr/bin/env bash
# =============================================================================
# dbt_orchestrate.sh -- dbt lifecycle orchestrator for the Artwork Pipeline
# =============================================================================
# Usage: scripts/dbt_orchestrate.sh --phase <init|build|test|teardown|full-refresh>
#
# This script:
#   1. Sources .env to load all required variables
#   2. Validates that required env vars are set (fail-fast)
#   3. Exports DBT_* and SNOWFLAKE_* vars so dbt's env_var() can read them
#   4. Invokes the appropriate dbt command
#
# Designed to run on the Mac alongside the existing IaC orchestrate.sh.
# Does NOT run inside the Snowflake workspace sandbox.
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DBT_PROJECT_DIR="$REPO_ROOT/artwork_pipeline"
PROFILES_DIR="$DBT_PROJECT_DIR"

# snow CLI connection used by the teardown phase's `snow sql` calls. Defaults to
# $SNOW_CONNECTION else "admin" (same convention as scripts/orchestrate.sh +
# apply_sql.sh), and is overridable via --connection NAME so teardown can target
# a second account set up via `setup.sh --profile <label>`.
ADMIN_CONN="${SNOW_CONNECTION:-admin}"

# ---------- Helpers ----------

usage() {
  cat <<EOF
Usage: $(basename "$0") --phase <phase>

Phases:
  init           Install dbt deps + run dbt debug (connectivity check)
  build          Run dbt build (models + tests)
  test           Run dbt test only (no model execution)
  teardown       Drop all dbt-managed objects in Silver/Gold (via snow sql)
  full-refresh   Run dbt build --full-refresh (rebuild all incrementals)
  docs           Generate and serve dbt docs locally

Options:
  --phase        Required. The lifecycle phase to execute.
  --connection   snow CLI connection for the teardown phase's admin DDL
                 (default: \$SNOW_CONNECTION else "admin"). Ignored by other phases.
  --help         Show this message.
EOF
  exit "${1:-0}"
}

log() { echo "==> [dbt_orchestrate] $*"; }
err() { echo "ERROR: $*" >&2; exit 1; }

# ---------- Load .env ----------

ENV_FILE="$REPO_ROOT/.env"
if [[ -f "$ENV_FILE" ]]; then
  log "Sourcing $ENV_FILE"
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
else
  err ".env not found at $ENV_FILE. Copy .env.example and fill in values."
fi

# ---------- Validate required variables ----------

REQUIRED_VARS=(
  SNOWFLAKE_ACCOUNT
  DBT_SNOWFLAKE_USER
  DBT_SNOWFLAKE_PRIVATE_KEY_PATH
  SNOWFLAKE_WAREHOUSE
  SNOWFLAKE_DATABASE
)

missing=()
for var in "${REQUIRED_VARS[@]}"; do
  if [[ -z "${!var:-}" ]]; then
    missing+=("$var")
  fi
done

if [[ ${#missing[@]} -gt 0 ]]; then
  err "Missing required env vars: ${missing[*]}
       Did you fill in .env? (copy from .env.example)"
fi

# Validate the key file exists
if [[ ! -f "${DBT_SNOWFLAKE_PRIVATE_KEY_PATH/#\~/$HOME}" ]]; then
  err "Private key not found at: $DBT_SNOWFLAKE_PRIVATE_KEY_PATH
       Generate one with: setup.sh --phase loader (or manually via openssl)"
fi

log "Config: account=$SNOWFLAKE_ACCOUNT user=$DBT_SNOWFLAKE_USER role=${DBT_SNOWFLAKE_ROLE:-ARTWORK_TRANSFORMER}"

# ---------- Parse args ----------

PHASE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --phase) PHASE="$2"; shift 2 ;;
    --connection) ADMIN_CONN="$2"; shift 2 ;;
    --help|-h) usage 0 ;;
    *) err "Unknown arg: $1" ;;
  esac
done

[[ -z "$PHASE" ]] && usage 1

# ---------- Execute phase ----------

case "$PHASE" in
  init)
    log "Phase: init -- installing packages + verifying connection"
    dbt deps --project-dir "$DBT_PROJECT_DIR" --profiles-dir "$PROFILES_DIR"
    dbt debug --project-dir "$DBT_PROJECT_DIR" --profiles-dir "$PROFILES_DIR"
    log "init complete. Connection verified."
    ;;

  build)
    log "Phase: build -- running dbt build (models + tests)"
    dbt build --project-dir "$DBT_PROJECT_DIR" --profiles-dir "$PROFILES_DIR"
    log "build complete."
    ;;

  test)
    log "Phase: test -- running dbt test only"
    dbt test --project-dir "$DBT_PROJECT_DIR" --profiles-dir "$PROFILES_DIR"
    log "test complete."
    ;;

  full-refresh)
    log "Phase: full-refresh -- rebuilding all models from scratch"
    dbt build --full-refresh --project-dir "$DBT_PROJECT_DIR" --profiles-dir "$PROFILES_DIR"
    log "full-refresh complete."
    ;;

  docs)
    log "Phase: docs -- generating and serving documentation"
    dbt docs generate --project-dir "$DBT_PROJECT_DIR" --profiles-dir "$PROFILES_DIR"
    log "Docs generated. Serving at http://localhost:8080 (Ctrl-C to stop)"
    dbt docs serve --project-dir "$DBT_PROJECT_DIR" --profiles-dir "$PROFILES_DIR" --port 8080
    ;;

  teardown)
    log "Phase: teardown -- dropping dbt-managed objects in Silver/Gold"
    log "WARNING: This drops ALL tables/views in SILVER and GOLD schemas!"
    read -rp "Type 'yes' to confirm: " confirm
    if [[ "$confirm" != "yes" ]]; then
      log "Aborted."
      exit 0
    fi
    # Use snow CLI (admin connection) to drop and recreate schemas, preserving grants.
    # Connection + database are parameterized for multi-account consistency:
    #   - $ADMIN_CONN  from --connection / $SNOW_CONNECTION (default "admin")
    #   - $SNOWFLAKE_DATABASE  validated above as a required .env var
    log "teardown target: ${SNOWFLAKE_DATABASE}.{SILVER,GOLD} via -c ${ADMIN_CONN}"
    snow sql -q "DROP SCHEMA IF EXISTS ${SNOWFLAKE_DATABASE}.SILVER CASCADE;"   -c "$ADMIN_CONN"
    snow sql -q "DROP SCHEMA IF EXISTS ${SNOWFLAKE_DATABASE}.GOLD CASCADE;"     -c "$ADMIN_CONN"
    snow sql -q "CREATE SCHEMA IF NOT EXISTS ${SNOWFLAKE_DATABASE}.SILVER;"     -c "$ADMIN_CONN"
    snow sql -q "CREATE SCHEMA IF NOT EXISTS ${SNOWFLAKE_DATABASE}.GOLD;"       -c "$ADMIN_CONN"
    log "Schemas recreated. Run 'make infra' to restore grants, then 'make dbt-build'."
    ;;

  *)
    err "Unknown phase: $PHASE (valid: init, build, test, full-refresh, docs, teardown)"
    ;;
esac
