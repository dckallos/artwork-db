#!/usr/bin/env bash
# Read-only diagnostics for GitHub classic branch-protection API access.
set -euo pipefail

REPO="dckallos/artwork-db"
BRANCH="main"

usage() {
  cat <<'EOF_USAGE'
usage: bash scripts/setup/diagnose_branch_protection_access.sh [--repo OWNER/NAME] [--branch NAME]

Runs read-only GitHub API checks to explain whether classic branch protection can be read.
EOF_USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO="${2:-}"; shift 2 ;;
    --branch) BRANCH="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "error: unknown option '$1'" >&2; usage; exit 64 ;;
  esac
done

export GH_CONFIG_DIR="${GH_CONFIG_DIR:-$HOME/.config/gh-artwork-admin}"

echo "==> GitHub branch-protection access diagnostics"
echo "repo:   ${REPO}"
echo "branch: ${BRANCH}"
echo "GH_CONFIG_DIR=${GH_CONFIG_DIR}"

printf '\n==> gh auth status\n'
gh auth status -h github.com || true

printf '\n==> repo permissions\n'
gh api "repos/${REPO}" --jq '{full_name, private, visibility, permissions}' || true

printf '\n==> branch exists\n'
gh api "repos/${REPO}/branches/${BRANCH}" --jq '{name, protected}' || true

printf '\n==> classic branch protection endpoint\n'
if gh api "repos/${REPO}/branches/${BRANCH}/protection" >/tmp/branch-protection.json 2>/tmp/branch-protection.err; then
  echo "classic branch protection endpoint: readable"
  python3 - <<'PY'
import json
from pathlib import Path
payload = json.loads(Path('/tmp/branch-protection.json').read_text())
print(json.dumps({
    'required_status_checks': payload.get('required_status_checks'),
    'required_pull_request_reviews': payload.get('required_pull_request_reviews'),
    'enforce_admins': payload.get('enforce_admins'),
}, indent=2))
PY
else
  echo "classic branch protection endpoint: not readable"
  sed 's/^/  /' /tmp/branch-protection.err || true
  cat <<'EOF_HINT'

Interpretation:
  - HTTP 404 usually means no classic protection is configured for that branch.
  - HTTP 403 means GitHub refused this endpoint for the authenticated account/repo.
    Common causes are plan/feature availability for private repositories, insufficient
    token permission for repository administration, or an organization/repository policy.
  - Environment secrets/variables can still be correctly configured even when this
    classic branch-protection endpoint is unavailable.
EOF_HINT
fi

printf '\n==> rulesets branch-rules endpoint\n'
gh api "repos/${REPO}/rules/branches/${BRANCH}" --jq 'length as $n | "branch-rules count=\($n)"' || true
