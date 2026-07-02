# dbt-diagnostics Resilience Hardening

## Your Role

You are a **Principal Software Engineer** with deep expertise in Python CLI
tooling, dbt internals (manifest.json, run_results.json, catalog.json), and
Snowflake SQL error codes. Your standards: every change has a test, error
paths are explicit (never swallowed), and the CLI never crashes on unexpected
input -- it degrades gracefully with actionable messages.

## Repository

- Repo: github.com/dckallos/dbt-diagnostics (branch: main)
- Install: cd ~/dev/dbt-diagnostics && pip install -e ".[live,dev]"
- Run tests: cd ~/dev/dbt-diagnostics && pytest
- Run tool: cd ~/dev/artwork-db/artwork_pipeline && dbt-diagnostics diagnose

## Package Structure

    dbt-diagnostics/
      pyproject.toml          -- v0.5.0, deps: sqlglot, pyyaml, jinja2
      dbt_diagnostics/
        main.py               -- CLI entry + orchestration (18KB, core logic)
        models.py             -- dataclasses for findings, results, manifest
        discover.py           -- locates target/, manifest.json, run_results.json
        renderer.py           -- Jinja2 report rendering
        colors.py             -- terminal ANSI helpers
        config.yml            -- classifier/enricher config
        classifiers/          -- error classifiers (compilation, contract, data, runtime, schema_change, timeout)
        enrichers/            -- live Snowflake introspection (connection, grants, query_history, schema_inspector)
        tracers/              -- DAG walking, column lineage, diff, snippet extraction
        linters/              -- static manifest checks (contracts, aliases, types)
        templates/            -- Jinja2 .j2 report templates
        fixtures/             -- test JSON (manifest + run_results pairs)
        tests/                -- pytest suite

## Known Issues (from live dbt test output)

The tool was run against artwork_pipeline which produced 8 errors + 5 warnings.
dbt-diagnostics diagnose reported only 4 of the 8. Specific problems:

### 1. Silently drops FAIL results (only reports ERROR)

dbt distinguishes ERROR (SQL compilation/runtime failure) from FAIL (test
assertion returned rows, threshold breached). The tool only processes status=error,
ignoring status=fail. 4 staging row-count tests (stg_met__artists,
stg_met__artworks, stg_met__enrichment_status, stg_met__images) were
silently dropped.

Fix: Process status:"fail" results. Classify them as test_failure
(a new class). Report them with their compiled SQL, actual vs expected, and the
model they test.

### 2. Misleading "fix" advice for unmaterialized models

For GOLD tables that don't exist, the tool says "Fix the error in
model.artwork_pipeline.dim_artists, then re-run." But there IS no error in the
model SQL -- it simply hasn't been materialized yet. The advice should be:
"Model has not been materialized. Run dbt run -s <model> first, or defer
this test until after a full build."

Fix: When the runtime_error classifier detects "Object does not exist" AND
the lineage trace shows the model IS in the manifest but NOT in Snowflake,
generate the correct fix advice (run the model, don't "fix" it).

### 3. Error count mismatch in header

Header says "4 error(s)" but dbt reported 8 total failures. The header should
report the full picture: errors, fails, and warns (matching dbt's own summary
line: PASS=51 WARN=5 ERROR=8).

### 4. "Manifest: None" is confusing

For the test node, the lineage output shows Manifest: None / Run: error.
This is misleading -- the test IS in the manifest. Clarify what's actually
being reported (e.g., "Manifest: present" or show the test's ref dependencies).

## Approach

1. Read first, then plan. Read main.py, models.py, discover.py, and
   the classifiers/runtime_error.py to understand current flow.
2. Propose a plan (file-by-file changes) before writing code.
3. Tests for every fix. Add fixture JSON for status:"fail" results.
   Add a test case for the "unmaterialized model" scenario.
4. No scope creep. Fix the 4 issues above. Don't refactor unrelated code.
5. Run pytest after each change to confirm nothing breaks.

## Constraints

- Python 3.11+, no new dependencies
- Keep backwards compatibility: existing dbt-diagnostics diagnose invocations
  must not break
- ASCII-only in output (no emoji)
- Tests must pass offline (no live Snowflake connection required for unit tests)
