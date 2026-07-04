#!/usr/bin/env bash
# Diagnose branch-protection GET/PUT failures without applying by default.
set -euo pipefail

REPO="dckallos/artwork-db"
BRANCH="main"
APPLY_PROBE=0
PAYLOAD=""

usage() {
  cat <<'USAGE'
usage: bash scripts/setup/diagnose_branch_protection_422.sh [options]

Read-only by default. Prints repo permission/visibility, branch info,
classic branch protection status, and ruleset-derived branch rules status.

Options:
  --repo OWNER/NAME       Default: dckallos/artwork-db
  --branch NAME           Default: main
  --payload FILE          JSON PUT body to use with --apply-probe
  --apply-probe           Actually send PUT /branches/<branch>/protection.
                          This can mutate branch protection if the payload is valid.
  -h, --help              Show this help.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO="${2:-}"; shift 2 ;;
    --branch) BRANCH="${2:-}"; shift 2 ;;
    --payload) PAYLOAD="${2:-}"; shift 2 ;;
    --apply-probe) APPLY_PROBE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "error: unknown option '$1'" >&2; usage; exit 64 ;;
  esac
done

if [[ -z "${GH_CONFIG_DIR:-}" ]]; then
  export GH_CONFIG_DIR="$HOME/.config/gh-artwork-admin"
fi

run_status() {
  local label="$1"; shift
  local out rc
  printf '\n==> %s\n' "$label"
  printf '+ '; printf '%q ' "$@"; printf '\n'
  set +e
  out="$("$@" 2>&1)"
  rc=$?
  set -e
  printf '%s\n' "$out"
  printf 'exit_code=%s\n' "$rc"
}

printf 'Branch protection diagnosis\n'
printf '  repo:   %s\n' "$REPO"
printf '  branch: %s\n' "$BRANCH"
printf '  GH_CONFIG_DIR: %s\n' "${GH_CONFIG_DIR}"

run_status "gh auth status" gh auth status -h github.com
run_status "repo permissions" gh api "repos/${REPO}" --jq '{name,visibility,private,permissions,allow_squash_merge,allow_rebase_merge,allow_merge_commit}'
run_status "branch exists" gh api "repos/${REPO}/branches/${BRANCH}" --jq '{name,commit:.commit.sha,protected}'
run_status "classic branch protection GET" gh api -i "repos/${REPO}/branches/${BRANCH}/protection"
run_status "rulesets list" gh api "repos/${REPO}/rulesets?includes_parents=true"
run_status "rules that apply to branch" gh api "repos/${REPO}/rules/branches/${BRANCH}"

if (( APPLY_PROBE == 0 )); then
  cat <<'EOF_NOTE'

Read-only diagnosis complete.

To probe a PUT and capture the exact GitHub validation error body, pass:
  --payload /tmp/main-protection.json --apply-probe

WARNING: --apply-probe can mutate branch protection if the payload is valid.
EOF_NOTE
  exit 0
fi

if [[ -z "$PAYLOAD" || ! -f "$PAYLOAD" ]]; then
  echo "error: --apply-probe requires --payload FILE" >&2
  exit 64
fi

run_status "branch protection PUT probe" gh api -i \
  --method PUT \
  "repos/${REPO}/branches/${BRANCH}/protection" \
  --input "$PAYLOAD"
