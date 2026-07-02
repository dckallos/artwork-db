# Prompt: Verify `extract_repos.sh` Readiness and Quality

Paste this into a fresh Cortex Code window (or Claude session with repo access).

---

## Your Role

You are a **Principal Software Engineer** reviewing a one-time git extraction
script before it runs in production. Your job: identify bugs, gaps, correctness
issues, and risks -- not style nits. The script runs ONCE, produces 2 new repos,
and is then archived. It must work the first time.

---

## Context

**Monorepo:** `artwork-db` on branch `donkey-kong-sandbox`
**Script:** `scripts/extract_repos.sh`
**Purpose:** Splits the monorepo into 3 repos using `git filter-repo`:
  1. `snowflake-toolkit` -- generic Snowflake CLI/IaC framework
  2. `dbt-diagnostics` -- standalone pip-installable dbt debugging CLI
  3. `artwork-db` -- stays as the slimmed primary repo (NOT extracted; just loses files later)

**Phase 0 (already committed):** Generalized all toolkit files to remove artwork-specific
hardcoding. The extraction can now proceed.

**Separation plan:** `docs/prompts/REPO_SEPARATION_PLAN.md` (the source of truth for
which files go where and the intended post-extraction structure).

---

## What to Verify (Checklist)

Read `scripts/extract_repos.sh` and `docs/prompts/REPO_SEPARATION_PLAN.md`, then
answer each question below. For any issue found, provide the fix (not just the diagnosis).

### A. Path Coverage (completeness)

1. **Missing toolkit paths:** Compare the `--path` arguments in STEP 2 against
   the full file listing of `scripts/snowflake_cli/`, `scripts/lib/`, `scripts/sql/`,
   `scripts/` (top-level .sh/.py files), `tests/`, and `docs/framework/`.
   - Are any files listed in Section 2.1 of the separation plan missing from the
     `--path` list?
   - **Known gap to check:** `scripts/snowflake_cli/sql/register_service_user_key.sql`
     was created in Phase 0. Since `--path scripts/snowflake_cli/` captures the whole
     directory tree, is it automatically included? (Answer: yes, `--path dir/` is
     recursive in git-filter-repo.)

2. **Incorrectly included paths:** Are any artwork-specific files captured by the
   directory-level `--path` includes?
   - `tests/` -- does it contain any artwork-specific test files? (Check the actual
     contents: `tests/__init__.py`, `tests/examples/basic_project_integration.sh`,
     `tests/framework/unit/...`, `tests/integration/test_multi_account_deployment.sh`)
   - `docs/framework/` -- are all 8-9 files there generic?

3. **dbt-diagnostics extraction:** It uses `--path dbt_diagnostics/`. Confirm this
   captures everything needed (pyproject.toml is inside that directory, along with
   all source, templates, fixtures, tests, and docs).

### B. Path Rename Correctness (STEP 2, second filter-repo pass)

4. **Rename completeness:** Every `--path` from the first pass must have a
   corresponding `--path-rename` in the second pass. Missing renames leave files
   stranded at their original `scripts/...` paths in the new repo.
   - `scripts/sql/` is renamed to `sql/` -- but the first pass includes 3 individual
     files (`show_active_sessions.sql`, `show_admin_account_grants.sql`, `checkpoint.sql`).
     Does `--path-rename scripts/sql/:sql/` correctly handle these? (It should -- it's
     a prefix rename.)
   - `tests/` and its contents: there's no `--path-rename tests/:...`. This means tests
     stay at `tests/` in the new repo. Is that intentional per the plan? (Yes -- plan
     says "path unchanged".)
   - `docs/framework/` -> `docs/`: confirm this prefix rename doesn't collide if
     other `docs/` paths existed.

5. **Double filter-repo:** The script runs `git filter-repo` TWICE on the same clone.
   Is this safe? (git-filter-repo docs say yes -- second run operates on the already-
   filtered repo. But verify: does the `--force` flag handle the "not a fresh clone"
   warning correctly on the second invocation?)

### C. Branch Handling

6. **Single branch extraction:** The script checks out `donkey-kong-sandbox` before
   filtering. Does `git filter-repo` operate on all branches by default, or only the
   current one? If all branches, do we risk including `main` history that has stale
   (pre-Phase-0) versions of the files?
   - Recommendation: should the script add `--refs refs/heads/donkey-kong-sandbox`
     to limit extraction to one branch?

### D. Structural Correctness of Extracted Repos

7. **snowflake-toolkit post-extraction layout:** After both filter-repo passes, the
   repo should look like:
   ```
   snowflake-toolkit/
     snowflake_cli/          (was scripts/snowflake_cli/)
       _lib.sh
       setup.sh
       sql/register_service_user_key.sql
       ...
     lib/                    (was scripts/lib/)
     sql/                    (was scripts/sql/)
     tests/                  (unchanged)
     docs/                   (was docs/framework/)
     orchestrate_modern.sh   (was scripts/orchestrate_modern.sh)
     apply_sql.sh            (was scripts/apply_sql.sh)
     bootstrap.py            (was scripts/bootstrap.py)
     ...
   ```
   Verify: are internal cross-references (shebangs, source paths, SCRIPT_DIR
   calculations) going to break after the rename? List any files whose internal
   `source "${SCRIPT_DIR}/_lib.sh"` or similar paths will no longer resolve.
   - Key concern: `bootstrap.py` references `INFRA_DIR = REPO_ROOT / "infrastructure"`.
     After extraction, there IS no `infrastructure/` in the toolkit. Is this acceptable?
     (It's only used by the `verify-contract` subcommand which reads the artwork-db's
     `create_roles.sql`. Post-separation, this function only runs FROM artwork-db context
     where TOOLKIT_DIR points here. But the REPO_ROOT calculation inside bootstrap.py
     uses `Path(__file__).resolve().parent.parent` -- after extraction, `__file__` is at
     repo root, so `parent.parent` goes ABOVE the repo. **This is a bug.**)

8. **dbt-diagnostics post-extraction layout:** Should be `dbt_diagnostics/` at repo
   root (since `--path dbt_diagnostics/` preserves the path). The pyproject.toml is
   inside. For `pip install -e .` to work from the repo root, pyproject.toml must be
   at the repo root. Is there a rename step missing? (The plan's Item 9 was deferred --
   does the script need to restructure this, or is that a post-extraction step?)

### E. Validation and Safety

9. **validate_extraction:** It checks commit count > 0 and file count > 0. Should it
   also verify specific sentinel files exist? E.g.:
   - toolkit: `snowflake_cli/_lib.sh` exists
   - dbt-diagnostics: `dbt_diagnostics/__init__.py` exists
   Would adding these catches a subtle filter-repo misconfiguration?

10. **Idempotency / rerunability:** The script fails if output directories exist. Good.
    But if it fails mid-way (e.g., after dbt-diagnostics extraction but before toolkit),
    should it offer a `--resume` or at least suggest cleanup?

11. **Remote handling:** The script prints push commands with hardcoded GitHub remotes.
    Confirm these match what the user actually wants (they may not have created the
    remote repos yet). This is informational-only, so low risk.

### F. Known Issues from Phase 0

12. **`executable_files.txt` paths:** This file lists paths that should be chmod +x.
    After extraction, those paths are relative to the OLD structure (`scripts/...`).
    The file needs updating post-extraction. Is this noted anywhere?

13. **`REPO_ROOT` calculations:** Several scripts compute REPO_ROOT as
    `"$(cd "${SCRIPT_DIR}/../.." && pwd)"` (two levels up from `scripts/snowflake_cli/`).
    After extraction, `snowflake_cli/` is ONE level from root. This means REPO_ROOT
    will point one directory ABOVE the repo. Enumerate all REPO_ROOT calculations and
    assess which break.

---

## Deliverable

Produce a numbered findings list:
- **BLOCKER:** Must fix before running (would produce incorrect output)
- **HIGH:** Should fix (produces technically correct but broken-in-practice repos)
- **LOW:** Nice to have (cosmetic, docs, or post-extraction cleanup)

For each finding, include:
- File and line number
- What's wrong
- Suggested fix (code snippet if applicable)

End with a YES/NO recommendation: "Is this script safe to run as-is, or does it
need patches first?"

---

## Pre-computed Findings (from prior aborted session)

A prior Cortex window read all the files and got most of the way through the
analysis before a connection break. Here are the confirmed findings so far.
**You do NOT need to re-read these files.** Validate these findings, add any
you find missing, and produce the final deliverable.

### BLOCKER-1: REPO_ROOT in `scripts/snowflake_cli/*.sh`

All numbered scripts (04, 05, 06, 08, 09, etc.) compute:
```bash
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
```
This assumes `scripts/snowflake_cli/` is **two levels below** the repo root.
After extraction + rename (`scripts/snowflake_cli/` -> `snowflake_cli/`), the
directory is **one level** from root. `../..` goes ABOVE the repo.

**Used for:** `SQL_FILE` paths (06, 09 already fixed in Phase 0 to use
`SCRIPT_DIR/sql/...` instead of `REPO_ROOT/git-setup/...`). But 04 and 05
still reference `REPO_ROOT/git-setup/operator/register_admin_public_key.sql`
(which won't exist in the toolkit). 08 uses REPO_ROOT for... (check this).

**Fix:** After extraction, change to `REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"`.
Or better: remove REPO_ROOT usage entirely in favor of SCRIPT_DIR-relative paths
(which Phase 0 already started for 06/09). This is a POST-extraction patch, not a
blocker for the extraction script itself -- the script correctly captures history.
The extracted repo just needs a follow-up commit.

**Verdict:** Not a blocker for `extract_repos.sh` running correctly. It IS a
HIGH for the extracted repo being functional without a follow-up patch.

### BLOCKER-2: `bootstrap.py` REPO_ROOT calculation

```python
REPO_ROOT = Path(__file__).resolve().parent.parent
INFRA_DIR = REPO_ROOT / "infrastructure"
ROLES_SQL = INFRA_DIR / "create_roles.sql"
PREFLIGHT_GRANTS_SQL = REPO_ROOT / "scripts" / "sql" / "show_admin_account_grants.sql"
```

After extraction, `bootstrap.py` moves to the toolkit repo ROOT. So
`Path(__file__).parent.parent` goes one level ABOVE the repo. And
`infrastructure/` does not exist in the toolkit at all -- it stays in artwork-db.

**Impact:** `verify-contract` subcommand breaks (reads `create_roles.sql`).
`assert-account-privileges` breaks (reads `show_admin_account_grants.sql`
which DOES exist in the toolkit but at `sql/` not `scripts/sql/`).

**Fix (post-extraction):**
```python
REPO_ROOT = Path(__file__).resolve().parent  # bootstrap.py is now at repo root
PREFLIGHT_GRANTS_SQL = REPO_ROOT / "sql" / "show_admin_account_grants.sql"
# INFRA_DIR / ROLES_SQL: accept as CLI argument or env var (infra is in artwork-db)
```

**Verdict:** Same as BLOCKER-1 -- extraction produces correct history, but the
extracted repo needs a follow-up commit. Not a blocker for the script running.

### HIGH-1: `scripts/lib/framework_integration_test.sh` REPO_ROOT

Line 36: `REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"` -- currently
`scripts/lib/../..` = repo root. After extraction, `lib/` is one level from
root, so `../..` goes above.

Lines 37-38 reference `infrastructure/` and `scripts/manifest.txt` -- neither
exists in the toolkit.

### HIGH-2: `tests/examples/basic_project_integration.sh` path references

Line ~397 references `"$framework_source_dir/scripts/orchestrate_modern.sh"`.
After extraction, orchestrate_modern.sh is at the repo root, not under `scripts/`.
The test would fail.

### HIGH-3: `executable_files.txt` paths

All paths are relative to the monorepo structure (`scripts/snowflake_cli/...`,
`scripts/orchestrate_modern.sh`, etc.). After extraction + rename, these paths
are wrong. Needs updating post-extraction.

### HIGH-4: `dbt-diagnostics` pyproject.toml at wrong level

After `git filter-repo --path dbt_diagnostics/`, the repo structure is:
```
dbt-diagnostics/          (repo root)
  dbt_diagnostics/        (the only directory)
    __init__.py
    pyproject.toml         <-- INSIDE the package, not at repo root
    ...
```
`pip install -e .` from the repo root won't find pyproject.toml. It needs to
be moved to the repo root. This was Item 9 (deferred from Phase 0). The
extraction script should either:
- Add a `--path-rename` to move pyproject.toml up, OR
- Note this as a required post-extraction step.

### LOW-1: Branch scope

`git filter-repo` operates on ALL refs by default, not just the checked-out
branch. If `main` has stale pre-Phase-0 versions, those commits are included.
Consider adding `--refs refs/heads/donkey-kong-sandbox` to limit scope.

### LOW-2: `snowflake_cli/sql/register_service_user_key.sql`

Automatically included via `--path scripts/snowflake_cli/` (which is recursive).
Renamed correctly via `--path-rename scripts/snowflake_cli/:snowflake_cli/`.
**No issue** -- just confirming.

### LOW-3: Sentinel validation

`validate_extraction()` only checks commit_count > 0 and file_count > 0.
Suggesting adding:
```bash
# For toolkit:
[[ -f "$repo_dir/snowflake_cli/_lib.sh" ]] || err "Sentinel missing: snowflake_cli/_lib.sh"
# For dbt-diagnostics:
[[ -f "$repo_dir/dbt_diagnostics/__init__.py" ]] || err "Sentinel missing"
```

---

## Summary for Next Window

The extraction script itself is **mechanically correct** -- it will run, filter
history, rename paths, and produce two repos with the right files. However, the
extracted repos will NOT be immediately functional without follow-up patches
(REPO_ROOT calculations, executable_files.txt, pyproject.toml location, test paths).

**Key question for you to answer:** Should the extraction script be enhanced to
apply these follow-up patches automatically (via a STEP 3 that runs `sed` or
commits fixes)? Or should they be separate manual commits after inspection?

Recommendation: Keep `extract_repos.sh` as a pure git-history tool. Create a
companion `post_extraction_fixup.sh` that applies the REPO_ROOT / path fixes
as a fresh commit on each extracted repo. This separates concerns cleanly.

