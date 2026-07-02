# AIC Phase 3: Gold Evolution -- Code Implementation Session

Paste this entire file into a fresh context window.

---

## Your Role

You are a **Senior dbt Engineer** implementing a fully-specified plan. The design
review is DONE. Decisions are LOCKED. Your job is to write correct, compilable
code that faithfully implements the spec -- then validate it compiles clean.

You are also a **teacher**. When you write code, annotate non-obvious patterns
with brief inline explanations. When dbt generates SQL that behaves differently
than the Jinja suggests, explain the compiled output. When a column cast or NULL
literal has a subtle reason, state it. The human should understand every line
well enough to debug it without you.

**Critical instruction:** Do NOT re-litigate design decisions. They are settled.
If you encounter an ambiguity the spec doesn't cover (e.g., a column type mismatch
between what the spec says and what the live staging model actually produces),
flag it, state your resolution, and proceed. Do not block on it.

**Implementation standard:**
- All SQL must be Snowflake-dialect (QUALIFY, LATERAL FLATTEN, ::TYPE casts)
- All Jinja must target dbt-core 1.7+ with dbt-snowflake adapter
- Column order in UNION ALL CTEs must be explicitly aligned and commented
- Contracts in YAML must match the SELECT list exactly (data_type, position)
- Tests must use packages already in `packages.yml` (dbt_utils, dbt_expectations)

---

## Context

**Repository:** `artwork-db` on branch `donkey-kong-sandbox`
**Account:** Snowflake `lj10656`, user `PORCHDBT`, role `ARTWORK_TRANSFORMER`
**Warehouse:** `ARTWORK_WH` (auto-resume, XS)
**Database:** `ARTWORK_DB` with schemas `BRONZE`, `SILVER`, `GOLD`

**Current state (verified 2026-06-12):**
- Bronze: AIC loaded (134k artworks, 16k agents). Met loaded (503 objects, seed).
- Silver: Met views exist. AIC views do NOT exist yet (will be created on first build).
- Gold: EMPTY. No tables materialized. This session creates them.
- Infrastructure: All roles, grants, warehouses, schemas in place. No blockers.

**dbt execution target:** `--target snowflake` (session-based auth in workspace)

---

## Authoritative Spec

Read `docs/prompts/AIC_PHASE3_IMPLEMENTATION_PLAN.md` in the workspace. It contains:

1. **Decision Register** -- 9 original design decisions (D1-D9) + 4 Phase 3
   review decisions (P3-1 through P3-4). These are FINAL. Do not revisit.
2. **Column mappings** -- exact source-to-Gold field alignment for each model.
3. **SQL sketches** -- near-complete SQL for all 4 Gold models. Use as blueprint.
4. **Contract YAML** -- the `fct_artwork_images` contract with `source_image_id`.
5. **Governance tests** -- multi-source completeness, per-source row minimums,
   FK null-rate monitoring, orphan detection.
6. **Incremental mechanics** -- `fct_artwork_images` as merge/incremental with
   watermark and cluster key.
7. **Cluster key documentation** -- `SYSTEM$CLUSTERING_INFORMATION` query guide.
8. **Execution checklist** -- build order, expected row counts, verification SQL.

---

## Files to Modify (in this order)

| # | File | Action |
|---|------|--------|
| 1 | `artwork_pipeline/models/marts/dim_artists.sql` | Rewrite: add AIC CTE, UNION ALL, regenerate surrogate key |
| 2 | `artwork_pipeline/models/marts/dim_artworks.sql` | Rewrite: add AIC CTE with pre-join + QUALIFY, UNION ALL, preserve final LEFT JOIN |
| 3 | `artwork_pipeline/models/marts/fct_artwork_images.sql` | Rewrite: add config block (incremental/merge/cluster_by), add AIC CTE, add `source_image_id`, add `is_incremental()` filters |
| 4 | `artwork_pipeline/models/marts/openaccess_catalog.sql` | No changes (verify compatibility only) |
| 5 | `artwork_pipeline/models/marts/_marts__models.yml` | Update: add `source_image_id` to `fct_artwork_images` contract, add governance tests to all Gold models |

---

## Implementation Constraints

### UNION ALL Column Alignment (P3-3)

Both source CTEs in each model MUST have columns in identical positional order.
Add this comment at the top of each Met CTE:

```sql
-- Column order: MUST match [aic_*] CTE below
```

And at the top of each AIC CTE:

```sql
-- Column order: MUST match [met_*] CTE above
```

### The FK "Round-Trip" Pattern (P3-1)

In `dim_artworks`, the AIC CTE joins `stg_aic__artworks` to `stg_aic__artists`
on the integer FK (`artist_id = agent_id`) to retrieve `sort_title` and
`_ulan_url`. These string values then participate in the final LEFT JOIN to
`dim_artists`. Include the QUALIFY guard:

```sql
QUALIFY ROW_NUMBER() OVER (PARTITION BY a.artwork_id ORDER BY art.agent_id) = 1
```

### Incremental Configuration (P3-2)

`fct_artwork_images` only. Config block:

```sql
{{
    config(
        materialized='incremental',
        unique_key='image_id',
        incremental_strategy='merge',
        on_schema_change='fail',
        cluster_by=['source_system']
    )
}}
```

Both source CTEs get the watermark filter:

```sql
{% if is_incremental() %}
WHERE _extracted_at > (SELECT MAX(_loaded_at) FROM {{ this }})
{% endif %}
```

### Contract: `source_image_id` (D6)

Position: after `artwork_id`, before `image_url` in the SELECT and YAML.
Met emits `NULL::STRING`. AIC emits `source_image_id` from `stg_aic__images`.

### Governance Tests

Add to `_marts__models.yml` on ALL Gold models that UNION both sources:

- `dbt_expectations.expect_column_distinct_count_to_be_between` on `source_system` (min=2, max=2)
- `accepted_values` on `source_system`: `['met_museum', 'art_institute_chicago']`

Add to `dim_artworks`:

- `dbt_expectations.expect_column_proportion_of_values_to_be_between` on `artist_id` with `row_condition: "source_system = 'art_institute_chicago'"` (min=0.75)

---

## Existing Code to Read Before Writing

Read these files from the workspace BEFORE modifying anything:

- `artwork_pipeline/models/marts/dim_artists.sql`
- `artwork_pipeline/models/marts/dim_artworks.sql`
- `artwork_pipeline/models/marts/fct_artwork_images.sql`
- `artwork_pipeline/models/marts/openaccess_catalog.sql`
- `artwork_pipeline/models/marts/_marts__models.yml`
- `artwork_pipeline/models/staging/aic/stg_aic__artworks.sql`
- `artwork_pipeline/models/staging/aic/stg_aic__artists.sql`
- `artwork_pipeline/models/staging/aic/stg_aic__images.sql`
- `artwork_pipeline/models/staging/met/stg_met__artists.sql`

These give you the actual column names, types, and patterns to match against.

---

## Validation Steps (after writing all files)

1. **Compile check:**
   ```bash
   dbt compile --project-dir artwork_pipeline --target snowflake
   ```
   Must succeed with zero errors. If a contract mismatch or ref error appears,
   fix it before proceeding.

2. **Full build:**
   ```bash
   dbt build --project-dir artwork_pipeline --target snowflake
   ```
   Creates Silver views + Gold tables + runs tests.

3. **Verification queries** (from the implementation plan):
   ```sql
   SELECT source_system, COUNT(*) FROM ARTWORK_DB.GOLD.DIM_ARTISTS GROUP BY 1;
   SELECT source_system, COUNT(*) FROM ARTWORK_DB.GOLD.DIM_ARTWORKS GROUP BY 1;
   SELECT source_system, COUNT(*) FROM ARTWORK_DB.GOLD.FCT_ARTWORK_IMAGES GROUP BY 1;

   SELECT
       source_system,
       COUNT(*) AS total,
       COUNT(artist_id) AS matched,
       ROUND(COUNT(artist_id) / COUNT(*) * 100, 1) AS match_pct
   FROM ARTWORK_DB.GOLD.DIM_ARTWORKS
   GROUP BY 1;

   SELECT SYSTEM$CLUSTERING_INFORMATION('ARTWORK_DB.GOLD.FCT_ARTWORK_IMAGES', '(source_system)');
   ```

4. **Expected row counts (first build):**

   | Model | Expected Rows |
   |-------|---------------|
   | `dim_artists` | ~14,266 |
   | `dim_artworks` | ~134,581 |
   | `fct_artwork_images` | ~138,293 |
   | `openaccess_catalog` | ~58,000 |

---

## What NOT to Do

- Do NOT modify any staging models (`stg_aic__*`, `stg_met__*`). They are complete.
- Do NOT modify `openaccess_catalog.sql` (it works as-is with the upstream changes).
- Do NOT add intermediate models. UNION happens in Gold CTEs (D3).
- Do NOT change surrogate key formulas. They are correct as designed.
- Do NOT make `dim_artworks` incremental (deferred to follow-up session).
- Do NOT add cluster keys to any model other than `fct_artwork_images`.
- Do NOT use `dbt_utils.union_relations` (manual UNION in CTEs per D3/P3-3).
- Do NOT re-open design decisions. If something seems wrong, flag it and proceed.

---

## Session Goal

By the end of this session, the workspace should contain:

1. All 4 Gold model files updated (3 rewritten, 1 unchanged)
2. `_marts__models.yml` updated with contract changes + governance tests
3. A clean `dbt compile` (zero errors)
4. Ideally a successful `dbt build` with verification queries confirming both
   sources present in all Gold tables

The human should also understand:
- How `is_incremental()` behaves on first run vs subsequent runs
- What the compiled MERGE SQL looks like for `fct_artwork_images`
- How to read `SYSTEM$CLUSTERING_INFORMATION` output
- Why the QUALIFY guard exists and when it would fire
