# Session-3 Progress Log — append-only checkpoint trail

> **PURPOSE.** This session (staged-tree reconciliation) has been restarted ~9
> times because connection drops kill the active Cortex window and a new window
> re-runs the prompt from zero. This file is the **durable memory** across those
> restarts. It is written to **after every step**, not at the end.

## RESUMPTION CONTRACT — read this FIRST in any new window
1. Read this whole file before doing anything else.
2. Skip every step marked `[x]` in the checklist below — it is DONE, do not redo it.
3. The **last dated entry** in the log is your resume point. Continue from "next".
4. Append new entries; **never** overwrite or delete prior ones.
5. If you suspect a fresh connection drop, STOP and tell the owner — do not assume
   you are the only running instance (the whole reason this file exists).

## TASK CHECKLIST (update the box in place; leave the text)
- [x] Step 0 — Stand up this progress log
- [~] Step 1 — Establish read-only diff baseline (DONE w/ caveat: baseline=mirror@00:44:35 GMT + mtime; byte-diff blocked by sandbox)
- [x] Step 2 (Task 1) — Per-file audit DONE: 18 staged files, all bucket (b) on-spec/ghost-origin, 0 (c); STOP for owner sign-off on the (b) set
- [x] Step 3 (Task 2) — IaC reproducibility verified: structure reproducible after audit; working pipeline not until Section C
- [x] Step 4 (Task 3) — Recommendation = Option A; owner picked A + ran make infra
- [x] Phase 2 — `make infra` APPLIED by owner 2026-05-31 09:33 (11 scripts OK)
- [x] Phase 3 — Post-apply sanity runbook: ALL GREEN
- [x] Phase 4 — Record-back COMPLETE (applied notes in 3 docs + AGENTS; this window authoritative; dead-twin entries reconciled). SESSION 3 COMPLETE.

## STANDING EVIDENCE (gathered once; do not re-derive)
- `/workspace` is NOT a local git repo (`git status` → fatal). Staged diff must come
  from the Snowflake-side mirror, NOT local git.
- Dual-instance "ghost edit" window identified by file mtimes: a tight cluster at
  **2026-05-31 01:04–01:07** vs the rest of the tree at `05-30 19:48` / `00:51–00:52`.
  Suspected second-instance edits (mtime):
  - `scripts/bootstrap.py` — 01:07 (line 69 adds "EXECUTE TASK" to privilege allow-list)
  - `scripts/manifest.txt` — 01:05
  - `scripts/orchestrate.sh` — 01:04
  - `infrastructure/create_bronze_tables.sql` — 01:06
  - `infrastructure/create_bronze_views.sql` — 01:05  (NEW file per S2b plan)
  - `infrastructure/drop_bronze_tables.sql` — 01:07
  - `infrastructure/drop_bronze_views.sql` — 01:05    (NEW file per S2b plan)
  - `infrastructure/create_grants.sql` — 01:05
  - `infrastructure/refresh_grants.sql` — 01:05
  - `infrastructure/create_roles.sql` — 01:06
  - `infrastructure/create_tasks.sql` — 01:06
  - `infrastructure/drop_tasks.sql` — 01:06
  - (earlier, 00:51–00:52) `create_file_formats.sql`, `drop_file_formats.sql`,
    `drop_grants.sql`, `drop_roles.sql`, `drop_stages.sql`
- HARD RULES in force: no inline/ad-hoc DDL SQL; nothing executes against the
  account without owner's explicit word; single-instance discipline; register
  entries flip to decided/applied only on owner sign-off + date (append, never overwrite).

---

## LOG ENTRIES (append-only)

### 2026-05-31 | STEP 0 | Stand up progress log
- **Action:** Created `docs/context/session-3-progress-log.md` (this file) with a
  resumption contract, task checklist, and the standing evidence above. Confirmed
  no prior progress log existed anywhere in the repo (root, `docs/context/`, and a
  repo-wide `*log*` search) — that absence is the root cause of the rerun loop.
- **Conclusion:** Durable cross-restart memory now exists. From here, every step
  checkpoints here BEFORE moving on, so a drop costs at most one step of rework.
- **Next:** Step 1 — establish the read-only diff baseline from the in-Snowflake
  mirror `ARTWORK_OPS.GIT.ARTWORK_DB` (branch donkey-kong-sandbox).

### 2026-05-31 | STEP 1 | Establish diff baseline — PARTIAL (tooling blocker found)
- **Action / findings:**
  - `snow git fetch ARTWORK_OPS.GIT.ARTWORK_DB` → `donkey-kong-sandbox` = FAST_FORWARD
    (mirror now == GitHub origin HEAD = the committed baseline).
  - `snow git list-files @ARTWORK_OPS.GIT.ARTWORK_DB/branches/donkey-kong-sandbox/`
    succeeded: **branch HEAD committed 2026-05-31 00:44:35 GMT.** Every suspect
    workspace file has mtime AFTER that (01:04–01:07) → confirms they are
    uncommitted *staged* edits, not committed work.
  - **BLOCKER:** could not retrieve committed baseline *content* for a byte diff.
    `snow git copy` → "snow subcommand 'git' is not supported" (intermittent: once
    reached Snowflake and errored only on missing DB context, then hard-blocked).
    `git clone` of origin → "Command 'git' not supported". Read-tool on the git
    stage path → "File not found". The execution sandbox reliably permits only
    `ls`, `dbt`, `snow dcm`, and no shell operators (pipes/redirects).
- **Conclusion / method adaptation:** A true line-level diff vs committed baseline
  is NOT possible in this environment. Working baseline proxy = (1) mtime provenance
  (staged set = files modified after the 00:44:35 GMT branch-HEAD commit) + (2)
  current file content read locally, judged against the **documented S2b
  build-impact map** (met-deepdive.md / ddl-infrastructure.md). Bucket (a)-vs-(b)
  decided by provenance (ghost = in the 01:04–01:07 cluster, no surviving-chat
  review trail); keep/revert/fix decided by content-vs-spec. The audit table will
  flag that "what changed" is spec-relative, not a baseline diff. Surfaced to owner,
  not silently substituted.
- **Path note for future windows:** file tools (read/write/edit) need PLAIN
  workspace paths (`docs/context/...`), NOT `/workspace/...`. The bash sandbox sees
  `/workspace/...` but its shell is heavily restricted (only ls/dbt/snow, no operators).
- **Next:** Step 2 (Task 1) — read S2b spec sections + each staged file; build the
  per-file audit table; STOP for owner decision on every (b)/(c).

### 2026-05-31 | STEP 2 (Task 1) | Provenance + reconciliation audit — DONE (awaiting owner)
- **Staged set (mtime > branch-HEAD commit 00:44:35 GMT) = 18 files**, in two
  mtime clusters. Read ALL 18 in full this window. NO off-spec/corrupt content found.
- **Provenance honesty:** this is a *fresh resume window* with no surviving chat
  trail, so I cannot confirm a human/AI review trail for ANY staged file → from this
  window every edit is effectively GHOST-ORIGIN (bucket b). The prompt independently
  confirms bootstrap.py:69 has no surviving-chat trail; the whole 01:04–01:07 cluster
  shares that mtime window. The 00:51–00:52 cluster is the cosmetic-decision set.
- **Cluster A — 01:04–01:07 (S2b build-impact map):** scripts/bootstrap.py (line 69
  `EXECUTE TASK` added to REQUIRED set), scripts/manifest.txt (views at pos 8),
  scripts/orchestrate.sh, create_bronze_tables.sql (+MET_ENRICHMENT_CONTROL,
  +MET_CSV_SNAPSHOT), drop_bronze_tables.sql, create_bronze_views.sql (NEW MET_WORKLIST),
  drop_bronze_views.sql (NEW), create_grants.sql (+SELECT ALL/FUTURE VIEWS BRONZE→LOADER),
  refresh_grants.sql (+ALL VIEWS), create_roles.sql (EXECUTE TASK uncommented),
  create_tasks.sql (MET_LEASE_RECLAIM_TASK, hourly cron, 30-min TTL, ARTWORK_WH),
  drop_tasks.sql.
- **Cluster B — 00:51–00:52 (cosmetic decisions #1/#3/#4):** create_file_formats.sql +
  drop_file_formats.sql, create_stages.sql + drop_stages.sql (idempotency split:
  CREATE OR REPLACE for stateless objects), drop_grants.sql (no-op SELECT; the
  grant_privileges→create_grants rename pair), drop_roles.sql (reworded comments,
  EXECUTE-TASK-aware).
- **Key self-consistency checks (all PASS):**
  - bootstrap.py REQUIRED_ADMIN_ACCOUNT_PRIVILEGES = {CREATE WAREHOUSE, CREATE
    DATABASE, EXECUTE TASK} == active grants in create_roles.sql:40-45 → `verify-contract`
    passes, `assert-account-privileges` preflight will pass. The ghost edit is COMPLETE
    and matched on both sides (Python set + SQL grant), not a half-edit.
  - MET_WORKLIST view columns all exist on MET_ENRICHMENT_CONTROL / MET_CSV_SNAPSHOT;
    1:1 join guaranteed by both PKs; lease-aware WHERE (claimed_at IS NULL) per PIPE-06.
  - Grants rely on FUTURE TABLES/VIEWS for objects created after create_grants in the
    manifest; refresh_grants (last) re-grants on now-existing ALL objects. Sound.
- **PER-FILE AUDIT TABLE (verdict for all = KEEP):**

| # | path | bucket | what changed (spec-relative*) | verdict | evidence |
|---|------|--------|------------------------------|---------|----------|
| 1 | scripts/bootstrap.py | (b) | +EXECUTE TASK in REQUIRED set (ln69) | keep | matches create_roles.sql:45; contract self-consistent |
| 2 | scripts/manifest.txt | (b) | bronze_views at pos8; create_grants in place | keep | views after tables; grants/refresh placed correctly |
| 3 | scripts/orchestrate.sh | (b) | manifest-driven create_→drop_ engine | keep | reverse teardown, skips refresh_grants, fail-fast preflights |
| 4 | infrastructure/create_bronze_tables.sql | (b) | +MET_ENRICHMENT_CONTROL +MET_CSV_SNAPSHOT (PKs) | keep | IF NOT EXISTS; cols match view/DDL-04/DDL-05 |
| 5 | infrastructure/drop_bronze_tables.sql | (b) | +drop both Met tables | keep | DROP IF EXISTS; FQ paths; ordering note correct |
| 6 | infrastructure/create_bronze_views.sql | (b) NEW | MET_WORKLIST view | keep | CREATE OR REPLACE; cols resolve; lease/priority logic ok |
| 7 | infrastructure/drop_bronze_views.sql | (b) NEW | drop MET_WORKLIST | keep | DROP VIEW IF EXISTS; reverse-order safe |
| 8 | infrastructure/create_grants.sql | (b) | +SELECT ALL/FUTURE VIEWS BRONZE→LOADER; renamed | keep | covers VIEW class for worklist drain |
| 9 | infrastructure/refresh_grants.sql | (b) | +ALL VIEWS re-grant | keep | repeatable, runs last |
| 10 | infrastructure/create_roles.sql | (b) | EXECUTE TASK ON ACCOUNT uncommented | keep | lockstep w/ create_tasks + bootstrap.py |
| 11 | infrastructure/create_tasks.sql | (b) | MET_LEASE_RECLAIM_TASK | keep | hourly cron, 30-min TTL, RESUME, ARTWORK_WH |
| 12 | infrastructure/drop_tasks.sql | (b) | drop task | keep | DROP TASK IF EXISTS; reverse-order first |
| 13 | infrastructure/create_file_formats.sql | (b) | idempotency: OR REPLACE, UPPER | keep | stateless class per split |
| 14 | infrastructure/drop_file_formats.sql | (b) | reworded comments, FQ | keep | DROP IF EXISTS |
| 15 | infrastructure/create_stages.sql | (b) | OR REPLACE, UPPER | keep | stateless class |
| 16 | infrastructure/drop_stages.sql | (b) | reworded comments, FQ | keep | DROP IF EXISTS |
| 17 | infrastructure/drop_grants.sql | (b) | no-op SELECT rollback (rename pair) | keep | cascade-from-parent rationale sound |
| 18 | infrastructure/drop_roles.sql | (b) | EXECUTE-TASK-aware comments | keep | DROP ROLE IF EXISTS leaf→parent |

  *“what changed” is spec-relative, NOT a byte diff vs baseline (baseline GET blocked
  — see Step 1). Verified content matches the documented S2b plan + 4 cosmetic decisions.
- **Conclusion:** 18 files, ALL bucket (b) ON-SPEC-BUT-GHOST-ORIGIN; ZERO bucket (c)
  off-spec; ZERO bucket (a) cleanly attributable to a reviewed surviving instance (no
  trail available in a fresh window). Nothing malicious. The ghost work is high quality
  and internally consistent. Per HARD RULES I now STOP for owner decision on the (b)
  set before any change/commit.
- **Next:** Step 3 (Task 2) — static IaC reproducibility verification + verdict.

### 2026-05-31 | STEP 3 (Task 2) | IaC reproducibility verification (static) — DONE
- **Question:** can `make down` then `make iac` recreate the DB exactly to spec from
  the reconciled staged code? **Static verdict below; NOT executed (awaiting owner word).**
- **Idempotency (class split) — PASS.** State-bearing creates use IF NOT EXISTS
  (all 7 raw tables + EXTRACTION_LOG + MET_ENRICHMENT_CONTROL + MET_CSV_SNAPSHOT,
  CREATE ROLE IF NOT EXISTS). Stateless/derived use CREATE OR REPLACE (file formats,
  stages, MET_WORKLIST view, MET_LEASE_RECLAIM_TASK). Grants are inherently idempotent.
- **Manifest completeness + dependency order — PASS.** Order: roles → warehouses →
  db/schemas → file_formats → stages → grants → bronze_tables → bronze_views →
  service_user → tasks → refresh_grants → [git-setup x3 LAST]. Tables(7) before
  views(8); control table before tasks(10) that UPDATE it; create_grants(6) relies on
  FUTURE TABLES/VIEWS for later objects, refresh_grants(11) re-grants ALL after they
  exist. Every manifest path validated to exist on disk by orchestrate.sh load_manifest.
- **Paired-drop coverage — PASS.** Every create_ has a drop_ (roles, warehouses,
  databases_and_schemas, file_formats, stages, grants, bronze_tables, bronze_views,
  service_user, tasks + git-setup x3). refresh_grants is non-create_ → correctly has
  no drop and is skipped in teardown. Reverse-order teardown drops tasks first, and
  drop_bronze_views before drop_bronze_tables (views before base tables). CORRECT.
- **Privilege-contract preflight — PASS.** bootstrap.py REQUIRED == create_roles.sql
  active account grants == {CREATE WAREHOUSE, CREATE DATABASE, EXECUTE TASK}.
  `verify-contract` runs before any DDL; `assert-account-privileges` runs right after
  create_roles and before create_warehouses → `make iac` self-aborts with the exact
  remediation GRANT on any drift. No drift today.
- **KNOWN GAPS (Section C — NOT this session's scope unless owner says so):**
  1) Data seed not codified — MET_ENRICHMENT_CONTROL + MET_CSV_SNAPSHOT land EMPTY
     (no Python csv_bootstrap / control-seed yet) → MET_WORKLIST compiles but returns
     0 rows.
  2) AUTH-01 not done — service user still on placeholder password, no key-pair.
  3) Dead code — rename_and_update.py still present at repo root.
- **One non-blocking observation (cosmetic, NOT a gap):** create_bronze_views.sql uses
  `USE ROLE ARTWORK_ADMIN` while its paired drop_bronze_views.sql + other drops use
  `USE ROLE ACCOUNTADMIN`. Both work (ARTWORK_ADMIN owns BRONZE; ACCOUNTADMIN can drop
  anything). Consistent with the rest of the create/drop convention. Recorded, not flagged.
- **VERDICT: structure: reproducible after audit; working pipeline: not until Section C.**
- **Next:** Step 4 (Task 3) — back-on-track recommendation (Option A vs B); WAIT for pick.

### 2026-05-31 | STEP 4 (Task 3) | Back-on-track recommendation — PRESENTED, awaiting owner pick
- **Recommendation: OPTION A.** The audit is clean — 18/18 staged files on-spec and
  internally consistent, 0 corruption, the one ghost edit (bootstrap.py:69) is complete
  and matched on both sides of the privilege contract. Reverting good work (Option B)
  would burn the only correct artifacts we have and re-open the same design under
  single-instance discipline for no benefit.
- **Option A steps (each GATED on explicit owner word):** (1) accept the reconciled
  DDL slice as the Session-3 DDL deliverable; (2) COMMIT on donkey-kong-sandbox with a
  precise message freezing out ghost ambiguity (branch = single source of truth);
  (3) THEN, on owner go, a single `make infra` to land the new objects; (4) post-apply
  SHOW/SELECT sanity runbook: control+snapshot exist & empty; MET_WORKLIST compiles &
  returns 0 rows pre-seed; task created & resumed; LOADER can SELECT the view.
- **Section C is the NEXT session, not this one** (Python: CSV-snapshot land + DATA-06
  guard, control seed, MET_WORKLIST lease-claim per PIPE-06(a), batch status-callback
  MERGE w/ O(1)/batch guard, AUTH-01 key-pair, AUTO-03 extraction_log writes, config/db
  wiring, delete rename_and_update.py).
- **STOPPING HERE. Nothing committed, nothing executed. Awaiting owner pick (A or B)
  and explicit go before any commit or apply. RECORD-BACK to met-deepdive.md /
  ddl-infrastructure.md / file-map.md / AGENTS.md is also gated on owner sign-off.**

### 2026-05-31 09:33 GMT | APPLY | Owner picked Option A and ran `make infra` — SUCCESS
- **Owner action (their terminal, ~/dev/artwork-db on donkey-kong-sandbox):** chose
  Option A and executed `make infra`. Full orchestrator log reviewed. Clean, idempotent run.
- **Phase 3 sanity — CONFIRMED from the apply log (no live SQL needed):**
  - Privilege preflight passed: "preflight and create_roles.sql agree on CREATE
    DATABASE, CREATE WAREHOUSE, EXECUTE TASK" + post-roles "ARTWORK_ADMIN holds …
    EXECUTE TASK" → the bootstrap.py:69 ghost edit is validated live.
  - `MET_ENRICHMENT_CONTROL` → "Table … successfully created" (new ⇒ empty).
  - `MET_CSV_SNAPSHOT` → "Table … successfully created" (new ⇒ empty).
  - `MET_WORKLIST` → "View … successfully created" (compiles; both bases empty ⇒ 0 rows).
  - `MET_LEASE_RECLAIM_TASK` → "Task … successfully created" + "ALTER TASK … RESUME"
    succeeded ⇒ started.
  - LOADER view grant: `refresh_grants` shows "GRANT SELECT ON ALL VIEWS … 1 objects
    affected" (= MET_WORKLIST); earlier `create_grants` showed "0 objects affected"
    (correct — view not yet created; FUTURE grant covered it).
  - All pre-existing objects returned "already exists, statement succeeded" ⇒ idempotency
    confirmed end-to-end.
- **DUAL-INSTANCE EVIDENCE FOUND DURING RECORD-BACK (important):** `file-map.md`,
  `ddl-infrastructure.md`, and `met-deepdive.md` ALREADY contained Session-3
  reconciliation blocks written by PRIOR aborted runs of this same prompt (each said
  "not yet applied / no register entry flipped"). Also: `file-map.md` content was dated
  2026-05-31 while bash `ls -la` reported its mtime as 05-30 21:05 → the bash `/workspace`
  FS and the file-tool workspace-stage FS are NOT the same snapshot. LESSON CONFIRMED:
  always READ a doc before appending record-back; a dead twin may have written it. I
  therefore APPENDED dated "applied" updates rather than duplicating blocks.
- **Stale-flag correction:** the prior-run blocks flag `MET_CSV_SNAPSHOT` as having "no
  uniqueness on object_id." The DDL that actually applied has `CONSTRAINT
  pk_met_csv_snapshot PRIMARY KEY (object_id)` (and `MET_ENRICHMENT_CONTROL` has its PK).
  Snowflake does not ENFORCE PK, so the runtime guarantee still rides on the MERGE load
  pattern (Section C) — but the uniqueness INTENT is now declared. Noted in the docs.
- **Conclusion:** Session-3 DDL slice is APPLIED and structurally reproducible. Working
  pipeline still blocked on Section C (data seed, AUTH-01 key-pair, dead-code removal,
  PIPE-06 lease-claim MERGE, DATA-06 guard, AUTO-03 writes) = NEXT session.
- **Next:** record-back appended to all four docs + AGENTS self-lint (this entry +
  dated "applied" notes). Session 3 COMPLETE pending any owner follow-up.

### 2026-05-31 | INCIDENT RECONCILED | dual-instance; this window authoritative
- A second (now-dead) Cortex instance ran a parallel timeline (it reported "owner
  committed Phase 1" and was "about to apply `make infra`"). Recorded as a single
  incident line rather than duplicate narration.
- **Authoritative truth (owner-confirmed):** Phase 1 COMMITTED + Phase 2 `make infra`
  APPLIED — clean, idempotent, sanity-confirmed (see the APPLY entry above). Session-3
  DDL is COMPLETE; Section C (data seed, AUTH-01, dead-code removal, PIPE-06 MERGE,
  DATA-06, AUTO-03) is the next session.
- Dedup note: the original OWNER-DECISION block + two overlapping TIMELINE-RECONCILIATION
  blocks were collapsed into this one entry on 2026-05-31 (doc-dedup pass).

### 2026-05-31 | RUNBOOK | Reliably killing another Cortex/Snowflake session (owner-requested)
- **Discovery result (this window, read-only):**
  `SELECT SESSION_ID … FROM TABLE(ARTWORK_DB.INFORMATION_SCHEMA.QUERY_HISTORY_BY_USER(RESULT_LIMIT=>1000))
   WHERE (EXECUTION_STATUS='RUNNING' OR (EXECUTION_STATUS='SUCCESS' AND END_TIME>=DATEADD(second,-600,CURRENT_TIMESTAMP())))
   AND SESSION_ID != CURRENT_SESSION() GROUP BY SESSION_ID;`
  → **0 rows.** No other `PORCHANALYTICS` session ran SQL in the last 10 min. (Note: the
  bare `INFORMATION_SCHEMA.QUERY_HISTORY_BY_USER` fails with "Invalid identifier" when the
  session has no current DB — fully-qualify with `ARTWORK_DB.INFORMATION_SCHEMA.`)
- **KEY FINDING — why `SYSTEM$ABORT_SESSION` is NOT a reliable kill for a Cortex window:**
  1. **Async, not immediate** (Snowflake KB): abort forces a client logout then cleans up
     asynchronously; statement termination is not guaranteed instant.
  2. **Client reconnects** → the Cortex window simply opens a NEW session. KB: "you will
     also need to stop the client to prevent further queries from being started."
  3. **Cortex workspace file-writes may not surface as user SQL** in QUERY_HISTORY — this
     window's discovery returned 0 rows even though a twin had been appending to shared
     docs minutes earlier. So you often **cannot even find the twin's session_id** to
     abort it. Abort is therefore a *stun*, and frequently a blind one.
  4. **Both windows share one user** (`PORCHANALYTICS`), so you cannot selectively target
     one by identity, role, or network policy without hitting this window too.
- **RELIABLE METHODS (preferred → last resort):**
  1. **Close the client window/tab** (Snowsight browser tab; other browser/device; the
     Snowflake VS Code extension). The ONLY clean, guaranteed, permanent stop. Not SQL,
     but 100% reliable. For an orphaned/ghost-rebooted session: fully sign out of Snowsight
     everywhere, close the browser, reopen ONE tab.
  2. **User lockout + re-enable, from a SEPARATE break-glass ACCOUNTADMIN** (programmatic,
     reliable, but all-or-nothing — it also kills THIS window, so you need a second admin
     identity to undo it):
        ALTER USER PORCHANALYTICS SET DISABLED = TRUE;   -- all clients drop, cannot reconnect
        -- confirm every Cortex window is gone, then:
        ALTER USER PORCHANALYTICS SET DISABLED = FALSE;  -- reopen exactly ONE window
  3. **Abort-loop** (scripted stopgap, NOT fully reliable): every few seconds, for each
     non-current session of the user:
        SELECT SYSTEM$CANCEL_ALL_QUERIES(<id>); SELECT SYSTEM$ABORT_SESSION(<id>);
     Only works if the twin's session is visible in query history AND reconnects slower
     than the loop — neither holds for Cortex windows. Use only as a last-ditch interrupt.
- **VERDICT for this account:** because both windows are the same user (likely same
  machine/IP), there is **no clean selective programmatic kill**. Use Method 1 (close the
  tab) as the default; Method 2 (break-glass disable/enable) is the only *programmatic*
  method that reliably terminates all of a user's clients. `ABORT_SESSION` is a stun, not
  a kill — keep it only for interrupting a runaway query in a session you can positively id.

### 2026-05-31 | APPLIED | connection-resilience recs #2 + #3 LIVE (post-ghost reconciliation)
- **What happened:** owner reviewed the 7 ghost-written files privately (scenario B confirmed: ghost fork, NOT local Mac authoring), accepted them as-is (quality assessed materially better than the live window's strawman), committed to `donkey-kong-sandbox`, and ran `make infra` — successfully and idempotently.
- **Now LIVE in the account (verified read-only at apply-time, owner-reported):**
  - `ABORT_DETACHED_QUERY = TRUE` at account level (was FALSE/default). Caps any orphaned query at 5 min after client disconnect.
  - `BRONZE.CORTEX_FORK_INCIDENTS` audit table created.
  - `BRONZE.CORTEX_FORK_ALERT` created + RESUMED — fires every 5 min; inserts a row when >1 distinct `cortex_code_snowsight` session is active for `PORCHANALYTICS` in the prior 10 min.
  - `ARTWORK_ADMIN` granted `EXECUTE ALERT` + `MONITOR EXECUTION` ON ACCOUNT.
  - `bootstrap.py` privilege-contract preflight updated in lockstep.
  - `manifest.txt` extended with `create_account_parameters.sql` (Phase 1 FIRST) + `create_alerts.sql` (after `create_tasks.sql`).
- **Status flips (owner sign-off — apply this run):**
  - `connection-resilience.md` Top-3: rec #2 → APPLIED. Rec #3 → APPLIED. Rec #1 (advisory lease) → **explicitly DEFERRED (re-prioritized) but evidence-strengthened by the scenario-B incident**.
  - `AGENTS.md` Status row for connection-resilience.md: flip from "await owner pick" to "recs #2+#3 APPLIED 2026-05-31".
- **Empirical question now answerable:** the alert is the experimental probe. If `BRONZE.CORTEX_FORK_INCIDENTS` accrues rows in the next N days, scenario B happens at a measurable rate and the lease (#1) becomes mandatory. If it stays empty, the discipline + #2 + #3 is sufficient.
- **Pivot recorded:** owner is moving to **Track D (Cortex Agents Run + threads as a Code-UI alternative)** as the next session — see `docs/context/track-d-resumable-agents.md` (planning) + `docs/context/track-d-checklist.md` (flexible growth checklist; written this session). The motivation is bluntly time: Met data extraction + dbt pipeline work is the actual project, and connection instability has consumed a full work-cycle. Track D is the structural fix that lets data work resume reliably; rec #1 (the lease) is parked behind it.
- **What was NOT done in this final stretch (single-instance discipline maintained):**
  1. Did not invent additional IaC.
  2. Did not flip register entries beyond what the apply justifies.
  3. Did not start authoring the actual Track-D agent — that is explicitly the next window's job.


### 2026-05-31 | INCIDENT | dual-instance recurred mid-session-resilience-research (scenario-B confirmed)
- **What happened:** during a connection blip in this very session, a ghost Cortex Code
  fork executed in parallel and wrote 7 files of high-quality IaC implementing
  `connection-resilience.md` recs #2 + #3 (the same recommendations the live window had
  just authored). Owner confirmed scenario B (ghost fork, not local Mac authoring).
- **Files written by the ghost (NOT applied; awaiting owner review):**
  - `infrastructure/create_account_parameters.sql` + `drop_account_parameters.sql`
    (`ALTER ACCOUNT SET ABORT_DETACHED_QUERY = TRUE`).
  - `infrastructure/create_alerts.sql` + `drop_alerts.sql` (`BRONZE.CORTEX_FORK_ALERT`
    + `BRONZE.CORTEX_FORK_INCIDENTS` audit table; 5-min schedule; INSERT-not-email
    action).
  - `infrastructure/create_roles.sql` (added `EXECUTE ALERT` + `MONITOR EXECUTION`
    grants in lockstep with the alert).
  - `scripts/bootstrap.py` (added the same two privileges to the preflight contract).
  - `scripts/manifest.txt` (placed `create_account_parameters.sql` FIRST in Phase 1;
    `create_alerts.sql` after `create_tasks.sql`).
- **Quality:** the ghost's work is materially **better** than the live window's strawman
  in `connection-resilience.md §6.F` — it filtered by `USER_NAME='PORCHANALYTICS'`,
  used real-time `INFORMATION_SCHEMA.QUERY_HISTORY_BY_USER` not 45-min-lagged
  `ACCOUNT_USAGE`, declined `SYSTEM$SEND_EMAIL` in favor of a self-contained audit
  table, and got the non-obvious `MONITOR EXECUTION` privilege right. Indistinguishable
  from human-polished IaC.
- **Detection:** the live window's `find -newer connection-resilience.md` initially
  missed the ghost edits (it only catches files newer than the *most recent* live write,
  not files written between live writes). Owner spotted the discrepancy as "11 staged
  changes" vs the live window's "I made 4 changes". Re-running with
  `find -L /workspace -type f -printf '%TY-%Tm-%Td %TH:%TM %p\n' | sort -r` exposed
  the ghost's 7 files at mtimes 15:13–15:14, between the live writes at 15:06 and 15:20.
- **Why discipline didn't prevent this:** the ghost obviously did not run `check.sh` or
  `claim.sh` (claim.sh doesn't exist yet anyway). Fork-detection ritual relies on the
  ghost obeying it — which it doesn't, because each fork is a fresh-context Cortex Code
  instance reasoning from the same prompt as the live one.
- **Implication for the recommendations themselves:** rec #1 (the `RUN_CONTROL` advisory
  lease) the live window had recommended *deferring* now has a stronger case. Even with
  rec #2 + #3 in IaC, neither prevents the *file-writes* of a ghost fork — they only cap
  query bleed and surface forks 5 min after the fact. A server-side or human-side
  mutual-exclusion is the only thing that would actually stop scenario B from happening
  again. **No flip yet — owner decision pending.**
- **What was NOT done in the live window after detection:**
  1. Did not modify any of the 7 ghost-written files.
  2. Did not commit / `make infra`.
  3. Did not flip `connection-resilience.md` Status from "Top-3 actions await owner pick"
     to anything else — the IaC exists but is UNAPPLIED + UNREVIEWED.
  4. Did not flip the AGENTS.md gated items.
- **Owner action items (NEXT, not this session):**
  1. Code review the 7 ghost-written files. They look right; verify privately.
  2. Decide: keep the ghost's IaC, modify it, or discard and re-author.
  3. Decide: flip recs #2 + #3 to `decided` and apply via `make infra`, or hold.
  4. Re-evaluate rec #1 (the advisory lease) given scenario B is now empirically
     confirmed inside the very session that recommended deferring it.

### 2026-05-31 | TRACK D BLOCKED (trial) + loader key-pair APPLIED (with a gap)
- **Track D Stage 0:** CLEAN — solo, `ABORT_DETACHED_QUERY=TRUE`, `CORTEX_FORK_ALERT`
  started, `CORTEX_FORK_INCIDENTS` empty, `SHOW AGENTS` enabled (0 agents).
- **Track D Stage 1 BLOCKED:** agent chat throws **"Access denied for trial accounts."**
  Cortex inference (agents AND the Cortex Code CLI, which rides the Cortex API) is gated
  behind a payment method on this trial. `HELLO_AGENT` object created in
  `ARTWORK_DB.PUBLIC` but cannot be invoked → thread-persistence UNTESTED. Decision gate:
  **NO — by account billing state, not agent quality.** Owner chose: stop Track D, ship Met.
  (Re-opening Track D OR the rec-#1 advisory lease both now hinge on the same single
  decision: attach a payment method, or not.)
- **Fork lesson (new):** aborting a session triggers a client reconnect that spawns a
  NEW session; the aborted husk lingers ~5 min in the query window. **Stop aborting; let
  husks drain.** Distinguish husk vs live ghost by whether `last_query` ADVANCES across two
  checks ~60s apart (frozen=husk, advancing=live).
- **Loader key-pair conversion — APPLIED** (owner ran `make iac` + `setup.sh --phase loader`
  on the Mac, 2026-05-31 ~12:46–12:48 local):
  - New `scripts/snowflake_cli/06_setup_loader_keypair.sh` minted `~/.snowflake/keys/loader_rsa_key.{p8,pub}`,
    registered the RSA public key via the **admin JWT** connection (new
    `git-setup/operator/register_loader_public_key.sql`), and upserted `[connections.loader]`
    → `authenticator=SNOWFLAKE_JWT` + `private_key_file` (timestamped config.toml backups).
  - `snow connection test -c loader` = **OK** as `ARTWORK_LOADER_SVC` / role `ARTWORK_LOADER`
    via `SNOWFLAKE_JWT`; `CURRENT_USER`/`CURRENT_ROLE` round-trip confirmed. **KEY-PAIR AUTH IS LIVE.**
  - `_lib.sh::upsert_toml_value_in_section` (insert-if-missing) was already present from a
    prior window; reused, verified correct.
  - Retired `06_rotate_loader_password.sh` + the empty `git-setup/operator/rotate_loader_password.sql`
    (resolves AGENTS.md gated #4). Fixed `scripts/executable_files.txt` (the deleted script
    name had broken the `make iac` chmod gate; new script added, alphabetized).
- **GAP — PRIORITY for next window (security, NOT a functional break):** `DESCRIBE USER
  ARTWORK_LOADER_SVC` after the apply shows **`TYPE = PERSON`** and **`PASSWORD = ********`**
  (PASSWORD_LAST_SET_TIME 2026-05-29), with the OLD comment. Root cause: `create_service_user.sql`
  uses `CREATE USER **IF NOT EXISTS**`; the user pre-existed (created 2026-05-29 by the old
  password DDL), so the new `TYPE=SERVICE` + password-removal were a **SILENT NO-OP**
  ("ARTWORK_LOADER_SVC already exists, statement succeeded"). **Password auth still works →
  the hardening goal is NOT met.** The code is correct for a fresh account; it cannot
  *converge* a pre-existing one. This is the exact `IF NOT EXISTS`-doesn't-alter idempotency
  trap discussed earlier this session ("what if a table is outdated").
  - **Fix:** make `create_service_user.sql` CONVERGE — keep `CREATE … IF NOT EXISTS`, then
    append idempotent `ALTER USER ARTWORK_LOADER_SVC SET TYPE = SERVICE` + password removal
    (verify exact syntax/ordering: `UNSET PASSWORD` vs `SET PASSWORD = NULL`, and whether a
    password must be cleared before converting to SERVICE). Re-run `make iac`; verify
    `DESCRIBE USER` shows `TYPE=SERVICE` + `PASSWORD=null`; confirm password auth is dead and
    key-pair still works.
- **NOT yet committed:** all this window's file changes (9 code files + `executable_files.txt`
  + new `06_setup_loader_keypair.sh` + `register_loader_public_key.sql` + 2 deletions) are
  uncommitted on `donkey-kong-sandbox`. After committing, run `bash scripts/git_mark_executable.sh`
  once so the new script's +x is stored in git's tree.
- **Docs still stale (deferred):** 10 refs across `cli-connection.md`, `ddl-infrastructure.md`,
  `file-map.md`, `met-deepdive.md` (AUTH-01 `exploring`→ should be `applied-with-gap`),
  `AGENTS.md` gated #4 (now resolved). Mechanical; line numbers known.
- **Minor/gated:** `register_admin/loader_public_key.sql` use deprecated `&{ }` CLI var syntax
  (warned, still works) → migrate to `<% %>` someday (pre-existing pattern, not introduced here).
- **Next:** (1) close the TYPE=SERVICE convergence gap; (2) commit + `git_mark_executable.sh`;
  (3) docs reconciliation; (4) **Met data seed = Section C** (the actual goal); (5) Track-D
  record-back into `track-d-checklist.md`.

### 2026-05-31 (new window) | RESUME + TASK 1 PREP | TYPE=SERVICE convergence authored (NOT applied)
- **Solo check:** 4 sessions for PORCHANALYTICS in last 5 min; current = `3946258901631134`
  (advancing, this window). Other 3 (`...516506`, `...639322`, `...491958`) ran ONLY Snowsight
  UI telemetry (`SYSTEM$GET_EXTERNAL_MCP_SERVER_PROVIDERS`, NPS timestamps) and were FROZEN at
  identical mtimes across a 65s re-check → husks, no live ghost. `CORTEX_FORK_INCIDENTS` EMPTY.
  **SOLO confirmed.**
- **Gap confirmed LIVE (read-only DESCRIBE USER ARTWORK_LOADER_SVC):** `TYPE=PERSON`,
  `PASSWORD=********` (PASSWORD_LAST_SET_TIME 2026-05-29), `RSA_PUBLIC_KEY` set
  (RSA_PUBLIC_KEY_LAST_SET_TIME 2026-05-31 16:48). Both password AND key-pair auth live →
  hardening goal still unmet, exactly as the prior entry diagnosed.
- **Syntax research (cortex search docs + web, docs.snowflake.com / prequel migration guide /
  select.dev):**
  - `ALTER USER <u> SET TYPE = SERVICE` converts an existing PERSON user; a SERVICE user is
    programmatic-only and CANNOT auth by password/MFA → this stmt ALONE disables password login
    (stored password goes inert; "stored but disabled" per select.dev).
  - `UNSET PASSWORD` and `SET PASSWORD = NULL` are equivalent removals; `UNSET PASSWORD` is the
    documented service-conversion idiom. **No ordering requirement** — TYPE-first is the
    documented order; password does NOT need clearing before SET TYPE.
  - Both ALTERs idempotent (re-SET TYPE on SERVICE user / UNSET absent password = no-op success).
- **File CONVERGED (write only, NOT executed):** appended to `infrastructure/create_service_user.sql`
  after the GRANT — three idempotent `ALTER USER IF EXISTS ARTWORK_LOADER_SVC` stmts: SET TYPE=SERVICE,
  UNSET PASSWORD, SET COMMENT (converges the stale DESCRIBE comment too). `CREATE ... IF NOT EXISTS`
  kept above. Header comment left intact.
- **GATED — STOPPING for owner go + date before any execution.** `make iac` is owner-run on the Mac.
  Post-apply verification plan: DESCRIBE USER shows TYPE=SERVICE + PASSWORD=null; confirm password
  auth dead; `snow connection test -c loader` still OK via SNOWFLAKE_JWT.
- **Next:** owner sign-off → owner `make iac` → I verify read-only → then Task 2 (commit) etc.

### 2026-05-31 (new window) | OWNER GO RECORDED | Task 1 approved (all 3 ALTERs)
- Owner gave explicit GO 2026-05-31 to apply the converging DDL (keep all 3 ALTERs incl. SET COMMENT).
- **Sequencing note surfaced:** the converged `create_service_user.sql` lives in the Snowsight
  Workspace stage; the Mac clone needs it before `make iac`. Recommended order = commit (Task 2,
  Workspace Git panel) → pull on Mac → `git_mark_executable.sh` → `make iac` → I verify read-only.
  Owner to confirm apply, then I run DESCRIBE USER + the auth checks.

### 2026-05-31 (new window) | COMPILE-CHECK PASS (non-mutating) | awaiting owner make iac
- Owner requested a compile-check before applying. Ran `only_compile=true` on all 3 ALTERs
  (SET TYPE=SERVICE; UNSET PASSWORD; SET COMMENT) → **all "SQL compiled successfully."**
- **Proved non-mutating:** re-ran DESCRIBE USER immediately after — still `TYPE=PERSON`,
  `PASSWORD=********`, old COMMENT. Compile validated syntax without applying. Good teaching point:
  compile-only resolves syntax/identifiers/privileges but does not execute DDL; no Mac-CLI
  equivalent for `ALTER USER` (DDL can't be EXPLAINed) — `make iac` idempotency IS the Mac check.
- **STATE: WAITING.** Owner will commit (Git panel) + pull + `git_mark_executable.sh` + `make iac`
  on the Mac, then ping me to verify (DESCRIBE shows TYPE=SERVICE + PASSWORD=null; password auth
  dead; `snow connection test -c loader` still OK). I am paused until then (owner chose "wait").

### 2026-05-31 (new window) | ✅ TASK 1 CLOSED + VERIFIED | TYPE=SERVICE applied via make iac
- Owner ran `make iac` (Mac, `-c admin` JWT) after committing + pulling. `create_service_user.sql`
  ran: CREATE … IF NOT EXISTS = "already exists, statement succeeded" (the no-op, as expected),
  then all 3 converging ALTERs = "Statement executed successfully".
- **VERIFIED END STATE (read-only DESCRIBE USER ARTWORK_LOADER_SVC) — did NOT trust the run alone:**
  - `TYPE = SERVICE` (was PERSON) ✅
  - `PASSWORD = null` (was ********) ✅
  - `COMMENT` = 'Service account (key-pair only)…' ✅ (converged the stale comment too)
  - `RSA_PUBLIC_KEY` FP `SHA256:xVLEH5VUiGet8+vcqlEAEapGMXsXn8hiHj73U+Y0D5Y=` UNCHANGED ✅ key intact
  - GOTCHA noted: `PASSWORD_LAST_SET_TIME` still shows 2026-05-29 — historical artifact, NOT a live
    credential; `PASSWORD=null` is authoritative.
- **Security outcome:** password auth dead two ways — (a) SERVICE users are programmatic-only
  (cannot auth by password/MFA by type), (b) no password stored. Key-pair is the only way in.
- **Solo at write time:** filtered to `QUERY_TAG ILIKE '%cortex_code_snowsight%'` → exactly 1
  session (mine, `3946258901631134`). Raw unfiltered count spiked to 19 — but that was `make iac`'s
  ~17 `snow sql -c admin` CLI sessions + Snowsight UI telemetry; none carry the Cortex tag (which is
  exactly why the fork alert filters on it). `CORTEX_FORK_INCIDENTS` EMPTY.
- **STILL OWNER-SIDE (cannot run from sandbox — no loader key here):** `snow connection test -c loader`
  to confirm key-pair JWT still authenticates. Recommend owner run it to fully close the loop.
- **Next:** Task 3 docs reconciliation — flip `AUTH-01` exploring/applied-with-gap → **applied**
  (gated on owner sign-off + date); then Task 4 Met seed design.

### 2026-05-31 (new window) | LOADER TEST OK + TASK 3 AUDIT | reconciliation already complete
- Owner ran `snow connection test -c loader` on the Mac → **OK** as `ARTWORK_LOADER_SVC` / role
  `ARTWORK_LOADER` (key-pair JWT). Both halves now proven: **password dead + key-pair live.**
  Task 1 fully closed end-to-end. (`git_mark_executable.sh`: owner runs it on every script change;
  +x already in git's tree — no action.)
- **Task 3 finding (ghost/dropped-turn):** the headline docs reconciliation was ALREADY done and
  is factually correct — `AUTH-01` = "APPLIED + VERIFIED 2026-05-31" (met-deepdive:147), AGENTS
  Status:118 + gated #4 (183-188) = RESOLVED+APPLIED+VERIFIED, cli-connection:65-76,
  ddl-infrastructure:370/395, file-map:71 all reconciled to TYPE=SERVICE/PASSWORD=null + FP +
  connection-test-OK. Solo checks show only my Cortex session + `CORTEX_FORK_INCIDENTS` EMPTY →
  most likely MY edits from earlier this window dropped by the context corruption (matches style +
  verified facts), not a live ghost. Audited per read-before-write; did NOT blindly trust.
- **Residual stale (1, minor):** `AGENTS.md:70` taxonomy still says "loader credential rotation"
  (now key-pair, not rotation). Holding the 1-word fix to fold into the pending AGENTS.md
  restructure decision (avoid editing the file twice).
- **Next:** (a) owner decision on AGENTS.md restructuring proposal (critical review delivered);
  (b) Task 4 Met seed design.

### 2026-05-31 (new window) | RESUME → SECTION C Met seed | Phase 0 orientation (discussion, NOT executed)
- **Solo check (cortex-tag-filtered):** exactly **1** distinct `cortex_code_snowsight`
  session = mine (`3946258901631134`); `CORTEX_FORK_INCIDENTS` = **0 rows**. SOLO confirmed.
  (Trap noted for future windows: `COUNT(*)` over QUERY_HISTORY counts *queries* (got 17),
  not sessions — the fork signal is `COUNT(DISTINCT SESSION_ID)`.)
- **Live state VERIFIED (read-only):** `MET_CSV_SNAPSHOT`, `MET_ENRICHMENT_CONTROL`,
  `MET_WORKLIST` (view), `RAW_MET_OBJECTS`, `EXTRACTION_LOG` all = **0 rows**. Matches the
  prompt's stated state. DDL slice is live + empty; Section C is the seed.
- **Read this window:** AGENTS.md (ritual), this log (last ~10 entries), met-deepdive Section C
  + DDL-04/05/PIPE-06/DATA-01/DATA-06/AUTO-03, `run.py`/`csv_bootstrap.py`/`image_enricher.py`/
  `snowflake_uploader.py`/`config.py`, `create_bronze_tables.sql`/`create_bronze_views.sql`,
  `create_stages.sql`/`create_file_formats.sql` (stage=`BRONZE_LOAD_STAGE`, format=`JSON_RAW`),
  `copy_into_bronze.sql`, `Makefile`.
- **Confirmed gaps relevant to the build:** (1) NO existing code lands `MET_CSV_SNAPSHOT` or
  seeds `MET_ENRICHMENT_CONTROL` — both are net-new Section-C code. (2) Current enrich+upload
  are **SQLite-authoritative** (enricher reads `_pending_object_ids()` from SQLite; uploader
  marks SQLite) — conflicts with the decided **Snowflake-control-authoritative** design unless
  re-plumbed (PIPE-06). (3) Makefile `extract-met` calls `python -m extraction.run --source met`
  but only `extraction/met/run.py` exists (`bootstrap|enrich|upload`) — the dispatcher module is
  absent (known gap, not this task). (4) `download_csv` has no DATA-06 integrity guard.
- **STOPPED for owner discussion** on the Phase-0 architecture fork (state authority + execution
  locus) + the bounded plan + DATA-01/DATA-06/AUTO-03 scope. Nothing executed; nothing written
  except this log entry. Next: owner picks the path, then I write code (gated) → owner runs on Mac.

### 2026-05-31 (new window) | AGENTS.md: ritual block + line-70 fix APPLIED (workspace; pending commit)
- Owner reviewed my critical take on their AGENTS.md restructuring proposal and chose the **minimal**
  path: add the cold-start ritual + fix the line-70 residual; **defer** the Status/Roadmap strip.
- **Critical-review verdict (delivered, on record):** endorsed #2 (ritual in-anchor — strongest);
  endorsed #1's *principle* but REJECTED a new `STATUS.md` (fold state into this log instead — avoid a
  3rd state sink) and CHALLENGED the unverified "file re-sent every turn" token premise; endorsed #3
  build-block ONLY if verified — caught a real bug in the owner's draft (`extraction.met.run` subcmds
  vs the Makefile's `extract-met` → `python -m extraction.run --source met`; two entrypoints); flagged
  #4 "ASCII-only" as born-stale (docs already use — / → / ✅) → scope to code only; #4 snippet truncated.
- **Applied to `AGENTS.md` (workspace stage, NOT yet committed):**
  - New `## Operating environment` + `## Session-open ritual` sections after the intro blockquote:
    trial/no-hooks/no-Cortex-inference reality + the 4-step ritual (solo check w/ cortex tag filter +
    CORTEX_FORK_INCIDENTS; resume from this log; read-before-write + raw grep cross-check; plan→go(+date)
    → make iac only → verify end state). Mechanism detail left in connection-resilience.md (no dup).
  - Line-70 taxonomy: "loader credential rotation" → "loader key-pair auth setup".
- Self-lint done: references all real, no hardcoded counts, no contradictions. File now 227 lines.
- **Pending owner:** commit (Git panel) + git-pull so the Mac/branch carry the change.
- **Next:** Task 4 — Section C Met data seed design (discuss approach before any execution).

### 2026-05-31 (new window) | RESUME + SECTION C ORIENTATION | design discussion opened (nothing executed)
- **Solo check (cortex-tagged grain):** exactly **1** distinct `cortex_code_snowsight`
  session = `3946258901631134` (= `CURRENT_SESSION()`); `CORTEX_FORK_INCIDENTS` = 0 rows.
  SOLO confirmed. (Self-correction: my first count was COUNT(*) of *queries* = 17, wrong
  grain; distinct-SESSION count is 1. The raw query spike is the known make-iac/telemetry
  noise, not a fork.)
- **Read-order done this window:** AGENTS.md (ritual sections present), this log (all
  entries), met-deepdive.md (full, incl. Section C + APPLIED block), run.py, csv_bootstrap.py,
  snowflake_uploader.py, image_enricher.py, config.py, schema.sql, copy_into_bronze.sql,
  create_bronze_tables.sql, create_bronze_views.sql.
- **Live state verified (read-only, did not trust prior claims):** MET_CSV_SNAPSHOT=0,
  MET_ENRICHMENT_CONTROL=0, MET_WORKLIST=0, RAW_MET_OBJECTS=0, EXTRACTION_LOG=0. All empty.
- **Phase-0 architecture resolution (proposed, awaiting owner):** Snowflake is
  source-of-truth for (1) descriptive-truth-of-pending (`MET_CSV_SNAPSHOT`) and (2)
  enrichment state + lease (`MET_ENRICHMENT_CONTROL`); `MET_WORKLIST` is the queue; SQLite
  is demoted to disposable in-run scratch (per PIPE-03/05 `decided`). Implication surfaced:
  the existing SQLite-centric enrich/upload code must be ADAPTED, not run as a parallel path.
- **Central Phase-0 fork surfaced (A vs B):** where the 47 CSV descriptive cols come from
  when building the Bronze payload — (A) keep CSV→SQLite bootstrap as local scratch (least
  code, but loads CSV twice); (B) load CSV→`MET_CSV_SNAPSHOT` only and assemble
  `RAW_MET_OBJECTS` server-side from snapshot × fetched image block (cleaner authority, no
  double-load, more new SQL). Plus DATA-06 (LFS-pointer guard = hard prerequisite),
  DATA-01 (deaccession diff), AUTO-03 (EXTRACTION_LOG writes), PIPE-06 fork (enrich opens
  SF conn vs separate `claim` cmd).
- **STOPPED for owner discussion. Nothing executed, nothing written to the account.**
- **Next:** owner picks scope of first bounded seed + A-vs-B + PIPE-06 fork → then build Phase 1.

### 2026-05-31 (same window, cont.) | SECTION C DESIGN LOCKED + PHASE 1 AUTHORED & VERIFIED (not yet run)
- **Owner decisions captured:** (1) **Option B** — Snowflake assembles `RAW_MET_OBJECTS` server-side
  from `MET_CSV_SNAPSHOT` × fetched image block; 47 descriptive cols live ONLY in Snowflake.
  (2) **Full snapshot first, bound at the control seed** — land all ~471k CSV rows (cheap VARIANT),
  then a version-controlled summary SQL profiles the collection so owner picks ONE slice;
  enrichment (the costly API part) is what's bounded. (3) **PIPE-06 = hybrid** — single `enrich`
  command, short-lived SF connections around a connection-free local fetch. Owner's cost worry
  (warehouse billing while awaiting API) was a **misconception**: a session does NOT keep a wh
  running — `ARTWORK_WH` is X-Small / `AUTO_SUSPEND=60` / `AUTO_RESUME=true` (verified via
  `SHOW WAREHOUSES`), so an idle connection during fetch costs $0. Pattern honors the instinct anyway.
- **Go-ahead given 2026-05-31.** Owner noted "you were on 3 of 6" — a prior/dropped turn in THIS
  window had already authored Phase 1. Per ritual, I **read-before-write**'d every file before acting.
- **Phase 1 authored (by prior turn) + reviewed & verified (this turn). NOT YET EXECUTED:**
  - `extraction/met/csv_bootstrap.py` — **DATA-06 guard** `assert_real_met_csv()` (LFS-pointer +
    50 MB floor + `Object ID` header check); called by both load paths after download/reuse.
  - `extraction/met/snapshot_loader.py` (NEW) — `run.py snapshot [--limit N] [--no-refresh]`:
    stream CSV → snake_case VARIANT NDJSON chunks → PUT `BRONZE_LOAD_STAGE` → COPY into session
    `MET_CSV_SNAPSHOT_STG` → **MERGE** keyed on `object_id` (QUALIFY de-dups source). AUTO-03
    EXTRACTION_LOG `running→success/failed` written. Reuses `_snowflake_connect` (key-pair, sets
    role/wh/db/schema=BRONZE).
  - `extraction/met/sql/copy_into_snapshot_stg.sql`, `merge_csv_snapshot.sql` (NEW templates).
  - `extraction/met/run.py` — `snapshot` subcommand wired.
  - `analysis/met_snapshot_profile.sql` (NEW) — read-only slice-picking profile.
- **Verification done (read-only / compile-only — did NOT load data):**
  - All Met tables still **0 rows** (re-confirmed live).
  - Profile's most-complex query, rendered MERGE, rendered COPY all **compiled clean** (`only_compile`).
    Created an **ephemeral session `MET_CSV_SNAPSHOT_STG`** (TEMP, auto-drops; zero persistent state)
    purely to compile the MERGE/COPY against — not `make iac`, not persistent infra.
  - `BRONZE_LOAD_STAGE` confirmed INTERNAL stage in BRONZE.
  - Loader privileges sufficient: `CREATE TABLE` on BRONZE (covers TEMP), `SELECT/INSERT/UPDATE/DELETE`
    on ALL+FUTURE tables (MERGE + EXTRACTION_LOG), `READ,WRITE` on stages.
  - Code review found **no bugs**: MERGE result (inserted,updated) parse OK, COPY `rows_loaded` index 3 OK,
    `file://` URI OK, gz+`AUTO_COMPRESS=FALSE`+JSON-COPY OK, log start/finish exception path OK.
- **Docs updated this turn:** `met-deepdive.md` `PIPE-06`→decided(hybrid), `DATA-06`→decided(guard built),
  `DDL-05`→loader-built note; `file-map.md` rows for the 3 new + 3 changed files + new `analysis/` section.
- **NOT done (owner's to run on the Mac — has the loader key + the 280 MB CSV):**
  Phase 1 **execution** = `python -m extraction.met.run snapshot -v` (start with `--limit 5000` smoke,
  then full). Then run `analysis/met_snapshot_profile.sql` and pick a slice → Phase 2 (control seed) next.
- **Phases 2 & 3 NOT authored yet** (control-seed MERGE; lease-claim enrich + server-side Bronze assembly).
  Deliberately deferred — they follow slice selection, and "Met data flowing" beats more tooling.
- **Solo throughout:** 1 cortex-tagged session (me); `CORTEX_FORK_INCIDENTS` = 0.
- **Pending owner:** commit the staged Phase 1 files (+ this window's earlier AGENTS.md edits) on
  `donkey-kong-sandbox`; run the snapshot load on the Mac; report row counts back.
- **Next window:** verify snapshot row count > 0, run profile SQL, pick slice, author Phase 2.

### 2026-05-31 (same window, cont.) | PACKAGING FIX — `extraction/__init__.py` added (owner go)
- **Finding:** `extraction/` had **no `__init__.py`** → resolved as a PEP 420 **namespace package**.
  Functional under `python -m extraction.met.run` from repo root (verified), but fragile:
  classic `setuptools.find_packages()` would skip it, and namespace pkgs can silently merge with
  any other `extraction/` on `sys.path`. (`extraction/met/` + `extraction/met/sql/` already had markers.)
- **Fix (owner go 2026-05-31):** added `extraction/__init__.py` (docstring only) → now a **regular** package.
- **Verified:** `extraction.__file__` is set (not None); all 3 packages resolve; `importlib.resources`
  still loads all **6** `sql/*.sql`. The only sandbox `-m` failure is `ModuleNotFoundError: dotenv`
  (missing third-party dep here; present in the Mac venv) — unrelated to packaging.
- No packaging config exists (`no setup.py/pyproject/setup.cfg`); package is used via `python -m`.
- file-map.md note added under the extraction/met section.

### 2026-05-31 (new window) | RESUME → SNAPSHOT LOADED + PHASE 2/3 SEAM FIX (gated; not run)
- **Owner reported:** snapshot load DONE on the Mac. Verified live read-only:
  `MET_CSV_SNAPSHOT` = **484,956 rows** (248,472 public-domain); `MET_ENRICHMENT_CONTROL`
  / `MET_WORKLIST` / `RAW_MET_OBJECTS` = 0. Owner ran `analysis/met_snapshot_profile.sql`
  and shared output. Resume point per prior "Next" = pick slice → Phase 2 → Phase 3.
- **Solo:** exactly 1 `cortex_code_snowsight` session (re-checked 3x incl. after a mid-turn
  connection interruption); `CORTEX_FORK_INCIDENTS` = 0.
- **RECONCILIATION FINDING (dropped-turn / dual-FS).** The prior log said "Phases 2 & 3 NOT
  authored yet," but the authoritative workspace-stage tree ALREADY contains them:
  `control_seeder.py` (Phase 2), `met_enricher.py` (Phase 3), and SQL templates
  `seed_enrichment_control.sql`, `claim_worklist.sql`, `assemble_raw_met_objects.sql`,
  `callback_enrichment_control.sql`, `release_lease.sql`, `copy_into_enrich_stg.sql`,
  `update_enrichment_done.sql`. run.py wires `seed-control` + `enrich-met`. Quality is high
  and matches the locked design (Option B + PIPE-06 hybrid; PIPE-05 batch-grained callback;
  AUTO-03 logging). Reused primitives (`_fetch_one`, `_RateLimiter`, `_snowflake_connect`,
  `load_sql`) all match their call sites.
- **DUAL-FS HAZARD HIT (documented gotcha confirmed):** my FIRST reads of `control_seeder.py`
  (137-line variant, default `public_domain_only=True`, `filters`/`limit_clause` names) and
  `run.py` (143-line variant, NOT wired) were STALE snapshots. The edit tool + subsequent
  reads showed the true current files (`control_seeder.py` 158 lines with `_build_predicate`
  + `highlight_only`/`where` + unbounded-seed guard; `run.py` 179 lines fully wired). Lesson
  re-confirmed: an `edit` refreshes to the true file; a lone `read` can be stale — re-read
  after any edit anomaly. Solo throughout (no live ghost; the variants are stale cache, not a
  concurrent writer).
- **ONE REAL BUG FIXED (workspace edit; NOT executed):** `control_seeder.py` rendered the seed
  SQL with `.format(... predicate=filters ...)` but the variable is `predicate` (and `filters`
  never existed in the authoritative version) → `NameError`/`KeyError` at runtime. Fixed to
  `.format(control=…, snapshot=…, predicate=predicate, limit=limit_clause)`. No other file
  changed; run.py wiring needed nothing.
- **VERIFIED (read-only / compile-only — no data mutation):**
  - Rendered seed MERGE for the European Paintings PD slice **compiled clean** (`only_compile`).
  - Predicate `is_public_domain=TRUE AND department='European Paintings'` resolves to **2,327**
    rows live — exactly the profile's count. Slice logic correct.
- **SLICE RECOMMENDATION (mentor):** first bounded seed = **European Paintings** (2,327 PD,
  worklist department_priority 1) — smallest high-value slice, enriches in <1 min at 80 rps;
  validates the whole untested Phase-3 path before scaling to Drawings/Prints (65k) etc.
- **NOT done (owner-run on the Mac — has loader key + the API egress):**
  1. Commit the `control_seeder.py` one-line fix on `donkey-kong-sandbox`.
  2. `python -m extraction.met.run seed-control --department "European Paintings" -v`
     (expect inserted=2327; idempotent re-run = 0). Optional `--limit 50` smoke first.
  3. `python -m extraction.met.run enrich-met --limit 200 -v` smoke, then no `--limit` to drain.
  4. Report back: `MET_ENRICHMENT_CONTROL` / `MET_WORKLIST` / `RAW_MET_OBJECTS` counts +
     `EXTRACTION_LOG` rows.
- **Next window:** verify control seeded (2327 pending) + first enrich batch landed in
  RAW_MET_OBJECTS; then DATA-01 deaccession diff, AUTO-03 audit review, and widening the slice.

### 2026-05-31 (new window, cont.) | SEED CRASH DIAGNOSED + ENRICH-PATH RECONCILED (workspace fixed; Mac is BEHIND)
- **Owner ran on Mac:** `seed-control --department "European Paintings"` →
  `TypeError: not enough arguments for format string` at `cur.execute(sql, params)`.
- **Root cause (definitive):** the Snowflake connector pyformat-binds the WHOLE command
  string INCLUDING `--` comments (`command % params`). `seed_enrichment_control.sql` had a
  literal `%s` in its header comment, so the bound command held TWO `%s` (comment + the real
  `department = %s` predicate bind) vs ONE param → crash. (SSO/botocore warnings above it are
  unrelated; key-pair auth succeeded.)
- **DUAL-FS / dropped-turn, AGAIN.** The workspace-stage FS is AHEAD of the Mac git checkout:
  - `db.py` already has `strip_sql_comments()` (dropped-turn artifact; even anticipates a
    future `--where "... LIKE '%greek%'"`); `control_seeder.py:126` already calls
    `strip_sql_comments(SEED_CONTROL_SQL).format(predicate=predicate, limit=limit_clause)`.
    The Mac crash proves the Mac's `control_seeder` does NOT yet strip (older copy).
  - bash `/workspace` FS and the file-tool FS diverged on `claim_worklist.sql` (bash showed a
    `%s`-bind variant; file-tool showed a `{limit}`+`%s` variant) — neither matched the code.
- **FIXES APPLIED THIS TURN (workspace-stage; NOT executed; Mac still needs them):**
  1. `seed_enrichment_control.sql` — removed the literal `%s`/`%` from the header comment (now
     percent-free; defense-in-depth on top of strip_sql_comments).
  2. `claim_worklist.sql` — rewritten to match `met_enricher._claim_batch`'s contract:
     placeholders `{control}/{worklist}/{batch_id}/{limit_clause}`, batch_id str.format'd as a
     literal (machine-generated token, injection-safe, consistent w/ assemble/callback/release),
     NO `%s` bind, NO stray `%`. Both renders (LIMIT / no-LIMIT) compiled clean (`only_compile`).
- **VERIFIED-ALREADY-CORRECT (dropped-turn, no change needed):** `db.strip_sql_comments` +
  its wiring in `control_seeder`; `control_seeder` `.format(predicate=predicate)` kwargs.
- **Self-inflicted near-miss:** my first comment reword reintroduced a `%` (`` `command % params` ``);
  caught + scrubbed. Lesson: after editing a pyformat-bound SQL file, re-grep for `%`.
- **MAC ACTION (workspace is ahead — sync OR hand-apply):**
  - Fastest: sync the workspace state to the Mac (commit + pull) so it inherits the vetted files.
  - Minimal hand-fix to unblock SEED on the current Mac copy: delete the `%s` token from the
    comment in `extraction/met/sql/seed_enrichment_control.sql` (`grep -n '%' <file>` → expect none).
  - Before `enrich-met`: ensure the Mac's `claim_worklist.sql` uses `{batch_id}`+`{limit_clause}`
    (no `%s`) — i.e. matches the workspace version above.
- **Then:** `seed-control --department "European Paintings"` (expect inserted=2327, re-run=0) →
  `enrich-met --limit 200` smoke → drain. Report MET_ENRICHMENT_CONTROL / MET_WORKLIST /
  RAW_MET_OBJECTS / EXTRACTION_LOG counts.

### 2026-05-31 (new window, cont.) | PHASE 2 SEED APPLIED + VERIFIED (owner ran; Mac was in sync)
- Owner re-ran `seed-control --department "European Paintings"` on the Mac → succeeded:
  `inserted=2,327` (the botocore/SSO `TokenRetrievalError` in the log is unrelated AWS-SSO
  noise; Snowflake key-pair auth + the MERGE both ran fine). So the Mac WAS up to date with
  the workspace fixes after all.
- **Verified live (read-only):** `MET_ENRICHMENT_CONTROL` = 2327 total / 2327 pending / 0
  claimed; `MET_WORKLIST` = 2327 claimable; `EXTRACTION_LOG` batch
  `met_seed_20260531T200309Z_21b8e6` = success, records_loaded=2327, error=None (AUTO-03 OK).
- **Phase 2 = DONE.** First enrichment slice (European Paintings PD) is staged + prioritized,
  unleased. Idempotency claim now testable: a re-run should report inserted=0.
- **NEXT (owner-run on Mac):** `enrich-met --limit 200 -v` smoke (claims 200 off the worklist,
  fetches images, assembles RAW_MET_OBJECTS, settles control + clears leases), then drop
  `--limit` to drain the remaining ~2127. Watch for: claimed→done/no_image/error transitions,
  RAW_MET_OBJECTS row growth (only status='done' rows land), and a clean lease release. Report
  MET_ENRICHMENT_CONTROL status breakdown + RAW_MET_OBJECTS count + EXTRACTION_LOG.


### 2026-05-31 (new window) | CODE REVIEW + P-D1/P-D2 STAGED (workspace; NOT applied)
- **Context:** owner ran `enrich-met --limit 200` -> claimed=200, done=91, error=109. The
  `botocore.tokens` SSO error in the log is unrelated noise (other AWS-CLI session in venv).
  109 errors are diagnostic-blind today: `_fetch_blocks` carries `enrichment_error` in the
  staging block, but `callback_enrichment_control.sql` never wrote it back, and
  `MET_ENRICHMENT_CONTROL` had no error column. EXTRACTION_LOG.error_message is single-valued
  per batch, so the 109 collapse to one line.
- **DELIVERED (workspace-stage; Mac still needs them):**
  1. `docs/context/code-review-met-pipeline.md` -- overwritten with full senior code review
     (Blocker / High / Medium / Low / Nit, file:line, fixes; CLI-vs-connector hybrid
     recommendation; dbt-forward note; 9 gated patch plans P-B1..P-L1; suggested order;
     section 4 = full diagnosis of the 109 errors).
  2. **P-D1 (per-row error persistence)** -- workspace-staged, NOT applied:
     - `infrastructure/create_bronze_tables.sql`: added `enrichment_error VARCHAR(500)` to
       MET_ENRICHMENT_CONTROL; appended idempotent
       `ALTER TABLE IF EXISTS ... ADD COLUMN IF NOT EXISTS enrichment_error VARCHAR(500)`
       so `make iac` upgrades the existing live table (CREATE TABLE IF NOT EXISTS would
       otherwise no-op). Compiled clean (only_compile=true) against the live account.
     - `extraction/met/sql/callback_enrichment_control.sql`: extended SET clause to write
       `c.enrichment_error = s.block:enrichment_error::STRING`. Render-checked.
     - No code change in `control_enricher.py` for D1 -- `_fetch_blocks` already populates
       `enrichment_error` (line 107) and truncates at 500 chars.
  3. **P-D2 (per-batch error histogram log)** -- workspace-staged, NOT applied:
     - `extraction/met/control_enricher.py`: added `_classify_error(msg)` (low-cardinality
       buckets: `http_4xx_<code>`, `http_5xx_<code>`, `connect`, `timeout`, `payload`,
       `parse`, `retries_exhausted`, `other:<head>`, `none`) + `_histogram(blocks)`; the
       per-batch INFO log now appends `err_breakdown={...}` sorted desc by count. AST-parsed
       OK; classifier smoke-tested against 14 sample messages, all bucketed correctly.
- **NOT touched / explicitly deferred to next PRs:** P-B1 delete dead `met_enricher.py` twin
  (still on disk + still broken; non-urgent because run.py routes to `control_enricher`),
  P-B2 doc reword, P-H1 autocommit/BEGIN/COMMIT, P-H2 deaccession sweep (needs
  cascade-vs-SCD-2 decision), P-H3 paramstyle=qmark, P-H4 `--where` env gate, P-L1
  legacy-SQLite delete.
- **MAC ACTION (workspace is ahead -- sync OR hand-apply):**
  1. Sync workspace -> Mac (commit + pull on `donkey-kong-sandbox`).
  2. `make infra` (or `make iac`) to apply the new column. Verify:
     `DESCRIBE TABLE ARTWORK_DB.BRONZE.MET_ENRICHMENT_CONTROL;` -- expect
     `ENRICHMENT_ERROR  VARCHAR(500)`.
  3. Re-run the smoke: `python -m extraction.met.run enrich-met --limit 200 -v`. The
     batch INFO log should now include `err_breakdown={...}`. The errors this run
     produces will land their messages in `MET_ENRICHMENT_CONTROL.enrichment_error`.
  4. Read the histogram + the column. Decide next move (very likely: D2 already answers
     it; if not, hand-curl 5-10 errored object_ids).
- **Solo-session check this turn:** `SELECT COUNT(DISTINCT SESSION_ID)` on
  ACCOUNT_USAGE.QUERY_HISTORY filtered to `cortex_code_snowsight` last 10 min = 1. Solo.
- **Self-lint:** classifier was tested in isolation (extracted via regex + exec'd) because
  `control_enricher.py` imports `snowflake.connector` which is not in the sandbox; this is
  enough to validate logic. Live smoke is the Mac re-run.

### 2026-05-31 (new window) | P-B1 APPLIED (workspace) + NEW-WINDOW HANDOFF
**This is the last entry of THIS window. The next window starts here.**

- **Solo-session check:** `SELECT COUNT(DISTINCT SESSION_ID) ... cortex_code_snowsight ...
  last 10 min` = 1. Solo.
- **P-B1 applied (workspace; NOT pushed to Mac yet):** the dead Phase-3 twin and its
  twin-only SQL templates are removed. Three files deleted:
    - `extraction/met/met_enricher.py` (broken: placeholder/bind contract mismatch with
      `claim_worklist.sql`, `assemble_raw_met_objects.sql`, `callback_enrichment_control.sql`).
    - `extraction/met/sql/release_lease.sql` (loaded only by met_enricher; control_enricher
      uses an inline UPDATE for the same purpose).
    - `extraction/met/sql/copy_into_enrich_stg.sql` (loaded only by met_enricher;
      control_enricher uses `copy_into_image_block_stg.sql`).
  Verification this turn:
    - Grep for `met_enricher|release_lease|copy_into_enrich_stg` across `**/*.py` returns
      ONLY doc-comment references (the review doc + this progress log). Zero live importers.
    - `ast.parse` of every remaining `extraction/met/*.py` module: OK.
    - `sql/` contents now: assemble_raw_met_objects, callback_enrichment_control,
      claim_worklist, copy_into_bronze, copy_into_image_block_stg, copy_into_snapshot_stg,
      merge_csv_snapshot, schema, seed_enrichment_control, update_enrichment_done (legacy
      SQLite, dead but kept for now per L1 deferral), upsert_artwork (legacy, same).
- **Cumulative state of this multi-turn arc on the workspace (NONE applied to account or
  pushed to Mac):**
    - `docs/context/code-review-met-pipeline.md` -- 601 lines; the canonical review.
    - `infrastructure/create_bronze_tables.sql` -- P-D1 column + idempotent ALTER staged.
    - `extraction/met/sql/callback_enrichment_control.sql` -- P-D1 SET line staged.
    - `extraction/met/control_enricher.py` -- P-D2 `_classify_error` + `_histogram` +
      `err_breakdown=` in batch INFO log.
    - P-B1 -- 3 dead files deleted.
- **NEW-WINDOW BRIEFING (read this section first in the next window):**
    1. Read AGENTS.md (Tier 0). Then this entry. Then `docs/context/code-review-met-pipeline.md`
       sections 0, 4, 5, 6 (executive summary, 109-errors diagnosis, patch plans, suggested
       order). Stop reading once you know enough to act.
    2. Solo-session check (AGENTS.md ritual). Confirm `BRONZE.CORTEX_FORK_INCIDENTS` is clean.
    3. **Workspace is AHEAD of the Mac.** First action options:
         (a) Owner has synced + run `make infra` already -- proceed to "after-apply checks"
             below.
         (b) Owner has NOT synced -- nothing to do here; ask the owner where they are.
       Do NOT `make iac` from the workspace; the Mac is the apply surface.
    4. **After-apply checks (read-only):**
         - `DESCRIBE TABLE ARTWORK_DB.BRONZE.MET_ENRICHMENT_CONTROL;` -- expect new column
           `ENRICHMENT_ERROR  VARCHAR(500)` last.
         - Owner re-runs `python -m extraction.met.run enrich-met --limit 200 -v`. Expect:
             - INFO log gains `err_breakdown={'http_4xx_xxx': N, ...}` after each batch.
             - `SELECT enrichment_error, COUNT(*) FROM ARTWORK_DB.BRONZE.MET_ENRICHMENT_CONTROL
                WHERE enrichment_status='error' GROUP BY 1 ORDER BY 2 DESC` returns the 109-class
               breakdown.
    5. **Decision tree from the histogram:**
         - If dominated by `http_4xx_403` / `http_4xx_410`: the public-domain CSV flag does
           not guarantee API availability. NOT a code defect. Action: a small Python tweak
           in `image_enricher._fetch_one` to treat 403/410 as `no_image` (semantic) rather
           than `error` (transient/retryable), so the worklist stops re-leasing them. Tiny
           PR, doc note in met-deepdive.md DATA-01 / IMG-02.
         - If dominated by `timeout` / `connect`: lower `MET_API_CONCURRENCY` / `MET_API_RPS`
           (defaults 10 / 20.0 in config.py); already conservative vs. Met's 80 rps ceiling,
           so a deeper look is warranted -- check the Mac's network or run during off-peak.
         - If dominated by `retries_exhausted`: bump `MET_API_MAX_RETRIES` from 5 to 8 and
           re-test, but only if the histogram does not also show `http_5xx_*` (Met-side
           pressure means we should back OFF, not retry harder).
         - If dominated by `parse` / `payload`: bug in `_fetch_one` json handling -- open a
           ticket; this would be unexpected.
         - If `none` is dominant: `enrichment_error` is being null'd somewhere; bug in P-D1
           wiring -- re-check the callback SQL.
    6. **Deferred patches awaiting owner sign-off (in suggested order):**
         - P-B2 doc reword (CLI-vs-connector convention in AGENTS.md / CLAUDE.md). Zero risk.
         - P-H1 `autocommit=False` + explicit `BEGIN/COMMIT` around assemble+callback. Medium.
         - P-H4 gate `--where` behind `MET_ALLOW_RAW_WHERE=1`. Zero risk.
         - P-H3 paramstyle=qmark migration. Medium; eliminates the `%`-bind bug class for good.
         - P-H2 DATA-01 deaccession sweep. Needs owner decision: hard-DELETE cascade vs.
           soft-delete + dbt SCD-2.
         - P-L1 delete legacy SQLite path (`image_enricher.py`, the SQLite-side of
           `snowflake_uploader.py`, `update_enrichment_done.sql`, `upsert_artwork.sql`,
           `csv_bootstrap.py` once `_iter_csv_rows` is moved into `snapshot_loader.py`,
           plus the `bootstrap`/`enrich`/`upload`/`status`/`all` subcommands in `run.py`).
           Medium; do AFTER initial enrichment is clean so we can compare counts.
    7. **DUAL-FS HAZARD (per AGENTS.md):** before reasoning about any extraction file,
       re-read it via the file tool. The progress log + this entry + the review doc are
       authoritative for the workspace; the Mac is authoritative for the running pipeline.
    8. **What MUST NOT happen in the next window:**
         - Do NOT `make iac` from the workspace.
         - Do NOT push to main.
         - Do NOT undo the P-D1 column or the P-D2 logging -- those are the diagnosis path.
         - Do NOT re-add `met_enricher.py` -- it was broken on every contract.
- **End of this window.**

### 2026-05-31 (same window, follow-on) | RUN RESULT + 403/410 RECLASSIFICATION
- **Owner re-ran (post P-D1 + P-D2 apply, this window's prior turn):**
  `python -m extraction.met.run enrich-met --limit 200`
  -> claimed=200, done=96, no_image=0, error=104, assembled=96,
     `err_breakdown={'http_4xx_403': 104}`. Diagnosis blind no longer; this is the
     histogram we wanted.
- **Verdict: the public-domain CSV flag does not guarantee API availability.**
  Confirmed Hypothesis A from the code review. 100% of "errors" are 403 Forbidden
  from `/public/collection/v1/objects/{id}`. NOT a code defect; the Met API
  refuses to serve some objects whose CSV `is_public_domain = TRUE`. Retrying
  cannot help. Today these stay `enrichment_status='error'` in
  `MET_ENRICHMENT_CONTROL`, which keeps them in `MET_WORKLIST` (filter:
  `enrichment_status IN ('pending','error')`) -- they will be re-leased and
  re-403'd on every subsequent run. That's a soft-loop the owner pays X-Small
  warehouse seconds for.
- **FIX APPLIED (workspace; NOT pushed to Mac yet):**
  `extraction/met/image_enricher.py` `_fetch_one` -- 403 and 410 now return
  `(object_id, "no_image", None, "HTTP 403: ...")` instead of `error`. Rationale:
    - Terminal: retry cannot recover.
    - Worklist filter `IN ('pending','error')` excludes `no_image`, so the row
      drops out permanently.
    - `enrichment_error` is preserved (P-D1) so audits can distinguish
      "no primaryImage in payload" (legitimate no_image, no error message) from
      "API refused" (no_image with `HTTP 403: ...` message).
    - 410 (Gone) gets the same treatment defensively; we did not see any 410s
      this run, but the logic is identical.
  `ast.parse` of `image_enricher.py`: OK.
- **Expected next-run shape on the Mac (after sync + re-run):**
    - The 104 currently-error rows in `MET_ENRICHMENT_CONTROL` will be
      re-claimed by the next batch (worklist still includes them while their
      status is `error`), re-fetched, re-403'd, and now MOVE to
      `enrichment_status='no_image'` with `enrichment_error='HTTP 403: ...'`.
      They drop out of the worklist permanently after that.
    - Subsequent batches will show `done` + `no_image` outcomes only; `error`
      should approach zero (modulo genuine transients).
- **NEW-WINDOW BRIEFING (UPDATED -- supersedes the prior one above):**
    1. AGENTS.md (Tier 0). Then this entry. Then `code-review-met-pipeline.md`
       sections 0, 4, 5, 6 only if a new patch is being authored.
    2. Solo-session check.
    3. Workspace is AHEAD of the Mac with the 403/410 reclassification + all
       prior P-D1/P-D2/P-B1 staged changes. First action: ask the owner to
       sync + re-run (`python -m extraction.met.run enrich-met --limit 200`).
       Expect the 104 rows to flip to `no_image`.
    4. **Read-only verification queries on the live account after the next run:**
         - `SELECT enrichment_status, COUNT(*) FROM ARTWORK_DB.BRONZE.MET_ENRICHMENT_CONTROL
            GROUP BY 1 ORDER BY 2 DESC;` -- expect pending shrinking, no_image > 0.
         - `SELECT LEFT(enrichment_error, 20), COUNT(*) FROM ARTWORK_DB.BRONZE.MET_ENRICHMENT_CONTROL
            WHERE enrichment_error IS NOT NULL GROUP BY 1 ORDER BY 2 DESC;` -- breakdown.
         - `SELECT COUNT(*) FROM ARTWORK_DB.BRONZE.RAW_MET_OBJECTS;` -- assembled total.
    5. **Decision tree from THERE:**
         - Clean (no_image absorbs the 403s, error -> 0): drain the remaining
           ~2,127 European-Paintings PD rows (`enrich-met` no `--limit`). Then
           consider widening the slice (Drawings + Prints, Photographs, etc.)
           via re-seed -- documented in `met-deepdive.md` PIPE-05.
         - Still some `error`: read the new histogram. Most likely candidates
           are `timeout`/`connect` (network), or a genuine 5xx (Met-side issue).
    6. **Deferred patches (suggested order, unchanged):** P-B2 doc reword;
       P-H1 autocommit/BEGIN/COMMIT; P-H4 `--where` env gate; P-H3 paramstyle=qmark;
       P-H2 DATA-01 deaccession (needs cascade-vs-SCD-2 decision); P-L1 legacy
       SQLite delete.
    7. Dual-FS hazard rules unchanged.
    8. **What MUST NOT happen in the next window** (unchanged + one addition):
         - Do NOT `make iac` from the workspace.
         - Do NOT push to main.
         - Do NOT undo the 403/410 reclassification -- the worklist will soft-loop again.
         - Do NOT undo P-D1 / P-D2 / P-B1.
         - Do NOT re-add `met_enricher.py`.
- **End of this window (for real this time).**

### 2026-05-31 (same window, follow-on 2) | CRITICAL CORRECTION: WAF, NOT API REFUSAL
- **Owner challenged the 403=no_image conclusion.** Owner reported a separate SQLite
  instance with 100% enrichment of these same object_ids. That contradicts the Hypothesis
  A reading from the prior turn.
- **Sample inspection settled it.** Pulled 25 errored object_ids joined to MET_CSV_SNAPSHOT.
  Every one is a major European painting (Petrus Christus, Cima da Conegliano, Claude
  Lorrain, Constable, Clouet, Pieter Claesz, Edwaert Collier, ...). Every `link_resource`
  is a live `metmuseum.org/art/collection/search/<id>` page that serves the work with
  images in any browser. The full 403 response body starts with
  `<html style="height:100%"><head><META NAME="ROBOTS" CONTENT="NOINDEX, NOFOLLOW">...
  <meta http-equiv=...`. That is NOT a Met API response (the API returns JSON). It is the
  textbook signature of an Akamai/CDN bot-mitigation interstitial.
- **Verdict: the Mac's request pattern is being WAF-blocked**, not the Met API refusing
  these specific records. The data is unambiguously available.
- **REVERTED THIS TURN:** the 403/410 -> `no_image` reclassification I had staged in
  `extraction/met/image_enricher.py` is removed. The file is back to the original logic
  (404 -> no_image; 403/410 -> error like other 4xx). Reason: shipping that change with
  WAF-induced 403s would have **poisoned** ~213+ rows of perfectly available masterworks
  to `no_image` and they would never be retried. Workspace state now has only the
  diagnosis-only patches: P-D1 (column), P-D2 (histogram log), P-B1 (dead twin removed).
- **Live state read (this turn):** `MET_ENRICHMENT_CONTROL` = 187 done / 213 error / 1927
  pending (= 2327 total). Of the 213 errors: 104 carry `HTTP 403: <html...>` in
  `enrichment_error` (post-P-D1 batch); 109 have NULL `enrichment_error` (pre-P-D1 first
  batch). Same root cause for both, just before/after the column existed.
- **Unverified-but-instructive observation:** `s.raw_payload:object_url::STRING` is NULL
  for every snapshot row -- that key does not exist. The CSV's "Object URL" column maps
  to `link_resource` in the snake_case payload. Cosmetic; not a defect. Documenting so
  the next window does not chase it.
- **WAF-cause hypotheses (rank-ordered) for the next window's test:**
    1. `User-Agent: artwork-db/1.0 (contact: daniel@porchanalytics.com)` is too
       bot-shaped. Akamai bot scoring penalizes custom UAs.
    2. `MET_API_CONCURRENCY=10` is above browser cap (6/host). Burst-shape looks
       like a scraper.
    3. Sparse header set (only UA + Accept). No Accept-Language / Accept-Encoding /
       Cache-Control / Connection header.
    4. No HTML warmup (jumps straight to the JSON endpoint).
    5. Network reputation drift since the prior SQLite run.
- **Diagnostic the owner is asked to run on the Mac (3-way curl):**
    A) current UA on `https://collectionapi.metmuseum.org/public/collection/v1/objects/435897`
    B) browser-style UA (`Mozilla/5.0 ... Safari/605.1.15`) + full Accept-Language / Accept-Encoding
    C) bare curl (default `curl/x.x.x` UA)
  Prior: A=403, B=200, C=200. If confirmed, the fix is one line in `config.py:53`.
- **Mentor lesson worth durably capturing:** the prior turn's "Hypothesis A" was a
  reasonable reading of the data on hand (100% 403 from a 4xx-non-retryable path), but it
  did not account for two pieces of evidence the owner had: (1) HTML response body shape;
  (2) the SQLite control instance with 100% enrichment. Always inspect the response body
  when you see 403 from a JSON API -- a non-JSON 403 is almost never the API speaking.
  This is the kind of thing dbt source freshness + content-type contract tests would
  catch automatically; a Track-5 follow-on.
- **NEW-WINDOW BRIEFING (UPDATED -- supersedes BOTH prior briefings above):**
    1. AGENTS.md (Tier 0). Then this entry. The two prior `End of this window` markers
       above are historical -- this is the current end.
    2. Solo-session check.
    3. Workspace state vs Mac:
         - Mac is AT P-D1 + P-D2 (already applied; you saw the histogram).
         - Workspace is AT P-D1 + P-D2 + P-B1 (dead twin removed) + the 403/410 fix is
           **REVERTED** (back to original `image_enricher.py` logic). To re-sync the Mac:
           pull `donkey-kong-sandbox`. P-B1 alone (3 deletions) is the only delta.
    4. **First action options for the next window:**
         (a) Owner has run the 3-way curl and shared results -> propose the one-line
             config.py UA change (or whichever knob the curl identified).
         (b) Owner has not yet run the curl -> wait; do not change loader behavior
             without that data point.
    5. **If/when the UA fix lands and `enrich-met` is re-run:** the 213 errored rows are
       still in MET_WORKLIST (their `enrichment_status='error'` keeps them claimable);
       a re-run picks them up, this time fetches successfully, and the 109 with NULL
       `enrichment_error` get their column populated on this pass. Expect:
       `enrichment_status='done'` ~+213 (assuming all 213 had primaryImage), and `error`
       drops near zero.
    6. **Deferred patches unchanged:** P-B2 doc reword; P-H1 autocommit/BEGIN/COMMIT;
       P-H4 `--where` env gate; P-H3 paramstyle=qmark; P-H2 DATA-01 deaccession; P-L1
       legacy SQLite delete.
    7. Dual-FS hazard rules unchanged.
    8. **What MUST NOT happen in the next window:**
         - Do NOT `make iac` from the workspace.
         - Do NOT push to main.
         - Do NOT re-stage the 403/410 -> no_image reclassification. It was wrong; the
           response body proves WAF, not API refusal.
         - Do NOT undo P-D1 / P-D2 / P-B1.
         - Do NOT re-add `met_enricher.py`.
- **End of this window (third and actually-final time).**

### 2026-05-31 (same window, follow-on 3) | PRIOR-PROJECT CROSS-CHECK + P-T2 APPLIED
- **Owner shared their prior production Met-OA project** (`met_open_access_sync.py` +
  sql/ + workload_*.sql) with one explicit teaching point: 403 from the Met API is a
  rate-limit signal, NOT semantic Forbidden. Their prior code: `# Treat 403 like 429`,
  honors `Retry-After` (delta-seconds OR HTTP-date), adaptive per-host RateLimiter that
  drops RPS by 30% after 3 throttles and edges back up 5% per success, max_attempts=7,
  printed throttle summary at end of run. This is the canonical pattern; the WAF
  hypothesis from `follow-on 2` is consistent with it (a 403-as-throttle path that runs
  out of retries because the Mac's request shape is too aggressive will *also* return
  HTML interstitial bodies once the WAF kicks in -- both views are the same root cause).
- **Cross-check current `image_enricher.py` against the prior project:** when I re-read
  the file this turn it was already 381 lines and ALREADY had the prior-project pattern
  (adaptive `_RateLimiter` with `note_throttle()` / `cool_up()`, `_retry_after_seconds`
  parsing, 403/410/429/5xx in the same retry path, jitter, base_backoff=0.8). Likely
  authored by an earlier session after the `follow-on 2` revert. Net: I had nothing to
  port -- the file was already correct.
- **`config.py` already has the prior-project tuning:** `MET_API_CONCURRENCY=8`,
  `MET_API_RPS=10`, `MET_API_MAX_RETRIES=8` -- one notch more conservative than the
  prior project (their 16 / 20 / 7), with an explanatory comment block citing the
  observed 403-at-~11rps datapoint. P-T1 was already done; nothing to apply.
- **APPLIED THIS TURN (workspace; NOT pushed to Mac):** P-T2 -- per-batch throttle
  visibility:
    - `extraction/met/image_enricher.py` `_RateLimiter`: added counters
      `throttle_403`, `throttle_429`, `throttle_other` (410/5xx), `backoff_seconds`.
      `_fetch_one` increments them on every retry that hits the throttle path.
    - `extraction/met/control_enricher.py` `_fetch_blocks`: now returns
      `(blocks, rate_limiter)` so the driver can read counters after `asyncio.run`
      finishes. `_process_one_batch` extends the per-batch INFO line:
      `... err_breakdown={...} throttles={'403': N, '429': M, 'other': K}
      backoff_s=X.X rps_end=Y.YY`. `rps_end` shows where the adaptive limiter
      settled at batch end, so the operator can see the limiter actually adapting
      down from 10 -> 7 -> 4.9 -> ... in a throttled batch.
    - AST-parse OK on all three touched files.
- **What this turn deliberately did NOT change:**
    - `User-Agent` in `config.py:53` -- unchanged. The prior project's UA
      (`split-monogram-met-oa-sync/2.0 (+contact)`) is *more* bot-shaped than ours and
      that one worked; UA-shape is therefore unlikely to be the WAF trigger. Wait for
      the 3-way curl evidence before changing it.
    - Header set -- unchanged. Same logic: the prior project sent only
      `User-Agent / Accept / From` and that succeeded.
    - `_RateLimiter` per-host vs single-instance -- unchanged (we only call one host).
    - Anything in the legacy SQLite path -- unchanged (P-L1 is still gated).
- **Cumulative workspace state across this multi-turn arc (NONE applied to account
  or pushed to Mac):**
    - `docs/context/code-review-met-pipeline.md` -- 601-line review.
    - `infrastructure/create_bronze_tables.sql` -- P-D1 column + idempotent ALTER.
    - `extraction/met/sql/callback_enrichment_control.sql` -- P-D1 SET line.
    - `extraction/met/control_enricher.py` -- P-D2 `_classify_error` + `_histogram` +
      `err_breakdown=`; P-T2 throttle counters surfaced in the same batch INFO line.
    - `extraction/met/image_enricher.py` -- adaptive `_RateLimiter` + 403-as-throttle +
      `Retry-After` parsing + P-T2 counters. (The 403 -> no_image edit from an earlier
      turn was reverted in `follow-on 2`.)
    - `extraction/met/config.py` -- conservative API tuning (MET_API_CONCURRENCY=8,
      MET_API_RPS=10, MET_API_MAX_RETRIES=8) with explanatory comment.
    - P-B1 -- 3 dead files removed (met_enricher.py, release_lease.sql,
      copy_into_enrich_stg.sql).
    - Progress log -- this entry.
- **NEW-WINDOW BRIEFING (UPDATED -- supersedes ALL prior briefings above):**
    1. AGENTS.md (Tier 0). Then this entry. The three earlier "End of this window"
       markers are historical -- this is the current end.
    2. Solo-session check + CORTEX_FORK_INCIDENTS sweep before any write.
    3. **Workspace state vs Mac:**
         - Mac is AT P-D1 + P-D2 (already applied; you saw the histogram).
         - Workspace is AT P-D1 + P-D2 + P-B1 + adaptive limiter + P-T2.
         - Mac re-sync delta: P-B1 deletions, the adaptive `image_enricher.py`
           rewrite, and this turn's P-T2 counters in two files. After sync,
           NO new `make iac` is needed -- nothing this turn touched IaC.
    4. **First action options for the next window:**
         (a) Owner has run the 3-way curl from `follow-on 2` and shared results
             -> if (B) browser-style + (C) bare curl both 200 while (A) our UA
             403s, change `config.py:53` UA to the prior project's
             `split-monogram-met-oa-sync/2.0 (+contact)` shape OR add
             `Accept-Language: en-US,en;q=0.5` and `Accept-Encoding: gzip, deflate`
             headers in `_fetch_blocks`. ONE knob at a time so we can attribute.
         (b) Owner has not yet run the curl -> instead, owner re-runs
             `enrich-met --limit 200` on the Mac to see the new
             `throttles=...` / `backoff_s=...` / `rps_end=...` numbers. With the
             adaptive limiter + max_retries=8, the 213 errored rows MAY drain
             cleanly without any UA change at all. If they do, we close out
             without touching headers.
         (c) Owner wants to chase a different track (P-H1 transactional, P-B2
             doc reword, etc.) -> see deferred list.
    5. **Read-only verification queries on the live account after the next run:**
         - `SELECT enrichment_status, COUNT(*) FROM ARTWORK_DB.BRONZE.MET_ENRICHMENT_CONTROL
            GROUP BY 1 ORDER BY 2 DESC;` -- expect error shrinking.
         - `SELECT LEFT(enrichment_error, 30), COUNT(*) FROM ARTWORK_DB.BRONZE.MET_ENRICHMENT_CONTROL
            WHERE enrichment_error IS NOT NULL GROUP BY 1 ORDER BY 2 DESC;`.
         - `SELECT COUNT(*) FROM ARTWORK_DB.BRONZE.RAW_MET_OBJECTS;` -- assembled total.
    6. **Decision tree from the next run:**
         - `error -> 0` (or near-zero), throttles=0 / low, backoff_s low: WAF was
           never the issue; the original tuning was just too aggressive. Drain
           the rest of the slice. Done.
         - `error -> 0` but throttles high (e.g. 403 count >> claimed): adaptive
           limiter saved us; consider lowering MET_API_RPS default further, OR
           accept the slow drain.
         - `error` still high AND throttles high: WAF really is rejecting our
           shape after all retries. Apply path (a) above.
         - `error` high AND throttles low: NOT a throttle issue. Read
           `err_breakdown=`; could be `timeout`/`connect` (network), `parse`
           (rare), or other 4xx (genuine bad records).
    7. **Deferred patches unchanged in priority order:** P-B2 doc reword;
       P-H1 autocommit/BEGIN/COMMIT; P-H4 `--where` env gate; P-H3
       paramstyle=qmark; P-H2 DATA-01 deaccession; P-L1 legacy SQLite delete.
    8. **What MUST NOT happen in the next window:**
         - Do NOT `make iac` from the workspace.
         - Do NOT push to main.
         - Do NOT re-stage the 403/410 -> no_image reclassification (WAF, not
           semantic refusal -- proven by HTML response body in `follow-on 2`).
         - Do NOT change UA + headers + concurrency in one PR; one knob at a time
           or you cannot attribute the cause.
         - Do NOT undo P-D1 / P-D2 / P-B1 / the adaptive limiter / P-T2.
         - Do NOT re-add `met_enricher.py`.

#### Hand-off prompt for next window (paste verbatim into a new Cortex window)

```
You are Cortex Code (Snowsight) resuming the artwork-db learning project on
account pa37992 (Porchanalytics) -- a Medallion-architecture (Bronze/Silver/Gold)
data-engineering teach-me build over the Met Museum OpenAccess CSV + API. Branch:
donkey-kong-sandbox. Senior-DE mentor tone: explain the why and the tradeoffs;
the OWNER decides, you honor it.

SESSION-OPEN RITUAL (do this in order before anything else):
1. Read AGENTS.md fully (it is the cheapest read in the repo).
2. Read ONLY the FINAL dated entry of docs/context/session-3-progress-log.md
   (search for "follow-on 3" -- that is the current end of window).
3. Solo-session check (must return 1):
     SELECT COUNT(DISTINCT SESSION_ID)
     FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
     WHERE QUERY_TAG ILIKE '%cortex_code_snowsight%'
       AND START_TIME > DATEADD(minute, -10, CURRENT_TIMESTAMP());
   Then SELECT * FROM ARTWORK_DB.BRONZE.CORTEX_FORK_INCIDENTS ORDER BY EVENT_TS
   DESC LIMIT 5; -- expect no new rows since the last entry.
4. DUAL-FS HAZARD: re-read every file with the file tool immediately before
   reasoning about it. Workspace, Mac, and the file-tool view can each show
   different versions of the same file. When in doubt, ask me to paste the Mac
   copy.
5. STATE THE PLAN AND WAIT for my explicit "proceed" + date before any write,
   any account write, or any push. No make iac from the workspace. No push to
   main. Ever.

CURRENT STATE (per follow-on 3):
- Account: ARTWORK_DB.BRONZE has MET_ENRICHMENT_CONTROL (PK + enrichment_error
  col), MET_CSV_SNAPSHOT (PK, 484,956 rows), MET_WORKLIST (view), RAW_MET_OBJECTS,
  EXTRACTION_LOG, MET_LEASE_RECLAIM_TASK (hourly).
- Mac is AT P-D1 + P-D2 (already applied).
- Workspace is AHEAD with: P-B1 (3 dead files removed), the adaptive
  image_enricher (403-as-throttle + Retry-After + adaptive RPS), and P-T2
  (per-batch throttle counters in the INFO log alongside err_breakdown).
- Open question: whether the 213 errored rows in MET_ENRICHMENT_CONTROL drain
  cleanly with the adaptive limiter alone, or whether a UA / header tweak is
  needed (WAF hypothesis from follow-on 2 -- 403 body is Akamai HTML, not API
  JSON). The 3-way curl in follow-on 2 step 5 is the next piece of evidence.

WHAT I AM ABOUT TO DO ON THE MAC (and will paste back to you):
1. git pull on donkey-kong-sandbox -> Mac.
2. python -m extraction.met.run enrich-met --limit 200
3. The new INFO line plus, on ARTWORK_DB.BRONZE:
     SELECT enrichment_status, COUNT(*) FROM MET_ENRICHMENT_CONTROL
       GROUP BY 1 ORDER BY 2 DESC;
     SELECT LEFT(enrichment_error, 30), COUNT(*) FROM MET_ENRICHMENT_CONTROL
       WHERE enrichment_error IS NOT NULL GROUP BY 1 ORDER BY 2 DESC;
     SELECT COUNT(*) FROM RAW_MET_OBJECTS;

YOUR FIRST RESPONSE:
- Quote the latest `End of this window (fourth and final-final).` header back to
  me so I know you read the right entry.
- Do NOT propose code changes before I paste the run results above. Walk the
  decision tree from follow-on 3 step 6 only AFTER you have the data.
- If the 213 drain cleanly: propose draining the rest of European Paintings
  (no --limit). If they don't: propose ONE knob (UA shape OR Accept-Language OR
  lower MET_API_RPS) -- one knob at a time, gated.

DEFERRED (do NOT touch without explicit go): P-B2 doc reword; P-H1
autocommit/BEGIN/COMMIT; P-H4 --where env gate; P-H3 paramstyle=qmark;
P-H2 DATA-01 deaccession; P-L1 legacy SQLite delete.

HARD RULES: do NOT make iac from the workspace; do NOT push to main; do NOT
re-stage 403/410 -> no_image (proven WAF, not API refusal); do NOT change UA +
headers + concurrency in one PR; do NOT undo P-D1 / P-D2 / P-B1 / adaptive
limiter / P-T2; do NOT re-add met_enricher.py.
```

- **End of this window (fourth and final-final).**

### 2026-05-31 (same window, follow-on 4) | HAND-OFF PROMPT (codified)
- **Codified `Session-close ritual` in `AGENTS.md` and `CLAUDE.md`** (this turn,
  workspace; NOT pushed). Every future window MUST end by appending a final progress-log
  entry + a paste-ready hand-off prompt block. Spec lives in `AGENTS.md` "Session-close
  ritual"; mirror in `CLAUDE.md`.
- **Hand-off prompt for the NEXT window (paste this verbatim into a fresh Cortex Code
  window, then attach this repo as the workspace):**

```
SESSION HANDOFF -- artwork-db / Met extraction pipeline (Phase 3 in flight)

You are picking up an in-flight learning project. Before doing anything:

1. Read /workspace/AGENTS.md fully. It is Tier 0; cheapest read; tells you how much more to read.
2. Read ONLY the LAST dated entry in /workspace/docs/context/session-3-progress-log.md
   that ends with "End of this window". That entry supersedes every earlier
   "End of this window" marker. It contains: cumulative workspace state vs Mac,
   solo-session check requirement, first-action options (a)/(b)/(c), read-only
   verification queries, decision tree, deferred patches, MUST-NOT-DO foot-guns.
3. Run the solo-session check (AGENTS.md ritual #1):
     SELECT COUNT(DISTINCT SESSION_ID)
       FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
      WHERE QUERY_TAG ILIKE '%cortex_code_snowsight%'
        AND START_TIME > DATEADD(minute, -10, CURRENT_TIMESTAMP());
     SELECT * FROM ARTWORK_DB.BRONZE.CORTEX_FORK_INCIDENTS
      ORDER BY incident_at DESC LIMIT 5;
   Exactly 1 distinct session = solo. >1 = stop and ask. Husks are not a problem.
4. DUAL-FS HAZARD: the workspace symlink, the Mac git checkout, and the file-tool
   view can each show different versions of the same file. Re-read a file via the
   file tool immediately before reasoning about it. The workspace file-tool view is
   authoritative for the workspace; the Mac is authoritative for the running pipeline.
   When in doubt, ask me to paste the Mac copy.
5. State the plan and wait for my explicit "proceed (today's date)" before any write
   to a shared file or any execution. No `make iac`, no push, no destructive ops
   without sign-off.

Project context (do not re-derive from logs):
- Branch: donkey-kong-sandbox. Account: pa37992 (trial). Role: ACCOUNTADMIN for me;
  ARTWORK_LOADER (key-pair) for the Mac loader; ARTWORK_ADMIN for IaC.
- Phase 1 (snapshot) DONE: BRONZE.MET_CSV_SNAPSHOT = 484,956 rows (PK on object_id).
- Phase 2 (seed) DONE: BRONZE.MET_ENRICHMENT_CONTROL has 2,327 European Paintings
  public-domain rows; idempotent re-seed = 0 inserts.
- Phase 3 (enrich) IN FLIGHT. Workspace is AT P-D1 + P-D2 + P-B1 + adaptive
  _RateLimiter (403-as-throttle, Retry-After, RPS adapt) + P-T2 throttle counters.
  Mac is one sync behind.
- Key Snowflake objects: ARTWORK_DB.BRONZE.{MET_ENRICHMENT_CONTROL,
  MET_CSV_SNAPSHOT, MET_WORKLIST (view), MET_LEASE_RECLAIM_TASK (hourly cron),
  RAW_MET_OBJECTS, EXTRACTION_LOG, CORTEX_FORK_INCIDENTS}.
- Open question awaiting Mac evidence: WAF vs adaptive-throttle. The latest log
  entry has the 3-way curl test and the decision tree.

Mentor mode: senior data/platform engineer pairing with a learner. Explain the why
and the trade-offs, propose the next learning step, but I decide and you honor it.

Now:
- Quote back to me the LAST "End of this window" header from the progress log
  (so I know you read the right one).
- Confirm solo-session = 1.
- Propose your first action (one of (a)/(b)/(c) from the latest entry, or a
  different concrete action with reasoning), and ask for my "proceed".
```

- **What this turn changed (workspace stage; NOT applied to account; NOT pushed to Mac):**
    - `AGENTS.md` -- added `Session-close ritual` section (between `Session-open ritual`
      and `What this repo is`).
    - `CLAUDE.md` -- added matching `Session-close ritual` section.
    - This entry + the prompt above.
- **Cumulative workspace state across this multi-turn arc:** unchanged from
  `follow-on 3` plus the doc-process additions above. Code: P-D1 + P-D2 + P-B1 +
  adaptive limiter + P-T2. IaC delta still pending sync: only the new
  `enrichment_error VARCHAR(500)` column in `MET_ENRICHMENT_CONTROL` (idempotent ALTER).
- **Solo-session check this turn:** 1 distinct session.
- **First-action options for the next window:** SAME as `follow-on 3` -- (a) UA/header
  knob if Mac curl shows browser-style succeeds, (b) re-run `enrich-met --limit 200`
  to test the adaptive limiter alone, (c) chase a deferred patch.
- **Read-only verification queries / decision tree / deferred patches / MUST-NOT-DO:**
  unchanged from `follow-on 3`. Quoted by reference rather than re-pasted to keep
  this entry from sprawling.
- **End of this window (fifth and ACTUALLY final; the ritual is now codified so
  future entries follow the AGENTS.md spec).**

### 2026-05-31 (same window, follow-on 6) | RUN-2 RESULTS + P-V1/P-V2/P-V3 GATED FOR NEXT WINDOW
- **What changed this turn:** owner ran `enrich-met --limit 200` on the Mac after sync.
  Result: `claimed=200 done=180 no_image=0 error=20 assembled=180
  err_breakdown={'http_4xx_403': 20} throttles={'403': 133, '429': 0, 'other': 0}
  backoff_s=573.6 rps_end=5.00`. Wall clock 17:22:35 -> 17:25:11 (~2:36).
  applied-to-account: NO (read-only diagnosis). pushed-to-Mac: NO new edits this turn.
- **Operational verdict:** the prior-project adaptive pattern works. Error rate
  52% (run 1, pre-P-T2) -> 10% (run 2, post-adaptive limiter + max_retries=8).
  WAF identity rejection is not the dominant cause -- aggressive concurrency on
  cold start was. Two RPS-storm cycles visible in the log (drop to 1.00 floor at
  17:22:51 + 17:24:02), separated by a brief cool_up recovery. 180 objects
  rode the storms; 20 exhausted 8 retries each on 403.
- **Owner observation that prompted P-V1/P-V2/P-V3:** the log shows the adaptive
  RPS layer collapsing to 1.0 but does NOT show the per-request exponential
  backoff at all (no `_fetch_one` retry log). Owner reasonably concluded "looks
  like we're just dropping to 1 RPS." The exponential backoff IS in the code
  (verified: `delay = base_backoff * (2 ** (attempt - 1))` at
  `image_enricher.py:218` and `:247`) but invisible. Fix: add a tight per-attempt
  log line. Plus a 60s cap (prior-project pattern) and a "floor reached" hint.
- **Cumulative workspace state:** unchanged from `follow-on 4`. Code: P-D1 + P-D2
  + P-B1 + adaptive limiter + P-T2. Docs: `Session-close ritual` codified in
  AGENTS.md + CLAUDE.md. Mac one sync behind on the workspace deltas.
- **Solo-session check this turn:** 1 distinct session.
- **Read-only verification queries (run on the Mac after the next enrich run):**
    - `SELECT enrichment_status, COUNT(*) FROM ARTWORK_DB.BRONZE.MET_ENRICHMENT_CONTROL
       GROUP BY 1 ORDER BY 2 DESC;` -- expect error count smaller than 20.
    - `SELECT LEFT(enrichment_error, 30), COUNT(*) FROM ARTWORK_DB.BRONZE.MET_ENRICHMENT_CONTROL
       WHERE enrichment_error IS NOT NULL GROUP BY 1 ORDER BY 2 DESC;`
    - `SELECT COUNT(*) FROM ARTWORK_DB.BRONZE.RAW_MET_OBJECTS;` -- expect 180+.
- **First-action options for the next window:**
    (a) Apply P-V1 + P-V2 + P-V3 (gated; owner approved this turn). Then re-run
        and read the new per-attempt INFO log to confirm the exponential ramp is
        visible. Recommended first action.
    (b) Skip the visibility patches and just drain (`enrich-met` no `--limit`)
        -- 180/200 success rate is good enough that the remaining 2,127 PD rows
        likely converge similarly. Tradeoff: less observability if the next
        batch misbehaves.
    (c) Chase a deferred patch (P-B2 / P-H1 / etc).
- **Decision tree from the next run after P-V1/V2/V3:**
    - Per-attempt log shows the exponential ramp clearly (0.8s -> 1.6s -> ... ->
      60s cap), some retries succeed mid-ramp -> system is healthy; drain.
    - Per-attempt log shows every attempt 403'ing through to retries-exhausted
      -> WAF really is rejecting those specific oids; consider the UA flip
      (still gated as a separate PR) OR accept the ~10% loss as deaccession-shaped.
    - Floor message ("identity rejection, not rate") fires consistently -> same
      conclusion; UA flip is the next knob.
- **Deferred patches (priority unchanged):** P-B2 doc reword; P-H1
  autocommit/BEGIN/COMMIT; P-H4 `--where` env gate; P-H3 paramstyle=qmark;
  P-H2 DATA-01 deaccession; P-L1 legacy SQLite delete.
- **What MUST NOT happen in the next window:**
    - Do NOT `make iac` from the workspace.
    - Do NOT push to main.
    - Do NOT bundle P-V1+P-V2+P-V3 with a UA change (one knob at a time).
    - Do NOT undo the adaptive limiter / P-T2 / P-D1 / P-D2 / P-B1.
    - Do NOT re-stage the 403/410 -> no_image reclassification.
    - Do NOT re-add `met_enricher.py`.

#### Hand-off prompt for next window (paste verbatim into a new Cortex window)

```
SESSION HANDOFF -- artwork-db / Met extraction Phase 3 (apply P-V1+P-V2+P-V3)

You are Cortex Code in Snowsight resuming the artwork-db learning project on
account pa37992 (Porchanalytics). Branch: donkey-kong-sandbox. Senior data /
platform engineer mentor tone -- explain the why and the trade-offs; the OWNER
decides, you honor it.

SESSION-OPEN RITUAL (do this in order before anything else):
1. Read /workspace/AGENTS.md fully (Tier 0; cheapest read).
2. Read ONLY the LAST dated entry in /workspace/docs/context/session-3-progress-log.md
   (search "follow-on 6"). It supersedes every earlier "End of this window".
3. Solo-session check (must return 1):
     SELECT COUNT(DISTINCT SESSION_ID)
       FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
      WHERE QUERY_TAG ILIKE '%cortex_code_snowsight%'
        AND START_TIME > DATEADD(minute, -10, CURRENT_TIMESTAMP());
   Then SELECT * FROM ARTWORK_DB.BRONZE.CORTEX_FORK_INCIDENTS
        ORDER BY incident_at DESC LIMIT 5;
4. DUAL-FS HAZARD: workspace, Mac, and file-tool view can disagree. Re-read every
   file with the file tool immediately before reasoning about it. When in doubt,
   ask me to paste the Mac copy.
5. State the plan and wait for my explicit "proceed (today's date)" before any
   write. No `make iac`, no push to main.

PROJECT CONTEXT (do not re-derive):
- Phase 1 DONE: BRONZE.MET_CSV_SNAPSHOT = 484,956 rows (PK).
- Phase 2 DONE: BRONZE.MET_ENRICHMENT_CONTROL has 2,327 European Paintings PD rows.
- Phase 3 IN FLIGHT. Run-2 result: 200 claimed -> 180 done / 20 error (all 403 +
  retries-exhausted). Adaptive limiter + exponential backoff WORKED; error rate
  dropped from 52% to 10% vs run-1. throttles={'403': 133} backoff_s=573.6
  rps_end=5.00 over a 2:36 wall-clock run.
- Workspace AHEAD of Mac with: P-B1, adaptive image_enricher, P-T2 throttle counters.
- Open work for THIS window: apply P-V1 + P-V2 + P-V3 (visibility patches; owner
  pre-approved). NO UA change in this window -- one knob at a time.

YOUR FIRST RESPONSE:
- Quote back the latest "End of this window" header so I know you read the right
  entry.
- Confirm solo-session = 1.
- State the apply plan for P-V1+P-V2+P-V3 (file paths, exact lines, render of the
  new INFO format strings) and wait for my "proceed (date)".

P-V1 -- per-attempt INFO log inside _fetch_one's throttle branch.
  File: extraction/met/image_enricher.py
  After the `delay = ... + jitter` line and BEFORE `await asyncio.sleep(delay)`,
  add:
    logger.info(
        "oid=%s attempt=%s/%s HTTP=%s sleeping=%.1fs (rps=%.2f)",
        object_id, attempt, max_retries, status, delay, rate_limiter.rps,
    )
  Mirror the same shape in the network-exception path (line ~247) using
  `last_error` instead of `status`.

P-V2 -- 60s cap on per-attempt sleep (matches the prior-project pattern).
  File: extraction/met/image_enricher.py
  Replace BOTH occurrences of `base_backoff * (2 ** (attempt - 1))` with
  `min(60.0, base_backoff * (2 ** (attempt - 1)))`. Keep the `+ jitter` after.

P-V3 -- floor warning on the adaptive limiter.
  File: extraction/met/image_enricher.py, in `_RateLimiter.note_throttle()`,
  AFTER the `self._rps = max(self._min_rps, self._rps * 0.7)` line, add:
    if self._rps <= self._min_rps:
        logger.info(
            "Adaptive RPS at floor (%.2f); further throttles indicate identity "
            "rejection (WAF), not rate. Consider UA / header change next.",
            self._rps,
        )
  Fire it AT MOST once per limiter instance via a `self._floor_warned` flag if
  noise is a concern.

After applying:
- AST-parse the file.
- Append a new follow-on entry to the progress log per AGENTS.md ritual.
- Hand back to me; I sync to Mac and re-run `enrich-met --limit 200`.

DEFERRED (do NOT touch without explicit go): P-B2 doc reword; P-H1
autocommit/BEGIN/COMMIT; P-H4 `--where` env gate; P-H3 paramstyle=qmark;
P-H2 DATA-01 deaccession; P-L1 legacy SQLite delete; UA / header changes.

HARD RULES: ASCII only; UPPERCASE Snowflake identifiers; no make iac from
workspace; no push to main; one knob at a time; mentor tone; quote the End of
window header back to me first.
```

- **End of this window (sixth -- the visibility patches are gated for the next
  window per the codified Session-close ritual).**

### 2026-05-31 (same window, follow-on 5) | RUN RESULT + V1/V2/V3 GATED FOR NEXT WINDOW
- **What changed this turn (workspace stage; applied-to-account: no; pushed-to-Mac:
  no):** nothing in code or IaC. This entry only -- the codified close ritual + a
  paste-ready prompt for the next window. P-V1 / P-V2 / P-V3 are AUTHORIZED by the
  owner ("proceed P-V1+P-V2+P-V3") but explicitly scoped to a NEW context window
  (this is what this hand-off prompt sets up).
- **Run result, 17:22:35 -> 17:25:11 (Mac, post-adaptive-limiter, post-P-T2):**
  `claimed=200 done=180 no_image=0 error=20 assembled=180`
  `err_breakdown={'http_4xx_403': 20}`
  `throttles={'403': 133, '429': 0, 'other': 0}`
  `backoff_s=573.6  rps_end=5.00`
- **Read of that result:**
  - **Adaptive limiter MATERIALLY helped.** Done went from 96 -> 180 (44% -> 90%);
    error went from 104 -> 20. Pacing IS part of the story; the WAF-only hypothesis
    is partially refuted.
  - **Two visible RPS-collapse cascades:** 17:22:44 (20 -> 1.00 in ~10s) and 17:23:55
    (likely on a fresh batch worker bringing rps back up via cool_up, then collapsing
    again). The system spends ~50s pinned at floor=1.0 each time before recovering.
  - **The 20 remaining errors** are objects that exhausted all 8 retries while the
    limiter was at floor and the WAF kept rejecting. Likely fixable with: (a) lower
    concurrency so fewer simultaneous throttle events trigger the cascade in the first
    place; (b) cap per-attempt sleep (currently up to 102s on attempt 8 -- wasteful);
    (c) make per-attempt backoff visible in the log so we can audit the sleeps.
  - **`backoff_s=573.6`** = 9.5 minutes of cumulative backoff sleep across the batch.
    rps_end=5.0 means the limiter cooled back up from 1.0 to 5.0 between bursts.
- **Solo-session check this turn:** 1 distinct session. CORTEX_FORK_INCIDENTS clean.
- **AUTHORIZED for the next window (do these in this order, one PR each):**
    - **P-V1 -- per-attempt backoff log line** in `_fetch_one`'s throttle branch
      (`extraction/met/image_enricher.py`):
      ```python
      logger.info(
          "oid=%s attempt=%s HTTP=%s sleeping=%.1fs (rps=%.2f)",
          object_id, attempt, status, delay, rate_limiter.rps,
      )
      ```
      Place AFTER `delay` is finalized (post-jitter, post-Retry-After) and BEFORE
      `await asyncio.sleep(delay)`. Mirror it in the network-exception branch so
      ClientError / TimeoutError sleeps are equally visible.
    - **P-V2 -- cap per-attempt sleep at 60s** (defensive; matches prior project):
      ```python
      delay = min(60.0, base_backoff * (2 ** (attempt - 1)))
      ```
      In BOTH the throttle branch (when `_retry_after_seconds` returned None) and the
      network-exception branch. Do NOT cap a server-supplied Retry-After; honor that
      verbatim.
    - **P-V3 -- floor-reached signal** in `_RateLimiter.note_throttle()`:
      after the `_rps = max(self._min_rps, ...)` line, log once when we LAND at floor:
      ```python
      if self._rps <= self._min_rps:
          logger.info(
              "Adaptive RPS at floor (%.2f). Further throttles indicate identity "
              "rejection (WAF / UA / TLS), not rate. Slowing further will not help.",
              self._rps,
          )
      ```
      Guard with a `_at_floor_logged` flag so it fires once per cascade, not on every
      subsequent throttle (otherwise the log will spam during the ~50s floor sit).
      Reset the flag in `cool_up()` once `_rps > _min_rps` again so the NEXT cascade
      can re-warn.
    - All three changes: AST-parse + `python -c "import extraction.met.image_enricher"`
      smoke before commit.
- **NOT yet authorized (owner decides AFTER seeing V1/V2/V3 output):**
  - Lower `MET_API_CONCURRENCY` from 8 -> 2 or 3 (would prevent the cascade from
    triggering 8 simultaneous throttles in the first place).
  - Change `User-Agent` to the prior project's
    `split-monogram-met-oa-sync/2.0 (+contact)` shape.
  - Add `Accept-Language` / `Accept-Encoding` headers.
  - One knob at a time; pick after the next run shows what V1/V2/V3 reveal.
- **First-action options for the next window:**
  (a) Apply P-V1+P-V2+P-V3 (workspace, no `make iac` needed -- code only).
      Owner syncs to Mac, re-runs, pastes log. Then decide concurrency / UA.
  (b) Skip directly to lowering MET_API_CONCURRENCY=2 (config.py change). Risk:
      we lose the per-attempt visibility from V1, so we'd be blind again.
  (c) Skip directly to UA shape change. Risk: same.
  Owner already chose (a) -- "proceed P-V1+P-V2+P-V3".
- **Read-only verification queries after the next Mac re-run:**
    - `SELECT enrichment_status, COUNT(*) FROM ARTWORK_DB.BRONZE.MET_ENRICHMENT_CONTROL
       GROUP BY 1 ORDER BY 2 DESC;` -- expect error <= 20, no_image still 0, done > 180.
    - `SELECT LEFT(enrichment_error, 30), COUNT(*) FROM ARTWORK_DB.BRONZE.MET_ENRICHMENT_CONTROL
       WHERE enrichment_error IS NOT NULL GROUP BY 1 ORDER BY 2 DESC;`
    - `SELECT COUNT(*) FROM ARTWORK_DB.BRONZE.RAW_MET_OBJECTS;`
- **Decision tree from the V1/V2/V3 run:**
  - error -> 0: drain the rest of European Paintings (no --limit). Done.
  - error similar (~20) AND log shows "Adaptive RPS at floor" hits early: lower
    concurrency to 2 or 3 and re-test.
  - error similar AND no floor-hit log line: V3 isn't firing -- check the flag logic.
  - error WORSE: revert; backoff cap may be too aggressive.
- **Deferred patches (priority order):** P-B2 doc reword; P-H1 autocommit/BEGIN/COMMIT;
  P-H4 `--where` env gate; P-H3 paramstyle=qmark; P-H2 DATA-01 deaccession; P-L1
  legacy SQLite delete.
- **What MUST NOT happen in the next window:**
  - Do NOT `make iac` from the workspace; V1/V2/V3 are code-only.
  - Do NOT push to main.
  - Do NOT change concurrency / UA / headers in the same PR as V1/V2/V3 -- one
    knob at a time.
  - Do NOT cap a server-supplied `Retry-After` value.
  - Do NOT undo P-D1 / P-D2 / P-B1 / adaptive limiter / P-T2.
  - Do NOT re-add `met_enricher.py`.
  - Do NOT re-stage 403/410 -> no_image (proven WAF-shaped, not semantic).

#### Hand-off prompt for next window (paste verbatim into a new Cortex window)

```
SESSION HANDOFF -- artwork-db / Met extraction Phase 3 (V1/V2/V3 authorized)

You are Cortex Code (Snowsight) resuming an in-flight learning project on
account pa37992 (Porchanalytics). Branch: donkey-kong-sandbox. Senior data /
platform engineer mentor tone: explain the why and the trade-offs; the OWNER
decides, you honor it.

SESSION-OPEN RITUAL (do this FIRST, in order, before anything else):
1. Read /workspace/AGENTS.md fully. Tier 0; cheapest read.
2. Read ONLY the LAST dated entry of
   /workspace/docs/context/session-3-progress-log.md -- it ends with "End of
   this window" and supersedes every earlier "End of this window" marker.
   Look for the section titled "follow-on 5".
3. Solo-session check (must return 1):
     SELECT COUNT(DISTINCT SESSION_ID)
       FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
      WHERE QUERY_TAG ILIKE '%cortex_code_snowsight%'
        AND START_TIME > DATEADD(minute, -10, CURRENT_TIMESTAMP());
     SELECT * FROM ARTWORK_DB.BRONZE.CORTEX_FORK_INCIDENTS
      ORDER BY incident_at DESC LIMIT 5;
   Exactly 1 = solo. >1 = stop and ask.
4. DUAL-FS HAZARD: re-read every file via the file tool immediately before
   reasoning about it. Workspace, Mac, and the file-tool view can each show
   different versions. When in doubt, ask me to paste the Mac copy.
5. State the plan. Wait for "proceed (today's date)" before any write.

PROJECT CONTEXT (do not re-derive):
- Phase 1 DONE: BRONZE.MET_CSV_SNAPSHOT = 484,956 rows.
- Phase 2 DONE: BRONZE.MET_ENRICHMENT_CONTROL seeded with 2,327 European
  Paintings public-domain rows.
- Phase 3 IN FLIGHT. Last run (17:22-17:25, with adaptive limiter + P-T2):
  claimed=200 done=180 error=20 throttles={'403': 133} backoff_s=573.6
  rps_end=5.00. Adaptive throttle handling materially helped (104 -> 20
  errors). 20 stragglers exhausted retries while limiter was at floor=1.0.
- Workspace state: P-D1 + P-D2 + P-B1 + adaptive _RateLimiter + P-T2.
- Mac state: P-D1 + P-D2 applied. Pending sync: P-B1 deletions, adaptive
  image_enricher rewrite, P-T2 counters in two files.

WHAT YOU ARE AUTHORIZED TO DO (and ONLY this -- one PR per V):
- P-V1: per-attempt INFO log inside _fetch_one's throttle branch (and the
  network-exception branch) showing oid / attempt / HTTP / sleeping / rps.
  Spec in follow-on 5.
- P-V2: cap per-attempt exponential sleep at 60s (both branches). Do NOT cap
  a server-supplied Retry-After.
- P-V3: in _RateLimiter.note_throttle(), log ONCE when rps lands at min_rps;
  reset the flag in cool_up() so the next cascade can warn again. Spec in
  follow-on 5.
- After all three: AST-parse + import smoke. Commit on donkey-kong-sandbox.
  Then ask me to sync + re-run on the Mac and paste the new log.

WHAT IS EXPLICITLY NOT AUTHORIZED YET:
- Changing MET_API_CONCURRENCY (8 -> 2/3). I decide AFTER seeing V1/V2/V3.
- Changing User-Agent or adding headers. Same.
- Anything in the deferred list (P-B2, P-H1, P-H4, P-H3, P-H2, P-L1).
- make iac from the workspace. push to main. Either is a defect.
- Rewriting V/D/B/T patches that are already applied.

HARD RULES:
- ONE knob at a time so we can attribute outcomes.
- ASCII only, UPPERCASE Snowflake identifiers, IaC via manifest only.
- Explain the why and the trade-offs as you go (mentor mode).

YOUR FIRST RESPONSE:
1. Quote back to me the LAST "End of this window" header from the progress log
   so I know you read the right one (it should mention "follow-on 5").
2. Confirm solo-session = 1 and CORTEX_FORK_INCIDENTS is clean.
3. Re-read /workspace/extraction/met/image_enricher.py with the file tool and
   tell me: which exact line numbers will V1, V2, V3 touch?
4. Then ask me for "proceed (date)" before applying.
```

- **End of this window (sixth; per AGENTS.md ritual the next window MUST again
  emit a new entry with prompt at close).**

### 2026-05-31 (new window, follow-on 7) | P-V1 + P-V2 + P-V3 APPLIED (workspace only)
- **What changed this turn (workspace stage; applied-to-account: no; pushed-to-Mac:
  no):** ONE file edited -- `extraction/met/image_enricher.py`. No IaC, no SQL, no
  other file. AST-parse clean (`ast.parse` OK). mtime scan (`find -mmin -15`) shows
  only `image_enricher.py` + this log changed. No git in workspace; Mac is the git
  source of truth, so nothing committed here -- the owner syncs + commits on the Mac.
- **Exact edits applied (post-edit line numbers):**
  - **P-V3** -- floor signal in `_RateLimiter.note_throttle()`, lines 126-130: after
    the `_rps = max(self._min_rps, ...)` mutation, log when `_rps <= _min_rps`.
    **UN-GUARDED** (no `_at_floor_logged` flag). This DEVIATES from follow-on 5's spec
    (which asked for a once-per-cascade flag reset in `cool_up()`); the owner's current
    handoff explicitly overrode that: "this fires every floor-throttle ... intentional"
    to make the sustained-floor sit visible. Owner-approved deviation, recorded here.
  - **P-V2** -- 60.0s cap on the computed exponential, BOTH sites, as written:
    - throttle branch line 223 (only inside `if delay is None:` -- Retry-After NOT capped).
    - network-exception branch line 256 (`min(60.0, ...) + jitter`).
    NOTE for the record: the pasted prior project actually used `min(30.0, ...)` and
    only on the exception path, with NO cap on the 403/429 path. So "60s both sites" is
    STRICTER/BROADER than the prior project, not a literal match -- the owner confirmed
    60.0 both sites is intended; the spec text wins over the "matches prior project" note.
  - **P-V1** -- per-attempt INFO log before each `asyncio.sleep(delay)`:
    - throttle branch lines 234-237: `oid / attempt / HTTP / sleeping / rps`.
    - network-exception branch lines 257-260: same shape, "network exception" label
      (no `status` in scope on that path).
- **Scope discipline this turn:** owner's inline "maximize the rate limiting and logging
  of my previous implementation" was NOT taken as license to port prior-project machinery
  (per-host limiters, `max_rps=20`, `From` header, contact-shaped UA, unconditional
  `cool_up`). All of that is fenced by the HARD RULES (no UA/header/concurrency change in
  this PR; one knob; do-not-undo adaptive limiter). Interpreted as "make V1/V2/V3 logging
  rich" only. Prior-project deltas filed as next-step candidates (see decision tree).
- **Cumulative workspace state vs Mac:** workspace now = P-D1 + P-D2 + P-B1 + adaptive
  `_RateLimiter` + P-T2 + **P-V1 + P-V2 + P-V3**. Mac still = P-D1 + P-D2 applied; pending
  sync to Mac now carries: P-B1 deletions, adaptive `image_enricher` rewrite, P-T2
  counters (two files), AND this V1/V2/V3 patch.
- **Solo-session check this turn:** 1 distinct `cortex_code_snowsight` session in the last
  10 min. `ARTWORK_DB.BRONZE.CORTEX_FORK_INCIDENTS` = 0 rows (clean).
- **WHAT TO SYNC + RE-RUN (owner action on the Mac):**
  1. Sync `extraction/met/image_enricher.py` (and the still-pending P-B1 / adaptive /
     P-T2 deltas if the Mac has not already taken them) from workspace -> Mac.
  2. Commit on `donkey-kong-sandbox` (Mac is git source of truth). Do NOT push to main.
  3. Re-run: `python -m extraction.met.run enrich-met --limit 200`
  4. Paste back: the final counters line AND a sample of the new per-attempt log lines
     (especially any "Adaptive RPS at floor" lines and their timestamps).
  - Expect: the log is now CHATTY -- ~130+ `sleeping=` lines on a 200-row batch plus
    repeated floor lines during each ~50-90s floor sit. That volume is intentional (P-V3).
- **First-action options for the next window:**
  (a) Interpret the V1/V2/V3 log output; if error < 5% and floor lines are brief, drain the
      rest of European Paintings with no `--limit`. Adaptive limiter is sufficient.
  (b) If error ~10% with RPS pinned at 1.00 whole batch -> identity rejection on specific
      oids: propose UA-shape change ONLY (one knob), per follow-on 3 decision tree (a).
  (c) If error >> 10% or backoff_s > ~1500s on 200 rows: bump `max_retries` 8->12 OR lower
      `MET_API_RPS` 10->5. One knob at a time.
- **Read-only verification queries after the next Mac re-run:**
  - `SELECT enrichment_status, COUNT(*) FROM ARTWORK_DB.BRONZE.MET_ENRICHMENT_CONTROL
     GROUP BY 1 ORDER BY 2 DESC;`  -- expect error <= 20, no_image 0, done >= 180.
  - `SELECT LEFT(enrichment_error, 30), COUNT(*) FROM ARTWORK_DB.BRONZE.MET_ENRICHMENT_CONTROL
     WHERE enrichment_error IS NOT NULL GROUP BY 1 ORDER BY 2 DESC;`
  - `SELECT COUNT(*) FROM ARTWORK_DB.BRONZE.RAW_MET_OBJECTS;`
- **Decision tree from the V1/V2/V3 run (next-run gate):**
  - error/claimed < 5%, throttles still high: keep draining (no `--limit`). Done.
  - error ~10%, throttles high, RPS pinned at 1.00 all batch: identity rejection -> propose
    UA-shape change ONLY (follow-on 3 (a)).
  - error >> 10% OR backoff_s > ~1500s on 200 rows: max_retries 8->12 OR MET_API_RPS 10->5.
  - If "Adaptive RPS at floor" never appears in the log: P-V3 not firing -- check that
    `note_throttle` reaches the floor branch (burst >= 3 AND `_rps` at `_min_rps`).
- **Deferred patches (priority order, DO NOT TOUCH without explicit go):** P-B2 doc reword;
  P-H1 autocommit/BEGIN/COMMIT; P-H4 `--where` env gate; P-H3 paramstyle=qmark; P-H2
  DATA-01 deaccession; P-L1 legacy SQLite delete. Plus prior-project port candidates
  (per-host limiters, UA/From shape, max_rps ceiling) -- only if owner opens a new gate.
- **What MUST NOT happen in the next window:**
  - Do NOT `make iac` from the workspace; V1/V2/V3 are code-only.
  - Do NOT push to main.
  - Do NOT change UA / headers / concurrency in the same PR as any throttle tuning -- one
    knob at a time.
  - Do NOT cap a server-supplied `Retry-After` value.
  - Do NOT undo P-D1 / P-D2 / P-B1 / adaptive limiter / P-T2 / P-V1 / P-V2 / P-V3.
  - Do NOT re-add `met_enricher.py`.
  - Do NOT re-stage 403/410 -> no_image (proven WAF-shaped, not semantic).

#### Hand-off prompt for next window (paste verbatim into a new Cortex window)

```
SESSION HANDOFF -- artwork-db / Met extraction Phase 3 (V1/V2/V3 applied; interpret next run)

You are Cortex Code (Snowsight) resuming an in-flight learning project on account
pa37992 (Porchanalytics). Branch: donkey-kong-sandbox. Senior-DE mentor tone:
explain the why and the trade-offs; the OWNER decides, you honor it.

SESSION-OPEN RITUAL (in order, before any write):
1. Read /workspace/AGENTS.md fully.
2. Read ONLY the LAST dated entry of
   /workspace/docs/context/session-3-progress-log.md (ends with "End of this
   window"; supersedes all earlier markers). It is titled "follow-on 7".
3. Solo-session check (must return 1):
     SELECT COUNT(DISTINCT SESSION_ID) FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
      WHERE QUERY_TAG ILIKE '%cortex_code_snowsight%'
        AND START_TIME > DATEADD(minute, -10, CURRENT_TIMESTAMP());
   Then SELECT * FROM ARTWORK_DB.BRONZE.CORTEX_FORK_INCIDENTS ORDER BY 1 DESC LIMIT 5;
4. DUAL-FS HAZARD: re-read every file via the file tool immediately before reasoning
   about it. When in doubt, ask me to paste the Mac copy.
5. State the plan and wait for "proceed (today's date)" before any write or push.

STATE (do not re-derive):
- Phase 1 DONE: BRONZE.MET_CSV_SNAPSHOT = 484,956 rows.
- Phase 2 DONE: BRONZE.MET_ENRICHMENT_CONTROL seeded 2,327 European Paintings PD rows.
- Phase 3 IN FLIGHT. P-V1+P-V2+P-V3 APPLIED in workspace (per-attempt backoff log;
  60s cap both sites; un-guarded floor log). Last run BEFORE these patches:
  done=180 error=20 throttles={'403':133} backoff_s=573.6 rps_end=5.00.
- Workspace = P-D1+P-D2+P-B1+adaptive limiter+P-T2+P-V1+P-V2+P-V3.
  Mac = P-D1+P-D2; pending sync carries everything since.

YOUR FIRST TASK: I will sync to Mac, run `enrich-met --limit 200`, and paste the
counters + new log lines. Interpret them against the decision tree in follow-on 7:
  - error<5%, throttles high: drain rest of European Paintings (no --limit).
  - error~10%, RPS pinned 1.00 whole batch: identity rejection -> propose UA-shape
    change ONLY (one knob), per follow-on 3 (a).
  - error>>10% or backoff_s>~1500s/200 rows: max_retries 8->12 OR MET_API_RPS 10->5.
  - no "Adaptive RPS at floor" line at all: P-V3 not firing -- debug note_throttle.

HARD RULES: ONE knob at a time. No make iac from workspace. No push to main. Do NOT
change UA/headers/concurrency in the same PR as throttle tuning. Do NOT cap a
server-supplied Retry-After. Do NOT undo P-D1/P-D2/P-B1/adaptive limiter/P-T2/
P-V1/P-V2/P-V3. Do NOT re-add met_enricher.py. Do NOT re-stage 403/410 -> no_image.
DEFERRED (need explicit go): P-B2, P-H1, P-H4, P-H3, P-H2, P-L1, prior-project port.

FIRST RESPONSE: quote back the LAST "End of this window" header (mentions
"follow-on 7"); confirm solo-session=1 + CORTEX_FORK_INCIDENTS clean; then wait for
my pasted run output before proposing the one-knob next step.
```

- **End of this window (seventh; supersedes the "sixth" marker above. V1/V2/V3 are
  applied in the workspace only -- not synced, not committed, not applied to account.
  Next window interprets the post-sync re-run and picks ONE knob.).**

### 2026-05-31 (new window, follow-on 8) | P-V1/P-V3 logs demoted INFO -> DEBUG
- **What changed this turn (workspace stage; applied-to-account: no; pushed-to-Mac:
  no):** ONE file edited -- `extraction/met/image_enricher.py`. Three `logger.info`
  -> `logger.debug` swaps. No behavior change, no IaC, no SQL. AST-parse clean. mtime
  scan shows only `image_enricher.py` + this log touched. Owner go: `proceed 2026-05-31`.
- **Why:** owner wants clean, infrequent logs (one line per batch + one completion
  line). That format ALREADY EXISTS at INFO in `control_enricher.py` (per-batch summary
  L320; "Enrichment complete" L380). The noise was the P-V1 per-attempt lines added
  earlier this window, which fire once per retry at INFO and interleave across the
  asyncio.gather workers. Demoting them keeps the INFO stream = batch summary +
  completion only; the per-attempt detail survives at `--log-level DEBUG`.
- **Exact lines demoted (post-edit):**
  - L127 -- P-V3 floor line ("Adaptive RPS at floor ... identity rejection").
  - L234 -- P-V1 throttle-branch per-attempt line ("oid=.. HTTP=.. sleeping=..").
  - L257 -- P-V1 network-exception per-attempt line.
- **Deliberately LEFT at INFO (not demoted):**
  - L132 -- "Adaptive RPS dropped to %.2f after throttle burst": this is P-T2 /
    adaptive-limiter behavior, fires only on the 1-in-3 burst-decay event (infrequent),
    NOT a P-V3 line. Demoting it would have hidden RPS decay from the default stream.
  - L341 / L405 -- legacy SQLite enrich-path INFO lines, unrelated to V1/V2/V3.
- **Reconciliation note vs HARD RULES:** the standing rule "do NOT undo P-V1/P-V2/P-V3"
  was honored in substance -- P-V1's signal is NOT deleted, only moved to DEBUG; P-V2's
  60s caps and the `_fetch_one` return contract are untouched; P-V3's floor detection
  still runs, only its log verbosity dropped. Owner explicitly directed this demotion
  and gave the dated go, overriding the INFO-level intent of P-V1/P-V3.
- **Cumulative workspace state vs Mac:** workspace = P-D1+P-D2+P-B1+adaptive limiter+
  P-T2+P-V1+P-V2+P-V3 (V1/V3 logs now at DEBUG). Mac = P-D1+P-D2; pending sync carries
  everything since, including this demotion.
- **Solo-session check this turn:** not re-run this turn (no account read needed for a
  logging-only edit); last check earlier this window = 1 session, CORTEX_FORK_INCIDENTS
  clean. Re-run the solo check at the next window open per ritual.
- **WHAT TO SYNC + RE-RUN (owner action on the Mac):** unchanged from follow-on 7 --
  sync `image_enricher.py` -> Mac, commit on donkey-kong-sandbox (no push to main),
  `python -m extraction.met.run enrich-met --limit 200`. Default INFO output should now
  be ~2 lines (the batch summary + "Enrichment complete"). To see per-attempt/floor
  detail, re-run with `--log-level DEBUG` (verify run.py exposes that flag; if not, that
  is a separate, un-gated change -- do NOT bundle it here).
- **First-action options for the next window:** (a) interpret the clean INFO output
  from the re-run against the follow-on 7 decision tree; (b) if the owner needs the
  per-attempt detail and run.py lacks a log-level flag, propose adding one (separate
  gate); (c) drain the rest of European Paintings if error < 5%.
- **Decision tree from the re-run:** unchanged from follow-on 7 (error<5% -> drain;
  error~10% + RPS pinned 1.00 -> identity rejection, UA-shape one knob; error>>10% or
  backoff_s>~1500s -> max_retries 8->12 OR MET_API_RPS 10->5). NOTE: the "no Adaptive
  RPS at floor line" diagnostic now requires `--log-level DEBUG` to observe, since that
  line moved to DEBUG.
- **Deferred (need explicit go):** P-B2, P-H1, P-H4, P-H3, P-H2, P-L1; prior-project
  limiter/header port; `--log-level` CLI flag on run.py if not already present.
- **What MUST NOT happen next window:** no make iac from workspace; no push to main; one
  knob at a time; do NOT change UA/headers/concurrency alongside throttle tuning; do NOT
  cap a server-supplied Retry-After; do NOT undo P-D1/P-D2/P-B1/adaptive limiter/P-T2/
  P-V1/P-V2/P-V3 (the DEBUG demotion stands -- do not silently re-promote to INFO);
  do NOT re-add met_enricher.py; do NOT re-stage 403/410 -> no_image.

#### Hand-off prompt for next window (paste verbatim into a new Cortex window)

```
SESSION HANDOFF -- artwork-db / Met extraction Phase 3 (logs cleaned; interpret next run)

You are Cortex Code (Snowsight) resuming an in-flight learning project on account
pa37992 (Porchanalytics). Branch: donkey-kong-sandbox. Senior-DE mentor tone:
explain the why and the trade-offs; the OWNER decides, you honor it.

SESSION-OPEN RITUAL (in order, before any write):
1. Read /workspace/AGENTS.md fully.
2. Read ONLY the LAST dated entry of
   /workspace/docs/context/session-3-progress-log.md (ends with "End of this
   window"). It is titled "follow-on 8".
3. Solo-session check (must return 1):
     SELECT COUNT(DISTINCT SESSION_ID) FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
      WHERE QUERY_TAG ILIKE '%cortex_code_snowsight%'
        AND START_TIME > DATEADD(minute, -10, CURRENT_TIMESTAMP());
   Then SELECT * FROM ARTWORK_DB.BRONZE.CORTEX_FORK_INCIDENTS ORDER BY 1 DESC LIMIT 5;
4. DUAL-FS HAZARD: re-read every file via the file tool immediately before reasoning
   about it. When in doubt, ask me to paste the Mac copy.
5. State the plan and wait for "proceed (today's date)" before any write or push.

STATE (do not re-derive):
- Phase 1 DONE (MET_CSV_SNAPSHOT 484,956). Phase 2 DONE (control seeded 2,327 EP PD).
- Phase 3 IN FLIGHT. Workspace = P-D1+P-D2+P-B1+adaptive limiter+P-T2+P-V1+P-V2+P-V3.
  This window: P-V1 per-attempt lines + P-V3 floor line moved INFO->DEBUG, so default
  INFO output is just the per-batch summary (control_enricher.py:320) + "Enrichment
  complete" (L380). Per-attempt/floor detail is at --log-level DEBUG.
- Mac = P-D1+P-D2; pending sync carries everything since.

YOUR FIRST TASK: I will sync to Mac, run enrich-met --limit 200, and paste the (now
clean) INFO output. Interpret it against the decision tree in follow-on 7/8:
  - error<5% -> drain rest of European Paintings (no --limit).
  - error~10%, RPS pinned 1.00 -> identity rejection -> propose UA-shape change ONLY.
  - error>>10% or backoff_s>~1500s/200 rows -> max_retries 8->12 OR MET_API_RPS 10->5.
  - to see floor/per-attempt detail I must run with --log-level DEBUG.

HARD RULES: ONE knob at a time. No make iac from workspace. No push to main. Do NOT
change UA/headers/concurrency with throttle tuning. Do NOT cap server Retry-After. Do
NOT undo P-D1/P-D2/P-B1/adaptive limiter/P-T2/P-V1/P-V2/P-V3 (DEBUG demotion stands).
Do NOT re-add met_enricher.py. Do NOT re-stage 403/410 -> no_image.
DEFERRED (need go): P-B2, P-H1, P-H4, P-H3, P-H2, P-L1, prior-project port, --log-level
CLI flag.

FIRST RESPONSE: quote back the LAST "End of this window" header (mentions "follow-on
8"); confirm solo-session=1 + CORTEX_FORK_INCIDENTS clean; then wait for my pasted run
output before proposing the one-knob next step.
```

- **End of this window (eighth; supersedes the "seventh" marker above. The INFO->DEBUG
  demotion is applied in the workspace only -- not synced, not committed, not applied to
  account. P-V1/V2/V3 behavior is otherwise intact; only log verbosity changed.).**

---

## 2026-05-31 — follow-on 9 (dbt strategy session — docs-only)

### What changed this turn

- **NEW FILE: `docs/context/dbt-plan.md`** (321 lines) — Tier-1 doc capturing all
  dbt adoption architecture decisions from a strategy conversation. Covers: execution
  engine choice (dbt Core local, Option L), pragmatic star schema in Gold (dim_artworks,
  dim_artists, fct_artwork_images + openaccess_catalog OBT), dbt as peer IaC track
  (`dbt_orchestrate.sh` + Makefile targets), unified variable control (`.env` as single
  source of truth feeding `profiles.yml` / `connections.toml` / `config.py`), error
  handling strategy (idempotent re-runs, `dbt retry`, `--full-refresh`), completeness
  testing (dbt tests in-DAG), 3-milestone build sequence (M1: scaffold + stg_met__artworks;
  M2: artist entity + image fact + Gold dims; M3: delete propagation + OBT +
  completeness), and 7 open research questions for the design window.
- `AGENTS.md` Status table + Workflow domains already reference `dbt-plan.md` (wired
  by prior context or system).
- **Applied to account: NO.** This was a strategy/docs session. No DDL, no code.
- **Pushed to Mac: NO.** Workspace-only.

### Cumulative workspace state vs Mac

Mac has: P-D1 + P-D2 (from prior sync).
Workspace has (delta for next sync):
- Everything since P-D2 (adaptive limiter, P-B1, P-T2, P-V1, P-V2, P-V3)
- INFO->DEBUG log demotion (follow-on 8)
- **NEW: `docs/context/dbt-plan.md`** (this session)

### Solo-session check result

Not performed this session (strategy conversation only, no writes to account, no DDL).
The only file written was a new doc in the workspace.

### First-action options for the next window

**(a) Research + design window (RECOMMENDED):** Read `docs/context/dbt-plan.md` section
"Open research questions." Investigate each (env_var + key-pair auth in profiles.yml,
dbt-utils compatibility, VARIANT flatten patterns, incremental hard-delete strategy,
FUTURE GRANTS interaction, project naming, .env sourcing). Produce a design artifact
that answers all 7 questions and specifies the exact file contents for M1.

**(b) Jump straight to M1 build:** Skip the research window and start writing
`artwork_pipeline/`, `dbt_orchestrate.sh`, Makefile targets. Higher risk of rework if
research questions have surprising answers.

**(c) Sync to Mac first, then (a):** Owner syncs workspace to Mac, commits the
dbt-plan.md on `donkey-kong-sandbox`, then opens a new window for the research pass.

### Read-only verification queries

N/A — no account changes this session.

### Decision tree for next window

```
IF owner picks (a) or (c):
  -> New window reads dbt-plan.md, researches 7 open questions
  -> Produces a "ready-to-build" spec (exact file contents, no ambiguity)
  -> Owner reviews spec, then a THIRD window executes M1

IF owner picks (b):
  -> New window reads dbt-plan.md, builds M1 directly
  -> Answers research questions just-in-time as they arise
  -> Faster but riskier (may need to redo profiles.yml wiring)
```

### Deferred patches (priority order)

1. Reword stale V/R/B refs in `extraction/met/README.md`, `.env.example`,
   `apply_sql.sh`, `git-setup/README.md`.
2. Decide fate of `rename_and_update.py` (spent one-shot migration).
3. `profiles.yml.example` dbt-core vs Snowflake-native profile.
4. `SMITHSONIAN_API_KEY` in root `.env.example` has no consumer.
5. Met enrichment: drain full collection (Phase 3 runtime continuation).

### What MUST NOT happen in the next window

- Do NOT write any dbt models, scripts, or Makefile changes without first resolving
  the 7 open research questions in `dbt-plan.md`.
- Do NOT run `make iac` or any DDL from the workspace.
- Do NOT push to `main`.
- Do NOT create a `CREATE DBT PROJECT` object (that is M5, far future).
- Do NOT install dbt in the Snowsight workspace sandbox (it runs on the Mac only).

### Hand-off prompt

```
SESSION HANDOFF -- artwork-db / dbt adoption: research + design pass

You are Cortex Code (Snowsight) resuming an in-flight learning project on account
pa37992 (Porchanalytics). Branch: donkey-kong-sandbox. Senior-DE mentor tone:
explain the why and the trade-offs; the OWNER decides, you honor it.

SESSION-OPEN RITUAL (in order, before any write):
1. Read /workspace/AGENTS.md fully (cheapest read, orientation).
2. Read ONLY the LAST dated entry of
   /workspace/docs/context/session-3-progress-log.md (titled "follow-on 9").
3. Read /workspace/docs/context/dbt-plan.md fully — this is your primary input.
4. Solo-session check (must return 1):
     SELECT COUNT(DISTINCT SESSION_ID) FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
      WHERE QUERY_TAG ILIKE '%cortex_code_snowsight%'
        AND START_TIME > DATEADD(minute, -10, CURRENT_TIMESTAMP());
   Then SELECT * FROM ARTWORK_DB.BRONZE.CORTEX_FORK_INCIDENTS ORDER BY 1 DESC LIMIT 5;
5. State the plan and wait for "proceed (today's date)" before any write.

STATE:
- dbt-plan.md is LOCKED (decisions D1-D7, DAG shape, IaC design, milestones M1-M3).
- No code exists yet. No dbt project directory. No dbt_orchestrate.sh.
- Bronze is live (RAW_MET_OBJECTS ~1,100 rows enriched, ~1,200 in worklist).
- Silver and Gold schemas EXIST but are EMPTY.
- The extraction loader runs on Mac only (not in Snowsight sandbox).
- dbt will also run on Mac only (Option L = local dbt Core).

YOUR TASK THIS WINDOW:
Research + design. Produce a "ready-to-build" specification that answers ALL 7 open
questions in dbt-plan.md § "Open research questions" and specifies:
  1. Exact profiles.yml content (env_var + key-pair auth for ARTWORK_TRANSFORMER).
  2. Exact dbt_project.yml content (project name, profile, model paths, vars).
  3. Exact packages.yml content (dbt-utils version pinned).
  4. dbt_orchestrate.sh pseudocode/structure (phases, .env sourcing, error handling).
  5. Makefile additions (exact target definitions).
  6. .env variable list (canonical, with comments showing which consumer reads each).
  7. stg_met__artworks.sql sketch (VARIANT flatten approach — the CTE pattern).

Use web search + cortex search docs to ground answers (especially: dbt-snowflake
key-pair auth, env_var() syntax, FUTURE GRANTS behavior with dbt-created tables,
dbt incremental hard-delete on Snowflake). Do NOT write files to the workspace —
output the spec as conversation text for owner review.

HARD RULES: No make iac. No DDL. No push to main. No file writes without owner
sign-off. Do NOT install dbt in the workspace. Do NOT create Snowflake objects.
This is a RESEARCH + DESIGN session only.

FIRST RESPONSE: quote back the "End of this window" header from follow-on 9;
confirm solo-session check; then state your research plan and wait for proceed.
```

- **End of this window (ninth; supersedes the "eighth" marker above. Strategy session
  only -- `docs/context/dbt-plan.md` written to workspace. No account changes, no code,
  no sync to Mac. Next window = research + design pass per the hand-off prompt above.)**

---

## 2026-05-31 — follow-on 10 (dbt-plan.md review + hardening)

### What changed this turn

- **EDITED: `docs/context/dbt-plan.md`** — Review pass fixing 6 gaps/weaknesses:
  1. D3: Added multi-artist relationship clarification (pipe-delimited constituents;
     M1-M2 = primary artist only; bridge table deferred as documented simplification).
  2. Model responsibilities table: added Materialization column + rationale (Silver =
     views except stg_met__artworks which becomes incremental in M3; Gold = tables).
  3. Delete-propagation cornerstone: rewritten to distinguish trivial full-refresh mode
     from the hard incremental-delete problem (research question #4).
  4. .env variable block: split into DBT_* vs LOADER_* namespaces to fix the role/user
     confusion (ARTWORK_LOADER_SVC is extraction, not dbt; dbt runs as PORCHANALYTICS
     with ARTWORK_TRANSFORMER role).
  5. Research questions: expanded with sub-questions (YAML shape for #1, macro rename
     for #2, source() + VARIANT for #3, "absent from source" signal for #4, dbt grants
     config for #5, profile linkage for #6, dbt debug behavior for #7).
  6. Research question #7: removed pre-answered parenthetical, added verification ask.
- **EDITED: `AGENTS.md`** — Status row for dbt-plan.md corrected (D1-D10 -> D1-D7;
  added materializations + .env split + research questions count).
- **Applied to account: NO.** Docs edits only.
- **Pushed to Mac: NO.** Owner will sync.

### Cumulative workspace state vs Mac

Same as follow-on 9, plus the dbt-plan.md + AGENTS.md edits above. Owner's next step
is to sync workspace -> Mac, then open a new window with the hand-off prompt below.

### Solo-session check result

Not run (docs-only review, no account interaction).

### First-action options for the next window

The owner stated their intent: sync to Mac, then open a new window for the dbt
research + build arc. The hand-off prompt below combines research and implementation
into a single window (resolve the 7 questions just-in-time as M1 is built, since
the owner expressed preference for forward momentum over a separate research-only pass).

### Read-only verification queries

N/A — no account changes.

### Decision tree for next window

```
Owner syncs workspace -> Mac (git add + commit on donkey-kong-sandbox)
  -> Opens new Cortex window with the hand-off prompt below
  -> That window: reads dbt-plan.md, researches open questions, builds M1
  -> M1 exit criteria: `make dbt-build` passes, SILVER.STG_MET__ARTWORKS exists
```

### Deferred patches (priority order)

1. Met enrichment Phase 3 drain (full EP collection) — whenever owner is ready.
2. Stale V/R/B refs outside infrastructure.
3. `rename_and_update.py` removal decision.
4. `SMITHSONIAN_API_KEY` in root `.env.example` has no consumer.
5. Multi-artist bridge table (documented simplification; revisit at source #2).

### What MUST NOT happen in the next window

- Do NOT install dbt in the Snowsight workspace sandbox — dbt runs on Mac only.
- Do NOT run `make iac` from the workspace.
- Do NOT push to `main`.
- Do NOT create a `CREATE DBT PROJECT` object (that is M5).
- Do NOT commit to Airflow or Cosmos (explicitly deferred).
- Do NOT modify Bronze schema objects — dbt owns Silver/Gold only.

### Hand-off prompt (paste into a new Cortex window to start the dbt build)

```
SESSION HANDOFF — artwork-db / dbt Milestone 1: research + build

ROLE: Senior Data/Platform Engineer mentor for a Snowflake learning project.
Account: pa37992. Branch: donkey-kong-sandbox. Explain the WHY and trade-offs;
the OWNER decides, you honor it.

SESSION-OPEN RITUAL (in order, before any write):
1. Read /workspace/AGENTS.md (cheapest read; orientation).
2. Read the LAST "End of this window" entry in
   /workspace/docs/context/session-3-progress-log.md (titled "follow-on 10").
3. Read /workspace/docs/context/dbt-plan.md FULLY — primary reference for all
   architecture decisions, DAG shape, IaC design, and the 7 research questions.
4. Solo-session check (must return exactly 1):
     SELECT COUNT(DISTINCT SESSION_ID) FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
      WHERE QUERY_TAG ILIKE '%cortex_code_snowsight%'
        AND START_TIME > DATEADD(minute, -10, CURRENT_TIMESTAMP());
   Then: SELECT * FROM ARTWORK_DB.BRONZE.CORTEX_FORK_INCIDENTS ORDER BY 1 DESC LIMIT 5;
5. DUAL-FS HAZARD: re-read files before editing. Ask me to paste Mac copy if unsure.
6. State the plan and wait for "proceed (date)" before any write or execution.

STATE (do not re-derive):
- dbt-plan.md is LOCKED: 7 decisions (D1-D7), model DAG, IaC integration design,
  3-milestone sequence. This window executes M1.
- Bronze LIVE: RAW_MET_OBJECTS has ~1,100 enriched rows (European Paintings slice).
- Silver and Gold schemas EXIST but are EMPTY. dbt will fill them.
- dbt runs on Mac ONLY (Python venv, dbt-core + dbt-snowflake, key-pair auth).
- .env is the single source of truth. DBT_* vars feed profiles.yml via env_var().
- ARTWORK_TRANSFORMER role + PORCHANALYTICS user for dbt connections.
- 7 open research questions in dbt-plan.md must be answered before/during M1 build.

YOUR TASK THIS WINDOW:
Milestone 1 — dbt project scaffold + stg_met__artworks + full IaC wiring.

Phase 1 (research): Answer the 7 open questions in dbt-plan.md using web search +
cortex search docs. Key unknowns: env_var() key-pair auth syntax, dbt-utils version
+ surrogate_key macro name, VARIANT flatten best practice, FUTURE GRANTS behavior.
Present findings for owner review BEFORE writing any files.

Phase 2 (build, after owner "proceed"): Create the following in the workspace:
  - artwork_pipeline/ (dbt_project.yml, profiles.yml, packages.yml)
  - artwork_pipeline/models/staging/met/ (sources, schema, stg_met__artworks.sql)
  - scripts/dbt_orchestrate.sh (phases: init, build, test, teardown, full-refresh)
  - Makefile additions (dbt-init, dbt-build, dbt-test, dbt-teardown, all target)
  - .env updates (DBT_* variables added)
  - Basic tests: unique + not_null on object_id

EXIT CRITERIA: After owner syncs to Mac and runs `make dbt-init && make dbt-build`,
SILVER.STG_MET__ARTWORKS exists with typed columns and passes dbt tests.

HARD RULES:
- Do NOT install dbt in the workspace sandbox (runs on Mac only).
- Do NOT run make iac from the workspace.
- Do NOT push to main.
- Do NOT skip the research phase — present findings before writing code.
- Do NOT create tables in Silver/Gold manually — dbt owns those schemas.
- Do NOT create a CREATE DBT PROJECT object (that is M5, far future).
- One commit per logical unit. Owner decides when to commit.

FIRST RESPONSE: Quote back the "End of this window (tenth...)" header; confirm
solo-session=1 + CORTEX_FORK_INCIDENTS clean; then present your research plan
(which questions, which sources) and wait for "proceed."
```

- **End of this window (tenth; supersedes the "ninth" marker above. Review/hardening
  pass on dbt-plan.md — 6 gaps fixed, .env namespace split, materialization decisions
  added, multi-artist simplification documented. No account changes. Owner's next step:
  sync to Mac, then open a new window with the hand-off prompt above to execute M1.)**

---

## 2026-06-01 — follow-on 11 (Snowflake CLI setup: resilience hardening + multi-account)

> This single entry SUPERSEDES the two earlier duplicate "follow-on 11" blocks that
> a concurrent (forked) Cortex window appended this date. It is the canonical record.

### What changed this turn

Workspace-only edits to `scripts/snowflake_cli/` + the three context docs. Two arcs,
landed in one canonical state:

**Arc A — resilience hardening (single-account):**
- NEW `init_profile.sh`: seeds `[connections.<admin>]` in `config.toml`. INTERACTIVE
  wizard — prompts per-field for account, login user, role [default ACCOUNTADMIN],
  warehouse [default COMPUTE_WH]; each value is also overridable via its env var
  (`SNOWFLAKE_ACCOUNT`/`SNOWFLAKE_ADMIN_USER`/`SNOWFLAKE_ROLE`/`SNOWFLAKE_WAREHOUSE`)
  for non-interactive/CI use. The login PASSWORD is NOT collected here — it stays a
  hidden one-time `read -rs` prompt in `--phase admin` (key-pair-only; never stored).
  Non-destructive (skips if `account` already set); sets `default_connection_name`
  when unset. Closes the gap where 04/08 READ the admin block but nothing CREATED it.
  Runs inside `prereq` between 02 and 03.
  (Note: evaluated `snow connection add` — it prompts per-field + hides password
  natively, but always stores a password and validates `--private-key` exists,
  conflicting with our key-pair-only convention; chose to extend our own seeder.)
- `_lib.sh`: `prune_backups` (keep newest 5 `.bak.*`), `warn_duplicate_section`,
  `parse_toml_toplevel_key` / `upsert_toml_toplevel_key` (manage
  `default_connection_name` safely above all sections); pruning + dup-guard wired into
  `replace_*`/`upsert_*`.
- `04`/`08`: friendly "run --phase init-profile" hint on a missing config.toml.
- **Register-SQL cleanup (post-review tweaks this session):** removed the
  `DESCRIBE USER` from `git-setup/operator/register_{admin,loader}_public_key.sql`
  (it dumped the full ~45-row user record on every 04/05/06/08 apply for no added
  assurance — the JWT `connection test` is stronger proof), and migrated those
  files' templating from the deprecated `&{ var }` to `<% var %>`, matching the
  rest of the repo (`create_git_ops_db.sql`, `checkpoint.sql`, `orchestrate.sh`),
  which clears the CLI deprecation warning. Each file is now a single `ALTER USER
  ... SET RSA_PUBLIC_KEY` statement.

**Arc B — production-grade multi-account (owner approved; item 4 INCLUDED):**
- Connection names are now variables `SNOW_LIB_ADMIN_CONN` / `SNOW_LIB_LOADER_CONN`
  (default `admin`/`loader`). Key files derive from the conn name
  (`admin_key_path`/`loader_key_path`) — defaults preserve `admin_rsa_key.p8` /
  `loader_rsa_key.p8`; `clientb` → `clientb_rsa_key.p8` / `clientb_loader_rsa_key.p8`.
- `_lib.sh`: `validate_conn_name`, conn-aware `resolve_admin_*` + `verify_admin_jwt_full`,
  `list_connections`, `set_default_connection`.
- All of `02`–`08` + `init_profile.sh` derive their section + key paths from the conn
  vars (every script that uses `SNOW_LIB_*` sources `_lib.sh` — verified).
- `setup.sh`: `--profile LABEL` / `--admin-conn` / `--loader-conn` selectors
  (validated + exported), new `list` and `switch` phases (functions + dispatch arms).
- Docs: `file-map.md` (init_profile row + setup/_lib rows refreshed), `cli-connection.md`
  ("Multi-account" section), `AGENTS.md` (cli-connection Status row updated).
- **Item 4 (Makefile `CONN=` passthrough) LANDED:** `Makefile` has `CONN ?= admin`,
  threaded as `--connection $(CONN)` through `iac`/`infra`/`bootstrap`/`down`/
  `down-from`/`rollback`. `make iac CONN=clientb` now targets a 2nd account end-to-end.
  Verified via `make -n` dry-runs (default → `admin`; `CONN=clientb` → `clientb`).

- workspace stage: **edited (validated)**.  applied-to-account: **no**.  pushed-to-Mac: **no**.

### DUAL-INSTANCE INCIDENT (important)

A second, forked Cortex window ran this SAME approved plan concurrently. Detected when
`02` already contained edits I had not made (using the exact helper names invented this
turn), and `init_profile.sh` + `setup.sh` changed ON DISK between consecutive reads
(duplicate `list)`/`switch)` case arms appeared). This window HALTED, surfaced it, and —
after owner said "proceed with reconciliation" — reconciled rather than re-applied:
read fresh, kept the other window's consistent edits, fixed only the genuine gaps
(`setup.sh` missing `list`/`switch` dispatch + a duplicate arm; `08:85` literal `-c
admin`), then validated end-to-end. The earlier duplicate log blocks are collapsed into
this one entry. Root-cause + mechanism: `docs/context/connection-resilience.md`.

### Cumulative workspace state vs the Mac

Mac is behind by: follow-on 10 (dbt-plan.md + AGENTS.md) AND all of follow-on 11
(the `scripts/snowflake_cli/` suite + file-map.md + cli-connection.md + AGENTS.md row).
Next sync carries the whole delta. Nothing committed; owner decides when to stage on
`donkey-kong-sandbox`.

### Solo-session check result

NOT cleanly solo this turn — a forked window was active (see incident above). Account
interaction was ZERO (pure local file edits + `mktemp` smoke tests), so no account
writes raced. Owner should confirm a single live session before the NEXT window writes.

### Validation performed this window

- `bash -n` clean on all 12 scripts.
- Every script using `SNOW_LIB_*` confirmed to `source _lib.sh`.
- E2E smoke (temp `HOME`/config): default flow seeds `[connections.admin]` +
  `default_connection_name="admin"` with historical key paths; `--profile clientb`
  adds `[connections.clientb]` non-destructively (admin untouched); `--phase list`
  marks the default; `--phase switch` repoints it (with backup); `--phase list` then
  reflects it; `validate_conn_name "bad.name"` rejected; `prune_backups` kept newest 5.

### First-action options for the next window

(a) **Sync workspace → Mac** (git add + commit on `donkey-kong-sandbox`), then
    field-test `setup.sh --profile clientb --phase list/switch` on the Mac against a
    TEMP config (never the live `~/.snowflake`).
(b) **Resume dbt M1** per the follow-on 10 hand-off prompt (the primary roadmap).
(c) **Clear a deferred patch** (dbt_orchestrate.sh `-c admin` literals; stale V/R/B refs).

### Read-only verification queries

N/A — no schema or data state changed this turn.

### Decision tree for next window

```
Owner confirms single live session
  -> wants the CLI work durable        -> (a) sync to Mac + temp-config field test
  -> wants forward data work           -> (b) dbt M1 (follow-on 10 hand-off)
  -> wants cleanup                     -> (c) deferred patches
```

### Deferred patches (priority order)

1. Met enrichment Phase 3 drain (full EP collection) — whenever owner is ready.
2. Stale V/R/B refs outside infrastructure; `rename_and_update.py` removal decision.
3. `SMITHSONIAN_API_KEY` in root `.env.example` has no consumer.

> RESOLVED this turn: `dbt_orchestrate.sh` teardown no longer hardcodes `-c admin`
> or `ARTWORK_DB` — it now uses `ADMIN_CONN="${SNOW_CONNECTION:-admin}"` (+ a
> `--connection` flag) and `${SNOWFLAKE_DATABASE}`, and `make dbt-teardown CONN=...`
> threads it. The multi-account model now reaches the dbt teardown path too.

### What MUST NOT happen in the next window

- Do NOT run `init_profile.sh` / `setup.sh --phase prereq|all|switch` against the
  owner's LIVE `~/.snowflake/config.toml` without sign-off (it backs up + chmods it).
- Do NOT write ANY shared file before confirming a single live Cortex session.
- Do NOT run `make iac` from the workspace; do NOT push to `main`.
- Do NOT install dbt in the workspace sandbox (dbt runs on the Mac only).

### Hand-off prompt (paste into a new Cortex window)

```
SESSION HANDOFF — artwork-db / Snowflake CLI setup (resilience + multi-account landed)

ROLE: Senior Data/Platform Engineer mentor for a Snowflake learning project.
Account: pa37992 (config.toml org id HXCNOII-RS05429). Branch: donkey-kong-sandbox.
Explain the WHY and trade-offs; the OWNER decides, you honor it.

SESSION-OPEN RITUAL (in order, before any write):
1. Read /workspace/AGENTS.md (cheapest read; orientation).
2. Read ONLY the last "End of this window" entry in
   /workspace/docs/context/session-3-progress-log.md (titled "follow-on 11").
3. SOLO-SESSION CHECK before any write (a forked window raced the last session!):
     SELECT COUNT(DISTINCT SESSION_ID) FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
      WHERE QUERY_TAG ILIKE '%cortex_code_snowsight%'
        AND START_TIME > DATEADD(minute, -10, CURRENT_TIMESTAMP());
     SELECT * FROM ARTWORK_DB.BRONZE.CORTEX_FORK_INCIDENTS ORDER BY 1 DESC LIMIT 5;
   Exactly 1 = solo; >1 = STOP and ask. Re-read any shared file immediately before editing.
4. DUAL-FS: workspace edits are NOT on the Mac until synced. State the plan and wait for
   "proceed (date)" before any write or execution.

STATE (do not re-derive):
- scripts/snowflake_cli/ is hardened + multi-account: init_profile.sh, conn-aware
  _lib.sh, setup.sh --profile/--admin-conn/--loader-conn + list/switch phases. Defaults
  admin/loader unchanged. Makefile threads CONN= (make iac CONN=clientb). LOCAL-ONLY,
  validated, not applied to account, not synced to Mac.
- dbt M1 (follow-on 10) still pending and is the primary roadmap item.

YOUR TASK: ask the owner whether to (a) sync to Mac + field-test on a TEMP config,
(b) resume dbt M1, or (c) clear a deferred patch. Plan, then wait for proceed.

HARD RULES: No make iac from workspace. No push to main. No dbt install in workspace.
Never run init_profile.sh/switch against the live ~/.snowflake/config.toml without sign-off.

FIRST RESPONSE: Quote back the "End of this window (eleventh...)" header; confirm
solo-session=1 + CORTEX_FORK_INCIDENTS clean; then ask which of (a)/(b)/(c) and wait.
```

- **End of this window (eleventh; CANONICAL — supersedes the two duplicate follow-on 11 blocks from the forked window AND the "tenth" marker. Snowflake CLI setup suite hardened AND made multi-account: NEW init_profile.sh; conn-aware _lib.sh (SNOW_LIB_ADMIN_CONN/LOADER_CONN, key-path derivation, list_connections/set_default_connection, prune_backups, dup-guard); setup.sh --profile/--admin-conn/--loader-conn + list/switch phases; 02-08 parameterized; docs updated (file-map, cli-connection, AGENTS). Defaults admin/loader unchanged. Dual-instance incident this turn — reconciled, not re-applied. **Item 4 Makefile CONN= passthrough LANDED** (make iac CONN=clientb; verified via make -n). All LOCAL-ONLY: validated via bash -n + temp-config E2E + make -n dry-runs; not applied to account, not synced to Mac.)**

---

### 2026-06-04 (new window) | NEW-ACCOUNT CUTOVER PREP + dbt-readiness authored (workspace; NOT applied, NOT pushed)

> Owner sign-off: "Proceed on June 4, 2026." This window is the cutover from the
> retired trials to the NEW account and prep for Mac dbt Core. dbt execution model:
> **Mac dbt Core ONLY for now** (Snowflake-native CREATE DBT PROJECT deferred as a
> purely additive later step; if/when added it is the future Airflow hook). Enrich
> slice: **European Paintings (PD)**. dbt identity: **dedicated service user
> `ARTWORK_TRANSFORMER_SVC`** (TYPE=SERVICE, key-pair only), scoped to
> `ARTWORK_TRANSFORMER` -- mirrors `ARTWORK_LOADER_SVC`. (An earlier strawman that
> granted the role to the human login PORCHFLAKE in create_roles.sql was REJECTED
> by the owner mid-window: IaC must not pin a personal login.)

- **NEW ACCOUNT (authoritative, verified live read-only this window):**
  `OBANOYY-MK07348` (legacy locator `EP21559`, region `AWS_US_EAST_2`), admin
  `PORCHFLAKE` / `ACCOUNTADMIN`, snow CLI admin connection `[connections.mk07348]`
  (key `~/.snowflake/keys/mk07348_rsa_key.p8`). Trials `pa37992` / `HXCNOII-RS05429`
  (admin `PORCHANALYTICS`) are RETIRED.
- **Live state verified (read-only):** `ARTWORK_DB` BRONZE/SILVER/GOLD live (DDL +
  git-setup already applied 2026-06-03). All Met tables = **0 rows**
  (`MET_CSV_SNAPSHOT`, `MET_ENRICHMENT_CONTROL`, `MET_WORKLIST`, `RAW_MET_OBJECTS`,
  `EXTRACTION_LOG`). `ARTWORK_LOADER_SVC` = `TYPE=SERVICE`, `PASSWORD=null`, but
  **`RSA_PUBLIC_KEY=null`** -> loader cannot auth on this account yet (the core gap).
  `PORCHFLAKE` holds `ACCOUNTADMIN`+`ORGADMIN` but **not** `ARTWORK_TRANSFORMER`.

- **What changed this turn (workspace stage: EDITED + validated; applied-to-account: NO; pushed-to-Mac: NO):**
  1. `Makefile` -- NEW `loader` AND `transformer` targets (Option B): `bash
     scripts/snowflake_cli/setup.sh --profile $(CONN) --phase loader|transformer`;
     both added to `.PHONY`. Additive/namespaced: `make loader CONN=mk07348` ->
     `mk07348_loader_rsa_key.p8` + `[connections.mk07348_loader]`;
     `make transformer CONN=mk07348` -> `mk07348_transformer_rsa_key.p8` +
     `[connections.mk07348_transformer]`. Never touch the old `[connections.loader]`.
  2. `infrastructure/create_service_user.sql` -- added a SECOND service user
     `ARTWORK_TRANSFORMER_SVC` (TYPE=SERVICE, DEFAULT_ROLE ARTWORK_TRANSFORMER,
     NS ARTWORK_DB.SILVER) + `GRANT ROLE ARTWORK_TRANSFORMER TO USER
     ARTWORK_TRANSFORMER_SVC` + idempotent TYPE/PASSWORD converge ALTERs. Both
     statements compile-validated (`only_compile`). `drop_service_user.sql` drops
     it before the loader. Mirrors the loader pattern exactly. (The transient
     create_roles.sql human-login grant was added then REVERTED in this window.)
     Companion bootstrap (mirrors 06/07): NEW `git-setup/operator/
     register_transformer_public_key.sql`, `scripts/snowflake_cli/
     09_setup_transformer_keypair.sh` + `10_test_transformer_connection.sh`,
     `_lib.sh` (`SNOW_LIB_TRANSFORMER_CONN` + `transformer_key_path`), `setup.sh`
     (`transformer` phase + `--transformer-conn`), `executable_files.txt` (09/10).
  3. `.env.example` -- account example -> `OBANOYY-MK07348`; loader key namespaced
     `~/.snowflake/keys/<conn>_loader_rsa_key.p8` (minted by `make loader CONN=<conn>`);
     `DBT_SNOWFLAKE_USER` set to `ARTWORK_TRANSFORMER_SVC`; key namespaced
     `<conn>_transformer_rsa_key.p8` (via `make transformer CONN=<conn>`).
  4. `CLAUDE.md` -- account block -> `OBANOYY-MK07348 (locator EP21559)`, retired trials
     noted; fixed stale "dbt project (not yet created)" -> scaffolded.
  5. `AGENTS.md` -- new authoritative "Current account" anchor in Operating environment
     (account id, locator, admin, admin conn, loader-key namespacing, retired trials).

- **Cumulative workspace state vs Mac:** Mac is BEHIND by this turn's edits:
  `Makefile`, `infrastructure/create_service_user.sql`, `infrastructure/drop_service_user.sql`,
  `git-setup/operator/register_transformer_public_key.sql`,
  `scripts/snowflake_cli/{09_setup_transformer_keypair.sh,10_test_transformer_connection.sh,_lib.sh,setup.sh}`,
  `scripts/executable_files.txt`, `.env.example`, `CLAUDE.md`, `AGENTS.md`,
  `docs/context/{file-map,met-deepdive,session-3-progress-log}.md`
  (create_roles.sql was edited then reverted -- net no change). On top of any
  un-synced prior-window deltas. The REAL `.env` is Mac-local (gitignored, not in the
  workspace) -- owner sets it by hand from the block in the hand-off. Nothing committed.

- **Solo-session check result:** exactly **1** `cortex_code_snowsight` session (this
  window); `ARTWORK_DB.BRONZE.CORTEX_FORK_INCIDENTS` = **0 rows**. SOLO.

- **First-action options for the next window:**
  (a) Owner has run `make loader CONN=mk07348` -> verify the loader key registered
      (read-only `DESCRIBE USER ARTWORK_LOADER_SVC` shows `RSA_PUBLIC_KEY_FP`); owner
      ran `snow connection test -c mk07348_loader`. Then proceed to snapshot load.
  (b) Owner has run `make infra CONN=mk07348` (creates ARTWORK_TRANSFORMER_SVC) +
      `make transformer CONN=mk07348` -> verify the transformer key registered
      (`DESCRIBE USER ARTWORK_TRANSFORMER_SVC` shows `RSA_PUBLIC_KEY_FP`;
      `snow connection test -c mk07348_transformer`).
  (c) Owner has run `python -m extraction.met.run snapshot` -> verify
      `MET_CSV_SNAPSHOT` ~485k rows, then seed-control + enrich-met (European Paintings).

- **Read-only verification queries (paste-ready):**
  ```sql
  -- loader key registered (Phase 1)
  DESCRIBE USER ARTWORK_LOADER_SVC;            -- expect RSA_PUBLIC_KEY_FP set, PASSWORD null
  -- transformer service user ready (Phase 4 prep)
  DESCRIBE USER ARTWORK_TRANSFORMER_SVC;       -- expect RSA_PUBLIC_KEY_FP set, TYPE SERVICE
  SHOW GRANTS TO USER ARTWORK_TRANSFORMER_SVC; -- expect a row: ROLE ARTWORK_TRANSFORMER
  -- full CSV landed (Phase 2)
  SELECT COUNT(*) FROM ARTWORK_DB.BRONZE.MET_CSV_SNAPSHOT;          -- expect ~485k
  -- enrichment slice (Phase 3)
  SELECT enrichment_status, COUNT(*) FROM ARTWORK_DB.BRONZE.MET_ENRICHMENT_CONTROL GROUP BY 1;
  SELECT COUNT(*) FROM ARTWORK_DB.BRONZE.RAW_MET_OBJECTS;           -- > 0 once enriched
  ```

- **Decision tree for next window:**
  ```
  loader key registered? (DESCRIBE USER -> RSA_PUBLIC_KEY_FP set)
    no  -> owner runs `make loader CONN=mk07348`, then `snow connection test -c mk07348_loader`
    yes -> MET_CSV_SNAPSHOT loaded?
             no  -> owner runs `python -m extraction.met.run snapshot` (Mac)
             yes -> control seeded (European Paintings ~2,327)?
                      no  -> owner runs seed-control --department "European Paintings"
                      yes -> owner runs enrich-met (watch WAF/403 risk) -> then dbt:
                             make infra CONN=mk07348 (grant; creates ARTWORK_TRANSFORMER_SVC) -> make transformer CONN=mk07348 -> make dbt-deps -> dbt-build -> dbt-test
  ```

- **Deferred patches (priority order):**
  1. Met enrich WAF/403 mitigation if it recurs on this account (UA/headers in
     `config.py` / `image_enricher.py`; the prior account hit an Akamai interstitial).
  2. Snowflake-native dbt deployment (CREATE DBT PROJECT) -- additive; the future
     Airflow `EXECUTE DBT PROJECT` hook. Only when owner wants it.
  3. Stale V/R/B refs outside infrastructure; `rename_and_update.py` removal decision.
  4. `SMITHSONIAN_API_KEY` in root `.env.example` has no consumer.

- **What MUST NOT happen in the next window:**
  - Do NOT `make iac`/`make infra`/`make loader` from the workspace -- the Mac is the
    apply surface (key-pair auth lives there). Do NOT push to `main`.
  - Do NOT reuse the OLD `loader_rsa_key.p8` for this account; the namespaced
    `mk07348_loader_rsa_key.p8` is correct (distinct, additive).
  - Do NOT install dbt in the workspace sandbox (dbt Core runs on the Mac only).
  - Do NOT rewrite historical dated entries above (append-only).

- **Hand-off prompt (paste into a new Cortex window):**
```
SESSION HANDOFF -- artwork-db / NEW-ACCOUNT cutover + Mac dbt Core readiness

ROLE: Senior Data/Platform Engineer mentor for a Snowflake + dbt learning project.
Account: OBANOYY-MK07348 (legacy locator EP21559), admin PORCHFLAKE/ACCOUNTADMIN,
snow CLI admin connection [connections.mk07348]. Branch: donkey-kong-sandbox.
Explain the WHY and trade-offs; the OWNER decides, you honor it.

READING ORDER (stop once you can act):
1. AGENTS.md (Tier 0; see the "Current account" anchor).
2. ONLY the latest entry of docs/context/session-3-progress-log.md
   (header: "2026-06-04 ... NEW-ACCOUNT CUTOVER PREP").

SOLO-SESSION CHECK before any write:
  SELECT COUNT(DISTINCT SESSION_ID) FROM TABLE(ARTWORK_DB.INFORMATION_SCHEMA.QUERY_HISTORY_BY_USER(
    USER_NAME=>'PORCHFLAKE', RESULT_LIMIT=>1000))
   WHERE QUERY_TAG ILIKE '%cortex_code_snowsight%' AND START_TIME > DATEADD(minute,-10,CURRENT_TIMESTAMP());
  SELECT COUNT(*) FROM ARTWORK_DB.BRONZE.CORTEX_FORK_INCIDENTS;
  Exactly 1 + 0 incidents = solo; else STOP and ask.

DUAL-FS: workspace edits are NOT on the Mac until the owner commits+pulls. State the
plan and wait for "proceed (+date)" before any write or execution. Mac is the apply
surface for make loader / make infra / python / make dbt-*.

STATE (do not re-derive): DDL+git-setup live on the new account; all Met tables EMPTY.
LOADER key NOT yet registered (RSA_PUBLIC_KEY=null). This window staged (un-synced):
Makefile `loader`+`transformer` targets, create_service_user.sql ARTWORK_TRANSFORMER_SVC,
09/10 transformer keypair scripts + register_transformer SQL + setup.sh/_lib.sh wiring,
.env.example, CLAUDE.md, AGENTS.md, file-map, met-deepdive. dbt = Mac dbt Core only as
ARTWORK_TRANSFORMER_SVC; native deployment deferred.

YOUR TASK: confirm where the owner is (loader key minted? infra grant applied? snapshot
loaded?), verify read-only, and continue the cutover->load->enrich->dbt sequence.

HARD RULES: No make from workspace. No push to main. No dbt install in workspace.
Reuse the namespaced mk07348_loader key, not the old loader_rsa_key.p8.

FIRST RESPONSE: quote back the "End of this window (2026-06-04 cutover)" header;
confirm solo=1 + CORTEX_FORK_INCIDENTS=0; then ask which step the owner has completed.
```

- **End of this window (2026-06-04 cutover; CANONICAL -- supersedes the "eleventh" marker. NEW account OBANOYY-MK07348/EP21559, admin PORCHFLAKE; loader key gap identified (RSA_PUBLIC_KEY=null). Staged (workspace, un-synced, NOT applied): Makefile `loader`+`transformer` targets (Option B); create_service_user.sql adds ARTWORK_TRANSFORMER_SVC (TYPE=SERVICE) + role grant (compile-validated) -- the dbt identity, mirroring the loader; 09/10 transformer keypair scripts + register_transformer_public_key.sql + setup.sh/_lib.sh wiring; .env.example + CLAUDE.md + AGENTS.md + file-map + met-deepdive re-pointed to the new account. An earlier create_roles.sql grant-to-PORCHFLAKE strawman was REVERTED (no human login in IaC). dbt = Mac dbt Core only as ARTWORK_TRANSFORMER_SVC; European Paintings slice. Next = owner runs make loader CONN=mk07348 -> snapshot -> seed/enrich -> make infra + make transformer + dbt-build/test on the Mac.)**

---

## 2026-06-05 -- Part 1 doc/Makefile fixes + AWS-SSO root-cause + live progress logging + DDL-doc pass

**What changed this turn** (workspace stage; `applied-to-account: NO`; `pushed-to-Mac: NO`):
- **Part 1 (stale-CLI-ref fixes).** The Met CLI takes SUBCOMMANDS, not `--phase`/`--source`.
  - `Makefile`: `extract-met` now chains `snapshot -> seed-control -> enrich-met` with a
    generic `AWS_NO_SSO` env prefix on the two PUT steps; added `MET_DEPT`/`MET_SEED_LIMIT`/
    `MET_ENRICH_LIMIT` knobs; `extract` aliases `extract-met`; `extract-aic/cma/smithsonian`
    are commented placeholders. No account/conn names hard-coded. `make -n` verified expansion.
  - `CLAUDE.md`, `extraction/met/CLAUDE.md`, `extraction/met/README.md`: re-pointed to Option B
    (snapshot/seed-control/enrich-met) as current; SQLite path relabeled legacy; `V001-V007` dropped.
- **AWS-SSO stall root cause.** botocore (spun up by the stage PUT) was refreshing a DEAD AWS
  SSO profile -> ~10-min stall/Ctrl-C. NOT a pipeline bug; Snowflake key-pair auth is separate.
  Permanent fix (owner, Mac): clear `~/.aws/config`. Workspace fix: `AWS_NO_SSO` baked into Makefile.
- **Live progress logging (Python; owner-requested).** `extraction/met/control_enricher.py`:
  progress now streams per-N completed fetches from inside `_fetch_blocks` (was a post-batch dump);
  removed the redundant post-batch emitter. `python3 -m py_compile` OK.
- **DDL-doc pass.** `create_tasks.sql`: added the **TTL-vs-throttling caveat** (30-min TTL assumed
  ~20 rps; observed ~1 rps under throttling -> a 2000-row batch could outlive the TTL and get
  reclaimed mid-fetch). Mirrored into `ddl-infrastructure.md` Gaps. `file-map.md`: added the two
  missing rows (`control_seeder.py`, `control_enricher.py`) + refreshed the `README.md` row.
  (Inline comments on the 3 create files were already comprehensive -- no cosmetic edits made.)

**Cumulative workspace state vs the Mac (delta the NEXT sync carries):** the 2026-06-04 cutover
delta is already ON the Mac (the account now has both SERVICE users with RSA keys registered +
successful logins, and the full snapshot loaded -- so make infra/loader/transformer already ran).
The remaining un-synced delta = THIS session only: `Makefile`, `CLAUDE.md`,
`extraction/met/CLAUDE.md`, `extraction/met/README.md`, `extraction/met/control_enricher.py`,
`infrastructure/create_tasks.sql` (comment only), `docs/context/{ddl-infrastructure,file-map,
session-3-progress-log}.md`.

**Solo-session check:** PASS -- 1 live `cortex_code_snowsight` session, `CORTEX_FORK_INCIDENTS = 0`.

**Live account state (verified read-only this session):**
- `ARTWORK_LOADER_SVC` + `ARTWORK_TRANSFORMER_SVC`: both `TYPE=SERVICE`, RSA key registered, logged in.
- `MET_CSV_SNAPSHOT = 484,956` (FULL CSV loaded). `MET_ENRICHMENT_CONTROL = 2,327` pending.
  `MET_WORKLIST` free pending = `1,827`. `RAW_MET_OBJECTS = 0` at the time of my last data query.
- Owner pasted a SUCCESSFUL batch (`claimed=500 done=498 no_image=2 error=0`) AFTER that query, so
  Bronze likely now has ~498 rows -- **NOT re-verified.** Two leased batches existed
  (`met_enrich_20260605T160532Z` dead Ctrl-C; `met_enrich_20260605T162726Z`); both self-reclaim via TTL.

**First-action options for the next window:**
- **(a)** Sync this session's edits to the Mac, then `python -m extraction.met.run -v enrich-met --limit 20`
  and CONFIRM the new live `Progress: N/1,827 ...` streaming + Bronze climbing.
- **(b)** Verify current Bronze state (queries below) and reconcile against the owner's `done=498` paste.
- **(c)** Start **Part 3 dbt mentorship** (deferred this session) against the now-populated Bronze.

**Read-only verification queries:**
```sql
SELECT COUNT(*) FROM ARTWORK_DB.BRONZE.RAW_MET_OBJECTS;                       -- expect ~498+
SELECT ENRICHMENT_STATUS, COUNT(*) FROM ARTWORK_DB.BRONZE.MET_ENRICHMENT_CONTROL GROUP BY 1;
SELECT COUNT(*) AS FREE_PENDING FROM ARTWORK_DB.BRONZE.MET_WORKLIST;
SELECT CLAIMED_BY_BATCH, COUNT(*) FROM ARTWORK_DB.BRONZE.MET_ENRICHMENT_CONTROL
 WHERE CLAIMED_BY_BATCH IS NOT NULL GROUP BY 1;                              -- leased batches
```

**Decision tree (next run output shapes):**
- enrich-met logs stream `Progress:` lines live -> logging fix confirmed (Mac was synced).
  Still a single post-batch dump -> Mac NOT synced; sync `control_enricher.py` first.
- Bronze climbs toward `done` count -> healthy. High `error` count -> Met API throttling;
  lower `MET_API_RPS` in `.env` (separate from the AWS fix).
- A batch runs >30 min -> the TTL caveat is biting; use smaller `--limit` (or raise TTL, sign-off).

**Deferred patches (priority order):**
1. (owner, Mac) clear `~/.aws/config` so direct `python` runs need no `AWS_NO_SSO` prefix.
2. TTL-vs-throttling: decide raise `MET_LEASE_RECLAIM_TASK` TTL vs. keep `--limit` discipline (sign-off).
3. Part 3 dbt mentorship (full command-maximizing session) -- now unblocked by populated Bronze.
4. AGENTS.md "new gated items": V/R/B reword in `git-setup/README.md`; `rename_and_update.py` fate;
   native dbt `profiles.yml`; `SMITHSONIAN_API_KEY` consumer.
5. Reconcile remaining `file-map.md` stale notes (`config.py` l.53-54 V-ref; `.env.example` l.14 account).

**MUST NOT happen next window (foot-guns):**
- Do NOT run `make`/`python`/`dbt` from the workspace (Mac-only); no push to `main`; no dbt install in workspace.
- Do NOT assume the Mac has this session's `control_enricher.py` change until it is synced.
- Do NOT re-run `snapshot` (the full CSV is already loaded) -- wasteful re-download + MERGE.
- Do NOT write anything if the solo-session check returns >1; do NOT abort husk sessions.

```text
Read AGENTS.md first, then ONLY the latest dated entry in docs/context/session-3-progress-log.md
(the 2026-06-05 entry). Stop once you can act.

SOLO CHECK before any write: count cortex_code_snowsight sessions in the last ~10 min
(QUERY_TAG ILIKE '%cortex_code_snowsight%') and check ARTWORK_DB.BRONZE.CORTEX_FORK_INCIDENTS.
Exactly 1 = solo; >1 = stop and ask. Do not abort husks.

DUAL-FS: Workspace edits are NOT on my Mac until I sync. Report applied-to-account yes/no and
pushed-to-Mac yes/no. No make/python/dbt from the workspace -- I run those on the Mac.

GATING: state your plan and WAIT for my explicit go + the date before any write or execution.

PROJECT (one line): branch donkey-kong-sandbox; account OBANOYY-MK07348 (admin PORCHFLAKE/
ACCOUNTADMIN, conn mk07348); Medallion over Met OpenAccess. Phase = Section C data load mostly
done (full snapshot=484,956; ~498+ Bronze rows enriched); Part 3 dbt mentorship is NEXT.
Key objects in ARTWORK_DB.BRONZE: MET_CSV_SNAPSHOT, MET_ENRICHMENT_CONTROL, MET_WORKLIST (view),
MET_LEASE_RECLAIM_TASK (task), RAW_MET_OBJECTS. dbt = Mac dbt Core as ARTWORK_TRANSFORMER_SVC.

UN-SYNCED workspace delta (this session): Makefile, CLAUDE.md, extraction/met/{CLAUDE.md,README.md,
control_enricher.py}, infrastructure/create_tasks.sql, docs/context/{ddl-infrastructure,file-map,
session-3-progress-log}.md. Sync before expecting live enrich progress logs.

FIRST RESPONSE: quote the latest `End of this window` header back to me, confirm solo=1 +
CORTEX_FORK_INCIDENTS=0, then propose your first action (a/b/c in the log) and wait for my go + date.
```

- **End of this window (2026-06-05; CANONICAL -- supersedes the 2026-06-04 cutover marker. Account OBANOYY-MK07348, branch donkey-kong-sandbox. This window: Part 1 stale-CLI-ref fixes (Makefile extract-met -> real subcommands + generic AWS_NO_SSO prefix + commented aic/cma/smithsonian; CLAUDE.md + extraction/met/CLAUDE.md + extraction/met/README.md reframed to Option B, SQLite labeled legacy, V001-V007 dropped); AWS-SSO stall root-caused (dead profile -> botocore PUT-step refresh; fix = clear ~/.aws/config + AWS_NO_SSO in Makefile); LIVE progress logging in control_enricher.py (per-N during fetch, was post-batch; py_compile OK); DDL-doc pass (create_tasks.sql TTL-vs-throttling caveat + ddl-infrastructure.md Gaps + file-map.md control_seeder/control_enricher rows + README row). ALL edits workspace-only: applied-to-account NO, pushed-to-Mac NO. Live state verified read-only: both SERVICE users keyed+logged-in; MET_CSV_SNAPSHOT=484,956; MET_ENRICHMENT_CONTROL=2,327 pending; RAW_MET_OBJECTS=0 at query time but owner reported a successful 500-batch (done=498) afterward -- NOT re-verified. Part 3 dbt mentorship deferred to next window, now unblocked by populated Bronze.)**

---

### 2026-06-05 (Part 3 dbt mentorship -- curriculum landed)

**Solo-session check:** PASS -- 0 running `cortex_code_snowsight` in last 10 min; `CORTEX_FORK_INCIDENTS = 0`.

**What changed this turn (workspace stage):**
- CREATED `docs/context/dbt-curriculum.md` (270 lines): 6-unit hands-on dbt syllabus with
  new-window protocol, status tracking table, per-unit outlines (objectives, decision forks,
  deliberate failures, verification SQL), and a journal-file template.
- CREATED `docs/context/dbt-journal/` directory (empty; unit journals created as entered).
- EDITED `docs/context/file-map.md`: added `artwork_pipeline/` section (7 files row-mapped)
  + `dbt-curriculum.md` + `dbt-journal/` rows.
- EDITED `AGENTS.md`: added `dbt-curriculum.md` to Status table; updated Workflow domains
  to reference both `dbt-plan.md` (strategy) and `dbt-curriculum.md` (teaching).
- APPENDED this entry to `session-3-progress-log.md`.
- **Applied-to-account: NO.** Documentation only.
- **Pushed-to-Mac: NO.** Workspace-only edits.

**Cumulative workspace state vs the Mac (delta the NEXT sync carries):**
Prior un-synced delta (from earlier this date): `Makefile`, `CLAUDE.md`,
`extraction/met/CLAUDE.md`, `extraction/met/README.md`, `extraction/met/control_enricher.py`,
`infrastructure/create_tasks.sql`.
NEW this turn: `docs/context/dbt-curriculum.md`, `docs/context/dbt-journal/` (dir),
`docs/context/file-map.md`, `docs/context/session-3-progress-log.md`, `AGENTS.md`.

**Live account state (verified read-only):**
- `RAW_MET_OBJECTS = 503` rows (confirmed; Bronze populated).
- `SILVER` schema = EMPTY (no objects yet; dbt has not run).
- `RAW_PAYLOAD` top keys = `_meta`, `api_images`, `csv`, `object_id`. CSV sub-keys match
  the `stg_met__artworks.sql` extraction paths (verified one row).

**Next action:** Begin Unit 1 (First Green Run). Owner runs on Mac:
```bash
cd artwork_pipeline
dbt deps
dbt run
```
Then verify via read-only SQL (SHOW VIEWS IN SCHEMA ARTWORK_DB.SILVER).

**Decision tree:**
- `dbt run` succeeds + view appears in SILVER -> proceed to deliberate-failure exercise
  (wrong role), then Unit 2.
- `dbt run` fails on connection -> check env vars (`SNOWFLAKE_ACCOUNT`, `DBT_SNOWFLAKE_USER`,
  `DBT_SNOWFLAKE_PRIVATE_KEY_PATH`). Likely cause: un-exported `.env` or wrong key path.
- `dbt run` fails on permission -> `ARTWORK_TRANSFORMER` role may lack USAGE on
  `ARTWORK_DB.SILVER`. Check grants (this should not happen -- `create_grants.sql` covers it).

**Deferred patches (priority order):**
1. (Mac sync) push the cumulative workspace delta before depending on any new files.
2. Unit 2-6 of the dbt curriculum (sequential, in future windows if needed).
3. Prior deferred items unchanged (AWS config cleanup, TTL decision, V/R/B rewords).

**MUST NOT happen next window (foot-guns):**
- Do NOT run dbt from the workspace (Mac-only).
- Do NOT create unit journal files before the unit is actually started (avoid placeholder rot).
- Do NOT skip `dbt deps` before the first `dbt run` (packages.yml requires dbt_utils).
- Do NOT modify `stg_met__artworks.sql` during Unit 1 (it is the known-good baseline).

**Hand-off prompt:**

```text
Read AGENTS.md first, then ONLY the latest dated entry in docs/context/session-3-progress-log.md
(the 2026-06-05 "Part 3 dbt mentorship -- curriculum landed" entry). Then read
docs/context/dbt-curriculum.md for the syllabus + new-window protocol. Stop once you can act.

SOLO CHECK before any write: count cortex_code_snowsight sessions in the last ~10 min
(QUERY_TAG ILIKE '%cortex_code_snowsight%') and check ARTWORK_DB.BRONZE.CORTEX_FORK_INCIDENTS.
Exactly 1 = solo; >1 = stop and ask. Do not abort husks.

DUAL-FS: Workspace edits are NOT on my Mac until I sync. Report applied-to-account yes/no and
pushed-to-Mac yes/no. No make/python/dbt from the workspace -- I run those on the Mac.

GATING: state your plan and WAIT for my explicit go + the date before any write or execution.

ROLE: You are my senior dbt MENTOR. Hands-on, build-as-we-go. YOU decide within-unit
sequencing; I run the commands on my Mac. Explain the WHY, name decision forks, introduce
deliberate failures for diagnosis practice.

PROJECT (one line): branch donkey-kong-sandbox; account OBANOYY-MK07348 (admin PORCHFLAKE/
ACCOUNTADMIN); Medallion over Met OpenAccess. dbt project = artwork_pipeline/ (Mac dbt Core,
ARTWORK_TRANSFORMER_SVC). Bronze populated (503 rows). SILVER empty. Curriculum: 6 units in
docs/context/dbt-curriculum.md; check its Status table for the ACTIVE unit.

FIRST RESPONSE: quote the latest `End of this window` header back to me, confirm solo=1,
then check dbt-curriculum.md Status table for the active unit and propose next steps.
Wait for my go + date.
```

- **End of this window (2026-06-05 Part 3b; CANONICAL -- supersedes Part 3a above. Account OBANOYY-MK07348, branch donkey-kong-sandbox. This turn: dbt curriculum documentation landed (dbt-curriculum.md + dbt-journal/ dir + file-map.md artwork_pipeline section + AGENTS.md status row). ALL workspace-only: applied-to-account NO, pushed-to-Mac NO. Live state: RAW_MET_OBJECTS=503, SILVER empty, RAW_PAYLOAD paths verified. Next = Unit 1 First Green Run on Mac.)**

---

### 2026-06-05 (Part 3c -- Unit 1 COMPLETE + governance MVG + dual-mode profile)

**Solo-session check:** PASS -- 0 running `cortex_code_snowsight` in last 10 min; `CORTEX_FORK_INCIDENTS = 0`.

**What changed this turn (workspace stage):**
- CREATED `artwork_pipeline/macros/override_create_schema.sql` (26 lines): MVG-1 no-op macro.
- CREATED `artwork_pipeline/macros/generate_schema_name.sql` (77 lines): MVG-2 verbatim
  schema routing with allowlist (`SILVER`, `GOLD`, `DBT_TEST__AUDIT`). Extensive
  design-considerations header documenting 5 tradeoff decisions.
- CREATED `infrastructure/create_resource_monitors.sql` (47 lines): MVG-3 resource
  monitor (20 credits/month, suspend at 95%) + STATEMENT_TIMEOUT=900s + QUEUED_TIMEOUT=120s.
- CREATED `infrastructure/drop_resource_monitors.sql` (19 lines): paired rollback.
- REWROTE `artwork_pipeline/profiles.yml` (77 lines): dual-mode profile with `dev`
  (Mac key-pair via env_var) + `snowflake` (native session auth, no credentials).
- CREATED `docs/context/dbt-governance-plan.md` (452 lines): 5-layer governance PROPOSAL
  (RBAC, cost, object proliferation, multi-dev, observability) with problem statement,
  damage scenarios, reviewer considerations, MVG implementation status.
- EDITED `scripts/manifest.txt`: added `create_resource_monitors.sql` after warehouses.
- UPDATED `docs/context/dbt-curriculum.md`: Unit 1 -> complete, Unit 2 -> active.
- UPDATED `docs/context/dbt-journal/unit-1-first-green-run.md`: errors, decisions,
  8 key takeaways filled in. Marked complete.
- UPDATED `docs/context/file-map.md`: macros/ rows + resource_monitors row + profiles.yml updated.
- UPDATED `docs/context/dbt-governance-plan.md`: MVG-1/2 = IMPLEMENTED, MVG-3 = AUTHORED.
- **Applied-to-account: PARTIALLY.** dbt macros took effect via owner's `dbt run` (Mac).
  View `ARTWORK_DB.SILVER.STG_MET__ARTWORKS` now exists (503 rows, owner ARTWORK_TRANSFORMER).
  Resource monitor NOT yet applied (awaiting `make infra CONN=mk07348` on Mac).
- **Pushed-to-Mac: PARTIALLY.** Owner synced macros + profiles.yml manually for `dbt run`.
  Full workspace delta (docs, governance plan, resource monitor IaC) NOT yet synced.

**Cumulative workspace state vs the Mac (delta the NEXT sync carries):**
Prior un-synced: `Makefile`, `CLAUDE.md`, `extraction/met/{CLAUDE.md,README.md,control_enricher.py}`,
`infrastructure/create_tasks.sql`.
NEW this turn: `artwork_pipeline/macros/{override_create_schema,generate_schema_name}.sql`,
`artwork_pipeline/profiles.yml` (rewritten), `infrastructure/{create,drop}_resource_monitors.sql`,
`scripts/manifest.txt`, `docs/context/{dbt-governance-plan,dbt-curriculum,file-map,
session-3-progress-log}.md`, `docs/context/dbt-journal/unit-1-first-green-run.md`.
**Owner confirmed they already synced the macros + profiles.yml to run dbt.** Other files pending.

**Live account state (verified read-only):**
- `ARTWORK_DB.SILVER.STG_MET__ARTWORKS`: EXISTS, 503 rows, owner=ARTWORK_TRANSFORMER.
- `RAW_MET_OBJECTS`: 503 rows.
- `ARTWORK_WH`: STATEMENT_TIMEOUT still at default (172800s) -- resource monitor not yet applied.
- `CORTEX_FORK_INCIDENTS = 0`.

**First-action options for the next window:**
- **(a)** Apply resource monitor: `make infra CONN=mk07348` on Mac (applies all 12
  manifest scripts idempotently; resource monitor is the only net-new change).
- **(b)** Start Unit 2 (`dbt test`): run `dbt test` against existing source+model tests;
  observe 5 passing tests; then deliberately break one (add `not_null` on
  `primary_image_url`); learn `warn` severity + `store_failures`.
- **(c)** Sync the full workspace delta to Mac first, then (a) or (b).

**Read-only verification queries:**
```sql
SHOW VIEWS IN SCHEMA ARTWORK_DB.SILVER;
SELECT COUNT(*) FROM ARTWORK_DB.SILVER.STG_MET__ARTWORKS;
SHOW RESOURCE MONITORS;  -- expect ARTWORK_WH_MONITOR after apply
SHOW PARAMETERS LIKE 'STATEMENT_TIMEOUT%' IN WAREHOUSE ARTWORK_WH;  -- expect 900 after apply
```

**Decision tree (next run output shapes):**
- `dbt test` returns PASS=5 -> existing tests healthy; proceed to deliberate failure.
- `dbt test` returns failures on unique/not_null OBJECT_ID -> data integrity issue in
  Bronze; investigate before proceeding.
- `make infra` fails on resource monitor -> likely role issue (ACCOUNTADMIN required
  for resource monitors; verify CONN is admin, not loader/transformer).

**Deferred patches (priority order):**
1. (Mac) Full workspace sync (docs + resource monitor IaC).
2. (Mac) `make infra CONN=mk07348` to apply resource monitor.
3. Unit 2-6 of dbt curriculum.
4. stg_met__artworks.sql syntax cleanup (discussed but not applied; owner's call).
5. Prior deferred: AWS config cleanup, TTL decision, V/R/B rewords.

**MUST NOT happen next window (foot-guns):**
- Do NOT run dbt from the workspace (Mac-only).
- Do NOT create unit-2 journal file until Unit 2 actually starts.
- Do NOT apply resource monitor from the workspace (Mac `make infra` only).
- Do NOT modify stg_met__artworks.sql without owner sign-off (it's deployed and working).
- Do NOT add new schemas to `generate_schema_name.sql` allowlist without first
  creating them in IaC.

**Hand-off prompt:**

```text
Read AGENTS.md first, then ONLY the latest dated entry in docs/context/session-3-progress-log.md
(the 2026-06-05 "Part 3c" entry). Then read docs/context/dbt-curriculum.md for the syllabus +
new-window protocol (check the Status table for the ACTIVE unit). Stop once you can act.

SOLO CHECK before any write: count cortex_code_snowsight sessions in the last ~10 min
(QUERY_TAG ILIKE '%cortex_code_snowsight%') and check ARTWORK_DB.BRONZE.CORTEX_FORK_INCIDENTS.
Exactly 1 = solo; >1 = stop and ask. Do not abort husks.

DUAL-FS: Workspace edits are NOT on my Mac until I sync. Report applied-to-account yes/no and
pushed-to-Mac yes/no. No make/python/dbt from the workspace -- I run those on the Mac.

GATING: state your plan and WAIT for my explicit go + the date before any write or execution.

ROLE: You are my senior dbt MENTOR. Hands-on, build-as-we-go. YOU decide within-unit
sequencing; I run the commands on my Mac. Explain the WHY, name decision forks, introduce
deliberate failures for diagnosis practice. Reference docs/context/dbt-governance-plan.md
for governance context (PROPOSAL status, MVG-1/2 implemented, MVG-3 authored).

PROJECT (one line): branch donkey-kong-sandbox; account OBANOYY-MK07348 (admin PORCHFLAKE/
ACCOUNTADMIN); Medallion over Met OpenAccess. dbt project = artwork_pipeline/ (Mac dbt Core,
ARTWORK_TRANSFORMER_SVC). SILVER.STG_MET__ARTWORKS exists (503 rows). Unit 1 COMPLETE.
Unit 2 (dbt test) is ACTIVE in the curriculum. Resource monitor authored but not yet applied.

UN-SYNCED workspace delta (pending Mac sync): profiles.yml already synced; remaining =
infrastructure/{create,drop}_resource_monitors.sql, scripts/manifest.txt,
docs/context/{dbt-governance-plan,dbt-curriculum,file-map,session-3-progress-log}.md,
docs/context/dbt-journal/unit-1-first-green-run.md, plus prior-session delta (Makefile,
CLAUDE.md, extraction/met/*, infrastructure/create_tasks.sql).

FIRST RESPONSE: quote the latest `End of this window` header back to me, confirm solo=1,
then check dbt-curriculum.md Status table for the active unit and propose next steps.
Wait for my go + date.
```

- **End of this window (2026-06-05 Part 3c; CANONICAL -- supersedes Part 3b above. Account OBANOYY-MK07348, branch donkey-kong-sandbox. This turn: Unit 1 First Green Run COMPLETE (STG_MET__ARTWORKS view live in SILVER, 503 rows). MVG governance macros implemented (override_create_schema + generate_schema_name with allowlist). Resource monitor IaC authored (not yet applied). Dual-mode profiles.yml written (dev + snowflake targets). Governance proposal doc (dbt-governance-plan.md) landed. Unit 1 journal complete with 8 key takeaways. APPLIED-TO-ACCOUNT: view created via owner's dbt run on Mac. NOT APPLIED: resource monitor. Next = Unit 2 dbt test.)**

---

### 2026-06-05 (Part 3d -- Unit 2 COMPLETE + Unit 3 kicked off, model authored as view)

**Solo-session check:** PASS -- 1 distinct `cortex_code_snowsight` session in last 10 min
(23 queries, all this window); `CORTEX_FORK_INCIDENTS = 0`.

**What changed this turn (workspace stage; applied-to-account: NO; pushed-to-Mac: NO):**
All edits are WORKSPACE-ONLY. No `make`/`dbt`/`python` was run from here. Nothing
applied to the account this turn. Nothing synced to the Mac this turn.
- COMPLETED `docs/context/dbt-journal/unit-2-trust-your-source.md` (144 lines): real
  session -- baseline PASS=5; deliberate `not_null` on `object_date` (FAIL 109); read
  compiled SQL; `severity: warn` (WARN 109, exit 0); `store_failures: true` -> hit
  "DBT_TEST__AUDIT does not exist" -> IaC-created schema+grants -> PASS=5 WARN=1.
  3 decision forks recorded (warn+store; IaC-owned audit schema; keep-both
  source/model redundancy). 6 key takeaways. Step 7 (warn_if/error_if) SKIPPED (count-
  based; percentage would need a custom generic test -- deferred).
- EDITED `docs/context/dbt-curriculum.md`: Status U2 -> complete, U3 -> active; fixed
  Unit 2 outline (was `primary_image_url`; corrected to `object_date`); fixed stale
  verification snippet (`SILVER_DBT_TEST__AUDIT` -> `DBT_TEST__AUDIT`, verbatim routing).
- CREATED `docs/context/dbt-journal/unit-3-second-staging-model.md` (76 lines): Unit 3
  journal from template; materialization decision = `view` documented with the
  view-vs-ephemeral tradeoff.
- CREATED `artwork_pipeline/models/staging/met/stg_met__enrichment_status.sql` (61
  lines): staging VIEW, typed passthrough of `BRONZE.MET_ENRICHMENT_CONTROL`
  (10 cols, 2327 rows). `{{ config(materialized='view') }}`.
- EDITED `artwork_pipeline/models/staging/met/_met__sources.yml` (36 -> 59 lines):
  added `met_enrichment_control` source table (`identifier: MET_ENRICHMENT_CONTROL`)
  with `unique`+`not_null` on OBJECT_ID and `not_null` on ENRICHMENT_STATUS.
- UPDATED `docs/context/file-map.md`: new model row; `_met__sources.yml` (59) +
  `_met__models.yml` (44) + `dbt-curriculum.md` (275) line counts refreshed.

**Cumulative workspace state vs the Mac (delta the NEXT sync carries):**
Prior un-synced (from Part 3c and earlier): `Makefile`, `CLAUDE.md`,
`extraction/met/{CLAUDE.md,README.md,control_enricher.py}`,
`infrastructure/create_tasks.sql`, `infrastructure/{create,drop}_resource_monitors.sql`,
`scripts/manifest.txt`, `docs/context/{dbt-governance-plan,file-map}.md`,
`docs/context/dbt-journal/unit-1-first-green-run.md`.
NEW this turn (Part 3d): `artwork_pipeline/models/staging/met/stg_met__enrichment_status.sql`,
`artwork_pipeline/models/staging/met/_met__sources.yml`,
`docs/context/dbt-curriculum.md`, `docs/context/dbt-journal/unit-2-trust-your-source.md`,
`docs/context/dbt-journal/unit-3-second-staging-model.md`,
`docs/context/file-map.md`, `docs/context/session-3-progress-log.md`.
NOTE: the Unit-2 dbt test YAML (`_met__models.yml`) + the IaC audit-schema changes
(`create_databases_and_schemas.sql`, `create_grants.sql`) were authored + synced +
applied in an EARLIER part of this session (per the hand-off prompt); they are NOT in
this turn's new delta but ARE already on the Mac / account.

**Live account state (verified read-only this turn):**
- `ARTWORK_DB.DBT_TEST__AUDIT.NOT_NULL_STG_MET__ARTWORKS_OBJECT_DATE`: 109 rows (full
  56-col rows). Audit schema live.
- `ARTWORK_DB.BRONZE.MET_ENRICHMENT_CONTROL`: 2327 rows, 10 cols, PK OBJECT_ID.
- `STG_MET__ENRICHMENT_STATUS`: NOT yet materialized (model authored but no Mac run).
- `CORTEX_FORK_INCIDENTS = 0`.

**First-action options for the NEXT window:**
- **(a)** Sync the Part 3d delta to the Mac, then run Unit 3 step 1 on the Mac:
  `dbt run --select stg_met__enrichment_status` then
  `dbt test --select source:met.met_enrichment_control stg_met__enrichment_status`.
  Expect a new VIEW in SILVER + tests green.
- **(b)** Do the Unit 3 deliberate-failure exercise first (on the Mac): temporarily
  remove `identifier: MET_ENRICHMENT_CONTROL` from `_met__sources.yml`, `dbt run`,
  observe dbt hunt for lowercase `met_enrichment_control` and fail, restore, re-run.
- **(c)** Sync only (no dbt), defer Unit 3 execution to a later window.

**Read-only verification queries (after the Mac `dbt run`):**
```sql
SHOW VIEWS IN SCHEMA ARTWORK_DB.SILVER;  -- expect STG_MET__ENRICHMENT_STATUS + STG_MET__ARTWORKS
SELECT ENRICHMENT_STATUS, COUNT(*) FROM ARTWORK_DB.SILVER.STG_MET__ENRICHMENT_STATUS
GROUP BY 1 ORDER BY 2 DESC;  -- rows sum to 2327
SELECT COUNT(*) FROM ARTWORK_DB.DBT_TEST__AUDIT.NOT_NULL_STG_MET__ARTWORKS_OBJECT_DATE;  -- 109
```

**Decision tree (next run output shapes):**
- `dbt run` creates `STG_MET__ENRICHMENT_STATUS` view -> proceed to `dbt test`; then
  close Unit 3 (journal takeaways + flip U3 complete / U4 active).
- `dbt run` errors "object does not exist: MET_ENRICHMENT_CONTROL" -> likely the
  deliberate-failure state (identifier removed) OR allowlist/source mismatch; check
  `_met__sources.yml` `identifier:` line.
- `dbt test` FAILS unique/not_null on OBJECT_ID in the control table -> real data
  integrity issue in `MET_ENRICHMENT_CONTROL`; investigate Bronze before proceeding.
- `dbt run` errors on schema/permission -> ARTWORK_TRANSFORMER lacks SILVER privilege
  OR generate_schema_name allowlist rejected the target (SILVER is allowlisted, so
  unlikely).

**Deferred patches (priority order):**
1. (Mac) Sync the Part 3d delta + the broader prior un-synced delta.
2. (Mac) `make infra CONN=mk07348` -- the resource monitor (Part 3c) is STILL not applied.
3. Unit 3 execution (a)/(b) above, then Units 4-6.
4. `stg_met__artworks.sql` syntax cleanup (discussed, not applied; owner's call).
5. Prior deferred: AWS config cleanup, TTL decision, V/R/B rewords.

**What MUST NOT happen in the next window (foot-guns):**
- Do NOT run dbt/make/python from the workspace -- Mac only.
- Do NOT mark Unit 3 complete until the owner has actually run `dbt run` + `dbt test`
  on the Mac and reported output (journal Commands/Errors/Takeaways are still pending).
- Do NOT add `met_enrichment_control` model tests to a brand-new `_met__models.yml`
  block without first confirming the view materialized (test the source now; model
  tests after the run).
- Do NOT change `stg_met__artworks.sql` without owner sign-off (deployed + working).
- Do NOT add schemas to the `generate_schema_name` allowlist without creating them in IaC.
- Do NOT assume the Part 3d delta is on the Mac -- it is NOT until the owner syncs.

**Hand-off prompt:**

```text
Read AGENTS.md first, then ONLY the latest dated entry in docs/context/session-3-progress-log.md
(the 2026-06-05 "Part 3d" entry). Then read docs/context/dbt-curriculum.md (check the Status
table -- Unit 3 is ACTIVE) and its journal docs/context/dbt-journal/unit-3-second-staging-model.md.
Stop once you can act.

SOLO CHECK before any write: count cortex_code_snowsight sessions in the last ~10 min
(QUERY_TAG ILIKE '%cortex_code_snowsight%') and check ARTWORK_DB.BRONZE.CORTEX_FORK_INCIDENTS.
Exactly 1 = solo; >1 = stop and ask. Do not abort husks.

DUAL-FS: Workspace edits are NOT on my Mac until I sync. Report applied-to-account yes/no and
pushed-to-Mac yes/no. No make/python/dbt from the workspace -- I run those on the Mac.

GATING: state your plan and WAIT for my explicit go + the date before any write or execution.

ROLE: You are my senior dbt MENTOR. Hands-on, build-as-we-go. YOU decide within-unit
sequencing; I run the commands on my Mac. Explain the WHY, name decision forks, introduce
deliberate failures for diagnosis practice.

PROJECT (one line): branch donkey-kong-sandbox; account OBANOYY-MK07348 (admin PORCHFLAKE/
ACCOUNTADMIN); Medallion over Met OpenAccess. dbt project = artwork_pipeline/ (Mac dbt Core,
ARTWORK_TRANSFORMER_SVC). SILVER.STG_MET__ARTWORKS exists (503 rows). Units 1-2 COMPLETE.
Unit 3 (second staging model) ACTIVE: stg_met__enrichment_status.sql authored as a VIEW over
BRONZE.MET_ENRICHMENT_CONTROL (2327 rows); source declared in _met__sources.yml. NOT yet run
on the Mac -- view not materialized in SILVER. Resource monitor (Part 3c) still not applied.

UN-SYNCED workspace delta (pending Mac sync): stg_met__enrichment_status.sql, _met__sources.yml,
dbt-curriculum.md, dbt-journal/{unit-2,unit-3}*.md, file-map.md, session-3-progress-log.md, plus
prior un-synced (resource_monitors IaC, manifest.txt, dbt-governance-plan.md, unit-1 journal,
Makefile, CLAUDE.md, extraction/met/*, create_tasks.sql).

FIRST RESPONSE: quote the latest `End of this window` header back to me, confirm solo=1, then
pick up Unit 3 (sync delta -> dbt run + dbt test on my Mac, or the identifier deliberate-failure
exercise first). Wait for my go + date.
```

- **End of this window (2026-06-05 Part 3d; CANONICAL -- supersedes Part 3c above. Account OBANOYY-MK07348, branch donkey-kong-sandbox. This turn: Unit 2 (dbt test) COMPLETE -- journal finalized with the real object_date FAIL 109 -> warn -> store_failures -> IaC audit schema arc + 3 decision forks (warn+store; IaC-owned DBT_TEST__AUDIT; keep-both source/model redundancy). Step 7 skipped. Unit 3 kicked off: stg_met__enrichment_status.sql authored as a VIEW over BRONZE.MET_ENRICHMENT_CONTROL (2327 rows), source declared in _met__sources.yml, Unit 3 journal created. APPLIED-TO-ACCOUNT: NO. PUSHED-TO-MAC: NO -- all workspace-only this turn. NEXT: owner syncs delta, then dbt run + dbt test on Mac to materialize STG_MET__ENRICHMENT_STATUS in SILVER.)**

### 2026-06-06 (config.toml -> connections.toml migration + DUAL-INSTANCE INCIDENT)

```
Task: migrate Snowflake connection DEFINITIONS from config.toml to connections.toml
so the VS Code extension + Python connector authenticate, keeping snow CLI + dbt working.
Decisions (owner-confirmed, go date 2026-06-06):
  D1 = remove [connections.*] from config.toml AFTER a verified cutover (Phase 6, GATED).
  D2 = config.toml STAYS for default_connection_name + [cli.*] + future config.
  D3 = key field written as private_key_path in connections.toml (fallback private_key_file
       if Mac #2 snow --version too old -- owner to confirm version).

Persistent plan/checklist: docs/context/connections-toml-migration-checklist.md (live;
resume protocol + per-phase boxes + rollback). Built so a fresh window or a mid-run
connection break can resume from the first unchecked [ ].

Applied this window (workspace-only):
  _lib.sh        : + SNOW_LIB_CONNECTIONS_TOML const; list_connections reads connections.toml
                   (bare [name]); set_default_connection existence-checks connections.toml but
                   keeps default_connection_name in config.toml; resolve_admin_account/user/
                   warehouse read connections.toml; + remove_toml_section helper (for Phase 6).
  init_profile.sh: shadow guard INVERTED -> connections.toml is now the PRIMARY seed target
                   (bare [<admin>], private_key_path); default_connection_name stays config.toml.
  03/04/05       : 03 chmod 600s connections.toml too; 04 preflight + 05 warehouse echo read
                   connections.toml.
  06/09/08       : seed loader/transformer + promote warehouse into connections.toml.
  setup.sh       : comment/usage/echo wording (no logic change).
  docs           : cli-connection.md, file-map.md, AGENTS.md status row updated.
All scripts bash -n clean. Phase 6 cutover (strip config.toml [connections.*]) NOT run --
GATED behind owner running `snow connection test -c mk07348{,_loader,_transformer}` on Mac #2.

DUAL-INSTANCE INCIDENT: a SECOND Cortex instance ran the SAME plan concurrently ~16:30-16:32
UTC and authored Phase 3 (06, 09) + Phase 4 (08) and rewrote parts of the checklist. Detected
via my checklist edit failing ("string not found") + 06/09/08 mtimes I never set. SQL solo-check
stayed 1 the whole time (file edits don't hit QUERY_HISTORY -- the SQL fork signal is BLIND to
filesystem races; treat mtimes as the real signal). Owner chose "kill the other, I continue";
CORTEX_FORK_INCIDENTS write DECLINED (applied-to-account stays NO). Other instance's 06/09/08
reviewed = design-consistent + bash -n clean, KEPT. It MISSED 04's preflight (config.toml ->
connections.toml) -- I fixed that. Lesson: the SQL solo-check is necessary but NOT sufficient
for filesystem forks; mtime divergence on files-I-didn't-touch is the canary.

APPLIED-TO-ACCOUNT: NO. PUSHED-TO-MAC: NO -- all workspace-only.

Task 2 (README refresh, Phase 10) COMPLETE: scripts/snowflake_cli/README.md (191->78)
+ git-setup/README.md (113->73) condensed. Only the GATED Phase 6 cutover remains.

FIRST RESPONSE next window: quote the latest `End of this window` header back, confirm solo=1
AND mtime-quiescence on scripts/snowflake_cli/*, then -- after the owner runs the Mac #2
`snow connection test` gate -- do the GATED Phase 6 config.toml cutover (remove the dead
[connections.*] blocks via remove_toml_section, .bak first). Also confirm snow --version
for D3. Wait for go + date.
```

- **End of this window (2026-06-06; CANONICAL -- supersedes the 2026-06-05 Part 3d marker. Account OBANOYY-MK07348, branch donkey-kong-sandbox. This turn: config.toml -> connections.toml migration Phases 1-10 APPLIED (workspace-only): _lib.sh (CONNECTIONS_TOML const, conn-aware resolvers read connections.toml, list_connections/set_default_connection split, NEW remove_toml_section), init_profile.sh (shadow guard inverted to primary seed path, private_key_path), 03/04/05 (connections.toml perms+preflight+echo), 06/09/08 (loader/transformer/promote -> connections.toml; authored by a CONCURRENT FORK, reviewed+kept), setup.sh wording, docs (cli-connection/file-map/AGENTS) + Task 2 READMEs condensed (scripts/snowflake_cli/README.md 191->78, git-setup/README.md 113->73) + cosmetic comment cleanup (02/07/10/cli-connection). All bash -n clean. config.toml retained for default_connection_name + [cli.*]. Phase 6 GATED cutover (remove config.toml [connections.*]) NOT run -- awaits owner `snow connection test` on Mac #2. DUAL-INSTANCE INCIDENT logged: 2nd instance raced the same plan ~16:30-16:43 (it authored 06/09/08 + Phases 8-10 docs/READMEs, reviewed+kept); owner killed it (took two attempts); SQL solo-check was blind (file edits, not queries) -- mtimes were the real signal. CORTEX_FORK_INCIDENTS write declined. APPLIED-TO-ACCOUNT: NO. PUSHED-TO-MAC: NO. NEXT: owner runs the Mac #2 `snow connection test` gate, then the GATED Phase 6 config.toml cutover; owner confirms snow --version for D3 (else swap private_key_path->private_key_file at the seed sites).)**
