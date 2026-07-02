# Repo Separation: Phase 0 Refactoring Execution Prompt

Paste this entire file into a fresh Cortex Code context window.

---

## Your Role

You are a **Principal Software Engineer** (L7 Google / E7 Meta / L8 Amazon equivalent)
executing a carefully planned codebase refactoring. You have deep expertise in:

- Shell scripting (bash, POSIX compliance, variable expansion, defensive defaults)
- Python CLI patterns (argparse parameterization, backward-compatible refactors)
- Python packaging (`pyproject.toml`, setuptools, editable installs)
- Snowflake CLI/IaC tooling and dbt project lifecycle
- Incremental refactoring (each commit leaves the monorepo fully functional)

Your standards: every edit is minimal and surgical. No behavior changes for
existing callers unless the plan explicitly requires it. No over-engineering.
Every change is testable in isolation. Backward compatibility is preserved via
defaults or `.env` values until the separation switchover (a future session).

---

## CRITICAL: Connection Break Resilience Protocol

Your Cortex Code context can be lost at any time due to connection breaks.
**This prompt has already been re-pasted twice due to connection errors.**
The ONLY way to preserve progress is to execute a tool call.

**Rules (non-negotiable):**

1. **After editing each file**, run a bash command to verify the edit (e.g.,
   `grep -n "the changed line" <file>`). This is your checkpoint.
2. **After completing each numbered item**, append a status line to
   `docs/prompts/REFACTORING_PROGRESS.md`. This is your durable memory.
3. **If resumed after a break:** Read `docs/prompts/REFACTORING_PROGRESS.md`
   first. Skip completed items. Continue from the first incomplete one.
4. **Never batch more than 2 edits** before checkpointing to disk.
5. **Before starting:** Create `docs/prompts/REFACTORING_PROGRESS.md` with all
   items listed as `[ ]` (pending). Update to `[x]` as each completes.

---

## Context: What Has Already Been Decided

The repo separation plan lives at `docs/prompts/REPO_SEPARATION_PLAN.md`.
Key decisions already locked in:

- **3-repo split:** snowflake-toolkit, artwork-db, dbt-diagnostics
- **Model C (sibling repos):** No embedding. artwork-db references toolkit via
  `TOOLKIT_DIR` env var pointing at a sibling directory.
- **This session:** Phase 0 only (refactoring prerequisites). No git extraction.
  No repo creation. The monorepo must still work identically after all edits.
- **Extraction script** already exists at `scripts/extract_repos.sh` (for later).

---

## The Work: Phase 0 Refactoring

You will make 14 edits across 3 groups. Each edit removes artwork-specific
hardcoding so the toolkit files become genuinely generic, while `.env` provides
the artwork-specific values (preserving current behavior for the monorepo).

**Commit strategy:** 3 commits on `donkey-kong-sandbox`:

1. Toolkit generalization (items 1-8)
2. dbt-diagnostics decoupling (items 9-12)
3. artwork-db preparation (items 13-14)

---

### Group 1: Toolkit Generalization (8 items)

#### Item 1: `scripts/snowflake_cli/_lib.sh` line 46

**Current:**
```bash
SNOW_LIB_DEFAULT_WAREHOUSE="${SNOW_LIB_DEFAULT_WAREHOUSE:-ARTWORK_WH}"
```

**Target:**
```bash
SNOW_LIB_DEFAULT_WAREHOUSE="${SNOW_LIB_DEFAULT_WAREHOUSE:-}"
```

No error needed here -- the scripts that consume this variable already handle
empty values or the `.env` will provide it. The default simply becomes "unset"
rather than "ARTWORK_WH". artwork-db's `.env` will set it explicitly (Item 13).

#### Item 2: `scripts/snowflake_cli/06_setup_loader_keypair.sh` lines 47-48

**Current:**
```bash
LOADER_USER="${LOADER_USER:-ARTWORK_LOADER_SVC}"
LOADER_ROLE="${LOADER_ROLE:-ARTWORK_LOADER}"
```

**Target:**
```bash
LOADER_USER="${LOADER_USER:?ERROR: LOADER_USER must be set (e.g. ARTWORK_LOADER_SVC)}"
LOADER_ROLE="${LOADER_ROLE:?ERROR: LOADER_ROLE must be set (e.g. ARTWORK_LOADER)}"
```

Uses bash `${var:?msg}` to fail immediately with a clear message if unset.
artwork-db's `.env` already exports these. No behavior change for existing users.

#### Item 3: `scripts/snowflake_cli/06_setup_loader_keypair.sh` line 53

**Current:**
```bash
SQL_FILE="${SQL_FILE:-${REPO_ROOT}/git-setup/operator/register_loader_public_key.sql}"
```

**Target:**
```bash
SQL_FILE="${SQL_FILE:-${SCRIPT_DIR}/sql/register_service_user_key.sql}"
```

Where `SCRIPT_DIR` is the directory containing 06_setup_loader_keypair.sh
(i.e., `scripts/snowflake_cli/`). `SCRIPT_DIR` is already defined at line 41
of this script; no addition needed. You must also:
- Create `scripts/snowflake_cli/sql/register_service_user_key.sql` containing a
  generic `ALTER USER` template (see below).

**Generic SQL template** (`scripts/snowflake_cli/sql/register_service_user_key.sql`):

The existing `register_loader_public_key.sql` uses snow CLI's `--variable`
substitution syntax: `<% variable_name %>`. The calling script invokes it via
`snow sql --filename ... --variable loader_user=VALUE --variable rsa_public_key=VALUE`.
The generic template must use this same `<% %>` mechanism:

```sql
-- Generic key registration template.
-- Variables substituted by snow CLI --variable at invocation time:
--   <% service_user %>    -- the service user (e.g. ARTWORK_LOADER_SVC)
--   <% rsa_public_key %>  -- the RSA public key body (no PEM header/footer)
ALTER USER <% service_user %> SET RSA_PUBLIC_KEY = '<% rsa_public_key %>';
```

NOTE: The existing artwork-specific file uses `RSA_PUBLIC_KEY` (not `_2`).
The generic template matches this. The calling script must pass
`--variable service_user=... --variable rsa_public_key=...` (updating the
`--variable` flags from `loader_user` to `service_user`).

#### Item 4: `scripts/snowflake_cli/09_setup_transformer_keypair.sh` lines 44-45

**Current:**
```bash
TRANSFORMER_USER="${TRANSFORMER_USER:-ARTWORK_TRANSFORMER_SVC}"
TRANSFORMER_ROLE="${TRANSFORMER_ROLE:-ARTWORK_TRANSFORMER}"
```

**Target:**
```bash
TRANSFORMER_USER="${TRANSFORMER_USER:?ERROR: TRANSFORMER_USER must be set (e.g. ARTWORK_TRANSFORMER_SVC)}"
TRANSFORMER_ROLE="${TRANSFORMER_ROLE:?ERROR: TRANSFORMER_ROLE must be set (e.g. ARTWORK_TRANSFORMER)}"
```

Same pattern as Item 2.

#### Item 5: `scripts/snowflake_cli/09_setup_transformer_keypair.sh` line 50

**Current:**
```bash
SQL_FILE="${SQL_FILE:-${REPO_ROOT}/git-setup/operator/register_transformer_public_key.sql}"
```

**Target:**
```bash
SQL_FILE="${SQL_FILE:-${SCRIPT_DIR}/sql/register_service_user_key.sql}"
```

Reuses the same generic template from Item 3. `SCRIPT_DIR` is already defined
at line 38 of this script; no addition needed.

#### Item 6: `scripts/lib/framework_integration_test.sh` line 207

**Current:** (approximately)
```bash
[[ "$database" == 'ARTWORK_DB' ]]
```

**Target:**
```bash
[[ "$database" == "${TEST_DATABASE:-ARTWORK_DB}" ]]
```

Read the surrounding context (lines 200-215) before editing. The env var allows
the test to work against any database while defaulting to the current behavior.

#### Item 7: `scripts/bootstrap.py`

This is the most complex edit. The script hardcodes `ARTWORK_ADMIN` in ~15 places.

**Functions that reference ARTWORK_ADMIN:**
- `verify_privilege_contract()` -- regex pattern matching GRANT statements
- `fetch_current_grants()` -- log messages
- `assert_account_privileges()` -- log/error messages + calls fetch_current_grants
- The module-level `REQUIRED_ADMIN_ACCOUNT_PRIVILEGES` docstring/comments
- The argparse subcommand definitions (help text + default values)

**Strategy:**
- Add a `--role-name` argument to both subcommands (default: `ARTWORK_ADMIN`)
- Replace all hardcoded `ARTWORK_ADMIN` string literals with the parameter value
- The regex pattern in `verify_privilege_contract()` must use the parameter
- Existing callers pass no `--role-name`, so they get the default -- zero behavior change

**Approach:**
1. Read the full file first
2. Identify every `ARTWORK_ADMIN` occurrence
3. Add `--role-name` to the argparse parsers for both subcommands
4. Thread the value through the functions
5. Verify by running: `python scripts/bootstrap.py verify-contract --help`

#### Item 8: `scripts/activate_mac.sh` lines 7 and 111

Read the file. Remove or generalize artwork-specific references in usage text.
Replace "extraction, dbt" or similar with generic "project environment" language.
This is a cosmetic/docs-only change.

---

### Group 2: dbt-diagnostics Decoupling (4 items)

#### Item 9: `dbt_diagnostics/pyproject.toml` lines 29-30

**Current:**
```toml
[tool.setuptools.packages.find]
where = [".."]
include = ["dbt_diagnostics*"]
```

**Target:**
```toml
[tool.setuptools.packages.find]
where = ["."]
include = ["dbt_diagnostics*"]
```

NOTE: Changing `where` from `[".."]` to `["."]` means the package is found
relative to `pyproject.toml`'s directory. Since `pyproject.toml` currently lives
INSIDE `dbt_diagnostics/`, verify what happens when you run
`pip install -e dbt_diagnostics/` from the repo root. The `where = [".."]` was
a workaround for the nested location. After extraction, `pyproject.toml` moves
to the repo root, so `["."]` is correct. But for NOW (before extraction), this
change might break editable installs from the monorepo. Consider: should this
change wait until extraction, or can we make it work in both contexts?

**Decision rule:** If `pip install -e dbt_diagnostics/` still works after the
change (test it!), proceed. If not, skip this item and mark it as
"deferred to extraction" in the progress file. If deferred, commit Group 2
with the other 3 items complete -- this does not block the commit or
subsequent phases.

#### Item 10: `dbt_diagnostics/config.yml` line 5

**Current:**
```yaml
dbt_project_dir: ../artwork_pipeline
```

**Target:**
```yaml
dbt_project_dir: .
```

This is a runtime default that users override via CLI flag or env var. The tool
will look for dbt artifacts in `.` (current working directory) by default.
Existing users who relied on the `../artwork_pipeline` default will need to pass
`--project-dir ../artwork_pipeline` or run from the artwork_pipeline directory.
Since this is a development tool used interactively, that's acceptable.

#### Item 11: `dbt_diagnostics/config.yml` line 9

**Current:**
```yaml
profile_name: artwork_pipeline
```

**Target:**
```yaml
profile_name: default
```

Same rationale as Item 10. `default` is the conventional dbt profile name.

#### Item 12: `dbt_diagnostics/LINEAGE_TRAIL_PLAN.md`

Read the file. Replace `artwork_pipeline`-specific CLI examples with generic
equivalents (e.g., `my_project` or `<your_project>`). This is docs-only.

---

### Group 3: artwork-db Preparation (2 items)

#### Item 13: `.env.example`

Add the following variables (in a new section near the top, after the Snowflake
Runtime Connection section):

```bash
# --- Toolkit location (sibling repo on disk) ---
# Point this at your local clone of snowflake-toolkit.
# Default: ../snowflake-toolkit (sibling directory)
TOOLKIT_DIR=../snowflake-toolkit

# --- Toolkit configuration (values the toolkit needs from this project) ---
SNOW_LIB_DEFAULT_WAREHOUSE=ARTWORK_WH
LOADER_USER=ARTWORK_LOADER_SVC
LOADER_ROLE=ARTWORK_LOADER
TRANSFORMER_USER=ARTWORK_TRANSFORMER_SVC
TRANSFORMER_ROLE=ARTWORK_TRANSFORMER
```

These make explicit what was previously hardcoded as defaults in the toolkit
scripts. No behavior change -- the values are identical.

#### Item 14: `Makefile`

Add a `TOOLKIT_DIR` variable near the top. For Phase 0 (before extraction), it
should default to the current in-repo path so existing `make` targets continue
working unchanged:

```makefile
# Toolkit scripts -- currently in-repo; after separation, sibling path.
# Override via: TOOLKIT_DIR=../snowflake-toolkit make iac
TOOLKIT_DIR ?= scripts
```

This is a minimal forward-compatible addition. The Makefile targets do NOT
change yet -- they already reference `scripts/` paths. The variable exists so
Phase 3 (switchover) can simply flip the default from `scripts` to
`../snowflake-toolkit` and prefix all toolkit calls with `$(TOOLKIT_DIR)/`.

---

## Execution Protocol

1. **Start by creating** `docs/prompts/REFACTORING_PROGRESS.md` with all 14 items
   listed as `[ ]` pending.

2. **Read each target file** before editing it. Never edit blind.

3. **Edit one item at a time.** After each edit:
   - Run a verification command (grep, python --help, or similar)
   - Update the progress file

4. **After all Group 1 items:** Verify the monorepo still works:
   - `python scripts/bootstrap.py verify-contract --help` (shows --role-name)
   - `grep -c "ARTWORK" scripts/snowflake_cli/_lib.sh` (should decrease by 1)

5. **After all Group 2 items:** Verify dbt-diagnostics:
   - `python -c "import dbt_diagnostics; print('OK')"`
   - Check `config.yml` has no artwork_pipeline reference

6. **After all items:** Report what's ready to commit (do NOT commit without
   owner sign-off, per AGENTS.md gating rule).

---

## What You May NOT Do

- Do NOT commit anything (wait for owner sign-off)
- Do NOT modify any file not listed in the 14 items above
- Do NOT run any `snow sql` or DDL against Snowflake
- Do NOT run `make iac` or any Snowflake-touching command
- Do NOT create new directories outside `scripts/snowflake_cli/sql/`
- Do NOT refactor beyond what's specified (no "while I'm here" cleanups)
- Do NOT delete the `git-setup/operator/register_*.sql` files (artwork-db still
  uses them; they become project-specific overrides post-separation)

---

## Files You Will Read (in likely order)

1. `docs/prompts/REFACTORING_PROGRESS.md` (create if absent, or resume from it)
2. `scripts/snowflake_cli/_lib.sh` (line 46 area)
3. `scripts/snowflake_cli/06_setup_loader_keypair.sh` (lines 47-53 area)
4. `git-setup/operator/register_loader_public_key.sql` (to understand the SQL template mechanism)
5. `scripts/snowflake_cli/09_setup_transformer_keypair.sh` (lines 44-50 area)
6. `scripts/lib/framework_integration_test.sh` (lines 200-215 area)
7. `scripts/bootstrap.py` (full file -- complex edit)
8. `scripts/activate_mac.sh` (lines 1-20 and 100-120 area)
9. `dbt_diagnostics/pyproject.toml` (lines 25-35)
10. `dbt_diagnostics/config.yml` (full file -- 10 lines)
11. `dbt_diagnostics/LINEAGE_TRAIL_PLAN.md` (scan for artwork_pipeline examples)
12. `.env.example` (full file)
13. `Makefile` (top ~30 lines)

---

## Success Criteria

Phase 0 is complete when:

1. All 14 items show `[x]` in the progress file
2. `grep -rn "ARTWORK" scripts/snowflake_cli/ scripts/lib/` returns only:
   - Comment references (not functional defaults)
   - The `activate_mac.sh` if any remain as generic examples
   - The framework_integration_test.sh default in `${TEST_DATABASE:-ARTWORK_DB}`
3. `python scripts/bootstrap.py verify-contract --help` shows `--role-name`
4. `dbt_diagnostics/config.yml` contains no `artwork_pipeline` string
5. `.env.example` contains `TOOLKIT_DIR`, `LOADER_USER`, `LOADER_ROLE`,
   `TRANSFORMER_USER`, `TRANSFORMER_ROLE`, `SNOW_LIB_DEFAULT_WAREHOUSE`
6. `Makefile` has a `TOOLKIT_DIR ?=` line near the top
7. The owner has been presented with the changes for sign-off

---

## Reminder: This Is Phase 0 Only

After this session, the owner will:
- Review and commit the changes (3 logical commits)
- Run `make iac CONN=mk07348` on their Mac to confirm nothing broke
- In a future session, run `scripts/extract_repos.sh` (Phases 1-2)
- In a further session, wire the Makefile to the sibling toolkit (Phase 3)

You are not responsible for those future phases. Focus exclusively on the 14
edits above, done surgically and verified incrementally.
