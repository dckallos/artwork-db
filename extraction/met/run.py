"""
Command-line entry point for the Met extractor pipeline.

The Snowflake-authoritative pipeline (Option B; the current architecture):
  snapshot    Load the full Met OpenAccess CSV into BRONZE.MET_CSV_SNAPSHOT
              (descriptive truth; no API calls). [Phase 1]
  seed        Insert 'pending' control rows for a bounded slice of the snapshot
              into BRONZE.MET_ENRICHMENT_CONTROL -- this is where the costly
              enrichment is bounded. [Phase 2]
  enrich      Drain BRONZE.MET_WORKLIST: lease-claim a batch, fetch image URLs from
              the Met API locally, assemble RAW_MET_OBJECTS server-side from the
              snapshot, and write outcomes back to the control table. [Phase 3]

Legacy SQLite path (kept for now; superseded by the above -- pending removal):
  bootstrap   Download the Met OpenAccess CSV and upsert it into SQLite.
  upload      Upload enriched SQLite rows (status=done, not yet uploaded) to Bronze.
  all         Run bootstrap, the legacy SQLite enrich, then upload in sequence.

  status      Print row counts by enrichment_status / upload state (SQLite).

Usage:
  python -m extraction.met.run <command> [-v]
"""
from __future__ import annotations

import argparse
import logging
import sys
from typing import Optional, Sequence

from .config import Config
from .control_enricher import enrich_from_control
from .control_seeder import seed_control
from .csv_bootstrap import bootstrap
from .db import connect, initialize_database
from .image_enricher import enrich as enrich_sqlite_legacy
from .snapshot_loader import load_snapshot
from .snowflake_uploader import upload


def _configure_logging(verbose: bool) -> None:
    """Configure the root logger for CLI output."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    # Suppress noisy third-party loggers at INFO (they emit connection/auth chatter).
    if not verbose:
        logging.getLogger("snowflake.connector").setLevel(logging.WARNING)
        logging.getLogger("botocore").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)


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

    p_snap = sub.add_parser(
        "snapshot",
        help="Load the Met CSV into BRONZE.MET_CSV_SNAPSHOT (Snowflake-authoritative).",
    )
    p_snap.add_argument(
        "--no-refresh", action="store_true",
        help="Reuse the existing local CSV instead of re-downloading.",
    )
    p_snap.add_argument(
        "--limit", type=int, default=None,
        help="Cap objects loaded (smoke testing). Default: full file.",
    )

    p_seed = sub.add_parser(
        "seed-control",
        help="Phase 2: seed MET_ENRICHMENT_CONTROL from a bounded snapshot slice.",
    )
    p_seed.add_argument(
        "--department", default=None,
        help="Exact Met department to seed (snapshot value). Default: all public-domain departments.",
    )
    p_seed.add_argument(
        "--include-non-public-domain", action="store_true",
        help="Drop the public-domain gate (seed the slice regardless of license).",
    )
    p_seed.add_argument(
        "--limit", type=int, default=None,
        help="Cap rows seeded (smoke testing). Default: the full slice.",
    )

    p_enrich_met = sub.add_parser(
        "enrich-met",
        help="Phase 3: claim a worklist batch, fetch images, assemble Bronze.",
    )
    p_enrich_met.add_argument(
        "--limit", type=int, default=None,
        help="Max objects to claim+enrich this run (batch bound). Default: whole worklist.",
    )
    p_enrich_met.add_argument(
        "--progress-every", type=int, default=100,
        help="Emit one progress line every N items processed. Default: 100.",
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
    elif args.command == "snapshot":
        load_snapshot(config, refresh_csv=not args.no_refresh, limit=args.limit)
    elif args.command == "seed-control":
        seed_control(
            config,
            department=args.department,
            public_domain_only=not args.include_non_public_domain,
            limit=args.limit,
        )
    elif args.command == "enrich-met":
        if args.limit is not None:
            # Bounded smoke: claim+enrich ONE batch of --limit objects, then stop.
            enrich_from_control(
                config, batch_size=args.limit, max_batches=1,
                progress_every=args.progress_every,
            )
        else:
            # Drain the whole worklist in default-size batches.
            enrich_from_control(config, progress_every=args.progress_every)
    elif args.command == "enrich":
        enrich_sqlite_legacy(config)
    elif args.command == "upload":
        upload(config)
    elif args.command == "status":
        _print_status(config)
    elif args.command == "all":
        bootstrap(config, refresh_csv=True)
        enrich_sqlite_legacy(config)
        upload(config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
