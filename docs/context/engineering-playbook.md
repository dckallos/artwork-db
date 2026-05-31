# engineering-playbook.md — best-practice teaching notes for the five tracks

> **Tier-1 forward-learning REFERENCE doc.** A *decision-reference / pattern
> library* you return to, **not** your primary learning tool — the guided,
> hands-on build is where the learning happens. Per track it gives the **why**,
> the **alternatives**, the **tradeoffs**, **one worked snippet**, and a
> **candidate entry point** (surfaced for consideration, never committed in
> advance). No exhaustive cookbooks.

## How to use this doc

- This is a **decision-reference that grows as we build**. It captures distilled
  tradeoffs, not a learning schedule.
- The mentor surfaces depth organically as the current task makes it relevant —
  you decide sequencing.

## Reading notes

- Each of the five optimization tracks (from AGENTS.md "Five optimization tracks
  driving growth") is one section.
- Snowflake claims are grounded with cited doc URLs (see **Sources** per track).
- Companion doc: **`cortex-ai-agents-playbook.md`** — optimizing Cortex AI &
  Cortex Agents (tools, MCP, orchestration, Web Search enablement).

---

## Track 1 — Met data modeling: Bronze → Silver → Gold

**Goal.** Turn raw Met OpenAccess API payloads (today landed in
`BRONZE.raw_met_objects`) into trustworthy, queryable Gold listings, while keeping
each layer's responsibility crisp.

**The why (layer contracts).**
- **Bronze = land, don't interpret.** Store the API response as `VARIANT` plus
  ingest metadata (source, load timestamp, batch id, raw hash). Never reshape
  here. If you guess wrong about a column upstream, you reload from Bronze, not
  from the museum. Bronze is your *replayable source of truth*.
- **Silver = conform & type.** Flatten the `VARIANT` into typed columns, apply
  one grain (one row per Met `objectID` version), standardize names/units, dedupe,
  and resolve foreign concepts (artist, medium, department) toward canonical keys.
  Silver is where data *quality* lives.
- **Gold = serve.** Consumer-shaped, business-named tables/views: e.g.
  `gold.open_access_artworks` = only currently-displayed, OpenAccess=true,
  non-deaccessioned rows, with the columns a downstream app or BI tool wants.

**Surrogate keys — the pedagogically interesting fork.**
- *Option A — deterministic hash key:* `MD5(source || ':' || object_id)` (or
  `SHA2`). Stateless, reproducible across full reloads, and — crucially — works
  inside **dynamic tables**, which cannot use sequences. Recommended default.
- *Option B — sequence/identity:* simpler to read, but non-deterministic across
  reloads and unavailable in dynamic-table definitions.
- **Tradeoff:** hashes cost a little CPU and are opaque to humans; sequences are
  friendly but brittle under replay. For a medallion that reloads from Bronze,
  **prefer the hash**.

**Worked snippet (Silver flatten + deterministic key):**
```sql
-- SILVER.met_objects : one typed row per Met objectID
CREATE OR REPLACE TABLE SILVER.MET_OBJECTS AS
SELECT
    MD5('MET:' || raw:objectID::string)            AS artwork_sk,
    raw:objectID::number                           AS source_object_id,
    'MET'                                          AS source_system,
    raw:title::string                              AS title,
    raw:artistDisplayName::string                  AS artist_display_name,
    raw:isPublicDomain::boolean                    AS is_public_domain,
    raw:GalleryNumber::string                      AS gallery_number,
    _loaded_at,                                    -- carried from Bronze
    _batch_id
FROM BRONZE.RAW_MET_OBJECTS;
```

**Candidate entry point (surfaced for consideration — not committed):** define the
Silver grain + the deterministic `artwork_sk`, then a thin Gold view that filters
to public-domain/on-display. Could start as plain DDL (to *see* the mechanics),
then later express it in dbt (Track 5).

**Sources:** dynamic tables overview & supported queries
(https://docs.snowflake.com/en/user-guide/dynamic-tables/overview,
https://docs.snowflake.com/en/user-guide/dynamic-tables/supported-queries).

---

## Track 2 — Met ingestion / updates

**Goal.** Move new and changed Met records into Bronze idempotently, then keep
Silver/Gold fresh — and *detect deaccessions/deletes*.

### 2a. Landing into Bronze with COPY INTO

**The why.** Snowflake's `COPY INTO <table>` tracks **load metadata per file** for
64 days and, by default, **skips files already loaded** — that is your built-in
idempotency for staged-file ingestion. Use `FORCE = TRUE` only to deliberately
reload. Prefer many medium files over one huge file for parallel loading.

```sql
COPY INTO BRONZE.RAW_MET_OBJECTS (raw, _loaded_at, _batch_id)
FROM (SELECT $1, CURRENT_TIMESTAMP(), '2026-05-30-met'
      FROM @BRONZE.MET_STAGE)
FILE_FORMAT = (TYPE = JSON)
ON_ERROR = ABORT_STATEMENT;   -- load metadata auto-skips already-loaded files
```

### 2b. The incremental engine — the central decision

You have three ways to propagate Bronze→Silver→Gold. This is the most important
design choice in the project, so weigh them deliberately:

| Approach | What it is | Best when | Tradeoffs |
|---|---|---|---|
| **Dynamic tables (DT)** | Declarative: you write the SELECT; Snowflake figures out incremental refresh to a `TARGET_LAG`. | You want least code, automatic dependency-graph refresh, medallion chains. | Less control over *when*/*how*; some SQL is full-refresh-only; sequences unsupported; cost tied to lag. |
| **Streams + Tasks** | Imperative: a stream captures row changes (CDC); a task runs your `MERGE` on a schedule/trigger. | You need fine control, custom MERGE/DELETE logic, or non-DT-supported SQL. | More moving parts to operate/monitor; you own the orchestration. |
| **Custom incrementalization on DT** | DT where you supply the incremental logic Snowflake can't infer. | A DT pipeline that hits one unsupported construct. | Advanced; narrow use. |

**Recommendation for this repo:** start with **dynamic tables** for the
Silver→Gold chain (teaches declarative medallion thinking, least ops), and keep
**streams+tasks** in your toolkit for the Bronze MERGE where you want explicit
delete handling (2c). Snowflake's own decision guide endorses DT-first unless you
need imperative control.

```sql
-- Declarative Silver as a dynamic table
CREATE OR REPLACE DYNAMIC TABLE SILVER.MET_OBJECTS
  TARGET_LAG = '1 hour'
  WAREHOUSE  = COMPUTE_WH
  REFRESH_MODE = AUTO
AS
SELECT MD5('MET:' || raw:objectID::string) AS artwork_sk, /* …typed cols… */
FROM BRONZE.RAW_MET_OBJECTS;
```

### 2c. Deaccession / delete detection — *why this is hard*

The Met API gives you *what exists now*, not *what was removed*. Two strategies:

- **Full-snapshot diff:** each run lands the complete current object-id set in a
  staging table; rows in Silver whose key is **absent from the latest snapshot**
  are deaccessioned. Robust, source-agnostic, but you must pull a full id list.
- **API delta (if the source exposes it):** the Met `objects` endpoint supports a
  `metadataDate` filter for *changes*; combine with periodic full reconciliation
  to catch hard deletes the delta feed may miss.

**Tradeoff:** delta is cheap but can silently miss deletions; full-snapshot is
authoritative but heavier. **Best practice = delta for freshness + periodic full
reconciliation for completeness** (this also feeds Track 5's reconciliation idea).

**Candidate entry point (surfaced for consideration — not committed):** stand up
the Silver DT with a 1-hour lag, then add a `met_object_ids_snapshot` staging
table and a "missing-key = deaccessioned" flag.

**Sources:** COPY INTO (https://docs.snowflake.com/en/sql-reference/sql/copy-into-table);
dynamic tables refresh modes & migrate-from-streams/tasks
(https://docs.snowflake.com/en/user-guide/dynamic-tables/refresh-modes,
https://docs.snowflake.com/en/user-guide/dynamic-tables/migrate-streams-tasks);
streams intro (https://docs.snowflake.com/en/user-guide/streams-intro).
Met API verified: base `https://collectionapi.metmuseum.org/public/collection/v1`,
no key, 80 req/sec; `GET /objects?metadataDate=YYYY-MM-DD` returns the `objectIDs`
changed after that date (https://metmuseum.github.io/). Verified via web search
2026-05-30 — see `met-deepdive.md` for the full Met-facts block.

### 2d. Worklist + lease-claim + batch-callback (the Mac↔Snowflake contract)

Reusable pattern (full Met-specific detail + strawman SQL in
`met-deepdive.md` → "Session-1 strawman", 2026-05-30; `DDL-04`/`PIPE-03`/`PIPE-05`):

- **System of record = a thin Snowflake control table**, narrow orchestration
  *state* only (status, timestamps, gate flags, lease cols) — never the wide data row.
- **Worklist = a VIEW** over the control table (joined to descriptive truth for
  priority ordering), not a second materialized table — it can't drift.
- **Claim = lease columns + atomic MERGE** (bounded set rides the `USING` subquery
  since `UPDATE` has no `LIMIT`); a Stream is the wrong tool for a prioritized queue.
- **Status callback = one MERGE per batch.** Acceptance rule: Snowflake round-trips
  per batch = **O(1)**, never O(N). External I/O stays on the cheapest executor; only
  a small per-batch status delta crosses the wire.

**Session-2 code-reconciliation notes (2026-05-30, against `extraction/met/`):**
The existing `snowflake_uploader.py` already owns the Snowflake connection + PUT/COPY,
so it is the natural home for the batch-callback MERGE — adding it there keeps the
O(1)/batch guard a one-line code review check (no per-row `executemany` status write).
Conversely `image_enricher.py` is currently **Snowflake-free** (worklist from local
SQLite), so the lease-claim forces a design choice — give enrich a Snowflake
connection, or split a separate `claim` command (see `met-deepdive.md` `PIPE-06`).
Two general lessons surfaced worth carrying to any executor pattern:
- **Crash-window idempotency.** A "do work → mark done" pair where the mark is a
  *separate* statement after a destructive load (`COPY … PURGE=TRUE`) has a duplicate
  window: die between COPY and mark → re-run reloads. Append-only Bronze tolerates it
  only if Silver de-dups. Prefer a single transactional unit, or make the loader
  naturally idempotent (load metadata / MERGE key).
- **Bounded fan-out.** Don't `asyncio.gather(*(... for x in N))` over a 471k-row set —
  it materializes all N tasks up front regardless of any semaphore. Drain in bounded
  slices so memory tracks the in-flight window, not the backlog.

---

## Track 3 — Delete propagation Bronze→Silver→Gold + clustering/cost

**Goal.** When a row leaves Bronze (hard delete) or is flagged deaccessioned, that
removal must reach Gold *quickly and cheaply*.

**How deletes flow under each engine.**
- **Dynamic tables:** deletes propagate automatically on refresh *if the source
  change is visible*. Caveat: a hard `DELETE` from Bronze is only captured when
  **change tracking** is on the source; and DT incremental refresh has
  edge-cases/"frozen" situations where it falls back to full refresh — know that
  it can cost more than you expect. Read the refresh-modes + troubleshooting docs.
- **Streams + Tasks:** a **standard stream** records `INSERT`, `UPDATE`, and
  `DELETE` (with `METADATA$ACTION`/`METADATA$ISUPDATE`); your task runs a
  `MERGE … WHEN MATCHED AND metadata$action='DELETE' THEN DELETE`. This gives you
  the most explicit, auditable delete path — recommended for the
  deaccession/delete-propagation requirement the owner cares about.

```sql
MERGE INTO SILVER.MET_OBJECTS t
USING BRONZE.MET_STREAM s
   ON t.artwork_sk = MD5('MET:' || s.raw:objectID::string)
WHEN MATCHED AND s.METADATA$ACTION = 'DELETE' AND s.METADATA$ISUPDATE = FALSE
     THEN DELETE
WHEN MATCHED THEN UPDATE SET title = s.raw:title::string /* … */
WHEN NOT MATCHED AND s.METADATA$ACTION = 'INSERT'
     THEN INSERT (...) VALUES (...);
```

**Clustering keys — chosen for cheap pruning *and* cheap deletes.**
- Snowflake prunes by **micro-partition** min/max metadata. If your delete/refresh
  predicate aligns with the clustering key, only a few partitions are touched —
  cheap. If deaccessions are scattered across every partition, you rewrite the
  whole table — expensive.
- **Design heuristic:** cluster Silver/Gold on a column that *co-locates the rows
  you delete together*. For Met, candidates: `source_system`, `department`, or a
  `_loaded_batch_date`. If deaccessions tend to come per-museum or per-batch,
  clustering on that column makes "drop deaccessioned rows" prune to a small set.
- **Cost discipline:** clustering only helps large tables (GB+/many partitions);
  on small tables it is pure overhead. **Automatic Clustering is a serverless,
  ongoing credit cost** — estimate before enabling with
  `SYSTEM$ESTIMATE_AUTOMATIC_CLUSTERING_COSTS`, and monitor.

**Other cost levers (spend-aware DDL):** DT `TARGET_LAG` (looser lag = fewer
refreshes = cheaper), warehouse sizing for refresh, and triggered tasks (run only
when upstream changed) vs. scheduled.

**Tradeoff to teach:** automatic clustering buys query/delete pruning at a
*continuous* credit cost; manual reclustering or partition-aligned loading can
achieve similar pruning without the always-on serverless spend — at the cost of
more design effort.

**Candidate entry point (surfaced for consideration — not committed):** pick the
Silver clustering key by reasoning about *how deaccessions arrive*, run
`SYSTEM$ESTIMATE_AUTOMATIC_CLUSTERING_COSTS` before turning auto-clustering on,
and wire one stream+task MERGE-with-DELETE so you can watch a delete reach Gold.

**Sources:** CHANGES/change-tracking
(https://docs.snowflake.com/en/sql-reference/constructs/changes);
streams manage/examples (https://docs.snowflake.com/en/user-guide/streams-manage,
https://docs.snowflake.com/en/user-guide/streams-examples);
clustering keys & micro-partitions
(https://docs.snowflake.com/en/user-guide/tables-clustering-keys,
https://docs.snowflake.com/en/user-guide/tables-clustering-micropartitions);
auto-reclustering (https://docs.snowflake.com/en/user-guide/tables-auto-reclustering);
clustering-cost estimator
(https://docs.snowflake.com/en/sql-reference/functions/system_estimate_automatic_clustering_costs);
DT cost & troubleshooting (https://docs.snowflake.com/en/user-guide/dynamic-tables/cost,
https://docs.snowflake.com/en/user-guide/dynamic-tables/troubleshoot-refreshes).

---

## Track 4 — New sources + normalized cross-source entity model

**Goal.** Onboard Cleveland Museum of Art (CMA), Art Institute of Chicago (AIC),
and the Smithsonian, and make "the same artist across sources" resolve to one
canonical entity.

**Onboarding pattern (repeat per source).**
1. One Bronze landing table per source: `BRONZE.RAW_CMA_OBJECTS`,
   `RAW_AIC_OBJECTS`, `RAW_SMITHSONIAN_OBJECTS` (VARIANT + ingest metadata).
2. One Silver conform model per source mapping that source's fields to the
   **shared Silver schema** (same column names/types as Met).
3. A **union Silver** (or Gold) that stacks all sources on the shared schema.

| Source | Base endpoint | Auth | License | Notes |
|---|---|---|---|---|
| Met | `https://collectionapi.metmuseum.org/public/collection/v1/` | none | OpenAccess / public-domain subset | already live |
| Cleveland (CMA) | `https://openaccess-api.clevelandart.org/` (e.g. `/api/artworks/`) | **none — no key or token required** | **all metadata CC0**; CC0 images only where `share_license_status = CC0` | ~64k records; 37k+ images |
| Art Institute (AIC) | `https://api.artic.edu/api/v1/` (e.g. `/artworks/{id}`) | **none** — anonymous, rate-limited 60 req/min/IP; send an `AIC-User-Agent` header | metadata **CC0 1.0** + artic.edu Terms; image rights vary per work (public-domain works' images are CC0) | 50k+ open-access images; IIIF at `https://www.artic.edu/iiif/2` |
| Smithsonian | Hosted on `api.data.gov` (EDAN; docs `https://edan.si.edu/openaccess/docs/`) | **API key required** (register via api.data.gov) | **CC0** metadata; media only for public-domain objects | store key as a secret, never in repo |

**Entity normalization — the canonical artist model.** The same artist appears
as different strings ("Vincent van Gogh", "van Gogh, Vincent", "Gogh, Vincent
van") and different source IDs. Build a conformed dimension:
- `DIM_ARTIST` with a canonical `artist_sk`, a `display_name`, and a bridge table
  `ARTIST_XREF (source_system, source_artist_id, artist_sk)`.
- **Matching strategy fork:** (a) deterministic — normalize+hash on
  name+nationality+birth year; cheapest, misspellings slip through. (b) fuzzy —
  `EDITDISTANCE`/`JAROWINKLER` blocking + threshold; catches variants, risks false
  merges. (c) authority join — match to an external authority (e.g. ULAN/Wikidata
  identifiers if a source carries them); most robust, more integration work.
- **Best practice:** start deterministic on a normalized natural key, add a fuzzy
  *candidate* step that a human (you) confirms, and reserve authority-linking for
  later. Keep the xref so a bad merge is reversible.

**Tradeoff to teach:** every match strategy trades *recall* (catching all true
duplicates) against *precision* (not merging distinct artists). The xref+canonical
pattern lets you change the matching logic later without rewriting Gold.

**Candidate entry point (surfaced for consideration — not committed):** add CMA
as source #2 (CC0, no key — the gentlest second source), build
`RAW_CMA_OBJECTS` + its Silver conform model against the shared schema, then
introduce `DIM_ARTIST` + `ARTIST_XREF` with deterministic matching.

**Sources:** Met already in `extraction/met/` (repo). CMA Open Access API —
endpoint + "no key or token is required" + CC0
(https://openaccess-api.clevelandart.org/, https://www.clevelandart.org/open-access-api,
https://www.clevelandart.org/open-access). AIC public API — `api.artic.edu/api/v1`,
no auth (60 req/min/IP, `AIC-User-Agent` recommended), metadata CC0 1.0 + Terms
(https://api.artic.edu/docs/, https://www.artic.edu/open-access/public-api,
https://www.artic.edu/open-access). Smithsonian Open Access — API key via
api.data.gov, CC0 metadata
(https://www.si.edu/openaccess/devtools, https://github.com/Smithsonian/OpenAccess,
https://edan.si.edu/openaccess/docs/). Verified via web search 2026-05-30.

---

## Track 5 — dbt adoption

**Goal.** Express Silver/Gold transforms as version-controlled dbt models with
automated quality checks — and decide *how* dbt runs on Snowflake.

### 5a. Completeness / volume testing — two philosophies

The owner's open question (AGENTS.md): **dbt tests vs. cross-schema
reconciliation.** They are complementary, not exclusive:

| | dbt tests | Cross-schema reconciliation |
|---|---|---|
| **What** | Declarative assertions in dbt: `not_null`, `unique`, `relationships`, `accepted_values`, plus `dbt_utils` (`equal_rowcount`, `recency`, `expression_is_true`). | A post-run query comparing counts/keys across Bronze↔Silver↔Gold (e.g. "every non-deaccessioned Bronze id appears in Gold"). |
| **Catches** | Schema/row-level invariants, referential integrity, freshness. | *Volume drift* and *leakage* between layers — the medallion-specific failure mode. |
| **Pros** | Lives with the model, runs in CI, fails the build, self-documents. | Directly answers "did rows get lost/duplicated across layers?" |
| **Cons** | Doesn't naturally express "Bronze count must reconcile to Gold count after delete-propagation." | Custom SQL to maintain; runs after the fact. |

**Best practice:** use **both** — dbt generic/`dbt_utils` tests for invariants and
freshness, *plus* a reconciliation model (which can itself be a dbt **singular
test** or an audited model) for layer-to-layer volume/completeness. That directly
serves the delete-propagation and completeness cornerstones.

```yaml
# schema.yml — invariant tests on Silver
models:
  - name: met_objects
    columns:
      - name: artwork_sk
        tests: [unique, not_null]
      - name: source_object_id
        tests: [not_null]
    tests:
      - dbt_utils.recency: {datepart: day, field: _loaded_at, interval: 2}
```

### 5b. Snowflake-native dbt vs dbt-core — and the repo's profile gap

- **dbt-core (current repo direction):** `profiles.yml.example` uses
  `env_var()` + key-pair auth. Per AGENTS.md/extraction.md this is **dbt-core
  only** — env vars aren't available when dbt runs *inside* Snowflake. That is the
  noted gap.
- **dbt Projects on Snowflake (native, now GA):** dbt runs *inside* Snowflake as a
  first-class `DBT PROJECT` object — versioning, scheduling via tasks, execution
  logs, and Workspace authoring, with auth handled by the Snowflake session (no
  `env_var()`/password/`authenticator` in `profiles.yml`).
- **Tradeoff:** dbt-core gives you the full OSS ecosystem and local control;
  native dbt gives governed, in-platform execution + scheduling without separate
  infra, but within Snowflake's supported dbt-core version range and
  [limitations].

**Best practice for this learning repo:** prototype models with dbt-core to learn
the OSS workflow, then **migrate to dbt Projects on Snowflake** for deployment —
and when you do, add a Snowflake-native profile (no `env_var()`), which closes the
gap. (Native deployment uses `CREATE DBT PROJECT`, not the dbt CLI — invoke the
`dbt-projects-on-snowflake` skill when we get there.)

**Candidate entry point (surfaced for consideration — not committed):** scaffold
a minimal dbt project for the Silver `met_objects` model with two tests
(`unique`/`not_null` on `artwork_sk`) plus one reconciliation singular test, run
it with dbt-core, *then* plan the native migration.

**Sources:** dbt Projects on Snowflake (GA) — overview, dbt-core versions,
limitations, scheduling
(https://docs.snowflake.com/en/user-guide/data-engineering/dbt-projects-on-snowflake,
https://docs.snowflake.com/en/user-guide/data-engineering/dbt-projects-on-snowflake-dbt-core-versions,
https://docs.snowflake.com/en/user-guide/data-engineering/dbt-projects-on-snowflake-limitations,
https://docs.snowflake.com/en/user-guide/data-engineering/dbt-projects-on-snowflake-schedule-project-execution);
GA release note
(https://docs.snowflake.com/en/release-notes/2025/other/2025-11-06-dbt-projects-on-snowflake-ga).
dbt generic tests & `dbt_utils` are documented at the canonical dbt docs
(docs.getdbt.com) — ⚠ exact pages **unverified** here (web_search disabled).

---

## There is no fixed order

The five tracks are a **map of terrain, not a route**. Which track we touch next
is decided turn-by-turn based on what the current build actually surfaces. The
mentor raises relevant forks, optimizations, and tradeoffs as they come up — you
choose what to engage.