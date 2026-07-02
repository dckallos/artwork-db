# Met API: Adaptive Rate Limiter with Chronic-Failure Detection

## Your Role

You are a **Principal Software Engineer** with deep expertise in Python async
programming, API rate-limiting patterns (token bucket, AIMD, exponential backoff),
and production ETL pipelines. Your standards: changes must be minimal (net +40
lines max), backwards compatible, and testable offline. You value simplicity over
cleverness -- a 20-line state machine beats a 200-line framework.

## Repository

- Repo: `github.com/dckallos/artwork-db` (branch: `donkey-kong-sandbox`)
- File to modify: `extraction/met/image_enricher.py`
- Config file: `extraction/met/config.py`
- Run: `cd ~/dev/artwork-db && python -m extraction.met.run enrich-met`

## Context

The Met OpenAccess API has an official rate limit of 80 requests per second but
empirically returns 403 (not 429) as a soft-throttle signal well below that
ceiling. A prior production run saw 104/200 requests 403'd at only ~11 rps
observed. The existing code (`image_enricher.py`) already has:

### What exists today

1. **`_RateLimiter`** (~70 lines): Adaptive token-bucket limiter.
   - `note_throttle()`: after 3 consecutive throttles, drop RPS by 30%.
   - `cool_up()`: on each success, nudge RPS up 5% toward ceiling.
   - Min floor: 1.0 rps. Max ceiling: configured RPS (default 40).
   - Tracks `throttle_403`, `throttle_429`, `throttle_other`, `backoff_seconds`.

2. **`_ThrottleGate`** (~50 lines): Global backoff gate shared by all workers.
   - `signal_throttle(retry_after)`: extends a shared `backoff_until` timestamp
     using exponential backoff (base=0.8s, max=60s) + jitter.
   - `wait_if_paused()`: all workers block behind the gate before each request.
   - `note_success()`: resets `_consecutive_throttles` to 0.

3. **`_fetch_one`** (~70 lines): Per-object fetch with retry loop.
   - Treats 403, 429, 410, 5xx as retryable (signals the gate).
   - Respects `Retry-After` header. Up to `max_retries=8` attempts.
   - 404 is terminal no_image. Other 4xx is terminal error.

4. **`_enrich_async`** (~50 lines): Fan-out via `asyncio.gather(*workers)`.
   - `api_max_concurrency=8` workers behind an `asyncio.Semaphore`.
   - Each worker acquires semaphore, calls `_fetch_one`, persists to SQLite.

5. **Config defaults**: `MET_API_RPS=40`, `MET_API_CONCURRENCY=8`, `MET_API_MAX_RETRIES=8`.

### What's missing

1. **No chronic-failure detection**: If the API returns 403 for extended periods
   (identity-based rejection, CDN block, or sustained throttle storm), the limiter
   keeps retrying at floor RPS (1.0) forever. It never escalates -- no wider
   backoff ceiling, no diagnostic, no bail-out.

2. **Concurrency is wasteful**: With an effective RPS of 40 (often decaying to
   5-10 during throttling), 8 concurrent workers spend most of their time blocked
   in `acquire()` or `wait_if_paused()`. The semaphore + gather pattern adds
   complexity (write_lock, progress counters, thundering-herd mitigation) for
   minimal throughput gain. A simpler 2-3 worker model (or even serial with the
   rate limiter) would achieve the same effective throughput with less code.

## What to implement

### Change 1: Chronic-failure detection in `_ThrottleGate` (~20 lines)

Add a rolling error-ratio tracker to `_ThrottleGate`:

- Track last N responses (success/fail) in a fixed-size deque (e.g., N=50).
- After the deque is full, compute `error_ratio = fails / N`.
- If `error_ratio > 0.8` (chronic threshold):
  1. Double `_max` backoff ceiling (up to a hard cap, e.g., 300s).
  2. Log a WARNING: "Chronic throttle detected (X/Y failures). Backoff ceiling
     raised to Zs. Consider stopping and investigating."
  3. Set a `chronic` flag on the gate (readable by caller for bail-out logic).
- Reset the deque on the first success after a chronic episode.

This gives progressive escalation: initial throttles use 0.8-60s backoff, but
chronic rejection widens to 120s, 240s, 300s between attempts.

### Change 2: Simplify concurrency (~10 lines net removal)

Reduce `MET_API_CONCURRENCY` default from 8 to 3 in `config.py`. Add a comment
explaining why: at 40 rps target (often decaying to 5-10 under throttle), more
than 3 workers adds lock contention without throughput gain. The semaphore already
caps concurrency, so this is just a default change + documentation.

Do NOT rewrite the gather pattern to serial -- that would be a larger refactor.
Just reduce the default and add a config guard:

```python
api_max_concurrency: int = int(os.getenv("MET_API_CONCURRENCY", "3"))
```

### Change 3: Bail-out on chronic failure (~10 lines)

In `_enrich_async`, after each batch of completions (or on the progress_every
tick), check `throttle_gate.chronic`. If True for 2 consecutive checks:

- Log ERROR: "Bailing out: chronic API rejection detected. X/Y objects completed.
  Re-run will resume from where we stopped."
- Break the gather loop (cancel remaining tasks).
- Return partial counters (the run is resumable by design).

This prevents burning hours of wall-clock time against an API that's rejecting
everything.

## Constraints

- **Net code change: +40 lines max** (excluding comments and the test file).
- **No new dependencies.** Use only `collections.deque` (stdlib).
- **Backwards compatible.** Existing env vars still work. Config dataclass
  unchanged except the concurrency default (8 -> 3).
- **Single file change:** `image_enricher.py` (+ 1 line in `config.py` default).
- **Test:** Add `tests/test_rate_limiter.py` (or extend existing) with:
  - Test that chronic detection triggers after N consecutive failures.
  - Test that backoff ceiling escalates progressively.
  - Test that a single success resets the chronic state.
  - All tests run offline (no network, no SQLite).

## How to validate

```bash
# Unit tests
cd ~/dev/artwork-db
pytest extraction/met/tests/test_rate_limiter.py -v

# Integration (small slice)
MET_API_RPS=5 MET_API_CONCURRENCY=2 python -m extraction.met.run enrich-met
# Watch logs for "Adaptive RPS" and "Chronic throttle" messages
```

## Anti-patterns to avoid

- Don't add a `ChronicFailureDetector` class with its own file. Keep it inside
  `_ThrottleGate` (it's 15-20 lines of deque logic, not a new abstraction).
- Don't add circuit-breaker library deps (tenacity, pybreaker, etc.).
- Don't refactor `_enrich_async` from gather to a producer-consumer queue.
  That's a larger change for a future PR. Just reduce concurrency default.
- Don't add per-worker chronic detection. It's a GLOBAL signal (the gate is
  already global). One deque, one threshold, one flag.
