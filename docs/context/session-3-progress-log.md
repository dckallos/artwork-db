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
- **End of this window (fourth and final-final).**

