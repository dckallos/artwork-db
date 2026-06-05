# Unit 2: dbt test -- Trust Your Source

> Started: 2026-06-05  |  Completed: in progress

## Objectives

Run `dbt test` against the already-declared source and model tests. Then add a
test that WILL fail to learn severity configuration.

What you will learn:
- Source tests vs. model tests (when each fires, what SQL each generates).
- The compiled test SQL pattern: `SELECT * FROM (...) WHERE condition` -- a passing
  test returns 0 rows.
- Source freshness as a separate concern (not covered here; preview for later).
- `warn_if` / `error_if` severity thresholds.
- `store_failures: true` and its schema implications.

## Starting test inventory (verified from YAML, 2026-06-05)

Five declared tests before any Unit 2 edits:
- Source `met.raw_met_objects` `OBJECT_ID`: `unique`, `not_null` (2)
- Model `stg_met__artworks` `object_id`: `unique`, `not_null` (2)
- Model `stg_met__artworks` `title`: `not_null` (1)

## Commands Run (in order)
1. `<pending: dbt test>` -- baseline, expect PASS=5
   - Output summary: ...
   - Observation: ...

## Decisions Made
- **Fork:** (pending) after primary_image_url failure -- accept `warn` severity vs.
  filter rows upstream in the staging model.
- **Choice:** ...
- **Rationale:** ...

## Errors Encountered
### Deliberate: not_null on primary_image_url
- Command: ...
- Error output: ...
- Diagnosis: ...
- Fix: ...

### Unexpected: <name> (if any)
- ...

## Key Takeaways (written by AI after unit completes)
1. ...

## Verification
- <SQL run + result>
