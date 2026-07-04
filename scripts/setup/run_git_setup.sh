#!/usr/bin/env bash
# Apply Snowflake git-setup (Git repository/API integration/MCP integration).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# shellcheck source=../snowflake_account_defaults.sh
source "${REPO_ROOT}/scripts/snowflake_account_defaults.sh"

APPLY=0
ENV_FILE="${REPO_ROOT}/.env"
REQUIRE_OAUTH=1

usage() {
  cat <<EOF_USAGE
usage: bash scripts/setup/run_git_setup.sh [options]

Runs the Makefile's git-setup phase:
  make bootstrap CONN=<profile> TOOLKIT_DIR=<toolkit>

This applies git-setup/create_git_ops_db.sql, create_api_integration.sql,
create_git_repository.sql, and create_mcp_integration.sql through the toolkit.
Dry-run by default. Add --apply to mutate Snowflake.

Options:
${COMMON_USAGE}
  --env-file FILE       File Makefile reads for GITHUB_PAT/OAuth values. Default: .env
  --apply              Execute make bootstrap. Without it, print the plan only.
  --pat-only-ok         Do not require OAuth values before running. Use only if you have
                       temporarily removed MCP from scripts/manifest.txt or know it is not applied.
EOF_USAGE
}

read_env_value() {
  local key="$1" file="$2" line value
  [[ -f "${file}" ]] || return 1
  line="$(grep -E "^[[:space:]]*${key}=" "${file}" | tail -n 1 || true)"
  [[ -n "${line}" ]] || return 1
  value="${line#*=}"
  value="${value%%$'\r'}"
  value="${value%\#*}"
  value="${value%"${value##*[![:space:]]}"}"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%\"}"; value="${value#\"}"
  value="${value%\'}"; value="${value#\'}"
  [[ -n "${value}" ]] || return 1
  printf '%s' "${value}"
}

has_value() {
  local key="$1"
  [[ -n "${!key:-}" ]] && return 0
  read_env_value "${key}" "${ENV_FILE}" >/dev/null
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) APPLY=1; shift ;;
    --env-file) ENV_FILE="${2:-}"; shift 2 ;;
    --pat-only-ok) REQUIRE_OAUTH=0; shift ;;
    -h|--help) usage; exit 0 ;;
    --profile) SNOW_ARTWORK_PROFILE="${2:-}"; shift 2 ;;
    --account) SNOW_ARTWORK_ACCOUNT="${2:-}"; shift 2 ;;
    --toolkit-dir) TOOLKIT_DIR="${2:-}"; shift 2 ;;
    *) echo "error: unknown option '$1'" >&2; usage; exit 64 ;;
  esac
done

require_toolkit
cd "${REPO_ROOT}"

missing=0
if has_value GITHUB_PAT; then echo "✅ GITHUB_PAT present (value hidden)"; else echo "❌ GITHUB_PAT missing or blank"; missing=1; fi
if (( REQUIRE_OAUTH == 1 )); then
  if has_value GITHUB_OAUTH_CLIENT_ID; then echo "✅ GITHUB_OAUTH_CLIENT_ID present (value hidden)"; else echo "❌ GITHUB_OAUTH_CLIENT_ID missing or blank"; missing=1; fi
  if has_value GITHUB_OAUTH_CLIENT_SECRET; then echo "✅ GITHUB_OAUTH_CLIENT_SECRET present (value hidden)"; else echo "❌ GITHUB_OAUTH_CLIENT_SECRET missing or blank"; missing=1; fi
fi
if (( missing != 0 )); then
  cat >&2 <<EOF_MISSING

Refusing to apply git-setup with missing values. Add them to ${ENV_FILE} or export them
in the current shell. Values are passed through Makefile -> snow sql templating and
are never committed by these scripts.
EOF_MISSING
  exit 78
fi

cmd=(make bootstrap "CONN=${SNOW_ARTWORK_PROFILE}" "TOOLKIT_DIR=${TOOLKIT_DIR}" "ENV_FILE=${ENV_FILE}")
printf '+ '; printf '%q ' "${cmd[@]}"; printf '\n'
if (( APPLY == 0 )); then
  echo "DRY-RUN: nothing changed. Re-run with --apply when ready."
  exit 0
fi
"${cmd[@]}"
echo "git-setup apply complete."
