# Phase 3: Wire artwork-db to Sibling Toolkit + Remove Extracted Files

Paste this entire file into a fresh Claude Code or Cortex Code context window.

---

## Your Role

You are a **Principal Software Engineer** executing the switchover that makes
artwork-db consume the snowflake-toolkit as a sibling repo instead of containing
it. You have deep expertise in:

- Makefile patterns (GNU Make, conditionals, `define` blocks, `$(wildcard)`)
- Shell scripting (bash, POSIX, defensive quoting)
- `git rm` bulk operations with history preservation
- dbt project wiring and Python packaging conventions

Your standards: every edit is minimal and surgical. The Makefile must work
identically before and after (same `make iac`, `make loader`, etc. behavior),
just sourcing scripts from `$(TOOLKIT_DIR)` instead of local paths. The `git rm`
step only removes files that now live in the sibling repos -- nothing else.

---

## CRITICAL: Connection Break Resilience Protocol

Your context can be lost at any time due to connection breaks.

**Rules (non-negotiable):**

1. **After editing each file**, run a verification command (e.g.,
   `grep -n "the changed line" <file>` or `make -n iac`). This is your checkpoint.
2. **After completing each numbered item**, append a status line to
   `docs/prompts/PHASE3_PROGRESS.md`. This is your durable memory.
3. **If resumed after a break:** Read `docs/prompts/PHASE3_PROGRESS.md` first.
   Skip completed items. Continue from the first incomplete one.
4. **Never batch more than 2 edits** before checkpointing to disk.
5. **Before starting:** Create `docs/prompts/PHASE3_PROGRESS.md` with all items
   listed as `[ ]` (pending). Update to `[x]` as each completes.

---

## Context: What Has Already Happened

The repo separation plan lives at `docs/prompts/REPO_SEPARATION_PLAN.md`.
Phases 0-2 are COMPLETE:

- **Phase 0 (DONE):** All toolkit files were generalized (artwork-specific
  hardcoding removed; env vars provide the values). Committed on
  `donkey-kong-sandbox`.
- **Phase 1 (DONE):** `dbt-diagnostics` extracted via `git filter-repo` and
  pushed to `github.com/dckallos/dbt-diagnostics` (branch:
  `donkey-kong-sandbox`). `pip install -e .` and `dbt-diagnostics --help`
  verified working.
- **Phase 2 (DONE):** `snowflake-toolkit` extracted via `git filter-repo` and
  pushed to `github.com/dckallos/snowflake-toolkit` (branch:
  `donkey-kong-sandbox`). Post-extraction fixups applied (REPO_ROOT, SQL_FILE,
  bootstrap.py, executable_files.txt, etc.).
- **The monorepo still has all the original files.** Nothing has been removed
  yet. Both sibling repos exist at `~/dev/snowflake-toolkit` and
  `~/dev/dbt-diagnostics`.

**This session: Phase 3 -- the switchover.** After this, artwork-db references
the toolkit from its sibling directory and the extracted files are gone.

---

## Pre-conditions (verify before starting)

Run these and confirm all pass before making any edits:

```bash
# 1. Toolkit sibling exists
ls ~/dev/snowflake-toolkit/snowflake_cli/_lib.sh

# 2. dbt-diagnostics sibling exists
ls ~/dev/dbt-diagnostics/dbt_diagnostics/__init__.py

# 3. artwork-db is on the right branch
cd ~/dev/artwork-db && git branch --show-current
# Expected: donkey-kong-sandbox

# 4. Working tree is clean
git status --short
# Expected: empty (nothing uncommitted)
```

---

## The Work: Phase 3 Switchover (10 items, 2 commits)

### Commit 1: Wire Makefile to sibling toolkit (items 1-5)

The Makefile is already ~80% wired (it has `TOOLKIT_DIR`, the fail-fast guard,
and uses `$(TOOLKIT_DIR)` for `chmod`, `iac`, `infra`, and `loader`). The
remaining targets still use `scripts/orchestrate_modern.sh` or
`scripts/snowflake_cli/` directly. Fix them.

#### Item 1: `Makefile` line 104 -- `transformer` target

**Current:**
```makefile
  bash scripts/snowflake_cli/setup.sh --profile $(CONN) --phase transformer
```

**Change to:**
```makefile
  bash $(TOOLKIT_DIR)/snowflake_cli/setup.sh --profile $(CONN) --phase transformer
```

#### Item 2: `Makefile` lines 113, 117, 121 -- `rollback`, `down`, `down-from`

These three targets use `bash scripts/orchestrate_modern.sh`. Change all three to
`bash $(TOOLKIT_DIR)/orchestrate_modern.sh`. The arguments stay the same.

#### Item 3: `Makefile` lines 203-204 -- `run_bootstrap` define block

**Current:**
```makefile
    bash -c 'vars="$(2)"; cmd="bash scripts/orchestrate_modern.sh ..."; ...',\
    bash scripts/orchestrate_modern.sh ...)
```

**Change to:**
```makefile
    bash -c 'vars="$(2)"; cmd="bash $(TOOLKIT_DIR)/orchestrate_modern.sh ..."; ...',\
    bash $(TOOLKIT_DIR)/orchestrate_modern.sh ...)
```

Note: preserve the `$(1)` and `$(2)` Make function args -- those are NOT shell vars.

#### Item 4: Verify the wiring works (dry-run)

```bash
# Dry-run (prints commands without executing them):
make -n iac CONN=admin
make -n loader CONN=admin
make -n transformer CONN=admin
make -n down CONN=admin
```

All printed commands should reference `../snowflake-toolkit/...` (the resolved
TOOLKIT_DIR), NOT `scripts/...`. If any still show `scripts/`, you missed one.

#### Item 5: Verify the fail-fast guard fires

```bash
# Temporarily break the path to confirm the guard works:
make -n iac TOOLKIT_DIR=/nonexistent 2>&1 | head -3
# Expected: "snowflake-toolkit not found at /nonexistent..."
```

---

### Commit 2: Remove extracted files from artwork-db (items 6-10)

These files now live in `snowflake-toolkit` or `dbt-diagnostics`. They are
redundant in artwork-db. The `dbt_orchestrate.sh` and `dbt_orchestrate_modern.sh`
scripts are artwork-SPECIFIC (they stay). `manifest.txt` stays (artwork deploy
ordering). `orchestrate.sh` (legacy) stays until fully replaced.

#### Item 6: `git rm` toolkit files (scripts that moved to snowflake-toolkit)

```bash
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
```

**DO NOT remove:**
- `scripts/orchestrate.sh` -- legacy, still referenced
- `scripts/dbt_orchestrate.sh` -- artwork-specific
- `scripts/dbt_orchestrate_modern.sh` -- artwork-specific
- `scripts/manifest.txt` -- artwork deploy ordering
- `scripts/secret_bearing.txt` -- artwork-specific
- `scripts/sql/show_pipeline_status.sql` -- artwork-specific
- `scripts/sql/show_run_control.sql` -- artwork-specific
- `scripts/extract_repos.sh` -- the extraction tool itself (archival)
- `scripts/post_extraction_fixup.sh` -- companion (archival)

#### Item 7: `git rm` dbt-diagnostics files

```bash
git rm -r dbt_diagnostics/
```

**DO NOT remove:**
- `inject_failures.py` -- generates fixtures FROM artwork_pipeline
- `inject_failures.sh` -- E2E fixture runner

#### Item 8: Update `.env.example` if needed

The `.env.example` already has `TOOLKIT_DIR=../snowflake-toolkit` (line 26) and
the toolkit configuration vars (lines 29-33). Confirm it's correct -- no changes
should be needed. If it still references any removed file paths, fix them.

#### Item 9: Update any remaining references

Check for dangling references to removed paths:

```bash
grep -rn "scripts/orchestrate_modern\|scripts/snowflake_cli\|scripts/lib/" . \
  --include='*.md' --include='*.sh' --include='Makefile' --include='*.py' \
  | grep -v '.git/' | grep -v 'docs/prompts/' | grep -v 'SEPARATION_PROGRESS'
```

Common places:
- `CLAUDE.md` -- update `Common commands` section (setup.sh path, etc.)
- `AGENTS.md` -- if it references `scripts/snowflake_cli/setup.sh`

Fix any found references to point at `$(TOOLKIT_DIR)/...` (in Makefiles) or
describe the sibling-repo relationship (in docs).

#### Item 10: Final validation

```bash
# Confirm no broken internal refs in Makefile
make -n iac CONN=admin
make -n loader CONN=admin
make -n down CONN=admin

# Confirm extraction scripts are still present (archival)
ls scripts/extract_repos.sh scripts/post_extraction_fixup.sh

# Confirm artwork-specific scripts survived
ls scripts/dbt_orchestrate.sh scripts/manifest.txt scripts/orchestrate.sh

# Confirm no dangling scripts/sql/ directory emptied
ls scripts/sql/

# git status should show only the removals + Makefile edit
git status
```

---

## Commit Strategy

Two commits on `donkey-kong-sandbox`:

1. **`refactor: wire Makefile to consume toolkit from sibling TOOLKIT_DIR`**
   - Only the Makefile changes (items 1-3)
   - Monorepo still works (toolkit files still exist as fallback)

2. **`chore: remove extracted files (now in snowflake-toolkit + dbt-diagnostics)`**
   - All `git rm` operations (items 6-7)
   - Any doc/reference updates (items 8-9)
   - After this commit, `make iac` REQUIRES the sibling toolkit to exist

**Do NOT squash these.** Keeping them separate allows reverting just the removal
if the sibling wiring has an issue, without losing the Makefile improvement.

---

## Rollback

If anything goes wrong after commit 2:

```bash
git revert HEAD    # Restores removed files
git revert HEAD~1  # Reverts Makefile (if needed)
```

The sibling repos are unaffected -- they're independent clones.

---

## Post-Phase-3 (do NOT do now -- record for next session)

- Phase 4: Update AGENTS.md and CLAUDE.md to reflect the slimmed repo structure
- Phase 4: Add `dbt-diagnostics` as optional dev dependency in requirements.txt
  (GitHub URL or `pip install -e ../dbt-diagnostics`)
- Consider: merge `donkey-kong-sandbox` to `main` across all 3 repos
- Consider: archive `scripts/extract_repos.sh` + `post_extraction_fixup.sh`
  (they've served their purpose)
