# Ingestion Platform Architecture

This document is the canonical implementation guide for evolving `artwork-db` from a small set of source-specific extractors into a reusable, typed, source-decoupled ingestion platform.

It intentionally distinguishes current repository rules from recommended implementation direction. Current rules in `AGENTS.md` and `CODE_STANDARDS.md` take precedence if this document ever drifts.

## Prime directive

The orchestration layer is YAML-driven and source-decoupled. Adding a data source should require:

1. One source YAML file under `orchestration/artwork_orchestration/sources/<key>.yaml`.
2. Source-owned extractor artifacts under `extraction/<key>/` as needed.
3. Source-owned dbt artifacts under `artwork_pipeline/models/staging/<key>/` and, when ready, `artwork_pipeline/models/intermediate/<key>/`.
4. Source-owned DDL/SQL artifacts as needed.
5. Zero edits to framework Python for source-specific behavior.

Framework Python under `orchestration/artwork_orchestration/**/*.py` must continue to pass the grep gate documented in `AGENTS.md`.

## Target shape

`artwork-db` should evolve into source-owned adapters composed from shared ingestion primitives.

The preferred common package name is:

- `extraction/artwork_ingestion`

The common package should own reusable mechanics:

- HTTP transport.
- Auth injection.
- Retry, backoff, `Retry-After`, and rate-limit gates.
- Pagination and feed walkers.
- Bulk download and local cache.
- Archive readers.
- CSV, JSON, JSONL, and XML stream readers where needed.
- NDJSON chunk writing.
- Snowflake stage/COPY/MERGE helpers.
- Extraction run, file, stage, watermark, and load manifests.
- Worklist/leasing primitives after at least two real sources prove the shared shape.
- Secret redaction.
- SQL identifier and template validation.
- IIIF/media helper utilities.
- Fixture/test harness utilities.
- DDL/dbt/source validation helpers.

Source packages should own provider-specific behavior:

- Provider URL defaults and docs.
- Auth environment variable names.
- Endpoint paths and query params.
- Dump/archive layout assumptions.
- Record selection and entity mapping.
- Natural keys and source identifiers.
- Source-owned merge SQL templates.
- Rights/media evidence extraction.
- Source README and local smoke commands.
- Source-specific tests and sanitized fixtures.

## Boundary between layers

### Extraction

Extraction preserves raw payloads and operational provenance. It may extract evidence, but it should not become the semantic classification layer.

Extraction should not define a universal artwork schema. A source record remains a source record until dbt staging and conformed models interpret it.

### Dagster

Dagster source YAML describes orchestration facts:

- Steps.
- Dependencies.
- Produced raw/dbt source assets.
- Static or dynamic partitions.
- Batch sizing.
- Rate-limit tags.
- Operational checks.
- Capabilities and operator hints.

Dagster framework Python must not know provider endpoints, source field mappings, rights rules, unit lists, or source-specific table names.

### dbt

dbt owns semantic parsing, conformance, classification, tests, and marts.

Recommended flow:

1. `BRONZE.RAW_<SOURCE>_<ENTITY>` raw payload tables.
2. `stg_<source>__<entity>` source-specific staging.
3. `int_<source>__<entity>_conformed` per-source conformed intermediates.
4. `int_<entity>__unioned` shared unioned intermediates controlled by `enabled_sources`.
5. Source-neutral marts.

### Snowflake DDL

Recommended model: hybrid.

Keep one raw table per source/entity for dbt clarity, operator usability, and source-specific lifecycle semantics. Add shared operational tables for manifests, watermarks, run logs, stage files, and eventually worklists.

Do not migrate to one generic raw object table unless a later decision reverses this recommendation.

## Local-first execution

Most extraction/orchestration work should remain runnable from a maintainer laptop.

Expected local-first features:

- `.env` or profile-driven runtime config read only at CLI/script edges.
- Snowflake/dbt profile reuse where possible.
- `--limit`, `--max-batches`, `--no-refresh`, `--cache-dir`, and `--temp-dir` flags for source CLIs.
- Offline tests by default.
- Credentialed tests explicitly marked and environment-scoped.
- Dagster schedules stopped by default for local examples.
- Doctor scripts that verify local readiness without printing secrets.

## Roadmap issues

The implementation backlog is tracked in GitHub:

- #10 — Consolidate ingestion architecture docs and anti-patterns.
- #11 — Build offline extraction and orchestration test harness foundation.
- #12 — Create typed `extraction/artwork_ingestion` P0 primitives.
- #13 — Introduce shared Snowflake loader and ingestion manifests.
- #14 — Extract reusable bulk download, cache, archive, and streaming primitives.
- #15 — Extract reusable HTTP, auth, retry, and rate-limit primitives.
- #16 — Add DDL, dbt source, and Dagster `produces` validation gates.
- #17 — Improve Dagster source YAML schema, operator UX, and rate-limit configuration.
- #18 — Harden dbt conformed layer and remove mart source hand-edits.
- #19 — Expand CI and local doctor checks for local-first operations.
- #20 — Add first new bulk-provider proof of concept using common primitives.
- #21 — Implement Smithsonian S3-first source as a design stress test.
- #22 — Roadmap index.
- #23 — Resolved (Option A): the CMA placeholder/stub was removed from production-like paths; Cleveland returns under #20 as a real source. See the placeholder policy in `docs/source_onboarding_contract.md`.

## AI implementation notes

Before implementing any roadmap issue, read:

1. `AGENTS.md`.
2. `CODE_STANDARDS.md`.
3. This document.
4. `docs/source_onboarding_contract.md`.
5. `docs/ingestion_anti_patterns.md`.
6. The GitHub issue being implemented and all prerequisite issues it references.
7. The files listed in the issue's review scope.

Do not present final file changes in diff format.
