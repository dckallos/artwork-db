#!/usr/bin/env bash
# Inspect local prerequisites and common foot-guns before Snowflake/GitHub setup.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# shellcheck source=../snowflake_account_defaults.sh
source "${REPO_ROOT}/scripts/snowflake_account_defaults.sh"

ENV_FILE="${REPO_ROOT}/.env"
ALLOW_TOKEN_ENV=0

usage() {
  cat <<EOF_USAGE
usage: bash scripts/setup/doctor_local_setup.sh [options]

Options:
${COMMON_USAGE}
  --env-file FILE        Env file to inspect. Default: .env
  --allow-gh-token-env   Warn, but do not fail, when GH_TOKEN/GITHUB_TOKEN/etc are exported.
  -h, --help             Show this help.
EOF_USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file) ENV_FILE="${2:-}"; shift 2 ;;
    --allow-gh-token-env) ALLOW_TOKEN_ENV=1; shift ;;
    -h|--help) usage; exit 0 ;;
    --profile|--account|--admin-user|--admin-role|--role|--init-warehouse|--warehouse|--database|--loader-user|--loader-role|--transformer-user|--transformer-role|--toolkit-dir)
      # Re-parse common args by hand so this script can also accept local flags.
      case "$1" in
        --profile) SNOW_ARTWORK_PROFILE="${2:-}" ;;
        --account) SNOW_ARTWORK_ACCOUNT="${2:-}" ;;
        --admin-user) SNOW_ARTWORK_ADMIN_USER="${2:-}" ;;
        --admin-role|--role) SNOW_ARTWORK_ADMIN_ROLE="${2:-}" ;;
        --init-warehouse) SNOW_ARTWORK_INIT_WAREHOUSE="${2:-}" ;;
        --warehouse) SNOW_ARTWORK_PROJECT_WAREHOUSE="${2:-}" ;;
        --database) SNOW_ARTWORK_DATABASE="${2:-}" ;;
        --loader-user) SNOW_ARTWORK_LOADER_USER="${2:-}" ;;
        --loader-role) SNOW_ARTWORK_LOADER_ROLE="${2:-}" ;;
        --transformer-user) SNOW_ARTWORK_TRANSFORMER_USER="${2:-}" ;;
        --transformer-role) SNOW_ARTWORK_TRANSFORMER_ROLE="${2:-}" ;;
        --toolkit-dir) TOOLKIT_DIR="${2:-}" ;;
      esac
      shift 2 ;;
    *) echo "error: unknown option '$1'" >&2; usage; exit 64 ;;
  esac
done

failures=0
warnings=0

ok() { printf '✅ %s\n' "$*"; }
warn() { warnings=$((warnings + 1)); printf '⚠️  %s\n' "$*"; }
fail() { failures=$((failures + 1)); printf '❌ %s\n' "$*"; }

check_cmd() {
  local cmd="$1"
  if command -v "$cmd" >/dev/null 2>&1; then ok "found command: $cmd"; else fail "missing command: $cmd"; fi
}

printf '==> artwork-db local setup doctor\n'
print_connection_summary

[[ -d "${REPO_ROOT}/.git" ]] && ok "repo root: ${REPO_ROOT}" || fail "not a git checkout: ${REPO_ROOT}"
branch="$(git -C "${REPO_ROOT}" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
[[ -n "${branch}" ]] && ok "git branch: ${branch}" || warn "could not determine git branch"

check_cmd bash
check_cmd python3
check_cmd snow
check_cmd gh
if command -v ghclient >/dev/null 2>&1; then ok "found command: ghclient"; else warn "ghclient is not on PATH; install with: pip install -e tools/github[dev]"; fi

if [[ -f "${TOOLKIT_DIR}/snowflake_cli/setup.sh" ]]; then
  ok "snowflake-toolkit found: ${TOOLKIT_DIR}"
else
  fail "snowflake-toolkit missing at ${TOOLKIT_DIR}; pass --toolkit-dir or set TOOLKIT_DIR"
fi

if [[ -f "${ENV_FILE}" ]]; then
  ok "env file exists: ${ENV_FILE}"
  env_account="$(awk -F= '/^SNOWFLAKE_ACCOUNT=/{gsub(/[\"\047 ]/, "", $2); print $2}' "${ENV_FILE}" | tail -n 1)"
  if [[ "${env_account}" == "${SNOW_ARTWORK_ACCOUNT}" ]]; then
    ok ".env SNOWFLAKE_ACCOUNT=${env_account}"
  else
    fail ".env SNOWFLAKE_ACCOUNT is '${env_account:-<missing>}', expected '${SNOW_ARTWORK_ACCOUNT}'"
  fi
else
  warn "env file not found: ${ENV_FILE}; generate one with scripts/setup/write_local_env.sh"
fi

existing_account="$(connection_account_from_toml "${SNOW_ARTWORK_PROFILE}" || true)"
if [[ -z "${existing_account}" ]]; then
  warn "Snowflake CLI profile '${SNOW_ARTWORK_PROFILE}' does not exist yet"
elif [[ "${existing_account}" == "${SNOW_ARTWORK_ACCOUNT}" ]]; then
  ok "Snowflake CLI profile '${SNOW_ARTWORK_PROFILE}' points at ${existing_account}"
else
  fail "Snowflake CLI profile '${SNOW_ARTWORK_PROFILE}' points at ${existing_account}, expected ${SNOW_ARTWORK_ACCOUNT}"
fi

upper_profile="$(printf '%s' "${SNOW_ARTWORK_PROFILE}" | tr '[:lower:]' '[:upper:]')"
legacy_upper="$(connection_account_from_toml "${upper_profile}" || true)"
if [[ -n "${legacy_upper}" && "${legacy_upper}" != "${SNOW_ARTWORK_ACCOUNT}" ]]; then
  warn "legacy uppercase profile '${upper_profile}' points at ${legacy_upper}; use lowercase '${SNOW_ARTWORK_PROFILE}'"
fi

exported_token_names=()
for name in GH_TOKEN GITHUB_TOKEN GITHUB_PAT DCKALLOS_GITHUB_TOKEN TMP_GH_TOKEN; do
  if [[ -n "${!name:-}" ]]; then exported_token_names+=("$name"); fi
done
if (( ${#exported_token_names[@]} > 0 )); then
  msg="exported GitHub token variables may override gh auth: ${exported_token_names[*]}"
  if (( ALLOW_TOKEN_ENV == 1 )); then warn "$msg"; else fail "$msg; unset them or pass --allow-gh-token-env"; fi
else
  ok "no GH_TOKEN/GITHUB_TOKEN/GITHUB_PAT-style variables exported"
fi

zshrc="${HOME}/.zshrc"
if [[ -f "${zshrc}" ]]; then
  if grep -Eq 'github_pat_|sk-proj-|sk-ant-' "${zshrc}"; then
    warn "${zshrc} appears to contain committed/exported API tokens; rotate them and remove them from shell startup"
  else
    ok "no obvious GitHub/OpenAI/Anthropic token patterns found in ${zshrc}"
  fi
fi

printf '\nDoctor summary: %d failure(s), %d warning(s).\n' "$failures" "$warnings"
if (( failures > 0 )); then exit 1; fi
