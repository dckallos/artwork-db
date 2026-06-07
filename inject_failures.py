#!/usr/bin/env python3
"""
inject_failures.py -- Inject and discard controlled test failures for dbt-diagnostics fixture generation.

This script modifies staging model SQL to introduce realistic Snowflake errors,
then reverts them. Designed to be run from the repo root (where artwork_pipeline/ lives).

Usage:
    python inject_failures.py --change 1       # Inject failure scenario 1
    python inject_failures.py --discard-change 1  # Revert failure scenario 1
    python inject_failures.py --list           # Show all scenarios and state

After injecting, run:
    dbt run --select stg_met__artworks    (or whichever model the scenario targets)
    dbt test --select tag:staging         (to see test-level failures)

After collecting target/run_results.json, discard:
    python inject_failures.py --discard-change N

Recommended dbt commands to run ONLY the working tests:
    dbt test --select tag:staging              # All staging tests (29 pass, 2 warn)
    dbt test --select tag:met                  # Same set (met sources + staging models)
    dbt test --select source:met               # Source-level tests only
"""

import argparse
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Configuration: paths relative to repo root
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent / "artwork_pipeline"
if not PROJECT_ROOT.exists():
    PROJECT_ROOT = Path(__file__).parent
    if not (PROJECT_ROOT / "dbt_project.yml").exists():
        PROJECT_ROOT = Path(__file__).parent / "artwork_pipeline"

STAGING_DIR = PROJECT_ROOT / "models" / "staging" / "met"
SOURCES_FILE = STAGING_DIR / "_met__sources.yml"
MODELS_FILE = STAGING_DIR / "_met__models.yml"


# ---------------------------------------------------------------------------
# Failure scenarios (1-12)
# ---------------------------------------------------------------------------
# Each scenario:
#   file:         which file to modify
#   original:     exact string to find (must be unique in the file)
#   replacement:  what replaces it (introduces the error)
#   description:  what error this causes
#   error_code:   expected Snowflake error code / dbt error class
#   trigger_cmd:  the dbt command to run to actually produce the failure
# ---------------------------------------------------------------------------

SCENARIOS = {
    # =======================================================================
    # COMPILATION ERRORS (fail before SQL reaches Snowflake)
    # =======================================================================
    1: {
        "file": STAGING_DIR / "stg_met__artworks.sql",
        "original": "FROM {{ source('met', 'raw_met_objects') }}",
        "replacement": "FROM {{ source('met', 'table_that_does_not_exist') }}",
        "description": (
            "Compilation error: source not found. dbt fails at compile time "
            "because 'table_that_does_not_exist' is not declared in _met__sources.yml."
        ),
        "error_code": "compilation_error (source not found)",
        "trigger_cmd": "dbt compile --select stg_met__artworks",
    },
    2: {
        "file": STAGING_DIR / "stg_met__artists.sql",
        "original": "FROM {{ source('met', 'raw_met_objects') }}",
        "replacement": "FROM {{ ref('model_that_does_not_exist') }}",
        "description": (
            "Compilation error: ref target not found. dbt fails at compile time "
            "because 'model_that_does_not_exist' is not in the project."
        ),
        "error_code": "compilation_error (model not found)",
        "trigger_cmd": "dbt compile --select stg_met__artists",
    },
    3: {
        "file": STAGING_DIR / "stg_met__images.sql",
        "original": "LATERAL FLATTEN(input => s.api_images:additional_images) f",
        "replacement": "LATERAL FLATTEN(input => s.api_images:additional_images  f",
        "description": (
            "Compilation/SQL syntax error: missing closing parenthesis on FLATTEN. "
            "dbt compiles the SQL successfully (no Jinja error), but Snowflake "
            "rejects it with SQL compilation error 001003 (syntax error)."
        ),
        "error_code": "001003 (SQL compilation syntax error)",
        "trigger_cmd": "dbt run --select stg_met__images",
    },

    # =======================================================================
    # RUNTIME DATA ERRORS (SQL compiles, Snowflake fails during execution)
    # =======================================================================
    4: {
        "file": STAGING_DIR / "stg_met__images.sql",
        "original": "1                                                    AS ordinal_position,",
        "replacement": "1 / 0                                                AS ordinal_position,",
        "description": (
            "Division by zero (Snowflake 100035). The primary_images CTE evaluates "
            "a constant 1/0 expression. Snowflake rejects it at runtime."
        ),
        "error_code": "100035 (division by zero)",
        "trigger_cmd": "dbt run --select stg_met__images",
    },
    5: {
        "file": STAGING_DIR / "stg_met__artworks.sql",
        "original": "raw_payload:csv:object_begin_date::INT           AS object_begin_date,",
        "replacement": "raw_payload:csv:title::NUMBER(5,0)               AS object_begin_date,",
        "description": (
            "Numeric overflow (Snowflake 100132). Casts the title string (e.g. "
            "'Marble Portrait Bust') to NUMBER(5,0). Overflows immediately because "
            "the string is not a number, let alone one that fits in 5 digits."
        ),
        "error_code": "100132 (numeric value out of range)",
        "trigger_cmd": "dbt run --select stg_met__artworks",
    },
    6: {
        "file": STAGING_DIR / "stg_met__artworks.sql",
        "original": "raw_payload:csv:department::STRING               AS department,",
        "replacement": "raw_payload:csv:department::VARCHAR(2)            AS department,",
        "description": (
            "String too long (Snowflake 100078). Casts department names like "
            "'European Paintings' into VARCHAR(2). Overflows on any real data."
        ),
        "error_code": "100078 (string too long)",
        "trigger_cmd": "dbt run --select stg_met__artworks",
    },

    # =======================================================================
    # OBJECT / PERMISSION ERRORS (runtime, infrastructure mismatch)
    # =======================================================================
    7: {
        "file": STAGING_DIR / "stg_met__artworks.sql",
        "original": "FROM {{ source('met', 'raw_met_objects') }}",
        "replacement": "FROM ARTWORK_DB.BRONZE.DOES_NOT_EXIST_TABLE",
        "description": (
            "Object does not exist (Snowflake 002003). Hardcodes a non-existent "
            "table name (bypassing the source() macro). Snowflake fails at runtime "
            "because the object doesn't exist."
        ),
        "error_code": "002003 (object does not exist)",
        "trigger_cmd": "dbt run --select stg_met__artworks",
    },
    8: {
        "file": STAGING_DIR / "stg_met__enrichment_status.sql",
        "original": "FROM {{ source('met', 'met_enrichment_control') }}",
        "replacement": "FROM ARTWORK_DB.GOLD.MET_ENRICHMENT_CONTROL",
        "description": (
            "Insufficient privileges (Snowflake 003001). References the control "
            "table in the GOLD schema where the transformer role likely lacks SELECT. "
            "If the object happens to not exist in GOLD, you'll get 002003 instead -- "
            "both are useful fixtures."
        ),
        "error_code": "003001 or 002003 (privileges or missing object)",
        "trigger_cmd": "dbt run --select stg_met__enrichment_status",
    },

    # =======================================================================
    # SCHEMA DRIFT / INVALID IDENTIFIER (runtime, column-level)
    # =======================================================================
    9: {
        "file": STAGING_DIR / "stg_met__artworks.sql",
        "original": "raw_payload:csv:title::STRING                    AS title,",
        "replacement": "NONEXISTENT_TOP_LEVEL_COLUMN::STRING             AS title,",
        "description": (
            "Invalid identifier (Snowflake 000904). References a column name that "
            "does not exist on RAW_MET_OBJECTS (not a VARIANT path, an actual column "
            "reference). Snowflake fails with 'invalid identifier'."
        ),
        "error_code": "000904 (invalid identifier)",
        "trigger_cmd": "dbt run --select stg_met__artworks",
    },
    10: {
        "file": STAGING_DIR / "stg_met__artists.sql",
        "original": "TRIM(sn.value::STRING)                                              AS artist_display_name,",
        "replacement": "TRIM(sn.nonexistent_field::STRING)                                  AS artist_display_name,",
        "description": (
            "Invalid identifier in LATERAL output (Snowflake 000904). "
            "SPLIT_TO_TABLE produces (SEQ, INDEX, VALUE) but we reference "
            "'nonexistent_field'. Snowflake rejects it as an invalid identifier."
        ),
        "error_code": "000904 (invalid identifier on lateral output)",
        "trigger_cmd": "dbt run --select stg_met__artists",
    },

    # =======================================================================
    # CONTRACT / TYPE MISMATCH (downstream test or contract enforcement)
    # =======================================================================
    11: {
        "file": STAGING_DIR / "stg_met__artworks.sql",
        "original": "raw_payload:csv:title::STRING                    AS title,",
        "replacement": "raw_payload:csv:title::STRING                    AS title,\n        raw_payload:csv:NONEXISTENT_FIELD_XYZ::STRING   AS ghost_column,",
        "description": (
            "Extra column in projection. Adds a phantom column that makes the view "
            "produce one more column than expected. If dim_artworks has a contract, "
            "this causes a contract violation. Even without a contract, downstream "
            "SELECT * will silently pass through an unexpected column."
        ),
        "error_code": "contract_violation (extra column in definition)",
        "trigger_cmd": "dbt run --select stg_met__artworks+",
    },
    12: {
        "file": STAGING_DIR / "stg_met__artworks.sql",
        "original": "object_id,",
        "replacement": "-- object_id,  -- REMOVED for failure injection",
        "description": (
            "Missing required column (drops object_id from the CTE). "
            "Downstream models and tests that reference object_id will fail with "
            "Snowflake 000904 (invalid identifier). This simulates an upstream "
            "schema change that removes a column depended on by the whole DAG."
        ),
        "error_code": "000904 (invalid identifier -- upstream schema change)",
        "trigger_cmd": "dbt run --select stg_met__artworks",
    },
}


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def inject(scenario_id: int) -> None:
    """Inject a failure into the model file."""
    scenario = SCENARIOS[scenario_id]
    filepath = scenario["file"]

    if not filepath.exists():
        print(f"ERROR: File not found: {filepath}", file=sys.stderr)
        print(f"  Are you running from the repo root?", file=sys.stderr)
        sys.exit(1)

    content = filepath.read_text()

    if scenario["original"] not in content:
        if scenario["replacement"] in content:
            print(f"Scenario {scenario_id} is ALREADY injected. Nothing to do.")
            return
        print(f"ERROR: Could not find the target string in {filepath.name}.", file=sys.stderr)
        print(f"  Another scenario may conflict (scenarios that modify the same file", file=sys.stderr)
        print(f"  cannot both be active). Discard the other one first.", file=sys.stderr)
        sys.exit(1)

    new_content = content.replace(scenario["original"], scenario["replacement"], 1)
    filepath.write_text(new_content)

    print(f"INJECTED scenario {scenario_id} into {filepath.name}")
    print(f"  Error type:  {scenario['error_code']}")
    print(f"  Description: {scenario['description']}")
    print()
    print(f"  Trigger with: {scenario['trigger_cmd']}")
    print()
    print("After collecting target/run_results.json:")
    print(f"  python {Path(__file__).name} --discard-change {scenario_id}")


def discard(scenario_id: int) -> None:
    """Revert an injected failure."""
    scenario = SCENARIOS[scenario_id]
    filepath = scenario["file"]

    if not filepath.exists():
        print(f"ERROR: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    content = filepath.read_text()

    if scenario["replacement"] not in content:
        if scenario["original"] in content:
            print(f"Scenario {scenario_id} is NOT injected (already clean). Nothing to do.")
            return
        print(f"ERROR: Neither original nor replacement found in {filepath.name}.", file=sys.stderr)
        print(f"  The file may have been modified further. Restore with git checkout.", file=sys.stderr)
        sys.exit(1)

    new_content = content.replace(scenario["replacement"], scenario["original"], 1)
    filepath.write_text(new_content)

    print(f"REVERTED scenario {scenario_id} in {filepath.name}")
    print(f"  File restored to working state.")


def list_scenarios() -> None:
    """Print all available scenarios."""
    print("Available failure scenarios:")
    print("=" * 78)

    # Group by category
    categories = {
        "COMPILATION ERRORS (fail before SQL reaches Snowflake)": [1, 2, 3],
        "RUNTIME DATA ERRORS (SQL compiles, Snowflake rejects data)": [4, 5, 6],
        "OBJECT / PERMISSION ERRORS (infrastructure mismatch)": [7, 8],
        "SCHEMA DRIFT / INVALID IDENTIFIER (column-level)": [9, 10],
        "CONTRACT / TYPE MISMATCH (downstream enforcement)": [11, 12],
    }

    for category, ids in categories.items():
        print(f"\n  --- {category} ---")
        for sid in ids:
            scenario = SCENARIOS[sid]
            status = "INJECTED" if _is_injected(sid) else "clean"
            print(f"\n  [{sid:2d}] ({status}) {scenario['error_code']}")
            print(f"       File:    {scenario['file'].name}")
            print(f"       Trigger: {scenario['trigger_cmd']}")
            # Wrap description to ~70 chars
            desc = scenario["description"]
            words = desc.split()
            line = "       "
            for word in words:
                if len(line) + len(word) + 1 > 78:
                    print(line)
                    line = "       " + word
                else:
                    line += " " + word if line.strip() else "       " + word
            if line.strip():
                print(line)

    print()
    print("=" * 78)
    print()
    print("IMPORTANT: Scenarios that target the same file CONFLICT with each other.")
    print("Only inject ONE scenario per file at a time. Discard before switching.")
    print()
    print("Conflict groups (only one active at a time):")
    print("  stg_met__artworks.sql:          1, 2, 5, 6, 7, 9, 11, 12")
    print("  stg_met__images.sql:            3, 4")
    print("  stg_met__artists.sql:           2 (conflicts w/ artworks: shares source line)")
    print("                                  10")
    print("  stg_met__enrichment_status.sql: 8")
    print()
    print("Working test commands (no injection needed):")
    print("  dbt test --select tag:staging     # 29 pass + 2 warn")
    print("  dbt test --select tag:met         # same set")
    print("  dbt test --select source:met      # source-level only")


def _is_injected(scenario_id: int) -> bool:
    """Check if a scenario is currently injected."""
    scenario = SCENARIOS[scenario_id]
    filepath = scenario["file"]
    if not filepath.exists():
        return False
    content = filepath.read_text()
    return scenario["replacement"] in content


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Inject/discard controlled dbt test failures for fixture generation.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python inject_failures.py --list
  python inject_failures.py --change 4
  cd artwork_pipeline && dbt run --select stg_met__images
  cp target/run_results.json ../dbt_diagnostics/fixtures/real_div_by_zero.json
  cd .. && python inject_failures.py --discard-change 4
        """,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--change", type=int, choices=sorted(SCENARIOS.keys()), metavar="N",
        help=f"Inject failure scenario N (1-{max(SCENARIOS.keys())})",
    )
    group.add_argument(
        "--discard-change", type=int, choices=sorted(SCENARIOS.keys()), metavar="N",
        help=f"Revert failure scenario N (1-{max(SCENARIOS.keys())})",
    )
    group.add_argument(
        "--list", action="store_true",
        help="List all available scenarios and their current state",
    )

    args = parser.parse_args()

    if args.list:
        list_scenarios()
    elif args.change:
        inject(args.change)
    elif args.discard_change:
        discard(args.discard_change)


if __name__ == "__main__":
    main()
