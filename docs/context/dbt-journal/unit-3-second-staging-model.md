# Unit 3: Build a Second Staging Model

> Started: 2026-06-05  |  Completed: in progress

## Objectives

Create `stg_met__enrichment_status.sql` sourcing from `MET_ENRICHMENT_CONTROL`,
declared as a new source table in `_met__sources.yml`. Materialize as a **view**
(decided 2026-06-05).

What you will learn:
- Multi-source staging: one `sources:` block can declare multiple tables.
- The `identifier:` property mapping dbt's lowercase convention to Snowflake's
  UPPERCASE physical table name.
- `view` vs `ephemeral` materialization tradeoffs (we chose `view`:
  queryable + lineage-visible vs. ephemeral's zero footprint but invisibility).
- How `{{ source() }}` compiles differently than `{{ ref() }}`.

## Source under test (verified 2026-06-05)

`ARTWORK_DB.BRONZE.MET_ENRICHMENT_CONTROL` -- 2327 rows, 10 columns, PK OBJECT_ID:
OBJECT_ID, ENRICHMENT_STATUS (pending|done|no_image|error), LAST_ENRICHED_AT,
METADATA_DATE, HAS_PRIMARY_IMAGE, IMAGE_STATUS (unknown|live|dead),
LAST_HEAD_CHECK_AT, CLAIMED_BY_BATCH, CLAIMED_AT, ENRICHMENT_ERROR.

## Materialization decision (the view-vs-ephemeral fork)

- **Choice:** `view` (consistent with `stg_met__artworks`).
- **Why view:** it materializes as a real object in `ARTWORK_DB.SILVER` --
  directly queryable, visible in `SHOW VIEWS`, appears in lineage, easy to debug
  with a row count. Costs one schema slot but stores no data (it's a view).
- **What ephemeral would have meant:** NO database object at all. An ephemeral
  model is inlined as a CTE into whatever downstream model `{{ ref() }}`s it --
  zero Snowflake footprint, but invisible: you cannot `SELECT` it directly, it has
  no `target/run/` artifact, and it is harder to debug. Ephemeral earns its place
  later when a staging model is purely an intermediate with no standalone value.

## Commands Run (in order)

1. `<pending: dbt run --select stg_met__enrichment_status>`
   - Output summary: ...
   - Observation: expect a VIEW created in ARTWORK_DB.SILVER.
2. `<pending: dbt test --select source:met.met_enrichment_control>` (after adding tests)
   - Output summary: ...

## Decisions Made
- **Fork:** view vs ephemeral materialization.
- **Choice:** view (see "Materialization decision" above).
- **Rationale:** debuggability + queryability + lineage visibility beat footprint
  savings at this learning stage; the control table is tiny.

## Errors Encountered
### Deliberate: omit identifier
- Command: remove the `identifier: MET_ENRICHMENT_CONTROL` line from
  `_met__sources.yml`, then `dbt run`.
- Error output: ... (expect dbt to look for lowercase `met_enrichment_control`,
  which does not exist).
- Diagnosis: ...
- Fix: restore `identifier: MET_ENRICHMENT_CONTROL`, re-run.

### Unexpected: <name> (if any)
- ...

## Key Takeaways (written by AI after unit completes)
1. ...

## Verification
```sql
SHOW VIEWS IN SCHEMA ARTWORK_DB.SILVER;
-- Expect: STG_MET__ENRICHMENT_STATUS (alongside STG_MET__ARTWORKS)
SELECT ENRICHMENT_STATUS, COUNT(*)
FROM ARTWORK_DB.SILVER.STG_MET__ENRICHMENT_STATUS
GROUP BY 1 ORDER BY 2 DESC;
-- Expect rows summing to 2327.
```
