# dbt-curriculum.md -- Hands-on dbt Mentorship Syllabus

> **Tier-1 doc.** This is the session-spanning syllabus for the dbt learning arc.
> It defines WHAT to learn and in what ORDER. Architectural decisions live in
> `dbt-plan.md` (do not duplicate here). Per-unit detailed notes, commands run,
> errors encountered, and key takeaways live in individual journal files created
> as each unit is started.

## New Window Protocol (READ THIS if resuming dbt work)

1. Read THIS file for overall progress (check the Status column below).
2. Read the journal file for the ACTIVE unit (the one marked `active` in Status).
   Journal files live at `docs/context/dbt-journal/unit-N-<slug>.md`.
3. Do NOT re-read completed unit journals unless the learner asks to review.
4. State your plan, wait for go + date. Honor the dual-FS rule.
5. When a unit completes, write a "Key Takeaways" section into its journal file
   and flip its status to `complete` in this file.
6. When starting a new unit, CREATE its journal file from the template below and
   flip status to `active`.

**Role reminder:** You are a senior dbt mentor. Explain the WHY at every step.
Name decision forks. Have the learner run commands (on their Mac -- never in the
workspace). Introduce deliberate failures so the learner practices diagnosis.

## Environment Facts (stable across windows)

- dbt Core runs on the Mac, NOT in the Snowsight workspace.
- Auth: key-pair via `profiles.yml` (`env_var()` for all secrets).
- Service user: `ARTWORK_TRANSFORMER_SVC` assuming role `ARTWORK_TRANSFORMER`.
- Project dir: `artwork_pipeline/` (profile name: `artwork_pipeline`).
- Source: `ARTWORK_DB.BRONZE.RAW_MET_OBJECTS` (503 rows as of 2026-06-05).
- Target schemas: SILVER (staging views), GOLD (mart tables).
- `copy_grants: true` is global (protects grants on OR REPLACE).
- Packages: `dbt_utils >=1.3,<2.0`, `codegen >=0.14,<0.15`.

## Curriculum Status

| Unit | Title | Status | Journal |
|------|-------|--------|---------|
| 1 | First Green Run | complete | `dbt-journal/unit-1-first-green-run.md` |
| 2 | dbt test -- Trust Your Source | complete | `dbt-journal/unit-2-trust-your-source.md` |
| 3 | Second Staging Model | active | `dbt-journal/unit-3-second-staging-model.md` |
| 4 | First Mart (Gold Layer) | pending | `dbt-journal/unit-4-first-mart.md` |
| 5 | Documentation and Lineage | pending | `dbt-journal/unit-5-docs-and-lineage.md` |
| 6 | The Incremental Conversation | pending | `dbt-journal/unit-6-incremental-preview.md` |

## Unit Outlines

### Unit 1: First Green Run

**Objective:** Execute `dbt deps` + `dbt run` against the existing
`stg_met__artworks` model. Observe the VIEW materialize in SILVER.

**What you will learn:**
- What `dbt run` generates under the hood (the compiled SQL).
- Why `copy_grants: true` matters on the very first run (and especially on
  subsequent `--full-refresh` runs).
- How `profiles.yml` env_var resolution works at invocation time.
- Reading `target/compiled/` and `target/run/` output to understand dbt internals.

**Decision fork:** None (this is a pure execution unit).

**Deliberate failure exercise:**
- After the green run, intentionally set `DBT_SNOWFLAKE_ROLE` to a role that does
  NOT have USAGE on `ARTWORK_DB`. Run again. Diagnose the Snowflake auth error
  from dbt's output. Then restore and re-run to confirm recovery.

**Verification (read-only SQL):**
```sql
SHOW VIEWS IN SCHEMA ARTWORK_DB.SILVER;
-- Expect: STG_MET__ARTWORKS
SELECT COUNT(*) FROM ARTWORK_DB.SILVER.STG_MET__ARTWORKS;
-- Expect: 503 (matches BRONZE.RAW_MET_OBJECTS)
```

---

### Unit 2: dbt test -- Trust Your Source

**Objective:** Run `dbt test` against the already-declared source and model tests.
Then add a test that WILL fail to learn severity configuration.

**What you will learn:**
- Source tests vs. model tests (when each fires, what SQL each generates).
- The compiled test SQL pattern: `SELECT * FROM (...) WHERE condition` -- a passing
  test returns 0 rows.
- Source freshness as a separate concern (not covered here; preview for later).
- `warn_if` / `error_if` severity thresholds.
- `store_failures: true` and its schema implications.

**Decision fork:** After seeing the failure on `object_date` (109 NULL rows),
decide: accept `warn` severity (known data gap) or filter those rows upstream in the
staging model? (Chosen 2026-06-05: `warn` + `store_failures`.)

**Deliberate failure exercise:**
- Add `not_null` test on `object_date` in `_met__models.yml`. Run `dbt test`.
  Observe the failure (FAIL, 109 rows). Then convert it to a `warn`-severity test
  with `config: {severity: warn}`, and add `store_failures: true` to materialize the
  failing rows to the IaC-owned `DBT_TEST__AUDIT` schema.

**Verification:**
```sql
-- After store_failures (note: generate_schema_name routes VERBATIM, so the audit
-- schema is DBT_TEST__AUDIT, NOT the dbt default SILVER_DBT_TEST__AUDIT):
SELECT COUNT(*) FROM ARTWORK_DB.DBT_TEST__AUDIT.NOT_NULL_STG_MET__ARTWORKS_OBJECT_DATE;
-- Or simply: check dbt CLI output for PASS/WARN/FAIL counts.
```

---

### Unit 3: Build a Second Staging Model

**Objective:** Create `stg_met__enrichment_status.sql` sourcing from
`MET_ENRICHMENT_CONTROL`. Declare it as a new source table in `_met__sources.yml`.

**What you will learn:**
- Multi-source staging: one `sources:` block can declare multiple tables.
- The `identifier:` property for mapping dbt's lowercase convention to Snowflake's
  UPPERCASE physical table names.
- When to use `view` vs `ephemeral` materialization (tradeoff: debuggability +
  direct-query access vs. zero schema footprint).
- How `{{ source() }}` compiles differently than `{{ ref() }}`.

**Decision fork:** Materialize as `view` (queryable, shows in SILVER, costs a
schema slot) or `ephemeral` (invisible, only exists inside downstream refs,
zero Snowflake object)? Mentor will lay out tradeoffs; learner decides.

**Deliberate failure exercise:**
- Omit the `identifier:` line for `MET_ENRICHMENT_CONTROL`. Run. Observe dbt
  looking for lowercase `met_enrichment_control` (which does not exist). Fix and
  re-run.

**Verification:**
```sql
-- If view:
SHOW VIEWS IN SCHEMA ARTWORK_DB.SILVER;
SELECT ENRICHMENT_STATUS, COUNT(*) FROM ARTWORK_DB.SILVER.STG_MET__ENRICHMENT_STATUS GROUP BY 1;
```

---

### Unit 4: Your First Mart (Gold Layer)

> **Prerequisite reading:** `docs/context/dbt-governance-plan.md` (the MVG-2
> section on `generate_schema_name` is implemented in this unit).

**Objective:** Build `marts/core/dim_artworks.sql` -- a TABLE in GOLD with a
surrogate key, selected business columns, and light transformation logic.

**What you will learn:**
- `dbt_utils.generate_surrogate_key()` -- what it does, why surrogate keys matter
  in dimensional modeling, and the MD5 vs. hash debate.
- TABLE materialization mechanics: `CREATE OR REPLACE TABLE ... AS SELECT`.
- Schema routing via `+schema: GOLD` in `dbt_project.yml` and how the
  `generate_schema_name` macro controls it (custom macro needed to drop the
  default prefix behavior).
- `{{ ref('stg_met__artworks') }}` -- the dependency graph.
- Why Gold is a table (pre-computed for consumers) vs. Silver being views
  (transparency, no storage duplication).

**Decision fork:** Use dbt's default `generate_schema_name` (which concatenates
`<target_schema>_<custom_schema>` = `SILVER_GOLD`) or add a custom macro that
uses the custom schema name verbatim? Mentor explains the gotcha; learner decides.

**Deliberate failure exercise:**
- Run `dbt run` (creates the table). Run again without `--full-refresh`. Observe
  it is a no-op (table already exists, no incremental logic). Discuss why this
  matters for idempotency and what changes when you add `is_incremental()` later.

**Verification:**
```sql
SHOW TABLES IN SCHEMA ARTWORK_DB.GOLD;
SELECT COUNT(*) FROM ARTWORK_DB.GOLD.DIM_ARTWORKS;
DESCRIBE TABLE ARTWORK_DB.GOLD.DIM_ARTWORKS;
-- Check surrogate key column exists and is non-null.
```

---

### Unit 5: Documentation and Lineage

**Objective:** Run `dbt docs generate` + `dbt docs serve`. Explore the DAG,
column descriptions, and lineage in the browser UI.

**What you will learn:**
- How `description:` fields in YAML render in the docs site.
- The DAG visualization (source -> staging -> marts dependency chain).
- Column-level lineage (what dbt CAN and CANNOT trace automatically).
- Why investing in docs early pays off when source #2 (Cleveland) arrives.
- `dbt docs generate` artifacts: `manifest.json`, `catalog.json`, `run_results.json`.

**Decision fork:** None (pure observation unit). But: discuss whether to commit
the `target/` artifacts or .gitignore them (standard: ignore; CI regenerates).

**Deliberate failure exercise:** None planned (this unit is a reward/cooldown
after the build-heavy Unit 4).

---

### Unit 6: The Incremental Conversation (Preview)

**Objective:** Understand what an incremental model WOULD look like for
`stg_met__artworks`, without building it yet. This primes Milestone 3.

**What you will learn:**
- The `{{ config(materialized='incremental', unique_key='object_id') }}` pattern.
- The `{% if is_incremental() %}` filter block and what SQL it compiles to on
  subsequent runs vs. first run.
- Hard-delete detection: why `MET_CSV_SNAPSHOT` (the full 484k-row catalog) is
  the diff source for detecting removed objects.
- The `+on_schema_change: 'append_new_columns'` config and its implications.
- `--full-refresh` as the escape hatch (and why you need `copy_grants`).

**Decision fork:** When to go incremental -- the cost/benefit: re-scanning 503
rows is free; re-scanning 484k rows is not. The trigger for converting is data
volume, not complexity.

**Deliberate failure exercise:** None (this is a discussion/whiteboard unit).
The actual build happens in a future window (M3).

---

## Journal File Template

When starting a new unit, create its journal file with this structure:

```markdown
# Unit N: <Title>

> Started: <date>  |  Completed: <date or "in progress">

## Objectives
<copied from curriculum>

## Commands Run (in order)
1. `<exact command>`
   - Output summary: ...
   - Observation: ...

## Decisions Made
- **Fork:** <description>
- **Choice:** <what was chosen>
- **Rationale:** <why>

## Errors Encountered
### Deliberate: <name>
- Command: ...
- Error output: ...
- Diagnosis: ...
- Fix: ...

### Unexpected: <name> (if any)
- ...

## Key Takeaways (written by AI after unit completes)
1. ...
2. ...
3. ...

## Verification
- <SQL run + result>
```

---

## What This Curriculum Intentionally Avoids

- **No `dbt init`:** The project is already scaffolded correctly.
- **No snapshot-strategy lecture:** Without a second data load to compare against,
  snapshots are academic. Deferred to after incremental is live.
- **No over-building:** We ship a working Silver view + Gold table with real tests
  against 503 live rows. Theory follows practice, not the reverse.
- **No Snowflake-native dbt (CREATE DBT PROJECT):** That is Milestone M3+, per
  `dbt-plan.md` decision D2.
