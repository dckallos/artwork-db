#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bash scripts/dev/diff_against_remote.sh [--remote origin] [--branch BRANCH] [--no-fetch] [--full]

Summarize workspace differences against a remote Git branch. This is intended for
Claude/Cortex/Snowflake CoCo sessions before making edits.

Options:
  --remote NAME     Remote name to compare against. Default: origin.
  --branch NAME     Remote branch to compare against. Default: current branch if present
                    on the remote; otherwise the remote default branch; otherwise main.
  --no-fetch        Do not run git fetch before comparison.
  --full            Print the full tracked-file diff after the summary.
  -h, --help        Show this help.

Environment overrides:
  REMOTE            Same as --remote.
  BRANCH            Same as --branch.
EOF
}

REMOTE_NAME="${REMOTE:-origin}"
BRANCH_NAME="${BRANCH:-}"
FETCH=1
SHOW_FULL=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --remote)
      REMOTE_NAME="${2:?--remote requires a value}"
      shift 2
      ;;
    --branch)
      BRANCH_NAME="${2:?--branch requires a value}"
      shift 2
      ;;
    --no-fetch)
      FETCH=0
      shift
      ;;
    --full)
      SHOW_FULL=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

if ! git remote get-url "$REMOTE_NAME" >/dev/null 2>&1; then
  echo "Remote '$REMOTE_NAME' does not exist." >&2
  exit 1
fi

if [[ $FETCH -eq 1 ]]; then
  echo "== Fetching $REMOTE_NAME =="
  git fetch --prune "$REMOTE_NAME" || {
    echo "Fetch failed. Re-run with --no-fetch to inspect existing local remote refs." >&2
    exit 1
  }
fi

if [[ -z "$BRANCH_NAME" ]]; then
  CURRENT_BRANCH="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || true)"
  if [[ -n "$CURRENT_BRANCH" ]] && git rev-parse --verify --quiet "refs/remotes/$REMOTE_NAME/$CURRENT_BRANCH" >/dev/null; then
    BRANCH_NAME="$CURRENT_BRANCH"
  else
    DEFAULT_REF="$(git symbolic-ref --quiet --short "refs/remotes/$REMOTE_NAME/HEAD" 2>/dev/null || true)"
    if [[ -n "$DEFAULT_REF" ]]; then
      BRANCH_NAME="${DEFAULT_REF#${REMOTE_NAME}/}"
    elif git rev-parse --verify --quiet "refs/remotes/$REMOTE_NAME/main" >/dev/null; then
      BRANCH_NAME="main"
    elif git rev-parse --verify --quiet "refs/remotes/$REMOTE_NAME/master" >/dev/null; then
      BRANCH_NAME="master"
    else
      echo "Could not infer remote branch. Pass --branch BRANCH." >&2
      exit 1
    fi
  fi
fi

REMOTE_REF="$REMOTE_NAME/$BRANCH_NAME"
if ! git rev-parse --verify --quiet "refs/remotes/$REMOTE_REF" >/dev/null; then
  echo "Remote ref '$REMOTE_REF' does not exist locally." >&2
  echo "Try: git fetch $REMOTE_NAME $BRANCH_NAME" >&2
  exit 1
fi

MERGE_BASE="$(git merge-base HEAD "$REMOTE_REF" 2>/dev/null || true)"

printf '\n== Comparison target ==\n'
echo "Repository: $ROOT"
echo "Remote ref: $REMOTE_REF"
echo "Remote SHA: $(git rev-parse --short "$REMOTE_REF")"
echo "HEAD SHA:   $(git rev-parse --short HEAD)"
if [[ -n "$MERGE_BASE" ]]; then
  echo "Merge base: $(git rev-parse --short "$MERGE_BASE")"
else
  echo "Merge base: unavailable"
fi

printf '\n== Branch/status ==\n'
git status --short --branch

printf '\n== Local commits ahead of %s ==\n' "$REMOTE_REF"
if git log --oneline "$REMOTE_REF"..HEAD -- 2>/dev/null | sed -n '1,40p' | grep -q .; then
  git log --oneline "$REMOTE_REF"..HEAD -- | sed -n '1,40p'
else
  echo "None"
fi

printf '\n== Remote commits not in local HEAD ==\n'
if git log --oneline HEAD.."$REMOTE_REF" -- 2>/dev/null | sed -n '1,40p' | grep -q .; then
  git log --oneline HEAD.."$REMOTE_REF" -- | sed -n '1,40p'
else
  echo "None"
fi

printf '\n== Tracked file changes versus %s ==\n' "$REMOTE_REF"
if git diff --name-status "$REMOTE_REF" -- | grep -q .; then
  git diff --name-status "$REMOTE_REF" --
else
  echo "None"
fi

printf '\n== Tracked diff stat versus %s ==\n' "$REMOTE_REF"
if git diff --stat "$REMOTE_REF" -- | grep -q .; then
  git diff --stat "$REMOTE_REF" --
else
  echo "None"
fi

printf '\n== Staged changes ==\n'
if git diff --cached --name-status | grep -q .; then
  git diff --cached --name-status
else
  echo "None"
fi

printf '\n== Unstaged tracked changes ==\n'
if git diff --name-status | grep -q .; then
  git diff --name-status
else
  echo "None"
fi

printf '\n== Untracked files ==\n'
if git ls-files --others --exclude-standard | grep -q .; then
  git ls-files --others --exclude-standard
else
  echo "None"
fi

if [[ $SHOW_FULL -eq 1 ]]; then
  printf '\n== Full tracked diff versus %s ==\n' "$REMOTE_REF"
  git diff "$REMOTE_REF" --
fi

printf '\n== Done ==\n'
echo "Review this summary before editing. Do not overwrite unrelated user or parallel-agent changes."
