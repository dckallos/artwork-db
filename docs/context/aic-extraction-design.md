# AIC Extraction Layer -- Design Document

> **Status:** Design (not yet implemented). Written 2026-06-07.
> **Branch:** `donkey-kong-sandbox`
> **Audience:** Owner + next-window Cortex sessions.
> **Companion:** `docs/prompts/AIC_EXTRACTION_DESIGN_PROMPT.md` (the brief that
> produced this document).

---

## 1. Ingestion Strategy

### Decision: Hybrid (bulk snapshot + API delta)

| Path | Mechanism | Volume | Warehouse cost | Freshness | Complexity |
|------|-----------|--------|---------------|-----------|------------|
| **A: S3 data dump** | Download `artic-api-data.tar.bz2` (~115 MB), extract, transform to NDJSON, COPY+MERGE into Bronze | 131k artworks + 15k agents (Tier 1) | ~10-20 warehouse-seconds (XS, COPY INTO + MERGE) | Monthly (dump updated monthly per README) | Low (one download, local transform, one MERGE) |
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

### Data flow (snapshot path)

```
artic-api-data.tar.bz2 (S3)
  |
  v  [download + extract locally, ~2 min]
json/artworks/*.json  +  json/agents/*.json
  |
  v  [Python: read each .json, emit NDJSON lines]
data/aic_artworks.ndjson  +  data/aic_agents.ndjson
  |
  v  [PUT to @BRONZE_LOAD_STAGE/aic/]
Snowflake internal stage
  |
  v  [COPY INTO temp staging table]
  |
  v  [MERGE INTO AIC_SNAPSHOT / RAW_AIC_AGENTS keyed on PK]
Bronze tables (idempotent, one row per entity)
```

### Data flow (delta path)

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

### Design principles (aligned to Met pattern)

1. **Bronze = land, don't interpret.** Store the complete API/dump JSON as
   `VARIANT`. Never reshape or filter here.
2. **All records loaded** -- both `is_public_domain = true` and `false`. The
   public-domain gate applies to **image URL construction in Silver/Gold only**,
   not to Bronze landing.
3. **MERGE, not append.** Primary key declares uniqueness intent; the MERGE
   load pattern enforces it at runtime (Snowflake does not enforce PK/UNIQUE).
4. **Delete-propagation via snapshot anti-join.** Objects present in a prior
   snapshot but absent from the current dump are detected as deaccessions.
5. **Naming convention:** `RAW_AIC_{SOURCE_ENTITY_NAME}` in Bronze (preserves
   the source API's vocabulary). Human-readable renames happen in Silver.

### Proposed DDL

#### AIC_SNAPSHOT (new -- peer to MET_CSV_SNAPSHOT)

The authoritative full-dump landing table. One row per artwork, keyed on
`artwork_id`. Supports re-runnable MERGE loads and deaccession detection.

```sql
-- In infrastructure/create_bronze_tables.sql (append or new file)
CREATE TABLE IF NOT EXISTS AIC_SNAPSHOT (
    artwork_id      INT             NOT NULL
        COMMENT 'AIC API artwork id (from data dump); PK -> one row per artwork',
    raw_payload     VARIANT         NOT NULL
        COMMENT 'Complete raw JSON from the data dump (one file per artwork)',
    _extracted_at   TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP()
        COMMENT 'UTC timestamp the snapshot row was landed',
    _source_system  VARCHAR         NOT NULL DEFAULT 'art_institute_chicago'
        COMMENT 'Source system identifier',
    _batch_id       VARCHAR         NOT NULL
        COMMENT 'UUID identifying the extraction batch',
    CONSTRAINT pk_aic_snapshot PRIMARY KEY (artwork_id)
)
COMMENT = 'Raw AIC data-dump snapshot (full artworks, VARIANT). One row per artwork_id (PK). Feeds delta detection + deaccession anti-join.';
```

#### RAW_AIC_ARTWORKS (exists -- add PK constraint)

The existing table in `create_bronze_tables.sql` becomes the target for
**API delta loads** (incremental upserts between dump refreshes). Propose
adding a PK constraint for optimizer hints and consistency:

```sql
-- Idempotent ALTER to add PK to existing table:
ALTER TABLE IF EXISTS RAW_AIC_ARTWORKS
    ADD CONSTRAINT pk_raw_aic_artworks PRIMARY KEY (artwork_id);
```

**Design note:** Two artwork tables (`AIC_SNAPSHOT` vs `RAW_AIC_ARTWORKS`)
mirrors the Met pattern (`MET_CSV_SNAPSHOT` vs `RAW_MET_OBJECTS`). The
snapshot is the complete truth from the bulk dump; the raw table accumulates
API-sourced enrichments/deltas. Silver reconciles them.

#### RAW_AIC_AGENTS (new)

```sql
CREATE TABLE IF NOT EXISTS RAW_AIC_AGENTS (
    agent_id        INT             NOT NULL
        COMMENT 'AIC API agent id; includes artists, donors, collectors',
    raw_payload     VARIANT         NOT NULL
        COMMENT 'Complete raw JSON from agents/ data dump',
    _extracted_at   TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP()
        COMMENT 'UTC timestamp of extraction',
    _source_system  VARCHAR         NOT NULL DEFAULT 'art_institute_chicago'
        COMMENT 'Source system identifier',
    _batch_id       VARCHAR         NOT NULL
        COMMENT 'UUID identifying the extraction batch',
    CONSTRAINT pk_raw_aic_agents PRIMARY KEY (agent_id)
)
COMMENT = 'Raw AIC agents (artists + non-artists). One row per agent_id (PK). Filter is_artist in Silver.';
```

#### Naming rationale

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
        merge_aic_snapshot.sql      # MERGE INTO AIC_SNAPSHOT (template)
        merge_aic_artworks.sql      # MERGE INTO RAW_AIC_ARTWORKS (delta path)
        merge_aic_agents.sql        # MERGE INTO RAW_AIC_AGENTS (template)
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
| `snapshot` | Download the S3 data dump, extract Tier 1 entities, transform to NDJSON, MERGE into Bronze snapshot tables | `--no-refresh` (reuse cached tar), `--limit N` (cap records for smoke test), `--entities artworks,agents` (select which to load) |
| `delta` | Query the API for records changed since the watermark, MERGE into `RAW_AIC_ARTWORKS` | `--since YYYY-MM-DD` (override watermark), `--limit N` (cap pages), `--dry-run` (fetch but don't upload) |
| `status` | Print current watermark, row counts, last batch timestamp | (none) |

### Example usage

```bash
# Initial full load (first time)
python -m extraction.aic.run snapshot

# Incremental update (between monthly dumps)
python -m extraction.aic.run delta

# Smoke test (5 records only)
python -m extraction.aic.run snapshot --limit 5

# Check pipeline state
python -m extraction.aic.run status
```

---

## 6. Delta / Freshness Strategy

### Watermark table: `AIC_LOAD_WATERMARK`

A minimal one-row-per-entity control table tracking the high-water mark for
incremental API queries:

```sql
CREATE TABLE IF NOT EXISTS AIC_LOAD_WATERMARK (
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

### Delta detection mechanism

The AIC API supports Elasticsearch range queries on `source_updated_at`:

```
GET /api/v1/artworks/search?query[range][source_updated_at][gte]=2025-01-01
    &sort[source_updated_at][order]=asc
    &limit=100&page=1&fields=id,title,image_id,...
```

The loader:
1. Reads `last_source_updated_at` from `AIC_LOAD_WATERMARK` for entity `artworks`.
2. Queries the API with that timestamp as the `gte` bound.
3. Paginates until exhausted (or `--limit` cap hit).
4. MERGEs results into `RAW_AIC_ARTWORKS`.
5. Updates the watermark to `max(source_updated_at)` from the batch.

### Snapshot refresh cadence

The S3 dump is updated monthly. The `snapshot` subcommand should be re-run
monthly (or whenever the owner wants a full reconciliation / deaccession
check). Between dumps, `delta` keeps Bronze fresh.

### Delete-propagation (deaccession detection)

On each `snapshot` run, after the MERGE completes:
- **Deaccessioned artworks** = rows in `AIC_SNAPSHOT` whose `artwork_id` does
  NOT appear in the current dump's set of IDs.
- Detection query (run post-MERGE):

```sql
-- Detect deaccessioned artworks (present in prior snapshot, absent from current load)
SELECT s.artwork_id, s.raw_payload:title::STRING AS title
FROM BRONZE.AIC_SNAPSHOT s
WHERE s._batch_id != '<current_batch_id>'
  AND s.artwork_id NOT IN (
      SELECT artwork_id FROM BRONZE.AIC_SNAPSHOT WHERE _batch_id = '<current_batch_id>'
  );
```

**Note:** This query works because the MERGE updates `_batch_id` for all
matched rows. Any row still carrying the old `_batch_id` after MERGE was NOT
in the current dump -- i.e., it was removed (deaccessioned, merged, or
withdrawn).

**Alternative (cleaner):** Track a `_last_seen_batch_id` column and soft-delete
rows not seen in the latest batch. Design decision deferred to implementation --
both approaches work.

---

## 7. Image URL Handling

### Decision: Store `image_id` in Bronze; compute IIIF URL in Silver

**Bronze:** The raw payload already contains `image_id` (a UUID string). No
transformation needed. Land as-is inside the VARIANT blob.

**Silver:** Compute the full IIIF URL as a derived column:

```sql
-- In a Silver model (dbt or DDL)
CASE
    WHEN raw_payload:is_public_domain::BOOLEAN = TRUE
         AND raw_payload:image_id::STRING IS NOT NULL
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
- **Enforcement point:** Silver. Bronze stores everything; Silver applies the
  gate. This keeps Bronze as an uninterpreted, replayable source of truth.

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

## 8. Cross-Source Entity Resolution (Forward-Looking)

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

## 9. Open Questions (Require Owner Input Before Implementation)

| # | Question | Options | Impact |
|---|----------|---------|--------|
| **OQ-1** | Should `snapshot` load the full tar.bz2 (all 27 entity folders) and just MERGE Tier 1, or only extract Tier 1 folders from the tar? | A: Extract all, load Tier 1 (simpler tar handling). B: Selective extraction (saves disk but more complex tar logic). | Disk usage during extraction (~2.5 GB vs ~1 GB). |
| **OQ-2** | Two-table pattern (`AIC_SNAPSHOT` + `RAW_AIC_ARTWORKS`) vs single table? The Met has this split because CSV snapshot and API enrichment are fundamentally different data. For AIC, the dump and API return the same shape. | A: Two tables (mirrors Met; snapshot for delete-detection, raw for deltas). B: Single table with MERGE from both paths (simpler; delete-detection via `_batch_id` staleness). | DDL complexity, Silver reconciliation logic. |
| **OQ-3** | Should the delta path also update `AIC_SNAPSHOT`, or only `RAW_AIC_ARTWORKS`? | A: Delta updates both (single source of truth). B: Delta only touches raw; snapshot is only refreshed on full dump re-run (cleaner separation). | Deaccession detection accuracy between dump refreshes. |
| **OQ-4** | Soft-delete strategy for deaccessioned artworks. | A: Add `_is_deleted BOOLEAN` + `_deleted_at TIMESTAMP` to snapshot table. B: Move to a separate `AIC_DEACCESSIONED` table. C: Just flag in Silver (don't mutate Bronze). | Whether Bronze ever mutates post-land. Option C is purest medallion. |
| **OQ-5** | Should we load the `getting-started/allArtworks.jsonl` file (single JSONL, key fields only) as a lightweight alternative to extracting 131k individual JSON files? | A: Use individual JSONs (complete data, nothing lost). B: Use JSONL shortcut (faster, but fewer fields). C: Try JSONL first, fall back to individual JSONs if fields are insufficient. | Load speed vs data completeness. |
| **OQ-6** | Frequency of `delta` runs -- manual only, or schedule a Snowflake Task? | A: Manual (`python -m extraction.aic.run delta`). B: Snowflake Task calling an external function / stored proc. C: Decide later after v1 works. | Automation complexity. |

---

## 10. Summary of Decisions

| # | Decision | Choice | Key rationale |
|---|----------|--------|---------------|
| D-1 | Ingestion strategy | Hybrid (dump + API delta) | Completeness + freshness; no per-object API calls needed. |
| D-2 | Tier 1 entities | artworks + agents | Core analytical value; cross-source join on ULAN. |
| D-3 | Bronze table naming | `RAW_AIC_AGENTS` (source vocab) | Bronze preserves API semantics; Silver renames to `AIC_ARTISTS`. |
| D-4 | Load semantics | MERGE keyed on PK | Idempotent, supports delete-detection, matches Met pattern. |
| D-5 | `is_public_domain` gate | Silver (not Bronze) | Bronze lands everything; Silver applies rights filtering for image URLs. |
| D-6 | Image URLs | Compute in Silver from `image_id` | No API call needed; simple string construction with `is_public_domain` gate. |
| D-7 | SQLite | None | No multi-hour crawl; re-run from scratch is cheap (~2 min). |
| D-8 | Entity resolution | ULAN primary key; fuzzy name+dates fallback | Both sources expose ULAN; Gold `DIM_ARTISTS` unifies. |
| D-9 | File count target | 3 Python + 3 SQL | Dramatically simpler than Met's 10-file architecture. |

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
AIC_DUMP_ENTITY_FOLDERS = ["artworks", "agents"]
```

## Appendix B: MERGE Template (snapshot path)

```sql
-- merge_aic_snapshot.sql (rendered with str.format)
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
    t._batch_id     = s._batch_id
WHEN NOT MATCHED THEN INSERT (artwork_id, raw_payload, _source_system, _batch_id)
    VALUES (s.artwork_id, s.raw_payload, 'art_institute_chicago', s._batch_id);
```

## Appendix C: Comparison to Met Extractor

| Dimension | Met | AIC |
|-----------|-----|-----|
| Initial data source | GitHub CSV (MetObjects.csv, ~500k rows) | S3 tar.bz2 (131k artworks + related entities) |
| Image URL discovery | Per-object API call required (350k calls) | Constructible from `image_id` field (zero API calls) |
| Local state | SQLite (accumulate during multi-hour crawl) | None (re-run from scratch is cheap) |
| Control table | `MET_ENRICHMENT_CONTROL` (lease/claim/status per object) | `AIC_LOAD_WATERMARK` (one row per entity type) |
| Enrichment pattern | Worklist: lease-claim-fetch-callback loop | N/A (dump has everything) |
| File count | 10 Python + 11 SQL | 3 Python + 3 SQL |
| Time to full load | Hours (API throttle at ~40 rps) | Minutes (download + transform + MERGE) |
| Delete detection | Anti-join on `MET_CSV_SNAPSHOT` | Anti-join on `AIC_SNAPSHOT` (same pattern) |
