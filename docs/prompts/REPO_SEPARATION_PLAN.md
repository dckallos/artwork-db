# Repository Separation Plan

> **Status:** PLAN ONLY -- no code changes, no git operations, no DDL.
> **Date:** 2026-06-07 (updated 2026-06-07: locked Model C sibling-repo approach)
> **Branch:** `donkey-kong-sandbox`
> **Author:** Cortex Code (Principal Engineer analysis)

---

## 1. Executive Summary

### Target repositories (3-repo split)

```text
~/projects/
  snowflake-toolkit/        (GENERIC: reusable across any SF project)
      Depends on: nothing

  artwork-db/               (DOMAIN: museum pipeline IaC + ETL + dbt)
      Depends on: snowflake-toolkit via TOOLKIT_DIR env var / Makefile path

  dbt-diagnostics/          (INDEPENDENT: pip-installable CLI tool)
      Depends on: nothing (runtime config points at any dbt project)
```

### Consumption model: sibling repos (Model C -- DECIDED)

The three repos live as **independent sibling directories** on disk. artwork-db
references snowflake-toolkit via a `TOOLKIT_DIR` environment variable (defaulting
to `../snowflake-toolkit`). There is no embedding, no git subtree, no submodule.
Each repo has fully independent git history with zero interleaving.

```text
artwork-db ----sources scripts from----> snowflake-toolkit (sibling on disk)
artwork-db ----dev-depends (pip)-------> dbt-diagnostics (sibling on disk)
dbt-diagnostics ----0 deps------------> (standalone)
snowflake-toolkit ----0 deps----------> (standalone)
```

### Why Model C over subtree/submodule

- Single developer actively iterating on both repos simultaneously
- Clean independent git histories (no merge-commit noise, no SHA pointer bumps)
- `TOOLKIT_DIR` is a one-line `.env` entry -- trivial wiring
- No "clone must be self-contained" requirement (you control the machine)
- Editing the toolkit doesn't require push/pull/subtree-dance -- just save and run

### Why 3 repos, not 2 or 4

**2-repo** (toolkit + everything else):
dbt-diagnostics is already pip-installable and has its own test suite, versioning,
changelog. Bundling it with artwork couples release cadences unnecessarily.

**3-repo** (toolkit + artwork + dbt-diagnostics) -- **Decided:**
Clean ownership: toolkit = infra plumbing reusable by future projects;
artwork = domain pipeline (DDL + extraction + dbt are deployed together, same
lifecycle); dbt-diagnostics = standalone tool.

**4-repo** (toolkit + artwork-iac + artwork-pipeline + dbt-diagnostics):
Over-split. `infrastructure/` and `artwork_pipeline/` share a deploy lifecycle
(`make iac` then `make dbt-build`), the same `.env`, the same Snowflake objects.
Splitting them doubles the coordination cost for zero ownership-boundary gain
(single developer).

---

## 2. Detailed File Assignment

### 2.1 snowflake-toolkit (new repo)

**Purpose:** Generic, reusable Snowflake CLI bootstrap, connection management,
and DDL orchestration framework. Works with ANY Snowflake project.

**CLI bootstrap scripts** (`scripts/snowflake_cli/` -> `snowflake_cli/`):

- `_lib.sh` -- REFACTOR: remove `ARTWORK_WH` default (use `COMPUTE_WH` or require env)
- `setup.sh` -- Generic
- `init_profile.sh` -- Generic
- `new_account.sh` -- Generic
- `00_install_snowflake_cli.sh` -- Generic
- `01_init_snowflake_home.sh` -- Generic
- `02_generate_admin_keypair.sh` -- Generic
- `03_lock_config_permissions.sh` -- Generic
- `04_register_admin_public_key.sh` -- Generic
- `05_verify_admin_jwt.sh` -- Generic
- `06_setup_loader_keypair.sh` -- Already env-overridable (LOADER_USER/LOADER_ROLE)
- `07_test_loader_connection.sh` -- Generic
- `08_promote_admin_warehouse.sh` -- Generic
- `09_setup_transformer_keypair.sh` -- Already env-overridable (TRANSFORMER_USER/TRANSFORMER_ROLE)
- `10_test_transformer_connection.sh` -- Generic
- `README.md` -- Update for standalone context

**Framework library** (`scripts/lib/` -> `lib/`):

- `connection_resolver.sh` -- Generic
- `ddl_orchestrator.sh` -- Deprecated stub; keep for migration compatibility
- `dbt_orchestrator.sh` -- Deprecated stub; keep for migration compatibility
- `framework_integration_test.sh` -- REFACTOR: remove line 207 ARTWORK_DB hardcode
- `legacy_comparison_test.sh` -- Generic (compares old vs new orchestration)

**Root-level orchestration scripts** (`scripts/` -> repo root):

- `orchestrate_modern.sh` -- Generic (reads --ddl-dir + --manifest from caller)
- `apply_sql.sh` -- Generic
- `rollback_sql.sh` -- Generic
- `bootstrap.py` -- REFACTOR: parameterize role name (currently hardcodes ARTWORK_ADMIN)
- `bootstrap_chmod.sh` -- Generic
- `activate_mac.sh` -- REFACTOR: remove artwork-specific usage text
- `load_profile.sh` -- Generic
- `unload_profile.sh` -- Generic
- `status_profile.sh` -- Generic
- `check.sh` -- Generic
- `checkpoint.sh` -- Generic (writes to any run_control table)
- `git_mark_executable.sh` -- Generic
- `executable_files.txt` -- REFACTOR: paths relative to new structure

**SQL helpers** (`scripts/sql/` -> `sql/`):

- `show_active_sessions.sql` -- Generic
- `show_admin_account_grants.sql` -- Generic
- `checkpoint.sql` -- Generic

**Tests** (path unchanged):

- `tests/framework/` -- Generic framework tests
- `tests/examples/basic_project_integration.sh` -- Generic
- `tests/integration/test_multi_account_deployment.sh` -- Generic
- `tests/__init__.py` -- Generic

**Documentation** (`docs/framework/` -> `docs/`):

- All 8 framework doc files

**NOT included in toolkit:**

- `scripts/orchestrate.sh` -- legacy; retained in artwork-db until `orchestrate_modern.sh` fully replaces it
- `scripts/manifest.txt` -- artwork-specific ordering
- `scripts/secret_bearing.txt` -- artwork-specific file list
- `scripts/dbt_orchestrate.sh` -- artwork-specific
- `scripts/dbt_orchestrate_modern.sh` -- artwork-specific (wraps toolkit for artwork)
- `scripts/sql/show_pipeline_status.sql` -- artwork-specific
- `scripts/sql/show_run_control.sql` -- artwork-specific

### 2.2 artwork-db (stays as primary repo, slimmed)

**Purpose:** The museum artwork medallion pipeline -- Snowflake DDL, Met/CMA/AIC
extraction, dbt models, operational SQL, and the project-specific orchestration
that ties it together.

**Domain directories** (path unchanged):

- `infrastructure/` (all 29 files) -- Domain DDL
- `extraction/` (all files) -- Domain ETL
- `artwork_pipeline/` (all files) -- Domain dbt project
- `operations/` -- Operational SQL
- `git-setup/` (all files) -- In-Snowflake Git mirror for this project
- `analysis/` -- Diagnostic SQL

**Project-specific scripts** (under `scripts/`):

- `orchestrate.sh` -- Legacy orchestrator (until modernized)
- `dbt_orchestrate.sh` -- Artwork dbt lifecycle
- `dbt_orchestrate_modern.sh` -- Modern artwork dbt lifecycle
- `manifest.txt` -- Artwork-specific apply order
- `secret_bearing.txt` -- Artwork-specific secrets list
- `sql/show_pipeline_status.sql` -- Artwork-specific
- `sql/show_run_control.sql` -- Artwork-specific

**Root-level project files:**

- `inject_failures.py` -- Fixture generation for dbt-diagnostics
- `inject_failures.sh` -- E2E fixture runner
- `Makefile` -- REFACTOR: add TOOLKIT_DIR pointing at sibling repo
- `.env.example` -- Artwork-specific env vars (including TOOLKIT_DIR)
- `profiles.yml.example` -- dbt profile template
- `requirements.txt` -- Python deps for extraction
- `.gitignore` -- Keep
- `LICENSE` -- Keep (or dual-license if toolkit gets its own)
- `AGENTS.md` -- REFACTOR: remove toolkit references
- `CLAUDE.md` -- REFACTOR: update for slimmed repo
- `infrastructure/CLAUDE.md` -- Keep
- `setup-claude-code.sh` -- AI tooling setup
- `.claude/` -- AI config
- `.mcp.json` -- AI config

**Documentation:**

- `docs/context/` (all non-framework docs) -- Project context (learning journals, plans, etc.)
- `docs/prompts/` -- Keep

**Toolkit integration:** artwork-db's Makefile resolves the toolkit via
`TOOLKIT_DIR` (defaults to `../snowflake-toolkit`). No files from the toolkit
live inside this repo. See Section 3.

### 2.3 dbt-diagnostics (new repo)

**Purpose:** Standalone, pip-installable dbt error diagnostics CLI. Works with
any dbt project on Snowflake.

**Extracted files:**

- `dbt_diagnostics/` (entire tree) -> `dbt_diagnostics/` (or root-level `src/`)
  All source + tests + fixtures
- `dbt_diagnostics/pyproject.toml` -> `pyproject.toml`
  REFACTOR: fix `where` in setuptools config
- `dbt_diagnostics/config.yml` -> `dbt_diagnostics/config.yml`
  REFACTOR: make paths configurable defaults
- `dbt_diagnostics/BUILD_PROMPT.md` -> `BUILD_PROMPT.md`
- `dbt_diagnostics/CHANGELOG.md` -> `CHANGELOG.md`
- `dbt_diagnostics/HANDOFF_PROMPT.md` -> `docs/`
- `dbt_diagnostics/HANDOFF_PROMPT_2.md` -> `docs/`
- `dbt_diagnostics/LINEAGE_TRAIL_PLAN.md` -> `docs/`

**What stays behind in artwork-db:**

- `inject_failures.py` / `inject_failures.sh` -- these generate fixtures FOR
  dbt-diagnostics but FROM artwork_pipeline models. They belong to the project
  that owns the models.

---

## 3. Dependency Contracts

### 3.1 snowflake-toolkit exposes (public interface)

The toolkit is consumed via filesystem path. The consuming project sets
`TOOLKIT_DIR` to point at the toolkit's clone directory. Its public interface:

**`snowflake_cli/setup.sh`** -- Entry point.
Accepts `--profile`, `--phase`, `--admin-conn`, `--loader-conn`, `--transformer-conn`.
Phases: `all`, `install`, `init`, `keypair`, `register`, `verify`, `promote`,
`loader`, `transformer`.

**`snowflake_cli/_lib.sh`** -- Sourceable library. Exports functions.
Env overrides: `SNOW_LIB_DEFAULT_WAREHOUSE`, `SNOW_LIB_CONFIG_TOML`,
`SNOW_LIB_CONNECTIONS_TOML`, `SNOW_LIB_KEY_DIR`, `ADMIN_CONN`, `LOADER_CONN`,
`TRANSFORMER_CONN`.

**`orchestrate_modern.sh`** -- CLI:
`--ddl-dir DIR --manifest FILE --phase PHASE --connection CONN [--file FILE] [--from FILE] [--var K=V]`.
Generic DDL orchestration.

**`apply_sql.sh` / `rollback_sql.sh`** -- Low-level: apply/rollback a single
.sql file via `snow sql`.

**`bootstrap.py`** -- Subcommands:
`verify-contract --role-name ROLE --roles-sql PATH`,
`assert-account-privileges --connection CONN --role-name ROLE`.

**`lib/connection_resolver.sh`** -- Sourceable. Connection resolution for
framework components.

**Environment variables (toolkit reads, consumer sets):**

- `SNOW_LIB_DEFAULT_WAREHOUSE` -- default warehouse (no artwork default after refactor)
- `LOADER_USER`, `LOADER_ROLE` -- service user for loader keypair
- `TRANSFORMER_USER`, `TRANSFORMER_ROLE` -- service user for transformer keypair
- `SNOW_CONNECTION` -- default snow CLI connection name

### 3.2 artwork-db consumes toolkit (sibling path)

The Makefile in artwork-db resolves the toolkit from a sibling directory:

```makefile
# Resolve toolkit: env var > .env > default sibling path
TOOLKIT_DIR ?= $(shell echo $${TOOLKIT_DIR:-../snowflake-toolkit})

iac: chmod
	bash $(TOOLKIT_DIR)/orchestrate_modern.sh \
	  --ddl-dir infrastructure/ \
	  --manifest scripts/manifest.txt \
	  --phase infra \
	  --connection $(CONN)
```

The `.env` in artwork-db sets all toolkit env vars:

```bash
# Toolkit location (sibling repo on disk)
TOOLKIT_DIR=../snowflake-toolkit

# Toolkit configuration
SNOW_LIB_DEFAULT_WAREHOUSE=ARTWORK_WH
LOADER_USER=ARTWORK_LOADER_SVC
LOADER_ROLE=ARTWORK_LOADER
TRANSFORMER_USER=ARTWORK_TRANSFORMER_SVC
TRANSFORMER_ROLE=ARTWORK_TRANSFORMER
```

**Fail-fast guard:** The Makefile errors immediately if `TOOLKIT_DIR` doesn't
exist, with a clear message:

```makefile
ifeq ($(wildcard $(TOOLKIT_DIR)/snowflake_cli/setup.sh),)
  $(error snowflake-toolkit not found at $(TOOLKIT_DIR). Clone it as a sibling: git clone ... ../snowflake-toolkit)
endif
```

### 3.3 dbt-diagnostics is standalone

- Zero import-time dependencies on artwork-db or snowflake-toolkit.
- `config.yml` ships with example defaults (`dbt_project_dir: .` or user-provided path).
- Fixtures contain `model.artwork_pipeline.*` unique IDs -- these are data strings
  used in tests, not import paths. They remain as realistic test data.
- Users point it at any dbt project via `--project-dir` CLI flag or config.yml override.

### 3.4 How artwork-db uses dbt-diagnostics (optional dev dependency)

```bash
# In artwork-db's dev workflow:
pip install -e ../dbt-diagnostics  # editable install from sibling
dbt-diagnostics --project-dir artwork_pipeline/

# Fixture generation (stays in artwork-db):
python inject_failures.py --change 3
dbt run --select stg_met__artworks
# Copy target/run_results.json to ../dbt-diagnostics/fixtures/
python inject_failures.py --discard-change 3
```

---

## 4. Git History Strategy

### 4.1 Tool choice: `git filter-repo`

| Method | When appropriate | Our case |
|--------|-----------------|----------|
| `git filter-repo --path` | Multiple non-contiguous paths | **snowflake-toolkit** |
| `git subtree split --prefix` | Single contiguous subtree | **dbt-diagnostics** |
| Fresh repo + squashed history | History not valuable | NOT recommended |

### 4.2 Extraction commands

#### dbt-diagnostics (simplest -- single prefix)

```bash
# Fresh clone (filter-repo is destructive)
git clone artwork-db dbt-diagnostics-extract
cd dbt-diagnostics-extract
git checkout donkey-kong-sandbox

# Extract the single prefix
git filter-repo --path dbt_diagnostics/

# The result has dbt_diagnostics/ at root level. Optionally flatten:
# git filter-repo --subdirectory-filter dbt_diagnostics/
# (only if we want all files at repo root -- recommend keeping
# dbt_diagnostics/ as package dir)

# Verify history
git log --oneline | head -20
git log --follow dbt_diagnostics/main.py

# Add new remote and push
git remote add origin git@github.com:dckallos/dbt-diagnostics.git
git push -u origin donkey-kong-sandbox
```

#### snowflake-toolkit (multiple paths)

```bash
git clone artwork-db snowflake-toolkit-extract
cd snowflake-toolkit-extract
git checkout donkey-kong-sandbox

# Extract all toolkit paths
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
  --path docs/framework/

# Restructure: promote scripts/ contents to root
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
  --path-rename docs/framework/:docs/

# Note: git filter-repo allows combining --path and --path-rename in a
# single invocation only if using --path-rename alone (second pass).
# The safest approach is two passes as shown above.

git remote add origin git@github.com:dckallos/snowflake-toolkit.git
git push -u origin donkey-kong-sandbox
```

#### artwork-db (stays as-is, toolkit files removed later)

The monorepo continues working during migration. Once the toolkit repo is proven
stable:

```bash
# In the monorepo, AFTER confirming toolkit works standalone:
# Remove toolkit files (they now live in the sibling snowflake-toolkit repo)
git rm -r scripts/snowflake_cli/ scripts/lib/
git rm scripts/orchestrate_modern.sh scripts/apply_sql.sh scripts/rollback_sql.sh
git rm scripts/bootstrap.py scripts/bootstrap_chmod.sh
git rm scripts/activate_mac.sh scripts/load_profile.sh scripts/unload_profile.sh
git rm scripts/status_profile.sh scripts/check.sh scripts/checkpoint.sh
git rm scripts/git_mark_executable.sh scripts/executable_files.txt
git rm -r scripts/sql/show_active_sessions.sql \
  scripts/sql/show_admin_account_grants.sql scripts/sql/checkpoint.sql
git rm -r tests/framework/ tests/examples/ tests/integration/ tests/__init__.py
git rm -r docs/framework/

git commit -m "Remove toolkit files (now in sibling snowflake-toolkit repo)"
```

### 4.3 History validation

After each extraction, run:

```bash
# Confirm no empty commits
git log --oneline | wc -l

# Confirm key files have history
git log --oneline --follow <key-file> | wc -l  # Should be > 0

# Confirm no artwork-specific strings in toolkit (post-refactor)
grep -rn "ARTWORK" . --include="*.sh" --include="*.py" \
  | grep -v "test\|fixture\|example"

# Confirm build/test passes
./run_tests.sh  # (once each repo has its own test entry point)
```

### 4.4 Known history caveats

1. **Shared commits:** Commits that touched both `scripts/snowflake_cli/` and
   `infrastructure/` will appear in both toolkit and artwork repos (with
   irrelevant changes stripped). This is expected behavior.
2. **Renamed files:** `_lib.sh` has always lived at `scripts/snowflake_cli/_lib.sh`
   (no rename history to worry about). `bootstrap.py` was always at
   `scripts/bootstrap.py`.
3. **Tag preservation:** No release tags exist yet -- not a concern.
4. **Branch preservation:** Only `donkey-kong-sandbox` and `main` matter. Both
   will be in all extracted repos.

---

## 5. Migration Sequence

### Phase 0: Refactoring prerequisites (IN monorepo, before any split)

1. Parameterize `_lib.sh` line 46: change default from `ARTWORK_WH` to empty
   string (require explicit setting)
2. Parameterize `bootstrap.py`: accept `--role-name` argument (default
   `ARTWORK_ADMIN` for backward compat)
3. Remove `framework_integration_test.sh` line 207 ARTWORK_DB hardcode (use env
   var or skip)
4. Update `activate_mac.sh` usage text to remove artwork-specific references
5. Fix `dbt_diagnostics/pyproject.toml` `[tool.setuptools.packages.find]` `where`
   field (currently `[".."]` -- needs to be `["."]` when standalone)
6. Make `dbt_diagnostics/config.yml` default `dbt_project_dir` to `.` (user
   overrides)
7. Commit all refactoring on `donkey-kong-sandbox`

### Phase 1: Extract dbt-diagnostics (lowest risk)

1. Clone monorepo fresh
2. Run `git filter-repo` for dbt-diagnostics (Section 4.2)
3. Create `dckallos/dbt-diagnostics` GitHub repo
4. Push extracted branch
5. **Validate:** `pip install -e .` works, `pytest` passes,
   `dbt-diagnostics --help` works
6. **Monorepo continues unchanged** -- dbt_diagnostics/ still exists in it

### Phase 2: Extract snowflake-toolkit (medium risk)

1. Clone monorepo fresh
2. Run `git filter-repo` for toolkit (Section 4.2)
3. Apply the `--path-rename` restructuring
4. Create `dckallos/snowflake-toolkit` GitHub repo
5. Push extracted branch
6. **Validate:** `./snowflake_cli/setup.sh --help` works, framework tests pass
7. **Monorepo continues unchanged**

### Phase 3: Wire artwork-db to sibling toolkit (switchover)

1. Add `TOOLKIT_DIR=../snowflake-toolkit` to `.env.example`
2. Update `Makefile` to resolve `TOOLKIT_DIR` and call toolkit scripts from there
3. Add fail-fast guard (error if `TOOLKIT_DIR` path doesn't exist)
4. Test: `make iac CONN=mk07348` works with the sibling toolkit
5. Once green: `git rm` the original toolkit files from artwork-db (Section 4.2)
6. Remove `docs/framework/` (now lives in toolkit repo)
7. Commit the switchover

### Phase 4: Remove dbt-diagnostics from artwork-db (cleanup)

1. Remove `dbt_diagnostics/` directory from artwork-db
2. Add to `requirements.txt` (or `pyproject.toml`): `dbt-diagnostics` as an
   optional dev dependency (from GitHub URL or PyPI)
3. Update `inject_failures.sh` to document that `dbt-diagnostics` must be
   installed separately
4. Commit

### Rollback at each phase

| Phase | Rollback |
|-------|----------|
| 0 | `git revert` the refactoring commits |
| 1 | Delete the new GitHub repo; monorepo is untouched |
| 2 | Delete the new GitHub repo; monorepo is untouched |
| 3 | `git revert` the switchover commit; restore from history |
| 4 | `git revert` the removal commit; directory returns |

**Key safety property:** Phases 1 and 2 do NOT modify the monorepo. The monorepo
stays fully functional until Phase 3 switchover is explicitly confirmed.

---

## 6. Shared File Resolution

| File | Decision | Rationale |
|------|----------|-----------|
| `Makefile` | Stays in artwork-db | Orchestrates the artwork pipeline |
| `requirements.txt` | Stays in artwork-db | Toolkit is pure bash |
| `.env.example` | Stays in artwork-db | Now includes TOOLKIT_DIR |
| `AGENTS.md` | Stays in artwork-db | Toolkit gets a minimal README |
| `CLAUDE.md` | Stays in artwork-db | Same as AGENTS.md |
| `LICENSE` | Duplicated to all 3 | Each repo needs its own |
| `.gitignore` | Per-repo | Each gets tailored ignores |
| `setup-claude-code.sh` | Stays in artwork-db | Project-specific |
| `.claude/`, `.mcp.json` | Stays in artwork-db | AI assistant config |
| `docs/context/` | Stays in artwork-db | Learning project context |
| `docs/framework/` | Moves to toolkit | Framework documentation |
| `docs/prompts/` | Stays in artwork-db | This plan and related prompts |

---

## 7. Refactoring Prerequisites

These are code changes that MUST happen before the split, committed on
`donkey-kong-sandbox`:

### 7.1 snowflake-toolkit generalization

1. **`scripts/snowflake_cli/_lib.sh:46`** (Low)
   Change `SNOW_LIB_DEFAULT_WAREHOUSE="${SNOW_LIB_DEFAULT_WAREHOUSE:-ARTWORK_WH}"`
   to `SNOW_LIB_DEFAULT_WAREHOUSE="${SNOW_LIB_DEFAULT_WAREHOUSE:-}"` with a clear
   error if unset when needed.

2. **`scripts/snowflake_cli/06_setup_loader_keypair.sh:47-48`** (Low)
   Already uses `${LOADER_USER:-ARTWORK_LOADER_SVC}` -- change defaults to empty
   and require env vars.

3. **`scripts/snowflake_cli/06_setup_loader_keypair.sh:53`** (Medium)
   Default `SQL_FILE` references
   `${REPO_ROOT}/git-setup/operator/register_loader_public_key.sql`. After
   toolkit extraction, caller must set `SQL_FILE` explicitly (or the toolkit
   ships a generic `ALTER USER ... SET RSA_PUBLIC_KEY` template). Change default
   to `${REPO_ROOT}/sql/register_loader_public_key.sql` with a bundled generic
   template.

4. **`scripts/snowflake_cli/09_setup_transformer_keypair.sh:44-45`** (Low)
   Same pattern as 06 for user/role defaults.

5. **`scripts/snowflake_cli/09_setup_transformer_keypair.sh:50`** (Medium)
   Same `SQL_FILE` coupling as 06 -- same fix (bundled generic template).

6. **`scripts/lib/framework_integration_test.sh:207`** (Low)
   Replace `ARTWORK_DB` check with `${TEST_DATABASE:-ARTWORK_DB}` env var.

7. **`scripts/bootstrap.py`** (Medium)
   Add `--role-name` parameter (default `ARTWORK_ADMIN`); replace all hardcoded
   `ARTWORK_ADMIN` with the parameter.

8. **`scripts/activate_mac.sh:7,111`** (Low)
   Remove "extraction, dbt" usage text; make it generic ("activate project
   environment").

**Critical coupling: `register_*_public_key.sql` files.**

Scripts 06 and 09 default to
`${REPO_ROOT}/git-setup/operator/register_<role>_public_key.sql`. These SQL files
contain a single `ALTER USER ... SET RSA_PUBLIC_KEY_2 = '...'` statement. The
toolkit should ship generic templates for these (just the ALTER USER with a
`&PUBLIC_KEY` substitution variable), and the artwork-db project's
`git-setup/operator/` files become project-specific overrides that the Makefile
passes via `SQL_FILE=`.

### 7.2 dbt-diagnostics decoupling

1. **`dbt_diagnostics/pyproject.toml:29-30`** (Low)
   Change `where = [".."]` to `where = ["."]` and adjust `include`.

2. **`dbt_diagnostics/config.yml:5`** (Low)
   Change `dbt_project_dir: ../artwork_pipeline` to `dbt_project_dir: .`.

3. **`dbt_diagnostics/config.yml:9`** (Low)
   Change `profile_name: artwork_pipeline` to `profile_name: default`.

4. **`dbt_diagnostics/LINEAGE_TRAIL_PLAN.md`** (Low, docs only)
   Replace artwork_pipeline CLI examples with generic ones.

### 7.3 Artwork-db preparation

1. **`.env.example`** (Low)
   Add `TOOLKIT_DIR=../snowflake-toolkit` and explicit
   `SNOW_LIB_DEFAULT_WAREHOUSE=ARTWORK_WH`.

2. **`Makefile`** (Low)
   Add `TOOLKIT_DIR` resolution with fail-fast guard. Initially point at
   local `scripts/` for backward compat during Phase 0; switch to sibling
   in Phase 3.

---

## 8. Post-Separation Validation

### 8.1 snowflake-toolkit standalone tests

```bash
cd ~/projects/snowflake-toolkit/

# Unit tests (no Snowflake connection needed)
bash tests/framework/unit/test_connection_resolver.sh
bash tests/framework/unit/test_orchestrate_modern.sh

# Integration test (needs live Snowflake -- run with CONN=test_account)
bash tests/integration/test_multi_account_deployment.sh

# Smoke test: help text for all entry points
bash snowflake_cli/setup.sh --help
bash orchestrate_modern.sh --help
python3 bootstrap.py --help

# Grep for residual artwork references (should be zero outside tests/examples)
grep -rn "ARTWORK\|artwork" . --include="*.sh" --include="*.py" \
  | grep -v "test\|example\|fixture\|README"
# Expected: 0 lines
```

### 8.2 dbt-diagnostics standalone tests

```bash
cd ~/projects/dbt-diagnostics/

# Install in editable mode
pip install -e ".[dev]"

# Run full test suite
pytest

# CLI smoke test
dbt-diagnostics --help

# Verify no artwork import dependencies
python -c "import dbt_diagnostics; print('OK')"

# Check no filesystem references to ../artwork_pipeline resolve
grep -rn "\.\./artwork" . --include="*.py"
# Expected: 0 lines (config.yml has "." as default now)
```

### 8.3 artwork-db with sibling toolkit

```bash
cd ~/projects/artwork-db/

# Verify toolkit resolves
make check-toolkit
# (prints: "Using toolkit at ../snowflake-toolkit (OK)")

# Full IaC apply (integration test)
make iac CONN=mk07348

# Full extraction
make extract-met

# Full dbt build
make dbt-build

# Verify no broken internal references to removed paths
grep -rn "scripts/snowflake_cli\|scripts/lib/" . \
  --include="Makefile" --include="*.sh"
# Expected: 0 lines
```

---

## 9. Risk Registry

### Risk 1: History loss for renamed files

- **Probability:** Low
- **Impact:** Medium
- **Mitigation:** `git filter-repo` preserves rename history. Validate with
  `git log --follow` on key files post-extraction. No files in the toolkit
  paths have been renamed historically.

### Risk 2: Broken `make iac` after switchover

- **Probability:** Medium
- **Impact:** High
- **Mitigation:** Phase 3 tests `make iac` BEFORE removing original files.
  Rollback = git revert. The Makefile first resolves to sibling, is tested,
  THEN originals are deleted.

### Risk 3: `bootstrap.py` parameterization breaks preflight

- **Probability:** Low
- **Impact:** High
- **Mitigation:** Unit test: run `verify-contract` and
  `assert-account-privileges` with explicit `--role-name ARTWORK_ADMIN` before
  and after refactor. Both must produce identical output.

### Risk 4: Toolkit not present on disk

- **Probability:** Medium (fresh machine, new clone)
- **Impact:** Medium (make fails immediately)
- **Mitigation:** Fail-fast `$(error ...)` in Makefile with clone instructions.
  README documents the sibling requirement. Optional `make clone-deps` target
  that runs `git clone` for missing siblings.

### Risk 5: CI setup for new repos

- **Probability:** Low
- **Impact:** Low
- **Mitigation:** Both new repos need their own CI. Toolkit: bash test runner.
  dbt-diagnostics: `pytest` in GitHub Actions. Simple YAML templates.

### Risk 6: Developer workflow disruption

- **Probability:** Low
- **Impact:** Medium
- **Mitigation:** Single developer (owner). All migration happens on
  `donkey-kong-sandbox`. Main is never touched. The monorepo continues working
  until explicit switchover.

### Risk 7: dbt-diagnostics fixtures contain artwork strings

- **Probability:** Zero
- **Impact:** Zero
- **Mitigation:** These are test data (JSON strings like
  `model.artwork_pipeline.stg_met__artworks`). They validate parsing logic.
  Changing them would invalidate tests. Keep as-is.

### Risk 8: Lost cross-repo commit atomicity

- **Probability:** Medium
- **Impact:** Low
- **Mitigation:** Some future changes may need coordinated commits across repos
  (e.g., toolkit API change + artwork-db consumer update). With Model C, you
  just edit both repos and commit each independently. No synchronization
  mechanism is needed for a single developer.

### Risk 9: `inject_failures.py` needs both repos

- **Probability:** Low
- **Impact:** Low
- **Mitigation:** This script lives in artwork-db and imports nothing from
  dbt-diagnostics. It generates fixtures that are manually copied. Document the
  workflow in README.

### Risk 10: Version drift between toolkit and artwork-db

- **Probability:** Medium
- **Impact:** Low
- **Mitigation:** Both repos are on the same machine, edited by the same person.
  If a toolkit change breaks artwork-db, you'll notice immediately when running
  `make iac`. No version pinning is needed for a single-developer workflow.
  If future multi-developer use arises, add a `TOOLKIT_COMMIT.txt` file that
  records the expected toolkit SHA (checked by CI, not enforced locally).

---

## 10. Open Questions (Owner Decisions Required)

### Q1: Toolkit consumption method

**DECIDED: Model C (sibling repos on disk).**

artwork-db references snowflake-toolkit via `TOOLKIT_DIR` env var, defaulting to
`../snowflake-toolkit`. No embedding, no git-level integration. Each repo has
fully independent history.

### Q2: What happens to `scripts/orchestrate.sh` (legacy)?

**Option A: Keep in artwork-db only (recommended)**
It's the working orchestrator today. The modern version exists but is marked
"requires thorough testing." Keep legacy until modern is validated, then delete.

**Option B: Move to toolkit**
It's generic in principle but hasn't been parameterized. Moving it before
validation is risky.

**Option C: Delete now, use modern**
Risk: modern isn't fully tested yet.

**Recommendation:** Option A. Keep `orchestrate.sh` in artwork-db. The Makefile
already calls `orchestrate_modern.sh` for most targets. Once modern is validated
E2E, delete legacy.

### Q3: Toolkit repo name?

- `snowflake-toolkit` -- Clear, searchable, matches npm/PyPI naming patterns
- `snowflake-cli-bootstrap` -- More specific but limits future scope
- `sf-iac-framework` -- Terse but less discoverable

**Recommendation:** `snowflake-toolkit` (or `snowflake-iac-toolkit` if the owner
wants to avoid confusion with Snowflake's official `snowflake-cli`).

### Q4: Should `bootstrap.py` stay in the toolkit or move to artwork-db?

The preflight currently hardcodes `ARTWORK_ADMIN`. After parameterization, it
becomes a generic "verify role X has privileges Y" utility.

**Option A: Keep in toolkit, parameterized (recommended)**
Generic privilege preflight is a toolkit concern. Any project can use it.

**Option B: Move to artwork-db**
It's tightly coupled to the create_roles.sql file structure today.
Parameterization adds complexity.

**Recommendation:** Option A. The preflight pattern is generic ("verify a role
has these grants before proceeding"). The `--role-name` + `--roles-sql`
parameters make it project-agnostic. The `infrastructure/create_roles.sql` path
is passed by the caller (artwork-db's Makefile), not baked into the script.

### Q5: Timeline preference for the migration?

This plan is designed for incremental execution. The owner can:

- Do Phase 0 + 1 in one session (refactor + extract dbt-diagnostics)
- Do Phase 2 in a separate session
- Do Phase 3 + 4 whenever confident

No phase has a deadline. Each phase produces a working state.

---

## Appendix A: Final Repo Structures

### snowflake-toolkit/

```text
snowflake-toolkit/
  snowflake_cli/
    _lib.sh
    setup.sh
    init_profile.sh
    new_account.sh
    00_install_snowflake_cli.sh
    01_init_snowflake_home.sh
    02_generate_admin_keypair.sh
    03_lock_config_permissions.sh
    04_register_admin_public_key.sh
    05_verify_admin_jwt.sh
    06_setup_loader_keypair.sh
    07_test_loader_connection.sh
    08_promote_admin_warehouse.sh
    09_setup_transformer_keypair.sh
    10_test_transformer_connection.sh
    README.md
  lib/
    connection_resolver.sh
    ddl_orchestrator.sh (deprecated stub)
    dbt_orchestrator.sh (deprecated stub)
    framework_integration_test.sh
    legacy_comparison_test.sh
  sql/
    show_active_sessions.sql
    show_admin_account_grants.sql
    checkpoint.sql
  tests/
    framework/unit/
    examples/
    integration/
  docs/
    README.md
    architecture.md
    api-reference.md
    integration-guide.md
    migration-guide.md
    deployment-patterns.md
    testing-guide.md
    troubleshooting.md
    ai-integration.md
  orchestrate_modern.sh
  apply_sql.sh
  rollback_sql.sh
  bootstrap.py
  bootstrap_chmod.sh
  activate_mac.sh
  load_profile.sh
  unload_profile.sh
  status_profile.sh
  check.sh
  checkpoint.sh
  git_mark_executable.sh
  executable_files.txt
  LICENSE
  README.md
```

### dbt-diagnostics/

```text
dbt-diagnostics/
  dbt_diagnostics/
    __init__.py
    __main__.py
    main.py
    models.py
    renderer.py
    colors.py
    discover.py
    config.yml
    classifiers/
    tracers/
    enrichers/
    linters/
    templates/
    fixtures/
    tests/
  pyproject.toml
  LICENSE
  README.md
  CHANGELOG.md
  BUILD_PROMPT.md
  docs/
    HANDOFF_PROMPT.md
    HANDOFF_PROMPT_2.md
    LINEAGE_TRAIL_PLAN.md
```

### artwork-db/ (post-migration)

```text
artwork-db/
  infrastructure/
    create_*.sql / drop_*.sql (29 files)
    CLAUDE.md
  extraction/
    __init__.py
    met/  (12+ files)
  artwork_pipeline/
    dbt_project.yml
    profiles.yml
    packages.yml
    models/
    macros/
    README.md
  operations/
    met_seed_enrichment_control.sql
  analysis/
    met_snapshot_profile.sql
  git-setup/
    create_*.sql / drop_*.sql (6 files)
    operator/
    README.md
  scripts/
    orchestrate.sh (legacy, until deprecated)
    dbt_orchestrate.sh
    dbt_orchestrate_modern.sh
    manifest.txt
    secret_bearing.txt
    sql/
      show_pipeline_status.sql
      show_run_control.sql
  docs/
    context/ (all learning docs, journals, plans)
    prompts/
  inject_failures.py
  inject_failures.sh
  Makefile
  .env.example
  profiles.yml.example
  requirements.txt
  AGENTS.md
  CLAUDE.md
  LICENSE
  .gitignore
  setup-claude-code.sh
  .claude/
  .mcp.json
```

Note: No `vendor/` directory. The toolkit is a sibling on disk, not embedded.

---

## Appendix B: Makefile After Migration (artwork-db)

```makefile
# artwork-db Makefile (post-toolkit-extraction)
#
# The toolkit lives as a sibling repo. Override TOOLKIT_DIR in .env or env:
#   TOOLKIT_DIR=~/other/path/snowflake-toolkit make iac
TOOLKIT_DIR ?= ../snowflake-toolkit
CONN ?= admin
VARS ?=
DBT_PROJECT_DIR := artwork_pipeline

# --- Fail-fast: toolkit must exist ---
ifeq ($(wildcard $(TOOLKIT_DIR)/snowflake_cli/setup.sh),)
  $(error snowflake-toolkit not found at $(TOOLKIT_DIR). \
    Clone it: git clone git@github.com:dckallos/snowflake-toolkit.git $(TOOLKIT_DIR))
endif

# Toolkit entry points
ORCHESTRATE := bash $(TOOLKIT_DIR)/orchestrate_modern.sh
SETUP := bash $(TOOLKIT_DIR)/snowflake_cli/setup.sh

.PHONY: check-toolkit chmod iac infra loader transformer

check-toolkit:
	@echo "Using toolkit at $(TOOLKIT_DIR) (OK)"

chmod:
	@bash $(TOOLKIT_DIR)/bootstrap_chmod.sh

iac: chmod
	$(ORCHESTRATE) --ddl-dir infrastructure/ \
	  --manifest scripts/manifest.txt --phase infra --connection $(CONN)
	$(ORCHESTRATE) --ddl-dir git-setup/ \
	  --manifest scripts/manifest.txt --phase bootstrap --connection $(CONN)

infra: chmod
	$(ORCHESTRATE) --ddl-dir infrastructure/ \
	  --manifest scripts/manifest.txt --phase infra --connection $(CONN)

loader: chmod
	$(SETUP) --profile $(CONN) --phase loader

transformer: chmod
	$(SETUP) --profile $(CONN) --phase transformer

# --- dbt and extraction targets unchanged ---
# dbt-build, dbt-test, extract-met, etc. remain as-is
```
