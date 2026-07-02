# Unit 2: dbt test -- Trust Your Source

> Started: 2026-06-05  |  Completed: 2026-06-05

## Objectives

Run `dbt test` against the already-declared source and model tests. Then add a
test that WILL fail to learn severity configuration and `store_failures`.

What you will learn:
- Source tests vs. model tests (when each fires, what SQL each generates).
- The compiled test SQL pattern: `SELECT * FROM (...) WHERE condition` -- a passing
  test returns 0 rows.
- `severity: warn` vs the default `error` (and what each does to the exit code).
- `store_failures: true` and its schema implications.
- Source-vs-model test redundancy: when "duplicate" tests are actually distinct
  contracts.

## Starting test inventory (verified from YAML, 2026-06-05)

Five declared tests before any Unit 2 edits:
- Source `met.raw_met_objects` `OBJECT_ID`: `unique`, `not_null` (2)
- Model `stg_met__artworks` `object_id`: `unique`, `not_null` (2)
- Model `stg_met__artworks` `title`: `not_null` (1)

A sixth test was added during the unit (the deliberate failure on `object_date`),
leaving 6 declared tests at unit close.

## Commands Run (in order)

1. `dbt test` -- baseline
   - Output summary: PASS=5 WARN=0 ERROR=0 (all original tests green).
   - Observation: a passing test returns 0 rows. The compiled SQL is
     `SELECT ... FROM (model) WHERE <condition that should never be true>`.

2. `dbt test` -- after adding `not_null` on `object_date` (default severity)
   - Output summary: FAIL 1 test, 109 failing rows.
   - Observation: read the compiled SQL under `target/compiled/` -- it is
     `SELECT object_date FROM SILVER.STG_MET__ARTWORKS WHERE object_date IS NULL`.
     109 rows is the real count of NULL/None object_date values in the 503-row view.
     Exit code = non-zero (a hard error fails the build).

3. `dbt test` -- after changing the test to `config: {severity: warn}`
   - Output summary: WARN 1, 109 rows; ERROR=0.
   - Observation: SAME 109 rows, different fate. `warn` keeps exit code 0, so the
     build proceeds. The number didn't change -- severity governs the *reaction*
     to failures, not the detection.

4. `dbt test` -- after adding `store_failures: true`
   - First attempt FAILED: "Schema 'ARTWORK_DB.DBT_TEST__AUDIT' does not exist or
     not authorized."
   - Fix: created `DBT_TEST__AUDIT` schema + granted ARTWORK_TRANSFORMER
     USAGE/CREATE TABLE/DML via IaC; re-ran `make infra` on the Mac.
   - Re-run output summary: PASS=5 WARN=1 ERROR=0.
   - Observation: failing rows are now materialized to
     `ARTWORK_DB.DBT_TEST__AUDIT.NOT_NULL_STG_MET__ARTWORKS_OBJECT_DATE`
     (109 rows, ALL 56 model columns -- because the test compiles to `SELECT *`).

## Decisions Made

- **Fork 1 -- severity on object_date:** accept `warn` (known data gap) rather than
  filter rows upstream.
  - **Choice:** `severity: warn` + `store_failures: true`.
  - **Rationale:** missing `object_date` is a real, accepted gap in the Met source
    (109/503 rows). We do not want it to break the build, but we DO want the failing
    rows queryable for analysts / future upstream fixers.

- **Fork 2 -- store_failures schema governance:** who owns the audit schema?
  - **Choice:** IaC owns `DBT_TEST__AUDIT` (added to
    `create_databases_and_schemas.sql` + grants); dbt gets CREATE TABLE + DML inside
    it, NOT `CREATE SCHEMA`.
  - **Rationale:** repo thesis is IaC-as-substrate. Letting dbt `CREATE SCHEMA` at
    runtime creates an account object invisible to the manifest (drift) and requires
    a broader privilege. IaC-owned keeps the schema reproducible from a clean
    teardown and grants least-privilege. The `generate_schema_name` allowlist (from
    Unit 1) already routed `DBT_TEST__AUDIT` verbatim -- only the *physical* schema
    was missing, which is why the macro accepted the write but Snowflake rejected it.

- **Fork 3 -- source-vs-model test redundancy:** `object_id` is tested unique+not_null
  in BOTH the source (`RAW_MET_OBJECTS`) and the model (`STG_MET__ARTWORKS`).
  - **Choice:** keep both.
  - **Rationale:** they LOOK identical (today the model's `object_id` is a verbatim
    passthrough, so if the source passes the model must pass), but they assert
    DIFFERENT contracts: the source test = an incoming-data contract / early warning
    at the Bronze boundary (and documents that contract for any future model reading
    `raw_met_objects`); the model test = a grain contract ("one row per object_id"
    in staging). A test is only redundant if the two can never diverge -- and the
    moment M2 multi-artist fan-out or M3 incremental/merge logic lands, the
    passthrough guarantee breaks and the model could violate uniqueness while the
    source stays clean. The "redundant" model test is a latent regression guard.
    Cost is trivial (metadata-light count queries over 503 rows).

- **Step 7 (warn_if/error_if thresholds):** SKIPPED. Built-in thresholds are
  count-based (evaluate `failures`, a row count); a percentage threshold would
  require a custom generic test that computes the ratio in its own SQL. Deferred.

## Errors Encountered

### Deliberate: not_null on object_date
- Command: added `not_null` test on `object_date` to `_met__models.yml`, ran `dbt test`.
- Error output: FAIL, 109 rows returned by the test.
- Diagnosis: read the compiled SQL (`WHERE object_date IS NULL`); 109 is the genuine
  count of objects with no display date in the Met source.
- Fix: not a bug to "fix" -- converted to `severity: warn` (accepted gap) and added
  `store_failures: true` to retain the failing rows for triage.

### Unexpected: DBT_TEST__AUDIT schema does not exist
- Command: `dbt test` after enabling `store_failures: true`.
- Error output: "Schema 'ARTWORK_DB.DBT_TEST__AUDIT' does not exist or not authorized."
- Diagnosis: `store_failures` writes to a `*_dbt_test__audit` schema; our verbatim
  `generate_schema_name` macro routed it to `DBT_TEST__AUDIT`, which had never been
  created in IaC. Root cause = missing physical schema, NOT a macro/allowlist issue.
- Fix: added `DBT_TEST__AUDIT` to `create_databases_and_schemas.sql`, added
  ARTWORK_TRANSFORMER grants (USAGE + CREATE TABLE + DML) in `create_grants.sql`,
  re-ran `make infra` on the Mac, re-ran `dbt test` -> PASS=5 WARN=1 ERROR=0.

## Key Takeaways

1. A dbt test is just SQL that returns the rows that VIOLATE the assertion -- 0 rows
   = pass. Reading `target/compiled/` demystifies every test.
2. Severity (`error` vs `warn`) governs the REACTION to failures (exit code / build
   gating), not the detection. The failing-row count is identical either way.
3. `store_failures: true` materializes the failing rows (`SELECT *`, all columns) to
   an audit schema -- great for accepted gaps and triage, truncate-and-reload each
   run (no history).
4. A runtime tool silently creating account objects is drift. We made IaC own
   `DBT_TEST__AUDIT` so the manifest remains the single source of truth; dbt gets
   table/DML privileges inside it, not `CREATE SCHEMA`.
5. The Unit-1 `generate_schema_name` allowlist paid off: it routed the audit schema
   verbatim; only the physical schema was missing. Routing (macro) and existence
   (IaC) are separate concerns.
6. "Redundant" source+model tests can be distinct contracts (incoming-data vs grain).
   Keep both when they will diverge under future transformations; the duplication is
   cheap insurance, not noise. Reflexive copy-everywhere IS the anti-pattern -- this
   wasn't that.

## Verification

```sql
-- Failing rows materialized by store_failures:
SELECT COUNT(*) FROM ARTWORK_DB.DBT_TEST__AUDIT.NOT_NULL_STG_MET__ARTWORKS_OBJECT_DATE;
-- Result: 109 (matches the WARN row count; full 56-column rows stored).
```
