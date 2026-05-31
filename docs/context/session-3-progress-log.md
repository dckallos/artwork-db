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

### 2026-05-31 | OWNER DECISION | Option A chosen; owner committed Phase 1
- Owner picked **Option A** and reported "I've committed" (Phase 1 commit of the 18
  reconciled files done by owner in their terminal). Authorized "Proceed".
- **Phase 0 verify (commit landed?) — NOT tool-possible:** `snow git fetch` and
  `snow git list-files` are now hard-blocked by the execution sandbox ("snow subcommand
  'git' is not supported"). Could not independently re-confirm the commit from here;
  trusting owner's statement. (A later window with snow-git access should re-verify.)
- **Phase 2 apply (`make infra`) — BLOCKED in sandbox:** `make` is not on the sandbox
  allowlist (only ls/dbt/snow). The apply needs full-system bash (dangerously_disable_sandbox,
  which prompts the owner) OR the owner runs `make infra` in their own terminal.
- **Next:** attempt `make infra` via sandbox-disabled bash (owner permission prompt).
  If owner prefers to run it themselves, they report results and I proceed to Phase 3
  (read-only SHOW/SELECT sanity runbook) + Phase 4 (record-back).

### 2026-05-31 | TIMELINE RECONCILIATION | this window is AUTHORITATIVE
- **Owner confirmed:** this is the only living session; the other instance (author of
  the "OWNER DECISION | Option A chosen; owner committed Phase 1" entry above) is DEAD.
  Its entry described a parallel branch — it is preserved (append-only discipline) but
  is NON-AUTHORITATIVE.
- **Authoritative facts (owner-stated 2026-05-31):**
  1. Phase 1 COMMITTED — the 18 reconciled files are committed on donkey-kong-sandbox.
  2. Phase 2 APPLIED — owner ran `make infra` locally on their Mac (their terminal);
     full orchestrator log reviewed in this window; clean idempotent run (see the
     "09:33 GMT | APPLY" entry above).
- **Net:** both Phase 1 (commit) and Phase 2 (apply) are DONE. The dead twin had only
  reached "about to apply." Record-back now proceeds from this window only.
- **Next:** append dated commit+applied notes to ddl-infrastructure.md + met-deepdive.md
  (correct the stale PK-uniqueness flag), file-map.md, AGENTS.md Status/Roadmap.

### 2026-05-31 | TIMELINE RECONCILIATION | dead-twin entries above resolved
- The two entries immediately above ("OWNER DECISION … owner committed Phase 1" and its
  Phase-0/2 notes, lines ~247–259) were written by a SECOND Cortex instance that has
  since died. Owner confirms (this turn): **this window is the only living session**,
  **Phase 1 was committed** by the owner in their terminal, and **`make infra` was run
  locally on the owner's Mac** (the orchestrator log captured in the APPLY entry above).
- The twin's entries are KEPT (append-only discipline) as primary evidence of the
  dual-instance incident — NOT deleted. They and this window's APPLY entry describe the
  same real-world outcome (Option A committed + applied); only the narration differs.
- **Authoritative state of record:** Phase 1 COMMITTED; Phase 2 `make infra` APPLIED
  (clean, idempotent, sanity-confirmed from log); Phase 4 record-back now completed in
  the four docs below. **Session 3 COMPLETE.** Section C is the next session.

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
