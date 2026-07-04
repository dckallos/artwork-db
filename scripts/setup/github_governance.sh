#!/usr/bin/env bash
# Create GitHub Environments, publish Snowflake CI settings, and optionally protect main.
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
APPLY_BRANCH_PROTECTION=0
BRANCH="main"

usage() {
  cat <<EOF_USAGE
usage: bash scripts/setup/github_governance.sh [options]

Creates GitHub Environments, publishes Snowflake CI secrets/variables using ghclient,
and previews branch protection/required-check reconciliation. Dry-run by default.

Options:
  --repo OWNER/NAME              Default: dckallos/artwork-db
  --apply                        Apply environments + secrets/variables only.
  --force-secrets                Pass --force to ghclient secrets publish.
  --staging-only                 Do not publish prod.
  --skip-secrets                 Only create/list environments and preview branch protection.
  --allow-gh-token-env           Permit GH_TOKEN/GITHUB_TOKEN/GITHUB_PAT env vars.
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
    --apply-branch-protection) APPLY_BRANCH_PROTECTION=1; shift ;;
    --branch) BRANCH="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "error: unknown option '$1'" >&2; usage; exit 64 ;;
  esac
done

cd "${REPO_ROOT}"
export GH_CONFIG_DIR="${GH_CONFIG_DIR:-$HOME/.config/gh-artwork-admin}"
mkdir -p "${GH_CONFIG_DIR}"

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
  export GH_CONFIG_DIR=\"$HOME/.config/gh-artwork-admin\"
  gh auth login -h github.com -s repo
EOF_TOKEN
    exit 78
  fi
fi

run_or_print() {
  printf '+ '; printf '%q ' "$@"; printf '\n'
  if (( APPLY == 1 )); then "$@"; fi
}

create_env() {
  local env_name="$1"
  run_or_print gh api --method PUT "repos/${REPO}/environments/${env_name}" --input <(printf '{}')
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
  if (( APPLY == 0 )) && ! gh api "repos/${REPO}/environments/${set_name}" >/dev/null 2>&1; then
    echo "DRY-RUN: environment '${set_name}' does not exist yet; ghclient publish preview requires it."
    echo "         Re-run with --apply to create it, then run this script again for the full preview/apply."
  else
    "${args[@]}"
  fi
  set_var "$set_name" DBT_TARGET "$target_value"
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

# Always show the branch-governance preview. It mutates only under --apply-branch-protection.
# Note: branch-protection export writes a local snapshot, so this dry-run path uses audit only.
ghclient audit --branch "$BRANCH" || true
tools/github/wrappers/protect.sh --branch "$BRANCH"
tools/github/wrappers/reconcile-ci.sh --branch "$BRANCH" || true

if (( APPLY_BRANCH_PROTECTION == 1 )); then
  cat <<'EOF_STOP'

Applying branch protection now. This makes the branch require ci-required.
Stop here if CI is not green.
EOF_STOP
  tools/github/wrappers/protect.sh --branch "$BRANCH" --apply
  tools/github/wrappers/reconcile-ci.sh --branch "$BRANCH" --apply
fi

if (( APPLY == 0 && APPLY_BRANCH_PROTECTION == 0 )); then
  echo "DRY-RUN complete. Re-run with --apply to create environments/publish settings."
fi
