# Orchestration: operations & path to production

This documents how the Dagster layer is meant to be operated, and how to evolve it
from the current local `dagster dev` setup toward a production-ready deployment.
It complements the code in `artwork_orchestration/`.

## Asset graph (after the 2026-07 optimization pass)

```
met_csv_snapshot ─► met_enrichment_control ─► met_enrichment_batch  ─► raw_met_objects ─► [dbt staging] ─► [dbt Gold]
                                              (PARTITIONED by dept)     (checkpoint)
aic_snapshot ─► (raw_aic_artworks, raw_aic_agents) ─────────────────────────────────► [dbt staging] ─► [dbt Gold]
```

Key change: the Met enrichment is no longer one unbounded 24h+ step. It is a
**department-partitioned, bounded** asset (`met_enrichment_batch`) that processes
`batching.size * batching.max_batches` rows (from `framework.yaml`) per materialization
and is fully resumable. `raw_met_objects` is now a lightweight **checkpoint** (the Bronze
table is assembled server-side inside each batch) that keeps the dbt source key.

## Jobs

All jobs are **generated from the source registry** (`factories/jobs.py` looping
`sources.REGISTRY`) — adding a museum adds its jobs automatically.

| Job                           | What it runs                                                       |
|-------------------------------|--------------------------------------------------------------------|
| `<key>_ingest_job`            | One source's full chain (e.g. `met_ingest_job`, `aic_ingest_job`)  |
| `<key>_enrich_next_batch_job` | Next bounded batch for ONE partition — only sources with enrichment (e.g. `met_enrich_next_batch_job`) |
| `ingest_all_job`              | Every source's Bronze ingest — EXCLUDING enrichment, no dbt        |
| `dbt_build_job`               | `dbt build` (models + tests)                                       |
| `full_pipeline_job`           | Everything EXCEPT bounded enrichment (snapshots/seeds/verify + dbt)|

Enrichment is deliberately kept **out** of `full_pipeline_job` and `ingest_all_job`.
It is the long, per-museum, rate-limited drain, driven by its own
`{key}_enrich_next_batch_job`. This also avoids the single-valued run-tag problem at
scale: a run can carry only ONE `artwork/rate_limited_api` value, so mixing several
museums' enrichment in one run would break per-museum capping. Each enrichment (and
per-source ingest) job for a rate-limited source therefore carries exactly one value
(its own source key), and the coordinator caps every museum's API independently.
`dbt_build_job` touches no API and is untagged.

## Adding a new museum (the whole point)

Adding source #3..N is **one YAML file, no code**. Full instructions live in
`artwork_orchestration/ADDING_A_SOURCE.md`; the field reference is `SCHEMA.md`. In brief:

1. Create the museum's Bronze tables (DDL) and its extraction CLI so that
   `python -m <cli_module> <subcommand>` runs one phase and exits 0.
2. Drop a `sources/<key>.yaml` declaring `source`, `cli_module`, and the ordered
   `steps` (each: a `name`, the CLI subcommand under `run`, and the Bronze tables it
   `produces`). Optional per-table `check_nonempty`/`fresh_within_days`; optional
   `partition_by` + `mode: batched` + `rate_limited: true` for a rate-limited API.

That's it — there is **no registry to edit**. `sources/__init__.py` scans the directory,
`loader.py` validates the YAML, and the factories generate the assets (chained by
declaration order), checks, per-source jobs, and schedule. `definitions.py` and every
factory stay untouched. See `sources/cma.yaml` for a complete worked example added this
way. The extraction CLI must honor the contract in `_runner.py`:
`python -m <cli_module> <subcommand> [flags]`, exit 0 on success; a rate-limited step
reads its per-worker request rate from the source's `rps_env_var` (default `API_RPS`).
Give each rate-limited museum its own `dagster.yaml` `tag_concurrency_limits` entry keyed
on its `artwork/rate_limited_api` value.

## Draining the Met collection

To enrich a department, materialize its partition repeatedly (each run does a
bounded slice, picks up where the last left off):

```
# UI: Assets ► met/enrichment_batch ► Materialize ► pick partition (e.g. photographs)
# or launch met_enrich_next_batch_job for that partition on a schedule.
```

Tune per-run throughput in `framework.yaml` (no code changes; env-overridable via the
`${ENV:default}` tokens shown):

- `defaults.batching.size`      (`${BATCH_SIZE:2000}`)   — rows leased+fetched per batch
- `defaults.batching.max_batches` (`${MAX_BATCHES:1}`)   — batches per materialization
- `defaults.rate_limit.concurrency` (`${API_CONCURRENCY:3}`) — max concurrent workers assumed
  when dividing the rps budget (keep in sync with `dagster.yaml` tag limit)
- `defaults.rate_limit.rps_budget` (`${API_RPS_BUDGET:30}`) — aggregate rps across ALL workers

## Concurrency and the rate-limit caveat (IMPORTANT)

The Met `_RateLimiter` is **per process**. Running N department partitions
concurrently multiplies the request rate N-fold against a single global Met API
ceiling → 403/429 throttling once the ceiling binds. Concurrency only raises
throughput while you are *latency-bound*, not once the rate cap binds.

Two guards are in place:

1. `dagster.yaml` caps the `artwork/rate_limited_api: met` run tag at **2**
   concurrent, so at most 2 Met workers ever run at once. The enrichment-bearing jobs
   set this run tag (see the Jobs section) — without it the coordinator cannot see the
   run and the cap would not apply.
2. The per-worker rps is derived automatically: the asset factory sets each enrichment
   subprocess's rps env var (the source's `rps_env_var`, e.g. `MET_API_RPS`) to
   `rate_limit.rps_budget / rate_limit.concurrency` (`policies.per_worker_rps()`), so the
   summed request rate stays under the ceiling. Tune the *budget* and *concurrency* in
   `framework.yaml`, not the rps env var directly.

**Recommendation:** start with 2 concurrent departments, measure done-rate and the
per-batch throttle counters (already logged), and only raise concurrency if you are
demonstrably latency-bound rather than rate-capped.

## Retries, timeouts, failure handling

- Every network-bound asset carries `EXTRACTION_RETRY_POLICY` (2 retries, exponential
  backoff + jitter).
- Per-asset wall-clock ceilings via the `dagster/max_runtime` op tag. These are only
  enforced when `run_monitoring.enabled: true` in `dagster.yaml` (it is) and the
  daemon is running.
- Enrichment resumability: a crashed batch leaves rows leased; `MET_LEASE_RECLAIM_TASK`
  frees them after the 30-min TTL, and the next materialization re-claims them. The
  `met_no_orphaned_leases` asset check warns if leases exceed the TTL.

## Observability

- Rich `MaterializeResult` metadata (row counts, worklist remaining, control status,
  per-department slice) pulled from Snowflake on each run.
- Asset checks (generated by `factories/checks.py` from each source's YAML):
  `raw_met_objects_has_rows` (ERROR), `met_no_orphaned_leases` (WARN),
  `raw_aic_artworks_has_rows` (ERROR).
- Freshness checks on the Gold marts (expect daily build) and Bronze terminals
  (weekly). They surface in the UI; auto-evaluation needs a freshness sensor (Stage 2).

## Path to production

Current state is local `dagster dev` (webserver + daemon in one process, SQLite
instance storage). To productionize:

1. **Dedicated host.** Run the webserver and daemon as separate long-lived services
   (systemd units or containers). Keep `$DAGSTER_HOME` on persistent disk.
2. **Persistence.** Replace default SQLite with **Postgres** for run/event/schedule
   storage (add a `storage:` block pointing at Postgres). SQLite will not survive
   real concurrency or restarts gracefully.
3. **Turn on the schedules.** Flip `daily_dbt_schedule` and
   `weekly_full_pipeline_schedule` to `RUNNING` (or set `default_status=RUNNING`) and
   ensure the daemon runs. Consider a schedule that walks the Met department
   partitions to drain enrichment steadily.
4. **Alerting.** Add a run-failure sensor (or Dagster+ alert policies) → Slack/email/
   webhook. Enable a freshness sensor so stale Gold marts page someone.
5. **Secrets.** Keep the key-pair creds in the host's secret store / env, not in the
   repo. The extraction `Config` already reads them from env.
6. **Executor.** For heavier parallelism, move from the multiprocess executor to a
   containerized run launcher (e.g. Docker/K8s) so each run is isolated.
7. **In-process extraction (later milestone).** The assets currently shell out to the
   CLIs. Refactoring to typed, in-process ops would unlock native partition
   parallelism, structured logging, and a shared/global rate limiter across workers
   (which would let concurrency exceed 2 safely).
