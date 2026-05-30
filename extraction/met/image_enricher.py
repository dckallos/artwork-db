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

Rate limiting:
  - Token-bucket-style limiter caps total requests/second (default 20 rps).
  - Bounded semaphore caps concurrent in-flight requests (default 10).
  - Exponential backoff with jitter on 429 / 5xx responses.
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
    """Enforces a minimum interval between successive request acquisitions."""

    def __init__(self, requests_per_second: float) -> None:
        # Guard against zero/negative rps so we never divide by zero.
        self._min_interval = 1.0 / max(requests_per_second, 0.1)
        self._lock = asyncio.Lock()
        self._next_allowed = 0.0

    async def acquire(self) -> None:
        """Block until it is safe to issue another request."""
        async with self._lock:
            now = time.monotonic()
            wait = self._next_allowed - now
            if wait > 0:
                await asyncio.sleep(wait)
                now = time.monotonic()
            self._next_allowed = now + self._min_interval


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
    """Fetch a single Met object record.

    Returns: (object_id, status, payload_or_None, error_message_or_None)
    where status is one of: 'done', 'no_image', 'error'.
    """
    url = f"{api_base}/objects/{object_id}"
    last_error: Optional[str] = None

    for attempt in range(1, max_retries + 1):
        await rate_limiter.acquire()
        try:
            async with session.get(url) as resp:
                # 404 means the object id doesn't exist in the API; treat as no_image.
                if resp.status == 404:
                    return object_id, "no_image", None, None
                if resp.status in (429, 500, 502, 503, 504):
                    last_error = f"HTTP {resp.status}"
                    backoff = min(60.0, (2 ** attempt) + random.uniform(0, 0.5))
                    await asyncio.sleep(backoff)
                    continue
                if resp.status >= 400:
                    text = await resp.text()
                    return object_id, "error", None, f"HTTP {resp.status}: {text[:200]}"

                payload = await resp.json(content_type=None)
                primary = (payload or {}).get("primaryImage") or ""
                if not primary:
                    return object_id, "no_image", None, None
                return object_id, "done", payload, None
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            backoff = min(60.0, (2 ** attempt) + random.uniform(0, 0.5))
            await asyncio.sleep(backoff)

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
