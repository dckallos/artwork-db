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
- [x] Step 1 — Staged-set enumeration + baseline-method decision (see log entry)
- [x] Step 2 (Task 1) — Per-file provenance audit done (read-only, content-vs-spec). Result: ALL on-spec; ZERO (c). Owner decision still pending (see entry).
- [x] Step 3 (Task 2) — Static IaC reproducibility verification done. Verdict: structure reproducible; working pipeline not until Section C.
- [x] Step 4 (Task 3) — Owner PICKED Option A (2026-05-31) + requested a mirror diff first.
- [x] Step 4b — Mirror diff DONE (2026-05-31), CLEAN, confirms audit (see entry).
- [ ] Record-back (in progress) — met-deepdive.md + ddl-infrastructure.md "Session-3 reconciliation"; file-map.md; AGENTS.md self-lint.
- [ ] Commit on donkey-kong-sandbox — SEPARATE go-ahead required.
- [ ] make infra + post-apply runbook — SEPARATE go-ahead required.
- [ ] Record-back (only after owner sign-off) — met-deepdive.md + ddl-infrastructure.md blocks; file-map.md reconcile; AGENTS.md self-lint

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

### 2026-05-31 | STEP 1 | Staged-set enumeration + baseline-method decision
- **Action:** New window resumed against this log (prior window only reached Step 0).
  Treating THIS window as authoritative per single-instance rule. Re-read AGENTS.md,
  met-deepdive.md (Session-2b DDL review §B build-impact map + DDL-04/05, PIPE-05/06,
  AUTH-01, DATA-01/06), ddl-infrastructure.md (S2b reconciliation + 4 approved
  decisions), then enumerated the full workspace tree via `ls -R` (83 files / 12 dirs).
- **Baseline-method decision (IMPORTANT):** A true line-level diff vs the last
  committed baseline requires the in-Snowflake mirror `ARTWORK_OPS.GIT.ARTWORK_DB`,
  which is an **account query = execution** → forbidden without owner's explicit word
  (HARD RULE). `/workspace` is not a local git repo (prior standing evidence). So Task 1
  proceeds as a **content-vs-spec audit**: read each staged file and classify against
  the S2b build-impact map + the 4 approved cosmetic decisions; anything unexplained is
  flagged (c). This needs ZERO account execution. The mirror diff is offered to the
  owner as an optional confirmation step (it would need their go-ahead).
- **NEW FINDING (not in prior standing evidence):** `infrastructure/` now contains
  BOTH `create_grants.sql` AND `drop_grants.sql` and NO `grant_privileges.sql`. That
  means **approved decision #3 (rename `grant_privileges.sql → create_grants.sql`)
  appears ALREADY APPLIED** in the staged tree — a ghost-origin structural change, not
  just the line-69 bootstrap edit. Must scrutinize: manifest + paired-drop wiring must
  match the new name. Also confirmed both S2b NEW files exist: `create_bronze_views.sql`,
  `drop_bronze_views.sql`.
- **Conclusion:** Full staged inventory known; audit can proceed read-only. The rename
  is the first (b)/(c) candidate to verify.
- **Next:** Step 2 (Task 1) — read the audit-set files (bronze tables/views create+drop,
  grants, tasks, roles, manifest, bootstrap.py, orchestrate.sh) and build the per-file
  audit table; STOP for owner on every (b)/(c).

### 2026-05-31 | STEP 2 (Task 1) | Provenance + reconciliation audit
- **Method:** content-vs-spec, read-only (no account execution). Read 16 files this
  window: create/drop_bronze_tables, create/drop_bronze_views, create_grants,
  drop_grants, refresh_grants, create/drop_tasks, create_roles, create_file_formats,
  create_stages, create_service_user, manifest.txt, bootstrap.py, orchestrate.sh.
- **Provenance reality (from prior mtime evidence):** the ENTIRE staged slice was
  written in the two ghost clusters (00:51–00:52 and 01:04–01:07) — NONE in the
  surviving chat's history. So by the strict provenance test almost everything is
  bucket (b) ON-SPEC-GHOST-ORIGIN. The reassuring finding: the ghost instance
  implemented the S2b build-impact map + the 4 cosmetic decisions FAITHFULLY.
- **Per-file verdict (all KEEP):**
  - `create_bronze_tables.sql` (b) — RAW_* uppercased; +MET_ENRICHMENT_CONTROL (9 cols
    +PK, matches DDL-04 strawman exactly); +MET_CSV_SNAPSHOT (VARIANT raw-blob, DDL-05
    Option A). IF NOT EXISTS throughout. KEEP.
  - `drop_bronze_tables.sql` (b) — uppercased drops + 2 new tables, IF EXISTS, FQ. KEEP.
  - `create_bronze_views.sql` (b, NEW) — MET_WORKLIST; CREATE OR REPLACE; joins
    control×snapshot; `<descriptive source>` resolved to MET_CSV_SNAPSHOT (DDL-04 fork
    (a)); IMG-02 priority ORDER BY. KEEP.
  - `drop_bronze_views.sql` (b, NEW) — DROP VIEW IF EXISTS MET_WORKLIST. KEEP.
  - `create_grants.sql` (b) — = renamed grant_privileges.sql; header documents rename;
    adds LOADER SELECT on ALL+FUTURE VIEWS in BRONZE (S2b grant-gap fix). KEEP.
  - `drop_grants.sql` (b) — reworded to create_grants.sql; cascade-from-parent no-op. KEEP.
  - `refresh_grants.sql` (b) — adds ALL VIEWS SELECT (BRONZE/SILVER/GOLD). KEEP.
  - `create_tasks.sql` (b) — MET_LEASE_RECLAIM_TASK; CRON hourly; TTL 30min;
    ARTWORK_WH; CREATE OR REPLACE + RESUME. Matches build-impact map. KEEP.
  - `drop_tasks.sql` (b) — DROP TASK IF EXISTS MET_LEASE_RECLAIM_TASK. KEEP.
  - `create_roles.sql` (b) — EXECUTE TASK ON ACCOUNT uncommented (l.45), lockstep note. KEEP.
  - `manifest.txt` (b) — create_grants in place; create_bronze_views inserted after
    create_bronze_tables (step 8). Order satisfies deps. KEEP.
  - `bootstrap.py` (b, the named ghost) — l.69 adds "EXECUTE TASK" to
    REQUIRED_ADMIN_ACCOUNT_PRIVILEGES. **Self-consistency CONFIRMED:** verify-contract
    parses create_roles.sql active GRANTs = {CREATE WAREHOUSE, CREATE DATABASE,
    EXECUTE TASK} == frozenset → contract PASSES. Without l.69 (or without l.45
    uncomment) the preflight would self-abort. Lockstep is correct. KEEP.
  - `orchestrate.sh` (b) — teardown() comment notes create_grants rename;
    create_->drop_ pairing maps create_grants→drop_grants automatically. No logic
    change. KEEP.
  - `create_file_formats.sql`/`create_stages.sql`/`create_service_user.sql` (b) —
    UPPERCASE applied (JSON_RAW/PARQUET_RAW/BRONZE_LOAD_STAGE/DEFAULT_NAMESPACE). KEEP.
- **(c) OFF-SPEC / UNEXPECTED:** NONE found.
- **Mentor-flag (not a blocker, Section C):** MET_CSV_SNAPSHOT has no uniqueness on
  object_id and MET_WORKLIST joins control→snapshot without filtering to a latest
  snapshot batch. If the snapshot is ever re-landed by append (needed for DATA-01
  diff history), the JOIN fans out → duplicate worklist rows. Harmless while empty /
  single-snapshot; must be resolved when the seed/diff Python lands (Section C).
  Also minor: a view-level ORDER BY isn't guaranteed to survive an outer LIMIT — drain
  query should carry its own ORDER BY (Section C / Python).
- **Conclusion:** audit CLEAN. Everything is on-spec; the only issue is *provenance*
  (no review trail), which Option A (commit to freeze it) resolves. STOP for owner
  decision on the (b) set before any commit/apply.

### 2026-05-31 | STEP 3 (Task 2) | Static IaC reproducibility verification
- **Idempotency:** PASS. Stateful = IF NOT EXISTS (roles, wh, db/schema, tables,
  user); stateless/derived = OR REPLACE (file formats, stages, view, task). Conforms
  to approved decision #1.
- **Manifest completeness + dep order:** PASS. roles→wh→db/schema→file_formats→
  stages→create_grants→bronze_tables→bronze_views→service_user→tasks→refresh_grants,
  then git-setup last. View after its base tables AND after grants (FUTURE VIEWS
  grant covers it; refresh_grants re-catches ALL VIEWS). Task after control table.
- **Paired-drop coverage:** PASS. Every create_* has a drop_*; teardown reverses the
  manifest and runs paired drops. drop_bronze_views runs BEFORE drop_bronze_tables
  (reverse order) so the view goes before its bases. refresh_grants (non-create_) is
  correctly skipped; create_grants→drop_grants now auto-pairs (rename).
- **Privilege-contract preflight:** PASS. bootstrap.py frozenset == create_roles.sql
  active account grants (incl. EXECUTE TASK) → verify-contract green;
  assert-account-privileges runs after create_roles.sql, before create_warehouses.sql.
- **KNOWN GAPS (Section C — NOT this session unless owner says so):**
  1. Data seed not codified — MET_ENRICHMENT_CONTROL + MET_CSV_SNAPSHOT land EMPTY
     (no Python csv_bootstrap snapshot-land + control-seed yet); MET_WORKLIST returns
     0 rows pre-seed.
  2. AUTH-01 not done — ARTWORK_LOADER_SVC still placeholder password, no key-pair.
  3. Dead code — rename_and_update.py still present at repo root.
- **VERDICT:** structure: reproducible after audit; working pipeline: not until
  Section C. (No execution performed to prove it — awaiting owner word.)

### 2026-05-31 | STEP 4 (Task 3) | Back-on-track recommendation
- **Recommendation: Option A.** Audit is clean (zero off-spec), so revert (Option B)
  would only destroy correct work. Accept the reconciled DDL slice as the Session-3
  DDL deliverable; COMMIT on donkey-kong-sandbox with a precise message to freeze out
  the ghost ambiguity (branch becomes single source of truth); THEN — only on owner's
  go — a single `make infra`, followed by the post-apply SHOW/SELECT sanity runbook.
  Section C (Python) is the NEXT session.
- **STATE:** PRESENTED to owner. No commit, no apply, no register flip performed.
  Awaiting owner's pick (A vs B) and explicit go-ahead.
- **Next (only after owner sign-off):** record-back blocks (met-deepdive.md +
  ddl-infrastructure.md "Session-3 reconciliation"), file-map.md reconcile (add
  create_bronze_views.sql + drop_bronze_views.sql), AGENTS.md self-lint; then (separate
  go) the commit; then (separate go) make infra + runbook.

### 2026-05-31 | STEP 4b | Owner-authorized mirror diff (read-only)
- **Owner action:** picked Option A AND requested a mirror diff first → explicit
  authorization for read-only mirror introspection (no DDL, no orchestrator, no commit).
- **What ran (read-only):** `ALTER GIT REPOSITORY ... FETCH` (mirror already up to
  date, origin unchanged); `SHOW GIT BRANCHES` (donkey-kong-sandbox HEAD = commit
  `2e957708e0fd13a8c3a833a99549735f2991be9a`); `LS` committed `infrastructure/`
  (19 files) + `LS` live workspace `infrastructure/` (21) and `scripts/`.
  NOTE: line-level diff NOT run — needs a NAMED file format (inline `FILE_FORMAT => (...)`
  is rejected for single-file stage reads) and creating one is ad-hoc DDL (HARD RULE).
  Diffed on file-set + byte-size, cross-checked vs the Step-2 content reads. (Hash
  equality unavailable: mirror = git-blob sha1, workspace = md5.)
- **Findings (CLEAN — confirms Step-2 audit):**
  - File-set: committed has `grant_privileges.sql`, NO `create_grants.sql`, NO
    `create_bronze_views.sql`, NO `drop_bronze_views.sql`. Rename + 2 new view files are
    genuinely UNCOMMITTED. 21 = 19 − grant_privileges + create_grants + 2 views.
  - Size deltas all map to planned edits: create_tasks 408→2160 (stub→full task),
    create_bronze_tables 4511→7776 (+2 tables), drop_bronze_tables 2173→2672,
    create_roles 2503→2544 (EXECUTE TASK uncomment), grant_privileges 2754→create_grants
    3248 (rename+VIEW grants), refresh_grants 1196→1280 (VIEW grants), drop_tasks
    2314→1392 (stub→lean DROP), cosmetic files +1..+26 (UPPERCASE/comments). NO
    unexplained delta; NO off-spec content.
  - scripts: bootstrap.py/manifest.txt/orchestrate.sh in the 01:04–01:07 ghost cluster;
    all other scripts untouched baseline.
- **Conclusion:** mirror diff INDEPENDENTLY confirms the audit. Proceeding to Option-A
  record-back (DOCS-ONLY). Commit + make infra remain separate owner go-aheads. Do NOT
  flip any register entry to applied (objects not yet applied; needs explicit word).
