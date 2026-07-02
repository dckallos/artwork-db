# Configuration schema reference

The orchestration layer is **generated from YAML**. There are two YAML layers, both
parsed and validated by `loader.py` into typed dataclasses (`model.py`, `spec.py`). You
almost never touch Layer A; adding a museum means writing one Layer-B file. Every field
below is documented in **technical** terms (what the engine does) and **plain** terms
(what it means for you).

`${ENV_VAR:default}` anywhere in either file is replaced with the environment variable's
value, or `default` if unset. This keeps environment-specific values (and env-var
*names*) in YAML, never in Python.

---

## Layer A — `framework.yaml` (internal engine config)

Source-agnostic. Replaces the old Python constants. Rarely edited when adding a source.

### `connection` (required)
How the orchestration layer opens its own small metadata/check queries. It **reuses the
dbt profile** — one connection identity for the whole project, no second credential store.

| key | req | type | technical | plain |
|---|---|---|---|---|
| `profile` | yes | str | dbt profile name (matches `profiles.yml` top key) | "Log in the same way dbt does." |
| `target` | yes | str | dbt target within the profile | "Which environment — `dev` (your laptop) or `snowflake` (inside Snowflake)." |
| `profiles_dir` | yes | str | dir holding `profiles.yml`, relative to repo root | "Where that login file lives." |

### `bronze` (required)
| key | req | type | technical | plain |
|---|---|---|---|---|
| `database` | yes | str | Snowflake database for raw landing tables | "Which database the raw data lands in." |
| `schema` | yes | str | Snowflake schema for raw landing tables | "Which folder inside that database." |

### `defaults` (required)
Generic step capabilities. There is deliberately **no "enrichment" concept** here —
batching and rate-limiting are generic and opt-in per step.

- `retry`: `max_retries` (int), `delay_seconds` (int), `backoff` (`exponential`|`linear`),
  `jitter` (`plus_minus`|`none`). *Technical:* the Dagster `RetryPolicy` applied to
  API-bound steps. *Plain:* "If a step hits a network blip, how many times and how
  patiently to retry."
- `timeouts_seconds`: a map with a required `default` plus any named step **kinds**
  (e.g. `snapshot`, `seed`, `batch`). *Technical:* per-run wall-clock ceiling the daemon
  enforces, chosen by a step's `kind`. *Plain:* "How long a step may run before it's
  killed."
- `batching`: `size` (int), `max_batches` (int). *Technical:* values passed as
  `--batch-size`/`--max-batches` to steps with `mode: batched`. *Plain:* "How much a
  single batched run bites off."
- `rate_limit`: `rps_budget` (number), `concurrency` (int). *Technical:* per-worker rps =
  `rps_budget / concurrency`, injected into a rate-limited step's `rps_env_var`. *Plain:*
  "The total request speed allowed for a throttled API, split across parallel workers."

### `tags` (required)
| key | req | technical | plain |
|---|---|---|---|
| `rate_limit_key` | yes | run-tag key the QueuedRunCoordinator caps on | "The label Dagster uses to limit how many throttled runs go at once." |
| `max_runtime_key` | yes | op/run-tag key `run_monitoring` enforces | "The label that carries each step's time limit." |

### `freshness` (required)
| key | req | technical | plain |
|---|---|---|---|
| `gold_marts` | yes | list of dbt Gold model names to freshness-check | "The finished tables we want a 'is this stale?' alarm on." |
| `gold_lag_hours` | no (default 30) | allowed staleness in hours | "How old is too old." |

---

## Layer B — `sources/<key>.yaml` (user-facing source declaration)

This is the **only** framework file you write for a new museum. Minimal by design; the
rich keys are all optional (see the simple CMA example in `ADDING_A_SOURCE.md`).

### Top level
| key | req | type | technical | plain |
|---|---|---|---|---|
| `source` | yes | str | source key; dbt source name; asset-key namespace; group `extraction_<source>` | "Your museum's short code, e.g. `cma`." |
| `cli_module` | yes | str | `python -m <cli_module> <step.run>` | "The Python module that runs your extraction." |
| `rps_env_var` | no (`API_RPS`) | str | env var the CLI reads for per-worker rps | "The env var your throttled fetch reads its speed from." |
| `rate_limit_value` | no (=`source`) | str | value for the rate-limit tag | "Usually leave blank — defaults to your source key." |
| `steps` | yes | list | ordered pipeline phases (see below) | "The steps to run, in order." |
| `checks` | no | list | source-level operational checks (see below) | "Optional plumbing checks — usually you rely on dbt instead." |

### `steps[]`
| key | req | type | technical | plain |
|---|---|---|---|---|
| `name` | yes | str | asset/op name | "A short name for this step." |
| `run` | no | str | CLI subcommand; **omit for a verify-only step** (no subprocess) | "The subcommand to run; leave out if the step only reads/verifies." |
| `kind` | no (`snapshot`) | str | picks the timeout default | "Rough type of step — sets a sensible time limit." |
| `timeout_seconds` | no | int | overrides the kind-derived timeout | "Override the time limit if needed." |
| `mode` | no (`simple`) | `simple`\|`batched` | `batched` appends `--batch-size/--max-batches` | "Set `batched` if the step drains data in chunks." |
| `rate_limited` | no (`false`) | bool | job gets the rate-limit run tag; per-worker rps injected | "Set true if the step calls a throttled API." |
| `api_bound` | no (`true`) | bool | `false` = no retry policy | "Set false for a step that only reads (nothing to retry)." |
| `static_args` | no | list[str] | extra CLI args appended verbatim | "Any fixed extra flags for the CLI." |
| `partition_by` | no | object | static-partition this step (`name`, `cli_flag`, `values{slug: real}`) | "Split the step into slices (e.g. one per department)." |
| `produces` | yes | list | Bronze tables this step writes (see below) | "Which raw tables this step fills." |
| `metadata_sql` | no | map | label → scalar SQL for UI counters; `{db}`/`{schema}`/`{partition_value}` tokens | "Optional numbers to show on the asset tile." |

### `steps[].produces[]`
Either a **bare table name** (shorthand for a dbt-source terminal), or a mapping:

| key | req | type | technical | plain |
|---|---|---|---|---|
| `table` | yes | str | logical table name | "The table name." |
| `dbt_source` | no (`true`) | bool | keyed via the translator for dbt lineage | "Leave true if dbt reads this table." |
| `internal` | no (`false`) | bool | intermediate table, not a dbt source | "Set true for a scratch/intermediate table." |
| `physical` | no (`UPPER(table)`) | str | actual Bronze table name | "Only if the physical name differs from the logical one." |
| `check_nonempty` | no (`false`) | bool | **optional** post-load `COUNT(*) > 0` asset check | "Optional 'did any rows land?' check — prefer dbt." |
| `severity` | no (`ERROR`) | `ERROR`\|`WARN` | severity of the non-empty check | "How loud that check is." |
| `fresh_within_days` | no | number | **optional** last-update freshness check | "Optional staleness alarm — prefer dbt `freshness:`." |

> **Data quality lives in dbt.** `check_nonempty` / `fresh_within_days` / `checks` are all
> optional and default off. New sources should rely on dbt (`dbt_expectations`, source
> `freshness:`) for data-quality tests. Use these orchestration checks only for a pre-dbt
> Bronze gate or genuinely operational plumbing (see `checks` below).

### `checks[]` (source-level, optional)
For operational checks on extraction bookkeeping that dbt does not model.

| key | req | type | technical | plain |
|---|---|---|---|---|
| `name` | yes | str | check name | "A short name." |
| `attach_table` | yes | str | logical table whose asset the check hangs off (must be produced) | "Which table this check is about." |
| `sql` | yes | str | scalar query; `{db}`/`{schema}` tokens allowed | "A query returning one number." |
| `expect` | yes | str | verdict comparator + integer, e.g. `"== 0"`, `"> 0"` | "The number is OK when it satisfies this." |
| `severity` | no (`WARN`) | `ERROR`\|`WARN` | check severity | "How loud a failure is." |
| `description` | no | str | human description | "What it means." |
