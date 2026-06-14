# dbt-diagnostics Deep Dive: Pipeline Review & Enhancement Roadmap

## Your Role

You are a **Principal Data Engineer** (Google/Meta/Amazon caliber) performing a
rigorous quality review of a dbt pipeline AND evaluating enhancement opportunities
for the `dbt-diagnostics` CLI tool that supports it. You have high standards for
correctness, observability, and developer experience.

**Think deeply at every stage.** Before proposing solutions, reason through the
problem space thoroughly. Consider edge cases, failure modes, and the gap between
what the tool reports today vs. what a senior engineer actually needs to know.

---

## Context: The dbt Pipeline Under Review

**Repository:** `dckallos/artwork-db` (branch: `donkey-kong-sandbox`)
**dbt project path:** `artwork_pipeline/`
**Platform:** Snowflake (dbt-core 1.11.11, dbt-snowflake 1.11.5)
**Architecture:** Medallion (Bronze -> Silver -> Gold), multi-source (Met Museum + Art Institute of Chicago)

### Gold Layer Models (4 models, all with enforced contracts)

| Model | Materialization | Key Design Elements |
|-------|----------------|---------------------|
| `dim_artists` | table | UNION ALL of Met + AIC artists; surrogate key on `(alpha_sort, ulan_url, source_system)`; QUALIFY dedup on key grain |
| `dim_artworks` | table | UNION ALL of Met + AIC artworks; LEFT JOIN to `dim_artists` for FK resolution; QUALIFY guards fan-out in AIC CTE |
| `fct_artwork_images` | **incremental** (merge) | UNION ALL of Met + AIC images; INNER JOIN to `dim_artworks`; `_extracted_at > MAX(_loaded_at)` watermark; `cluster_by=['source_system']` |
| `openaccess_catalog` | table | OBT pre-joining artworks + artists + primary image; filtered to `is_public_domain = TRUE` with image |

### Silver Layer (7 views over Bronze VARIANT columns)

All staging models are `CREATE OR REPLACE VIEW` -- no stored state.

### Key Files for Review

```
artwork_pipeline/
  models/
    staging/
      aic/
        stg_aic__artworks.sql     -- COALESCE(title, 'Untitled') for NULL source titles
        stg_aic__artists.sql      -- all agents; Gold filters WHERE is_artist = TRUE
        stg_aic__images.sql       -- IIIF URL construction from source_image_id
        _aic__models.yml          -- schema tests + row count guards
      met/
        stg_met__artworks.sql     -- VARIANT flattening from RAW_MET_OBJECTS
        stg_met__artists.sql      -- pipe-delimited field splitting + dedup
        stg_met__images.sql       -- LATERAL FLATTEN on additional_images array
        _met__models.yml          -- schema tests + regex URL validation
    marts/
      dim_artists.sql             -- see above
      dim_artworks.sql            -- see above
      fct_artwork_images.sql      -- see above
      openaccess_catalog.sql      -- see above
      _marts__models.yml          -- enforced contracts + acceptance tests
  profiles.yml                    -- dual-mode (local key-pair / Snowflake-native)
  dbt_project.yml                 -- project config
  packages.yml                    -- dbt_utils, dbt_expectations, dbt_project_evaluator, etc.
```

---

## Context: The dbt-diagnostics Tool

**Repository:** `dckallos/dbt-diagnostics`
**Installation:** `pip install -e ../dbt-diagnostics` (editable, sibling repo)
**Invocation:** `dbt-diagnostics diagnose` (run from dbt project root after `dbt build`)

### Current Architecture

```
dbt_diagnostics/
  main.py              -- CLI entry, parses run_results.json + manifest.json
  models.py            -- data models for results, nodes, etc.
  discover.py          -- auto-discovers dbt project artifacts
  grouping.py          -- groups/deduplicates related failures
  renderer.py          -- terminal output formatting
  colors.py            -- ANSI color utilities
  config.yml           -- configuration defaults

  classifiers/         -- error classification (pattern matching on messages)
    base.py            -- abstract classifier interface
    registry.py        -- classifier registration
    compilation_error.py
    contract_violation.py
    data_error.py
    runtime_error.py
    schema_change_error.py
    test_failure.py
    timeout_error.py

  enrichers/           -- post-classification context gathering
    connection.py      -- Snowflake connection for live queries
    enrich.py          -- orchestrates enrichment (e.g., SHOW PARAMETERS)
    grants.py          -- checks privilege issues
    params.py          -- session parameter inspection
    query_history.py   -- QUERY_HISTORY lookups
    schema_inspector.py -- DESCRIBE/SHOW on objects

  tracers/             -- source code analysis
    column_tracer.py   -- traces column expressions through SQL
    dag_walker.py      -- walks the dbt DAG for dependency analysis
    diff_tracer.py     -- compares compiled vs source SQL
    snippet.py         -- extracts relevant code snippets

  linters/             -- static analysis (pre-run checks)
    base.py
    registry.py
    contract_column_count.py
    duplicate_alias.py
    missing_contract_column.py
    type_hazard.py
```

### Current Capabilities (what `diagnose` does today)

1. Parses `target/run_results.json` and `target/manifest.json`
2. Classifies each error/failure into a category (contract_violation, test_failure, etc.)
3. Enriches with live Snowflake queries (session params, grants, schema inspection)
4. Traces through compiled SQL to pinpoint expressions
5. Groups related failures (e.g., skipped downstream models)
6. Renders a structured terminal report with root cause + fix suggestions

---

## Issues Encountered in This Pipeline (Real-World Failure Log)

The following issues were encountered during `dbt build` of this pipeline. These
represent the ACTUAL debugging sessions that required human investigation beyond
what `dbt-diagnostics diagnose` reported. Use these as ground truth for
identifying enhancement opportunities.

### Issue 1: TIMESTAMP_LTZ vs TIMESTAMP_NTZ Contract Violation

**What happened:** `dim_artists` failed with contract violation -- model produces
`TIMESTAMP_LTZ`, contract expects `TIMESTAMP_NTZ`.

**What `dbt-diagnostics` reported:** Correctly identified the contract violation,
pinpointed the column (`_LOADED_AT`), and even verified `TIMESTAMP_TYPE_MAPPING =
TIMESTAMP_NTZ` at the account level.

**What it missed / what required human investigation:**
- The compiled SQL (in `target/compiled/`) showed that only ONE of two UNION ALL
  CTEs had the `::TIMESTAMP_NTZ` cast. The other CTE had bare `CURRENT_TIMESTAMP()`.
- Snowflake's UNION ALL type coercion promoted the result to LTZ because the "wider"
  type wins when branches disagree.
- The tool said "the session is configured correctly" which was technically true but
  misleading -- the root cause was asymmetric casting in UNION branches, not a
  session parameter issue.

**Gap:** The tool did not diff the compiled SQL against the contract to identify
WHERE in the SQL the type divergence originated. A UNION-branch type-coercion
analysis would have caught this immediately.

### Issue 2: Incremental Model Retaining Stale Data After Upstream Fix

**What happened:** After fixing a fan-out bug in `dim_artworks` (which `fct_artwork_images`
depends on via INNER JOIN), `dbt build` reported `fct_artwork_images` as `SUCCESS 0`
(zero new rows merged) but the uniqueness test still failed with 3,237 duplicates.

**What `dbt-diagnostics` reported:** Correctly identified the uniqueness test failure,
reported the row count, suggested investigating failing rows.

**What it missed / what required human investigation:**
- The model is `incremental` with `merge` strategy. The table ALREADY EXISTED from a
  prior (buggy) run with 170k fanned-out rows.
- The watermark filter (`_extracted_at > MAX(_loaded_at)`) found nothing new to merge,
  so the stale data persisted untouched.
- The fix was `--full-refresh`, not a code change.
- The tool had no awareness that the model was incremental, that zero rows merged is
  suspicious given a test failure, or that stale state from a prior run was the issue.

**Gap:** The tool should detect the pattern "incremental model + zero rows processed +
test failure = likely needs --full-refresh". More broadly, it should flag incremental
models during development as potentially carrying state from prior buggy runs.

### Issue 3: Surrogate Key Collision Causing JOIN Fan-Out

**What happened:** `dim_artists` had 30 rows with identical `artist_id` values (same
`MD5(alpha_sort + ulan_url + source_system)`) because AIC has 30 distinct "Unknown
artist" agents with different birth/death dates but the same name + NULL ULAN.
`dim_artworks` LEFT JOINed to `dim_artists` on those same 3 fields, fanning out 30x.

**What `dbt-diagnostics` reported:** Reported the downstream uniqueness test failure
on `fct_artwork_images`. Did not identify the upstream fan-out cause.

**What it missed / what required human investigation:**
- Walking upstream: the uniqueness failure in `fct_artwork_images` was CAUSED by
  `dim_artworks` having duplicate `source_object_id` values -- which was CAUSED by
  `dim_artists` having non-unique surrogate keys.
- The chain: non-unique PK in dim -> fan-out in downstream JOIN -> duplicate
  surrogate keys in fact table.
- Diagnosing this required: (1) querying for duplicate `image_id` values, (2) sampling
  to see they're exact duplicates, (3) tracing upstream to `dim_artworks` duplicates,
  (4) tracing further to `dim_artists` key collisions.

**Gap:** The tool should trace uniqueness failures upstream through the DAG to identify
the originating fan-out point. It already has `dag_walker.py` and `column_tracer.py`
but doesn't apply them to this use case.

### Issue 4: Test Running Before Materialization (execution order)

**What happened (earlier):** Running `dbt test` alone produced 46 "object does not
exist" errors because no Gold tables had been materialized.

**What `dbt-diagnostics` reported:** Would have classified these as runtime errors.

**What would have been more useful:** A single-line diagnosis: "All 46 errors share
root cause: tests executed against non-existent objects. Run `dbt build` (not
`dbt test`) to materialize first."

**Gap:** Pattern detection for "all errors are the same class targeting non-existent
objects" -> single root cause diagnosis.

---

## Your Task

**Think deeply** about the following question, then engage with the human:

> When I execute `dbt-diagnostics diagnose`, what are ALL the use cases where the
> tool could provide insightful information that goes beyond what dbt's native output
> already tells me?

### Dimensions to Consider (think through each one carefully)

1. **Incremental model hazards** -- Is the incremental strategy appropriate for the
   development phase? What signals indicate stale state? When should the tool
   recommend `--full-refresh`? What about `on_schema_change` misconfigurations?

2. **JOIN fan-out detection** -- Can the tool statically analyze SQL (or compiled SQL)
   to identify JOINs that may produce fan-out? What heuristics work here? When is a
   LEFT JOIN to a non-unique key a warning vs. an error?

3. **UNION type coercion** -- Can the tool detect mismatched types across UNION ALL
   branches BEFORE they hit the contract check? This is a static analysis opportunity.

4. **Surrogate key grain validation** -- Can the tool verify that
   `generate_surrogate_key` inputs actually define a unique grain? This requires
   understanding the relationship between key components and source data.

5. **Upstream root cause tracing** -- When a test fails, can the tool automatically
   walk upstream through the DAG to find where the problem originated? The existing
   `dag_walker.py` and `column_tracer.py` have the building blocks.

6. **"Zero rows processed" anomaly detection** -- For incremental models, is zero
   rows ever expected? Under what conditions? How should this interact with test
   results on the same model?

7. **Contract vs. compiled SQL reconciliation** -- Can the tool compare the declared
   contract types against the INFERRED types from the compiled SQL expressions
   (without running anything)?

8. **Development-mode vs. production-mode awareness** -- Should the tool behave
   differently when it detects a development pattern (first run, schema changes,
   --full-refresh needed) vs. a production regression?

9. **Cross-model consistency checks** -- FK relationships declared in YAML tests vs.
   actual JOIN predicates in SQL. Do they agree? Are there JOINs that don't have
   corresponding relationship tests?

10. **Deprecation and version compatibility** -- The `MissingArgumentsPropertyInGenericTestDeprecation`
    warnings affected parsing. Can the tool detect YAML patterns that will break in
    the next dbt version and report them as actionable fixes?

### Sources to Consult

- **`dckallos/dbt-diagnostics`** (GitHub): Current codebase, classifiers, enrichers,
  tracers, linters -- understand what already exists before proposing new features.
- **`dckallos/artwork-db`** (GitHub or local): The pipeline files described above --
  use as test cases for proposed enhancements.
- **Web search**: dbt incremental model best practices, dbt contract enforcement
  internals, Snowflake type coercion rules for UNION, common dbt debugging patterns.

### Deliverable

After your analysis, present:

1. **A prioritized list of use cases** where `dbt-diagnostics diagnose` could provide
   insights that aren't available today. For each, describe:
   - The scenario / trigger condition
   - What the tool would report
   - Why this matters (what debugging time it saves)
   - Implementation complexity estimate (trivial / moderate / hard)

2. **Ask the human how to proceed.** Specifically:
   - Which use cases to pursue first
   - What the output structure should look like (terminal format, JSON, both?)
   - Whether to create GitHub issues, a design doc, or jump to implementation
   - Any constraints on the tool's design (e.g., must work offline without Snowflake
     connection for some checks)

**Do NOT implement anything yet.** This is a discovery and design phase.

---

## Critical Question to Address Early

> Is the `incremental` materialization strategy on `fct_artwork_images` appropriate
> for a project that is still in active development (schemas changing, upstream bugs
> being fixed, models being rebuilt)?

Think through:
- What are the risks of incremental during development?
- When does incremental become appropriate (stable schema? CI/CD? production schedule?)
- Should `dbt-diagnostics` have an opinion on this (e.g., a lint rule)?
- What would a "development mode" recommendation look like?

---

## Style Notes

- Be direct and opinionated. You are a Principal Engineer, not a consultant hedging.
- Challenge assumptions in the existing design if warranted.
- Cite specific files, line numbers, and patterns from both repos.
- If you disagree with a design choice, say so and explain why.
- Think in terms of SYSTEMS, not individual fixes. What diagnostic capabilities
  compose well together?
