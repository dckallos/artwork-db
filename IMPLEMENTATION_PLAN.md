# IMPLEMENTATION_PLAN.md — Dagster OSS orchestration optimization (artwork-db)

Single source of truth. Authored by fork-39b1c4 (see `.fork_id`). Update if the
codebase diverges. Priority order preserved from the task brief.

## Reconciliation baseline (state discovered this session)
Not a git repo. Multiple forks edited files. ONE fork produced a complete, wired,
self-consistent implementation; others left orphaned/contradictory duplicates.

### WIRED & authoritative (imported by definitions.py) — KEEP
- `orchestration/artwork_orchestration/assets_extraction.py`
  - `EXTRACTION_RETRY_POLICY = RetryPolicy(max_retries=2, delay=30, backoff=EXPONENTIAL, jitter=PLUS_MINUS)` (WS2)
  - Timeout consts: `TIMEOUT_SNAPSHOT=1800`, `TIMEOUT_SEED=900`, `TIMEOUT_ENRICH_BATCH=5400` (WS2, mirrored to op_tags `dagster/max_runtime`)
  - Sizing: `MET_ENRICH_BATCH_SIZE=2000`, `MET_ENRICH_MAX_BATCHES=1`; rps: `MET_API_RPS_BUDGET=30`, `MET_ENRICH_CONCURRENCY=3` (WS1/WS3)
  - Inline `MET_DEPARTMENTS` (slug->dept) + `met_department_partitions = StaticPartitionsDefinition` (WS3) — THE partitions used by assets
  - Assets: `met_csv_snapshot`, `met_enrichment_control`, `met_enrichment_batch` (partitioned, bounded, resumable — WS1), `raw_met_objects` (verification checkpoint keyed to dbt source), `aic_snapshot` (multi_asset -> raw_aic_artworks + raw_aic_agents)
  - Snowflake helper convention: `_sf_scalars(context, {...})`
- `jobs.py` — `met_ingest_job`, `met_enrich_next_batch_job` (WS1 "next batch"), `ingest_all_job`, `dbt_build_job`, `full_pipeline_job`
- `observability.py` — `extraction_asset_checks` (row-count + orphaned-lease + aic) + `freshness_checks` (defensive import); uses `_sf_scalars` (exists) — VALID (WS5)
- `schedules.py` — `daily_dbt_schedule`, `hourly_met_enrich_schedule`, `weekly_full_pipeline_schedule` (all STOPPED)
- `definitions.py` — wires assets + `observability` checks + jobs + schedules + `dbt_resource`
- `resources.py`, `translator.py`, `assets_dbt.py` — base, dbt source keys intact
- CLI `extraction/met/run.py` — already exposes `--department`, `--batch-size`, `--max-batches`; `control_enricher.enrich_from_control(...)` accepts `department`

### ORPHANED / CONTRADICTORY (NOT imported anywhere) — DELETE
1. `checks.py` — dup checks; imports `_scalar`/`_snowflake_cursor` from assets_extraction (DO NOT EXIST) -> broken if wired
2. `asset_checks.py` — dup checks via `sf_introspect`
3. `sf_introspect.py` — support module only for asset_checks.py
4. `partitions.py` — dup department map/partitions with DIFFERENT slugs & counts vs the inline `MET_DEPARTMENTS` the assets actually use

Resolution rule applied: keep the single wired implementation; delete dead duplicates
("no duplicate/again function definitions from fork collisions").

## Remaining work (this fork)
- [x] STEP1: write this plan
- [x] STEP2: init append-only session-progress-log.md with unique fork id
- [ ] R1: delete 4 orphan files (checks.py, asset_checks.py, sf_introspect.py, partitions.py)
- [ ] WS4: fix rate-limit guard. Live `dagster.yaml` gates run-tag `artwork/rate_limited_api: met`, but QueuedRunCoordinator gates on RUN tags while the asset only sets an op-tag. FIX: add run-tag `{"artwork/rate_limited_api": "met"}` to enrichment-bearing jobs (`met_enrich_next_batch_job`, `met_ingest_job`, `full_pipeline_job`) in jobs.py so `tag_concurrency_limits` (limit 2) actually caps concurrent Met enrichment. Keep max_concurrent_runs=2, multiprocess max=4, run_monitoring on.
- [ ] VALIDATE: background `python -c 'import artwork_orchestration.definitions'`; confirm no NameError, single department map, dbt source keys unchanged.
- [ ] WS6 (DOCS ONLY): verify/extend orchestration/PRODUCTION.md — Postgres storage, run daemon, enable the 2 STOPPED schedules, failure sensor -> webhook/email. No code.

## Invariants that must not break
- dbt<->Dagster lineage: terminal extraction assets keep `AssetKey([source, table])` (translator.py). Do not rename.
- Only ONE department partition map (assets_extraction inline). No second map.
- No new credentials; assets shell out to existing CLIs.

## PHASE 2 — Config-driven, multi-museum architecture (approved 2026-07-02)
Decisions: keep subprocess CLI calls; orchestration-layer only (extraction/ CLIs
untouched, but must honor a documented CLI contract). Goal: adding museum N = add ONE
data file (`sources/<key>.py`) + register it. Zero factory/job/check/definition edits.

### New package layout (artwork_orchestration/)
- `config.py`      — `BronzeConfig(database, schema)` (env-overridable) + `.fqn(table)`; central. Kills every hardcoded `ARTWORK_DB.BRONZE.*`.
- `policies.py`    — `EXTRACTION_RETRY_POLICY`, `timeout_tags()`, `RATE_LIMIT_TAG_KEY`, env knobs (`MET_ENRICH_BATCH_SIZE`, `MAX_BATCHES`, `RPS_BUDGET`, `CONCURRENCY`).
- `_runner.py`     — `run_module(context, cli_module, args, extra_env)` (was `_run_module`).
- `_snowflake.py`  — `sf_scalars(context, {label: sql})` (was `_sf_scalars`); removes observability->assets_extraction coupling.
- `sources/spec.py`— dataclasses (the abstraction):
  - `PartitionDim(name, cli_flag, values: {slug->real})` -> `.partitions_def()`
  - `Produces(table, dbt_source=False, physical=None, nonempty=False, severity="ERROR", freshness_days=None)` — physical defaults UPPER(table)
  - `ExtractionStep(name, subcommand|None, static_args=(), uses_batch_flags=False, partition=None, rate_limited=False, api_bound=True, produces=(), extra_metadata_sql={})`
  - `HealthCheck(name, attach_table, sql, ok: Callable[[int],bool], severity)`
  - `SourceSpec(key, cli_module, steps, checks=(), rate_limit_value=None, rps_env_var="MET_API_RPS")`; `.group_name -> f"extraction_{key}"`
- `sources/met.py`, `sources/aic.py` — pure data `SourceSpec` instances.
- `sources/__init__.py` — `REGISTRY = (MET_SPEC, AIC_SPEC)` + lookups.
- `factories/assets.py`  — `build_source_assets(spec)`: one `@asset` per step; `@multi_asset` when a step has >1 dbt-source Produces. Verify-only step (subcommand=None) does no CLI. Partitioned step gets `partitions_def` + maps partition_key->real value->cli flag + per-worker rps env.
- `factories/checks.py`  — `build_source_checks(spec)` (nonempty from Produces + custom HealthChecks) + `build_freshness_checks(REGISTRY)` (+ static GOLD marts list).
- `factories/jobs.py`    — `build_jobs(REGISTRY, dbt_assets)`: per-source `{key}_ingest_job`, `{key}_enrich_next_batch_job` (if a partitioned rate-limited step exists); global `ingest_all_job`, `dbt_build_job`, `full_pipeline_job`. Rate-limit run tag `{artwork/rate_limited_api: spec.rate_limit_value}` on any job that includes a rate-limited step.
- `factories/schedules.py`— per-source enrich schedule (STOPPED) + global daily dbt + weekly full (STOPPED).
- `definitions.py` — loops REGISTRY -> assets/checks/jobs/schedules; +dbt assets +resources.

### EXACT keys/tags to preserve (parity contract)
- met: `["met","csv_snapshot"]` (internal), `dbt_source("met","met_enrichment_control")`, `["met","enrichment_batch"]` (partitioned, internal), `dbt_source("met","raw_met_objects")` (verify terminal).
- aic: multi_asset -> `dbt_source("aic","raw_aic_artworks")` + `dbt_source("aic","raw_aic_agents")`.
- groups `extraction_met`/`extraction_aic`; RetryPolicy(2,EXP,+/-jitter); timeouts 1800/900/5400; run tag `artwork/rate_limited_api=met` on met_ingest/met_enrich_next_batch/ingest_all/full_pipeline (NOT dbt_build); 19 dept partitions.
- Physical tables: RAW_MET_OBJECTS, MET_ENRICHMENT_CONTROL, MET_CSV_SNAPSHOT, MET_WORKLIST, RAW_AIC_ARTWORKS, RAW_AIC_AGENTS.

### Retire after parity
Delete `assets_extraction.py`, `jobs.py`, `observability.py`, `schedules.py` once factories reproduce identical defs (verified by import + key/tag diff under /tmp venv).

## PHASE 2 STATUS — DONE + fork reconciliation (2026-07-02)
A parallel Cortex fork ("Fork B", never logged an ID) concurrently built the same
refactor with an INCOMPATIBLE `Output`-based API. Reconciled to option A (my
`Produces` API). Final coherent package (all under `artwork_orchestration/`):
- infra: `config.py` (BRONZE + REPO_ROOT), `policies.py`, `_runner.py`, `_snowflake.py` (sf_scalars + render)
- `sources/`: `spec.py`, `met.py`, `aic.py`, `__init__.py` (REGISTRY)
- `factories/`: `assets.py`, `checks.py`, `jobs.py`, `schedules.py`
- `definitions.py` (kept B's — loops REGISTRY), `resources.py`, `translator.py`, `assets_dbt.py`
DELETED: Fork-B duplicates `runner.py`, `snowflake_io.py`; old monolith `assets_extraction.py`, `jobs.py`, `observability.py`, `schedules.py`.
DELIBERATE IMPROVEMENT over strict parity (sanctioned "update the architecture"):
enrichment is EXCLUDED from `full_pipeline_job` + `ingest_all_job`; each rate-limited
source gets `{key}_enrich_next_batch_job` carrying tag value=key -> fixes the
single-valued run-tag problem at 20-50 museums.
VALIDATED under real Dagster (stubbed dbt/resources to skip network manifest): full
Definitions loads; 6 extraction keys + groups + 19 partitions + 3 data checks + 6 jobs
with correct rate-tags. dbt-manifest full load still blocked by network (unchanged env limit).

