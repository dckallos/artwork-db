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
| `IMG-04` | exploring | How do we validate that *current* image URLs are still valid? | Decouple from discovery: a cheap `HEAD` against `images.metmuseum.org` (CDN, **not** rate-limited) confirms liveness without API pressure. Re-discover via API only when a HEAD fails or `metadataDate` moved. |
| `IMG-05` | open | What rate-limit / backoff policy — given the prior 24h ordeal? | Met allows **80 rps** (verified); extractor defaults to a polite 20 rps with token-bucket + jittered backoff (already sound). Lever: raise rps for backfills, stay polite for steady-state. The old ordeal was a more naive tool. |
| `IMG-06` | open | How do we make image enrichment "automated from Snowflake" when fetching is cheapest locally? | Resolved in principle by the worklist split (`AUTO-02`): Snowflake schedules/decides *what*; the Mac fetches. Fully Snowflake-native fetch (External Access + UDF) is possible but costs warehouse credits — see `COST-02`. |
| `IMG-07` | open | **(Mentor-flagged.)** Do we store just the image *URL*, or archive the image *bytes*? | URLs rot; for an Etsy profit motive, link rot is an existential risk to inventory. Option: archive high-res bytes for the `isPublicDomain ∧ primaryImage` subset into a Snowflake stage / object storage so "sellable inventory" survives upstream URL churn. Tradeoff: meaningful storage + egress cost (`COST-04`) vs. durability of the crown-jewel asset. Scope it to the *sellable* subset, not all 471k. Ties `LEG-02`, `IMG-04`. |

### PIPE — execution locus / architecture

| ID | Status | Question | Notes / position |
|---|---|---|---|
| `PIPE-01` | exploring | Keep the Python local on the Mac, or move to a Snowflake-native architecture? | Keep fetching local. Enrich is ~6.5h of *waiting on the API*; a warehouse would bill to sit idle. Local compute = $0. Snowflake owns storage + transforms + worklist decisions. |
| `PIPE-02` | open | How do local Python + the SQL scripts reconcile with the `infrastructure/` DDL? | Runtime ETL (`extraction/met/*`) *consumes* IaC objects (Workflow 2); it is not IaC. The SQL it runs is operational (COPY/UPSERT), separate from the versioned DDL. Keep that boundary explicit. |
| `PIPE-03` | open | What's the hybrid division of labor — Mac vs Snowflake? | Mac: CSV download, SQLite staging, API fetch, NDJSON build, PUT. Snowflake: COPY, Bronze/Silver/Gold transforms, worklist computation, scheduling. |
| `PIPE-04` | open | You flagged the SQL scripts as "untested." How do we trust them before they touch DDL? | Two layers: compile-validate operational SQL (`snow sql` / compile-only) in a preflight; and once dbt lands, the Silver/Gold transforms get dbt tests. This is a genuine gap, not yet covered. |
| `PIPE-05` | open | **(Mentor-flagged — the hinge.)** Where does enrichment *state* live: local SQLite or a Snowflake control table? | Today `enrichment_status` / `bronze_uploaded_at` live in local SQLite. "Automate from Snowflake" pulls the worklist + state toward a Bronze control table (so a Task can compute what needs work and audit progress). Fork: (a) keep SQLite as the only state, Snowflake just receives uploads — simplest, but Snowflake can't *decide* work; (b) mirror state into a Snowflake control table the Mac drains (`AUTO-02`) — enables scheduling/observability at the cost of a sync contract. Most of the pipeline questions rotate on this. Ties `AUTO-01/02/03`, `PIPE-01`. |

### DATA — Met data semantics / quality

| ID | Status | Question | Notes / position |
|---|---|---|---|
| `DATA-01` | open | **(Owner did not raise — mentor-flagged, high value.)** The CSV is a full snapshot; bootstrap is UPSERT-only. When the Met deaccessions a work it just vanishes from the next CSV — nothing deletes the stale row. How do we propagate removal? | Snapshot-diff: compare the new CSV `object_id` set vs. existing; tombstone the missing rows so removal flows Bronze→Silver→Gold and drops from sellable Gold fast. Directly serves AGENTS.md "timeliness/deaccession" + "delete propagation" cornerstones. Strong learning fork — pairs with `DDL-02`. |
| `DATA-02` | open | How do we detect/handle CSV schema drift (columns added, renamed, removed)? | 47 columns are mapped 1:1 today. Need a column-contract check at bootstrap so a silent header change doesn't corrupt the load. |
| `DATA-03` | exploring | How do we use `Metadata Date` to drive incremental work? | CSV `Metadata Date` + API `metadataDate` deltas together identify the minimal re-enrich set. Pairs with `IMG-03`. |
| `DATA-04` | exploring | "Most of the data" is in the CSV — what's authoritative where? | CSV = descriptive truth (continuously updated upstream). API = image URLs only. Model accordingly: CSV-sourced columns vs. API-sourced image block. |
| `DATA-05` | open | **(Mentor-flagged.)** Do CSV re-pull and image re-validation share a cadence, or differ? | You noted image URLs change rarely. So tier the cadences: (a) CSV re-pull — frequent (descriptive truth + deaccession signal, `DATA-01`); (b) image *discovery* — driven by `metadataDate` deltas + null-image backfill (`IMG-03`); (c) image *liveness* `HEAD` re-check — slow background sweep (`IMG-04`), since CDN URLs are stable. Avoids paying full-enrichment cost on every refresh. Ties `AUTO-01`, `IMG-04`. |

### DDL — schema design

| ID | Status | Question | Notes / position |
|---|---|---|---|
| `DDL-01` | open | Which DDL decisions are we already prepared to make now? | Few, honestly — most should wait until a Silver table is large enough that pruning/clustering *matters* (avoid premature optimization). Capture candidates here as they surface; don't pre-commit. |
| `DDL-02` | open | Clustering so deaccession/delete prunes cheaply? | Tie to `DATA-01`: choose a clustering key so tombstoned/affected rows cluster together and delete cheaply. Only worth designing once data volume justifies it. |
| `DDL-03` | open | How do we model images as a first-class high-value column across Bronze→Silver→Gold? | Bronze keeps the raw API block; Silver conforms to `primary_image_url` + flags; Gold exposes the sellable, validated subset. Ties `LEG-02`, `IMG-04`, `IMG-07`. |

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
| `AUTO-01` | open | Can Snowflake Tasks/Streams *schedule detection* of stale/missing images? | Yes — a scheduled Task can compute "needs discovery or revalidation" (null image ∨ `metadataDate` advanced ∨ last-checked age exceeded) into a worklist table. (Note: `infrastructure/create_tasks.sql` is currently a placeholder.) |
| `AUTO-02` | exploring | **Worklist pattern** to reconcile "automate from Snowflake" with "fetch cheaply on the Mac." | Snowflake (Task) writes a prioritized worklist table → the Mac polls/drains it, fetches, and uploads results → Snowflake marks them done. Snowflake decides *what*; the Mac does the *fetch*. Resolves the `PIPE-01`/`PIPE-05`/`IMG-06` tension at minimal cost. |
| `AUTO-03` | open | **(Mentor-flagged.)** How do we get run history into Snowflake so automation is auditable? | Today `extraction_runs` lives only in SQLite and the Bronze `extraction_log` table is never written (per `extraction.md`). For Snowflake-driven scheduling we need run/phase history *in* Snowflake — land each phase's `running→success/failed` + counts into `BRONZE.extraction_log` so Tasks and dashboards can see it. Ties `AUTO-01`, `PIPE-05`. |

---

## Cross-references

- Patterns behind these decisions: `engineering-playbook.md` (Track 2 ingestion,
  Track 3 Bronze/Silver/Gold, medallion delete-propagation).
- Existing pipeline mechanics & gaps: `extraction.md`.
- IaC objects these decisions touch (do NOT edit under current gating):
  `ddl-infrastructure.md`.
