# met-deepdive.md — Met data collection & ingestion: decision register

> **Tier-1 DECISION REGISTER (not a plan, not a syllabus).** This doc captures
> every open question about Met OpenAccess data collection and ingestion as a
> **granular, addressable, cross-session-stable** list. It is the companion to
> `engineering-playbook.md` (which holds order-independent *patterns*); this doc
> holds *our specific Met questions and their evolving answers*.
>
> **The point is durability:** a question raised in one session must be findable
> and resumable in the next. So every concern gets a **stable ID** (e.g. `IMG-04`)
> that we cite across sessions — granularity is never lost to summarization.

## How to use this doc

- **One ID per concern.** Cite it in conversation ("let's resolve `DATA-01` today").
  IDs are stable and never reused; closing one keeps its number.
- **Class prefixes cross-cut the 5 optimization tracks** in `engineering-playbook.md`
  — a single question may touch Track 2 (ingestion) *and* Track 3 (tables). The
  class is about the *concern type* (legal/cost/pipeline/…), not the track.
- **Status values:** `open` (raised, untouched) · `exploring` (notes/positions
  recorded, not committed) · `decided` (owner signed off — record the decision and
  date) · `gated` (decided but deliberately not yet applied).
- **Never flip to `decided` without the owner's explicit sign-off.** The mentor
  records positions as `exploring`; the owner decides.
- **Append, don't overwrite.** When a question evolves, add to its Notes with a
  date. Preserve the original question text verbatim.

## Verified Met facts (web-verified 2026-05-30 — don't re-research)

- **License:** the entire `MetObjects` dataset is **CC0 1.0**; *images* are CC0
  only for works where **`isPublicDomain = true`**. The Open Access initiative
  "makes images of public-domain artworks and basic data on all accessioned works
  available for unrestricted use under CC0."
  (https://github.com/metmuseum/openaccess, https://www.metmuseum.org/hubs/open-access,
  https://deepwiki.com/metmuseum/openaccess)
- **Collection API base:** `https://collectionapi.metmuseum.org/public/collection/v1`.
  Requested rate limit **80 req/sec**, no key/registration required.
  (https://metmuseum.github.io/, https://publicapi.dev/metropolitan-museum-of-art-api)
- **Change detection:** `GET /objects?metadataDate=YYYY-MM-DD` (optionally
  `&departmentIds=3|9|12`) returns the `objectIDs` whose metadata was updated after
  that date — the incremental driver. Only the id list is used; details come from
  the per-object call. (https://metmuseum.github.io/,
  https://make.wordpress.org/openverse/handbook/openverse-catalog/provider-api-met-museum/)
- **Image host is separate from the API:** `primaryImage` / `primaryImageSmall` /
  `additionalImages` URLs live on **`images.metmuseum.org`** (CDN, e.g.
  `/CRDImages/as/original/DP251139.jpg`), NOT on the rate-limited
  `collectionapi.metmuseum.org`. So liveness checks (`HEAD`) need not touch the
  rate-limited API. (https://metmuseum.github.io/)
- **CSV vs API split:** the canonical **GitHub `MetObjects.csv`** (distributed via
  **Git LFS**, ~225 MB LFS object; ~471,581 objects) carries ~47 descriptive
  columns incl. `Is Public Domain`, `Is Highlight`, `Metadata Date` — but
  **does *not* carry image URLs**: "Images are not included and are not part of the
  dataset." Image URLs come only from the API `/objects/{id}` call.
  (https://github.com/metmuseum/openaccess, https://github.com/metmuseum/openaccess/issues/2)
  - *Nuance (don't conflate):* the HuggingFace mirror `metmuseum/openaccess` is a
    **separate, enriched** distribution whose schema *does* include `primaryImage`
    columns (joined from the API). The repo's extractor uses the GitHub CSV, so the
    "image URLs are API-only" premise holds for us.
    (https://huggingface.co/datasets/metmuseum/openaccess)

## What already exists (grounding — see `extraction.md`)

The `extraction/met/` package is a mature 3-phase, resumable, idempotent ETL:
bootstrap (CSV→SQLite UPSERT, image cols preserved across refreshes) → enrich
(async API for image URLs, token-bucket rate limiter + backoff, ~6.5h at 20 rps
over ~471k rows) → upload (NDJSON + PUT + COPY INTO `BRONZE.raw_met_objects`).
**Local SQLite is intermediate; Snowflake Bronze is the destination.** This register
is about *policy and hardening decisions on top of that*, not a rebuild.

---

## Register

### LEG — legal / licensing

| ID | Status | Question | Notes / position |
|---|---|---|---|
| `LEG-01` | exploring | From a legal perspective, what must we keep (and may we keep) from the Met CSV in Snowflake? | The dataset is CC0 1.0 — storing **all** CSV columns is legally fine. The question is really *value/cost* retention, not legality. Keep the rights-bearing flags (`Is Public Domain`) regardless — they gate monetization (`LEG-02`). |
| `LEG-02` | exploring | The image URL is the profit center (e.g. resell prints on Etsy). What makes that legal? | **Image-URL availability ≠ reproduction rights.** CC0 reproduction (incl. commercial) is clean only where `isPublicDomain = true`. Treat `isPublicDomain` as the monetization gate: Gold "sellable" = `isPublicDomain ∧ has primaryImage`. |
| `LEG-03` | open | Attribution/citation the Met *requests* even under CC0 — do we honor it in Gold? | Met asks (not requires) for attribution on CC0 datasets. Cheap to carry `creditLine`/artist/title for caption use; decide whether Gold surfaces it. |

### IMG — image-URL lifecycle (the crown jewel)

| ID | Status | Question | Notes / position |
|---|---|---|---|
| `IMG-01` | exploring | How do we *progressively* get image URLs instead of one giant run? | Worklist-driven, bounded batches (see `AUTO-02`). The pipeline is already resumable; the missing piece is a *prioritized, capped* worklist rather than "enrich everything." |
| `IMG-02` | exploring | How do we decide *which* artworks to enrich first? | Prioritize by monetizable value: `isPublicDomain` first, then `isHighlight` + high-value departments (e.g. paintings). First slice of the run yields sellable inventory fastest. |
| `IMG-03` | exploring | How do we avoid re-making the same API calls over time? | Use `GET /objects?metadataDate=` deltas (verified). Only re-hit `/objects/{id}` for objects whose `Metadata Date` advanced since last enrich. Pairs with `DATA-03`. |
| `IMG-04` | exploring | How do we validate that *current* image URLs are still valid? | Decouple from discovery: a cheap `HEAD` against `images.metmuseum.org` (CDN, **not** rate-limited) confirms liveness without API pressure. Re-discover via API only when a HEAD fails or `metadataDate` moved. **Strawman 2026-05-30 (Fork 1 → B):** liveness gets its *own* `image_status` enum (`unknown\|live\|dead`) + `last_head_check_at` on the control table — kept distinct from the discovery `enrichment_status` so "never had an image" (`no_image`) ≠ "link now dead" (`dead`). See Session-1 strawman §1. |
| `IMG-05` | open | What rate-limit / backoff policy — given the prior 24h ordeal? | Met allows **80 rps** (verified); extractor defaults to a polite 20 rps with token-bucket + jittered backoff (already sound). Lever: raise rps for backfills, stay polite for steady-state. The old ordeal was a more naive tool. |
| `IMG-06` | open | How do we make image enrichment "automated from Snowflake" when fetching is cheapest locally? | Resolved in principle by the worklist split (`AUTO-02`): Snowflake schedules/decides *what*; the Mac fetches. Fully Snowflake-native fetch (External Access + UDF) is possible but costs warehouse credits — see `COST-02`. |
| `IMG-07` | open | **(Mentor-flagged.)** Do we store just the image *URL*, or archive the image *bytes*? | URLs rot; for an Etsy profit motive, link rot is an existential risk to inventory. Option: archive high-res bytes for the `isPublicDomain ∧ primaryImage` subset into a Snowflake stage / object storage so "sellable inventory" survives upstream URL churn. Tradeoff: meaningful storage + egress cost (`COST-04`) vs. durability of the crown-jewel asset. Scope it to the *sellable* subset, not all 471k. Ties `LEG-02`, `IMG-04`. |

### PIPE — execution locus / architecture

| ID | Status | Question | Notes / position |
|---|---|---|---|
| `PIPE-01` | decided | Keep the Python local on the Mac, or move to a Snowflake-native architecture? | Keep fetching local. Enrich is ~6.5h of *waiting on the API*; a warehouse would bill to sit idle. Local compute = $0. Snowflake owns storage + transforms + worklist decisions. **DECIDED 2026-05-30:** keep fetch **local**. The *deciding* reason is architectural, not raw $: egress/I-O-bound work (awaiting an external API) must stay off per-second warehouse compute — the ~6.5 credits (~few $) for a native run is small, so cost alone isn't the knockout. Supporting reasons: the battle-tested token-bucket/backoff logic already exists locally (`image_enricher.py`); native fetch needs an External Access Integration (network rules + secret governance → more IaC surface); a 6.5h external fetch is far more debuggable/restartable locally. **Flip condition (principled boundary, not dogma):** if the Mac-on-a-desk dependency ever becomes unacceptable (true 24/7 cloud scheduling with no laptop in the loop), revisit SPCS or a serverless task + External Access despite the cost. For a single-owner learning repo, local wins decisively. Ties `COST-02`. |
| `PIPE-02` | open | How do local Python + the SQL scripts reconcile with the `infrastructure/` DDL? | Runtime ETL (`extraction/met/*`) *consumes* IaC objects (Workflow 2); it is not IaC. The SQL it runs is operational (COPY/UPSERT), separate from the versioned DDL. Keep that boundary explicit. |
| `PIPE-03` | decided | What's the hybrid division of labor — Mac vs Snowflake? | Mac: CSV download, SQLite staging, API fetch, NDJSON build, PUT. Snowflake: COPY, Bronze/Silver/Gold transforms, worklist computation, scheduling. **DECIDED 2026-05-30:** the `PIPE-05` decision sharpens this from a loose list into a **two-table contract**. **Mac owns** all external I/O + ephemeral compute (CSV download, API fetch, NDJSON build, PUT, batch status callbacks) and is effectively **stateless / rebuildable** from Snowflake + CSV. **Snowflake owns** durable state + the orchestration *brain* + scheduling (the control/worklist table, Bronze landing, Silver/Gold transforms, the worklist-computation Task per `AUTO-01`, run/phase audit per `AUTO-03`). **Contract surface = exactly two tables:** (1) a **prioritized worklist** (Snowflake→Mac, Mac claims/drains, ordered per `IMG-02`: `isPublicDomain` → highlights → high-value departments); (2) **Bronze landing + batch status callback** (Mac→Snowflake, image data via COPY + one batch `MERGE` of status). Boundary principle: system-of-record + brain in Snowflake, external I/O + ephemeral compute on the cheapest executor; the interface is a *small* set of single-owner tables, never a chatty per-row sync. Ties `PIPE-05`, `AUTO-01/02/03`, `IMG-02`. **Strawman realization 2026-05-30 (non-final):** the two-table contract is drawn concretely — worklist = `MET_WORKLIST` view (down), landing+callback = `RAW_MET_OBJECTS` COPY + one `MET_ENRICHMENT_CONTROL` status MERGE (up). See Session-1 strawman §2–§3. |
| `PIPE-04` | open | You flagged the SQL scripts as "untested." How do we trust them before they touch DDL? | Two layers: compile-validate operational SQL (`snow sql` / compile-only) in a preflight; and once dbt lands, the Silver/Gold transforms get dbt tests. This is a genuine gap, not yet covered. |
| `PIPE-05` | decided | **(Mentor-flagged — the hinge.)** Where does enrichment *state* live: local SQLite or a Snowflake control table? | Today `enrichment_status` / `bronze_uploaded_at` live in local SQLite. "Automate from Snowflake" pulls the worklist + state toward a Bronze control table (so a Task can compute what needs work and audit progress). Fork: (a) keep SQLite as the only state, Snowflake just receives uploads — simplest, but Snowflake can't *decide* work; (b) mirror state into a Snowflake control table the Mac drains (`AUTO-02`) — enables scheduling/observability at the cost of a sync contract. Most of the pipeline questions rotate on this. Ties `AUTO-01/02/03`, `PIPE-01`. **DECIDED 2026-05-30 — reframed the fork (rejected the "mirror" framing).** A true two-way *mirror* (both systems authoritative) is an anti-pattern → reconciliation hell; never let two systems claim authority over the same fact. Chosen **Option 3 (not a/b as written): Snowflake-authoritative worklist + coarse status; SQLite *demoted* to disposable in-run scratch.** Snowflake owns a **thin Bronze control table** — the durable, cross-run, schedulable system of record — with *narrow* columns only (`object_id, enrichment_status, last_enriched_at, metadata_date, has_primary_image, last_head_check_at, claimed_by_batch`), **not** the full 47-column row. SQLite is demoted to fast in-run execution scratch (500-row commits, intra-run resumability) and is rebuildable/disposable. **Critical cost rule:** with ~471k rows, **never** round-trip Snowflake per object for status — that's hundreds of thousands of connector calls + warehouse time. Use **batch-grained callbacks**: the Mac *claims* a batch of N object_ids from the worklist, fetches all N locally, then does **one** `COPY`/`MERGE` to update status for the batch. Snowflake stays authoritative at *batch* grain; per-object work stays local + free. This operationalizes the `AUTO-02` worklist pattern and unblocks `AUTO-01` (Task computes the worklist) + `AUTO-03` (run history in Snowflake). Ties `PIPE-01`, `PIPE-03`, `AUTO-01/02/03`, `IMG-02`. **Strawman realization 2026-05-30 (non-final):** the "narrow control table" is given a concrete column set (`DDL-04`) and the "batch-grained callback" a concrete O(1)/batch MERGE shape; the SQLite→control **demotion delta** is mapped column-by-column. See Session-1 strawman §1, §3, §4. |
| `PIPE-06` | exploring | **(Session-2 review.)** Where does the lease-claim happen — does the enrich phase open its own Snowflake connection, or is "claim" a separate command that materializes a local worklist the Mac then drains? | Today `image_enricher.py` is **Snowflake-free** (reads `_pending_object_ids()` from SQLite). The strawman's lease-MERGE (§2) requires Snowflake access in Phase 2. Fork: (a) enrich opens a Snowflake connection, claims, fetches, calls back — fewer moving parts, but couples fetch to live Snowflake; (b) a `claim` subcommand writes a local worklist file the offline fetcher drains — keeps fetch decoupled/offline-capable, but adds a command + a local artifact. Ties `PIPE-03`, `PIPE-05`, `AUTO-02`. |

### DATA — Met data semantics / quality

| ID | Status | Question | Notes / position |
|---|---|---|---|
| `DATA-01` | open | **(Owner did not raise — mentor-flagged, high value.)** The CSV is a full snapshot; bootstrap is UPSERT-only. When the Met deaccessions a work it just vanishes from the next CSV — nothing deletes the stale row. How do we propagate removal? | Snapshot-diff: compare the new CSV `object_id` set vs. existing; tombstone the missing rows so removal flows Bronze→Silver→Gold and drops from sellable Gold fast. Directly serves AGENTS.md "timeliness/deaccession" + "delete propagation" cornerstones. Strong learning fork — pairs with `DDL-02`. **Session-2b note 2026-05-30:** `BRONZE.MET_CSV_SNAPSHOT` (`DDL-05`, owner-preferred) is the natural Snowflake home for the snapshot-diff — compare the new bootstrap snapshot's `object_id` set vs the prior one to detect vanished rows. |
| `DATA-02` | open | How do we detect/handle CSV schema drift (columns added, renamed, removed)? | 47 columns are mapped 1:1 today. Need a column-contract check at bootstrap so a silent header change doesn't corrupt the load. |
| `DATA-03` | exploring | How do we use `Metadata Date` to drive incremental work? | CSV `Metadata Date` + API `metadataDate` deltas together identify the minimal re-enrich set. Pairs with `IMG-03`. |
| `DATA-04` | exploring | "Most of the data" is in the CSV — what's authoritative where? | CSV = descriptive truth (continuously updated upstream). API = image URLs only. Model accordingly: CSV-sourced columns vs. API-sourced image block. |
| `DATA-05` | open | **(Mentor-flagged.)** Do CSV re-pull and image re-validation share a cadence, or differ? | You noted image URLs change rarely. So tier the cadences: (a) CSV re-pull — frequent (descriptive truth + deaccession signal, `DATA-01`); (b) image *discovery* — driven by `metadataDate` deltas + null-image backfill (`IMG-03`); (c) image *liveness* `HEAD` re-check — slow background sweep (`IMG-04`), since CDN URLs are stable. Avoids paying full-enrichment cost on every refresh. Ties `AUTO-01`, `IMG-04`. |
| `DATA-06` | exploring | **(Session-2 review.)** Does `download_csv` actually fetch the CSV, or a Git-LFS *pointer*? | `MetObjects.csv` is distributed via **Git LFS** (~225 MB, verified). `raw.githubusercontent.com/.../master/MetObjects.csv` commonly returns the ~130-byte **LFS pointer file**, not the CSV bytes. The extractor is described as "untested," so it may never have loaded 471k rows. `csv_bootstrap.download_csv` has no size/row-count integrity guard, so a pointer or truncated body would "succeed" silently. Session-3 fix: assert min-size/row-count after download, and/or switch to `media.githubusercontent.com` or the LFS media endpoint. Ties `DATA-02`. |

### DDL — schema design

| ID | Status | Question | Notes / position |
|---|---|---|---|
| `DDL-01` | open | Which DDL decisions are we already prepared to make now? | Few, honestly — most should wait until a Silver table is large enough that pruning/clustering *matters* (avoid premature optimization). Capture candidates here as they surface; don't pre-commit. |
| `DDL-02` | open | Clustering so deaccession/delete prunes cheaply? | Tie to `DATA-01`: choose a clustering key so tombstoned/affected rows cluster together and delete cheaply. Only worth designing once data volume justifies it. |
| `DDL-03` | open | How do we model images as a first-class high-value column across Bronze→Silver→Gold? | Bronze keeps the raw API block; Silver conforms to `primary_image_url` + flags; Gold exposes the sellable, validated subset. Ties `LEG-02`, `IMG-04`, `IMG-07`. |
| `DDL-04` | exploring | **(Strawman 2026-05-30.)** What is the thin Bronze enrichment-control table schema (the `PIPE-05` system of record)? | `BRONZE.MET_ENRICHMENT_CONTROL` strawman: `object_id` PK, `enrichment_status` (outcome enum), `last_enriched_at`, `metadata_date`, `has_primary_image`, `image_status` (liveness enum), `last_head_check_at`, `claimed_by_batch`, `claimed_at`. Narrow orchestration state only — descriptive/image *data* stays in `RAW_MET_OBJECTS`. Claim = lease (not a status value); priority inputs joined via the worklist view, not duplicated. **NON-FINAL** — reconcile + sign off in Session 2. See Session-1 strawman §1. Ties `PIPE-05`, `AUTO-01/02`, `IMG-02/04`, `DDL-03`. **Session-2 review 2026-05-30 — two under-specifications found:** (i) **seed path** — the strawman never says how control gets its initial ~471k `pending` rows; options are a bootstrap-time seed-COPY of `(object_id, metadata_date, gate flags)` or derive from `RAW_MET_OBJECTS`. (ii) **worklist descriptive-source tension** — `MET_WORKLIST` joins control → `is_public_domain/is_highlight/department`, but no Silver table exists yet (only `BRONZE.raw_met_objects` VARIANT). Fork: (a) join to VARIANT extractions, or (b) relax the "narrow" rule and carry the 3 priority flags *in* control. Both `exploring`, for Session-3 design. **Resolved toward (a) 2026-05-30 (owner-preferred, gated):** land the full CSV into Snowflake at bootstrap as a new `BRONZE.MET_CSV_SNAPSHOT` table (see `DDL-05`); `MET_WORKLIST` joins `control → MET_CSV_SNAPSHOT` for priority ordering. Keeps control narrow and makes the descriptive truth queryable for *pending* (not-yet-enriched) rows — which `raw_met_objects` cannot, since it's only populated post-upload. |
| `DDL-05` | exploring | **(Session-2b setup 2026-05-30, owner-preferred Option A.)** Land the full Met CSV into Snowflake at bootstrap so the worklist can prioritize *pending* rows and deaccession can be detected. | `BRONZE.MET_CSV_SNAPSHOT` — **VARIANT raw-blob** (one JSON row per `object_id`, mirroring the `raw_met_objects` shape: `object_id INT`, `raw_payload VARIANT`, `_batch_id`, audit cols), seeded at **bootstrap** independent of enrichment. Rationale (plain): to fetch the *best* artworks first (public-domain → highlight → department), Snowflake needs the descriptive fields **before** fetching; today those live only in local SQLite for pending rows, and only reach Bronze (`raw_met_objects.raw_payload:csv.*`) *after* enrichment+upload — too late to rank. Discipline: **land the whole raw row in Bronze, promote selectively in Silver** — sparse columns (`locus/excavation/river/subregion/reign/dynasty`) cost ~nothing as VARIANT; `artist_ulan_url`/`artist_wikidata_url`/`object_wikidata_url` are the cross-museum entity-normalization hooks worth keeping. **Bonus:** this same full-list-in-Snowflake is the natural home for the `DATA-01` deaccession snapshot-diff. **Fork (for 2b/build):** VARIANT raw-blob (chosen default, max flexibility) vs typed columns. **GATED.** Ties `DDL-04`, `DATA-01`, `AUTO-01/02`, `IMG-02`, Track 4 (entity normalization). |

### COST

| ID | Status | Question | Notes / position |
|---|---|---|---|
| `COST-01` | exploring | Cost estimate of the full pipeline? | bootstrap + enrich = local = **$0 compute**. Snowflake cost = COPY warehouse-seconds (minutes on X-Small) + small VARIANT storage. Steady-state deltas are tiny. |
| `COST-02` | exploring | Cost of enriching *in* Snowflake vs locally? | In-Snowflake fetch (External Access + UDF/proc) bills warehouse time for ~6.5h of API-waiting — wasteful. Local fetch avoids it entirely. Anti-pattern to avoid. |
| `COST-03` | open | Cost of ongoing image-URL re-validation? | `HEAD` on the CDN from the Mac = $0. If ever done from Snowflake, it's warehouse + egress — prefer local. |
| `COST-04` | open | Storage footprint? | Bronze VARIANT for ~471k rows is small (compressed). Local: GitHub CSV via Git LFS (~225 MB) + 1–2 GB SQLite under `extraction/met/data/` (gitignored, disk-bound). If `IMG-07` archives image bytes, add high-res object storage to the estimate — scope to the sellable subset. |

### AUTO — orchestration / scheduling

| ID | Status | Question | Notes / position |
|---|---|---|---|
| `AUTO-01` | exploring | Can Snowflake Tasks/Streams *schedule detection* of stale/missing images? | Yes — a scheduled Task can compute "needs discovery or revalidation" (null image ∨ `metadataDate` advanced ∨ last-checked age exceeded) into a worklist table. (Note: `infrastructure/create_tasks.sql` is currently a placeholder.) **Strawman 2026-05-30:** the "needs work" predicate is realized as the `MET_WORKLIST` **view's** `WHERE` clause (no separate worklist table to maintain); a Task's job shrinks to lease-reclaim/housekeeping rather than recomputing a materialized list. Streams rejected for the queue role (see §2). See Session-1 strawman §2. |
| `AUTO-02` | exploring | **Worklist pattern** to reconcile "automate from Snowflake" with "fetch cheaply on the Mac." | Snowflake (Task) writes a prioritized worklist table → the Mac polls/drains it, fetches, and uploads results → Snowflake marks them done. Snowflake decides *what*; the Mac does the *fetch*. Resolves the `PIPE-01`/`PIPE-05`/`IMG-06` tension at minimal cost. **Strawman 2026-05-30:** "writes a worklist table" sharpened to a **view + lease columns** — drain = read bounded slice then atomic `MERGE` claim (`claimed_by_batch`/`claimed_at`); "marks them done" = the single batch status-callback MERGE (O(1)/batch guard). See Session-1 strawman §2–§3. |
| `AUTO-03` | open | **(Mentor-flagged.)** How do we get run history into Snowflake so automation is auditable? | Today `extraction_runs` lives only in SQLite and the Bronze `extraction_log` table is never written (per `extraction.md`). For Snowflake-driven scheduling we need run/phase history *in* Snowflake — land each phase's `running→success/failed` + counts into `BRONZE.extraction_log` so Tasks and dashboards can see it. Ties `AUTO-01`, `PIPE-05`. **Session-2 review 2026-05-30:** confirmed `extraction_log` is still written nowhere; `run.py`'s `status` reads only SQLite `extraction_runs`. Design-only this session — the batch status-callback path (strawman §3) is the natural carrier for a phase-level run record too. Build deferred to Session 3. **Session-2b correction 2026-05-30:** the target table **already exists** — `infrastructure/create_bronze_tables.sql` defines `BRONZE.extraction_log` (`log_id AUTOINCREMENT, source_system, batch_id, records_loaded, started_at, completed_at, status, error_message`). So `AUTO-03` needs **no DDL** — only the Python write path. Build-ready. |

### AUTH — authentication / service-identity

| ID | Status | Question | Notes / position |
|---|---|---|---|
| `AUTH-01` | APPLIED (code) 2026-05-31 | Should `ARTWORK_LOADER_SVC` authenticate by password or key-pair (or PAT)? | **DECIDED + BUILT: KEY-PAIR.** On branch `donkey-kong-sandbox` (committed; not yet `make iac`'d): `create_service_user.sql` now creates the user `TYPE = SERVICE` (no password possible). New `06_setup_loader_keypair.sh` (replaces the deleted `06_rotate_loader_password.sh`) lazily mints `~/.snowflake/keys/loader_rsa_key.{p8,pub}`, registers the pubkey via the admin JWT connection (`git-setup/operator/register_loader_public_key.sql`, replaces the deleted empty `rotate_loader_password.sql`), and upserts `[connections.loader]` to `authenticator=SNOWFLAKE_JWT` + `private_key_file` (via `_lib.sh upsert_toml_value_in_section`). `config.py`/`snowflake_uploader.py` use `private_key_file`; `.env.example` (root + met) dropped `SNOWFLAKE_PASSWORD` for `SNOWFLAKE_PRIVATE_KEY_FILE`. No chicken-and-egg: loader key registered by admin over JWT after `make iac`. Alternative C (PAT) not chosen. **NEXT: owner runs `make iac` + `setup.sh --phase loader` on Mac to apply.** Ties cli-connection, `PIPE-03`. |

---

## Session-1 strawman — control-table / worklist contract (appended 2026-05-30)

> **STRAWMAN — NON-FINAL.** Recorded for Session-2 reconciliation + owner sign-off.
> Nothing here is `decided`. The SQL below is illustrative shape only; the gate is
> DOWN (docs-only) — no objects were created. Forks resolved this session:
> **image liveness = its own `image_status` enum** (Fork 1 → B);
> **full detail lives here**, playbook only points back (Fork 2 → A).
> Realizes `PIPE-03` + `PIPE-05` (both `decided`); seeds `DDL-04`; advances
> `AUTO-01`, `AUTO-02`, `IMG-04` to `exploring`.

### 1. The thin BRONZE control table (`DDL-04`)

The control table is the **orchestration brain, not a data store.** The 47 CSV
columns and the image URLs themselves are *data* and live in `RAW_MET_OBJECTS`.
The control table carries only what a scheduling Task needs to **decide work** and
**audit progress** — honoring `PIPE-05`'s "narrow, not the full 47-column row" rule.

```sql
-- STRAWMAN — do NOT apply (gate down)
CREATE TABLE BRONZE.MET_ENRICHMENT_CONTROL (
    object_id          NUMBER         NOT NULL PRIMARY KEY, -- Met objectID; join key to RAW_MET_OBJECTS
    enrichment_status  STRING         NOT NULL DEFAULT 'pending',
                                      -- OUTCOME enum: pending | done | no_image | error
    last_enriched_at   TIMESTAMP_NTZ,                       -- when API discovery last ran for this object
    metadata_date      DATE,                                -- Met "Metadata Date" / API metadataDate (change signal)
    has_primary_image  BOOLEAN,                             -- monetization gate result (LEG-02 / IMG-02)
    image_status       STRING         DEFAULT 'unknown',    -- LIVENESS enum: unknown | live | dead (IMG-04)
    last_head_check_at TIMESTAMP_NTZ,                       -- IMG-04 CDN HEAD liveness-sweep timestamp
    claimed_by_batch   STRING,                              -- lease owner: batch_id currently fetching this row
    claimed_at         TIMESTAMP_NTZ                        -- lease timestamp -> TTL reclaim of abandoned claims
);
```

**Per-column justification (why each earns a slot — it's *state*, not *data*):**

| Column | Why narrow-rule allows it |
|---|---|
| `object_id` | Identity + join key to `RAW_MET_OBJECTS`. Mandatory. |
| `enrichment_status` | **Outcome** only (`pending\|done\|no_image\|error`) — mirrors today's SQLite enum 1:1. |
| `last_enriched_at` | Pairs with `metadata_date` to compute the IMG-03 re-enrich set. |
| `metadata_date` | The incremental driver (DATA-03 / IMG-03). One narrow date, not the row. |
| `has_primary_image` | Lets the worklist + Gold prioritize **without** re-reading the VARIANT payload. |
| `image_status` | **Fork 1 → B.** Keeps "never had an image" (`no_image`) distinct from "link is now dead" (`dead`). Decouples liveness from discovery per IMG-04. |
| `last_head_check_at` | Drives the slow background liveness sweep (DATA-05 cadence c). |
| `claimed_by_batch` / `claimed_at` | The **lease** (see §2). Net-new; no SQLite equivalent. |

**Two design calls (recorded as positions, not decisions):**

- **Claim is a lease, not a status.** Rejected adding a `claimed` value to
  `enrichment_status`. Status = *outcome*; possession = orthogonal
  (`claimed_at IS NOT NULL AND claimed_at > DATEADD(minute,-:ttl,CURRENT_TIMESTAMP)`).
  Folding possession into the enum would create a combinatorial blow-up and lose the
  prior outcome on reclaim.
- **Priority inputs are deliberately NOT duplicated here.** `is_public_domain`,
  `is_highlight`, `department` are CSV truth (`DATA-04`); the worklist *view* joins
  to them (§2) instead of copying them — one authority per fact, table stays narrow.

### 2. The worklist contract — a VIEW, not a second table (`AUTO-01`, `AUTO-02`, `IMG-02`)

A view can't drift from the control table (single authority). Claiming writes back
to the control table's lease columns.

```sql
-- STRAWMAN — do NOT apply (gate down)
CREATE VIEW BRONZE.MET_WORKLIST AS
SELECT c.object_id, c.enrichment_status, c.metadata_date, c.has_primary_image,
       o.is_public_domain, o.is_highlight, o.department
FROM   BRONZE.MET_ENRICHMENT_CONTROL c
JOIN   <descriptive source> o ON o.object_id = c.object_id      -- RAW/Silver CSV truth
WHERE  c.claimed_at IS NULL                                     -- not currently leased
  AND ( c.enrichment_status IN ('pending','error')             -- never done / retryable
        OR c.metadata_date > c.last_enriched_at                 -- upstream changed (IMG-03)
        OR c.has_primary_image IS NULL )                        -- never discovered
ORDER BY o.is_public_domain DESC, o.is_highlight DESC,          -- IMG-02 priority
         <department_priority>, c.object_id;
```

**Claim/drain = lease columns + atomic MERGE (not a Stream).**
The Mac reads a bounded slice, then claims it in one statement. Snowflake `UPDATE`
has no `LIMIT`, so the bounded candidate set rides in the `MERGE … USING` subquery:

```sql
-- STRAWMAN — do NOT apply (gate down)
MERGE INTO BRONZE.MET_ENRICHMENT_CONTROL t
USING ( SELECT object_id FROM BRONZE.MET_WORKLIST LIMIT :batch_n ) s
  ON t.object_id = s.object_id
WHEN MATCHED THEN UPDATE
  SET t.claimed_by_batch = :batch_id, t.claimed_at = CURRENT_TIMESTAMP;
```

**Why not a Stream:** Streams are CDC over *changes*, not a prioritized lease
queue; they can't express IMG-02 ordering or a TTL reclaim. With a single owner
(one Mac) lease contention is ~zero, so a lease column is both sufficient and the
correct tool. (A `CHANGES`/Stream would be the wrong abstraction here.)

### 3. The batch status-callback — one MERGE per batch (PIPE-05 cost rule, made testable)

After fetching N objects locally, the Mac lands a **small status delta** via the
existing PUT→COPY-into-staging path, then **one** MERGE updates status and clears
the lease. Image URLs themselves still flow through the existing
`COPY INTO RAW_MET_OBJECTS`; this callback is the *status* channel only.

```sql
-- STRAWMAN — do NOT apply (gate down). Status delta already staged as one file.
MERGE INTO BRONZE.MET_ENRICHMENT_CONTROL t
USING ( SELECT $1:object_id::NUMBER          AS object_id,
               $1:enrichment_status::STRING  AS enrichment_status,
               $1:last_enriched_at::TIMESTAMP_NTZ AS last_enriched_at,
               $1:has_primary_image::BOOLEAN AS has_primary_image
        FROM @<status_stage>/met/:batch_id/ ) s
  ON t.object_id = s.object_id
WHEN MATCHED THEN UPDATE SET
  t.enrichment_status = s.enrichment_status,
  t.last_enriched_at  = s.last_enriched_at,
  t.has_primary_image = s.has_primary_image,
  t.claimed_by_batch  = NULL,            -- release the lease
  t.claimed_at        = NULL;
```

**Hard guard (acceptance criterion, not prose):**
*Snowflake round-trips per batch = **O(1)**, never O(N).* No `executemany` row-by-row
status writes; the callback is always a set operation over the staged batch file.
This is the `PIPE-05` "never round-trip per object" rule made checkable.

### 4. Demotion delta — how today's SQLite state projects onto the control table (Part B)

Mapping the current `extraction/met/sql/schema.sql` `met_artworks` state model
(and `image_enricher.py` / `snowflake_uploader.py` behavior) onto the strawman:

| SQLite `met_artworks` state today | Disposition under `PIPE-05` |
|---|---|
| `enrichment_status` (`pending\|done\|no_image\|error`) | **PROMOTED** → control table is system of record (enum carried verbatim). |
| `enriched_at` | **PROMOTED** → `last_enriched_at`. |
| `metadata_date` (CSV-sourced) | **PROMOTED** (also stays as fetch scratch). |
| derived "payload had `primaryImage`" | **PROMOTED** → `has_primary_image` BOOLEAN. |
| `enrichment_error` (full text, `[:500]`) | **DEMOTED** to disposable scratch; only the *fact* (`status='error'`) reports up. |
| `primary_image_url / _small_url / additional_image_urls` | **DATA, not state** → land in `RAW_MET_OBJECTS` via COPY; never control state. |
| 47 CSV descriptive columns | **DATA** → fetch scratch + Bronze; never control state. |
| `bronze_batch_id` / `bronze_uploaded_at` | **DEMOTED** to in-run idempotency scratch (rebuildable from control table). |
| 500-row commit cadence, WAL pragmas, `idx_*` indexes | **STAYS** pure in-run scratch mechanics. |
| `extraction_runs` (SQLite) | **DEFER to Session 2** (`AUTO-03` run-history-in-Snowflake) — mentioned only. |
| lease (`claimed_by_batch`/`claimed_at`), `last_head_check_at`, `image_status` | **NET-NEW** — no SQLite equivalent today. |

**One-line framing:** SQLite keeps the heavy, rebuildable stuff (47 cols, URLs,
error text, in-run idempotency); Snowflake owns the thin decision/audit state; the
Mac→Snowflake wire carries only the per-batch status delta.

**What must be *reported up* in batch callbacks** (the only Mac→Snowflake state
flow): `{object_id, enrichment_status, last_enriched_at, has_primary_image}` for the
claimed batch — one MERGE (§3). Everything else is either local scratch or bulk data
on the existing COPY path.

**Demotion delta = net change vs. today:** SQLite stops being authoritative for
`enrichment_status`/`enriched_at`/upload-state across runs (it becomes a within-run
cache); those facts move to Snowflake; and three orchestration concepts (lease,
liveness, head-check timestamp) appear that have no SQLite home today.

---

## Session-2 review — code reconciliation & build-impact map (appended 2026-05-30)

> **DOCS-ONLY (gate down).** Full readability + optimization review of every
> `extraction/met/` Python module and its `sql/` files, reconciled against the
> Session-1 strawman. **Nothing flips to `decided`** — all positions are
> `exploring`, for owner sign-off at session end (which lifts the gate to open
> Session 3). Original question text in the register above is preserved verbatim;
> this block only appends.
>
> Rubric — Severity: `[H]` correctness/cost risk · `[M]` robustness/maintainability
> · `[L]` cosmetic. Class: `R` readability · `O` optimization.

### A. Per-module findings

**`run.py` (120 ln) — CLI dispatcher.** argparse front door for the 3 phases +
`status` + `all`; pure orchestration.
- `[M][R]` `main()` always returns `0`; failures surface only as raw tracebacks.
  A `try/except → log + return 1` would make `all`-chaining and future
  Task-invocation diagnosable.
- `[L][R]` `--no-refresh` exists for `bootstrap` but `all` hardcodes
  `refresh_csv=True` — can't run `all` against a cached CSV.
- `[L][R]` `_print_status` builds SQL via string concatenation; triple-quoted
  literals read better.
- *Build-impact:* `status` reads SQLite only; under `PIPE-05` it must learn to read
  `BRONZE.MET_ENRICHMENT_CONTROL` (new system of record) or it reports stale scratch.

**`config.py` (71 ln) — env-driven `Config` dataclass.**
- `[M][R]` stale comment l.53-54 ("infrastructure/V001-V007") — already gated.
- `[L][R]` **eager vs lazy inconsistency:** `Path` fields use `field(default_factory=…)`
  (lazy/per-instance) but scalar fields call `os.getenv(...)` in the class body
  (evaluated **once at import**). Harmless for a one-shot CLI; a footgun if imported
  as a library.
- *Build-impact:* Session 3 adds knobs — `MET_CONTROL_TABLE`, `MET_WORKLIST_VIEW`,
  `MET_CLAIM_BATCH` (lease size N), `MET_LEASE_TTL_MIN`, `MET_STATUS_STAGE`.

**`db.py` (43 ln) — SQL loader + SQLite connection.**
- `[M][O]` **PRAGMAs don't reach the working connections.** `synchronous=NORMAL`
  and `temp_store=MEMORY` are *connection-scoped* but live in `schema.sql`, run only
  by `initialize_database()`'s throwaway connection. Every `connect()` workload
  connection runs at default `synchronous=FULL`, silently forgoing the speed-up.
  (`journal_mode=WAL` is the exception — persistent on the file.) Fix: apply PRAGMAs
  in `connect()`.
- `[M][O]` no `busy_timeout`; a `PRAGMA busy_timeout=5000` hardens against transient
  `database is locked`.

**`csv_bootstrap.py` (223 ln) — CSV → SQLite UPSERT (Phase 1).**
- `[H][O]` **Deaccession blind spot (`DATA-01`).** UPSERT-only; a dropped object just
  vanishes from the next CSV and the stale row lives forever. Confirmed in
  `upsert_artwork.sql` (no DELETE path).
- `[H][O]` **Possible Git-LFS pointer download (`DATA-06`).** `MetObjects.csv` is Git
  LFS (~225 MB, verified). `raw.githubusercontent.com/.../master/MetObjects.csv`
  typically returns the **LFS pointer text** (~130 B), not the CSV. Given the client
  is "untested," this may never have loaded 471k rows. Needs validation in Session 3.
- `[M][O]` `download_csv` has no integrity guard (min-size/row-count assertion) —
  pairs with `DATA-06`; a pointer/truncated download "succeeds" silently.
- `[L][R]` two independent magic `5000`s (`bootstrap(batch_size=5000)` vs
  `config.upload_chunk_size`); `batch: list` untyped.

**`image_enricher.py` (280 ln) — async API fetch (the heart, Phase 2).**
- `[H][O]` **Eager task explosion over 471k rows.**
  `asyncio.gather(*(worker(oid) for oid in object_ids))` instantiates **all ~471k
  coroutines/Tasks up front**. The `Semaphore` bounds in-flight HTTP, but every Task
  object + future + materialized arg tuple coexists → hundreds of MB scheduler
  overhead + slow startup stall. Drain in bounded slices (queue, or `gather`
  per chunk). This is the "memory over ~471k rows" risk.
- `[M][O]` single `write_lock` funnels every SQLite write through one coroutine,
  commit every 500 — correct, fine while API-bound at 20 rps; only matters once the
  eager-gather is fixed and throughput rises.
- `[M][R]` `_fetch_one` returns a 4-tuple consumed positionally (`result[1]`); a
  `NamedTuple`/dataclass would remove positional fragility.
- `[L][R]` two inline SQL constants (`UPDATE_NO_IMAGE_SQL`, `UPDATE_ERROR_SQL`) break
  the "SQL lives in files" ethos (documented exception, but asymmetric).
- `[L][O]` backoff `2**attempt` (2,4,8,16,32, cap 60) sound; 404 / missing
  `primaryImage` → `no_image` correct.
- *Build-impact (largest):* enrich is currently **Snowflake-free** (worklist from
  SQLite `_pending_object_ids()`). The strawman drives it from `MET_WORKLIST` via a
  lease-MERGE claim → enrich must open a Snowflake connection, OR a separate `claim`
  command materializes a local worklist. See `PIPE-06`.

**`snowflake_uploader.py` (289 ln) — NDJSON → PUT → COPY INTO Bronze (Phase 3).**
- `[M][O]` **Non-idempotent crash window → duplicate Bronze rows.** Death *after*
  COPY succeeds but *before* `_mark_uploaded` → next run re-selects (SQLite unmarked),
  re-PUTs (prior file `PURGE`d), re-COPYs → duplicates. COPY load-metadata can't dedup
  (PURGE removed the file). Bronze is append-only VARIANT, so dedup must happen in
  Silver — flag explicitly.
- `[L][R]` chunk-flush logic duplicated (loop body + final partial); extract
  `_flush_chunk()`.
- `[L][O]` PUT-then-COPY serial per chunk; could PUT several into the batch dir then
  one COPY over the prefix. Minor; per-chunk unit keeps idempotency simple.
- `[L][O]` `rows_loaded` parsed by positional index 3 of the COPY result — brittle if
  connector column order shifts; named access safer.
- *Build-impact:* already owns the Snowflake connection + PUT/COPY — natural home for
  the **batch status-callback MERGE** (strawman §3). Today marks SQLite only; Session 3
  adds the staged status-delta + one MERGE into `MET_ENRICHMENT_CONTROL`.

**SQL files.** `schema.sql` — PRAGMA placement (see `db.py`); demoted to scratch under
`PIPE-05`. `upsert_artwork.sql` — confirms `DATA-01` (no DELETE/tombstone).
`update_enrichment_done.sql` — clean. `copy_into_bronze.sql` — `[L/M]` `str.format`
templating of `{table}/{stage}/{batch_id}/{filename}`; inputs internally generated
(uuid/timestamp) so injection risk low, and COPY can't bind identifiers as params
anyway — deserves a "trusted inputs" comment. `STRIP_OUTER_ARRAY=FALSE` correct.

### B. Build-impact map (strawman element → Session-3 change)

| Strawman element | Added / moved / disposable | Session-3 work | Correction surfaced |
|---|---|---|---|
| `MET_ENRICHMENT_CONTROL` (`DDL-04`) | **NEW** Snowflake table; SQLite status/enriched_at → in-run scratch | DDL + a **seed path** to populate ~471k pending rows | **Under-specified:** strawman never says *how* control is initially seeded (bootstrap seed-COPY vs derive from `RAW_MET_OBJECTS`). → `DDL-04` note. |
| `MET_WORKLIST` view (`AUTO-01/02`, `IMG-02`) | **NEW** view; replaces `_pending_object_ids()` | DDL; resolve `<descriptive source>` + `<department_priority>` | **Real tension:** view joins control → descriptive truth for `is_public_domain/is_highlight/department`, but **no Silver table exists yet** — only `BRONZE.raw_met_objects` (VARIANT). Fork: (a) join to VARIANT extractions, or (b) relax "narrow" rule and carry the 3 priority flags *in* control. → `DDL-04` note. |
| Lease-MERGE claim | **NEW** Python in enrich path | `MERGE … USING (SELECT … FROM MET_WORKLIST LIMIT :n)` sets lease | **Architectural:** enrich is Snowflake-free today; claiming forces a Snowflake connection into Phase 2 (or a separate `claim` cmd). → new `PIPE-06`. |
| Batch status-callback | **NEW** Python in uploader (or sibling) | stage per-batch delta → **one** MERGE; clear lease | O(1)/batch guard is the acceptance test — no per-row status `executemany`. |
| Demotion delta | SQLite → in-run cache | `status` reads control; resumability becomes control-driven | `bronze_batch_id/bronze_uploaded_at` become idempotency scratch, rebuildable from control. |
| Run history (`AUTO-03`) | deferred design | land each phase `running→success/failed`+counts into `BRONZE.extraction_log` (today written nowhere) | design only this session; build deferred to Session 3. |

### C. Dead-code decisions (gated — do NOT apply)

- **`rename_and_update.py` (91 ln) → REMOVE.** Spent one-shot `git mv` migration; tree
  is already prefix-free, so it's dead, and it's a dense source of stale `V###/R###`
  strings that pollute future greps. Git history preserves it. Gated.
- **Loader service-user auth → KEY-PAIR: APPLIED (code) 2026-05-31.** See `AUTH-01`
  (now flipped). The empty `git-setup/operator/rotate_loader_password.sql` + its
  `06_rotate_loader_password.sh` are **deleted**; replaced by
  `06_setup_loader_keypair.sh` + `operator/register_loader_public_key.sql`.
  Committed on `donkey-kong-sandbox`; **owner still needs to run `make iac` +
  `setup.sh --phase loader`** to apply to the account.

### Deferred to Session 3 (noted, not solved here)

The actual build (apply DDL → Python); `DDL-02` clustering (premature pre-volume);
`PIPE-02` IaC-vs-operational placement; `AUTO-03` `extraction_log` implementation
(design-only here).

---

## Session-2b setup — DDL scope correction + `MET_CSV_SNAPSHOT` decision (appended 2026-05-30)

> **DOCS-ONLY (gate down).** Owner-flagged scope correction. Nothing newly `decided`;
> Option A below is **owner-preferred + gated**, flips to `decided` only at sign-off.

**Scope correction.** Session 2 (per its prompt) reviewed Python + `extraction/met/sql/`
only; the `infrastructure/*` DDL was carried as `trusted-prior` and **not re-read this
arc**. Reconciling a control-table/worklist design without reading the Bronze DDL it
sits beside was a gap. The owner inserted **Session 2b** = a dedicated review of the
**full `infrastructure/` DDL set**. Revised arc: **S1 (Python strawman) → S2 (Python
review) → S2b (DDL review) → S3 (build)**.

**Findings from `infrastructure/create_bronze_tables.sql`** (owner-supplied, read 2026-05-30):
- `[H]` **No descriptive data in Snowflake for *pending* rows.** `raw_met_objects` is
  VARIANT-only and is populated **only by the uploader, only for `done` rows** (CSV
  descriptive block rides inside `raw_payload:csv.*`). The 47 CSV fields for *pending*
  objects live only in local SQLite. So `MET_WORKLIST` cannot prioritize the work it
  hasn't done yet — it has no `is_public_domain/is_highlight/department` to sort on.
  This is the concrete root of `DDL-04` under-spec (ii). → resolved via `DDL-05`.
- `[correction]` **`extraction_log` already exists** (see `AUTO-03`) — no DDL needed,
  only the Python write path.
- `[build note]` `raw_met_objects` defaults (`_extracted_at`, `_source_system`) match
  the uploader's `COPY INTO (object_id, raw_payload, _batch_id)` — that contract is
  fine; the genuinely-new objects are `MET_ENRICHMENT_CONTROL` + `MET_WORKLIST`
  (+ `MET_CSV_SNAPSHOT`), which will also need **grants** (loader: SELECT/MERGE;
  created by `ARTWORK_ADMIN` like the rest of `create_bronze_tables.sql`).

**Decision (owner-preferred, gated) — Option A: `BRONZE.MET_CSV_SNAPSHOT`.** Land the
full Met CSV into Snowflake at bootstrap (VARIANT raw-blob default), independent of
enrichment, so the worklist can prioritize pending rows and deaccession can be
detected. Full entry: `DDL-05`. Discipline carried into `engineering-playbook.md`:
**land the whole raw row in Bronze (sparse columns ~free as VARIANT), promote
selectively in Silver; keep `*_ulan_url`/`*_wikidata_url` for entity normalization.**
Note this does **not** relitigate `PIPE-03` — the Mac↔Snowflake *contract surface*
stays two tables; `MET_CSV_SNAPSHOT` is a Snowflake-internal feeder behind the
worklist view.

---

## Session-2b DDL review — full infrastructure/ reconciliation (appended 2026-05-31)

> **DOCS-ONLY (gate down).** Systematic review of all 19 `infrastructure/` files
> (10 forward + 9 drop/rollback) against the Session-1 strawman + `DDL-05` +
> `DDL-04`. Rubric: `[H]` correctness/cost · `[M]` robustness/maint · `[L]`
> cosmetic. Class: `R` readability · `O` optimization · `X` reconciliation.
> Nothing flips to `decided`; reconciliation verdicts and the build-impact map
> are positions for owner sign-off at session end.

### A. Per-file review (key findings; files with nothing notable omitted)

| File | Verdict vs strawman | Key findings |
|---|---|---|
| `create_roles.sql` (46 ln) | **forces-a-change** | `EXECUTE TASK ON ACCOUNT` (l.45, commented) must uncomment in lockstep with real tasks in `create_tasks.sql`. Already self-documented. |
| `create_warehouses.sql` (15 ln) | matches | ARTWORK_WH X-Small sufficient; new objects don't need a new warehouse. |
| `create_databases_and_schemas.sql` (21 ln) | matches | All new objects land in existing BRONZE schema. |
| `create_file_formats.sql` (22 ln) | matches | VARIANT-blob design means `json_raw` (existing) covers `MET_CSV_SNAPSHOT` loading (NDJSON path). No new format needed. |
| `create_stages.sql` (14 ln) | **forces-a-change (resolved: no DDL)** | Strawman §3 references a status stage for batch callbacks. **Position:** reuse `bronze_load_stage` with a `/status/met/` path prefix — no new stage DDL needed; LOADER already has R/W. `[L][R]` trailing whitespace l.14. |
| `grant_privileges.sql` (45 ln) | **forces-a-change (additive)** | `[M][X]` LOADER has full CRUD on ALL+FUTURE **TABLES** in BRONZE (covers `MET_ENRICHMENT_CONTROL` + `MET_CSV_SNAPSHOT`). But **no VIEW grants in BRONZE** — `MET_WORKLIST` (VIEW) is unreadable by LOADER. Session 3 must add: `GRANT SELECT ON ALL VIEWS IN SCHEMA ARTWORK_DB.BRONZE TO ROLE ARTWORK_LOADER;` + `GRANT SELECT ON FUTURE VIEWS IN SCHEMA ARTWORK_DB.BRONZE TO ROLE ARTWORK_LOADER;`. |
| `create_bronze_tables.sql` (85 ln) | **missing — new objects** | Natural home for `MET_ENRICHMENT_CONTROL` + `MET_CSV_SNAPSHOT` (both tables, same pattern as existing 6 raw_* tables). `MET_WORKLIST` (VIEW) recommended for a separate file. `[H][X]` `raw_met_objects` has no PK — intentional (append-only Bronze log; control is the PK authority). `[M][X]` No `CHANGE_TRACKING` — needed later for DT/stream Track 2/3 work, not for the strawman. |
| `create_service_user.sql` (31 ln) | matches | Key-pair migration (`AUTH-01`) is orthogonal; placeholder pw + rotation comment intact. |
| `create_tasks.sql` (7 ln) | **forces-a-change (fill placeholder)** | Lease-reclaim housekeeping task lives here. Reclaim predicate: `claimed_at < DATEADD(minute, -:ttl, CURRENT_TIMESTAMP())` → NULL both lease cols. In lockstep: uncomment `EXECUTE TASK` in `create_roles.sql`; fill `drop_tasks.sql`. |
| `refresh_grants.sql` (23 ln) | **forces-a-change (minor)** | Add `GRANT SELECT ON ALL VIEWS IN SCHEMA ARTWORK_DB.BRONZE TO ROLE ARTWORK_LOADER;` to mirror `grant_privileges.sql` addition. |
| `drop_bronze_tables.sql` (43 ln) | **missing** | Add `DROP TABLE IF EXISTS ARTWORK_DB.BRONZE.MET_ENRICHMENT_CONTROL;` + `DROP TABLE IF EXISTS ARTWORK_DB.BRONZE.MET_CSV_SNAPSHOT;`. |
| `drop_tasks.sql` (47 ln) | **forces-a-change** | Replace placeholder SELECT with `DROP TASK IF EXISTS ARTWORK_DB.BRONZE.<lease_reclaim_task>;`. |
| `drop_roles.sql` (42 ln) | matches (stale V### ref l.9 already flagged) | No reconciliation impact. |
| `drop_grants.sql` (40 ln) | matches (stale V###/B002 refs already flagged) | No reconciliation impact. |
| All other drops | matches | New objects cascade through existing `drop_databases_and_schemas.sql`; fine-grained drops need the additions above. |

### B. DDL build-impact map for Session 3

| New object | Type | Created by | Owner | Manifest position | LOADER grant | Rollback |
|---|---|---|---|---|---|---|
| `BRONZE.MET_ENRICHMENT_CONTROL` | TABLE | append `create_bronze_tables.sql` | ARTWORK_ADMIN | step 7 (existing) | S/I/U/D already covered (ALL+FUTURE TABLES) | append `drop_bronze_tables.sql` |
| `BRONZE.MET_CSV_SNAPSHOT` | TABLE | append `create_bronze_tables.sql` | ARTWORK_ADMIN | step 7 (existing) | S/I/U/D already covered (ALL+FUTURE TABLES) | append `drop_bronze_tables.sql` |
| `BRONZE.MET_WORKLIST` | VIEW | **new file** `create_bronze_views.sql` | ARTWORK_ADMIN | **insert after step 7** (new manifest entry) | **NEW grant:** SELECT ON ALL+FUTURE VIEWS in BRONZE (add to `grant_privileges.sql` + `refresh_grants.sql`) | **new file** `drop_bronze_views.sql` |
| Lease-reclaim TASK (e.g. `MET_LEASE_RECLAIM_TASK`) | TASK | fill `create_tasks.sql` | ARTWORK_ADMIN | step 9 (existing) | none (runs AS admin, inherits LOADER) | fill `drop_tasks.sql` |
| `EXECUTE TASK ON ACCOUNT` | ACCOUNT GRANT | uncomment l.45 `create_roles.sql` | ACCOUNTADMIN | step 1 (existing) | N/A (revokes on DROP ROLE) | auto |

**Positions (Session-3 design choices, not decisions):**

1. **View in its own file** (recommended) — clean object-class split; manifest slot
   controls dependency order; drop pair stays symmetric.
2. **Reuse `bronze_load_stage`** with `/status/met/` path prefix — zero new DDL for
   the batch-callback channel. LOADER already has READ/WRITE.
3. **Loading format for `MET_CSV_SNAPSHOT`** — NDJSON (Python maps CSV→JSON rows,
   PUT, COPY with `json_raw`). Keeps the loading path uniform with `raw_met_objects`.
   No new file format.
4. **Control-table seed path** — operational INSERT (Python bootstrap), not DDL.
   `INSERT INTO MET_ENRICHMENT_CONTROL (object_id, metadata_date) SELECT … FROM
   MET_CSV_SNAPSHOT`. Runs at first bootstrap; idempotent (PK conflict = skip).
5. **Lease-reclaim task warehouse** — `ARTWORK_WH` (existing X-Small). ~471k row
   scan with a simple date predicate = O(seconds). No scaling needed.
6. **Task schedule** — position: `SCHEDULE = 'USING CRON 0 * * * * UTC'` (hourly) or
   a short-interval `SCHEDULE = '5 MINUTE'` for development. Owner decides at build.
7. **Manifest ordering** — `create_bronze_views.sql` must come AFTER `create_bronze_tables.sql`
   AND after `grant_privileges.sql` (the view needs SELECT on both tables; grants
   must already exist). Current order: `grant_privileges.sql` is step 6,
   `create_bronze_tables.sql` is step 7. Slot the view at **step 7.5** (between
   `create_bronze_tables.sql` and `create_service_user.sql`).

### C. Collision check: gated "Approved decisions" vs new objects

All four gated decisions in `ddl-infrastructure.md` are **orthogonal** to the new
control/snapshot/worklist objects:

| Gated decision | Collision? | Note |
|---|---|---|
| 1. Idempotency policy (IF NOT EXISTS / OR REPLACE) | **None** | New tables use IF NOT EXISTS; view uses OR REPLACE — conforms naturally. |
| 2. UPPERCASE identifiers | **None** | New names already UPPERCASE. The `raw_met_objects` → `RAW_MET_OBJECTS` rename is cosmetic (unquoted = CI); view JOIN refs work either way. Best practice: apply rename first, then write view with uppercased refs. |
| 3. Rename `grant_privileges.sql` → `create_grants.sql` | **None** | The new VIEW grant lines go in whichever name the file has at edit time. Manifest + paired-drop wiring is independent. |
| 4. Reword stale V/R/B refs | **None** | Comment-only; new objects introduce no V/R/B references. |

**Recommended Session-3 order:** apply gated cosmetic fixes first (they're self-contained),
then add new objects. This avoids referencing about-to-be-renamed identifiers.

**Independent re-verification (2026-05-31, second window).** The four load-bearing
claims were re-read against source this window before drafting the Session-3 prompt:
(1) `grant_privileges.sql:17-23` — LOADER has TABLES+STAGES in BRONZE, **no VIEW
grant** → gap confirmed; (2) `create_bronze_tables.sql` — 7 tables, VARIANT, `IF NOT
EXISTS`, runs as `ARTWORK_ADMIN`, `extraction_log` present (AUTO-03 "no DDL" holds),
`raw_met_objects` has no PK → confirmed; (3) `create_tasks.sql:6` — bare-SELECT
placeholder → confirmed; (4) `create_roles.sql:45` — `EXECUTE TASK ON ACCOUNT`
commented with explicit lockstep note → confirmed. Coverage corrected to **19 files
(9 drops, not 8)** — per-file table already covered all 19. Review stands; build-impact
map is sound input to the Session-3 prompt.

### Deferred to Session 3 (noted here, not solved)

- The build itself (DDL + Python).
- `DDL-02` clustering (premature pre-volume).
- `DATA-01` deaccession build (needs `MET_CSV_SNAPSHOT` to exist first; Session 3
  designs the diff query but may defer the automated pipeline).
- `AUTO-03` extraction_log Python write (table exists — only Python changes).
- `MET_CSV_SNAPSHOT` VARIANT-vs-typed fork: VARIANT (owner-preferred default;
  max flexibility, zero schema maintenance) vs typed columns (queryable without
  `::` casting, but schema-drift-sensitive). **Recommendation: VARIANT.** The view
  or Silver can expose typed extractions.
- Whether to apply the gated "Approved decisions" inside Session 3 or as a
  separate pre-patch.

## Session-3 reconciliation (2026-05-31)

**Dual-instance incident.** Connection drops spawned overlapping Cortex windows; the
staged `donkey-kong-sandbox` tree was authored across two ghost clusters (00:51–00:52
and 01:04–01:07 GMT) with no review trail in the surviving chat. A resuming window
ran a read-only **provenance + reconciliation audit** + an owner-authorized **mirror
diff** (committed baseline `2e957708`). Durable step trail:
`docs/context/session-3-progress-log.md`.

**Audit outcome — CLEAN (zero off-spec).** Staged DDL implements the Session-2b
build-impact map + the four cosmetic decisions exactly: `MET_ENRICHMENT_CONTROL`
(DDL-04 strawman, 9 cols + PK), `MET_CSV_SNAPSHOT` (DDL-05 Option A, VARIANT raw blob
— matches owner-preferred VARIANT default), `MET_WORKLIST` (new `create_bronze_views.sql`;
DDL-04 fork (a) resolved → joins control × CSV-snapshot, IMG-02 priority, lease-aware),
paired drops, `MET_LEASE_RECLAIM_TASK` (PIPE-06 lease housekeeping), grant gap fixed,
rename + UPPERCASE + idempotency split applied, `EXECUTE TASK` uncommented +
`bootstrap.py` contract in lockstep (preflight self-consistent). Mirror diff confirmed
independently (file-set + size deltas all expected; rename + 2 views genuinely
uncommitted).

**IaC verdict:** structure reproducible after audit; working pipeline not until
Section C. Section-C gaps unchanged and still owner-gated: data seed (control +
`MET_CSV_SNAPSHOT` land EMPTY — needs the CSV-snapshot land + control seed Python),
`AUTH-01` (key-pair), `DATA-06` (CSV download integrity guard), dead-code
`rename_and_update.py` removal, `AUTO-03` extraction_log writes, `PIPE-06`
lease-claim MERGE.

**Mentor-flag (Section C, not a DDL blocker):** the PK/uniqueness + snapshot-fan-out
resolution is in the APPLIED block below. Additional still-open caveat: the view-level
`ORDER BY` in `MET_WORKLIST` may not survive an outer `LIMIT` — the Mac's drain query must
carry its own `ORDER BY`.

**APPLIED — 2026-05-31 (owner sign-off + execution).** Owner committed Phase 1 (18
reconciled files) and ran `make infra` on their Mac; all 11 manifest scripts applied
clean + idempotent. New objects live in `ARTWORK_DB.BRONZE`: `MET_ENRICHMENT_CONTROL`,
`MET_CSV_SNAPSHOT`, `MET_WORKLIST` (view), `MET_LEASE_RECLAIM_TASK` (resumed). Register
flips (owner-authorized, dated 2026-05-31): **`DDL-04` (control table + worklist) →
applied; `DDL-05` (`MET_CSV_SNAPSHOT`, Option A VARIANT) → applied; PIPE-06 lease
housekeeping task → applied (the lease-CLAIM MERGE itself is Section C).** The four
cosmetic decisions (idempotency split, UPPERCASE, `grant_privileges→create_grants`
rename, V/R/B reword) → applied. **Mentor-flag correction:** the applied DDL declares
`pk_met_csv_snapshot` / `pk_met_enrichment_control` PRIMARY KEYs (uniqueness intent
declared; runtime 1:1 still rides on the MERGE load — Section C). **Dual-instance
incident:** two concurrent Cortex instances wrote to the shared docs/log this arc; owner
confirmed one living session, this window authoritative (full trail +
restart-resumption contract in `session-3-progress-log.md`). **Still open / Section C
(next session):** data seed (control + `MET_CSV_SNAPSHOT` empty), `AUTH-01` key-pair,
`DATA-01`/`DATA-06`, `AUTO-03` extraction_log writes, `PIPE-06` lease-claim MERGE,
`rename_and_update.py` removal.

---

## Cross-references

- Patterns behind these decisions: `engineering-playbook.md` (Track 2 ingestion,
  Track 3 Bronze/Silver/Gold, medallion delete-propagation).
- Existing pipeline mechanics & gaps: `extraction.md`.
- IaC objects these decisions touch (do NOT edit under current gating):
  `ddl-infrastructure.md`.
