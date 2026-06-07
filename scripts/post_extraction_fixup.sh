#!/usr/bin/env bash
# =============================================================================
# post_extraction_fixup.sh -- Fix path references in extracted repos
# =============================================================================
#
# After extract_repos.sh produces the snowflake-toolkit and dbt-diagnostics
# repos via git filter-repo, the internal path references (REPO_ROOT, source
# paths, executable_files.txt) still reflect the monorepo layout. This script
# applies deterministic sed/rewrite patches so the extracted repos are
# immediately functional.
#
# This script is authored PRE-extraction (alongside extract_repos.sh) but
# EXECUTED post-extraction. It creates one clean commit per repo.
#
# Usage:
#   bash post_extraction_fixup.sh <toolkit|diagnostics> /path/to/extracted-repo
#
# Examples:
#   bash post_extraction_fixup.sh toolkit   ~/projects/snowflake-toolkit
#   bash post_extraction_fixup.sh diagnostics ~/projects/dbt-diagnostics
#
# What it does (toolkit):
#   - HIGH-1/2/3: Fix REPO_ROOT in 04/05/08 (../../ -> ../)
#   - HIGH-1/2/3: Fix SQL_FILE defaults (git-setup/operator/ -> snowflake_cli/sql/)
#   - HIGH-4: Fix bootstrap.py REPO_ROOT + path constants
#   - HIGH-5: Fix framework_integration_test.sh REPO_ROOT + parameterize paths
#   - HIGH-6: Fix basic_project_integration.sh framework paths
#   - HIGH-7: Regenerate executable_files.txt with new paths
#   - LOW-3: Remove dead REPO_ROOT from 06 and 09
#
# What it does (diagnostics):
#   - Fix pyproject.toml setuptools.packages.find where = ["."]
#
# =============================================================================

set -euo pipefail

log() { echo "==> $*"; }
err() { echo "ERROR: $*" >&2; exit 1; }

# --- Argument parsing ---

if [[ $# -lt 2 ]]; then
    echo "Usage: bash post_extraction_fixup.sh <toolkit|diagnostics> /path/to/repo"
    exit 1
fi

MODE="$1"
REPO_DIR="$(cd "$2" && pwd)"

if [[ ! -d "$REPO_DIR/.git" ]]; then
    err "$REPO_DIR is not a git repository"
fi

# =============================================================================
# TOOLKIT FIXUPS
# =============================================================================

fix_toolkit() {
    log "Applying toolkit fixups to: $REPO_DIR"

    # -------------------------------------------------------------------------
    # HIGH-1/2/3: Fix REPO_ROOT + SQL_FILE in snowflake_cli/04, 05, 08
    #
    # REPO_ROOT: After extraction, snowflake_cli/ is ONE level from root (was
    # two under scripts/snowflake_cli/). So ../../ becomes ../
    #
    # SQL_FILE: The default pointed to git-setup/operator/ which stays in
    # artwork-db. Change to SCRIPT_DIR/sql/ (local to toolkit).
    # -------------------------------------------------------------------------

    local scripts_to_fix=(
        "snowflake_cli/04_register_admin_public_key.sh"
        "snowflake_cli/05_verify_admin_jwt.sh"
        "snowflake_cli/08_promote_admin_warehouse.sh"
    )

    for script in "${scripts_to_fix[@]}"; do
        local filepath="$REPO_DIR/$script"
        if [[ ! -f "$filepath" ]]; then
            log "SKIP (not found): $script"
            continue
        fi

        # Fix REPO_ROOT: change /../.. to /..
        # Match the distinctive pattern: SCRIPT_DIR}/../..
        sed -i.bak 's|{SCRIPT_DIR}/\.\./\.\.|{SCRIPT_DIR}/..|g' "$filepath"

        # Fix SQL_FILE: git-setup/operator/ -> SCRIPT_DIR/sql/
        sed -i.bak 's|\${REPO_ROOT}/git-setup/operator/register_admin_public_key\.sql|${SCRIPT_DIR}/sql/register_admin_public_key.sql|g' "$filepath"

        rm -f "$filepath.bak"
        log "FIXED: $script (REPO_ROOT + SQL_FILE)"
    done

    # -------------------------------------------------------------------------
    # HIGH-4: Fix bootstrap.py REPO_ROOT + path constants
    # After extraction, bootstrap.py is at repo root (was scripts/bootstrap.py).
    # -------------------------------------------------------------------------

    local bootstrap="$REPO_DIR/bootstrap.py"
    if [[ -f "$bootstrap" ]]; then
        # Fix REPO_ROOT: parent.parent -> parent (file is at repo root now)
        sed -i.bak 's|\.resolve()\.parent\.parent|.resolve().parent|' "$bootstrap"

        # Fix PREFLIGHT_GRANTS_SQL: scripts/sql/ -> sql/
        sed -i.bak 's|REPO_ROOT / "scripts" / "sql" / "show_admin_account_grants.sql"|REPO_ROOT / "sql" / "show_admin_account_grants.sql"|' "$bootstrap"

        # INFRA_DIR / ROLES_SQL point to infrastructure/ which does NOT exist
        # in the toolkit. Make INFRA_DIR accept an env override so artwork-db
        # can provide its infrastructure/ path at runtime.
        sed -i.bak 's|^INFRA_DIR = REPO_ROOT / "infrastructure"|INFRA_DIR = Path(os.environ.get("TOOLKIT_INFRA_DIR", str(REPO_ROOT / "infrastructure")))|' "$bootstrap"

        rm -f "$bootstrap.bak"
        log "FIXED: bootstrap.py (REPO_ROOT, PREFLIGHT_GRANTS_SQL, INFRA_DIR)"
    fi

    # -------------------------------------------------------------------------
    # HIGH-5: Fix framework_integration_test.sh
    # After extraction, lib/ is ONE level from root (was scripts/lib/ = two).
    # Also parameterize infrastructure/ and manifest.txt paths (they don't exist
    # in the toolkit; they're provided by the consumer project).
    # -------------------------------------------------------------------------

    local fit="$REPO_DIR/lib/framework_integration_test.sh"
    if [[ -f "$fit" ]]; then
        # Fix REPO_ROOT: ../../ -> ../
        sed -i.bak 's|{SCRIPT_DIR}/\.\./\.\.|{SCRIPT_DIR}/..|g' "$fit"

        # Parameterize TEST_DDL_DIR (infrastructure/ lives in artwork-db)
        sed -i.bak 's|TEST_DDL_DIR="${REPO_ROOT}/infrastructure"|TEST_DDL_DIR="${FRAMEWORK_TEST_DDL_DIR:-${REPO_ROOT}/infrastructure}"|' "$fit"

        # Parameterize TEST_MANIFEST (manifest.txt lives in artwork-db)
        sed -i.bak 's|TEST_MANIFEST="${REPO_ROOT}/scripts/manifest.txt"|TEST_MANIFEST="${FRAMEWORK_TEST_MANIFEST:-${REPO_ROOT}/manifest.txt}"|' "$fit"

        rm -f "$fit.bak"
        log "FIXED: lib/framework_integration_test.sh (REPO_ROOT + parameterized paths)"
    fi

    # -------------------------------------------------------------------------
    # HIGH-6: Fix tests/examples/basic_project_integration.sh
    # After extraction, orchestrate_modern.sh is at root (not scripts/),
    # and connection_resolver.sh is at lib/ (not scripts/lib/).
    # -------------------------------------------------------------------------

    local bpi="$REPO_DIR/tests/examples/basic_project_integration.sh"
    if [[ -f "$bpi" ]]; then
        sed -i.bak 's|/scripts/orchestrate_modern\.sh|/orchestrate_modern.sh|g' "$bpi"
        sed -i.bak 's|/scripts/lib/connection_resolver\.sh|/lib/connection_resolver.sh|g' "$bpi"

        rm -f "$bpi.bak"
        log "FIXED: tests/examples/basic_project_integration.sh (framework paths)"
    fi

    # -------------------------------------------------------------------------
    # HIGH-7: Regenerate executable_files.txt with post-extraction paths
    # -------------------------------------------------------------------------

    local exe_file="$REPO_DIR/executable_files.txt"
    cat > "$exe_file" << 'EOF'
# Every .sh in the toolkit that must be mode 0755.
# Read by bootstrap_chmod.sh (chmod policy) and
# git_mark_executable.sh (stages +x into git's index).
# One path per line, relative to repo root. Blank lines and #-comments
# are ignored. This data file is NOT itself executable.
# Keep alphabetized within each subtree for easy diffing.
activate_mac.sh
apply_sql.sh
bootstrap_chmod.sh
check.sh
checkpoint.sh
git_mark_executable.sh
lib/connection_resolver.sh
lib/dbt_orchestrator.sh
lib/ddl_orchestrator.sh
lib/framework_integration_test.sh
lib/legacy_comparison_test.sh
load_profile.sh
orchestrate_modern.sh
rollback_sql.sh
snowflake_cli/_lib.sh
snowflake_cli/00_install_snowflake_cli.sh
snowflake_cli/01_init_snowflake_home.sh
snowflake_cli/02_generate_admin_keypair.sh
snowflake_cli/03_lock_config_permissions.sh
snowflake_cli/04_register_admin_public_key.sh
snowflake_cli/05_verify_admin_jwt.sh
snowflake_cli/06_setup_loader_keypair.sh
snowflake_cli/07_test_loader_connection.sh
snowflake_cli/08_promote_admin_warehouse.sh
snowflake_cli/09_setup_transformer_keypair.sh
snowflake_cli/10_test_transformer_connection.sh
snowflake_cli/init_profile.sh
snowflake_cli/new_account.sh
snowflake_cli/setup.sh
status_profile.sh
tests/examples/basic_project_integration.sh
tests/framework/unit/test_connection_resolver.sh
tests/framework/unit/test_orchestrate_modern.sh
tests/integration/test_multi_account_deployment.sh
unload_profile.sh
EOF
    log "FIXED: executable_files.txt (regenerated with post-extraction paths)"

    # -------------------------------------------------------------------------
    # LOW-3: Remove dead REPO_ROOT from 06 and 09
    # These compute REPO_ROOT but never use it (Phase 0 migrated them to
    # SCRIPT_DIR-relative paths). Remove the dead line.
    # -------------------------------------------------------------------------

    local dead_scripts=(
        "snowflake_cli/06_setup_loader_keypair.sh"
        "snowflake_cli/09_setup_transformer_keypair.sh"
    )

    for script in "${dead_scripts[@]}"; do
        local filepath="$REPO_DIR/$script"
        if [[ -f "$filepath" ]]; then
            # Delete any line that starts with REPO_ROOT= and contains SCRIPT_DIR
            sed -i.bak '/^REPO_ROOT=.*SCRIPT_DIR/d' "$filepath"
            rm -f "$filepath.bak"
            log "FIXED: $script (removed dead REPO_ROOT)"
        fi
    done

    # -------------------------------------------------------------------------
    # Commit all fixups as a single clean commit
    # -------------------------------------------------------------------------

    cd "$REPO_DIR"
    git add -A
    if git diff --cached --quiet; then
        log "No changes to commit (fixups may already be applied)"
    else
        git commit -m "fix: adapt internal paths for standalone toolkit repo

Post-extraction path corrections applied by post_extraction_fixup.sh:
- REPO_ROOT: ../../ -> ../ in snowflake_cli/04, 05, 08 (1 level from root now)
- SQL_FILE: git-setup/operator/ -> snowflake_cli/sql/ (local to toolkit)
- bootstrap.py: parent.parent -> parent, PREFLIGHT_GRANTS_SQL, INFRA_DIR env
- framework_integration_test.sh: REPO_ROOT + parameterized DDL/manifest paths
- basic_project_integration.sh: removed scripts/ prefix from framework paths
- executable_files.txt: regenerated for new layout
- Removed dead REPO_ROOT from 06, 09 (unused since Phase 0)"
        log "Committed fixup (toolkit)"
    fi
}

# =============================================================================
# DIAGNOSTICS FIXUPS
# =============================================================================

fix_diagnostics() {
    log "Applying diagnostics fixups to: $REPO_DIR"

    # -------------------------------------------------------------------------
    # Fix pyproject.toml: where = [".."] -> where = ["."]
    # After extraction + rename, pyproject.toml is at repo root and
    # dbt_diagnostics/ is a direct child.
    # -------------------------------------------------------------------------

    local pyproject="$REPO_DIR/pyproject.toml"
    if [[ -f "$pyproject" ]]; then
        sed -i.bak 's|where = \["\.\."\]|where = ["."]|' "$pyproject"
        rm -f "$pyproject.bak"
        log "FIXED: pyproject.toml (where = [\".\"])"
    else
        log "SKIP: pyproject.toml not found at repo root (check extraction)"
    fi

    # -------------------------------------------------------------------------
    # Commit
    # -------------------------------------------------------------------------

    cd "$REPO_DIR"
    git add -A
    if git diff --cached --quiet; then
        log "No changes to commit (fixups may already be applied)"
    else
        git commit -m "fix: adapt pyproject.toml for standalone repo layout

Post-extraction path correction applied by post_extraction_fixup.sh:
- setuptools packages.find where: ['..'] -> ['.'] (pyproject.toml is now
  at repo root, not inside the package directory)"
        log "Committed fixup (diagnostics)"
    fi
}

# =============================================================================
# DISPATCH
# =============================================================================

case "$MODE" in
    toolkit)
        fix_toolkit
        ;;
    diagnostics)
        fix_diagnostics
        ;;
    *)
        err "Unknown mode: $MODE. Use 'toolkit' or 'diagnostics'."
        ;;
esac

log "Done. Inspect the repo and push when ready."
