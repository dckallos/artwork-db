"""
Asynchronously fetch image URLs from the Met API for every pending row.

Workflow for each met_artworks row with enrichment_status in ('pending', 'error'):
  1. GET /public/collection/v1/objects/{object_id}
  2. If response has primaryImage, store it (plus primaryImageSmall and
     additionalImages); mark status='done'.
  3. If response has no primaryImage or returns 404, mark status='no_image'.
  4. On unrecoverable error, mark status='error' with the error message.

The enricher is fully resumable: re-running picks up where it left off because
only rows with status in ('pending', 'error') are queried. The 'error' state
is retried automatically so transient failures self-heal across runs.

Rate limiting (informed by the owner's prior production Met OA project):
  - The Met returns BOTH 429 AND 403 as throttle signals. Treat them identically.
  - Respect the `Retry-After` response header (seconds OR HTTP-date format) when
    present; otherwise fall back to base * 2^attempt with jitter.
  - Adaptive RPS: after 3 consecutive throttles the limiter drops RPS 30 percent;
    on every success it edges back up 5 percent toward the configured ceiling.
  - Bounded semaphore caps concurrent in-flight requests.
  - 403/410 are NOT terminal: 403 is a throttle signal in disguise, 410 (Gone)
    is rare and rolled into the retry path so a transient masquerade does not
    look permanent. After exhausting retries, both fall through to terminal
    'error' with the last HTTP status preserved.
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

from .config import Config
from .db import connect, initialize_database, load_sql

logger = logging.getLogger(__name__)

# Multi-column UPDATE lives in extraction/met/sql/update_enrichment_done.sql.
# The smaller no_image / error UPDATEs are kept inline just below.
UPDATE_DONE_SQL = load_sql("update_enrichment_done.sql")

UPDATE_NO_IMAGE_SQL = """
UPDATE met_artworks
SET primary_image_url       = NULL,
    primary_image_small_url = NULL,
    additional_image_urls   = NULL,
    enrichment_status       = 'no_image',
    enrichment_error        = NULL,
    enriched_at             = :enriched_at
WHERE object_id = :object_id;
"""

UPDATE_ERROR_SQL = """
UPDATE met_artworks
SET enrichment_status = 'error',
    enrichment_error  = :enrichment_error,
    enriched_at       = :enriched_at
WHERE object_id = :object_id;
"""


class _RateLimiter:
    """Adaptive token-bucket-style limiter.

    Enforces a minimum interval between successive acquisitions, AND adapts the
    target RPS in response to throttle signals (a la the owner's prior project):
        - note_throttle(): three throttles in a window -> drop RPS by 30 percent.
        - cool_up():       on each success -> nudge RPS up 5 percent toward the
                           configured ceiling.
    The min/max guards keep the limiter from collapsing or runaway-tightening.
    """

    def __init__(
        self,
        requests_per_second: float,
        min_rps: float = 1.0,
        max_rps: Optional[float] = None,
    ) -> None:
        rps = max(float(requests_per_second), float(min_rps))
        self._rps = rps
        self._min_rps = float(min_rps)
        # Default ceiling is the configured RPS (no auto-overshoot above the
        # owner's chosen budget) but never lower than 5.0 so cool_up has room.
        self._max_rps = float(max_rps) if max_rps is not None else max(rps, 5.0)
        self._lock = asyncio.Lock()
        self._next_allowed = 0.0
        self._throttle_burst = 0
        # P-T2: per-run counters surfaced in the per-batch log so the throttle
        # picture is visible without a re-query of the control table. These are
        # read after a batch finishes; they aggregate every retry within
        # _fetch_one across every worker for the limiter's lifetime.
        self.throttle_403 = 0
        self.throttle_429 = 0
        self.throttle_other = 0   # 410 / 5xx that hit the same backoff path
        self.backoff_seconds = 0.0

    @property
    def rps(self) -> float:
        return self._rps

    async def acquire(self) -> None:
        """Block until it is safe to issue another request."""
        async with self._lock:
            min_interval = 1.0 / self._rps if self._rps > 0 else 0.1
            now = time.monotonic()
            wait = self._next_allowed - now
            if wait > 0:
                await asyncio.sleep(wait)
                now = time.monotonic()
            self._next_allowed = now + min_interval

    def note_throttle(self) -> None:
        """Throttle observed; after 3 in a row, decay RPS by 30 percent."""
        self._throttle_burst += 1
        if self._throttle_burst >= 3:
            self._rps = max(self._min_rps, self._rps * 0.7)
            self._throttle_burst = 0
            logger.info("Adaptive RPS dropped to %.2f after throttle burst", self._rps)

    def cool_up(self) -> None:
        """Successful response; edge RPS back up toward the ceiling."""
        # Reset burst counter so isolated 403s don't compound across long runs.
        self._throttle_burst = 0
        new = min(self._max_rps, self._rps * 1.05)
        if new > self._rps:
            self._rps = new


def _retry_after_seconds(resp: aiohttp.ClientResponse) -> Optional[float]:
    """Parse the `Retry-After` response header into a non-negative seconds delay.

    The header may be either:
      - a delta-seconds integer/float (e.g. "120"), or
      - an HTTP-date (RFC 7231 section 7.1.3, e.g. "Wed, 21 Oct 2026 07:28:00 GMT").
    Returns None if absent or malformed; callers fall back to exponential backoff.
    """
    raw = resp.headers.get("Retry-After")
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        pass
    try:
        when = parsedate_to_datetime(raw)
        if when is None:
            return None
        delta = (when - datetime.now(timezone.utc)).total_seconds()
        return max(0.0, delta)
    except (TypeError, ValueError):
        return None


def _pending_object_ids(conn: sqlite3.Connection) -> List[int]:
    """Return all object_ids whose enrichment_status is 'pending' or 'error'."""
    cur = conn.execute(
        "SELECT object_id FROM met_artworks "
        "WHERE enrichment_status IN ('pending', 'error') "
        "ORDER BY object_id"
    )
    return [r[0] for r in cur.fetchall()]


async def _fetch_one(
    session: aiohttp.ClientSession,
    rate_limiter: _RateLimiter,
    api_base: str,
    object_id: int,
    max_retries: int,
) -> Tuple[int, str, Optional[Dict[str, Any]], Optional[str]]:
    """Fetch a single Met object record with adaptive throttle handling.

    Returns: (object_id, status, payload_or_None, error_message_or_None)
    where status is one of: 'done', 'no_image', 'error'.

    Throttle policy (informed by the owner's prior project):
      - 403 and 429 are BOTH treated as rate-limit signals. The Met API returns
        403 as a soft-throttle in addition to 429; treating 403 as terminal would
        silently bury legitimate work. Both honor Retry-After and decay RPS.
      - 5xx (500/502/503/504) follow the same retry path.
      - 410 (Gone) is included in the retry set defensively in case it ever
        appears as a transient masquerade; if it persists across all attempts,
        the final fall-through marks it terminal 'error'.
      - Other 4xx (400/401/etc.) remain terminal -- those signal a bad request,
        not a rate limit, and retrying does not help.
    """
    url = f"{api_base}/objects/{object_id}"
    last_error: Optional[str] = None
    base_backoff = 0.8  # seconds; matches the prior project

    for attempt in range(1, max_retries + 1):
        await rate_limiter.acquire()
        try:
            async with session.get(url) as resp:
                status = resp.status
                # 404 = does not exist; terminal no_image.
                if status == 404:
                    rate_limiter.cool_up()
                    return object_id, "no_image", None, None

                # Throttle / transient: 403 (Met returns this as soft-throttle),
                # 410 (defensive; usually Gone but treated as transient first),
                # 429 (rate limit), 5xx (transient server). All retry with
                # backoff that prefers Retry-After when the server suggests one.
                if status in (403, 410, 429, 500, 502, 503, 504):
                    last_error = f"HTTP {status}"
                    delay = _retry_after_seconds(resp)
                    if delay is None:
                        delay = base_backoff * (2 ** (attempt - 1))
                    delay += random.uniform(0, 0.5)  # jitter
                    # P-T2: surface the throttle picture in the per-batch log.
                    if status == 403:
                        rate_limiter.throttle_403 += 1
                    elif status == 429:
                        rate_limiter.throttle_429 += 1
                    else:
                        rate_limiter.throttle_other += 1
                    rate_limiter.backoff_seconds += delay
                    rate_limiter.note_throttle()
                    await asyncio.sleep(delay)
                    continue

                # Other 4xx: terminal client error.
                if status >= 400:
                    text = await resp.text()
                    return object_id, "error", None, f"HTTP {status}: {text[:200]}"

                # 2xx: parse and return.
                payload = await resp.json(content_type=None)
                primary = (payload or {}).get("primaryImage") or ""
                rate_limiter.cool_up()
                if not primary:
                    return object_id, "no_image", None, None
                return object_id, "done", payload, None

        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            delay = base_backoff * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
            await asyncio.sleep(delay)

    # All retries exhausted.
    return object_id, "error", None, last_error or "max retries exceeded"


def _apply_result(
    conn: sqlite3.Connection,
    object_id: int,
    status: str,
    payload: Optional[Dict[str, Any]],
    error_message: Optional[str],
) -> None:
    """Persist a single API result back to SQLite."""
    now_iso = datetime.now(timezone.utc).isoformat()
    if status == "done" and payload is not None:
        additional = payload.get("additionalImages") or []
        conn.execute(
            UPDATE_DONE_SQL,
            {
                "object_id":               object_id,
                "primary_image_url":       payload.get("primaryImage") or None,
                "primary_image_small_url": payload.get("primaryImageSmall") or None,
                "additional_image_urls":   json.dumps(additional) if additional else None,
                "enriched_at":             now_iso,
            },
        )
    elif status == "no_image":
        conn.execute(
            UPDATE_NO_IMAGE_SQL,
            {"object_id": object_id, "enriched_at": now_iso},
        )
    else:
        conn.execute(
            UPDATE_ERROR_SQL,
            {
                "object_id":        object_id,
                "enrichment_error": (error_message or "unknown")[:500],
                "enriched_at":      now_iso,
            },
        )


async def _enrich_async(
    config: Config,
    object_ids: List[int],
    progress_every: int = 500,
) -> Dict[str, int]:
    """Drive the async fetch loop and persist results to SQLite."""
    counters = {"done": 0, "no_image": 0, "error": 0}
    rate_limiter = _RateLimiter(config.api_requests_per_second)
    semaphore = asyncio.Semaphore(config.api_max_concurrency)
    timeout = aiohttp.ClientTimeout(
        total=None, connect=15, sock_read=config.api_request_timeout_seconds,
    )
    headers = {
        "User-Agent": config.api_user_agent,
        "Accept":     "application/json",
    }

    completed = 0
    write_lock = asyncio.Lock()  # serializes SQLite writes from coroutines

    with connect(config.sqlite_path) as conn:
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:

            async def worker(oid: int) -> None:
                """Fetch one object and persist the result."""
                nonlocal completed
                async with semaphore:
                    result = await _fetch_one(
                        session, rate_limiter,
                        config.api_base, oid, config.api_max_retries,
                    )
                async with write_lock:
                    _apply_result(conn, *result)
                    counters[result[1]] += 1
                    completed += 1
                    if completed % progress_every == 0:
                        conn.commit()
                        logger.info(
                            "Enrich progress: %s/%s (done=%s no_image=%s error=%s)",
                            f"{completed:,}", f"{len(object_ids):,}",
                            counters["done"], counters["no_image"], counters["error"],
                        )

            await asyncio.gather(*(worker(oid) for oid in object_ids))

        conn.commit()

    return counters


def enrich(config: Config) -> Dict[str, int]:
    """Enrich every pending/error row. Returns final status counts."""
    initialize_database(config.sqlite_path)

    with connect(config.sqlite_path) as conn:
        run_id = uuid.uuid4().hex[:12]
        conn.execute(
            "INSERT INTO extraction_runs (run_id, phase, started_at, status) "
            "VALUES (?, 'enrich', ?, 'running')",
            (run_id, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        pending = _pending_object_ids(conn)

    if not pending:
        logger.info("No pending rows to enrich.")
        with connect(config.sqlite_path) as conn:
            conn.execute(
                "UPDATE extraction_runs SET completed_at=?, status='success', "
                "records_processed=0 WHERE run_id=?",
                (datetime.now(timezone.utc).isoformat(), run_id),
            )
            conn.commit()
        return {"done": 0, "no_image": 0, "error": 0}

    logger.info("Enriching %s rows from the Met API...", f"{len(pending):,}")
    counters: Dict[str, int] = {"done": 0, "no_image": 0, "error": 0}
    status = "success"
    notes: Optional[str] = None
    try:
        counters = asyncio.run(_enrich_async(config, pending))
        notes = json.dumps(counters)
    except Exception as exc:
        status = "failed"
        notes = str(exc)
        raise
    finally:
        with connect(config.sqlite_path) as conn:
            conn.execute(
                "UPDATE extraction_runs SET completed_at=?, status=?, "
                "records_processed=?, notes=? WHERE run_id=?",
                (
                    datetime.now(timezone.utc).isoformat(),
                    status,
                    len(pending),
                    notes,
                    run_id,
                ),
            )
            conn.commit()

    logger.info(
        "Enrichment complete. done=%s no_image=%s error=%s",
        counters["done"], counters["no_image"], counters["error"],
    )
    return counters
