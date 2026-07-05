# Ingestion Anti-Patterns

This document lists architecture patterns that should be rejected during review.

## Framework source branches

Do not add source-specific conditionals, museum names, source table names, or hand-maintained source lists to `orchestration/artwork_orchestration/**/*.py`.

The grep gate from `AGENTS.md` must remain clean.

## Universal artwork schema in extraction

Do not normalize all providers into a single artwork schema in Python extraction code.

Extraction should preserve raw payloads and operational provenance. dbt should own semantic parsing, conformance, and classification.

## One-off standalone clients

Do not create a new provider package that reimplements common mechanics already available or planned in `extraction/artwork_ingestion`.

Common mechanics include:

- HTTP transport.
- Retry/backoff.
- Auth injection.
- Download/cache.
- Archive reading.
- NDJSON chunking.
- Snowflake stage/COPY/MERGE.
- Manifest logging.
- Secret redaction.
- SQL identifier validation.

## Source packages importing other source packages for common behavior

AIC should not import Met helpers, and future providers should not import AIC or Met helpers. Shared behavior belongs in the common ingestion package.

## Opaque DDL generation

Do not build a generator that mutates Snowflake directly without checked-in SQL review.

Validation should come first. If generation is added, generated SQL should be committed and reviewed.

## Generic raw table too early

Do not prematurely replace source/entity raw tables with a single generic raw object table. The recommended path is hybrid: raw source/entity tables plus shared operational manifest/watermark/log tables.

## Mart hand edits for every source

Do not add a new source by editing every mart with a new source-specific CTE.

New sources should flow through source-specific staging, per-source conformed intermediates, shared unioned intermediates, and then marts.

## Rights/media flattening without evidence

Do not convert complex rights/media fields into one boolean without preserving evidence.

Keep metadata rights, object rights, media rights, media availability, and media liveness distinct until dbt classification.

## Import-time side effects

Do not perform any of the following at import time:

- Network calls.
- Snowflake connections or mutations.
- dbt shell-outs.
- Credential reads.
- `.env` loading.
- Provider API calls.

Runtime side effects belong in explicit CLI functions, Dagster asset bodies, setup scripts, or clearly named operator commands.

## Production credentials for local development

Do not require production credentials for local tests, local docs validation, local Dagster definition loading, or bounded extraction smoke tests.

Credentialed tests must be opt-in and environment-scoped.

## Aggregators as direct museums

Do not treat aggregators as direct museum sources without preserving original provider attribution and reconciliation risk.

Aggregator data needs explicit external identifier and duplicate/reconciliation modeling.

## API crawling when dumps exist

Do not prefer full API crawling when a provider offers a suitable dump. Use APIs for enrichment, deltas, live lookups, or fields missing from the dump.

## Placeholder production sources

Do not leave no-op placeholder sources in production-like registry paths. Use test fixtures for fake sources, or mark research-only sources explicitly if the schema supports it.
