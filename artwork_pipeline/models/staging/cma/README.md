# CMA Integration: `source_object_id` Type Conflict

## Problem

`dim_artworks.source_object_id` is currently typed as `number(38,0)` in the
contract (`_marts__models.yml`). This works for Met (integer `object_id`) and
AIC (integer `artwork_id`).

Cleveland Museum of Art (CMA) uses **string-based accession numbers** as its
primary object identifier (e.g., `"1916.1065"`). When CMA is added as source #3,
the UNION ALL in `dim_artworks` will fail with a type mismatch: the CMA CTE
produces VARCHAR while Met/AIC produce NUMBER.

## Affected Files

- `artwork_pipeline/models/marts/dim_artworks.sql` -- CTE `source_object_id` column
- `artwork_pipeline/models/marts/fct_artwork_images.sql` -- INNER JOIN on `source_object_id`
- `artwork_pipeline/models/marts/openaccess_catalog.sql` -- passes through `source_object_id`
- `artwork_pipeline/models/marts/_marts__models.yml` -- contract type declaration

## Resolution Options

1. **Migrate `source_object_id` to VARCHAR now (pre-emptive):** Change the contract
   to `varchar(16777216)`, add `::STRING` casts to Met and AIC CTEs. Safe -- no
   data loss (integers cast cleanly to strings). Requires `--full-refresh` on Gold.

2. **Migrate when CMA is added (deferred):** Keep NUMBER for now. Change to VARCHAR
   in the same PR that adds CMA staging + Gold CTEs. Reduces churn today but makes
   the CMA PR larger.

## Decision

Deferred to CMA onboarding. Documented here so the conflict is visible before it
becomes a compile error.

## Date

2026-06-12 (Phase 3 design review session)
