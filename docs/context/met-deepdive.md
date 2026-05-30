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
  only for works where **`isPublicDomain = true`**. CSV is distributed via Git LFS.
  (https://github.com/metmuseum/openaccess, https://www.metmuseum.org/hubs/open-access)
- **Collection API base:** `https://collectionapi.metmuseum.org/public/collection/v1`.
  Requested rate limit **80 req/sec**, no key required.
  (https://metmuseum.github.io/, https://publicapi.dev/metropolitan-museum-of-art-api)
- **Change detection:** `GET /objects?metadataDate=YYYY-MM-DD` returns the
  `objectIDs` whose metadata was updated after that date — the incremental driver.
  (https://metmuseum.github.io/, https://make.wordpress.org/openverse/handbook/openverse-catalog/provider-api-met-museum/)
- **Image host is separate from the API:** `primaryImage` / `primaryImageSmall` /
  `additionalImages` URLs live on **`images.metmuseum.org`** (a CDN), NOT on the
  rate-limited `collectionapi.metmuseum.org`. So liveness checks (`HEAD`) need not
  touch the rate-limited API. (https://metmuseum.github.io/)
- **CSV vs API split:** the CSV carries ~47 descriptive columns incl.
  `Is Public Domain`, `Is Highlight`, `Metadata Date`; it does **not** carry image
  URLs. Image URLs come only from the API `/objects/{id}` call.

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
| `IMG-05` | open | What rate-limit / backoff policy — given the prior 24h ordeal? | Met allows 80 rps; extractor defaults to a polite 20 rps with token-bucket + jittered backoff (already sound). Lever: raise rps for backfills, stay polite for steady-state. The old ordeal was a more naive tool. |
| `IMG-06` | open | How do we make image enrichment "automated from Snowflake" when fetching is cheapest locally? | Resolved in principle by the worklist split (`AUTO-02`): Snowflake schedules/decides *what*; the Mac fetches. Fully Snowflake-native fetch (External Access + UDF) is possible but costs warehouse credits — see `COST-02`. |

### PIPE — execution locus / architecture

| ID | Status | Question | Notes / position |
|---|---|---|---|
| `PIPE-01` | exploring | Keep the Python local on the Mac, or move to a Snowflake-native architecture? | Keep fetching local. Enrich is ~6.5h of *waiting on the API*; a warehouse would bill to sit idle. Local compute = $0. Snowflake owns storage + transforms + worklist decisions. |
| `PIPE-02` | open | How do local Python + the SQL scripts reconcile with the `infrastructure/` DDL? | Runtime ETL (`extraction/met/*`) *consumes* IaC objects (Workflow 2); it is not IaC. The SQL it runs is operational (COPY/UPSERT), separate from the versioned DDL. Keep that boundary explicit. |
| `PIPE-03` | open | What's the hybrid division of labor — Mac vs Snowflake? | Mac: CSV download, SQLite staging, API fetch, NDJSON build, PUT. Snowflake: COPY, Bronze/Silver/Gold transforms, worklist computation, scheduling. |
| `PIPE-04` | open | You flagged the SQL scripts as "untested." How do we trust them before they touch DDL? | Two layers: compile-validate operational SQL (`snow sql` / compile-only) in a preflight; and once dbt lands, the Silver/Gold transforms get dbt tests. This is a genuine gap, not yet covered. |

### DATA — Met data semantics / quality

| ID | Status | Question | Notes / position |
|---|---|---|---|
| `DATA-01` | open | **(Owner did not raise — mentor-flagged, high value.)** The CSV is a full snapshot; bootstrap is UPSERT-only. When the Met deaccessions a work it just vanishes from the next CSV — nothing deletes the stale row. How do we propagate removal? | Snapshot-diff: compare the new CSV `object_id` set vs. existing; tombstone the missing rows so removal flows Bronze→Silver→Gold and drops from sellable Gold fast. Directly serves AGENTS.md "timeliness/deaccession" + "delete propagation" cornerstones. Strong learning fork — pairs with `DDL-02`. |
| `DATA-02` | open | How do we detect/handle CSV schema drift (columns added, renamed, removed)? | 47 columns are mapped 1:1 today. Need a column-contract check at bootstrap so a silent header change doesn't corrupt the load. |
| `DATA-03` | exploring | How do we use `Metadata Date` to drive incremental work? | CSV `Metadata Date` + API `metadataDate` deltas together identify the minimal re-enrich set. Pairs with `IMG-03`. |
| `DATA-04` | exploring | "Most of the data" is in the CSV — what's authoritative where? | CSV = descriptive truth (continuously updated upstream). API = image URLs only. Model accordingly: CSV-sourced columns vs. API-sourced image block. |

### DDL — schema design

| ID | Status | Question | Notes / position |
|---|---|---|---|
| `DDL-01` | open | Which DDL decisions are we already prepared to make now? | Few, honestly — most should wait until a Silver table is large enough that pruning/clustering *matters* (avoid premature optimization). Capture candidates here as they surface; don't pre-commit. |
| `DDL-02` | open | Clustering so deaccession/delete prunes cheaply? | Tie to `DATA-01`: choose a clustering key so tombstoned/affected rows cluster together and delete cheaply. Only worth designing once data volume justifies it. |
| `DDL-03` | open | How do we model images as a first-class high-value column across Bronze→Silver→Gold? | Bronze keeps the raw API block; Silver conforms to `primary_image_url` + flags; Gold exposes the sellable, validated subset. Ties `LEG-02`, `IMG-04`. |

### COST

| ID | Status | Question | Notes / position |
|---|---|---|---|
| `COST-01` | exploring | Cost estimate of the full pipeline? | bootstrap + enrich = local = **$0 compute**. Snowflake cost = COPY warehouse-seconds (minutes on X-Small) + small VARIANT storage. Steady-state deltas are tiny. |
| `COST-02` | exploring | Cost of enriching *in* Snowflake vs locally? | In-Snowflake fetch (External Access + UDF/proc) bills warehouse time for ~6.5h of API-waiting — wasteful. Local fetch avoids it entirely. Anti-pattern to avoid. |
| `COST-03` | open | Cost of ongoing image-URL re-validation? | `HEAD` on the CDN from the Mac = $0. If ever done from Snowflake, it's warehouse + egress — prefer local. |
| `COST-04` | open | Storage footprint? | Bronze VARIANT for ~471k rows is small (compressed). Local: ~500 MB CSV + 1–2 GB SQLite under `extraction/met/data/` (gitignored, disk-bound). |

### AUTO — orchestration / scheduling

| ID | Status | Question | Notes / position |
|---|---|---|---|
| `AUTO-01` | open | Can Snowflake Tasks/Streams *schedule detection* of stale/missing images? | Yes — a scheduled Task can compute "needs discovery or revalidation" (null image ∨ `metadataDate` advanced ∨ last-checked age exceeded) into a worklist table. (Note: `infrastructure/create_tasks.sql` is currently a placeholder.) |
| `AUTO-02` | exploring | **Worklist pattern** to reconcile "automate from Snowflake" with "fetch cheaply on the Mac." | Snowflake (Task) writes a prioritized worklist table → the Mac polls/drains it, fetches, and uploads results → Snowflake marks them done. Snowflake decides *what*; the Mac does the *fetch*. Resolves the `PIPE-01`/`IMG-06` tension at minimal cost. |

---

## Cross-references

- Patterns behind these decisions: `engineering-playbook.md` (Track 2 ingestion,
  Track 3 Bronze/Silver/Gold, medallion delete-propagation).
- Existing pipeline mechanics & gaps: `extraction.md`.
- IaC objects these decisions touch (do NOT edit under current gating):
  `ddl-infrastructure.md`.
