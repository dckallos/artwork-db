#!/usr/bin/env bash
# Bootstrap/repair the local Snowflake CLI profiles and apply Snowflake IaC.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# shellcheck source=../snowflake_account_defaults.sh
source "${REPO_ROOT}/scripts/snowflake_account_defaults.sh"

APPLY=0
REPLACE_EXISTING=0
INCLUDE_GIT_SETUP=0
SKIP_ADMIN=0
SKIP_INFRA=0
SKIP_SERVICE_KEYS=0

usage() {
  cat <<EOF_USAGE
usage: bash scripts/setup/bootstrap_snowflake_account.sh [options]

Bootstraps this Mac for the Snowflake account, then applies infrastructure.
Dry-run by default. Add --apply to mutate local Snowflake config and Snowflake.

Options:
${COMMON_USAGE}
  --apply                 Execute commands. Without this, print the plan only.
  --replace-existing      Allow toolkit to rewrite an existing mismatched profile.
  --include-git-setup     After infra/service keys, run scripts/setup/run_git_setup.sh --apply.
  --skip-admin            Skip prereq/admin key registration.
  --skip-infra            Skip make infra.
  --skip-service-keys     Skip promote/loader/transformer phases.
EOF_USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) APPLY=1; shift ;;
    --replace-existing) REPLACE_EXISTING=1; shift ;;
    --include-git-setup) INCLUDE_GIT_SETUP=1; shift ;;
    --skip-admin) SKIP_ADMIN=1; shift ;;
    --skip-infra) SKIP_INFRA=1; shift ;;
    --skip-service-keys) SKIP_SERVICE_KEYS=1; shift ;;
    -h|--help) usage; exit 0 ;;
    --profile) SNOW_ARTWORK_PROFILE="${2:-}"; shift 2 ;;
    --account) SNOW_ARTWORK_ACCOUNT="${2:-}"; shift 2 ;;
    --admin-user) SNOW_ARTWORK_ADMIN_USER="${2:-}"; shift 2 ;;
    --admin-role|--role) SNOW_ARTWORK_ADMIN_ROLE="${2:-}"; shift 2 ;;
    --init-warehouse) SNOW_ARTWORK_INIT_WAREHOUSE="${2:-}"; shift 2 ;;
    --warehouse) SNOW_ARTWORK_PROJECT_WAREHOUSE="${2:-}"; shift 2 ;;
    --database) SNOW_ARTWORK_DATABASE="${2:-}"; shift 2 ;;
    --loader-user) SNOW_ARTWORK_LOADER_USER="${2:-}"; shift 2 ;;
    --loader-role) SNOW_ARTWORK_LOADER_ROLE="${2:-}"; shift 2 ;;
    --transformer-user) SNOW_ARTWORK_TRANSFORMER_USER="${2:-}"; shift 2 ;;
    --transformer-role) SNOW_ARTWORK_TRANSFORMER_ROLE="${2:-}"; shift 2 ;;
    --toolkit-dir) TOOLKIT_DIR="${2:-}"; shift 2 ;;
    *) echo "error: unknown option '$1'" >&2; usage; exit 64 ;;
  esac
done

require_toolkit
cd "${REPO_ROOT}"

printf '==> Snowflake bootstrap plan\n'
print_connection_summary

replace_arg=()
if (( REPLACE_EXISTING == 1 )); then
  replace_arg=(--replace-existing)
elif [[ "${APPLY}" == "1" ]]; then
  ensure_profile_not_pointing_elsewhere
fi

run_or_print() {
  printf '+ '
  printf '%q ' "$@"
  printf '\n'
  if (( APPLY == 1 )); then "$@"; fi
}

run_toolkit_or_print() {
  local phase="$1"; shift || true
  if (( APPLY == 1 )); then
    run_toolkit_phase "${phase}" "$@"
  else
    print_toolkit_phase "${phase}"
  fi
}

if (( SKIP_ADMIN == 0 )); then
  run_toolkit_or_print prereq "${replace_arg[@]}"
  run_toolkit_or_print admin
else
  echo "==> skipping admin prereq/key registration"
fi

if (( SKIP_INFRA == 0 )); then
  run_or_print make infra "CONN=${SNOW_ARTWORK_PROFILE}" "TOOLKIT_DIR=${TOOLKIT_DIR}"
else
  echo "==> skipping make infra"
fi

if (( SKIP_SERVICE_KEYS == 0 )); then
  run_toolkit_or_print promote
  run_toolkit_or_print loader
  run_toolkit_or_print transformer
else
  echo "==> skipping promote/loader/transformer"
fi

if (( INCLUDE_GIT_SETUP == 1 )); then
  if (( APPLY == 1 )); then
    bash scripts/setup/run_git_setup.sh --profile "${SNOW_ARTWORK_PROFILE}" --toolkit-dir "${TOOLKIT_DIR}" --apply
  else
    echo "bash scripts/setup/run_git_setup.sh --profile ${SNOW_ARTWORK_PROFILE} --toolkit-dir ${TOOLKIT_DIR} --apply"
  fi
fi

if (( APPLY == 0 )); then
  echo "DRY-RUN complete. Re-run with --apply when ready."
else
  echo "Snowflake bootstrap complete."
fi
