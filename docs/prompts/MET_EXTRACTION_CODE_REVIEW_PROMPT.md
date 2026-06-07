# Met Extraction Code Review & Repair

## Your Role

You are a **Principal Software Engineer** conducting a rigorous code review of
`extraction/met/`. Your standards: code must be correct, internally consistent,
importable without error, and match its own documentation. Dead code, broken
imports, and signature mismatches are not "tech debt to track" -- they are
defects to fix in this pass.

## Context

The `extraction/met/` package was recently converted from an async architecture
(aiohttp + asyncio) to a fully synchronous one (requests library only). The
conversion was incomplete. A concurrent-session incident (two Cortex Code
windows writing to the same files) left the codebase in a broken state where:

- One file (`control_enricher.py`) still contains async/aiohttp code that
  cannot execute.
- The README and requirements.txt both state "no async/await or aiohttp" but
  the code contradicts this.
- The module cannot be imported cleanly because `aiohttp` is not in
  `requirements.txt`.

## Repository

- Repo: `github.com/dckallos/artwork-db` (branch: `donkey-kong-sandbox`)
- Package: `extraction/met/` (10 Python files, 11 SQL templates, 1 test file)
- Entry point: `python -m extraction.met.run <subcommand>`
- Snowflake target: `ARTWORK_DB.BRONZE`, role `ARTWORK_LOADER`, key-pair auth

## Scope of This Review

### Phase 1: Identify all defects (read-only audit)

Read every file in `extraction/met/` and produce a defect list. For each defect,
state:
- **File:line** -- exact location.
- **Severity** -- BLOCKING (code cannot run), HIGH (incorrect behavior at
  runtime), MEDIUM (misleading but non-fatal), LOW (style/cleanup).
- **Description** -- what is wrong and why.
- **Fix** -- the specific change required.

Known defects to confirm (your audit must independently verify these):

1. `control_enricher.py` imports `asyncio` and `aiohttp` (not in requirements).
2. `control_enricher.py` defines `async def _fetch_blocks()` using
   `aiohttp.ClientSession`, `asyncio.Semaphore`, `asyncio.Lock`,
   `asyncio.gather`.
3. `control_enricher.py:176` calls `await _fetch_one(session, ...)` but
   `_fetch_one` (in `image_enricher.py`) is a synchronous function that
   expects a `requests.Session`, not an `aiohttp.ClientSession`.
4. `control_enricher.py:323` calls `asyncio.run(_fetch_blocks(...))` to bridge
   async into the sync driver -- this is the only async entry point and it
   calls a sync function with the wrong session type.
5. `config.py:55` has `api_max_concurrency` with a comment "Reserved for future
   threading use" but `control_enricher.py` uses it as an `asyncio.Semaphore`
   value -- which path is canonical?

Your audit should also look for:
- Any other async remnants (await, async with, async for) anywhere in the package.
- Dead imports that served the async path but are now unused.
- Type annotation mismatches (e.g., functions annotated to accept
  `aiohttp.ClientSession` but now receiving `requests.Session`).
- Error-class references in `_classify_error()` that reference aiohttp exception
  names (`ClientConnectorError`, `ServerTimeoutError`, `ClientPayloadError`,
  `ContentTypeError`) -- are these still correct for the requests-based path?
- Whether `_ThrottleGate` and `_RateLimiter` are thread-safe (they use
  `time.sleep` which is fine for sync, but check for any leftover
  `asyncio.Lock` patterns).
- Whether the test file (`tests/test_throttle_gate.py`) still passes given the
  current state of the code it tests.

### Phase 2: Fix all defects

Apply the fixes. The conversion target is clear:

**`control_enricher.py` must become fully synchronous**, matching the pattern
already established in `image_enricher.py:_enrich_sync()`:
- Use a `requests.Session` (not aiohttp).
- Call `_fetch_one()` in a serial loop (not asyncio.gather).
- Remove all asyncio/aiohttp imports.
- The `config.api_max_concurrency` setting remains dormant (as documented in
  config.py) until a threading-based concurrency model is added in the future.

**`_classify_error()` error class names** must reflect the exception hierarchy
of `requests`, not `aiohttp`:
- `requests.ConnectionError` (not `ClientConnectorError`)
- `requests.Timeout` (not `ServerTimeoutError`)
- `requests.exceptions.ChunkedEncodingError` (not `ClientPayloadError`)
- `requests.exceptions.ContentDecodingError` or `json.JSONDecodeError`
  (not `ContentTypeError`)

However: verify first whether `_fetch_one` actually emits these exact error
strings before renaming the classifier buckets. The classifier must match what
`_fetch_one` produces, not a hypothetical.

### Phase 3: Verify

After applying fixes:
1. Confirm the module imports cleanly: `python -c "import extraction.met"`.
2. Confirm `python -m extraction.met.run --help` prints the help text.
3. Run the existing tests: `pytest extraction/met/tests/ -v`.
4. Confirm no `async`, `await`, `aiohttp`, or `asyncio` strings remain in the
   package (grep check).

## Constraints

- Do NOT add `aiohttp` back to requirements. The architectural decision is
  made: this package is synchronous.
- Do NOT introduce threading/concurrent.futures in this pass. The serial
  fetch loop is correct for now (the Met API throttles aggressively; parallelism
  gains are eaten by backoff). If concurrency is added later, it will be a
  separate PR with its own design review.
- Do NOT change the public API of `enrich_from_control()` -- its signature,
  return type, and behavior (drain worklist in batches) must remain stable.
  Internal implementation can change freely.
- Do NOT change SQL templates -- they are correct and tested against live
  Snowflake objects.
- Do NOT modify `image_enricher.py`'s `_fetch_one` signature or behavior --
  it is the canonical, working, sync fetch function. `control_enricher.py`
  must adapt to it.
- Preserve the per-batch logging (progress lines, error histograms, throttle
  counters) -- these are operationally important. Adapt them to the sync flow.
- Keep the docstrings in `control_enricher.py` accurate to the new sync
  implementation (remove references to asyncio, aiohttp, semaphores, etc.).

## Deliverables

1. A defect list (Phase 1) with file:line, severity, and fix description.
2. The fixed files (Phase 2) -- only the files that change.
3. Verification output (Phase 3) -- import check, help check, test run, grep.

## Style Standards

- No unused imports.
- No dead code behind `if False:` or commented-out blocks.
- Type annotations must be accurate (no `Any` where a concrete type is known).
- Docstrings must match the implementation (not describe a prior architecture).
- Follow existing code style in the package (see `image_enricher.py` as the
  reference for the sync pattern, `snapshot_loader.py` for the Snowflake
  interaction pattern).
