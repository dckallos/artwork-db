"""
Command-line entry point for the Met extractor pipeline.

Subcommands:
  bootstrap   Download the Met OpenAccess CSV and upsert it into SQLite.
  enrich      Call the Met API to fetch image URLs for every pending row.
  upload      Upload enriched rows (status=done, not yet uploaded) to Bronze.
  status      Print row counts by enrichment_status / upload state.
  all         Run bootstrap, enrich, then upload in sequence.

Usage:
  python -m extraction.met.run <command> [-v]
"""
from __future__ import annotations

import argparse
import logging
import sys
from typing import Optional, Sequence

from .config import Config
from .csv_bootstrap import bootstrap
from .db import connect, initialize_database
from .image_enricher import enrich
from .snowflake_uploader import upload


def _configure_logging(verbose: bool) -> None:
    """Configure the root logger for CLI output."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def _print_status(config: Config) -> None:
    """Print a small dashboard of current pipeline state."""
    initialize_database(config.sqlite_path)
    with connect(config.sqlite_path) as conn:
        print("met_artworks by enrichment_status:")
        cur = conn.execute(
            "SELECT enrichment_status, COUNT(*) FROM met_artworks "
            "GROUP BY enrichment_status ORDER BY enrichment_status"
        )
        for status, count in cur.fetchall():
            print(f"  {status:>10s}: {count:,}")

        cur = conn.execute(
            "SELECT "
            "  SUM(CASE WHEN enrichment_status='done' THEN 1 ELSE 0 END) AS done_total, "
            "  SUM(CASE WHEN enrichment_status='done' "
            "             AND bronze_uploaded_at IS NULL THEN 1 ELSE 0 END) AS not_uploaded, "
            "  SUM(CASE WHEN bronze_uploaded_at IS NOT NULL THEN 1 ELSE 0 END) AS uploaded "
            "FROM met_artworks"
        )
        row = cur.fetchone()
        done_total   = row[0] or 0
        not_uploaded = row[1] or 0
        uploaded     = row[2] or 0
        print("")
        print("upload state:")
        print(f"  done total  : {done_total:,}")
        print(f"  not uploaded: {not_uploaded:,}")
        print(f"  uploaded    : {uploaded:,}")

        cur = conn.execute(
            "SELECT run_id, phase, started_at, completed_at, status, "
            "records_processed "
            "FROM extraction_runs ORDER BY started_at DESC LIMIT 10"
        )
        print("")
        print("recent runs:")
        for run_id, phase, started, completed, status, records in cur.fetchall():
            print(f"  {run_id} {phase:<9s} {status:<8s} {records or 0:>8,}  "
                  f"{started} -> {completed or '...'}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="met-extractor",
        description="Met OpenAccess -> SQLite -> Snowflake Bronze loader.",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    p_boot = sub.add_parser("bootstrap", help="Download Met CSV and load into SQLite.")
    p_boot.add_argument(
        "--no-refresh", action="store_true",
        help="Reuse the existing local CSV instead of re-downloading.",
    )

    sub.add_parser("enrich", help="Fetch image URLs from the Met API for pending rows.")
    sub.add_parser("upload", help="Upload enriched rows to Snowflake Bronze.")
    sub.add_parser("status", help="Print pipeline status counts.")
    sub.add_parser("all", help="Run bootstrap -> enrich -> upload.")

    args = parser.parse_args(argv)
    _configure_logging(args.verbose)
    config = Config()
    config.ensure_paths()

    if args.command == "bootstrap":
        bootstrap(config, refresh_csv=not args.no_refresh)
    elif args.command == "enrich":
        enrich(config)
    elif args.command == "upload":
        upload(config)
    elif args.command == "status":
        _print_status(config)
    elif args.command == "all":
        bootstrap(config, refresh_csv=True)
        enrich(config)
        upload(config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
