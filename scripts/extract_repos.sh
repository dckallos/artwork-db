#!/usr/bin/env bash
# =============================================================================
# extract_repos.sh -- One-time repo extraction for the 3-repo split
# =============================================================================
#
# Runs git filter-repo to extract snowflake-toolkit and dbt-diagnostics from
# the artwork-db monorepo. Produces two ready-to-push directories.
#
# Prerequisites:
#   - git filter-repo installed (pip install git-filter-repo)
#   - Phase A refactoring already committed on donkey-kong-sandbox
#   - Run from a directory WHERE YOU WANT the extracted repos created
#     (e.g., ~/projects/)
#
# Usage:
#   bash extract_repos.sh /path/to/artwork-db
#
# What it does:
#   1. Clones artwork-db twice (fresh clones -- filter-repo is destructive)
#   2. Extracts dbt-diagnostics (single path)
#   3. Extracts snowflake-toolkit (multiple paths + rename)
#   4. Validates both extractions
#   5. Prints manual push commands (does NOT push automatically)
#
# What it does NOT do:
#   - Push to any remote (you inspect first, then push manually)
#   - Modify the original artwork-db repo
#   - Run any refactoring edits
#
# =============================================================================

set -euo pipefail

# --- Configuration ---

BRANCH="donkey-kong-sandbox"
TOOLKIT_REPO_NAME="snowflake-toolkit"
DIAGNOSTICS_REPO_NAME="dbt-diagnostics"

# GitHub remotes (printed in push instructions; edit if different)
TOOLKIT_REMOTE="git@github.com:dckallos/snowflake-toolkit.git"
DIAGNOSTICS_REMOTE="git@github.com:dckallos/dbt-diagnostics.git"

# --- Helpers ---

log() { echo "==> $*"; }
err() { echo "ERROR: $*" >&2; exit 1; }
separator() { echo ""; echo "========================================"; echo ""; }

validate_extraction() {
    local repo_dir="$1"
    local label="$2"

    local commit_count
    commit_count=$(git -C "$repo_dir" rev-list --count HEAD)

    if [[ "$commit_count" -eq 0 ]]; then
        err "$label extraction produced 0 commits. Something went wrong."
    fi

    local file_count
    file_count=$(git -C "$repo_dir" ls-files | wc -l | tr -d ' ')

    if [[ "$file_count" -eq 0 ]]; then
        err "$label extraction has 0 tracked files. Something went wrong."
    fi

    log "$label: $commit_count commits, $file_count files -- OK"
}

# --- Argument parsing ---

if [[ $# -lt 1 ]]; then
    echo "Usage: bash extract_repos.sh /path/to/artwork-db"
    echo ""
    echo "Run from the directory where you want the extracted repos created."
    echo "Example:"
    echo "  cd ~/projects"
    echo "  bash extract_repos.sh ./artwork-db"
    exit 1
fi

SOURCE_REPO="$(cd "$1" && pwd)"
WORK_DIR="$(pwd)"

# --- Preflight checks ---

log "Source repo: $SOURCE_REPO"
log "Working dir: $WORK_DIR"
log "Branch: $BRANCH"

if [[ ! -d "$SOURCE_REPO/.git" ]]; then
    err "$SOURCE_REPO is not a git repository"
fi

if ! command -v git-filter-repo &>/dev/null; then
    err "git-filter-repo not found. Install: pip install git-filter-repo"
fi

if [[ -d "$WORK_DIR/$DIAGNOSTICS_REPO_NAME" ]]; then
    err "$WORK_DIR/$DIAGNOSTICS_REPO_NAME already exists. Remove or rename it."
fi

if [[ -d "$WORK_DIR/$TOOLKIT_REPO_NAME" ]]; then
    err "$WORK_DIR/$TOOLKIT_REPO_NAME already exists. Remove or rename it."
fi

separator
log "All preflight checks passed."

# =============================================================================
# STEP 1: Extract dbt-diagnostics
# =============================================================================

separator
log "STEP 1: Extracting $DIAGNOSTICS_REPO_NAME"
log "Cloning $SOURCE_REPO -> $DIAGNOSTICS_REPO_NAME"

git clone --no-hardlinks "$SOURCE_REPO" "$DIAGNOSTICS_REPO_NAME"
cd "$WORK_DIR/$DIAGNOSTICS_REPO_NAME"
git checkout "$BRANCH"

log "Running git filter-repo (keeping dbt_diagnostics/ only)..."

git filter-repo --path dbt_diagnostics/ --force

validate_extraction "$WORK_DIR/$DIAGNOSTICS_REPO_NAME" "dbt-diagnostics"

cd "$WORK_DIR"

# =============================================================================
# STEP 2: Extract snowflake-toolkit
# =============================================================================

separator
log "STEP 2: Extracting $TOOLKIT_REPO_NAME"
log "Cloning $SOURCE_REPO -> $TOOLKIT_REPO_NAME"

git clone --no-hardlinks "$SOURCE_REPO" "$TOOLKIT_REPO_NAME"
cd "$WORK_DIR/$TOOLKIT_REPO_NAME"
git checkout "$BRANCH"

log "Running git filter-repo (keeping toolkit paths)..."

git filter-repo \
    --path scripts/snowflake_cli/ \
    --path scripts/lib/ \
    --path scripts/orchestrate_modern.sh \
    --path scripts/apply_sql.sh \
    --path scripts/rollback_sql.sh \
    --path scripts/bootstrap.py \
    --path scripts/bootstrap_chmod.sh \
    --path scripts/activate_mac.sh \
    --path scripts/load_profile.sh \
    --path scripts/unload_profile.sh \
    --path scripts/status_profile.sh \
    --path scripts/check.sh \
    --path scripts/checkpoint.sh \
    --path scripts/git_mark_executable.sh \
    --path scripts/executable_files.txt \
    --path scripts/sql/show_active_sessions.sql \
    --path scripts/sql/show_admin_account_grants.sql \
    --path scripts/sql/checkpoint.sql \
    --path tests/ \
    --path docs/framework/ \
    --force

log "Restructuring paths (scripts/* -> root, docs/framework/ -> docs/)..."

git filter-repo \
    --path-rename scripts/snowflake_cli/:snowflake_cli/ \
    --path-rename scripts/lib/:lib/ \
    --path-rename scripts/orchestrate_modern.sh:orchestrate_modern.sh \
    --path-rename scripts/apply_sql.sh:apply_sql.sh \
    --path-rename scripts/rollback_sql.sh:rollback_sql.sh \
    --path-rename scripts/bootstrap.py:bootstrap.py \
    --path-rename scripts/bootstrap_chmod.sh:bootstrap_chmod.sh \
    --path-rename scripts/activate_mac.sh:activate_mac.sh \
    --path-rename scripts/load_profile.sh:load_profile.sh \
    --path-rename scripts/unload_profile.sh:unload_profile.sh \
    --path-rename scripts/status_profile.sh:status_profile.sh \
    --path-rename scripts/check.sh:check.sh \
    --path-rename scripts/checkpoint.sh:checkpoint.sh \
    --path-rename scripts/git_mark_executable.sh:git_mark_executable.sh \
    --path-rename scripts/executable_files.txt:executable_files.txt \
    --path-rename scripts/sql/:sql/ \
    --path-rename docs/framework/:docs/ \
    --force

validate_extraction "$WORK_DIR/$TOOLKIT_REPO_NAME" "snowflake-toolkit"

cd "$WORK_DIR"

# =============================================================================
# STEP 3: Summary and push instructions
# =============================================================================

separator
log "EXTRACTION COMPLETE"
echo ""
echo "Two repos extracted and validated:"
echo ""
echo "  $WORK_DIR/$DIAGNOSTICS_REPO_NAME"
echo "  $WORK_DIR/$TOOLKIT_REPO_NAME"
echo ""
echo "--- INSPECT BEFORE PUSHING ---"
echo ""
echo "Review each repo:"
echo "  cd $DIAGNOSTICS_REPO_NAME && git log --oneline | head -20"
echo "  cd $TOOLKIT_REPO_NAME && git log --oneline | head -20"
echo ""
echo "Check for residual artwork references in toolkit:"
echo "  cd $TOOLKIT_REPO_NAME && grep -rn 'ARTWORK' . --include='*.sh' --include='*.py' | grep -v test"
echo ""
echo "--- PUSH COMMANDS (run manually after inspection) ---"
echo ""
echo "  # dbt-diagnostics"
echo "  cd $WORK_DIR/$DIAGNOSTICS_REPO_NAME"
echo "  git remote add origin $DIAGNOSTICS_REMOTE"
echo "  git push -u origin $BRANCH"
echo ""
echo "  # snowflake-toolkit"
echo "  cd $WORK_DIR/$TOOLKIT_REPO_NAME"
echo "  git remote add origin $TOOLKIT_REMOTE"
echo "  git push -u origin $BRANCH"
echo ""
echo "--- AFTER PUSHING: Clean up artwork-db (Phase 3) ---"
echo ""
echo "  cd $SOURCE_REPO"
echo "  # Wire Makefile to TOOLKIT_DIR=../$TOOLKIT_REPO_NAME"
echo "  # Then git rm the extracted files (see plan Section 4.2)"
echo ""
