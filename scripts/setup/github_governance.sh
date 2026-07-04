#!/usr/bin/env bash
# Create GitHub Environments, publish Snowflake CI settings, and optionally preview/apply branch governance.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# shellcheck source=../snowflake_account_defaults.sh
source "${REPO_ROOT}/scripts/snowflake_account_defaults.sh"

REPO="dckallos/artwork-db"
APPLY=0
FORCE_SECRETS=0
INCLUDE_PROD=1
SKIP_SECRETS=0
ALLOW_GH_TOKEN_ENV=0
PREVIEW_BRANCH_PROTECTION=0
APPLY_BRANCH_PROTECTION=0
BRANCH="main"

usage() {
  cat <<EOF_USAGE
usage: bash scripts/setup/github_governance.sh [options]

Creates GitHub Environments and publishes Snowflake CI secrets/variables using ghclient.
Dry-run by default. Branch-protection preview/apply is deliberately opt-in so a
branch-protection API 403 cannot block Environment/secret setup.

Options:
  --repo OWNER/NAME              Default: dckallos/artwork-db
  --apply                        Apply environments + secrets/variables only.
  --force-secrets                Pass --force to ghclient secrets publish.
  --staging-only                 Do not publish prod.
  --skip-secrets                 Only create/list environments; do not publish Snowflake CI settings.
  --allow-gh-token-env           Permit GH_TOKEN/GITHUB_TOKEN/GITHUB_PAT env vars.
  --preview-branch-protection    Also run non-mutating branch-protection/ci-required previews.
  --skip-branch-preview          Explicit no-op alias; branch preview is skipped by default.
  --apply-branch-protection      Apply branch protection and ci-required reconciliation.
                                 This is separate from --apply and should be used only after CI is green.
  --branch NAME                  Branch to protect/reconcile. Default: main
  -h, --help                     Show this help.
EOF_USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO="${2:-}"; shift 2 ;;
    --apply) APPLY=1; shift ;;
    --force-secrets) FORCE_SECRETS=1; shift ;;
    --staging-only) INCLUDE_PROD=0; shift ;;
    --skip-secrets) SKIP_SECRETS=1; shift ;;
    --allow-gh-token-env) ALLOW_GH_TOKEN_ENV=1; shift ;;
    --preview-branch-protection) PREVIEW_BRANCH_PROTECTION=1; shift ;;
    --skip-branch-preview) PREVIEW_BRANCH_PROTECTION=0; shift ;;
    --apply-branch-protection) APPLY_BRANCH_PROTECTION=1; PREVIEW_BRANCH_PROTECTION=1; shift ;;
    --branch) BRANCH="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "error: unknown option '$1'" >&2; usage; exit 64 ;;
  esac
done

cd "${REPO_ROOT}"
export GH_CONFIG_DIR="${GH_CONFIG_DIR:-$HOME/.config/gh-artwork-admin}"
mkdir -p "${GH_CONFIG_DIR}"

need_cmd() {
  local cmd="$1"
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    echo "error: required command not found on PATH: ${cmd}" >&2
    exit 69
  fi
}
need_cmd gh
need_cmd ghclient

if (( ALLOW_GH_TOKEN_ENV == 0 )); then
  token_vars=()
  for name in GH_TOKEN GITHUB_TOKEN GITHUB_PAT DCKALLOS_GITHUB_TOKEN TMP_GH_TOKEN; do
    [[ -n "${!name:-}" ]] && token_vars+=("$name")
  done
  if (( ${#token_vars[@]} > 0 )); then
    cat >&2 <<EOF_TOKEN
error: exported GitHub token variables may override 'gh' auth: ${token_vars[*]}
Unset them first, or pass --allow-gh-token-env deliberately.
Suggested clean session:
  unset GH_TOKEN GITHUB_TOKEN GITHUB_PAT DCKALLOS_GITHUB_TOKEN TMP_GH_TOKEN
  export GH_CONFIG_DIR="$HOME/.config/gh-artwork-admin"
  gh auth login -h github.com -s repo
EOF_TOKEN
    exit 78
  fi
fi

run_or_print() {
  printf '+ '; printf '%q ' "$@"; printf '\n'
  if (( APPLY == 1 )); then "$@"; fi
}

run_nonfatal() {
  printf '+ '; printf '%q ' "$@"; printf '\n'
  if ! "$@"; then
    echo "warning: command failed but was non-mutating/preview-only: $*" >&2
    return 1
  fi
}

create_env() {
  local env_name="$1"
  run_or_print gh api --method PUT "repos/${REPO}/environments/${env_name}" --input <(printf '{}')
}

env_exists() {
  local env_name="$1"
  gh api "repos/${REPO}/environments/${env_name}" >/dev/null 2>&1
}

set_var() {
  local env_name="$1" name="$2" value="$3"
  printf '+ printf %%s [hidden/non-secret:%s] | gh variable set %q --env %q --repo %q\n' "$name" "$name" "$env_name" "$REPO"
  if (( APPLY == 1 )); then
    printf '%s' "$value" | gh variable set "$name" --env "$env_name" --repo "$REPO"
  fi
}

publish_set() {
  local set_name="$1" target_value="$2"
  args=(ghclient secrets publish --profile-set "$set_name")
  (( FORCE_SECRETS == 1 )) && args+=(--force)
  (( APPLY == 1 )) && args+=(--apply)
  printf '+ '; printf '%q ' "${args[@]}"; printf '\n'

  if (( APPLY == 0 )) && ! env_exists "$set_name"; then
    echo "DRY-RUN: environment '${set_name}' does not exist yet; ghclient publish preview requires it."
    echo "         Re-run with --apply to create it, then run this script again for the full preview/apply."
  else
    "${args[@]}"
  fi
  set_var "$set_name" DBT_TARGET "$target_value"
}

branch_preview() {
  echo
  echo "==> Branch-governance preview for ${REPO}@${BRANCH} (non-mutating)"
  echo "    If these commands return HTTP 403, Environment/secret setup can still be complete;"
  echo "    run scripts/setup/diagnose_branch_protection_access.sh to inspect branch-protection access."
  run_nonfatal ghclient audit --branch "$BRANCH" || true
  run_nonfatal bash tools/github/wrappers/protect.sh --branch "$BRANCH" || true
  run_nonfatal bash tools/github/wrappers/reconcile-ci.sh --branch "$BRANCH" || true
}

apply_branch_governance() {
  cat <<'EOF_STOP'

Applying branch protection now. This makes the branch require ci-required.
Stop here unless CI is green and branch-protection access has been verified.
EOF_STOP
  ghclient audit --branch "$BRANCH"
  bash tools/github/wrappers/protect.sh --branch "$BRANCH" --apply
  bash tools/github/wrappers/reconcile-ci.sh --branch "$BRANCH" --apply
}

printf '==> GitHub governance for %s\n' "$REPO"
echo "GH_CONFIG_DIR=${GH_CONFIG_DIR}"

ghclient preflight

create_env staging
(( INCLUDE_PROD == 1 )) && create_env prod

if (( SKIP_SECRETS == 0 )); then
  publish_set staging staging
  (( INCLUDE_PROD == 1 )) && publish_set prod prod
fi

if (( PREVIEW_BRANCH_PROTECTION == 1 )); then
  branch_preview
else
  echo
  echo "Skipping branch-governance preview by default. Add --preview-branch-protection when you want to inspect it."
fi

if (( APPLY_BRANCH_PROTECTION == 1 )); then
  apply_branch_governance
fi

if (( APPLY == 0 && APPLY_BRANCH_PROTECTION == 0 )); then
  echo
  echo "DRY-RUN complete. Re-run with --apply to create environments/publish settings."
elif (( APPLY == 1 )); then
  echo
  echo "GitHub Environment/secrets/variables step complete."
fi
