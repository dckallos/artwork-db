# dbt-diagnostics: Fixture Rewrite & Resilience Validation

## Your Role

You are a **Principal Software Engineer** (Staff+ at FAANG) with deep expertise in
Python CLI tooling, dbt internals (manifest.json, run_results.json, catalog.json),
and Snowflake SQL error codes. Your standards: every fixture is grounded in REAL
production data, error paths are explicit (never swallowed), and the test suite
catches regressions that matter -- not just "does the code run" but "does the
output match what a user actually sees."

You are a **data quality fanatic**. If a fixture contains invented data that
doesn't match what dbt actually produces, you consider it a defect -- because
the tool's consumers are diagnosing real pipeline failures, and hallucinated
test data masks real bugs.

## Context

Repository: `github.com/dckallos/dbt-diagnostics` (branch: `main` for base,
`fix/resilience-hardening-4-issues` for the in-progress fix).

The tool was run against the `artwork_pipeline` dbt project which produced
**8 failures** (4 ERROR + 4 FAIL) and **5 warnings**. The tool (`dbt-diagnostics
diagnose`) currently reports only **4 of the 8 failures** -- all 4 FAIL results
are silently dropped.

A prior Cortex Code session pushed a fix commit to the branch
`fix/resilience-hardening-4-issues` that addresses 4 known issues. However,
**the fixtures in that commit are AI-generated guesses** that do NOT match the
real dbt output. They need to be replaced with data derived from the actual
`run_results.json` and `manifest.json`.

## Evidence Files (in this workspace)

1. **`tmp/run_results_for_fixtures.json`** -- The REAL `target/run_results.json`
   from a live `dbt test` run (dbt 1.11.11, dbt-snowflake 1.11.5). 64 results.
   This is the authoritative source for what the tool parses.

2. **`tmp/diagnose.log`** -- The REAL output of `dbt-diagnostics diagnose` run
   against the same project. Shows what the tool currently produces (4 errors
   reported, 4 fails silently dropped, header says "4 error(s)" when dbt
   reported 8 total failures).

## What the tool gets RIGHT (from `tmp/diagnose.log`)

- Correctly identifies the 4 ERROR results (Object does not exist)
- Correctly classifies them as `runtime_error`
- Correctly extracts the problematic SQL line (line 16, the `from` clause)
- Correctly traces lineage to find the parent model
- Correctly determines the model is in the manifest but not in Snowflake
- Correct verdict: "was never materialized"

## What the tool gets WRONG (compare `tmp/diagnose.log` vs `tmp/run_results_for_fixtures.json`)

1. **Silently drops all 4 FAIL results** -- The staging row-count tests
   (`stg_met__artworks`, `stg_met__artists`, `stg_met__enrichment_status`,
   `stg_met__images`) have status="fail" and are completely invisible in the
   output. Zero mention.

2. **Header count mismatch** -- Reports "4 error(s)" but dbt's summary was
   `PASS=51 WARN=5 ERROR=8`. The tool should show errors, fails, and warns
   (matching dbt's own summary line).

3. **Misleading "fix" advice** -- For unmaterialized GOLD tables, the FIX says
   "Fix the error in model.artwork_pipeline.dim_artists, then re-run." But
   there IS no error in the model SQL -- it simply hasn't been materialized.
   The correct advice: "Run `dbt run -s dim_artists` first."

4. **"Manifest: None" is confusing** -- The lineage trace shows "Manifest: None"
   for the test node (818205a8b7). The test IS in the manifest. This display is
   misleading.

## Branch State

The branch `fix/resilience-hardening-4-issues` has a single commit that
attempts to fix all 4 issues. The code logic changes (in `main.py`,
`runtime_error.py`, `test_failure.py`, templates) are structurally sound but
the **fixtures are wrong** -- they were invented without access to real dbt
output. Specific fixture problems:

- Wrong schema version (v5 vs real v6)
- Wrong message format for errors ("in model" vs real "in test", missing error code)
- Wrong message for fails ("Got 0 results, configured to fail if < 1" vs real "Got 1 result, configured to fail if != 0")
- Wrong adapter_response shape for errors
- Wrong unique_id format (fake hash suffixes)
- `failures: 1` for errors (real value is `null`)

## Your Task

1. **Read the existing branch code** via GitHub MCP (`dckallos/dbt-diagnostics`,
   branch `fix/resilience-hardening-4-issues`). Understand what the logic changes do.

2. **Read the real artifacts** in this workspace (`tmp/run_results_for_fixtures.json`
   and `tmp/diagnose.log`) to understand the ground truth.

3. **Design corrected fixtures** (`test_failures.json` and `manifest_test_failures.json`)
   derived from the real data. Trim to a representative subset (2 errors, 2 fails,
   1 warn, 2 passes -- enough to exercise all code paths without bloat).

4. **Update the test file** (`tests/test_test_failure.py`) so assertions match
   the corrected fixture data.

5. **Validate that the existing logic changes** in `main.py`, `runtime_error.py`,
   `test_failure.py`, and templates will work correctly with the real data shapes.
   If they won't, propose fixes.

6. **Push the corrected files** to the `fix/resilience-hardening-4-issues` branch
   as a new commit. Do NOT force-push or rebase -- add a commit on top.

## Constraints

- Python 3.11+, no new dependencies
- Keep backwards compatibility: existing `dbt-diagnostics diagnose` invocations must not break
- ASCII-only in output (no emoji in code/fixtures)
- Tests must pass offline (no live Snowflake connection required for unit tests)
- Fixtures must be structurally faithful to real dbt output (schema version,
  field names, null vs missing, types)

## Access

- GitHub MCP tools: full read/write access to `dckallos/dbt-diagnostics`
- This workspace: `tmp/run_results_for_fixtures.json` and `tmp/diagnose.log`
- The manifest data was provided in a prior conversation turn (the full
  `manifest.json` nodes for the artwork_pipeline project). Key nodes to include
  in the manifest fixture: `dim_artists`, `dim_artworks`, `fct_artwork_images`,
  `openaccess_catalog`, `stg_met__artworks`, `stg_met__artists`,
  `stg_met__enrichment_status`, `stg_met__images`, and the test nodes that
  reference them.

## How to Start

1. Read `tmp/run_results_for_fixtures.json` in this workspace
2. Read the branch files via GitHub MCP:
   - `dbt_diagnostics/fixtures/test_failures.json` (on `fix/resilience-hardening-4-issues`)
   - `dbt_diagnostics/fixtures/manifest_test_failures.json`
   - `dbt_diagnostics/tests/test_test_failure.py`
   - `dbt_diagnostics/classifiers/test_failure.py`
   - `dbt_diagnostics/main.py`
3. Design the corrected fixtures
4. Propose the plan, wait for approval, then execute
