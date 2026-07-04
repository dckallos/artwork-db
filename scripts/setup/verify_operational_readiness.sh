#!/usr/bin/env bash
# Verify local Snowflake, dbt, and GitHub governance readiness without applying changes.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# shellcheck source=../snowflake_account_defaults.sh
source "${REPO_ROOT}/scripts/snowflake_account_defaults.sh"

ENV_FILE="${REPO_ROOT}/.env"
SKIP_SNOW=0
SKIP_DBT=0
SKIP_GH=0
INCLUDE_PROD=1

usage() {
  cat <<EOF_USAGE
usage: bash scripts/setup/verify_operational_readiness.sh [options]

Runs non-mutating checks after setup.

Options:
${COMMON_USAGE}
  --env-file FILE       Env file for dbt validation. Default: .env
  --skip-snow           Skip snow connection tests.
  --skip-dbt            Skip dbt debug/deps/parse.
  --skip-gh             Skip ghclient/GitHub checks.
  --staging-only        Do not check prod CI profile/environment.
EOF_USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file) ENV_FILE="${2:-}"; shift 2 ;;
    --skip-snow) SKIP_SNOW=1; shift ;;
    --skip-dbt) SKIP_DBT=1; shift ;;
    --skip-gh) SKIP_GH=1; shift ;;
    --staging-only) INCLUDE_PROD=0; shift ;;
    -h|--help) usage; exit 0 ;;
    --profile) SNOW_ARTWORK_PROFILE="${2:-}"; shift 2 ;;
    --account) SNOW_ARTWORK_ACCOUNT="${2:-}"; shift 2 ;;
    --toolkit-dir) TOOLKIT_DIR="${2:-}"; shift 2 ;;
    *) echo "error: unknown option '$1'" >&2; usage; exit 64 ;;
  esac
done

cd "${REPO_ROOT}"
failures=0
run_check() {
  local label="$1"; shift
  printf '\n==> %s\n' "$label"
  printf '+ '; printf '%q ' "$@"; printf '\n'
  if "$@"; then
    echo "✅ ${label} passed"
  else
    echo "❌ ${label} failed"
    failures=$((failures + 1))
  fi
}

if (( SKIP_SNOW == 0 )); then
  run_check "snow admin connection" snow connection test --connection "${SNOW_ARTWORK_PROFILE}"
  run_check "snow loader connection" snow connection test --connection "${SNOW_ARTWORK_PROFILE}_loader"
  run_check "snow transformer connection" snow connection test --connection "${SNOW_ARTWORK_PROFILE}_transformer"
  run_check "snow staging CI connection" snow connection test --connection "${SNOW_ARTWORK_CI_STAGING_PROFILE:-artwork_ci_staging}"
  if (( INCLUDE_PROD == 1 )); then
    run_check "snow prod CI connection" snow connection test --connection "${SNOW_ARTWORK_CI_PROD_PROFILE:-artwork_ci_prod}"
  fi
fi

if (( SKIP_DBT == 0 )); then
  if [[ ! -f "${ENV_FILE}" ]]; then
    echo "❌ env file missing: ${ENV_FILE}"
    failures=$((failures + 1))
  else
    set -a
    # shellcheck source=/dev/null
    source "${ENV_FILE}"
    set +a
    run_check "dbt debug" dbt debug --project-dir artwork_pipeline --profiles-dir artwork_pipeline
    run_check "dbt deps" dbt deps --project-dir artwork_pipeline --profiles-dir artwork_pipeline
    run_check "dbt parse" dbt parse --project-dir artwork_pipeline --profiles-dir artwork_pipeline --target "${DBT_TARGET:-dev}" --no-partial-parse
  fi
fi

if (( SKIP_GH == 0 )); then
  export GH_CONFIG_DIR="${GH_CONFIG_DIR:-$HOME/.config/gh-artwork-admin}"
  run_check "ghclient preflight" ghclient preflight
  run_check "ghclient audit main" ghclient audit --branch main
  run_check "list staging secrets" gh secret list --env staging --repo dckallos/artwork-db
  run_check "list staging variables" gh variable list --env staging --repo dckallos/artwork-db
  if (( INCLUDE_PROD == 1 )); then
    run_check "list prod secrets" gh secret list --env prod --repo dckallos/artwork-db
    run_check "list prod variables" gh variable list --env prod --repo dckallos/artwork-db
  fi
fi

printf '\nReadiness summary: %d failure(s).\n' "$failures"
exit "$failures"
