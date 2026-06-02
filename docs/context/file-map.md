# Tier 2 — File map

One line per file: purpose + line count + "open full source only if…" trigger.
Consult this before opening any source.

**Coverage:** every substantive file is row-mapped below. Total file/dir counts are
intentionally NOT hardcoded here (they rot) — reconcile against `ls -R` when needed.
The `Verified` column records provenance: a date = read end-to-end that window;
`prior` = trusted from an earlier window, not re-read. Trivial files (`.gitignore`,
`LICENSE`) and the `docs/context/*.md` docs themselves are intentionally not row-mapped.

**Session-3 (2026-05-31) — APPLIED + connection-resilience research.** Live IaC
additions: `create_bronze_views.sql`/`drop_bronze_views.sql` (`MET_WORKLIST`);
`create_run_control.sql`/`drop_run_control.sql` (`RUN_CONTROL` checkpoint table);
`MET_ENRICHMENT_CONTROL` + `MET_CSV_SNAPSHOT` in `create_bronze_tables.sql`; real
`MET_LEASE_RECLAIM_TASK` in `create_tasks.sql`; and the `grant_privileges.sql →
create_grants.sql` rename. Plus a standalone read-only ops suite — `scripts/check.sh`,
`scripts/checkpoint.sh`, `scripts/sql/show_{active_sessions,run_control,pipeline_status}.sql`
— and two append-only docs: `docs/context/session-3-progress-log.md` (restart trail)
+ `docs/context/connection-resilience.md` (research + advisory-lease design).

## scripts/snowflake_cli/ (Workflow 1 — reviewed)

| File | Lines | Purpose | Verified | Open source only if… |
|---|---|---|---|---|
| `setup.sh` | ~ | Entry point; `--phase` dispatcher (prereq/init-profile/admin/loader/promote/all/**list/switch**), `--profile`/`--admin-conn`/`--loader-conn` selectors, chmods + runs 00–08 | 2026-06-01 | changing phase routing |
| `_lib.sh` | ~ | Shared helpers (TOML parse/rewrite incl. top-level keys, JWT verify, conn-aware resolvers, key-path derivation, `list_connections`/`set_default_connection`, `prune_backups`) | 2026-06-01 | need exact awk/TOML logic |
| `init_profile.sh` | ~120 | Local-only: seed `[connections.<admin>]` non-destructively (prompts/env) + set `default_connection_name`; runs inside `prereq` between 02 and 03 | 2026-06-01 | changing config.toml seeding |
| `00_install_snowflake_cli.sh` | 29 | brew/pipx install, idempotent | prior | changing install path |
| `01_init_snowflake_home.sh` | 25 | mkdir ~/.snowflake/{keys,logs}, chmod 700 | prior | changing perms/layout |
| `02_generate_admin_keypair.sh` | 40 | PKCS#8 keypair, overwrite-guarded | prior | changing key type/encryption |
| `03_lock_config_permissions.sh` | 34 | chmod 600 config.toml + key | prior | — |
| `04_register_admin_public_key.sh` | 81 | ONLY password-auth call; registers RSA pubkey | prior | changing bootstrap auth |
| `05_verify_admin_jwt.sh` | 54 | JWT verify vs current warehouse | prior | — |
| `06_setup_loader_keypair.sh` | 107 | loader key-pair: lazy keygen → register pubkey via admin JWT → upsert `[connections.loader]` | 2026-05-31 | changing loader auth |
| `07_test_loader_connection.sh` | 24 | `snow connection test -c loader` (key-pair; no `.env`) | 2026-05-31 | — |
| `08_promote_admin_warehouse.sh` | 152 | promote admin warehouse → ARTWORK_WH, rewrite config | prior | changing promotion logic |

## git-setup/ (reviewed 2026-05-30 — see `ddl-infrastructure.md` "Git bind chain")

| File | Lines | Purpose | Verified | Open source only if… |
|---|---|---|---|---|
| `create_git_ops_db.sql` | 51 | `ARTWORK_OPS` DB + `GIT` schema + `github_pat_artwork_db` SECRET (templated PAT) | 2026-05-30 | changing the secret/DB host |
| `create_api_integration.sql` | 38 | API INTEGRATION `github_artwork_db_integration`; whitelists the PAT secret | 2026-05-30 | debugging Git bind chain |
| `create_git_repository.sql` | 67 | GIT REPOSITORY `artwork_db` (binds integration+creds), FETCH, GRANT READ to ADMIN | 2026-05-30 | changing origin/creds/grant |
| `drop_git_repository.sql` | 38 | rollback step 1: `DROP GIT REPOSITORY IF EXISTS` (FQ) | 2026-05-30 | rolling back |
| `drop_api_integration.sql` | 39 | rollback step 2: `DROP API INTEGRATION IF EXISTS` | 2026-05-30 | rolling back |
| `drop_git_ops_db.sql` | 60 | rollback step 3: FQ `DROP SECRET`+`SCHEMA`+`DATABASE` | 2026-05-30 | rolling back |
| `operator/register_admin_public_key.sql` | 33 | `ALTER USER … SET RSA_PUBLIC_KEY` (+ DESCRIBE) | prior | — |
| `operator/register_loader_public_key.sql` | 33 | `ALTER USER … SET RSA_PUBLIC_KEY` for the loader (+ DESCRIBE); applied by `06_setup_loader_keypair.sh` | 2026-05-31 | — |
| `.env.example` | 6 | gitignored `git-setup/.env` template; ships blank `GITHUB_PAT=` | 2026-05-30 | — |
| `README.md` | 112 | git-setup runbook; **written in retired B###/V###/R### scheme (stale)** | 2026-05-30 | need narrative context |

## infrastructure/ (Workflow 2 — reviewed)

Prefix-free `create_*` / `drop_*` pairs, matched **by base name** (no V/R/B
prefixes — retired; see `ddl-infrastructure.md`). Apply order lives in
`scripts/manifest.txt`, not the names. **11 create/drop pairs present** (Session-3
added the `bronze_views` and `run_control` pairs; the `grant_privileges → create_grants`
rename makes grants an auto-paired `create_`).

| File | Lines | Purpose | Verified | Open source only if… |
|---|---|---|---|---|
| `create_roles.sql` | 46 | 3 roles (LOADER/TRANSFORMER/ADMIN) + hierarchy + account grants (CREATE WH/DB; **EXECUTE TASK now uncommented, Session-3 lockstep with create_tasks**) | 2026-05-31 | changing role model / account grants |
| `create_warehouses.sql` | 15 | `ARTWORK_WH` X-Small, auto-suspend 60 (`IF NOT EXISTS`) | prior | resizing/adding WH |
| `create_databases_and_schemas.sql` | 21 | `ARTWORK_DB` + BRONZE/SILVER/GOLD schemas (`IF NOT EXISTS`) | prior | adding schemas |
| `create_file_formats.sql` | 22 | `JSON_RAW`, `PARQUET_RAW` in BRONZE (`OR REPLACE`, UPPERCASE) | 2026-05-31 | adding formats |
| `create_stages.sql` | 14 | `BRONZE_LOAD_STAGE` internal stage (`OR REPLACE`, UPPERCASE) | 2026-05-31 | adding stages |
| `create_bronze_tables.sql` | 124 | 6 `RAW_*` VARIANT tables + `EXTRACTION_LOG` + **Session-3: `MET_ENRICHMENT_CONTROL` (lease/state) + `MET_CSV_SNAPSHOT` (VARIANT raw CSV)** (`IF NOT EXISTS`) | 2026-05-31 | schema changes |
| `create_bronze_views.sql` *(NEW, Session-3)* | 59 | `MET_WORKLIST` view (control × CSV-snapshot, IMG-02 priority, lease-aware; `OR REPLACE`) | 2026-05-31 | changing worklist priority/filters |
| `create_run_control.sql` *(NEW, Session-3)* | 46 | `RUN_CONTROL` durable checkpoint table — PK (run_id, step), VARIANT checkpoint, session_id/query_tag provenance; resume work across connection drops (`IF NOT EXISTS`) | 2026-05-31 | changing checkpoint schema |
| `create_service_user.sql` | 69 | `ARTWORK_LOADER_SVC` SERVICE user; `CREATE … IF NOT EXISTS` then idempotent `ALTER USER` converge to `TYPE=SERVICE` + `UNSET PASSWORD` (AUTH-01 applied + verified 2026-05-31; key-pair only) | 2026-05-31 | auth/identity changes |
| `create_tasks.sql` | 44 | **Session-3: real `MET_LEASE_RECLAIM_TASK`** (hourly CRON, 30-min TTL lease reclaim, ARTWORK_WH; `OR REPLACE` + `RESUME`) | 2026-05-31 | defining/altering tasks |
| `drop_*.sql` (11) | — | paired rollbacks; `DROP … IF EXISTS`; incl. `drop_bronze_views` (drops view before bases), `drop_run_control`, + real `drop_tasks` | 2026-05-31 | rolling back |
| `create_grants.sql` *(renamed from grant_privileges.sql, Session-3)* | 51 | ALL+FUTURE grants to functional roles + **LOADER SELECT on ALL+FUTURE VIEWS in BRONZE** (runs as ARTWORK_ADMIN) | 2026-05-31 | changing grants |
| `refresh_grants.sql` | 24 | repeatable: re-grant ALL (current) incl. **VIEWS**; no drop | 2026-05-31 | after new objects land |
| `drop_grants.sql` | 41 | no-op SELECT (grants cascade); reworded to reference `create_grants.sql` | 2026-05-31 | implementing real REVOKEs |

## scripts/ (orchestration — Workflow 2)

| File | Lines | Purpose | Verified | Open source only if… |
|---|---|---|---|---|
| `orchestrate.sh` | — | bash IaC entry point; reads `manifest.txt`, maps `--phase {bootstrap\|infra\|all\|down}` by directory, pairs `create_→drop_`, runs preflight after `create_roles.sql` | prior | changing phase routing / preflight / secret suppression |
| `manifest.txt` | — | **single source of apply order** (forward) + teardown reversal; header has stale V/R/B + `bootstrap.py` refs | prior | changing apply order |
| `bootstrap.py` | 281 | thin Python preflight (`verify-contract`, `assert-account-privileges`); authors no SQL | 2026-05-30 | changing privilege checks |
| `apply_sql.sh` | 67 | `snow sql --filename` forward wrapper; `--enhanced-exit-codes`; `SNOW_SUPPRESS_STDOUT` secret path; **stale B001 ref l.38** | 2026-05-30 | debugging CLI invocation |
| `rollback_sql.sh` | 32 | paired-drop wrapper; mirrors apply connection logic | 2026-05-30 | debugging CLI invocation |
| `secret_bearing.txt` | — | scripts whose stdout is suppressed (fail-closed on PAT marker) | prior | adding secret-bearing scripts |
| `bootstrap_chmod.sh`, `git_mark_executable.sh`, `executable_files.txt`, `sql/show_admin_account_grants.sql` | — | chmod policy + helpers | prior | — |
| `check.sh` *(NEW, Session-3)* | 36 | standalone read-only ad-hoc SQL runner (`snow sql --filename`); not in orchestrator | 2026-05-31 | adding/altering ad-hoc checks |
| `checkpoint.sh` *(NEW, Session-3)* | 51 | write one `RUN_CONTROL` checkpoint (`<run_id> <step> [status] [note]`); standalone DML, sets QUERY_TAG | 2026-05-31 | changing checkpoint write |
| `sql/show_active_sessions.sql`, `sql/show_run_control.sql`, `sql/show_pipeline_status.sql` *(NEW, Session-3)* | — | read-only checks: live sessions / fork detection, run-control trail + dual-instance smell test, pipeline object+task status | 2026-05-31 | — |

## Root / other

| File | Lines | Purpose | Verified | Open source only if… |
|---|---|---|---|---|
| `Makefile` | — | task runner (see ddl-infrastructure.md carryover) | prior | changing make targets |
| `.env.example` | 33 | runtime (loader) env template; `SNOWFLAKE_*` for `ARTWORK_LOADER_SVC` + `SMITHSONIAN_API_KEY` (no consumer yet); stale `V008` refs | 2026-05-30 | — |
| `profiles.yml.example` | 39 | dbt-core profile (env_var + key-pair, dev→SILVER/prod→GOLD); **gap for Snowflake-native dbt** (extraction.md) | 2026-05-30 | — |
| `requirements.txt` | — | root pin set (mirrors extraction deps) | 2026-05-30 | bumping pins |
| `rename_and_update.py` | 91 | **spent one-shot** V###/R### → prefix-free `git mv` + ref-rewrite migration; historical/dead, candidate for removal | 2026-05-30 | auditing the prefix-retirement history |
| `.gitignore`, `LICENSE` | — | trivial; not row-mapped | prior | — |

## extraction/met/ (Workflow 3 — reviewed; see `extraction.md`)

Standalone Met OpenAccess → Bronze ETL. SQL externalized in `sql/*.sql`; SQLite
is intermediate, `ARTWORK_DB.BRONZE.raw_met_objects` is the destination.
Note: `extraction/__init__.py` (added 2026-05-31) makes `extraction` a **regular**
package (was a PEP 420 namespace package); all 3 packages resolve + resources load (verified).

| File | Lines | Purpose | Verified | Open full source only if… |
|---|---|---|---|---|
| `run.py` | 137 | argparse CLI: bootstrap/**snapshot**/enrich/upload/status/all | 2026-05-31 | changing CLI/phase wiring |
| `config.py` | 71 | `Config` dataclass; `MET_*`+`SNOWFLAKE_*` env w/ defaults | 2026-05-30 | changing settings/defaults; **stale V001-V007 ref (l.53-54)** |
| `db.py` | 43 | `load_sql()`, `initialize_database()`, `connect()` | 2026-05-30 | changing SQL-load or SQLite conn |
| `csv_bootstrap.py` | 268 | download CSV + `_map_row` + batched UPSERT + **`assert_real_met_csv` DATA-06 guard** | 2026-05-31 | adding/removing a CSV column; CSV-integrity rules |
| `snapshot_loader.py` | 302 | **Section C Phase 1:** full CSV → VARIANT NDJSON → PUT → COPY (session STG) → MERGE `MET_CSV_SNAPSHOT` (keyed `object_id`); AUTO-03 log; Option B | 2026-05-31 | changing snapshot load/MERGE/AUTO-03 |
| `image_enricher.py` | 280 | async API fetch; rate limiter + backoff (Snowflake-free today; Phase 3 will add lease-claim) | 2026-05-30 | changing retry/limiter/state logic |
| `snowflake_uploader.py` | 289 | NDJSON + PUT + COPY INTO Bronze; marks upload state; `_snowflake_connect` (key-pair) | 2026-05-31 | changing Bronze JSON shape / COPY mapping / connect |
| `sql/schema.sql` | 97 | SQLite DDL: `met_artworks` + `extraction_runs` + indexes | 2026-05-30 | schema changes |
| `sql/upsert_artwork.sql` | 79 | `INSERT … ON CONFLICT DO UPDATE` (image/bronze cols excluded) | 2026-05-30 | column changes |
| `sql/update_enrichment_done.sql` | 9 | mark row `done` w/ image URLs | 2026-05-30 | — |
| `sql/copy_into_bronze.sql` | 18 | templated COPY INTO raw_met_objects; `PURGE=TRUE` | 2026-05-30 | changing load target/format |
| `sql/copy_into_snapshot_stg.sql` | 20 | templated COPY of CSV JSON into the session `MET_CSV_SNAPSHOT_STG` (compiled clean 2026-05-31) | 2026-05-31 | changing snapshot stage/format |
| `sql/merge_csv_snapshot.sql` | 24 | templated MERGE STG → `MET_CSV_SNAPSHOT` on `object_id` (QUALIFY de-dup; compiled clean 2026-05-31) | 2026-05-31 | changing snapshot MERGE/keys |
| `sql/__init__.py` | 3 | package marker for `importlib.resources` | 2026-05-30 | — |
| `__init__.py` | 5 | package docstring | 2026-05-30 | — |
| `requirements.txt` | 5 | connector/requests/aiohttp/dotenv | 2026-05-30 | bumping pins |
| `.env.example` | 25 | Met-specific env template; **hardcoded sample account (l.14)** | 2026-05-30 | — |
| `README.md` | 207 | operator runbook (phases, recovery, tuning, verify SQL); **stale V001-V007 ref (l.37)** | 2026-05-30 | need narrative/recovery context |

## analysis/ (Section C — read-only profiling, not IaC, not operational ETL)

| File | Lines | Purpose | Verified | Open full source only if… |
|---|---|---|---|---|
| `met_snapshot_profile.sql` | 84 | **Section C Phase 1.5:** read-only profile of `MET_CSV_SNAPSHOT` (counts by department / classification / culture×period / century / public-domain×highlight + a worklist-priority candidate-slice query) so the owner picks the first enrichment slice. Most complex query compiled clean (`only_compile`, 2026-05-31) | 2026-05-31 | adding a slice axis |
