# Repository Separation Plan

> **Status:** PLAN ONLY -- no code changes, no git operations, no DDL.
> **Date:** 2026-06-07
> **Branch:** `donkey-kong-sandbox`
> **Author:** Cortex Code (Principal Engineer analysis)

---

## 1. Executive Summary

### Target repositories (3-repo split)

```
artwork-db (monorepo)
    |
    +---> snowflake-toolkit        (GENERIC: reusable across any SF project)
    |         Depends on: nothing
    |
    +---> artwork-db               (DOMAIN: museum pipeline IaC + ETL + dbt)
    |         Depends on: snowflake-toolkit (as git subtree or submodule)
    |
    +---> dbt-diagnostics          (INDEPENDENT: pip-installable CLI tool)
              Depends on: nothing (runtime config points at any dbt project)
```

### Dependency direction (acyclic)

```
artwork-db ----depends-on----> snowflake-toolkit
artwork-db ----dev-depends---> dbt-diagnostics (optional; fixture generation)
dbt-diagnostics ----0 deps---> (standalone)
snowflake-toolkit ----0 deps-> (standalone)
```

### Why 3 repos, not 2 or 4

| Option | Tradeoffs |
|--------|-----------|
| **2-repo** (toolkit + everything else) | dbt-diagnostics is already pip-installable and has its own test suite, versioning, changelog. Bundling it with artwork couples release cadences unnecessarily. |
| **3-repo** (toolkit + artwork + dbt-diagnostics) | **Recommended.** Clean ownership: toolkit = infra plumbing reusable by future projects; artwork = domain pipeline (DDL + extraction + dbt are deployed together, same lifecycle); dbt-diagnostics = standalone tool. |
| **4-repo** (toolkit + artwork-iac + artwork-pipeline + dbt-diagnostics) | Over-split. `infrastructure/` and `artwork_pipeline/` share a deploy lifecycle (`make iac` then `make dbt-build`), the same `.env`, the same Snowflake objects. Splitting them doubles the coordination cost for zero ownership-boundary gain (single developer). |

---

## 2. Detailed File Assignment

### 2.1 snowflake-toolkit (new repo)

**Purpose:** Generic, reusable Snowflake CLI bootstrap, connection management, and DDL orchestration framework. Works with ANY Snowflake project.

| Source path (monorepo) | Target path (new repo) | Notes |
|------------------------|------------------------|-------|
| `scripts/snowflake_cli/_lib.sh` | `snowflake_cli/_lib.sh` | REFACTOR: remove `ARTWORK_WH` default (use `COMPUTE_WH` or require env) |
| `scripts/snowflake_cli/00_install_snowflake_cli.sh` | `snowflake_cli/00_install_snowflake_cli.sh` | Generic |
| `scripts/snowflake_cli/01_init_snowflake_home.sh` | `snowflake_cli/01_init_snowflake_home.sh` | Generic |
| `scripts/snowflake_cli/02_generate_admin_keypair.sh` | `snowflake_cli/02_generate_admin_keypair.sh` | Generic |
| `scripts/snowflake_cli/03_lock_config_permissions.sh` | `snowflake_cli/03_lock_config_permissions.sh` | Generic |
| `scripts/snowflake_cli/04_register_admin_public_key.sh` | `snowflake_cli/04_register_admin_public_key.sh` | Generic |
| `scripts/snowflake_cli/05_verify_admin_jwt.sh` | `snowflake_cli/05_verify_admin_jwt.sh` | Generic |
| `scripts/snowflake_cli/06_setup_loader_keypair.sh` | `snowflake_cli/06_setup_loader_keypair.sh` | Already env-overridable (LOADER_USER/LOADER_ROLE) |
| `scripts/snowflake_cli/07_test_loader_connection.sh` | `snowflake_cli/07_test_loader_connection.sh` | Generic |
| `scripts/snowflake_cli/08_promote_admin_warehouse.sh` | `snowflake_cli/08_promote_admin_warehouse.sh` | Generic |
| `scripts/snowflake_cli/09_setup_transformer_keypair.sh` | `snowflake_cli/09_setup_transformer_keypair.sh` | Already env-overridable (TRANSFORMER_USER/TRANSFORMER_ROLE) |
| `scripts/snowflake_cli/10_test_transformer_connection.sh` | `snowflake_cli/10_test_transformer_connection.sh` | Generic |
| `scripts/snowflake_cli/README.md` | `snowflake_cli/README.md` | Update for standalone context |
| `scripts/snowflake_cli/init_profile.sh` | `snowflake_cli/init_profile.sh` | Generic |
| `scripts/snowflake_cli/new_account.sh` | `snowflake_cli/new_account.sh` | Generic |
| `scripts/snowflake_cli/setup.sh` | `snowflake_cli/setup.sh` | Generic |
| `scripts/lib/connection_resolver.sh` | `lib/connection_resolver.sh` | Generic |
| `scripts/lib/ddl_orchestrator.sh` | `lib/ddl_orchestrator.sh` | Deprecated stub -- keep for migration compatibility |
| `scripts/lib/dbt_orchestrator.sh` | `lib/dbt_orchestrator.sh` | Deprecated stub -- keep for migration compatibility |
| `scripts/lib/framework_integration_test.sh` | `lib/framework_integration_test.sh` | REFACTOR: remove line 207 ARTWORK_DB hardcode |
| `scripts/lib/legacy_comparison_test.sh` | `lib/legacy_comparison_test.sh` | Generic (compares old vs new orchestration) |
| `scripts/orchestrate_modern.sh` | `orchestrate_modern.sh` | Generic (reads --ddl-dir + --manifest from caller) |
| `scripts/apply_sql.sh` | `apply_sql.sh` | Generic |
| `scripts/rollback_sql.sh` | `rollback_sql.sh` | Generic |
| `scripts/bootstrap.py` | `bootstrap.py` | REFACTOR: parameterize role name (currently hardcodes ARTWORK_ADMIN) |
| `scripts/bootstrap_chmod.sh` | `bootstrap_chmod.sh` | Generic |
| `scripts/activate_mac.sh` | `activate_mac.sh` | REFACTOR: remove artwork-specific usage text |
| `scripts/load_profile.sh` | `load_profile.sh` | Generic |
| `scripts/unload_profile.sh` | `unload_profile.sh` | Generic |
| `scripts/status_profile.sh` | `status_profile.sh` | Generic |
| `scripts/check.sh` | `check.sh` | Generic |
| `scripts/checkpoint.sh` | `checkpoint.sh` | Generic (writes to any run_control table) |
| `scripts/git_mark_executable.sh` | `git_mark_executable.sh` | Generic |
| `scripts/executable_files.txt` | `executable_files.txt` | REFACTOR: paths relative to new structure |
| `scripts/sql/show_active_sessions.sql` | `sql/show_active_sessions.sql` | Generic |
| `scripts/sql/show_admin_account_grants.sql` | `sql/show_admin_account_grants.sql` | Generic |
| `scripts/sql/checkpoint.sql` | `sql/checkpoint.sql` | Generic |
| `tests/framework/` | `tests/framework/` | Generic framework tests |
| `tests/examples/basic_project_integration.sh` | `tests/examples/basic_project_integration.sh` | Generic |
| `tests/integration/test_multi_account_deployment.sh` | `tests/integration/test_multi_account_deployment.sh` | Generic |
| `tests/__init__.py` | `tests/__init__.py` | Generic |
| `docs/framework/` (all 8 files) | `docs/` | Framework documentation |

**NOT included in toolkit:**
- `scripts/orchestrate.sh` -- legacy; retained in artwork-db until `orchestrate_modern.sh` fully replaces it
- `scripts/manifest.txt` -- artwork-specific ordering
- `scripts/secret_bearing.txt` -- artwork-specific file list
- `scripts/dbt_orchestrate.sh` -- artwork-specific
- `scripts/dbt_orchestrate_modern.sh` -- artwork-specific (wraps toolkit for artwork)
- `scripts/sql/show_pipeline_status.sql` -- artwork-specific
- `scripts/sql/show_run_control.sql` -- artwork-specific

### 2.2 artwork-db (stays as primary repo, slimmed)

**Purpose:** The museum artwork medallion pipeline -- Snowflake DDL, Met/CMA/AIC extraction, dbt models, operational SQL, and the project-specific orchestration that ties it together.

| Source path | Target path | Notes |
|-------------|-------------|-------|
| `infrastructure/` (all 29 files) | `infrastructure/` | Domain DDL |
| `extraction/` (all files) | `extraction/` | Domain ETL |
| `artwork_pipeline/` (all files) | `artwork_pipeline/` | Domain dbt project |
| `operations/` | `operations/` | Operational SQL |
| `git-setup/` (all files) | `git-setup/` | In-Snowflake Git mirror for this project |
| `analysis/` | `analysis/` | Diagnostic SQL |
| `scripts/orchestrate.sh` | `scripts/orchestrate.sh` | Legacy orchestrator (until modernized) |
| `scripts/dbt_orchestrate.sh` | `scripts/dbt_orchestrate.sh` | Artwork dbt lifecycle |
| `scripts/dbt_orchestrate_modern.sh` | `scripts/dbt_orchestrate_modern.sh` | Modern artwork dbt lifecycle |
| `scripts/manifest.txt` | `scripts/manifest.txt` | Artwork-specific apply order |
| `scripts/secret_bearing.txt` | `scripts/secret_bearing.txt` | Artwork-specific secrets list |
| `scripts/sql/show_pipeline_status.sql` | `scripts/sql/show_pipeline_status.sql` | Artwork-specific |
| `scripts/sql/show_run_control.sql` | `scripts/sql/show_run_control.sql` | Artwork-specific |
| `inject_failures.py` | `inject_failures.py` | Fixture generation for dbt-diagnostics |
| `inject_failures.sh` | `inject_failures.sh` | E2E fixture runner |
| `Makefile` | `Makefile` | REFACTOR: update paths to reference toolkit location |
| `.env.example` | `.env.example` | Artwork-specific env vars |
| `profiles.yml.example` | `profiles.yml.example` | dbt profile template |
| `requirements.txt` | `requirements.txt` | Python deps for extraction |
| `.gitignore` | `.gitignore` | Keep |
| `LICENSE` | `LICENSE` | Keep (or dual-license if toolkit gets its own) |
| `AGENTS.md` | `AGENTS.md` | REFACTOR: remove toolkit references |
| `CLAUDE.md` | `CLAUDE.md` | REFACTOR: update for slimmed repo |
| `infrastructure/CLAUDE.md` | `infrastructure/CLAUDE.md` | Keep |
| `docs/context/` (all non-framework docs) | `docs/context/` | Project context (learning journals, plans, etc.) |
| `docs/prompts/` | `docs/prompts/` | Keep |
| `setup-claude-code.sh` | `setup-claude-code.sh` | AI tooling setup |
| `.claude/` | `.claude/` | AI config |
| `.mcp.json` | `.mcp.json` | AI config |

**Toolkit integration:** The `snowflake-toolkit` is consumed as a **git subtree** at `vendor/snowflake-toolkit/` (see Section 3).

### 2.3 dbt-diagnostics (new repo)

**Purpose:** Standalone, pip-installable dbt error diagnostics CLI. Works with any dbt project on Snowflake.

| Source path | Target path | Notes |
|-------------|-------------|-------|
| `dbt_diagnostics/` (entire tree) | `dbt_diagnostics/` (or root-level `src/`) | All source + tests + fixtures |
| `dbt_diagnostics/pyproject.toml` | `pyproject.toml` | REFACTOR: fix `where` in setuptools config |
| `dbt_diagnostics/config.yml` | `dbt_diagnostics/config.yml` | REFACTOR: make paths configurable defaults |
| `dbt_diagnostics/BUILD_PROMPT.md` | `BUILD_PROMPT.md` | Development context |
| `dbt_diagnostics/CHANGELOG.md` | `CHANGELOG.md` | Keep at root |
| `dbt_diagnostics/HANDOFF_PROMPT.md` | docs/ | Development context |
| `dbt_diagnostics/HANDOFF_PROMPT_2.md` | docs/ | Development context |
| `dbt_diagnostics/LINEAGE_TRAIL_PLAN.md` | docs/ | Development context |

**What stays behind in artwork-db:**
- `inject_failures.py` / `inject_failures.sh` -- these generate fixtures FOR dbt-diagnostics but FROM artwork_pipeline models. They belong to the project that owns the models.

---

## 3. Dependency Contracts

### 3.1 snowflake-toolkit exposes (public interface)

The toolkit is consumed via filesystem paths after being placed in the consuming project (git subtree, submodule, or manual copy). Its public interface:

| Interface | Contract |
|-----------|----------|
| `snowflake_cli/setup.sh` | Entry point. Accepts `--profile`, `--phase`, `--admin-conn`, `--loader-conn`, `--transformer-conn`. Phases: `all`, `install`, `init`, `keypair`, `register`, `verify`, `promote`, `loader`, `transformer`. |
| `snowflake_cli/_lib.sh` | Sourceable library. Exports functions. Env overrides: `SNOW_LIB_DEFAULT_WAREHOUSE`, `SNOW_LIB_CONFIG_TOML`, `SNOW_LIB_CONNECTIONS_TOML`, `SNOW_LIB_KEY_DIR`, `ADMIN_CONN`, `LOADER_CONN`, `TRANSFORMER_CONN`. |
| `orchestrate_modern.sh` | CLI: `--ddl-dir DIR --manifest FILE --phase PHASE --connection CONN [--file FILE] [--from FILE] [--var K=V]`. Generic DDL orchestration. |
| `apply_sql.sh` / `rollback_sql.sh` | Low-level: apply/rollback a single .sql file via `snow sql`. |
| `bootstrap.py` | Subcommands: `verify-contract --role-name ROLE --roles-sql PATH`, `assert-account-privileges --connection CONN --role-name ROLE`. |
| `lib/connection_resolver.sh` | Sourceable. Connection resolution for framework components. |

**Environment variables (toolkit reads, consumer sets):**
- `SNOW_LIB_DEFAULT_WAREHOUSE` -- default warehouse (no artwork default after refactor)
- `LOADER_USER`, `LOADER_ROLE` -- service user for loader keypair
- `TRANSFORMER_USER`, `TRANSFORMER_ROLE` -- service user for transformer keypair
- `SNOW_CONNECTION` -- default snow CLI connection name

### 3.2 artwork-db consumes toolkit

The Makefile in artwork-db will reference the toolkit at a relative path:

```makefile
TOOLKIT_DIR := vendor/snowflake-toolkit
# or if using submodule:
# TOOLKIT_DIR := snowflake-toolkit

iac: chmod
  bash $(TOOLKIT_DIR)/orchestrate_modern.sh \
    --ddl-dir infrastructure/ \
    --manifest scripts/manifest.txt \
    --phase infra \
    --connection $(CONN)
```

The `.env` in artwork-db sets the env vars the toolkit reads:
```bash
SNOW_LIB_DEFAULT_WAREHOUSE=ARTWORK_WH
LOADER_USER=ARTWORK_LOADER_SVC
LOADER_ROLE=ARTWORK_LOADER
TRANSFORMER_USER=ARTWORK_TRANSFORMER_SVC
TRANSFORMER_ROLE=ARTWORK_TRANSFORMER
```

### 3.3 dbt-diagnostics is standalone

- Zero import-time dependencies on artwork-db or snowflake-toolkit.
- `config.yml` ships with example defaults (`dbt_project_dir: .` or user-provided path).
- Fixtures contain `model.artwork_pipeline.*` unique IDs -- these are data strings used in tests, not import paths. They remain as realistic test data.
- Users point it at any dbt project via `--project-dir` CLI flag or config.yml override.

### 3.4 How artwork-db uses dbt-diagnostics (optional dev dependency)

```bash
# In artwork-db's dev workflow:
pip install -e ../dbt-diagnostics  # or pip install dbt-diagnostics from PyPI
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
| `git filter-repo --path` | Multiple non-contiguous paths into one repo | **snowflake-toolkit** (paths scattered under `scripts/`, `tests/`, `docs/framework/`) |
| `git subtree split --prefix` | Single contiguous subtree | **dbt-diagnostics** (single `dbt_diagnostics/` dir) |
| Fresh repo + squashed history | When history is not valuable | NOT recommended -- owner wants history |
| Keep monorepo + submodules pointing out | Minimal disruption, maximal complexity | NOT recommended -- defeats the purpose |

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
# (only if we want all files at repo root -- recommend keeping dbt_diagnostics/ as package dir)

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

#### artwork-db (stays as-is, toolkit removed later)

The monorepo continues working during migration. Once the toolkit repo is proven stable:

```bash
# In the monorepo, AFTER confirming toolkit works standalone:
# Remove toolkit files (they now live in vendor/snowflake-toolkit/ via subtree)
git rm -r scripts/snowflake_cli/ scripts/lib/
git rm scripts/orchestrate_modern.sh scripts/apply_sql.sh scripts/rollback_sql.sh
git rm scripts/bootstrap.py scripts/bootstrap_chmod.sh
git rm scripts/activate_mac.sh scripts/load_profile.sh scripts/unload_profile.sh
git rm scripts/status_profile.sh scripts/check.sh scripts/checkpoint.sh
git rm scripts/git_mark_executable.sh scripts/executable_files.txt
git rm -r scripts/sql/show_active_sessions.sql scripts/sql/show_admin_account_grants.sql scripts/sql/checkpoint.sql
git rm -r tests/framework/ tests/examples/ tests/integration/ tests/__init__.py
git rm -r docs/framework/

# Add toolkit back as subtree
git subtree add --prefix=vendor/snowflake-toolkit \
  git@github.com:dckallos/snowflake-toolkit.git donkey-kong-sandbox --squash

git commit -m "Replace inline toolkit with git subtree from snowflake-toolkit repo"
```

### 4.3 History validation

After each extraction, run:

```bash
# Confirm no empty commits
git log --oneline | wc -l

# Confirm key files have history
git log --oneline --follow <key-file> | wc -l  # Should be > 0

# Confirm no artwork-specific strings in toolkit (post-refactor)
grep -rn "ARTWORK" . --include="*.sh" --include="*.py" | grep -v "test\|fixture\|example"

# Confirm build/test passes
./run_tests.sh  # (once each repo has its own test entry point)
```

### 4.4 Known history caveats

1. **Shared commits:** Commits that touched both `scripts/snowflake_cli/` and `infrastructure/` will appear in both toolkit and artwork repos (with irrelevant changes stripped). This is expected behavior.
2. **Renamed files:** `_lib.sh` has always lived at `scripts/snowflake_cli/_lib.sh` (no rename history to worry about). `bootstrap.py` was always at `scripts/bootstrap.py`.
3. **Tag preservation:** No release tags exist yet -- not a concern.
4. **Branch preservation:** Only `donkey-kong-sandbox` and `main` matter. Both will be in all extracted repos.

---

## 5. Migration Sequence

### Phase 0: Refactoring prerequisites (IN monorepo, before any split)

1. Parameterize `_lib.sh` line 46: change default from `ARTWORK_WH` to empty string (require explicit setting)
2. Parameterize `bootstrap.py`: accept `--role-name` argument (default `ARTWORK_ADMIN` for backward compat)
3. Remove `framework_integration_test.sh` line 207 ARTWORK_DB hardcode (use env var or skip)
4. Update `activate_mac.sh` usage text to remove artwork-specific references
5. Fix `dbt_diagnostics/pyproject.toml` `[tool.setuptools.packages.find]` `where` field (currently `[".."]` -- needs to be `["."]` when standalone)
6. Make `dbt_diagnostics/config.yml` default `dbt_project_dir` to `.` (user overrides)
7. Commit all refactoring on `donkey-kong-sandbox`

### Phase 1: Extract dbt-diagnostics (lowest risk)

1. Clone monorepo fresh
2. Run `git filter-repo` for dbt-diagnostics (Section 4.2)
3. Create `dckallos/dbt-diagnostics` GitHub repo
4. Push extracted branch
5. **Validate:** `pip install -e .` works, `pytest` passes, `dbt-diagnostics --help` works
6. **Monorepo continues unchanged** -- dbt_diagnostics/ still exists in it

### Phase 2: Extract snowflake-toolkit (medium risk)

1. Clone monorepo fresh
2. Run `git filter-repo` for toolkit (Section 4.2)
3. Apply the `--path-rename` restructuring
4. Create `dckallos/snowflake-toolkit` GitHub repo
5. Push extracted branch
6. **Validate:** `./snowflake_cli/setup.sh --help` works, framework tests pass
7. **Monorepo continues unchanged**

### Phase 3: Integrate toolkit into artwork-db (switchover)

1. In monorepo, add toolkit as git subtree at `vendor/snowflake-toolkit/`
2. Update `Makefile` paths to use `vendor/snowflake-toolkit/` prefix
3. Update `.env.example` to set all toolkit env vars explicitly
4. Test: `make iac CONN=mk07348` works with the vendored toolkit
5. Once green: remove the original `scripts/snowflake_cli/`, `scripts/lib/`, etc.
6. Remove `docs/framework/` (now lives in toolkit repo)
7. Commit the switchover

### Phase 4: Remove dbt-diagnostics from artwork-db (cleanup)

1. Remove `dbt_diagnostics/` directory from artwork-db
2. Add to `requirements.txt` (or `pyproject.toml`): `dbt-diagnostics` as an optional dev dependency (from GitHub URL or PyPI)
3. Update `inject_failures.sh` to document that `dbt-diagnostics` must be installed separately
4. Commit

### Rollback at each phase

| Phase | Rollback |
|-------|----------|
| 0 | `git revert` the refactoring commits |
| 1 | Delete the new GitHub repo; monorepo is untouched |
| 2 | Delete the new GitHub repo; monorepo is untouched |
| 3 | `git revert` the switchover commit; restore original files from git history |
| 4 | `git revert` the removal commit; `dbt_diagnostics/` returns from history |

**Key safety property:** Phases 1 and 2 do NOT modify the monorepo. The monorepo stays fully functional until Phase 3 switchover is explicitly confirmed.

---

## 6. Shared File Resolution

| File | Decision | Rationale |
|------|----------|-----------|
| `Makefile` | **Stays in artwork-db**, refactored | It orchestrates the artwork pipeline. Toolkit has no Makefile (it's a library, not a project). |
| `requirements.txt` | **Stays in artwork-db** | Python deps for extraction. Toolkit is pure bash. dbt-diagnostics has its own `pyproject.toml`. |
| `.env.example` | **Stays in artwork-db** | Artwork-specific vars. Toolkit documents its env vars in its own README. |
| `AGENTS.md` | **Stays in artwork-db**, refactored | AI context for the artwork project. Toolkit gets a minimal README. dbt-diagnostics keeps its BUILD_PROMPT.md. |
| `CLAUDE.md` | **Stays in artwork-db**, refactored | Same as AGENTS.md. |
| `LICENSE` | **Duplicated** to all 3 repos | Each repo needs its own license. Same license (MIT or Apache-2.0). |
| `.gitignore` | **Per-repo** | Each gets a tailored `.gitignore`. Toolkit ignores `.p8` files, dbt-diagnostics ignores `__pycache__`, artwork ignores both. |
| `setup-claude-code.sh` | **Stays in artwork-db** | Project-specific AI setup. |
| `.claude/`, `.mcp.json` | **Stays in artwork-db** | AI assistant config. |
| `docs/context/` | **Stays in artwork-db** | Learning project context and journals. |
| `docs/framework/` | **Moves to toolkit** | Framework documentation. |
| `docs/prompts/` | **Stays in artwork-db** | This plan and related prompts. |

---

## 7. Refactoring Prerequisites

These are code changes that MUST happen before the split, committed on `donkey-kong-sandbox`:

### 7.1 snowflake-toolkit generalization

| File | Change | Difficulty |
|------|--------|-----------|
| `scripts/snowflake_cli/_lib.sh:46` | Change `SNOW_LIB_DEFAULT_WAREHOUSE="${SNOW_LIB_DEFAULT_WAREHOUSE:-ARTWORK_WH}"` to `SNOW_LIB_DEFAULT_WAREHOUSE="${SNOW_LIB_DEFAULT_WAREHOUSE:-}"` with a clear error if unset when needed | Low |
| `scripts/snowflake_cli/06_setup_loader_keypair.sh:47-48` | Already uses `${LOADER_USER:-ARTWORK_LOADER_SVC}` -- change defaults to empty and require env vars | Low |
| `scripts/snowflake_cli/06_setup_loader_keypair.sh:53` | Default `SQL_FILE` references `${REPO_ROOT}/git-setup/operator/register_loader_public_key.sql`. After toolkit extraction, caller must set `SQL_FILE` explicitly (or the toolkit ships a generic `ALTER USER ... SET RSA_PUBLIC_KEY` template). Change default to `${REPO_ROOT}/sql/register_loader_public_key.sql` with a bundled generic template. | Medium |
| `scripts/snowflake_cli/09_setup_transformer_keypair.sh:44-45` | Same pattern as 06 for user/role defaults | Low |
| `scripts/snowflake_cli/09_setup_transformer_keypair.sh:50` | Same `SQL_FILE` coupling as 06 -- same fix (bundled generic template) | Medium |
| `scripts/lib/framework_integration_test.sh:207` | Replace `ARTWORK_DB` check with `${TEST_DATABASE:-ARTWORK_DB}` env var | Low |
| `scripts/bootstrap.py` | Add `--role-name` parameter (default `ARTWORK_ADMIN`); replace all hardcoded `ARTWORK_ADMIN` with the parameter | Medium |
| `scripts/activate_mac.sh:7,111` | Remove "extraction, dbt" usage text; make it generic ("activate project environment") | Low |

**Critical coupling: `register_*_public_key.sql` files.**
Scripts 06 and 09 default to `${REPO_ROOT}/git-setup/operator/register_<role>_public_key.sql`. These SQL files contain a single `ALTER USER ... SET RSA_PUBLIC_KEY_2 = '...'` statement. The toolkit should ship generic templates for these (just the ALTER USER with a `&PUBLIC_KEY` substitution variable), and the artwork-db project's `git-setup/operator/` files become project-specific overrides that the Makefile passes via `SQL_FILE=`.

### 7.2 dbt-diagnostics decoupling

| File | Change | Difficulty |
|------|--------|-----------|
| `dbt_diagnostics/pyproject.toml:29-30` | Change `where = [".."]` to `where = ["."]` and adjust `include` | Low |
| `dbt_diagnostics/config.yml:5` | Change `dbt_project_dir: ../artwork_pipeline` to `dbt_project_dir: .` | Low |
| `dbt_diagnostics/config.yml:9` | Change `profile_name: artwork_pipeline` to `profile_name: default` | Low |
| `dbt_diagnostics/LINEAGE_TRAIL_PLAN.md` | Replace artwork_pipeline CLI examples with generic ones | Low (docs only) |

### 7.3 Artwork-db preparation

| File | Change | Difficulty |
|------|--------|-----------|
| `.env.example` | Add explicit `SNOW_LIB_DEFAULT_WAREHOUSE=ARTWORK_WH` | Low |
| `Makefile` | Prepare `TOOLKIT_DIR` variable (initially `scripts`, later `vendor/snowflake-toolkit`) | Low |

---

## 8. Post-Separation Validation

### 8.1 snowflake-toolkit standalone tests

```bash
cd snowflake-toolkit/

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
cd dbt-diagnostics/

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

### 8.3 artwork-db with vendored toolkit

```bash
cd artwork-db/

# Verify toolkit subtree exists
ls vendor/snowflake-toolkit/snowflake_cli/setup.sh

# Full IaC apply (integration test)
make iac CONN=mk07348

# Full extraction
make extract-met

# Full dbt build
make dbt-build

# Verify no broken references
grep -rn "scripts/snowflake_cli\|scripts/lib/" . --include="Makefile" --include="*.sh" \
  | grep -v "vendor/"
# Expected: 0 lines (all references point to vendor/snowflake-toolkit/)
```

---

## 9. Risk Registry

| # | Risk | Probability | Impact | Mitigation |
|---|------|-------------|--------|-----------|
| 1 | **History loss for renamed files** | Low | Medium | `git filter-repo` preserves rename history. Validate with `git log --follow` on key files post-extraction. No files in the toolkit paths have been renamed historically. |
| 2 | **Broken `make iac` after switchover** | Medium | High | Phase 3 tests `make iac` BEFORE removing original files. Rollback = git revert. The toolkit subtree is added FIRST, tested, THEN originals removed. |
| 3 | **`bootstrap.py` parameterization breaks preflight** | Low | High | Unit test: run `verify-contract` and `assert-account-privileges` with explicit `--role-name ARTWORK_ADMIN` before and after refactor. Both must produce identical output. |
| 4 | **Subtree update conflicts** | Low | Low | Git subtrees can have merge conflicts on `git subtree pull`. Mitigation: use `--squash` so subtree history is collapsed; conflicts are rare in practice for a library. |
| 5 | **CI setup for new repos** | Low | Low | Both new repos need their own CI. Toolkit: bash test runner. dbt-diagnostics: `pytest` in GitHub Actions. Simple YAML templates. |
| 6 | **Developer workflow disruption** | Low | Medium | Single developer (owner). All migration happens on `donkey-kong-sandbox`. Main is never touched. The monorepo continues working until explicit switchover. |
| 7 | **dbt-diagnostics fixtures contain artwork strings** | Zero | Zero | These are test data (JSON strings like `model.artwork_pipeline.stg_met__artworks`). They validate parsing logic. Changing them would invalidate tests. Keep as-is. |
| 8 | **Lost cross-repo commit atomicity** | Medium | Low | Some future changes may need coordinated commits across repos (e.g., toolkit API change + artwork-db consumer update). Mitigation: semantic versioning in toolkit; artwork-db pins to a specific toolkit commit via subtree. |
| 9 | **`inject_failures.py` needs both repos** | Low | Low | This script lives in artwork-db and imports nothing from dbt-diagnostics. It generates fixtures that are manually copied. Document the workflow in README. |
| 10 | **Stale toolkit copy in artwork-db** | Medium | Low | `git subtree pull --squash` updates the vendored copy. Add a Makefile target: `make update-toolkit`. |

---

## 10. Open Questions (Owner Decisions Required)

### Q1: Toolkit consumption method -- git subtree vs git submodule vs package?

| Option | Pros | Cons | Precedent |
|--------|------|------|-----------|
| **A. Git subtree (recommended)** | Files are fully in the consuming repo; works offline; no `.gitmodules` confusion; `git clone` just works; history squashed on pull | Slightly complex pull/push commands; files duplicated in consuming repo | Kubernetes, many Google projects |
| **B. Git submodule** | Clean separation; no file duplication; explicit version pinning | `git clone --recursive` required; easy to get into detached-HEAD state; confuses less-experienced git users; CI needs extra steps | Many open-source projects |
| **C. Published shell package (e.g., basher)** | True package management; versioned releases | Shell package managers are niche; tooling is immature; adds a runtime dependency on the package manager | Rare in practice |

**Recommendation:** Option A (git subtree with `--squash`). It's the simplest model for a single developer, requires no extra tooling, and the consuming repo is always self-contained.

### Q2: What happens to `scripts/orchestrate.sh` (legacy)?

| Option | Tradeoffs |
|--------|-----------|
| **A. Keep in artwork-db only** | It's the working orchestrator today. The modern version exists but is marked "requires thorough testing." Keep legacy until modern is validated, then delete. |
| **B. Move to toolkit** | It's generic in principle but hasn't been parameterized. Moving it before validation is risky. |
| **C. Delete now, use modern** | Risk: modern isn't fully tested yet. |

**Recommendation:** Option A. Keep `orchestrate.sh` in artwork-db. The Makefile already calls `orchestrate_modern.sh` for most targets. Once modern is validated E2E, delete legacy.

### Q3: Toolkit repo name?

| Option | Notes |
|--------|-------|
| `snowflake-toolkit` | Clear, searchable, matches npm/PyPI naming patterns |
| `snowflake-cli-bootstrap` | More specific but limits future scope |
| `sf-iac-framework` | Terse but less discoverable |

**Recommendation:** `snowflake-toolkit` (or `snowflake-iac-toolkit` if the owner wants to avoid confusion with Snowflake's official `snowflake-cli`).

### Q4: Should `bootstrap.py` stay in the toolkit or move to artwork-db?

The preflight currently hardcodes `ARTWORK_ADMIN`. After parameterization, it becomes a generic "verify role X has privileges Y" utility.

| Option | Tradeoffs |
|--------|-----------|
| **A. Keep in toolkit (parameterized)** | Generic privilege preflight is a toolkit concern. Any project can use it. |
| **B. Move to artwork-db** | It's tightly coupled to the create_roles.sql file structure today. Parameterization adds complexity. |

**Recommendation:** Option A. The preflight pattern is generic ("verify a role has these grants before proceeding"). The `--role-name` + `--roles-sql` parameters make it project-agnostic. The `infrastructure/create_roles.sql` path is passed by the caller (artwork-db's Makefile), not baked into the script.

### Q5: Timeline preference for the migration?

This plan is designed for incremental execution. The owner can:
- Do Phase 0 + 1 in one session (refactor + extract dbt-diagnostics)
- Do Phase 2 in a separate session
- Do Phase 3 + 4 whenever confident

No phase has a deadline. Each phase produces a working state.

---

## Appendix A: Final Repo Structures

### snowflake-toolkit/
```
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
```
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
```
artwork-db/
  vendor/
    snowflake-toolkit/  (git subtree)
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

---

## Appendix B: Makefile After Migration (artwork-db)

```makefile
# artwork-db Makefile (post-toolkit-extraction)
TOOLKIT_DIR := vendor/snowflake-toolkit
CONN ?= admin
VARS ?=
DBT_PROJECT_DIR := artwork_pipeline

# Toolkit entry points
ORCHESTRATE := bash $(TOOLKIT_DIR)/orchestrate_modern.sh
SETUP := bash $(TOOLKIT_DIR)/snowflake_cli/setup.sh

chmod:
  @bash $(TOOLKIT_DIR)/bootstrap_chmod.sh

iac: chmod
  $(ORCHESTRATE) --ddl-dir infrastructure/ --manifest scripts/manifest.txt --phase infra --connection $(CONN)
  $(ORCHESTRATE) --ddl-dir git-setup/ --manifest scripts/manifest.txt --phase bootstrap --connection $(CONN)

infra: chmod
  $(ORCHESTRATE) --ddl-dir infrastructure/ --manifest scripts/manifest.txt --phase infra --connection $(CONN)

loader: chmod
  $(SETUP) --profile $(CONN) --phase loader

transformer: chmod
  $(SETUP) --profile $(CONN) --phase transformer

# ... (dbt and extraction targets unchanged)

update-toolkit:
  git subtree pull --prefix=$(TOOLKIT_DIR) \
    git@github.com:dckallos/snowflake-toolkit.git donkey-kong-sandbox --squash
```
