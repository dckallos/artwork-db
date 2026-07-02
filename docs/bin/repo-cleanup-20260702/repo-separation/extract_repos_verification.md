# Extraction Script Verification: Final Findings

**Date:** 2026-06-07
**Reviewer:** Principal Software Engineer (Cortex Code)
**Script:** `scripts/extract_repos.sh`
**Plan:** `docs/prompts/REPO_SEPARATION_PLAN.md`
**Branch:** `donkey-kong-sandbox`

---

## Executive Summary

The extraction script is **mechanically correct** -- it will produce two repos
with the right files and complete git history. No BLOCKERs exist for running it.
However, 8 HIGH-severity issues mean the extracted repos are **not functional
without follow-up patches** (broken REPO_ROOT calculations, wrong test paths,
invalid executable_files.txt, misplaced pyproject.toml).

**Verdict: YES, safe to run. Follow-up fixup commit required for each repo.**

---

## Findings List

### BLOCKER: None

The extraction script will:
- Clone twice (fresh clones, safe for destructive filter-repo)
- Extract the correct paths for both repos
- Apply rename transforms correctly
- Validate basic success criteria
- Print (not execute) push commands

There is no scenario where running this script produces incorrect git history.

---

### HIGH-1: REPO_ROOT in `scripts/snowflake_cli/04_register_admin_public_key.sh:39`

**What's wrong:** `REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"` -- after
extraction, `snowflake_cli/` is ONE level from root, so `../..` resolves one
directory ABOVE the repo.

**Impact:** Line 60 uses `${REPO_ROOT}/git-setup/operator/register_admin_public_key.sql`
-- this path won't exist in the toolkit (and `git-setup/` stays in artwork-db).
The script will fail at the `[[ -f "${SQL_FILE}" ]]` check with exit 66.

**Fix (post-extraction commit):**
```bash
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SQL_FILE="${SQL_FILE:-${SCRIPT_DIR}/sql/register_admin_public_key.sql}"
```
Plus ship a generic `snowflake_cli/sql/register_admin_public_key.sql` template
(or require callers to set `SQL_FILE` explicitly via env).

---

### HIGH-2: REPO_ROOT in `scripts/snowflake_cli/05_verify_admin_jwt.sh:41`

**Same pattern as HIGH-1.** Line 47:
`SQL_FILE="${SQL_FILE:-${REPO_ROOT}/git-setup/operator/register_admin_public_key.sql}"`.
Breaks identically.

**Fix:** Same as HIGH-1.

---

### HIGH-3: REPO_ROOT in `scripts/snowflake_cli/08_promote_admin_warehouse.sh:55`

**Same pattern.** Line 73:
`SQL_FILE="${SQL_FILE:-${REPO_ROOT}/git-setup/operator/register_admin_public_key.sql}"`.
Breaks identically.

**Fix:** Same as HIGH-1.

**Note on 06 and 09:** These were already fixed in Phase 0 -- they use
`${SCRIPT_DIR}/sql/register_service_user_key.sql` (line 53 in 06, line 50 in
09). The `REPO_ROOT` variable is still computed but is **unused** in 06 and 09.
Dead code, but harmless.

---

### HIGH-4: `scripts/bootstrap.py:42-53` REPO_ROOT + path references

**What's wrong:**
```python
REPO_ROOT = Path(__file__).resolve().parent.parent  # After extraction: one level ABOVE repo
INFRA_DIR = REPO_ROOT / "infrastructure"            # Does not exist in toolkit
ROLES_SQL = INFRA_DIR / "create_roles.sql"          # Does not exist in toolkit
PREFLIGHT_GRANTS_SQL = REPO_ROOT / "scripts" / "sql" / "show_admin_account_grants.sql"
```

**Impact:** `verify-contract` subcommand breaks completely (requires
`infrastructure/create_roles.sql` which lives in artwork-db).
`assert-account-privileges` breaks (the SQL file exists in the toolkit but at
`sql/show_admin_account_grants.sql`, not `scripts/sql/...`).

**Fix (post-extraction commit):**
```python
REPO_ROOT = Path(__file__).resolve().parent  # bootstrap.py is at repo root after extraction
PREFLIGHT_GRANTS_SQL = REPO_ROOT / "sql" / "show_admin_account_grants.sql"
# INFRA_DIR / ROLES_SQL: accept as --roles-sql CLI argument (infra lives in artwork-db)
```

---

### HIGH-5: `scripts/lib/framework_integration_test.sh:36-38`

**What's wrong:**
```bash
readonly REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"       # lib/ is 1 level from root, not 2
readonly TEST_DDL_DIR="${REPO_ROOT}/infrastructure"            # Does not exist in toolkit
readonly TEST_MANIFEST="${REPO_ROOT}/scripts/manifest.txt"    # Does not exist in toolkit
```

**Impact:** Test is completely non-functional post-extraction. `infrastructure/`
and `scripts/manifest.txt` both stay in artwork-db.

**Fix (post-extraction):**
```bash
readonly REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
readonly TEST_DDL_DIR="${FRAMEWORK_TEST_DDL_DIR:-${REPO_ROOT}/infrastructure}"
readonly TEST_MANIFEST="${FRAMEWORK_TEST_MANIFEST:-${REPO_ROOT}/scripts/manifest.txt}"
```

---

### HIGH-6: `tests/examples/basic_project_integration.sh:397-409`

**What's wrong:** Line 397 checks for
`"$framework_source_dir/scripts/orchestrate_modern.sh"`. After extraction,
`orchestrate_modern.sh` is at the repo root, not under `scripts/`. Line 409
copies from `"$framework_source_dir/scripts/orchestrate_modern.sh"` and
`scripts/lib/connection_resolver.sh` -- both paths are wrong post-extraction.

**Fix (post-extraction):**
```bash
if [[ ! -f "$framework_source_dir/orchestrate_modern.sh" ]]; then
    ...
fi
cp "$framework_source_dir/orchestrate_modern.sh" scripts/
cp "$framework_source_dir/lib/connection_resolver.sh" scripts/lib/
```

---

### HIGH-7: `scripts/executable_files.txt` paths

**What's wrong:** All 22 paths use the monorepo structure
(`scripts/snowflake_cli/...`, `scripts/apply_sql.sh`, etc.). After extraction +
rename, these are invalid. `bootstrap_chmod.sh` reads this file to set chmod, so
it would silently skip all entries (file-existence guards in the chmod loop).

**Fix (post-extraction):** Regenerate the file with new paths:
```text
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
snowflake_cli/setup.sh
apply_sql.sh
bootstrap_chmod.sh
check.sh
checkpoint.sh
git_mark_executable.sh
orchestrate_modern.sh
rollback_sql.sh
```

---

### HIGH-8: `dbt-diagnostics` pyproject.toml at wrong level

**What's wrong:** After `git filter-repo --path dbt_diagnostics/`, the repo has:
```
dbt-diagnostics/          (repo root)
  dbt_diagnostics/        (the package directory)
    pyproject.toml         <-- buried inside the package
    __init__.py
    ...
```

`pip install -e .` expects `pyproject.toml` at the repo root. The current
`where = [".."]` (line 30 of pyproject.toml) was designed to work from WITHIN
the monorepo -- it won't resolve correctly from the extracted repo root either.

The separation plan (Section 2.3) explicitly states the target layout:
`dbt_diagnostics/pyproject.toml -> pyproject.toml` (repo root). But the
extraction script has **no** `--path-rename` for this restructuring.

**Fix (either in extraction script OR post-extraction):**
```bash
# Add to the dbt-diagnostics filter-repo second pass:
git filter-repo \
    --path-rename dbt_diagnostics/pyproject.toml:pyproject.toml \
    --path-rename dbt_diagnostics/BUILD_PROMPT.md:BUILD_PROMPT.md \
    --path-rename dbt_diagnostics/CHANGELOG.md:CHANGELOG.md \
    --path-rename dbt_diagnostics/HANDOFF_PROMPT.md:docs/HANDOFF_PROMPT.md \
    --path-rename dbt_diagnostics/HANDOFF_PROMPT_2.md:docs/HANDOFF_PROMPT_2.md \
    --path-rename dbt_diagnostics/LINEAGE_TRAIL_PLAN.md:docs/LINEAGE_TRAIL_PLAN.md \
    --force
```

And update `pyproject.toml`'s `[tool.setuptools.packages.find]`:
```toml
[tool.setuptools.packages.find]
where = ["."]
include = ["dbt_diagnostics*"]
```

---

### LOW-1: Branch scope (all refs included)

**What:** `git filter-repo` operates on ALL refs by default. Both `main` and
`donkey-kong-sandbox` will be in the extracted repos. If `main` has stale
pre-Phase-0 versions of files, those appear in the `main` branch of the
extracted repo (with old hardcoded ARTWORK references).

**Risk:** Low. The extracted repos would be pushed from `donkey-kong-sandbox`
initially. The stale `main` branch is noise but not harmful.

**Fix (optional):**
```bash
git filter-repo --path ... --refs refs/heads/donkey-kong-sandbox --force
```

---

### LOW-2: Sentinel validation gaps

**What:** `validate_extraction()` only checks commit_count > 0 and file_count > 0.
A subtle misconfiguration (e.g., typo in a `--path` argument) would pass if ANY
commits/files remain from other paths.

**Fix (hardening):**
```bash
validate_extraction() {
    local repo_dir="$1"
    local label="$2"
    local sentinel="$3"  # New parameter

    # ... existing checks ...

    if [[ -n "${sentinel}" && ! -f "$repo_dir/$sentinel" ]]; then
        err "$label extraction missing sentinel file: $sentinel"
    fi
}

# Usage:
validate_extraction "$WORK_DIR/$DIAGNOSTICS_REPO_NAME" "dbt-diagnostics" \
    "dbt_diagnostics/__init__.py"
validate_extraction "$WORK_DIR/$TOOLKIT_REPO_NAME" "snowflake-toolkit" \
    "snowflake_cli/_lib.sh"
```

---

### LOW-3: Dead `REPO_ROOT` in 06 and 09

**What:** Both `06_setup_loader_keypair.sh:42` and
`09_setup_transformer_keypair.sh:39` compute `REPO_ROOT` but never use it
(all references were migrated to `SCRIPT_DIR`-relative paths in Phase 0).

**Fix (post-extraction cleanup):** Remove the dead `REPO_ROOT` line from both.

---

### LOW-4: Dev prompt files in dbt-diagnostics

**What:** `CLASSIFIER_FIX_PLAN.md`, `CLASSIFIER_FIX_PROMPT.md` exist in
`dbt_diagnostics/` and will be captured by `--path dbt_diagnostics/`. They're
internal dev prompts -- probably should be in `docs/` or deleted.

---

### LOW-5: Mid-run failure cleanup UX

**What:** If the script fails after extracting dbt-diagnostics but before
completing the toolkit, the user must manually `rm -rf` and re-run. The script
correctly refuses to overwrite but doesn't suggest the cleanup command.

**Fix (cosmetic):**
```bash
err() {
    echo "ERROR: $*" >&2
    echo "  To retry: rm -rf $DIAGNOSTICS_REPO_NAME $TOOLKIT_REPO_NAME" >&2
    exit 1
}
```

---

## Summary Table

| ID     | Severity | Extraction correctness? | Extracted repo usability? |
|--------|----------|------------------------|--------------------------|
| HIGH-1 | HIGH     | Unaffected             | 04 script fails          |
| HIGH-2 | HIGH     | Unaffected             | 05 script fails          |
| HIGH-3 | HIGH     | Unaffected             | 08 script fails          |
| HIGH-4 | HIGH     | Unaffected             | bootstrap.py breaks      |
| HIGH-5 | HIGH     | Unaffected             | Integration test breaks  |
| HIGH-6 | HIGH     | Unaffected             | Example test breaks      |
| HIGH-7 | HIGH     | Unaffected             | chmod has no effect      |
| HIGH-8 | HIGH     | Unaffected             | pip install fails        |
| LOW-1  | LOW      | Unaffected             | Noise (stale main)       |
| LOW-2  | LOW      | Unaffected             | Misses subtle failures   |
| LOW-3  | LOW      | Unaffected             | Dead code                |
| LOW-4  | LOW      | Unaffected             | Cosmetic                 |
| LOW-5  | LOW      | Unaffected             | UX on failure            |

---

## Recommendation

**YES -- the script is safe to run as-is.**

Run `extract_repos.sh` first, then apply a fixup commit to each extracted repo.
The one change worth patching INTO `extract_repos.sh` before running: HIGH-8's
`--path-rename` directives for the dbt-diagnostics pyproject.toml (cheap, aligns
output with the plan, prevents a confusing intermediate state).

---

## Resolution (Applied 2026-06-07)

All findings addressed via two scripts:

### 1. `scripts/extract_repos.sh` (enhanced)

- **HIGH-8 RESOLVED:** Added `--path-rename` directives in the dbt-diagnostics
  second filter-repo pass (pyproject.toml, BUILD_PROMPT.md, CHANGELOG.md, and
  HANDOFF/LINEAGE docs moved to repo root or `docs/`).
- **LOW-2 RESOLVED:** `validate_extraction()` accepts a third `sentinel`
  parameter; checks `snowflake_cli/_lib.sh` (toolkit) and
  `dbt_diagnostics/__init__.py` (diagnostics).
- **NEW:** STEP 3 auto-invokes `post_extraction_fixup.sh` for both repos.
  Invocation passes mode (`toolkit`/`diagnostics`) + full path.
- Header updated to reflect 6-step flow (clone, dbt-extract, toolkit-extract,
  validate, fixup, print push commands).

### 2. `scripts/post_extraction_fixup.sh` (new -- companion fixup script)

Authored pre-extraction, executed post-extraction as STEP 3. Uses sed with `|`
delimiter for reliable pattern replacement.

| Finding | Resolution |
|---------|-----------|
| HIGH-1/2/3 | REPO_ROOT `../../` -> `../` in 04/05/08; SQL_FILE default repointed to `${SCRIPT_DIR}/sql/` |
| HIGH-4 | bootstrap.py: `parent.parent` -> `parent`; PREFLIGHT path; INFRA_DIR env-overridable |
| HIGH-5 | framework_integration_test.sh: REPO_ROOT fixed; TEST_DDL_DIR/TEST_MANIFEST parameterized |
| HIGH-6 | basic_project_integration.sh: `scripts/orchestrate_modern.sh` -> `orchestrate_modern.sh` etc. |
| HIGH-7 | executable_files.txt regenerated with correct post-extraction paths |
| LOW-3 | Dead REPO_ROOT removed from 06/09 |

### Decision: `post_extraction_fixup.sh` -- Written Pre, Run Post

The fixup script is **authored pre-extraction** (committed to the monorepo
alongside `extract_repos.sh`) but **executed post-extraction** by STEP 3.
Rationale:

1. Authoring pre-extraction lets us validate replacement patterns against the
   current monorepo source (we can grep to confirm the old strings exist).
2. Execution post-extraction is the only time the new paths exist to be fixed.
3. `extract_repos.sh` calls it automatically -- user gets functional repos in
   one command. The git log shows a clean separation: all history-preserving
   commits from filter-repo, then one "fix: adapt paths" commit at HEAD.

### Open item: `snowflake_cli/sql/register_admin_public_key.sql`

The SQL_FILE fixup in 04/05/08 repoints the default to
`${SCRIPT_DIR}/sql/register_admin_public_key.sql`. This file does NOT currently
exist in `scripts/snowflake_cli/sql/` (only `register_service_user_key.sql` is
there). Two options:

1. **Copy the SQL from `git-setup/operator/` into the toolkit** (add it to the
   `--path` list in extract_repos.sh with a rename), OR
2. **Require callers to set `SQL_FILE` explicitly** (env var override) when the
   SQL lives outside the toolkit.

Recommendation: option 1 (the SQL is generic; it belongs in the toolkit). This
requires adding one more `--path` + `--path-rename` pair to `extract_repos.sh`.
Deferred to your decision.

