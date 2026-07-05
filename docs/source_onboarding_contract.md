# Source Onboarding Contract

This document defines what a new source must provide as it moves from research to Bronze extraction, dbt staging, conformed participation, and shared marts.

The contract is intentionally staged. A source may stop at an earlier readiness level without pretending it is ready for shared marts.

## Readiness levels

### Level 0: Research only

A source is documented but not runnable.

Expected artifacts:

- Notes in `docs/open_access_artwork_api_catalog.md` or a source-specific research doc.
- Access method, licensing/access caveats, expected entity types, and preferred extraction archetype.

Not expected:

- Production-like Dagster source YAML.
- Placeholder Bronze DDL.
- No-op source CLI.

### Level 1: Fixture/local sample extraction

A source package can transform a tiny fixture or local sample into raw envelopes/NDJSON without live services.

Expected artifacts:

- `extraction/<source>/README.md`.
- `extraction/<source>/__init__.py`.
- `extraction/<source>/config.py`.
- `extraction/<source>/run.py`.
- Source-specific mapping/evidence helpers as needed.
- Sanitized fixtures and tests.

### Level 2: Bronze load

A source can load bounded data into Snowflake Bronze in a dev/staging target.

Expected artifacts:

- Source-owned SQL templates under `extraction/<source>/sql/`.
- Raw Bronze DDL.
- Drop/rollback DDL where appropriate.
- Local smoke command with bounded flags.
- DDL/source/dbt validation passing where available.

### Level 3: dbt source and staging

A source has dbt source YAML and source-specific staging models.

Expected artifacts:

- `artwork_pipeline/models/staging/<source>/_<source>__sources.yml`.
- `artwork_pipeline/models/staging/<source>/stg_<source>__*.sql`.
- Schema docs and tests.
- Source database/schema parameterization consistent with the dbt project.

### Level 4: Conformed intermediates

A source emits shared conformed contracts but does not necessarily enter marts.

Expected artifacts:

- `artwork_pipeline/models/intermediate/<source>/int_<source>__*_conformed.sql`.
- Model docs and conformed contract tests.
- Rights/media/external-identifier evidence models if applicable.

### Level 5: Shared marts

A source is admitted to shared unioned intermediates and marts.

Expected artifacts:

- Source key included in `enabled_sources` or the accepted source-enablement mechanism.
- `int_<entity>__unioned` includes the source without mart hand edits.
- Mart tests pass.
- Rights/media classification is documented and tested where relevant.
- Aggregator sources preserve original provider attribution and reconciliation caveats.

## Required source package shape

Recommended package:

- `extraction/<source>/README.md`
- `extraction/<source>/__init__.py`
- `extraction/<source>/config.py`
- `extraction/<source>/run.py`
- `extraction/<source>/mapping.py` when useful
- `extraction/<source>/rights.py` when rights evidence is available
- `extraction/<source>/media.py` when media evidence is available
- `extraction/<source>/sql/*.sql`
- `extraction/<source>/tests/*`

The source package should compose `extraction/artwork_ingestion` helpers instead of duplicating common mechanics.

## Required local commands

Each source README should include bounded local commands, adapted to the source's actual CLI:

- Validate configuration.
- Run fixture/sample extraction.
- Run bounded snapshot with `--limit` or equivalent.
- Run with `--no-refresh` when cache is supported.
- Run one small enrichment batch if the source has enrichment.
- Show status if a status command exists.

## Dagster source YAML expectations

A real active source should have one YAML file:

- `orchestration/artwork_orchestration/sources/<source>.yaml`

The YAML should describe orchestration only:

- Steps.
- Dependencies.
- Produced assets.
- `dbt_source` terminal outputs.
- Partitions.
- Batch sizing.
- Rate-limit metadata.
- Operational checks.
- Capabilities/operator hints if supported.

It should not encode provider endpoints, field mappings, or rights rules.

## DDL expectations

New raw tables should preserve raw source payloads and include operational metadata. Exact required columns should be validated by the DDL/source contract validator once implemented.

DDL must be idempotent and reviewable. Generated DDL, if introduced, must be checked in.

## dbt expectations

Source-specific staging is required before conformed participation.

Marts must not be hand-edited for every source. New sources should join shared marts through conformed and unioned intermediate models.

## Rights and media expectations

Preserve evidence before classification.

Do not collapse the following into one extraction-time boolean:

- Metadata rights.
- Object/artwork rights.
- Media rights.
- Media availability.
- Media liveness.
- Provider license URI/text.
- Source payload field path.

## Placeholder policy

Production-like no-op source stubs should be avoided.

A fake source may live in test fixtures to prove framework source-decoupling. A real registry source should be runnable, explicitly disabled/research-only, or removed.

### CMA precedent (issue #23, Option A)

The Cleveland Museum of Art (CMA) placeholder was removed from all production-like paths — the `extraction/cma/` stub CLI, the `sources/cma.yaml` registry entry, the `RAW_CMA_*` Bronze DDL, and the `models/staging/cma/` stub — rather than kept as an ambiguous no-op source. Source-decoupling acceptance coverage now lives in a fixture-only source (`orchestration/tests/fixtures/sources/example_museum.yaml`) exercised by `orchestration/tests/unit/test_source_registry_acceptance.py`, which proves a new source is discovered from one YAML file with zero framework `.py` edits. Cleveland returns under #20 as a real, source-owned implementation built on the common primitives — not as a stub.
