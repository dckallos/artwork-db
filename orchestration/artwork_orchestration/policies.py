"""Shared Dagster policies and tuning knobs (source-agnostic).

Everything here is DERIVED from the validated engine config (``framework.yaml`` via
``config.FRAMEWORK``) -- there are no hardcoded constants and no museum-specific names.
This is the one place the factories reach for retry/timeout/rate behavior; tuning any of
it means editing YAML, not Python.
"""
from __future__ import annotations

from typing import Any, Dict

from dagster import Backoff, Jitter, RetryPolicy

from .config import FRAMEWORK

_defaults = FRAMEWORK.defaults

_BACKOFF = {"exponential": Backoff.EXPONENTIAL, "linear": Backoff.LINEAR}
_JITTER = {"plus_minus": Jitter.PLUS_MINUS, "none": None}

# Transient failures (API 5xx/timeouts, S3 hiccups) should not fail the whole run.
# Backoff with jitter avoids a retry thundering herd.
EXTRACTION_RETRY_POLICY = RetryPolicy(
    max_retries=_defaults.retry.max_retries,
    delay=_defaults.retry.delay_seconds,
    backoff=_BACKOFF.get(_defaults.retry.backoff, Backoff.EXPONENTIAL),
    jitter=_JITTER.get(_defaults.retry.jitter, Jitter.PLUS_MINUS),
)

# Per-run wall-clock ceilings (seconds), enforced by the daemon's run_monitoring when
# set as run tags (see factories/jobs.py) and mirrored onto op_tags. Chosen by step kind.
TIMEOUT_SNAPSHOT = _defaults.timeouts.for_kind("snapshot")
TIMEOUT_SEED = _defaults.timeouts.for_kind("seed")
TIMEOUT_ENRICH_BATCH = _defaults.timeouts.for_kind("batch")

# Bounded batching sizing (one materialization drains up to SIZE*MAX_BATCHES rows) for
# steps declared ``mode: batched``.
BATCH_SIZE = _defaults.batching.size
MAX_BATCHES = _defaults.batching.max_batches

# Aggregate request budget across ALL concurrent rate-limited workers, and the max
# workers run at once (mirror in dagster.yaml tag_concurrency_limits). Per-worker rps =
# budget / concurrency, so N workers never exceed one global cap.
API_RPS_BUDGET = _defaults.rate_limit.rps_budget
API_CONCURRENCY = _defaults.rate_limit.concurrency

# The run/op tag key the QueuedRunCoordinator gates on (dagster.yaml
# tag_concurrency_limits). The VALUE is per-source (spec.rate_limit_value) so each
# source's API gets its own concurrency budget.
RATE_LIMIT_TAG_KEY = FRAMEWORK.tags.rate_limit_key

# Op tag used by the daemon's run_monitoring to bound a single step's runtime.
MAX_RUNTIME_TAG_KEY = FRAMEWORK.tags.max_runtime_key


def timeout_tags(seconds: int) -> Dict[str, Any]:
    """Op tags mirroring the per-run wall-clock ceiling (see jobs run tags)."""
    return {MAX_RUNTIME_TAG_KEY: seconds}


def per_worker_rps() -> float:
    """Divide the global rps budget across the max concurrent rate-limited workers."""
    return _defaults.rate_limit.per_worker_rps()
