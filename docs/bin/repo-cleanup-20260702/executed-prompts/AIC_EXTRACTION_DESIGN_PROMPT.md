# Art Institute of Chicago: Extraction Layer Design

## Your Role

You are a **Senior Data Engineer** experienced in Python ETL pipelines, REST API
integration, Snowflake Medallion architecture (Bronze/Silver/Gold), and
museum-domain data modeling. You are pairing with the repo owner as a mentor:
explain tradeoffs and propose options, but the owner decides. Keep the design
simpler than the Met extractor (2-3 files, not 10) while being comprehensive
and correct.

## Repository

- Repo: `github.com/dckallos/artwork-db` (branch: `donkey-kong-sandbox`)
- Target location: `extraction/aic/` (new directory, peer to `extraction/met/`)
- Run: `cd ~/dev/artwork-db && python -m extraction.aic.run <subcommand>`
- Snowflake: `ARTWORK_DB.BRONZE` schema, `ARTWORK_LOADER` role, key-pair auth

## Context

The Art Institute of Chicago (AIC) provides **two complementary data paths**:

### Path A: Nightly S3 Data Dump (bulk, ~131k artworks + related entities)

- URL: `https://artic-api-data.s3.amazonaws.com/artic-api-data.tar.bz2`
- Updated **monthly** (per the README; docs say nightly but README says monthly)
- ~115 MB compressed, ~2.5 GB extracted
- Structure: `json/{endpoint}/{id}.json` -- one file per record
- Contains 27 entity folders (see "Data dump folders" below)
- Also: `getting-started/allArtworks.jsonl` (all artworks, key fields, JSONL)
- License: per-record `info.license_text` field; images separate (CC0 for public domain)

### Path B: Live REST API (per-record, paginated, searchable)

- Base: `https://api.artic.edu/api/v1`
- Pagination: 12 records/page default, configurable via `?limit=100&page=N`
- Field selection: `?fields=id,title,image_id,...` (sparse responses)
- Elasticsearch search: `/artworks/search?query[term][is_public_domain]=true`
- Delta detection: `source_updated_at` field + range query on search endpoint:
  `?query[range][source_updated_at][gte]=now-7d&sort[source_updated_at][order]=desc`
- Rate limiting: Not explicitly documented; avg response ~722ms; no known
  aggressive throttling (unlike the Met's 403 storm)
- No API key required

### Image URLs (IIIF 2.0)

Images are NOT in the data dump. They are served via IIIF:

```
{iiif_url}/{image_id}/full/{width},/0/default.jpg
```

Where:
- `iiif_url` = `https://www.artic.edu/iiif/2` (from `config.json`)
- `image_id` = UUID from the artwork record (e.g., `7b7a6f39-1cd8-ea2f-9811-18b0e23edac0`)
- `width` = `843` (recommended) or `1686` (only if needed)
- Full URL example: `https://www.artic.edu/iiif/2/7b7a6f39-1cd8-ea2f-9811-18b0e23edac0/full/843,/0/default.jpg`

The `image_id` is already embedded in the artwork record. **No second API call is
needed to discover image URLs** -- just construct the IIIF URL from the image_id
field. This is a massive simplification vs. the Met (which requires a per-object
API call to discover image URLs).

### Data dump folders (27 entity types)

**Core collection data (highest priority for Medallion):**
- `artworks/` -- 131k+ records, ~5KB each. Primary entity.
- `agents/` -- Artists, donors, collectors. Has `is_artist` boolean.
- `exhibitions/` -- Historical exhibitions (6,500+)
- `images/` -- Image metadata records (separate from IIIF URLs)
- `places/` -- Geographic origins
- `galleries/` -- Physical gallery locations within the museum
- `category-terms/` -- Taxonomy terms (subjects, materials, techniques)
- `artwork-types/` -- Classification (Painting, Sculpture, Print, etc.)
- `artwork-date-qualifiers/` -- Qualifier on date (Made, Designed, Published)
- `artwork-place-qualifiers/` -- Qualifier on place of origin

**Secondary/reference data:**
- `agent-roles/` -- Role taxonomy for agents
- `agent-types/` -- Type taxonomy for agents (Individual, Corporate Body, etc.)

**Website/CMS content (lower priority, maybe skip in v1):**
- `articles/`, `digital-publications/`, `digital-publication-articles/`
- `educator-resources/`, `events/`, `event-occurrences/`, `event-programs/`
- `generic-pages/`, `highlights/`, `mobile-sounds/`, `press-releases/`
- `printed-publications/`, `products/`, `publications/`, `sections/`
- `sites/`, `sounds/`, `static-pages/`, `texts/`, `tours/`, `videos/`

### Sample artwork payload (key fields)

```json
{
    "id": 11,
    "api_model": "artworks",
    "title": "Self-Portrait",
    "date_start": 1878,
    "date_end": 1878,
    "date_display": "1878",
    "artist_display": "Walter Shirlaw\nAmerican, 1838-1909",
    "place_of_origin": "United States",
    "medium_display": "Oil on canvas",
    "dimensions": "70.2 x 53.4 cm (27 5/8 x 21 in.)",
    "credit_line": "Gift of Joseph M. Rogers",
    "is_public_domain": true,
    "is_on_view": false,
    "department_title": "Arts of the Americas",
    "department_id": "PC-3",
    "artwork_type_title": "Painting",
    "artwork_type_id": 1,
    "artist_id": 36656,
    "artist_title": "Walter Shirlaw",
    "classification_id": "TM-9",
    "classification_title": "painting",
    "category_ids": ["PC-3"],
    "category_titles": ["Arts of the Americas"],
    "term_titles": ["painting", "oil paint (paint)", "self-portraits"],
    "image_id": "7b7a6f39-1cd8-ea2f-9811-18b0e23edac0",
    "alt_image_ids": ["3b212d9c-cac1-d846-367d-68ca6cd6c74f"],
    "source_updated_at": "2023-12-07T14:12:37-06:00",
    "updated_at": "2024-12-12T18:41:56-06:00",
    "timestamp": "2025-02-16T00:21:59-06:00"
}
```

### Sample agent payload

```json
{
    "id": 135,
    "api_model": "agents",
    "title": "Gertrude Abercrombie",
    "sort_title": "Abercrombie, Gertrude",
    "is_artist": true,
    "birth_date": 1909,
    "death_date": 1977,
    "description": "<p>A leading figure of Chicago's Hyde Park arts scene...</p>",
    "source_updated_at": "2024-05-02T12:28:49-05:00",
    "updated_at": "2024-12-15T23:24:05-06:00"
}
```

## Existing Met Extractor (for pattern reference, not for copying)

The Met extractor grew organically to ~10 files because:
1. Met requires a per-object API call to discover image URLs (slow, 350k calls)
2. SQLite is used as a local accumulator during the multi-hour crawl
3. A control-table pattern in Snowflake drives worklist prioritization
4. Separate bootstrap (CSV) vs. enrichment (API) vs. upload phases

**AIC is fundamentally simpler** because:
1. The S3 data dump gives you EVERYTHING in one download (~2 min)
2. Image URLs are constructible from `image_id` -- no API calls needed
3. Delta detection uses a single paginated API query (not per-object)
4. No multi-hour crawl means no need for SQLite as local state

## What to Design (Scope of This Session)

The owner wants you to make **design decisions** for the AIC extraction layer.
Produce a concrete design document covering:

### 1. Ingestion Strategy Decision

Choose between (or combine) the two paths:
- **Bulk-first**: Download the S3 tar.bz2, extract, load all JSON into Bronze
- **API-incremental**: Paginate through the API, load page-by-page
- **Hybrid**: Bulk for initial load, API delta queries for ongoing updates

For each option, state: volume, cost (warehouse seconds), complexity, freshness.
Recommend one and explain why.

### 2. Entity Scope Decision

Which of the 27 entity types to load in v1? Recommend a tiered approach:
- **Tier 1** (load immediately): artworks + ???
- **Tier 2** (load next): ???
- **Tier 3** (skip for now): ???

Justify based on: analytical value, cross-source join potential (Met <-> AIC),
entity-resolution relevance, and volume.

### 3. Bronze Table Design

For each Tier 1 entity, propose the Bronze table DDL:
- Table name convention (e.g., `RAW_AIC_ARTWORKS`)
- Column strategy: single VARIANT column (raw JSON) vs. typed columns?
- Timestamp/audit columns for SCD tracking
- Key/clustering choices

### 4. File Layout

Propose the `extraction/aic/` directory structure. Target: 2-4 Python files max.
Must support:
- `python -m extraction.aic.run snapshot` (bulk load from S3 dump)
- `python -m extraction.aic.run delta` (incremental from API)
- Config via `.env` (same pattern as Met)
- Upload to Snowflake Bronze via COPY INTO

### 5. Delta/Freshness Strategy

How to detect what changed since last load:
- The API has `source_updated_at` with range queries
- The dump has `timestamp` on each record
- What goes into a Snowflake control table? (Keep it minimal)

### 6. Image URL Handling

Since image URLs are constructible (no API call), where in the pipeline do we
materialize them? Bronze (store `image_id` only) vs. Silver (compute IIIF URL)?
What about the `iiif_url` base -- hardcode or store from `config.json`?

### 7. Cross-Source Entity Resolution (Forward-Looking)

Both Met and AIC have artists. The Met has `artist_display_name` + ULAN IDs.
AIC has `agents` with `ulan_id` (nullable) + `title` (name). How will we
reconcile the same artist across sources in Gold? Just flag the question and
propose a column/strategy -- don't implement yet.

## Constraints

- No warehouse time during bulk download (fetch to local disk, then COPY INTO)
- Use `requests` library (no aiohttp) -- same as Met extractor
- Key-pair auth to Snowflake (ARTWORK_LOADER_SVC, same as Met)
- Simpler than the Met extractor: fewer files, no SQLite, no multi-hour crawl
- Must handle the `is_public_domain` gate correctly (images are CC0 ONLY when
  `is_public_domain` is true)
- The design must support delete-propagation (if an artwork disappears from the
  dump, the pipeline must detect and mark it)

## Anti-Patterns to Avoid

- Don't build a generic "museum API framework" -- just build the AIC loader
- Don't store the full 2.5GB extracted tar on Snowflake stages -- JSONL or
  NDJSON the records for COPY INTO, discard the individual .json files
- Don't call the API per-object for data that's already in the dump
- Don't over-normalize in Bronze -- that's Silver/Gold's job
- Don't add SQLite -- there's no multi-hour crawl to accumulate through
- Don't skip `is_public_domain` -- it gates image usage rights

## Deliverable

A markdown design document (`docs/context/aic-extraction-design.md`) with:
1. Each of the 7 decisions above, with the chosen option and rationale
2. Proposed DDL for Bronze tables (Tier 1 entities)
3. Proposed file layout for `extraction/aic/`
4. A CLI interface spec (`run.py` subcommands)
5. A diagram or pseudocode showing the data flow for both snapshot and delta paths
6. Open questions that need owner input before implementation
