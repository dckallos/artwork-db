# AIC Extraction Layer -- Design Document

> **Status:** Design FINALIZED (all open questions resolved 2026-06-07).
> Not yet implemented.
> **Branch:** `donkey-kong-sandbox`
> **Audience:** Owner + next-window Cortex sessions.
> **Companion:** `docs/prompts/AIC_EXTRACTION_DESIGN_PROMPT.md` (the brief that
> produced this document).

---

## 1. Ingestion Strategy

### Decision: Hybrid (bulk snapshot + API delta)

| Path | Mechanism | Volume | Warehouse cost | Freshness | Complexity |
|------|-----------|--------|---------------|-----------|------------|
| **A: S3 data dump** | Download `artic-api-data.tar.bz2` (~115 MB), selectively extract Tier 1 folders, transform to NDJSON, COPY+MERGE into Bronze | 131k artworks + 15k agents (Tier 1) | ~10-20 warehouse-seconds (XS, COPY INTO + MERGE) | Monthly (dump updated monthly per README) | Low (one download, selective extract, one MERGE) |
| **B: API incremental** | Paginate `/artworks/search` with `source_updated_at >= ?` range query, page size 100 | Varies (days since last sync) | ~5-10 warehouse-seconds per delta run | Near-real-time (hours) | Medium (pagination, rate-limit handling, watermark tracking) |
| **Hybrid (chosen)** | A for initial load + monthly refresh; B for between-dump freshness | Full corpus on snapshot; deltas between | A cost + B cost (modest) | Hours (API delta cadence) | Medium overall, but each path is individually simple |

### Rationale

- The data dump gives us **completeness** (every entity, every field) in one
  operation. It is the cheapest path to full coverage and the only path that
  supports **delete-propagation** (anti-join between successive snapshots).
- The API gives us **freshness** between monthly dumps. The
  `source_updated_at` range query returns only changed records -- no need to
  paginate the full 131k corpus.
- No per-object API calls are needed (unlike the Met). AIC's dump contains
  complete records, and image URLs are constructible from `image_id` without
  any API round-trip.

### Tar extraction approach: Selective (DECIDED)

Use Python's `tarfile` member filtering to extract **only** the `json/artworks/`
and `json/agents/` folders from the tar.bz2. This saves ~1.5 GB of temp disk
(~1 GB extracted vs ~2.5 GB for the full archive) and avoids cluttering the
local filesystem with 25 unused entity folders.

```python
# Pseudocode for selective extraction
with tarfile.open(tar_path, "r:bz2") as tf:
    members = [m for m in tf.getmembers()
               if any(m.name.startswith(f"json/{entity}/")
                      for entity in ["artworks", "agents"])]
    tf.extractall(path=extract_dir, members=members)
```

### Snapshot data source: Individual JSON files (DECIDED)

Use the individual JSON files from `json/artworks/*.json` (131k files, ~5KB
each) rather than the convenience `getting-started/allArtworks.jsonl`.
Rationale: individual JSONs contain the **complete** record (every field);
the JSONL shortcut contains only key fields and may omit data needed in
Silver/Gold (e.g., full `category_ids`, `term_titles`, `alt_image_ids`).

### Data flow (snapshot path)

```
artic-api-data.tar.bz2 (S3, ~115 MB)
  |
  v  [download to data/aic_dump.tar.bz2, ~2 min]
  |
  v  [selective extract: only json/artworks/ + json/agents/]
data/aic_extract/json/artworks/*.json  (~131k files)
data/aic_extract/json/agents/*.json    (~15k files)
  |
  v  [Python: read each .json, emit one NDJSON line per record]
data/aic_artworks.ndjson  (~650 MB uncompressed NDJSON)
data/aic_agents.ndjson    (~75 MB uncompressed NDJSON)
  |
  v  [PUT to @BRONZE_LOAD_STAGE/aic/artworks/ and /aic/agents/]
Snowflake internal stage
  |
  v  [COPY INTO temp staging table (CREATE TEMPORARY TABLE)]
  |
  v  [MERGE INTO RAW_AIC_ARTWORKS / RAW_AIC_AGENTS keyed on PK]
Bronze tables (idempotent, one row per entity)
  |
  v  [Post-MERGE: detect + soft-delete deaccessioned rows via _batch_id anti-join]
_is_deleted = TRUE, _deleted_at = NOW() for rows not in current batch
```

### Data flow (delta path -- future enhancement)

```
API: /artworks/search?query[range][source_updated_at][gte]=<watermark>
  |
  v  [paginate with limit=100, collect changed records]
In-memory list of changed artwork dicts
  |
  v  [Python: emit NDJSON]
data/aic_artworks_delta.ndjson
  |
  v  [PUT + COPY INTO temp + MERGE INTO RAW_AIC_ARTWORKS]
Bronze table (upsert changed rows only)
  |
  v  [UPDATE AIC_LOAD_WATERMARK SET last_source_updated_at = max(batch)]
Watermark advanced
```

---

## 2. Entity Scope

### Tier 1 -- Load immediately (v1)

| Entity | Source folder/endpoint | Volume | Why |
|--------|----------------------|--------|-----|
| **artworks** | `json/artworks/` / `/api/v1/artworks` | ~131k records | Primary entity. Cross-source join candidate (Met <-> AIC). Drives all downstream Gold models. |
| **agents** | `json/agents/` / `/api/v1/agents` | ~15k records | Artists + donors + collectors. Has `ulan_id` for cross-source entity resolution. `is_artist` boolean enables Silver filtering. |

### Tier 2 -- Load next

| Entity | Volume | Why |
|--------|--------|-----|
| exhibitions | ~6,500 | Historical context; potential Gold dimension. |
| places | ~1,000 | Geographic origin; join to artworks via `place_of_origin`. |
| category-terms | ~2,000 | Subject/material/technique taxonomy. |
| artwork-types | ~50 | Classification (Painting, Sculpture, etc.). Small reference table. |

### Tier 3 -- Skip in v1

All CMS/website content: articles, digital-publications, educator-resources,
events, generic-pages, highlights, mobile-sounds, press-releases, printed-
publications, products, publications, sections, sites, sounds, static-pages,
texts, tours, videos. Also: agent-roles, agent-types, images (metadata),
galleries, artwork-date-qualifiers, artwork-place-qualifiers.

**Justification:** No analytical value for cross-museum artwork comparison.
Can revisit if a specific Gold use case emerges.

---

## 3. Bronze Table Design

### Decision: Single artworks table (DECIDED -- OQ-2 resolved)

AIC uses a **single `RAW_AIC_ARTWORKS` table** for both snapshot (dump) and
delta (API) loads. This differs from the Met's two-table split because:

1. AIC's dump and API return the **same JSON shape** -- no structural
   difference to separate.
2. Delete-detection works via `_batch_id` staleness (rows whose `_batch_id`
   doesn't match the current snapshot batch were not in the dump).
3. Simpler DDL, simpler Silver (no reconciliation between two tables).

### Design principles (aligned to Met pattern)

1. **Bronze = land, don't interpret.** Store the complete API/dump JSON as
   `VARIANT`. Never reshape or filter here.
2. **All records loaded** -- both `is_public_domain = true` and `false`. The
   public-domain gate applies to **image URL construction in Silver/Gold only**,
   not to Bronze landing.
3. **MERGE, not append.** Primary key declares uniqueness intent; the MERGE
   load pattern enforces it at runtime (Snowflake does not enforce PK/UNIQUE).
4. **Soft-delete for deaccessions.** `_is_deleted` + `_deleted_at` +
   `_deletion_reason` columns enable explicit rights-compliance signaling
   without removing rows from Bronze.
5. **Naming convention:** `RAW_AIC_{SOURCE_ENTITY_NAME}` in Bronze (preserves
   the source API's vocabulary). Human-readable renames happen in Silver.

### Final Bronze table inventory (3 tables)

| Table | Entity | Purpose |
|-------|--------|---------|
| `RAW_AIC_ARTWORKS` | artworks | Single table for both snapshot (dump) and delta (API) loads. One row per `artwork_id`. Soft-delete columns for deaccession tracking. |
| `RAW_AIC_AGENTS` | agents | All agents (artists + non-artists). One row per `agent_id`. Loaded from the dump only (no delta path in v1). |
| `AIC_LOAD_WATERMARK` | metadata | One row per entity type tracking last delta timestamp. |

### Proposed DDL

#### RAW_AIC_ARTWORKS (replaces the existing skeleton)

```sql
CREATE OR REPLACE TABLE BRONZE.RAW_AIC_ARTWORKS (
    artwork_id        INT             NOT NULL
        COMMENT 'AIC API artwork id; PK (one row per artwork)',
    raw_payload       VARIANT         NOT NULL
        COMMENT 'Complete raw JSON from the data dump or API response',
    _extracted_at     TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP()
        COMMENT 'UTC timestamp the row was landed or last updated',
    _source_system    VARCHAR         NOT NULL DEFAULT 'art_institute_chicago'
        COMMENT 'Source system identifier',
    _batch_id         VARCHAR         NOT NULL
        COMMENT 'UUID identifying the extraction batch (snapshot or delta)',
    _is_deleted       BOOLEAN         NOT NULL DEFAULT FALSE
        COMMENT 'TRUE if artwork was detected as deaccessioned/withdrawn',
    _deleted_at       TIMESTAMP_NTZ
        COMMENT 'UTC timestamp when deaccession was detected (NULL if active)',
    _deletion_reason  VARCHAR
        COMMENT 'How deaccession was detected: snapshot_anti_join | api_404 | manual',
    CONSTRAINT pk_raw_aic_artworks PRIMARY KEY (artwork_id)
)
COMMENT = 'Raw AIC artworks (VARIANT). Both snapshot and delta paths MERGE here. Soft-delete columns track deaccessions for rights compliance.';
```

#### RAW_AIC_AGENTS

```sql
CREATE TABLE IF NOT EXISTS BRONZE.RAW_AIC_AGENTS (
    agent_id          INT             NOT NULL
        COMMENT 'AIC API agent id; includes artists, donors, collectors',
    raw_payload       VARIANT         NOT NULL
        COMMENT 'Complete raw JSON from agents/ data dump',
    _extracted_at     TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP()
        COMMENT 'UTC timestamp of extraction',
    _source_system    VARCHAR         NOT NULL DEFAULT 'art_institute_chicago'
        COMMENT 'Source system identifier',
    _batch_id         VARCHAR         NOT NULL
        COMMENT 'UUID identifying the extraction batch',
    CONSTRAINT pk_raw_aic_agents PRIMARY KEY (agent_id)
)
COMMENT = 'Raw AIC agents (artists + non-artists). One row per agent_id (PK). Filter is_artist in Silver.';
```

#### AIC_LOAD_WATERMARK

```sql
CREATE TABLE IF NOT EXISTS BRONZE.AIC_LOAD_WATERMARK (
    entity_type             VARCHAR         NOT NULL
        COMMENT 'Entity being tracked (artworks, agents)',
    last_source_updated_at  TIMESTAMP_NTZ   NOT NULL
        COMMENT 'Max source_updated_at from the last successful delta load',
    last_batch_id           VARCHAR         NOT NULL
        COMMENT 'Batch UUID of the last successful delta load',
    updated_at              TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP()
        COMMENT 'When this watermark row was last written',
    CONSTRAINT pk_aic_load_watermark PRIMARY KEY (entity_type)
)
COMMENT = 'High-water mark for AIC API delta queries. One row per entity type.';
```

### Naming rationale

| Layer | Table name | Why |
|-------|-----------|-----|
| Bronze | `RAW_AIC_AGENTS` | Source API vocabulary. The endpoint is `/agents`, the dump folder is `agents/`. Bronze preserves source semantics without interpretation. |
| Silver | `AIC_ARTISTS` | Business vocabulary. Filtered to `is_artist = true`, typed columns, human-friendly. The interpretive rename belongs here. |

### No clustering key in v1

At 131k rows (artworks) and 15k rows (agents), the tables are well below the
threshold (~1B+ micro-partitions) where clustering keys provide meaningful
pruning benefit. Re-evaluate if volume grows 100x (unlikely for a single
museum's collection).

---

## 4. File Layout

```
extraction/aic/
    __init__.py          # Package marker (empty)
    run.py               # CLI entry point (argparse, subcommands)
    config.py            # Config dataclass + .env loading
    loader.py            # Snapshot + delta logic (download, transform, upload, merge)
    sql/
        merge_aic_artworks.sql   # MERGE INTO RAW_AIC_ARTWORKS (both paths)
        merge_aic_agents.sql     # MERGE INTO RAW_AIC_AGENTS
        soft_delete_deaccessioned.sql  # UPDATE _is_deleted for stale rows
```

**Target: 3 Python files + 3 SQL templates.** Compare to Met's 10 Python
files -- AIC is simpler because there is no multi-hour crawl, no SQLite, no
lease/claim/control-table enrichment loop.

### Why no SQLite?

The Met extractor uses SQLite as a local accumulator because:
1. The per-object API crawl takes hours (350k objects x ~100ms each).
2. The process can crash mid-crawl; SQLite preserves partial progress.
3. The enrichment loop (lease-claim-fetch-callback) needs local state.

None of these apply to AIC:
1. The data dump downloads in ~2 minutes. No crawl.
2. If the process crashes mid-transform, re-run from scratch (cheap).
3. Delta detection is a single paginated query, not a per-object loop.

---

## 5. CLI Interface Spec

```
python -m extraction.aic.run <subcommand> [options]
```

| Subcommand | Description | Options |
|-----------|-------------|---------|
| `snapshot` | Download the S3 data dump, selectively extract Tier 1 entities, transform to NDJSON, MERGE into Bronze, soft-delete deaccessioned rows | `--no-refresh` (reuse cached tar), `--limit N` (cap records for smoke test), `--entities artworks,agents` (select which to load) |
| `delta` | Query the API for records changed since the watermark, MERGE into `RAW_AIC_ARTWORKS` | `--since YYYY-MM-DD` (override watermark), `--limit N` (cap pages), `--dry-run` (fetch but don't upload) |
| `status` | Print current watermark, row counts, last batch timestamp, deaccession count | (none) |

### Example usage

```bash
# Initial full load (first time)
python -m extraction.aic.run snapshot

# Monthly refresh (re-download dump, re-MERGE, detect deaccessions)
python -m extraction.aic.run snapshot

# Incremental update (between monthly dumps) -- FUTURE ENHANCEMENT
python -m extraction.aic.run delta

# Smoke test (5 records only)
python -m extraction.aic.run snapshot --limit 5

# Check pipeline state
python -m extraction.aic.run status
```

---

## 6. Deaccession Detection & Rights Compliance

### Decision: Soft-delete in Bronze (DECIDED -- OQ-4 resolved)

When a full snapshot run detects that an `artwork_id` was in the prior load
but is NOT in the current dump, the row is **soft-deleted in place**:

```sql
-- soft_delete_deaccessioned.sql (run post-MERGE on each snapshot)
UPDATE {target}
SET _is_deleted      = TRUE,
    _deleted_at      = CURRENT_TIMESTAMP(),
    _deletion_reason = 'snapshot_anti_join'
WHERE _batch_id != '{current_batch_id}'
  AND _is_deleted = FALSE;
```

### Why soft-delete in Bronze (not Silver-only)?

The owner's legal concern: if an artwork leaves the AIC and loses OpenAccess
status, any downstream consumer of image URLs must stop serving that image
**immediately** (next pipeline refresh). This requires the deaccession signal
to be:

1. **Explicit** -- not implicit (a stale `_batch_id` that Silver must interpret).
2. **Visible at every layer** -- if someone queries Bronze directly (bypassing
   Silver), the `_is_deleted = TRUE` flag is unambiguous.
3. **Auditable** -- `_deleted_at` and `_deletion_reason` provide a compliance
   trail ("we detected removal on date X via method Y").

If we relied on Silver-only detection (Option C), a bug in the Silver model
or a direct Bronze query would silently serve deaccessioned artwork images
with no warning. For a rights-sensitive pipeline, the deletion signal must be
at the source-of-truth layer.

### Detection mechanisms (current + future)

| Mechanism | Trigger | Latency | Status |
|-----------|---------|---------|--------|
| **Snapshot anti-join** | Monthly `snapshot` re-run: rows with stale `_batch_id` after MERGE | Up to 30 days | **v1 (implementing now)** |
| **API liveness spot-check** | On each `delta` run: query API for a sample of known `artwork_id`s; 404 = soft-delete immediately | Hours | **Future enhancement** |
| **Full liveness sweep** | Periodically check ALL 131k artwork_ids against the API | Hours (but expensive: 131k API calls) | **Future (if needed)** |
| **Manual override** | Owner sets `_deletion_reason = 'manual'` via SQL | Immediate | **Always available** |

### Downstream circuit-breakers (Silver + Gold)

Every downstream model MUST filter on `_is_deleted`:

```sql
-- Silver model (dbt or DDL): hard exclusion
WHERE _is_deleted = FALSE

-- Silver image URL computation: double-gate (rights + liveness)
CASE
    WHEN _is_deleted = FALSE
         AND raw_payload:is_public_domain::BOOLEAN = TRUE
         AND raw_payload:image_id::STRING IS NOT NULL
    THEN 'https://www.artic.edu/iiif/2/'
         || raw_payload:image_id::STRING
         || '/full/843,/0/default.jpg'
    ELSE NULL
END AS primary_image_url

-- Gold OpenAccess listing: belt-and-suspenders
WHERE is_public_domain = TRUE
  AND is_deleted = FALSE
```

### API liveness spot-check (future enhancement design)

When the `delta` subcommand is implemented, it should include an optional
`--check-liveness` flag (or always-on sampling) that:

1. Selects a random sample of N artwork_ids from `RAW_AIC_ARTWORKS` where
   `_is_deleted = FALSE` (default N = 100, configurable).
2. Queries the AIC API for each: `GET /api/v1/artworks/{id}`.
3. If the API returns 404: immediately soft-delete that row
   (`_deletion_reason = 'api_404'`).
4. If the API returns 200: no action (artwork is still live).

This reduces worst-case deaccession detection from 30 days to the delta
cadence (e.g., daily). Cost: ~100 extra API calls per delta run (~10 seconds
at AIC's typical 722ms response time).

**Priority-weighted sampling:** Rather than pure random, preferentially
check artworks that:
- Have `is_public_domain = TRUE` (rights-sensitive subset)
- Were last confirmed a long time ago (oldest `_extracted_at`)
- Are being actively served in Gold (if usage tracking exists)

---

## 7. Delta / Freshness Strategy

### Watermark table: `AIC_LOAD_WATERMARK`

A minimal one-row-per-entity control table tracking the high-water mark for
incremental API queries (see DDL in Section 3).

### Delta detection mechanism (future enhancement)

The AIC API supports Elasticsearch range queries on `source_updated_at`:

```
GET /api/v1/artworks/search?query[range][source_updated_at][gte]=2025-01-01
    &sort[source_updated_at][order]=asc
    &limit=100&page=1&fields=id,title,image_id,...
```

The loader (when implemented):
1. Reads `last_source_updated_at` from `AIC_LOAD_WATERMARK` for entity `artworks`.
2. Queries the API with that timestamp as the `gte` bound.
3. Paginates until exhausted (or `--limit` cap hit).
4. MERGEs results into `RAW_AIC_ARTWORKS`.
5. Updates the watermark to `max(source_updated_at)` from the batch.

### v1 scope: Snapshot only (manual monthly)

For v1 (development phase), only the `snapshot` subcommand is implemented.
The `delta` subcommand is stubbed in the CLI (with a "not yet implemented"
message) and fully designed here for future build-out. The watermark table
DDL is created now so the schema is stable when delta is added.

### Provenance tracking (DECIDED -- OQ-3 resolved)

Both snapshot and delta writes go to the **same table** (`RAW_AIC_ARTWORKS`).
Provenance is tracked via `_batch_id`:
- Snapshot batches use a UUID prefixed with `snap_` (e.g., `snap_a1b2c3d4...`)
- Delta batches use a UUID prefixed with `delta_` (e.g., `delta_e5f6g7h8...`)

This lets you distinguish the origin of any row's last update without
needing separate tables. Delete-detection only fires on snapshot runs (where
the MERGE touches all 131k rows and leaves stale `_batch_id` on removed
artworks).

---

## 8. Image URL Handling

### Decision: Store `image_id` in Bronze; compute IIIF URL in Silver

**Bronze:** The raw payload already contains `image_id` (a UUID string). No
transformation needed. Land as-is inside the VARIANT blob.

**Silver:** Compute the full IIIF URL as a derived column, gated on BOTH
`is_public_domain` AND `_is_deleted`:

```sql
-- In a Silver model (dbt or DDL)
CASE
    WHEN raw_payload:is_public_domain::BOOLEAN = TRUE
         AND raw_payload:image_id::STRING IS NOT NULL
         AND _is_deleted = FALSE
    THEN 'https://www.artic.edu/iiif/2/'
         || raw_payload:image_id::STRING
         || '/full/843,/0/default.jpg'
    ELSE NULL
END AS primary_image_url
```

### The `is_public_domain` gate

- AIC's license terms: images are CC0 **only when `is_public_domain` is true**.
- Non-public-domain artworks may still have an `image_id`, but we MUST NOT
  construct/serve the URL (it would be a rights violation).
- **Enforcement point:** Silver (with `_is_deleted` as an additional gate).
  Bronze stores everything; Silver applies both the rights filter AND the
  liveness filter. This keeps Bronze as an uninterpreted, replayable source
  of truth while ensuring legal compliance at the consumption layer.

### The IIIF base URL

The base `https://www.artic.edu/iiif/2` comes from AIC's `config.json`
endpoint. It has been stable for years. Strategy:

- **v1:** Hardcode as a Python constant in `config.py` and as a literal in the
  Silver model. Simple, correct for now.
- **Future:** If AIC changes the IIIF base, a single constant update
  propagates everywhere. Could also store it from `config.json` at load time
  in the watermark/metadata row, but this is over-engineering for v1.

### Image width

AIC recommends `843` pixels (standard resolution). `1686` is available for
high-res but doubles bandwidth and storage. Use `843` as the default.

---

## 9. Cross-Source Entity Resolution (Forward-Looking)

### The problem

Both Met and AIC have artist records. The same artist (e.g., Claude Monet)
appears in both collections with different internal IDs and potentially
different name spellings.

### Available join keys

| Source | Artist ID | ULAN ID | Name field | Birth/death years |
|--------|-----------|---------|-----------|-------------------|
| Met | `raw:artistID` (nullable) | `raw:artistULAN_URL` (ULAN URL, parseable) | `raw:artistDisplayName` | `raw:artistBeginDate`, `raw:artistEndDate` |
| AIC | `agent_id` | `raw_payload:ulan_id` (nullable integer) | `raw_payload:title` (sort_title also available) | `raw_payload:birth_date`, `raw_payload:death_date` |

### Proposed strategy (Gold layer)

1. **Primary join: ULAN ID.** Where both sources provide a ULAN identifier,
   join directly. This is the most reliable -- ULAN is the Getty's canonical
   artist authority file.
   - Met: parse the numeric ID from the ULAN URL
     (`http://vocab.getty.edu/page/ulan/{id}` -> extract `{id}`).
   - AIC: `ulan_id` is already a bare integer.

2. **Fallback: fuzzy match on name + life dates.** Where ULAN is null on one
   or both sides, match on:
   - Normalized artist name (lowercase, strip diacritics, surname-first)
   - Birth year (+/- 1 year tolerance for data quality)
   - Death year (+/- 1 year tolerance)

3. **Gold dimension table: `DIM_ARTISTS`**

```sql
-- Sketch (not final DDL)
CREATE TABLE GOLD.DIM_ARTISTS (
    artist_sk       VARCHAR     NOT NULL COMMENT 'Deterministic hash: MD5(COALESCE(ulan_id, source||id))',
    ulan_id         INT         COMMENT 'Getty ULAN authority ID (canonical cross-source key)',
    display_name    VARCHAR     NOT NULL,
    birth_year      INT,
    death_year      INT,
    nationality     VARCHAR,
    -- Source provenance (which museums have this artist)
    met_artist_id   INT         COMMENT 'Met API constituentID (null if not in Met)',
    aic_agent_id    INT         COMMENT 'AIC API agent_id (null if not in AIC)',
    source_systems  ARRAY       COMMENT '[met_museum, art_institute_chicago, ...]',
    _resolved_at    TIMESTAMP_NTZ
);
```

### What we are NOT doing yet

- No NLP-based name matching (overkill for <50k artists across 2 sources).
- No external ULAN API calls to enrich missing IDs (possible future enhancement).
- No automated conflict resolution -- first pass surfaces duplicates for
  manual review.

---

## 10. Summary of All Decisions

| # | Decision | Choice | Key rationale |
|---|----------|--------|---------------|
| D-1 | Ingestion strategy | Hybrid (dump + API delta) | Completeness + freshness; no per-object API calls needed. |
| D-2 | Tier 1 entities | artworks + agents | Core analytical value; cross-source join on ULAN. |
| D-3 | Bronze table naming | `RAW_AIC_AGENTS` (source vocab) | Bronze preserves API semantics; Silver renames to `AIC_ARTISTS`. |
| D-4 | Load semantics | MERGE keyed on PK | Idempotent, supports delete-detection, matches Met pattern. |
| D-5 | `is_public_domain` gate | Silver (not Bronze) | Bronze lands everything; Silver applies rights filtering for image URLs. |
| D-6 | Image URLs | Compute in Silver from `image_id` | No API call needed; simple string construction with double gate (public domain + not deleted). |
| D-7 | SQLite | None | No multi-hour crawl; re-run from scratch is cheap (~2 min). |
| D-8 | Entity resolution | ULAN primary key; fuzzy name+dates fallback | Both sources expose ULAN; Gold `DIM_ARTISTS` unifies. |
| D-9 | File count target | 3 Python + 3 SQL | Dramatically simpler than Met's 10-file architecture. |
| D-10 | Tar extraction | Selective (Tier 1 folders only) | Saves ~1.5 GB temp disk; `tarfile` member filtering is straightforward. |
| D-11 | Table count (artworks) | Single table (`RAW_AIC_ARTWORKS`) | Dump and API return same shape; no structural reason to split. |
| D-12 | Deaccession handling | Soft-delete in Bronze (`_is_deleted` + `_deleted_at` + `_deletion_reason`) | Explicit, auditable, visible at every layer. Rights compliance demands unambiguous signal. |
| D-13 | Deaccession detection | Monthly snapshot anti-join (v1); API liveness spot-check (future) | 30-day latency acceptable in dev; spot-check design ready for when production needs tighter SLA. |
| D-14 | Delta provenance | `_batch_id` prefix distinguishes `snap_*` vs `delta_*` | Single table, clear lineage without schema complexity. |
| D-15 | Snapshot data source | Individual JSON files (complete records) | JSONL shortcut may omit fields needed in Silver/Gold. |
| D-16 | Delta scheduling | Manual only in v1; decide automation after v1 works | No premature complexity; `delta` CLI subcommand stubbed for future. |

---

## Appendix A: Config Constants

```python
# extraction/aic/config.py (sketch)
AIC_DUMP_URL = "https://artic-api-data.s3.amazonaws.com/artic-api-data.tar.bz2"
AIC_API_BASE = "https://api.artic.edu/api/v1"
AIC_IIIF_BASE = "https://www.artic.edu/iiif/2"
AIC_DEFAULT_IMAGE_WIDTH = 843
AIC_API_PAGE_SIZE = 100  # max supported by the API

# Tier 1 entity folders in the data dump tar
AIC_TIER1_ENTITIES = ["artworks", "agents"]

# Batch ID prefixes for provenance tracking
BATCH_PREFIX_SNAPSHOT = "snap"
BATCH_PREFIX_DELTA = "delta"
```

## Appendix B: MERGE Template (artworks)

```sql
-- merge_aic_artworks.sql (rendered with str.format)
-- Used by both snapshot and delta paths (same target table)
MERGE INTO {target} AS t
USING (
    SELECT artwork_id, raw_payload, _batch_id
    FROM {stg}
    QUALIFY ROW_NUMBER() OVER (PARTITION BY artwork_id ORDER BY artwork_id) = 1
) AS s
ON t.artwork_id = s.artwork_id
WHEN MATCHED THEN UPDATE SET
    t.raw_payload   = s.raw_payload,
    t._extracted_at = CURRENT_TIMESTAMP(),
    t._batch_id     = s._batch_id,
    t._is_deleted   = FALSE,
    t._deleted_at   = NULL,
    t._deletion_reason = NULL
WHEN NOT MATCHED THEN INSERT (artwork_id, raw_payload, _source_system, _batch_id)
    VALUES (s.artwork_id, s.raw_payload, 'art_institute_chicago', s._batch_id);
```

**Note:** The WHEN MATCHED clause resets `_is_deleted` to FALSE. This handles
the edge case where a previously-deaccessioned artwork reappears in a later
dump (e.g., returned from loan, re-accessioned). The row is "un-deleted"
automatically on the next MERGE.

## Appendix C: Soft-Delete Template (post-snapshot)

```sql
-- soft_delete_deaccessioned.sql (rendered with str.format)
-- Run AFTER the snapshot MERGE completes.
-- Any row whose _batch_id does not match the current snapshot batch was NOT
-- in the dump -> deaccessioned / withdrawn / merged into another record.
UPDATE {target}
SET _is_deleted      = TRUE,
    _deleted_at      = CURRENT_TIMESTAMP(),
    _deletion_reason = 'snapshot_anti_join'
WHERE _batch_id != '{current_batch_id}'
  AND _is_deleted = FALSE;
```

## Appendix D: Comparison to Met Extractor

| Dimension | Met | AIC |
|-----------|-----|-----|
| Initial data source | GitHub CSV (MetObjects.csv, ~500k rows) | S3 tar.bz2 (131k artworks + related entities) |
| Image URL discovery | Per-object API call required (350k calls) | Constructible from `image_id` field (zero API calls) |
| Local state | SQLite (accumulate during multi-hour crawl) | None (re-run from scratch is cheap) |
| Control table | `MET_ENRICHMENT_CONTROL` (lease/claim/status per object) | `AIC_LOAD_WATERMARK` (one row per entity type) |
| Enrichment pattern | Worklist: lease-claim-fetch-callback loop | N/A (dump has everything) |
| File count | 10 Python + 11 SQL | 3 Python + 3 SQL |
| Time to full load | Hours (API throttle at ~40 rps) | Minutes (download + transform + MERGE) |
| Delete detection | Anti-join on `MET_CSV_SNAPSHOT` | Soft-delete via `_batch_id` staleness on `RAW_AIC_ARTWORKS` |
| Deaccession columns | None (Met uses absence from snapshot) | `_is_deleted`, `_deleted_at`, `_deletion_reason` (explicit) |
| Rights gate | `isPublicDomain` in Silver | `is_public_domain` AND `_is_deleted = FALSE` in Silver (double gate) |

## Appendix E: Open Items Remaining (implementation-phase)

These are NOT design decisions -- they are implementation details to resolve
when coding begins:

1. **Tar caching strategy:** How long to keep `data/aic_dump.tar.bz2` on disk?
   (Propose: keep until next `--no-refresh` run overwrites it; `.gitignore` the
   `data/` directory.)
2. **NDJSON chunking:** Should `aic_artworks.ndjson` be split into multiple
   files for parallel COPY INTO? (Propose: single file for v1; revisit if
   COPY INTO takes >30 seconds.)
3. **Temp staging table cleanup:** Use `CREATE TEMPORARY TABLE` (auto-drop on
   session end) or explicit `DROP TABLE` after MERGE? (Propose: TEMPORARY.)
4. **Error handling on download:** Retry logic for the S3 tar download (network
   flap mid-download of 115 MB). (Propose: simple retry with `requests` +
   `stream=True` + resume via `Range` header if supported.)
5. **Progress reporting:** During the 131k JSON-to-NDJSON transform, emit
   progress every N records. (Propose: every 10,000.)
