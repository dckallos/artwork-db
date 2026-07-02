#!/usr/bin/env bash
# =============================================================================
# Phase 3 Mac Execution Script
# Run this from ~/dev/artwork-db on the donkey-kong-sandbox branch.
# Prerequisites: Items 1-3 already applied (Makefile wired to TOOLKIT_DIR).
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

echo "=== Phase 3 Switchover: Mac Execution ==="
echo "Working directory: $(pwd)"
echo "Branch: $(git branch --show-current)"
echo ""

# ---------------------------------------------------------------------------
# Item 4: Verify Makefile wiring (dry-run)
# ---------------------------------------------------------------------------
echo "--- Item 4: Dry-run verification ---"
echo ""
echo "Running: make -n iac CONN=admin VARS=\"github_pat=PLACEHOLDER\""
make -n iac CONN=admin VARS="github_pat=PLACEHOLDER" 2>&1 | head -20
echo ""

echo "Running: make -n loader CONN=admin"
make -n loader CONN=admin 2>&1 | head -20
echo ""

echo "Running: make -n transformer CONN=admin"
make -n transformer CONN=admin 2>&1 | head -20
echo ""

echo "Running: make -n down CONN=admin"
make -n down CONN=admin 2>&1 | head -20
echo ""

# Check that no output references scripts/ for TOOLKIT scripts (scripts/manifest.txt is expected -- artwork-specific)
echo "Checking for lingering toolkit references in dry-run output..."
STALE=$(make -n iac CONN=admin VARS="github_pat=PLACEHOLDER" 2>&1 | grep "scripts/" | grep -cv "scripts/manifest.txt" || true)
if [ "$STALE" -gt 0 ]; then
    echo "WARNING: Found $STALE references to scripts/ (non-manifest) in make -n iac output!"
    make -n iac CONN=admin VARS="github_pat=PLACEHOLDER" 2>&1 | grep "scripts/" | grep -v "scripts/manifest.txt"
    echo ""
    echo "STOP: Fix these before continuing."
    exit 1
fi
echo "OK: All toolkit commands reference TOOLKIT_DIR. Only scripts/manifest.txt remains (expected)."
echo ""

# ---------------------------------------------------------------------------
# Item 5: Verify fail-fast guard fires
# ---------------------------------------------------------------------------
echo "--- Item 5: Fail-fast guard test ---"
echo ""
echo "Running: make -n iac TOOLKIT_DIR=/nonexistent 2>&1 | head -3"
make -n iac TOOLKIT_DIR=/nonexistent 2>&1 | head -3 || true
echo ""
echo "(Expected: 'snowflake-toolkit not found at /nonexistent...')"
echo ""

# ---------------------------------------------------------------------------
# PAUSE: Review output above before continuing
# ---------------------------------------------------------------------------
echo "=== Items 4-5 complete. Review output above. ==="
echo ""
read -rp "Continue with git rm (Items 6-7)? [y/N] " CONFIRM
if [[ "$CONFIRM" != "y" && "$CONFIRM" != "Y" ]]; then
    echo "Aborted. Re-run when ready."
    exit 0
fi

# ---------------------------------------------------------------------------
# Item 6: git rm toolkit files (now in snowflake-toolkit)
# ---------------------------------------------------------------------------
echo ""
echo "--- Item 6: git rm toolkit files ---"

# Orchestration + utility scripts (now at toolkit repo root)
git rm scripts/orchestrate_modern.sh
git rm scripts/apply_sql.sh
git rm scripts/rollback_sql.sh
git rm scripts/bootstrap.py
git rm scripts/bootstrap_chmod.sh
git rm scripts/activate_mac.sh
git rm scripts/load_profile.sh
git rm scripts/unload_profile.sh
git rm scripts/status_profile.sh
git rm scripts/check.sh
git rm scripts/checkpoint.sh
git rm scripts/git_mark_executable.sh
git rm scripts/executable_files.txt

# Toolkit CLI suite (now snowflake_cli/ in toolkit)
git rm -r scripts/snowflake_cli/

# Framework library (now lib/ in toolkit)
git rm -r scripts/lib/

# SQL utilities that moved to toolkit (artwork-specific SQL stays)
git rm scripts/sql/show_active_sessions.sql
git rm scripts/sql/show_admin_account_grants.sql
git rm scripts/sql/checkpoint.sql

# Framework tests (now tests/ in toolkit)
git rm -r tests/

# Framework docs (now docs/ in toolkit)
git rm -r docs/framework/

echo ""
echo "Item 6 complete."

# ---------------------------------------------------------------------------
# Item 7: git rm dbt-diagnostics files
# ---------------------------------------------------------------------------
echo ""
echo "--- Item 7: git rm dbt-diagnostics files ---"
git rm -r dbt_diagnostics/

echo ""
echo "Item 7 complete."

# ---------------------------------------------------------------------------
# Item 10: Final validation
# ---------------------------------------------------------------------------
echo ""
echo "--- Item 10: Final validation ---"
echo ""

echo "Verifying Makefile dry-run still works..."
make -n iac CONN=admin > /dev/null 2>&1 && echo "OK: make -n iac passes" || echo "FAIL: make -n iac broken!"
make -n loader CONN=admin > /dev/null 2>&1 && echo "OK: make -n loader passes" || echo "FAIL: make -n loader broken!"
make -n down CONN=admin > /dev/null 2>&1 && echo "OK: make -n down passes" || echo "FAIL: make -n down broken!"
echo ""

echo "Verifying archival extraction scripts survived..."
ls scripts/extract_repos.sh scripts/post_extraction_fixup.sh && echo "OK" || echo "FAIL"
echo ""

echo "Verifying artwork-specific scripts survived..."
ls scripts/dbt_orchestrate.sh scripts/manifest.txt scripts/orchestrate.sh && echo "OK" || echo "FAIL"
echo ""

echo "Checking scripts/sql/ still has artwork-specific files..."
ls scripts/sql/ || echo "WARN: scripts/sql/ may be empty"
echo ""

echo "Git status (should show removals + no unexpected changes):"
git status --short | head -30
echo ""
echo "(Total removed files:)"
git status --short | grep -c '^D ' || echo "0"
echo ""

echo "=== Phase 3 Mac execution COMPLETE ==="
echo ""
echo "Next steps:"
echo "  1. Review 'git status' output above"
echo "  2. git add -A && git commit -m 'chore: remove extracted files (now in snowflake-toolkit + dbt-diagnostics)'"
echo "     (Or split into two commits per the plan: Makefile wiring first, removals second)"
echo ""
echo "Suggested two-commit approach:"
echo "  # Commit 1 (if Makefile changes aren't committed yet):"
echo "  git add Makefile"
echo "  git commit -m 'refactor: wire Makefile to consume toolkit from sibling TOOLKIT_DIR'"
echo ""
echo "  # Commit 2 (the removals + doc updates):"
echo "  git add -A"
echo "  git commit -m 'chore: remove extracted files (now in snowflake-toolkit + dbt-diagnostics)'"
