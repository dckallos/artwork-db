# Tier 2 — File map

One line per file: purpose + line count + "open full source only if…" trigger.
Consult this before opening any source. **Partial:** auth/connection and
infrastructure files reviewed; extraction is listed but not yet summarized.

## scripts/snowflake_cli/ (Workflow 1 — reviewed)

| File | Lines | Purpose | Open source only if… |
|---|---|---|---|
| `setup.sh` | ~ | Entry point; `--phase` dispatcher, chmods + runs 00–08 | changing phase routing |
| `_lib.sh` | ~ | Shared helpers (TOML parse/rewrite, JWT verify, resolvers) | need exact awk/TOML logic |
| `00_install_snowflake_cli.sh` | 29 | brew/pipx install, idempotent | changing install path |
| `01_init_snowflake_home.sh` | 25 | mkdir ~/.snowflake/{keys,logs}, chmod 700 | changing perms/layout |
| `02_generate_admin_keypair.sh` | 40 | PKCS#8 keypair, overwrite-guarded | changing key type/encryption |
| `03_lock_config_permissions.sh` | 34 | chmod 600 config.toml + key | — |
| `04_register_admin_public_key.sh` | 81 | ONLY password-auth call; registers RSA pubkey | changing bootstrap auth |
| `05_verify_admin_jwt.sh` | 54 | JWT verify vs current warehouse | — |
| `06_rotate_loader_password.sh` | 47 | rotate loader pw via admin JWT | **paired .sql is empty (gap)** |
| `07_test_loader_connection.sh` | 40 | source .env, test loader conn | — |
| `08_promote_admin_warehouse.sh` | 152 | promote admin warehouse → ARTWORK_WH, rewrite config | changing promotion logic |

## git-setup/ (auth-chain files reviewed; DDL pending)

| File | Lines | Purpose | Open source only if… |
|---|---|---|---|
| `create_api_integration.sql` | 39 | API INTEGRATION github_artwork_db_integration; whitelists PAT secret | debugging Git bind chain |
| `operator/register_admin_public_key.sql` | 34 | `ALTER USER &{admin_user} SET RSA_PUBLIC_KEY` (+ DESCRIBE) | — |
| `operator/rotate_loader_password.sql` | 0 | **EMPTY — expected ALTER USER SET PASSWORD (gap)** | implementing the fix |
| `create_git_ops_db.sql` | — | GIT ops DB + PAT secret (Workflow 2) | reviewing Workflow 2 |
| `create_git_repository.sql` | — | GIT REPOSITORY object (Workflow 2) | reviewing Workflow 2 |
| `drop_*.sql` | — | paired rollbacks | rolling back |
| `README.md` | — | git-setup walkthrough | need narrative context |

## infrastructure/ (Workflow 2 — reviewed)

Prefix-free `create_*` / `drop_*` pairs, matched **by base name** (no V/R/B
prefixes — retired; see `ddl-infrastructure.md`). Apply order lives in
`scripts/manifest.txt`, not the names. All 8 create/drop pairs present.

| File | Lines | Purpose | Open source only if… |
|---|---|---|---|
| `create_roles.sql` | 46 | 3 roles (LOADER/TRANSFORMER/ADMIN) + hierarchy + account grants (CREATE WH/DB; EXECUTE TASK commented out) | changing role model / account grants |
| `create_warehouses.sql` | 15 | `ARTWORK_WH` X-Small, auto-suspend 60 (`IF NOT EXISTS`) | resizing/adding WH |
| `create_databases_and_schemas.sql` | 21 | `ARTWORK_DB` + BRONZE/SILVER/GOLD schemas (`IF NOT EXISTS`) | adding schemas |
| `create_file_formats.sql` | 22 | `json_raw`, `parquet_raw` in BRONZE (`OR REPLACE`) | adding formats |
| `create_stages.sql` | 14 | `bronze_load_stage` internal stage (`OR REPLACE`); trailing-ws line 14 | adding stages |
| `create_bronze_tables.sql` | 85 | 6 `raw_*` VARIANT tables + `extraction_log` (`IF NOT EXISTS`) | schema changes |
| `create_service_user.sql` | 31 | `ARTWORK_LOADER_SVC` user, placeholder pw to rotate | auth/identity changes |
| `create_tasks.sql` | 7 | **placeholder** (bare SELECT — no real tasks) | defining real tasks |
| `drop_*.sql` (8) | — | paired rollbacks; `DROP … IF EXISTS`; `drop_tasks` is a placeholder too | rolling back / defining tasks |
| `grant_privileges.sql` | 45 | ALL+FUTURE grants to functional roles (runs as ARTWORK_ADMIN) | changing grants |
| `refresh_grants.sql` | 23 | repeatable: re-grant ALL (current) only; no drop | after new objects land |
| `drop_grants.sql` | 40 | no-op SELECT (grants cascade); **not in manifest → never auto-run**; stale V###/B002 comment refs | implementing real REVOKEs |

## scripts/ (orchestration — Workflow 2)

| File | Purpose | Open source only if… |
|---|---|---|
| `orchestrate.sh` | bash IaC entry point; reads `manifest.txt`, maps `--phase {bootstrap\|infra\|all\|down}` by directory, pairs `create_→drop_`, runs preflight after `create_roles.sql` | changing phase routing / preflight / secret suppression |
| `manifest.txt` | **single source of apply order** (forward) + teardown reversal; header has stale V/R/B + `bootstrap.py` refs | changing apply order |
| `bootstrap.py` | thin Python preflight (`verify-contract`, `assert-account-privileges`) | changing privilege checks |
| `apply_sql.sh` / `rollback_sql.sh` | `snow sql --filename` wrappers (forward / paired drop) | debugging CLI invocation |
| `secret_bearing.txt` | scripts whose stdout is suppressed (fail-closed on PAT marker) | adding secret-bearing scripts |
| `bootstrap_chmod.sh`, `git_mark_executable.sh`, `executable_files.txt`, `sql/show_admin_account_grants.sql` | chmod policy + helpers | — |

## Root / other

| File | Purpose |
|---|---|
| `Makefile` | task runner (reviewed — see ddl-infrastructure.md carryover) |
| `.env.example` | runtime (loader) env template |
| `profiles.yml.example` | dbt profile (env_var-based; gap for native dbt) |
| `requirements.txt`, `rename_and_update.py` | not yet reviewed |
| `extraction/met/*` | Phase 1A extractor (separate workflow; out of current scope) |
