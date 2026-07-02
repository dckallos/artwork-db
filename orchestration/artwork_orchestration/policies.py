"""Shared Dagster policies and tuning knobs (source-agnostic).

These were previously inlined in ``assets_extraction.py``. Centralizing them keeps
the per-source spec files pure data and gives one place to tune retry/timeout/rate
behavior for every museum at once.
"""
from __future__ import annotations

import os
from typing import Any, Dict

from dagster import Backoff, Jitter, RetryPolicy

# Transient failures (API 5xx/timeouts, S3 hiccups) should not fail the whole run.
# Exponential backoff with jitter avoids a retry thundering herd.
EXTRACTION_RETRY_POLICY = RetryPolicy(
    max_retries=2, delay=30, backoff=Backoff.EXPONENTIAL, jitter=Jitter.PLUS_MINUS
)

# Per-run wall-clock ceilings (seconds), enforced by the daemon's run_monitoring
# when set as run tags (see factories/jobs.py) and mirrored onto op_tags.
TIMEOUT_SNAPSHOT = 60 * 30      # 30 min: CSV/S3 download + COPY/MERGE.
TIMEOUT_SEED = 60 * 15          # 15 min: one MERGE / a verification query, fast.
TIMEOUT_ENRICH_BATCH = 60 * 90  # 90 min: a bounded per-partition enrichment slice.

# Bounded enrichment sizing (one materialization claims up to SIZE*MAX_BATCHES objects).
MET_ENRICH_BATCH_SIZE = int(os.getenv("MET_ENRICH_BATCH_SIZE", "2000"))
MET_ENRICH_MAX_BATCHES = int(os.getenv("MET_ENRICH_MAX_BATCHES", "1"))

# Aggregate request budget across ALL concurrent rate-limited workers, and the max
# partitions we let run at once (mirror in dagster.yaml tag_concurrency_limits).
# Per-worker rps = budget / concurrency, so N workers never exceed one global cap.
MET_API_RPS_BUDGET = float(os.getenv("MET_API_RPS_BUDGET", "30"))
MET_ENRICH_CONCURRENCY = int(os.getenv("MET_ENRICH_CONCURRENCY", "3"))

# The run/op tag key the QueuedRunCoordinator gates on (dagster.yaml
# tag_concurrency_limits). The VALUE is per-source (spec.rate_limit_value) so each
# museum's API gets its own concurrency budget.
RATE_LIMIT_TAG_KEY = "artwork/rate_limited_api"

# Op tag used by the daemon's run_monitoring to bound a single step's runtime.
MAX_RUNTIME_TAG_KEY = "dagster/max_runtime"


def timeout_tags(seconds: int) -> Dict[str, Any]:
    """Op tags mirroring the per-run wall-clock ceiling (see jobs run tags)."""
    return {MAX_RUNTIME_TAG_KEY: seconds}


def per_worker_rps() -> float:
    """Divide the global rps budget across the max concurrent rate-limited workers."""
    return max(MET_API_RPS_BUDGET / max(MET_ENRICH_CONCURRENCY, 1), 1.0)
