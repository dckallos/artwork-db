"""
Command-line entry point for the AIC extractor pipeline.

Subcommands:
  snapshot    Download the S3 data dump, selectively extract Tier 1 entities,
              transform to NDJSON, MERGE into Bronze, soft-delete deaccessions.
  delta       (Not yet implemented) Query the API for records changed since the
              watermark and MERGE into RAW_AIC_ARTWORKS.
  status      Print current row counts, deaccession counts, and last batch info.

Usage:
  python -m extraction.aic.run <command> [-v]
"""
from __future__ import annotations

import argparse
import logging
import sys
from typing import Optional, Sequence

from extraction.met.snowflake_uploader import _snowflake_connect

from .config import Config
from .loader import run_snapshot


def _configure_logging(verbose: bool) -> None:
    """Configure the root logger for CLI output."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    if not verbose:
        logging.getLogger("snowflake.connector").setLevel(logging.WARNING)
        logging.getLogger("botocore").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)


def _print_status(config: Config) -> None:
    """Print a dashboard of current AIC pipeline state from Snowflake."""
    conn = _snowflake_connect(config)
    try:
        db_schema = f"{config.snowflake_database}.{config.snowflake_schema}"
        cur = conn.cursor()

        # Artworks counts
        cur.execute(f"SELECT COUNT(*) FROM {db_schema}.RAW_AIC_ARTWORKS")
        artworks_total = cur.fetchone()[0]

        cur.execute(
            f"SELECT COUNT(*) FROM {db_schema}.RAW_AIC_ARTWORKS "
            f"WHERE _IS_DELETED = TRUE"
        )
        artworks_deleted = cur.fetchone()[0]

        cur.execute(
            f"SELECT _BATCH_ID, COUNT(*) AS CNT, MIN(_EXTRACTED_AT) AS LOADED_AT "
            f"FROM {db_schema}.RAW_AIC_ARTWORKS "
            f"GROUP BY _BATCH_ID ORDER BY LOADED_AT DESC LIMIT 3"
        )
        artworks_batches = cur.fetchall()

        # Agents counts
        cur.execute(f"SELECT COUNT(*) FROM {db_schema}.RAW_AIC_AGENTS")
        agents_total = cur.fetchone()[0]

        cur.execute(
            f"SELECT _BATCH_ID, COUNT(*) AS CNT, MIN(_EXTRACTED_AT) AS LOADED_AT "
            f"FROM {db_schema}.RAW_AIC_AGENTS "
            f"GROUP BY _BATCH_ID ORDER BY LOADED_AT DESC LIMIT 3"
        )
        agents_batches = cur.fetchall()

        # Watermark
        cur.execute(
            f"SELECT ENTITY_TYPE, LAST_SOURCE_UPDATED_AT, LAST_BATCH_ID, UPDATED_AT "
            f"FROM {db_schema}.AIC_LOAD_WATERMARK "
            f"ORDER BY ENTITY_TYPE"
        )
        watermarks = cur.fetchall()

        # Print
        print("=== AIC Pipeline Status ===")
        print("")
        print(f"RAW_AIC_ARTWORKS: {artworks_total:,} total, {artworks_deleted:,} soft-deleted")
        if artworks_batches:
            print("  Recent batches:")
            for batch_id, cnt, loaded_at in artworks_batches:
                print(f"    {batch_id}  {cnt:>8,} rows  loaded {loaded_at}")
        print("")
        print(f"RAW_AIC_AGENTS: {agents_total:,} total")
        if agents_batches:
            print("  Recent batches:")
            for batch_id, cnt, loaded_at in agents_batches:
                print(f"    {batch_id}  {cnt:>8,} rows  loaded {loaded_at}")
        print("")
        if watermarks:
            print("AIC_LOAD_WATERMARK:")
            for entity, last_ts, last_batch, updated in watermarks:
                print(f"  {entity}: last_updated={last_ts}, batch={last_batch}, at={updated}")
        else:
            print("AIC_LOAD_WATERMARK: (empty -- no delta runs yet)")

    finally:
        conn.close()


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="aic-extractor",
        description="AIC data dump -> Snowflake Bronze loader.",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    # snapshot
    p_snap = sub.add_parser(
        "snapshot",
        help="Download the AIC dump, extract, transform, MERGE into Bronze.",
    )
    p_snap.add_argument(
        "--no-refresh", action="store_true",
        help="Reuse the cached tar.bz2 instead of re-downloading.",
    )
    p_snap.add_argument(
        "--limit", type=int, default=None,
        help="Cap records per entity (smoke testing). Default: full dump.",
    )
    p_snap.add_argument(
        "--entities", type=str, default=None,
        help="Comma-separated entity list to load (default: artworks,agents).",
    )

    # delta (stub)
    sub.add_parser(
        "delta",
        help="(Not yet implemented) Incremental API delta load.",
    )

    # status
    sub.add_parser(
        "status",
        help="Print row counts, deaccession counts, and last batch info.",
    )

    args = parser.parse_args(argv)
    _configure_logging(args.verbose)
    config = Config()
    config.ensure_paths()

    if args.command == "snapshot":
        entities = None
        if args.entities:
            entities = [e.strip() for e in args.entities.split(",")]
        run_snapshot(
            config,
            refresh=not args.no_refresh,
            limit=args.limit,
            entities=entities,
        )
    elif args.command == "delta":
        print("Not yet implemented. See the design doc (Section 7) for the planned delta path.")
        return 1
    elif args.command == "status":
        _print_status(config)

    return 0


if __name__ == "__main__":
    sys.exit(main())
