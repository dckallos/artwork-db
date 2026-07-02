# dbt Diagnostics Tool -- Design Plan

> Created: 2026-06-06 | Status: planning (not yet implemented)
>
> A Python-based diagnostic tracer that parses dbt build errors, walks the DAG
> backwards through model lineage, and finds the root cause layer where a
> type/value/schema mismatch was first introduced.

## Problem Statement

When a Gold-layer model contract fails (e.g. `TIMESTAMP_LTZ` vs `TIMESTAMP_NTZ`),
the error fires at the LAST layer but the cause may live in ANY upstream layer:

```
Bronze: _EXTRACTED_AT is TIMESTAMP_LTZ (Snowflake default)
  -> Silver: view passes it through (no cast) -- still LTZ
    -> Gold: CURRENT_TIMESTAMP() produces LTZ; contract says NTZ
      -> ERROR reported here
```

A human traces this manually by reading the error, opening the model SQL, checking
upstream views, querying Snowflake `DESCRIBE`, and checking session parameters.
This tool automates that trace.

## Input Sources (how the tool gets error data)

The tool reads dbt artifacts -- NOT pasted logs. dbt produces structured JSON after
every invocation, even failed ones.

### Primary inputs (always available in `target/`):

| File | Contents | Key fields |
|------|----------|-----------|
| `target/run_results.json` | One entry per model/test with status, message, compiled_code | `results[].status`, `results[].message`, `results[].unique_id` |
| `target/manifest.json` | Full project DAG: every node, its dependencies, column definitions, configs | `nodes`, `sources`, `parent_map`, `child_map` |
| `target/compiled/<path>.sql` | The actual SQL dbt would execute (Jinja resolved) | Raw SQL text |

### Secondary inputs (richer context):

| File | Contents | When to use |
|------|----------|-----------|
| `target/catalog.json` | Column types + stats for materialized objects (from `dbt docs generate`) | Cross-referencing actual vs expected types |
| `logs/dbt.log` (JSON mode) | Streaming event log with macro call chains | When you need the full "stacktrace" (called by X, called by Y) |

### How to enable JSON logs:

```bash
# Option A: environment variable (recommended -- set once)
export DBT_LOG_FORMAT=json

# Option B: per-invocation flag
dbt build --select tag:marts --log-format json
```

## Architecture

```
dbt_diagnostics/
|-- diagnose.py              # Entry point (single script for now)
|-- config.yml               # Project-specific expectations + connection info
|-- classifiers/             # (future) One module per error class
|   |-- contract_violation.py
|   |-- runtime_error.py
|   +-- test_failure.py
+-- tracers/                 # (future) DAG walking + Snowflake inspection
    |-- dag_walker.py
    |-- type_tracer.py
    +-- snowflake_inspector.py
```

### Phase 1 deliverable: `diagnose.py` (single script, ~250 lines)

Does everything in one file. Refactor into modules later when pattern stabilizes.

## Error Classification

The tool classifies errors into buckets, each with its own resolution strategy:

| Error class | Detection signal | Resolution strategy |
|-------------|-----------------|---------------------|
| **Contract type mismatch** | `"enforced contract that failed"` + mismatch table in message | Parse table -> find column -> trace type through DAG |
| **Contract column missing** | `"number of columns"` in mismatch_reason | Compare model SELECT list vs contract YAML |
| **Compilation error (SQL)** | `status: "error"` + Snowflake SQL error code in message | Parse error code, find the expression, check upstream |
| **Compilation error (Jinja)** | `"Compilation Error"` + `"Undefined variable"` or similar | Check macro arguments, ref() targets |
| **Test failure (data)** | `status: "fail"` + `"Got N results, configured to fail"` | Query the test SQL, inspect failing rows, trace upstream |
| **Dependency skip** | `status: "skipped"` | Find the upstream error that caused the skip chain |

## DAG Walking Logic

Given an error on model `X`:

```python
def trace_upstream(manifest, target_node_id, target_column):
    """Walk backwards through the DAG to find root cause."""
    
    # 1. Get the node's parent models from manifest
    parents = manifest['parent_map'][target_node_id]
    
    # 2. For each parent, DESCRIBE the Snowflake object
    #    (if materialized) or parse the compiled SQL (if view)
    for parent_id in parents:
        parent_node = manifest['nodes'][parent_id]
        # ...
    
    # 3. Check: does the target_column exist in this parent?
    #    If yes, what's its type? Does it match the expected type?
    
    # 4. If mismatch found here, recurse into THIS node's parents
    #    If type is correct here, the problem is in the CURRENT model's transform
    
    # 5. Return the first layer where the mismatch appears
```

### Column lineage within a model (sqlglot):

```python
import sqlglot
from sqlglot.lineage import lineage

# Parse compiled SQL, trace _LOADED_AT back to its source expression
compiled_sql = open("target/compiled/.../dim_artists.sql").read()
node = lineage("_LOADED_AT", compiled_sql, dialect="snowflake")
# -> tells you it comes from CURRENT_TIMESTAMP() (a function, not a column ref)
```

## Configuration File (`config.yml`)

```yaml
# =============================================================================
# dbt_diagnostics/config.yml -- Project-specific diagnostic configuration
# =============================================================================

# Where to find dbt artifacts
project:
  path: ./artwork_pipeline
  target_dir: ./artwork_pipeline/target
  compiled_dir: ./artwork_pipeline/target/compiled/artwork_pipeline/models

# Snowflake connection (for DESCRIBE queries during tracing)
# Uses the same connection as dbt -- reads from profiles.yml or env vars
connection:
  profile: artwork_pipeline
  target: dev
  # OR explicit (if not using profiles.yml):
  # account: OBANOYY-MK07348
  # role: ARTWORK_TRANSFORMER
  # warehouse: COMPUTE_WH
  # database: ARTWORK_DB

# Type expectations (your team's standards)
type_policies:
  timestamps:
    preferred: TIMESTAMP_NTZ
    reason: "All internal timestamps are UTC; no timezone context needed"
    known_producers_of_ltz:
      - "CURRENT_TIMESTAMP() without explicit cast"
      - "Account parameter TIMESTAMP_TYPE_MAPPING = TIMESTAMP_LTZ"
      - "METADATA$ACTION columns in streams"
    fix_pattern: "Cast to NTZ: CURRENT_TIMESTAMP()::TIMESTAMP_NTZ"
  
  numbers:
    default_precision: 38
    default_scale: 0
    flag_if_scale_exceeds: 6
  
  strings:
    flag_unbounded_varchar: true  # warn if contract uses VARCHAR(16777216)
    max_reasonable_length: 4096

# Error class overrides (customize severity / behavior)
error_handling:
  contract_type_mismatch:
    severity: error
    auto_trace: true        # automatically walk DAG on this error type
    check_session_params: true  # query SHOW PARAMETERS for timestamp mapping
  
  test_failure:
    severity: warn
    auto_trace: false       # just report; don't walk DAG for test failures
  
  dependency_skip:
    severity: info
    # Just report which upstream error caused the skip chain

# Snowflake session parameters to check (tracing context)
session_params_to_check:
  - TIMESTAMP_TYPE_MAPPING
  - TIMESTAMP_INPUT_FORMAT
  - TIMESTAMP_OUTPUT_FORMAT
  - TIMEZONE
  - BINARY_INPUT_FORMAT
```

## Implementation Roadmap

### Phase 1: Contract violation tracer (first script)

**Scope:** Handle the exact error class you hit today -- contract type mismatch.

**Steps:**
1. Load `target/run_results.json` -- find entries with `status: "error"`
2. Parse the mismatch table from the `message` field (regex on pipe-delimited table)
3. Extract: column_name, definition_type (what model produces), contract_type (what YAML expects)
4. Load `target/manifest.json` -- find the node, its compiled SQL path, its parents
5. Read the compiled SQL -- use sqlglot to trace the column back to its source expression
6. If source is a function (e.g. `CURRENT_TIMESTAMP()`): report the fix
7. If source is a ref()'d column: DESCRIBE the upstream object in Snowflake, compare types
8. Walk upstream until the mismatch disappears -- that's the root cause layer

**Output example:**
```
DIAGNOSIS: Contract type mismatch in dim_artists
  Column: _LOADED_AT
  Contract expects: TIMESTAMP_NTZ
  Model produces:   TIMESTAMP_LTZ

ROOT CAUSE: dim_artists.sql line 24
  Expression: CURRENT_TIMESTAMP()
  Produces TIMESTAMP_LTZ because account parameter TIMESTAMP_TYPE_MAPPING = TIMESTAMP_LTZ

FIX OPTIONS:
  1. Cast in the model: CURRENT_TIMESTAMP()::TIMESTAMP_NTZ  (recommended)
  2. Change account param: ALTER ACCOUNT SET TIMESTAMP_TYPE_MAPPING = TIMESTAMP_NTZ
  3. Change contract: set data_type to TIMESTAMP_LTZ in _marts__models.yml
```

### Phase 2: Test failure tracer

Parse test failures, query the failing rows, trace the bad values upstream.

### Phase 3: Runtime SQL error tracer

Parse Snowflake error codes, correlate with the compiled SQL expression that failed.

### Phase 4: Auto-fix mode (optional)

For known-safe fixes (like adding `::TIMESTAMP_NTZ`), optionally write the file edit.

## Python Dependencies

These are Python packages the diagnostic script needs (NOT dbt packages):

```
# requirements.txt (for the diagnostic tool)
sqlglot>=26.0
dbt-artifacts-parser>=1.0
snowflake-connector-python>=3.0
pyyaml>=6.0
```

## Usage

```bash
# After a failed dbt build:
cd artwork_pipeline
dbt build --select tag:marts    # fails with contract error

# Run the diagnostic tool (reads target/ artifacts automatically):
python ../dbt_diagnostics/diagnose.py

# Or with explicit paths:
python ../dbt_diagnostics/diagnose.py \
  --run-results target/run_results.json \
  --manifest target/manifest.json \
  --config ../dbt_diagnostics/config.yml
```

---

## Package Exploration Guide ("Dabble" Instructions)

These are the dbt packages in your `packages.yml` and the Python packages for the
diagnostic tool. For each one, here's how to quickly see its value.

### dbt Packages (in packages.yml)

#### 1. dbt_utils (dbt-labs/dbt_utils)

**What it does:** Utility macros -- surrogate keys, pivot, date spines, generic tests.

**Dabble:**
```bash
# You're already using it (generate_surrogate_key). Try these:
# In a dbt model or analysis:
SELECT {{ dbt_utils.star(from=ref('stg_met__artworks'), except=["_extracted_at", "_batch_id"]) }}
FROM {{ ref('stg_met__artworks') }}

# Generate a date spine:
{{ dbt_utils.date_spine(datepart="day", start_date="'2020-01-01'", end_date="'2026-12-31'") }}
```

#### 2. dbt_expectations (metaplane/dbt_expectations)

**What it does:** 50+ Great Expectations-style tests as dbt-native YAML. Statistical
distributions, regex matching, row count bounds, cross-column comparisons.

**Dabble:**
```yaml
# Already in your _met__models.yml. Try adding to any model:
columns:
  - name: object_begin_date
    tests:
      - dbt_expectations.expect_column_values_to_be_between:
          min_value: -5000  # No artwork before 5000 BC
          max_value: 2030
          config:
            severity: warn
      - dbt_expectations.expect_column_most_common_value_to_be_in_set:
          value_set: [null]  # Most artworks have no begin_date
          top_n: 1
```

#### 3. dbt_project_evaluator (dbt-labs/dbt_project_evaluator)

**What it does:** Audits your DAG structure, naming conventions, test coverage,
documentation coverage. Outputs models you can query for violations.

**Dabble:**
```bash
# Run the evaluator (creates views in DBT_TEST__AUDIT):
dbt build --select package:dbt_project_evaluator

# Then query what it found:
# (run in Snowflake after the above)
SELECT * FROM ARTWORK_DB.DBT_TEST__AUDIT.FCT_MODEL_NAMING_CONVENTIONS;
SELECT * FROM ARTWORK_DB.DBT_TEST__AUDIT.FCT_DOCUMENTATION_COVERAGE;
SELECT * FROM ARTWORK_DB.DBT_TEST__AUDIT.FCT_TEST_COVERAGE;
```

#### 4. audit_helper (dbt-labs/audit_helper)

**What it does:** Compare two relations row-by-row or column-by-column. Essential
for verifying refactors didn't change output, or comparing dev vs prod.

**Dabble:**
```sql
-- Create an analysis file: analyses/compare_artworks.sql
-- Compare your staging model against a known-good snapshot:
{% set audit_query = audit_helper.compare_relations(
    a_relation=ref('stg_met__artworks'),
    b_relation=source('met', 'raw_met_objects'),
    primary_key='object_id',
    exclude_columns=['_extracted_at', '_batch_id']
) %}

{{ audit_query }}

-- Run: dbt compile --select compare_artworks
-- Then execute the compiled SQL manually to see match/mismatch counts
```

#### 5. dbt_snowflake_monitoring (get-select/dbt_snowflake_monitoring)

**What it does:** Models Snowflake ACCOUNT_USAGE views to calculate cost per query,
warehouse utilization, and query performance metrics.

**Dabble:**
```bash
# This package creates models from Snowflake metadata. Build them:
dbt run --select package:dbt_snowflake_monitoring

# Then query cost insights:
SELECT * FROM <schema>.QUERY_COST  -- cost per query
SELECT * FROM <schema>.WAREHOUSE_COST  -- cost per warehouse per day
```

**Note:** This package requires access to `SNOWFLAKE.ACCOUNT_USAGE` views (which
ACCOUNTADMIN has). The ARTWORK_TRANSFORMER role may need grants.

#### 6. codegen (dbt-labs/codegen)

**What it does:** Generates boilerplate: model SQL from a source, YAML stubs from
an existing model, base model code.

**Dabble:**
```bash
# Generate a YAML schema stub for an existing model:
dbt run-operation generate_model_yaml --args '{"model_names": ["stg_met__artworks"]}'

# Generate a base model from a source:
dbt run-operation generate_base_model --args '{"source_name": "met", "table_name": "raw_met_objects"}'
```

### Python Packages (for the diagnostic tool)

#### 1. sqlglot

**What it does:** Parses SQL into an AST. Trace column lineage through CTEs,
subqueries, JOINs. Transpile between dialects.

**Dabble:**
```python
import sqlglot
from sqlglot.lineage import lineage

# Trace where _LOADED_AT comes from in your compiled Gold SQL:
sql = open("artwork_pipeline/target/compiled/artwork_pipeline/models/marts/dim_artists.sql").read()
node = lineage("_LOADED_AT", sql, dialect="snowflake")
print(node.name)        # The column name
print(node.expression)  # The source expression (e.g. CURRENT_TIMESTAMP())
for dep in node.downstream:
    print(f"  depends on: {dep.name} from {dep.expression}")
```

#### 2. dbt-artifacts-parser

**What it does:** Loads manifest.json, run_results.json, catalog.json into typed
Python objects with proper dataclass fields.

**Dabble:**
```python
import json
from dbt_artifacts_parser.parser import parse_manifest, parse_run_results

with open("artwork_pipeline/target/manifest.json") as f:
    manifest = parse_manifest(json.load(f))

# Walk the DAG:
for node_id, node in manifest.nodes.items():
    if "dim_artists" in node_id:
        print(f"Node: {node_id}")
        print(f"  Depends on: {node.depends_on.nodes}")
        print(f"  Columns: {list(node.columns.keys())}")

# Check run results:
with open("artwork_pipeline/target/run_results.json") as f:
    results = parse_run_results(json.load(f))

for r in results.results:
    if r.status == "error":
        print(f"FAILED: {r.unique_id}")
        print(f"  Message: {r.message[:200]}")
```

#### 3. snowflake-connector-python

**What it does:** Direct Snowflake queries from Python. The tool uses this to
run DESCRIBE and SHOW PARAMETERS during tracing.

**Dabble:**
```python
import snowflake.connector

# Connect using the same creds as dbt:
conn = snowflake.connector.connect(
    account="OBANOYY-MK07348",
    authenticator="externalbrowser",  # or key-pair
    role="ARTWORK_TRANSFORMER",
    warehouse="COMPUTE_WH",
    database="ARTWORK_DB"
)
cur = conn.cursor()
cur.execute("DESCRIBE VIEW ARTWORK_DB.SILVER.STG_MET__ARTISTS")
for row in cur:
    print(f"  {row[0]:30s} {row[1]:30s}")  # column_name, type
cur.execute("SHOW PARAMETERS LIKE 'TIMESTAMP_TYPE_MAPPING' IN ACCOUNT")
print(cur.fetchone())
```
