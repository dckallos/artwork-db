"""
Fetch image URLs from the Met API for every pending row.

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
    present; otherwise the GLOBAL throttle gate computes exponential backoff.
  - Adaptive RPS: after 3 consecutive throttles the limiter drops RPS 30 percent;
    on every success it edges back up 5 percent toward the configured ceiling.
  - Global throttle gate: when ANY request observes a throttle, subsequent requests
    block behind a shared backoff_until timestamp. Exponential backoff is driven by
    consecutive global throttle signals, not per-object attempt counters.
  - 403/410 are NOT terminal: 403 is a throttle signal in disguise, 410 (Gone)
    is rare and rolled into the retry path so a transient masquerade does not
    look permanent. After exhausting retries, both fall through to terminal
    'error' with the last HTTP status preserved.
"""
from __future__ import annotations

import json
import logging
import random
import sqlite3
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional, Tuple

import requests

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
    """
    Adaptive token-bucket-style limiter.

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
        self._next_allowed = 0.0
        self._throttle_burst = 0
        # Per-run counters surfaced in the per-batch log so the throttle
        # picture is visible without a re-query of the control table.
        self.throttle_403 = 0
        self.throttle_429 = 0
        self.throttle_other = 0   # 410 / 5xx that hit the same backoff path
        self.backoff_seconds = 0.0

    @property
    def rps(self) -> float:
        return self._rps

    def acquire(self) -> None:
        """
        Block until it is safe to issue another request.
        """
        min_interval = 1.0 / self._rps if self._rps > 0 else 0.1
        now = time.monotonic()
        wait = self._next_allowed - now
        if wait > 0:
            time.sleep(wait)
            now = time.monotonic()
        self._next_allowed = now + min_interval

    def note_throttle(self) -> None:
        """
        Throttle observed; after 3 in a row, decay RPS by 30 percent.
        """
        self._throttle_burst += 1
        if self._throttle_burst >= 3:
            self._rps = max(self._min_rps, self._rps * 0.7)
            if self._rps <= self._min_rps:
                logger.debug(
                    "Adaptive RPS at floor (%.2f); further throttles indicate "
                    "identity rejection, not rate.", self._rps,
                )
            self._throttle_burst = 0
            logger.debug("Adaptive RPS dropped to %.2f after throttle burst", self._rps)

    def cool_up(self) -> None:
        """
        Successful response; edge RPS back up toward the ceiling.
        """
        # Reset burst counter so isolated 403s don't compound across long runs.
        self._throttle_burst = 0
        new = min(self._max_rps, self._rps * 1.05)
        if new > self._rps:
            self._rps = new


class _ThrottleGate:
    """
    Global backoff gate.

    When a request observes a throttle (403/429/5xx), it signals the gate.
    The gate computes a global backoff_until timestamp using exponential backoff
    driven by consecutive global throttle signals. Subsequent requests call
    wait_if_paused() before each attempt and block until the gate lifts.
    """

    def __init__(self, base_backoff: float = 0.8, max_backoff: float = 60.0) -> None:
        self._base = base_backoff
        self._max = max_backoff
        self._max_initial = max_backoff
        self._max_ceiling = 300.0  # hard cap for chronic escalation
        self._backoff_until = 0.0  # monotonic timestamp
        self._consecutive_throttles = 0
        # Chronic-failure detection: rolling window of recent outcomes.
        self._history: deque = deque(maxlen=50)
        self.chronic = False

    def signal_throttle(self, retry_after_hint: Optional[float]) -> None:
        """
        A throttle was observed; extend the global pause.
        """
        self._consecutive_throttles += 1
        self._history.append(False)
        if retry_after_hint is not None and retry_after_hint > 0:
            delay = retry_after_hint
        else:
            delay = min(
                self._max,
                self._base * (2 ** (self._consecutive_throttles - 1)),
            )
        delay += random.uniform(0, 0.5)  # jitter
        new_until = time.monotonic() + delay
        # Only extend; never shorten a pause already in effect.
        if new_until > self._backoff_until:
            self._backoff_until = new_until
        # Chronic detection: once the window is full, check error ratio.
        if len(self._history) == self._history.maxlen:
            fails = self._history.maxlen - sum(self._history)
            ratio = fails / self._history.maxlen
            if ratio > 0.8:
                if not self.chronic:
                    self._max = min(self._max * 2, self._max_ceiling)
                    self.chronic = True
                    logger.warning(
                        "Chronic throttle detected (%d/%d failures). "
                        "Backoff ceiling raised to %.0fs. "
                        "Consider stopping and investigating.",
                        fails, self._history.maxlen, self._max,
                    )
                else:
                    # Already chronic -- keep escalating the ceiling.
                    self._max = min(self._max * 2, self._max_ceiling)
                    logger.warning(
                        "Chronic throttle persists. Backoff ceiling now %.0fs.",
                        self._max,
                    )

    def wait_if_paused(self) -> None:
        """
        Block until the global backoff window has elapsed.
        """
        now = time.monotonic()
        wait = self._backoff_until - now
        if wait > 0:
            time.sleep(wait)

    def note_success(self) -> None:
        """
        A non-throttle response was received; reset the escalation.
        """
        self._consecutive_throttles = 0
        self._history.append(True)
        if self.chronic:
            self._history.clear()
            self._max = self._max_initial
            self.chronic = False
            logger.info(
                "Chronic throttle cleared after successful response. "
                "Backoff ceiling reset to %.0fs.", self._max,
            )


def _retry_after_seconds(resp: requests.Response) -> Optional[float]:
    """
    Parse the `Retry-After` response header into a non-negative seconds delay.

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
    """
    Return all object_ids whose enrichment_status is 'pending' or 'error'.
    """
    cur = conn.execute(
        "SELECT object_id FROM met_artworks "
        "WHERE enrichment_status IN ('pending', 'error') "
        "ORDER BY object_id"
    )
    return [r[0] for r in cur.fetchall()]


def _fetch_one(
    session: requests.Session,
    rate_limiter: _RateLimiter,
    throttle_gate: _ThrottleGate,
    api_base: str,
    object_id: int,
    max_retries: int,
    timeout: float = 20,
) -> Tuple[int, str, Optional[Dict[str, Any]], Optional[str]]:
    """
    Fetch a single Met object record with global throttle gate.

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

    Backoff is GLOBAL: when a throttle is observed, the shared _ThrottleGate
    extends backoff_until. The next iteration blocks behind the gate via
    wait_if_paused(), then re-acquires the rate limiter before retrying.
    """
    url = f"{api_base}/objects/{object_id}"
    last_error: Optional[str] = None

    for attempt in range(1, max_retries + 1):
        # Block behind the global gate (no-op if no active pause).
        throttle_gate.wait_if_paused()
        rate_limiter.acquire()
        try:
            resp = session.get(url, timeout=timeout)
            status_code = resp.status_code

            # 404 = does not exist; terminal no_image.
            if status_code == 404:
                rate_limiter.cool_up()
                throttle_gate.note_success()
                return object_id, "no_image", None, None

            # Throttle / transient: 403 (Met returns this as soft-throttle),
            # 410 (defensive; usually Gone but treated as transient first),
            # 429 (rate limit), 5xx (transient server). Signal the global
            # gate and let it compute the shared backoff.
            if status_code in (403, 410, 429, 500, 502, 503, 504):
                last_error = f"HTTP {status_code}"
                retry_after = _retry_after_seconds(resp)
                if status_code == 403:
                    rate_limiter.throttle_403 += 1
                elif status_code == 429:
                    rate_limiter.throttle_429 += 1
                else:
                    rate_limiter.throttle_other += 1
                rate_limiter.note_throttle()
                throttle_gate.signal_throttle(retry_after)
                # Track cumulative backoff for the per-batch summary.
                gate_wait = max(0.0, throttle_gate._backoff_until - time.monotonic())
                rate_limiter.backoff_seconds += gate_wait
                logger.debug(
                    "oid=%s attempt=%s HTTP=%s gate_wait=%.1fs (rps=%.2f)",
                    object_id, attempt, status_code, gate_wait, rate_limiter.rps,
                )
                continue

            # Other 4xx: terminal client error.
            if status_code >= 400:
                return object_id, "error", None, f"HTTP {status_code}: {resp.text[:200]}"

            # 2xx: parse and return.
            payload = resp.json()
            primary = (payload or {}).get("primaryImage") or ""
            rate_limiter.cool_up()
            throttle_gate.note_success()
            if not primary:
                return object_id, "no_image", None, None
            return object_id, "done", payload, None

        except requests.RequestException as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            throttle_gate.signal_throttle(None)
            logger.debug(
                "oid=%s attempt=%s network exception (rps=%.2f)",
                object_id, attempt, rate_limiter.rps,
            )
            continue

    # All retries exhausted.
    return object_id, "error", None, last_error or "max retries exceeded"


def _apply_result(
    conn: sqlite3.Connection,
    object_id: int,
    status: str,
    payload: Optional[Dict[str, Any]],
    error_message: Optional[str],
) -> None:
    """
    Persist a single API result back to SQLite.
    """
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


def _enrich_sync(
    config: Config,
    object_ids: List[int],
    progress_every: int = 500,
) -> Dict[str, int]:
    """
    Drive the serial fetch loop and persist results to SQLite.
    """
    counters: Dict[str, int] = {"done": 0, "no_image": 0, "error": 0}
    rate_limiter = _RateLimiter(config.api_requests_per_second)
    throttle_gate = _ThrottleGate()

    session = requests.Session()
    session.headers.update({
        "User-Agent": config.api_user_agent,
        "Accept": "application/json",
    })
    request_timeout = config.api_request_timeout_seconds

    completed = 0
    chronic_checks = 0

    with connect(config.sqlite_path) as conn:
        for oid in object_ids:
            result = _fetch_one(
                session, rate_limiter, throttle_gate,
                config.api_base, oid, config.api_max_retries,
                timeout=request_timeout,
            )
            _apply_result(conn, *result)
            counters[result[1]] += 1
            completed += 1
            if completed % progress_every == 0:
                conn.commit()
                logger.debug(
                    "Enrich progress: %s/%s (done=%s no_image=%s error=%s "
                    "| 403=%s 429=%s other=%s backoff=%.1fs rps=%.2f)",
                    f"{completed:,}", f"{len(object_ids):,}",
                    counters["done"], counters["no_image"], counters["error"],
                    rate_limiter.throttle_403, rate_limiter.throttle_429,
                    rate_limiter.throttle_other, rate_limiter.backoff_seconds,
                    rate_limiter.rps,
                )
                # Bail-out: if chronic throttle persists across 2 progress ticks,
                # stop burning wall-clock time against a rejecting API.
                if throttle_gate.chronic:
                    chronic_checks += 1
                    if chronic_checks >= 2:
                        logger.error(
                            "Bailing out: chronic API rejection detected. "
                            "%s/%s objects completed. "
                            "Re-run will resume from where we stopped.",
                            f"{completed:,}", f"{len(object_ids):,}",
                        )
                        conn.commit()
                        break
                else:
                    chronic_checks = 0
        else:
            conn.commit()

    session.close()
    return counters


def enrich(config: Config) -> Dict[str, int]:
    """
    Enrich every pending/error row. Returns final status counts.
    """
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
        counters = _enrich_sync(config, pending)
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
