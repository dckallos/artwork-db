# Met Extraction Pipeline -- Code Review + Patch Plans

**Date:** 2026-05-31
**Reviewer:** Cortex Code (senior data engineer perspective; Cortex Code in Snowsight)
**Scope:** Met extraction pipeline -- Phase 1 snapshot + Phase 2 control seed + Phase 3
lease-claim enrichment, plus a triage of the 109 errors observed in the
2026-05-31T20:35Z run (`enrich-met --limit 200`: claimed=200, done=91, error=109).
**Supersedes:** the prior 264-line draft at the same path.

---

## 0. Executive summary

Overall health: substantive design is sound and matches the locked Section-C
contract (Option B + PIPE-06 hybrid). Phase 1 (snapshot, 484,956 rows) and Phase 2
(seed, 2,327 European Paintings public-domain rows) are demonstrably correct; the
live data confirms it. What concerns me is **structural, not algorithmic**:

1. **Phase 3 currently exists as two conflicting twins** (`met_enricher.py` and
   `control_enricher.py`) that share `claim_worklist.sql` with **incompatible
   placeholder contracts**. Only `control_enricher` is wired by `run.py`. The
   other module would crash on first call. This is a Blocker -- exactly the
   dropped-turn / dual-FS hazard you warned about, frozen as code.
2. **The CLI-vs-connector split is real but partial.** Recommendation: hybrid.
   Phase 2 to CLI; Phase 1 + Phase 3 stay on the connector with hardening; the
   convention doc gets reworded to match reality (DDL via `snow`, runtime ETL
   via connector + key-pair).
3. **The pyformat `%`-binding bug class** has been beaten back tactically
   (comment stripping + comment scrub) but is one stray character away from
   biting again. Switching paramstyle to `qmark` retires the whole class in one
   line.
4. **DATA-01 deaccession is unimplemented** in `merge_csv_snapshot.sql`. An
   object removed from the next OpenAccess CSV will linger forever.
5. **The 109 errors are diagnostic blind**: `enrichment_error` is captured in
   `_fetch_blocks` but never reaches the control table or any log. We are
   running half-deaf. Fix that BEFORE chasing root cause.

CLI-migration recommendation (the headline): **partial migration.**

| Phase                 | Recommendation                | Why                                                                                   |
|-----------------------|-------------------------------|---------------------------------------------------------------------------------------|
| Phase 2 (seed)        | **Migrate to CLI**            | One MERGE + count. Trivial port. Kills pyformat bug class on the most-exposed surface |
| Phase 1 (snapshot)    | Keep connector                | Chunked PUT/COPY across hundreds of chunks benefits from one auth + one session       |
| Phase 3 (enrich)      | Keep connector + harden       | TEMP staging table + multi-statement txn is exactly what CLI cannot express well      |
| Legacy SQLite upload  | Delete                        | Option B is locked; this is dead code                                                 |

Update AGENTS.md / CLAUDE.md, do not break working code: the docs currently read
as "ALL Snowflake access goes through the CLI." That has never been true for
runtime ETL. Reword to "ALL DDL / IaC flows through `snow` / `make iac`. Runtime
ETL (`extraction/`) uses `snowflake.connector` with key-pair auth; Phase 2 (seed)
is the documented exception that does flow through `snow sql`."

---

## 1. Verify-before-trust list (dual-FS caveats)

I read these from the workspace file tool (Cortex Code's view of the workspace
stage). Please paste the Mac copy if anything below disagrees with what is on
`donkey-kong-sandbox`:

- `extraction/met/met_enricher.py` -- I see it as a 292-line file with a
  `_claim_batch` whose `.format(...)` does NOT match `claim_worklist.sql`. If
  the Mac no longer has this file (i.e. it was deleted in a prior turn), strike
  all `met_enricher.py` findings.
- `extraction/met/sql/release_lease.sql` -- I see it loaded only by
  `met_enricher.py:52`. `control_enricher` uses an inline UPDATE instead. If
  `met_enricher.py` is gone, this template is also dead.
- `extraction/met/sql/claim_worklist.sql` -- I see `{control}/{worklist}/{limit}`
  + one `%s`. The progress log mentions a variant with `{batch_id}` +
  `{limit_clause}` (and no `%s`). Confirm the Mac copy.

---

## 2. Findings (severity-ranked, file:line, with concrete fixes)

### BLOCKER

**B1. Twin Phase-3 modules; one is dead and broken.**
`extraction/met/met_enricher.py:93` calls
`CLAIM_WORKLIST_SQL.format(control=..., worklist=..., batch_id=batch_id, limit_clause=limit_clause)`.
`extraction/met/sql/claim_worklist.sql:20-24` declares `{control}/{worklist}/{limit}`
and a literal `%s` for the batch_id bind. Calling `met_enricher.enrich_met` would
raise `KeyError: 'limit'` immediately, and even if fixed, the unbound `%s` would
survive into the executed SQL because `met_enricher._claim_batch` does NOT pass a
params tuple to `cur.execute`. Same module also calls
`ASSEMBLE_RAW_SQL.format(target=...)` (line 212) but
`assemble_raw_met_objects.sql:19-49` expects `{raw}` -- a second `KeyError`.
`met_enricher._callback` (line 225) passes `batch_id=batch_id` but
`callback_enrichment_control.sql:13-23` declares only `{control}/{stg}` (extra
kwargs ignored -- silent divergence).
`run.py:166-172` wires `enrich-met` to `control_enricher.enrich_from_control`,
NOT to `met_enricher.enrich_met`. So `met_enricher.py` is unreachable at runtime
but still on disk.
**Fix:** delete `met_enricher.py` and `release_lease.sql` (only loaded by
met_enricher). Patch plan P-B1 below.

**B2. The CLI-vs-connector convention is misstated, not actually violated.**
`AGENTS.md:35-37` and `CLAUDE.md:13-19` declare "every Snowflake object is
created through the Snowflake CLI" / "ALL Snowflake access goes through Snowflake
CLI." That is true for DDL/IaC; it has never been true for runtime ETL. The
connector use predates the convention doc by several windows and the doc never
carved that out. Today `control_seeder.py:35`, `snapshot_loader.py:39`,
`snowflake_uploader.py:120-147`, `control_enricher.py:44`, and the dead
`met_enricher.py:44` all import `_snowflake_connect` from `snowflake_uploader`.
Calling this a Blocker because it spreads doubt across every other finding.
**Fix:** doc-reword (no code). Patch plan P-B2 below.

### HIGH

**H1. `autocommit=True` makes the "transactional" framing in three docstrings false.**
`snowflake_uploader._snowflake_connect` does not set `autocommit`, and the
connector default is `autocommit=True`. So in:
- `control_enricher._process_one_batch` (lines 235-254) `_assemble_and_callback`
  runs `ASSEMBLE_RAW_SQL` then `CALLBACK_CONTROL_SQL`; the trailing
  `sf_conn.commit()` is a no-op. If the callback raises, RAW already has rows
  but the lease is still held; the `_release_unfinished` UPDATE in the except
  branch frees the lease, and on retry the next batch will re-fetch and the
  assemble MERGE will refresh in place (idempotent -- fine). But the docstring
  "Assembly + callback commit together" is misleading.
- `control_seeder.seed_control` (lines 138-160): `_log_start` already
  auto-committed by the time the MERGE runs. If the MERGE fails, EXTRACTION_LOG
  has a `running` row that gets updated to `failed` in the except branch (good).
- `snapshot_loader.load_snapshot` (lines 264-302): each chunk's COPY
  auto-commits; the final MERGE auto-commits.

**Fix:** explicitly set `autocommit=False` in `_snowflake_connect`, then wrap
genuine atomic groups in `cur.execute("BEGIN")` / `sf_conn.commit()` /
`sf_conn.rollback()` on except. The clearest win is wrapping
`_assemble_and_callback` so a callback failure rolls back the assemble too.
Patch plan P-H1 below.

**H2. DATA-01 deaccession not implemented in the snapshot MERGE.**
`merge_csv_snapshot.sql:12-24` has only `WHEN MATCHED UPDATE` and
`WHEN NOT MATCHED INSERT`. An object removed from the next OpenAccess CSV will
linger in `MET_CSV_SNAPSHOT` indefinitely -- leaks into `MET_WORKLIST` (control
join hides this only if control is also missing the row), leaks into
`RAW_MET_OBJECTS` once enriched. Owner explicitly cares (timeliness /
deaccession).
**Fix:** add a deletion sweep, gated to FULL snapshot loads. Patch plan P-H2.
**Mentor learning fork:** this is the canonical place to introduce a dbt
**snapshots** model (SCD-2) so deaccession history becomes auditable rather
than destructive.

**H3. Pyformat `%`-binding fragility persists.**
`seed_enrichment_control.sql` is now percent-free in comments and
`control_seeder.py:126` calls `strip_sql_comments` before `.format`. But the
design is still: any `%` anywhere in the rendered SQL must coexist with `%s`
binds, and the connector will fail with "not enough arguments for format
string" the moment they don't tally. A future `LIKE '%greek%'` predicate, a
tag inside a comment, anything: breaks it.
**Fix that retires the bug class:** set
`snowflake.connector.paramstyle = "qmark"` once at import time, migrate every
`%s` to `?`. Patch plan P-H3.

**H4. SQL-injection escape hatch.**
`control_seeder._build_predicate` (line 66-67) interpolates the raw `--where`
argument into the predicate. Documented as "owner-supplied escape hatch."
**Fix:** require an env flag (`MET_ALLOW_RAW_WHERE=1`) and log the rendered
predicate at WARN level, not INFO, when `--where` is present. Patch plan P-H4.

**H5. Duplicated fetch / stage logic.**
`control_enricher._fetch_blocks` (line 81-114) and `met_enricher._fetch_images`
(line 103-159) are nearly identical; `_stage_results` / `_stage_blocks` mirror
each other. If you keep `met_enricher` (you should not -- see B1), factor the
rate-limited async fetch into a single helper. If you delete `met_enricher`,
this resolves itself.

### MEDIUM

**M1. Stage debris on failed batch.** `control_enricher` PUTs into
`<stage>/met_enrich/<batch_id>/`; `copy_into_image_block_stg.sql:17` reads with
`PURGE = TRUE`. Good. But on a failed batch (exception before COPY), the staged
file is NOT purged. Add `REMOVE @<stage>/met_enrich/<batch_id>/` in the except
branch, or rely on a periodic stage cleanup task. Same applies to
`snapshot_loader._put_and_copy_stg` and `snowflake_uploader._put_and_copy`.

**M2. `EXTRACTION_LOG.records_loaded` semantics drift.** `control_seeder._log_finish`
records `inserted` (good). `snapshot_loader._log_finish` records `inserted+updated`
(good). `control_enricher._log_finish` records `assembled` (line 240) but the dead
`met_enricher._log_finish` records `len(claimed)` (line 275). Pick one definition
and write it down in the column comment in `create_bronze_tables.sql:78`
("rows that successfully landed in the target Bronze table").

**M3. `image_status` / IMG-04 column never written.**
`MET_ENRICHMENT_CONTROL.image_status` defaults to `'unknown'`
(`create_bronze_tables.sql:100`) and is referenced in IMG-03 logic, but no code
ever advances it. Either remove the column until IMG-04 ships, or carry an
explicit TODO in the column COMMENT.

**M4. `config.snowflake_table` defaults lowercase.** `config.py:71` sets
`snowflake_table` default `"raw_met_objects"`. Snowflake folds unquoted
identifiers to UPPER, so it works, but CLAUDE.md mandates UPPERCASE Snowflake
identifiers. Same for `snowflake_stage`. Note: `control_enricher.py:157` ignores
`config.snowflake_table` and hardcodes `RAW_MET_OBJECTS` (correct value, wrong
source).

**M5. Lease-claim race correctness.** `claim_worklist.sql` is correct for
**single-drainer** topology: the `claimed_at IS NULL` predicate and the
worklist's own filter together enforce mutual exclusion at UPDATE time. For two
simultaneous drainers, the second's UPDATE would observe fewer rows than `n`,
which `_claim_batch` then reads back via
`SELECT WHERE claimed_by_batch=batch_id` -- correct, just under-claimed.
**Defensible** but **not stress-tested.** Document single-drainer as the
supported topology in `claim_worklist.sql:16-19`.

**M6. `_release_unfinished` ordering after H1 fix.** Sequence the rollback
explicitly: `sf_conn.rollback(); _release_unfinished(...); sf_conn.commit()`.
Without H1, the inline UPDATE auto-commits and is durable, which is fine; with
H1 (autocommit=False), the release UPDATE rolls back along with everything
else if you don't sequence it.

**M7. `_create_staging_table` runs once per `enrich_from_control` call.** Correct
(TEMP table is session-scoped; subsequent batches `TRUNCATE`). Just noting that
this is the strongest argument AGAINST porting Phase 3 to CLI (each `snow sql`
call is a fresh session, the TEMP table evaporates between batches).

**M8. `csv_bootstrap._iter_csv_rows` mutates a global on import.**
`csv_bootstrap.py:186` does `csv.field_size_limit(sys.maxsize)`. Module-import
side effects are surprising in tests/REPL. Move it inside the function.

### LOW

**L1. Dead code.** `image_enricher.py`, `snowflake_uploader._iter_upload_rows /
_build_payload / _write_ndjson_chunk / _mark_uploaded / upload`,
`update_enrichment_done.sql`, `db.connect / db.initialize_database` (sqlite),
plus the `bootstrap` / `enrich` / `upload` / `status` / `all` subcommands in
`run.py:100-104, 145-148, 155-156, 173-182`. Now that Option B is locked +
applied, this is a maintenance liability. Delete in one PR; retain only
`_snowflake_connect` (move it to `db.py`).

**L2. Stale module docstrings.** `snowflake_uploader.py:1-18` describes the
obsolete SQLite-authoritative strategy verbatim. Re-word once L1 lands.

**L3. `rename_and_update.py` at repo root.** Already on the gated-items list
(AGENTS.md gated #2). Delete with L1.

**L4. `release_lease.sql`** documented for `met_enricher.py`. Delete with B1.

**L5. `_snowflake_connect` no context-manager support.** All call sites use
`try/finally`. Functionally equivalent; could be cleaner with
`@contextmanager` wrapper.

**L6. Ad-hoc str.format-as-literal of `batch_id`** in
`assemble_raw_met_objects.sql:35,47,49`, `release_lease.sql:13`. Generated from
`uuid.uuid4().hex[:6] + datetime` so injection-safe in practice; an
`assert re.fullmatch(r"[A-Za-z0-9_]+", batch_id)` near generation in
`control_enricher.py:217-220` would make this a defensive guarantee.

**L7. `EXTRACTION_LOG.error_message VARCHAR` unbounded.** Code already
truncates at 1000 chars. Either declare `VARCHAR(1000)` for symmetry or remove
the truncation. No correctness issue.

**L8. `merge_csv_snapshot.sql` QUALIFY tiebreaker.** `ORDER BY object_id` ties
to itself (constant for ties on object_id) -- effectively `ORDER BY 1`, picks
arbitrarily. CSV duplicates are rare; tighten to a stable column when one is
available.

### NIT

- `EXTRACTION_LOG.status` enum is implicit (`running`, `success`, `failed`).
  Consider a CHECK constraint or a comment listing the values.
- `control_enricher.py:42` imports `strip_sql_comments` and `load_sql`; only
  `load_sql` is referenced in the file body. `CLAIM_WORKLIST_SQL` is
  pre-stripped at import (line 48), so the import IS needed -- just place it on
  its own line for clarity.
- `seed_enrichment_control.sql:7` -- the doc-comment says "`{{limit}}` trailing
  LIMIT clause text"; the rendered key is `{limit}`. Reword.

---

## 3. dbt-forward note (Track 5 -- Section C to Silver)

What should NOT stay in Python long-term:

- `assemble_raw_met_objects.sql`'s server-side `OBJECT_CONSTRUCT` join. This is
  a Silver model, not a Bronze loader concern. Once dbt is in: the Mac fetches
  image blocks, lands them in a thin `BRONZE.MET_IMAGE_BLOCKS` table; dbt
  assembles `SILVER.MET_OBJECTS` from `MET_CSV_SNAPSHOT` x `MET_IMAGE_BLOCKS`.
  `RAW_MET_OBJECTS` becomes redundant.
- `MET_WORKLIST`'s priority logic -- fine as a view today, becomes a dbt model
  once Silver lands so tests and docs travel with it.
- DATA-01 deaccession (H2) -- canonical dbt **snapshots** territory. Don't bake
  destructive deletes into the Python loader; let dbt own SCD-2 history.

What SHOULD stay in Python: the API fetch, the rate limiter, and the
lease-claim / PUT / COPY plumbing. Imperative I/O work, not transformations.

---

## 4. The 109 errors -- diagnosis + fix plan

Run: `python -m extraction.met.run enrich-met --limit 200`
Result: claimed=200, done=91, no_image=0, error=109.

Note: the `botocore.tokens` SSO error at the top of the log is **unrelated
noise** -- some other process in the same Python venv is trying to refresh an
AWS SSO token and failing. It does not affect the Met fetch (which uses
`aiohttp`, not boto). Ignore it; or, better, scrub the AWS-CLI dependency from
this venv.

### 4a. The top problem: errors are diagnostic blind

`control_enricher._fetch_blocks` (line 100-108) constructs a block dict that
does carry `enrichment_error`. But:

- `copy_into_image_block_stg.sql` lands the block whole into a single VARIANT
  column, so `enrichment_error` survives in staging.
- `callback_enrichment_control.sql:18-23` writes only
  `enrichment_status` and `has_primary_image` back to `MET_ENRICHMENT_CONTROL`.
- `MET_ENRICHMENT_CONTROL` has no error column at all.
- `EXTRACTION_LOG.error_message` is single-valued per batch; the 109 per-row
  errors collapse to one line.

So today the 109 errors leave **no forensic trail**. We can re-run them, but
we cannot ask "why did 109 fail" from Snowflake.

### 4b. Likely root causes (ranked by my prior)

`_fetch_one` returns status `error` in three paths:

1. HTTP 4xx other than 404 (immediate, no retry): line 120-122. Possible Met
   responses include 400 / 403 / 410 for unusual / restricted / deaccessioned
   IDs.
2. `aiohttp.ClientError` or `asyncio.TimeoutError` after `MET_API_MAX_RETRIES`
   (default 5) attempts: line 129-134.
3. 429 / 5xx after max retries: line 115-119.

The run finished in approximately 20 seconds. With `MET_API_MAX_RETRIES=5` and
exponential backoff capped at 60s per retry, a single retried error costs up
to ~62s -- which means MOST of the 109 errors did NOT exhaust retries; they
returned at attempt 1, which points at path (1): non-retryable 4xx.

**Hypothesis A (most likely): a non-trivial fraction of the 200 claimed
European Paintings public-domain rows return 4xx from
`/objects/{id}`.** Possible reasons:
- The public-domain CSV flag is **metadata**, not a guarantee that the API
  knows the object publicly. Some object_ids may exist in the CSV but be
  unavailable via the API (deaccession lag, restricted, embargoed).
- The CSV may carry stale or non-canonical object_ids (very rare).

**Hypothesis B: HTTP/2 connection reuse with high concurrency.** aiohttp
defaults are usually fine; with `MET_API_RPS=20` and concurrency=10 we are well
below Met's 80 rps ceiling. Less likely but worth ruling out.

**Hypothesis C: SSL handshake spikes early in the run.** A burst of new
connections at start can transiently fail. The first wave of 10 concurrent
requests would all attempt connect at once.

### 4c. Fix plan for the 109 (in order)

1. **Persist the per-row error message.** This is the cheapest, highest-value
   change. Patch plan P-D1 below.
2. **Re-run the 109 errored object_ids and read the persisted errors.** Because
   the lease was released (callback ran with `enrichment_status='error'` and
   cleared the lease), they are back in MET_WORKLIST -- but with the current
   schema we still won't see WHY. Sequence: P-D1 first, then re-run.
3. **Add an HTTP-status histogram log line per batch.** Already most of the
   shape we need. Patch plan P-D2.
4. **Triage by hand** the first ~10 errored object_ids with `curl` to a Met
   API URL once the histogram tells us which status codes dominate.
5. **Only then** consider lowering RPS/concurrency or extending retries. We
   should not tune knobs blind.

---

## 5. Patch plans (gated -- nothing applied without sign-off)

Each plan is sized for a single PR. Each is reversible. Branch:
`donkey-kong-sandbox`. None of these touch the IaC manifest unless explicitly
called out (only P-H2 adds a SQL template; P-D1 adds a column to
MET_ENRICHMENT_CONTROL through `infrastructure/create_bronze_tables.sql`).

### P-B1 -- Delete the dead Phase-3 twin

**Goal:** remove `met_enricher.py` + `release_lease.sql` so there is exactly
one Phase-3 implementation.

Steps:
1. Verify with the Mac copy that `met_enricher.py` is not the canonical
   implementation. (Workspace view says it is broken; confirm.)
2. `git rm extraction/met/met_enricher.py extraction/met/sql/release_lease.sql`.
3. Grep for any leftover import: there should be none (run.py imports
   `control_enricher`, not `met_enricher`).
4. Update `extraction/met/CLAUDE.md` and `docs/context/extraction.md` to drop
   any reference.
5. Commit on `donkey-kong-sandbox` with message
   `chore(met): drop dead met_enricher.py twin (B1)`.
6. No Snowflake action.

Risk: zero, IF Hypothesis-verification step (1) holds.

### P-B2 -- Reword the convention docs

**Goal:** convention doc tells the truth about runtime ETL.

Steps:
1. `AGENTS.md`: edit "What this repo is" so the line reads
   "All Snowflake DDL is created through the Snowflake CLI (`snow`) and is
   reproducible end-to-end from automated scripts. Runtime ETL
   (`extraction/`) uses `snowflake.connector` with key-pair auth; Phase 2
   (control seed) is the documented exception that does flow through
   `snow sql`."
2. `CLAUDE.md`: edit "Core conventions" similarly.
3. `extraction/met/config.py`: docstring already correct; no change.
4. Commit: `docs: clarify CLI-vs-connector split per code review (B2)`.

Risk: zero (no code).

### P-D1 -- Persist per-row enrichment error (BLOCK 109 diagnosis)

**Goal:** the 109 errors stop being diagnostic-blind.

Steps (single PR):
1. `infrastructure/create_bronze_tables.sql`: add column to
   `MET_ENRICHMENT_CONTROL`:
   ```
   enrichment_error    VARCHAR(500)    COMMENT 'Last fetch error message; cleared on success.',
   ```
   (`IF NOT EXISTS` is irrelevant for ADD COLUMN; declare the column once,
   re-applies will no-op via `CREATE TABLE IF NOT EXISTS`.) Because the table
   is `CREATE TABLE IF NOT EXISTS` and ALREADY EXISTS in BRONZE, the column
   addition needs a one-shot ALTER. Two options:
   - (a) one-shot `ALTER TABLE MET_ENRICHMENT_CONTROL ADD COLUMN
     enrichment_error VARCHAR(500)` applied via `make iac` after editing the
     CREATE TABLE DDL to include the new column. Future fresh applies see the
     column on creation; the one ALTER is the only manual step.
   - (b) idempotent shim: append
     `ALTER TABLE IF EXISTS MET_ENRICHMENT_CONTROL ADD COLUMN IF NOT EXISTS
     enrichment_error VARCHAR(500);` to the same file. Keeps `make iac` fully
     re-runnable. Recommended.
2. `infrastructure/drop_bronze_tables.sql`: no change (the table is dropped
   whole).
3. `extraction/met/sql/callback_enrichment_control.sql`: extend the SET clause
   to write `enrichment_error`:
   ```
   c.enrichment_error  = s.block:enrichment_error::STRING,
   ```
   On success the block has `"enrichment_error": null`, which clears the
   column. Idempotent.
4. `extraction/met/control_enricher.py`: `_fetch_blocks` already populates
   `enrichment_error` (line 107). No code change.
5. Test: re-run `enrich-met --limit 50` against a known-error slice.
6. Commit: `feat(met): persist per-row enrichment_error for diagnosis (D1)`.

Risk: low. Adds a column; values default to NULL on existing rows; callback
writes NULL on success.

### P-D2 -- Per-batch HTTP-status histogram

**Goal:** per batch, log a one-line histogram of failure modes.

Steps:
1. `extraction/met/control_enricher._fetch_blocks` -- replace the lock-guarded
   `blocks.append(block)` with a parallel update of a `defaultdict[str, int]`
   keyed by an `error_class` derived from `error`:
   - HTTP 4xx: `http_4xx_<code>`
   - HTTP 5xx: `http_5xx_<code>`
   - `ClientConnectorError`: `connect`
   - `ServerTimeoutError` / `asyncio.TimeoutError`: `timeout`
   - `JSONDecodeError`: `parse`
   - everything else: `other`
2. Extend the existing INFO log line:
   ```
   Batch X: claimed=200 done=91 no_image=0 error=109 assembled=91
     err_breakdown={'http_4xx_403': 87, 'http_4xx_410': 14, 'timeout': 8}
   ```
3. Commit: `feat(met): histogram error classes per batch (D2)`.

Risk: zero (logging only).

### P-H1 -- Explicit `autocommit=False` + `BEGIN/COMMIT`

**Goal:** assemble + callback are a real transaction.

Steps:
1. `extraction/met/snowflake_uploader._snowflake_connect`: add
   `autocommit=False` to `snowflake.connector.connect(...)`.
2. `extraction/met/control_enricher._process_one_batch`:
   - Wrap `_assemble_and_callback` in `cur.execute("BEGIN")` / `commit` /
     `rollback` on except.
   - Re-order the except path:
     `sf_conn.rollback(); _release_unfinished(cur, config, batch_id);
     sf_conn.commit(); raise`.
3. `extraction/met/control_seeder.seed_control`:
   - Open a transaction around `_log_start` + MERGE + `_log_finish` (success)
     so a MERGE failure rolls back the open EXTRACTION_LOG row; in the except
     branch, rollback then explicitly insert a `failed` log row + commit.
4. `extraction/met/snapshot_loader.load_snapshot`:
   - Each chunk PUT/COPY in its own committed unit (already effectively true);
     the final MERGE in its own committed unit. Don't try to span chunks; the
     idempotent MERGE plus PK already gives re-runnability.
5. Commit: `fix(met): autocommit=False + explicit BEGIN/COMMIT (H1)`.

Risk: medium. Test on a small slice first. The connector behavior under
`autocommit=False` differs subtly for DDL-like statements; PUT, COPY, MERGE,
UPDATE all support transactions in Snowflake.

### P-H2 -- DATA-01 deaccession sweep

**Goal:** vanished CSV rows propagate as deletes through the medallion.

Steps:
1. New SQL template: `extraction/met/sql/delete_vanished_snapshot.sql` -- only
   safe when staging holds the FULL CSV:
   ```
   DELETE FROM {target}
    WHERE object_id NOT IN (SELECT object_id FROM {stg});
   ```
2. `extraction/met/snapshot_loader.load_snapshot`: only execute the deletion
   when `limit is None` (full-CSV load) AND no `--no-refresh` (i.e. we are
   sure the stage reflects the CURRENT upstream truth). Log the delete count;
   include in EXTRACTION_LOG records_loaded breakdown
   (`inserted+updated, deleted`).
3. Cascade choice (owner decision -- gated, do not apply):
   - (a) cascade: also `DELETE FROM MET_ENRICHMENT_CONTROL WHERE object_id IN
     (deleted)` and `DELETE FROM RAW_MET_OBJECTS WHERE object_id IN
     (deleted)`.
   - (b) soft-delete + dbt SCD-2: add `_deleted_at TIMESTAMP_NTZ` columns to
     all three tables; flip them rather than DELETE; let Silver / Gold hide
     deleted rows via WHERE.
   The owner cares about timeliness, so (a) is the simplest correct answer
   today; (b) is the dbt-forward answer once Silver lands.
4. Commit: `feat(met): DATA-01 deaccession sweep on full snapshot (H2)`.

Risk: high if applied during a partial CSV load; the `limit is None` gate is
load-bearing. Add an `assert` in Python and a runbook note.

### P-H3 -- Switch paramstyle to qmark

**Goal:** retire the entire pyformat `%`-binding bug class.

Steps:
1. `extraction/met/snowflake_uploader.py` (or move to `db.py` once L1 lands):
   at module top, after the `import snowflake.connector`, add
   `snowflake.connector.paramstyle = "qmark"`.
2. Migrate all `%s` to `?` in: `seed_enrichment_control.sql:37`,
   `claim_worklist.sql:21`, `control_seeder.py` inline EXECs (lines 84, 98,
   143), `control_enricher.py` inline EXECs (lines 71, 74, 174, 188, 202),
   `snapshot_loader.py` inline EXECs (lines 222, 234).
3. Remove `strip_sql_comments` calls (no longer needed for safety, but harmless
   to keep). Remove the function in a follow-up.
4. Commit: `refactor(met): switch connector paramstyle to qmark (H3)`.

Risk: medium. Snowflake connector supports both. Test with a smoke run after
the change; the failure mode if a `%s` is missed is a parameter count
mismatch at execute time -- loud and immediate.

### P-H4 -- Gate the `--where` escape hatch

Steps:
1. `extraction/met/run.py` `seed-control` parser: add `--where`. (Currently
   only `--department` / `--include-non-public-domain` / `--limit`.)
2. `extraction/met/control_seeder.seed_control`: refuse if `where` is set and
   `os.getenv("MET_ALLOW_RAW_WHERE") != "1"`. Log at WARN.
3. Commit: `chore(met): gate --where escape hatch behind env flag (H4)`.

Risk: zero.

### P-L1 -- Delete legacy SQLite path

**Goal:** remove dead code; one source of truth.

Steps:
1. Delete files: `extraction/met/image_enricher.py`,
   `extraction/met/sql/update_enrichment_done.sql`,
   `extraction/met/csv_bootstrap.py` (after migrating `_iter_csv_rows` into
   `snapshot_loader.py` -- it is the only consumer remaining), `rename_and_update.py`
   at repo root.
2. `extraction/met/db.py`: keep `load_sql` and `strip_sql_comments`; drop
   `connect`, `initialize_database` (sqlite); add `_snowflake_connect` here
   (move from `snowflake_uploader.py`).
3. `extraction/met/snowflake_uploader.py`: delete the SQLite-authoritative
   upload path and stale docstring; if the file becomes empty, delete it.
4. `extraction/met/run.py`: remove `bootstrap`, `enrich`, `upload`, `status`,
   `all` subcommands.
5. Commit: `chore(met): drop legacy SQLite path; Option B is canonical (L1)`.

Risk: medium. Read every line of `csv_bootstrap.py` once more before deleting
-- some helpers may be used by `snapshot_loader`. Already verified: `_iter_csv_rows`
is the only cross-module helper.

---

## 6. Suggested order of operations

Owner's call, but my recommendation:

1. **P-D1** first -- tells us why the 109 failed.
2. **P-D2** with it.
3. Re-run `enrich-met --limit 200`. Read the histogram and the error column.
4. **P-B1** -- pure cleanup, removes risk of the wrong file being touched.
5. **P-B2** -- doc reword; closes the convention-violation framing.
6. **P-H1** -- transactional correctness before more enrichment volume.
7. **P-H4** -- defensive (one-line CLI gate).
8. **P-H3** -- once the pipeline is stable, retire the pyformat class.
9. **P-H2** -- needs an owner decision on cascade vs SCD-2; do AFTER initial
   enrichment runs are clean.
10. **P-L1** -- last, when nothing else points at the legacy code.

Each PR carries one logical change per CLAUDE.md "one logical commit per unit
of work."
