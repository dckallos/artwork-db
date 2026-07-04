# Smithsonian Open Access Implementation Notes

Verified on 2026-07-04.

This document is an implementation briefing for an AI or human preparing to add Smithsonian
Open Access extraction to this repository. It intentionally avoids choosing an extraction
design. It records source facts, local repository patterns, API behavior, data shapes, and
questions that an implementer will need to resolve.

## Source Links

- [Smithsonian Open Access on AWS Registry](https://registry.opendata.aws/smithsonian-open-access/)
- [Smithsonian Open Access Dev Tools](https://www.si.edu/openaccess/devtools)
- [Smithsonian EDAN Open Access API Docs](https://edan.si.edu/openaccess/apidocs/)
- [Smithsonian Open Access GitHub repository](https://github.com/Smithsonian/OpenAccess)
- [Smithsonian Open Access S3 bucket root](https://smithsonian-open-access.s3-us-west-2.amazonaws.com/)
- [Smithsonian Open Access metadata index](https://smithsonian-open-access.s3-us-west-2.amazonaws.com/metadata/edan/index.txt)
- [EDAN content documentation](https://edan.si.edu/openaccess/docs/)
- [EDAN data model notes](https://edan.si.edu/openaccess/docs/more.html)
- [EDAN object record schema PDF](https://sirismm.si.edu/siris/EDAN_IMM_OBJECT_RECORDS_1.09.pdf)
- [api.data.gov developer manual](https://api.data.gov/docs/)

## Repository Context

The repository already has extraction implementations for the Met and AIC, plus a
YAML-driven Dagster orchestration layer. Smithsonian is partially represented but not yet
implemented.

Relevant local files:

- `extraction/met/README.md`
- `extraction/met/snapshot_loader.py`
- `extraction/met/control_seeder.py`
- `extraction/met/control_enricher.py`
- `extraction/aic/README.md`
- `extraction/aic/loader.py`
- `extraction/aic/config.py`
- `infrastructure/create_bronze_tables.sql`
- `orchestration/artwork_orchestration/sources/met.yaml`
- `orchestration/artwork_orchestration/sources/aic.yaml`
- `orchestration/artwork_orchestration/ADDING_A_SOURCE.md`
- `orchestration/artwork_orchestration/SCHEMA.md`
- `orchestration/artwork_orchestration/factories/assets.py`
- `orchestration/artwork_orchestration/factories/jobs.py`
- `orchestration/artwork_orchestration/factories/schedules.py`
- `transform/dbt/models/staging/met/`
- `transform/dbt/models/staging/aic/`
- `transform/dbt/models/marts/`

Current Smithsonian-specific local state:

- `infrastructure/create_bronze_tables.sql` already defines
  `RAW_SMITHSONIAN_OBJECTS`.
- The inspected working tree includes `env.template` with `SMITHSONIAN_API_KEY`, but that
  file was untracked during this review.
- `Makefile` contains a commented placeholder for `extract-smithsonian`.
- There is no committed `extraction/smithsonian/` package in the inspected tree.
- There is no committed `orchestration/artwork_orchestration/sources/smithsonian.yaml` in
  the inspected tree.
- There are no inspected Smithsonian dbt staging models.

The orchestration prime directive from `AGENTS.md` applies here: source behavior belongs in
YAML and typed configuration, not source-specific branches in framework Python.

## Existing Extraction Patterns

These are observed patterns only. They are not recommendations for Smithsonian.

### Met Pattern

The Met extractor combines a bulk CSV snapshot with bounded API enrichment.

Primary local components:

- `extraction/met/snapshot_loader.py`
- `extraction/met/control_seeder.py`
- `extraction/met/control_enricher.py`
- `extraction/met/README.md`

Observed flow:

1. `snapshot` loads `MetObjects.csv` into `ARTWORK_DB.BRONZE.MET_CSV_SNAPSHOT`.
2. `seed-control` derives an enrichment worklist into `BRONZE.MET_ENRICHMENT_CONTROL`.
3. `enrich-met` leases worklist rows, calls the Met object API for image data, stages image
   payloads, and assembles `RAW_MET_OBJECTS`.
4. A verify-only orchestration step exposes `RAW_MET_OBJECTS` as a downstream source.

Storage characteristics:

- `MET_CSV_SNAPSHOT` preserves the source CSV as JSON-like raw payloads with normalized
  snake_case keys. Typing is deferred to dbt staging models.
- `MET_ENRICHMENT_CONTROL` records enrichment state, attempts, leases, and error details.
- `RAW_MET_OBJECTS` combines CSV-derived object fields and API image fields in one raw
  payload.
- API enrichment is resumable and batch-bounded.

API behavior handled locally:

- Uses synchronous `requests`.
- Treats HTTP 403 and 429 as throttle signals.
- Uses adaptive throttling, a throttle gate, and configurable RPS.
- Uses a required or configurable User-Agent.

Orchestration shape:

- `sources/met.yaml` contains multiple extraction steps.
- The API-bound enrichment step is marked `mode: batched` and `rate_limited: true`.
- Partitioning is by department through a static partition list.
- The final raw table step is verify-only.
- The factory layer consumes generic YAML fields and does not contain Met-specific branches.

Downstream dbt pattern:

- `stg_met__artworks` reads object and artist fields from `raw_payload:csv`.
- `stg_met__images` flattens primary and additional image fields into a long image table.
- `stg_met__artists` parses pipe-delimited artist values into rows and deduplicates them.

### AIC Pattern

The AIC extractor uses a public bulk dump instead of crawling the API for the full snapshot.

Primary local components:

- `extraction/aic/loader.py`
- `extraction/aic/config.py`
- `extraction/aic/README.md`

Observed flow:

1. Download or reuse the AIC tarball dump.
2. Extract selected Tier 1 entities from the archive.
3. Transform source JSON files to gzipped NDJSON.
4. Upload staged files to Snowflake.
5. `COPY` and `MERGE` into Bronze raw tables.
6. Mark stale artworks as soft-deleted.

Storage characteristics:

- `RAW_AIC_ARTWORKS` stores artwork payloads.
- `RAW_AIC_AGENTS` stores artist/agent payloads.
- `AIC_LOAD_WATERMARK` records load metadata.
- Artworks have `_is_deleted`, `_deleted_at`, and `_last_seen_batch_id` style lifecycle
  fields.
- The selected entity list is local extractor configuration, not orchestration framework
  code.

API and data behavior handled locally:

- Full-load behavior comes from a public S3 tarball.
- The API base URL and IIIF base URL are captured in extractor configuration.
- Image URLs are derived in dbt staging from AIC image identifiers and the IIIF URL pattern.

Orchestration shape:

- `sources/aic.yaml` contains one snapshot step.
- The step produces multiple output tables.
- The generic asset factory treats multiple outputs as one multi-asset.

Downstream dbt pattern:

- `stg_aic__artworks` reads typed values from `RAW_AIC_ARTWORKS` and filters out soft-deleted
  rows.
- `stg_aic__artists` reads from `RAW_AIC_AGENTS`.
- `stg_aic__images` creates a long image table from primary and alternate image IDs.

## Existing Orchestration Consumption

The orchestration layer uses YAML source specs to describe extract commands, produced
tables, checks, metadata SQL, jobs, and schedules.

Important observed mechanics:

- A source is added by creating `orchestration/artwork_orchestration/sources/<key>.yaml`.
- Each extraction step names a Python module and subcommand, for example
  `python -m extraction.aic.loader snapshot`.
- `produces` entries map extraction steps to dbt source names and physical Bronze tables.
- Nonempty and freshness checks are configured in YAML.
- Steps can be single-output or multi-output.
- Steps can be marked `mode: batched`.
- Steps can be marked `rate_limited: true`.
- Rate-limited steps can declare an RPS environment variable in YAML.
- `factories/assets.py` builds Dagster assets from the typed config.
- `factories/jobs.py` builds per-source ingest jobs and special bounded enrichment jobs.
- `factories/schedules.py` builds stopped schedules from generic source config.

Important source-decoupling constraint:

- Adding Smithsonian must not require museum-specific branches in
  `orchestration/artwork_orchestration/factories/*.py`.
- New source names, table names, commands, checks, and schedules belong in YAML and existing
  typed config, unless the generic model itself lacks a needed capability.

## Existing Storage And dbt Consumption

Bronze tables use raw payload storage and defer normalization to dbt.

Observed Bronze pattern:

- A natural source key identifies each row.
- `raw_payload VARIANT` preserves source data.
- `_extracted_at`, `_source_system`, and `_batch_id` provide load metadata.
- Some sources add lifecycle fields such as `_is_deleted`.

Current Smithsonian Bronze table:

```sql
CREATE TABLE IF NOT EXISTS RAW_SMITHSONIAN_OBJECTS (
    object_id VARCHAR COMMENT 'Smithsonian record ID (varies by unit)',
    raw_payload VARIANT NOT NULL COMMENT 'Complete raw JSON response',
    _extracted_at TIMESTAMP_NTZ NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    _source_system VARCHAR NOT NULL DEFAULT 'smithsonian',
    _batch_id VARCHAR NOT NULL
)
COMMENT = 'Raw Smithsonian Institution OpenAccess responses.';
```

Observed dbt mart pattern:

- Staging models turn source-specific raw payloads into typed, source-specific staging
  tables.
- Image staging models produce source-specific long image tables.
- Gold models union source-specific staging models into conformed marts.
- `dim_artworks`, `dim_artists`, and `fct_artwork_images` currently contain Met and AIC
  source-specific CTEs.
- `openaccess_catalog` filters public-domain artworks with usable primary image data.

Implementation-relevant implication:

- A Smithsonian extractor can preserve raw source structure in Bronze while dbt staging
  later decides how to map Smithsonian fields into the conformed artwork, artist, and image
  shapes.
- Existing marts would need explicit downstream work before Smithsonian records appear in
  conformed outputs.

## Smithsonian Open Access Overview

Smithsonian Open Access covers millions of collection records and media assets released
under CC0 where eligible. It is interdisciplinary: art, design, history, culture, science,
technology, archives, libraries, and natural history collections are all present.

Key facts from the source documentation:

- The AWS Open Data Registry entry describes the dataset as open access content released by
  Smithsonian, with 2-D and 3-D images plus metadata.
- The AWS Registry lists the S3 bucket as `smithsonian-open-access` in `us-west-2`.
- The AWS Registry says the data is updated weekly.
- The AWS Registry lists the license as CC0.
- The Smithsonian Dev Tools page says collection data is available through GitHub-style JSON
  access, S3 data, and an api.data.gov-hosted API.
- The EDAN docs describe EDAN as the central content repository behind the API.
- The EDAN docs state that the Open Access API exposes more than 11 million objects,
  artifacts, and specimens.
- Not every record with CC0 metadata has downloadable media.
- Metadata and media rights can differ by field and object.

Smithsonian uses the term EDAN for its central content repository. EDAN content is flexible:
records may vary by unit, type, and collection system.

## Bulk Data Access

Primary bulk access is through the public S3 bucket:

```bash
aws s3 ls --no-sign-request s3://smithsonian-open-access/
```

HTTP indexes are also available:

```text
https://smithsonian-open-access.s3-us-west-2.amazonaws.com/metadata/edan/index.txt
```

The GitHub repository currently points users toward S3 for the compressed archive and
metadata files. The repository was observed as archived/read-only in May 2026, so the S3
bucket and Smithsonian docs are the more important current references.

### S3 Metadata Layout

The top-level metadata index lists Smithsonian units. Examples observed in the public index:

| Unit code | Unit name in Smithsonian docs or repository |
| --- | --- |
| `AAA` | Archives of American Art |
| `ACM` | Anacostia Community Museum |
| `CHNDM` | Cooper Hewitt, Smithsonian Design Museum |
| `FSG` | Freer Gallery of Art and Arthur M. Sackler Gallery |
| `HMSG` | Hirshhorn Museum and Sculpture Garden |
| `NMAAHC` | National Museum of African American History and Culture |
| `NMAH` | National Museum of American History |
| `NMAI` | National Museum of the American Indian |
| `NMAfA` | National Museum of African Art |
| `NMNH*` | National Museum of Natural History variants |
| `NPG` | National Portrait Gallery |
| `NPM` | National Postal Museum |
| `NZP` | Smithsonian National Zoological Park |
| `SAAM` | Smithsonian American Art Museum |
| `SIA` | Smithsonian Institution Archives |
| `SIL` | Smithsonian Libraries |

Unit-specific indexes use paths such as:

```text
https://smithsonian-open-access.s3-us-west-2.amazonaws.com/metadata/edan/saam/index.txt
https://smithsonian-open-access.s3-us-west-2.amazonaws.com/metadata/edan/npg/index.txt
https://smithsonian-open-access.s3-us-west-2.amazonaws.com/metadata/edan/chndm/index.txt
```

Observed unit indexes list shard files named `00.txt` through `ff.txt`. Shards contain
line-delimited JSON records.

The OpenAccess repository describes records as distributed by the first two characters of a
content serialization hash. That means shard names are not semantic categories.

### Bulk Record Shape

Observed JSON lines from Smithsonian S3 metadata shards have top-level fields like:

| Field | Meaning or observed role |
| --- | --- |
| `id` | Persistent EDAN identifier, often prefixed by the content type, such as `edanmdm:`. |
| `version` | Record version integer. |
| `unitCode` | Owning Smithsonian unit code, such as `SAAM`, `NPG`, or `CHNDM`. |
| `linkedId` | Optional linked identifier. |
| `type` | EDAN content type, for example `edanmdm` or archive-related types. |
| `content` | Main content body. For collection records, usually includes EDAN sections. |
| `url` | EDAN URL or match key, often close to the record identifier. |
| `hash` | Hash of core fields. |
| `docSignature` | Hash of core and content fields, useful for change detection. |
| `timestamp` | Unix-like timestamp from EDAN. |
| `lastTimeUpdated` | Unix-like timestamp from EDAN. |
| `title` | Top-level title. |

For `edanmdm` collection records, `content` commonly contains:

| Field | Observed role |
| --- | --- |
| `descriptiveNonRepeating` | Non-repeating descriptive fields, including title, source unit, links, and media block. |
| `indexedStructured` | Arrays of indexed values such as date, name, topic, place, object type, and media type. |
| `freetext` | Labeled text arrays grouped by category, such as date, name, credit line, object type, and rights. |

Common `descriptiveNonRepeating` fields:

| Field | Observed role |
| --- | --- |
| `guid` | GUID-like stable link for the record. |
| `title` | Display title. |
| `record_ID` | Unit-specific record identifier, such as `saam_...` or `npg_...`. |
| `unit_code` | Unit code inside the content payload. |
| `title_sort` | Sortable title. |
| `data_source` | Owning collection source label. |
| `record_link` | Public Smithsonian collection page. |
| `metadata_usage.access` | Metadata rights or usage status, often `CC0`. |
| `online_media.media` | Media objects when online media is available. |

Observed `online_media.media[]` fields:

| Field | Observed role |
| --- | --- |
| `id` | Media identifier. |
| `guid` | Media GUID. |
| `type` | Media type label, often `Images`. |
| `idsId` | Smithsonian image delivery service identifier. |
| `usage.access` | Media rights or usage status, often `CC0` for open media. |
| `content` | Delivery service URL. |
| `thumbnail` | Thumbnail URL. |
| `resources` | Alternate media resources and formats. |

Observed media resource labels include:

- `High-resolution TIFF`
- `High-resolution JPEG`
- `Screen Image`
- `Thumbnail Image`

Observed image service URL patterns:

```text
https://ids.si.edu/ids/deliveryService?id=<idsId>
https://ids.si.edu/ids/download?id=<idsId>
```

Implementation-relevant caveat:

- Bulk unit shards can include more than one EDAN content type. For example, public unit
  shards may include archive component records as well as `edanmdm` collection records.

## EDAN API Access

Base URL:

```text
https://api.si.edu/openaccess
```

The API is hosted through api.data.gov and requires an API key.

API key locations supported by api.data.gov:

- `api_key` query parameter
- `X-Api-Key` request header
- HTTP Basic auth username

Default api.data.gov limits documented for APIs using that gateway:

- 1,000 requests per hour per API key.
- `DEMO_KEY` is much lower and is intended only for small tests.
- Rate limit responses can use HTTP 429.
- Responses can include `X-RateLimit-Limit` and `X-RateLimit-Remaining`.

The Smithsonian EDAN docs and the generated API data identify these main endpoints.

### Search

```http
GET /api/v1.0/search
```

Full URL:

```text
https://api.si.edu/openaccess/api/v1.0/search
```

Documented parameters:

| Parameter | Required | Notes |
| --- | --- | --- |
| `q` | Yes | Query string. Supports keywords and fielded terms. |
| `start` | No | Offset, default `0`. |
| `rows` | No | Page size, default `10`, documented range `0` to `1000`. |
| `sort` | No | Allowed values include `id`, `newest`, `updated`, and `random`; default is relevance. |
| `type` | No | Allowed values include `edanmdm`, `ead_collection`, `ead_component`, and `all`; default is `edanmdm`. |
| `row_group` | No | Allowed values include `objects` and `archives`; default is `objects`. |
| `api_key` | Yes, unless sent another way | api.data.gov key. |

Example shape:

```text
GET https://api.si.edu/openaccess/api/v1.0/search?q=unit_code:SAAM&rows=1000&start=0&type=edanmdm&api_key=<key>
```

Documented response shape:

| Field | Notes |
| --- | --- |
| `status` | API status. |
| `responseCode` | Numeric status value in API payload. |
| `response.rows` | Result records. |
| `response.rowCount` | Total matching row count. |
| `message` | Message string. |

Rows contain the same broad EDAN fields as bulk records: `id`, `title`, `unitCode`,
`linkedId`, `type`, `url`, `content`, `hash`, `docSignature`, `timestamp`,
`lastTimeUpdated`, and `version`.

### Category Search

```http
GET /api/v1.0/category/:cat/search
```

Full URL pattern:

```text
https://api.si.edu/openaccess/api/v1.0/category/art_design/search
```

Documented categories:

- `art_design`
- `history_culture`
- `science_technology`

Documented parameters are similar to the main search endpoint:

| Parameter | Required | Notes |
| --- | --- | --- |
| `q` | Yes | Query string. |
| `start` | No | Offset, default `0`. |
| `rows` | No | Page size, default `10`, documented range `0` to `1000`. |
| `sort` | No | Allowed values include `id`, `newest`, `updated`, and `random`. |
| `api_key` | Yes, unless sent another way | api.data.gov key. |

Example shape:

```text
GET https://api.si.edu/openaccess/api/v1.0/category/art_design/search?q=online_media_type:Images&rows=1000&api_key=<key>
```

### Content By Identifier

```http
GET /api/v1.0/content/:id
```

Full URL pattern:

```text
https://api.si.edu/openaccess/api/v1.0/content/<id>
```

Documented parameters:

| Parameter | Required | Notes |
| --- | --- | --- |
| `id` | Yes | Path value. The docs describe this as row ID or URL. |
| `api_key` | Yes, unless sent another way | api.data.gov key. |

Implementation-relevant caveat:

- EDAN IDs often contain punctuation such as `:`. Path identifiers may need URL encoding.

### Terms

```http
GET /api/v1.0/terms/:category
```

Full URL pattern:

```text
https://api.si.edu/openaccess/api/v1.0/terms/unit_code
```

Documented categories:

- `culture`
- `data_source`
- `date`
- `object_type`
- `online_media_type`
- `place`
- `topic`
- `unit_code`

Documented parameters:

| Parameter | Required | Notes |
| --- | --- | --- |
| `category` | Yes | One of the categories above. |
| `starts_with` | No | Prefix filter. |
| `api_key` | Yes, unless sent another way | api.data.gov key. |

This endpoint is important for discovery. It can reveal valid values for unit, object type,
media type, topic, and other indexed fields before an extractor commits to query slices.

### Stats

```http
GET /api/v1.0/stats
```

Full URL:

```text
https://api.si.edu/openaccess/api/v1.0/stats
```

Documented parameter:

| Parameter | Required | Notes |
| --- | --- | --- |
| `api_key` | Yes, unless sent another way | api.data.gov key. |

The docs describe this endpoint as returning statistics for CC0 objects and media.

## Search Query Details

The docs show boolean and fielded query examples.

Observed query forms:

```text
term
term AND other_term
term OR other_term
topic:Gastropoda
unit_code:SAAM
online_media_type:Images
```

Implementation-relevant caveats:

- The API docs do not fully enumerate every searchable field on the endpoint page.
- The terms endpoint is the primary documented way to discover category values.
- EDAN field availability varies by unit and record type.
- Search pagination uses `start` and `rows`, not cursor tokens.
- API search is rate-limited by api.data.gov, while S3 bulk reads are not API-key-gated.

## EDAN Content Model

The EDAN docs describe a generic content wrapper plus registered content schemas.

Top-level EDAN wrapper fields:

| Field | Documentation summary |
| --- | --- |
| `id` | Persistent identifier. |
| `title` | Record title. |
| `unitCode` | Owning or managing unit code. |
| `linkedId` | Linked ID when available. |
| `type` | EDAN data type, such as `edanmdm`. |
| `url` | Normalized key or URL used for matching and lookup. |
| `content` | Schema-specific content. |
| `hash` | Hash over core fields. |
| `docSignature` | Hash over core and content fields. |
| `timestamp` | EDAN timestamp. |
| `lastTimeUpdated` | Last-updated timestamp. |
| `status` | Publishing status. |
| `version` | Version number. |
| `publicSearch` | Public search visibility flag. |
| `extensions` | Additional extension data. |

For museum object records, the primary content type is `edanmdm`.

The EDAN docs identify three major `edanmdm` sections:

- `descriptiveNonRepeating`
- `indexedStructured`
- `freetext`

Important implementation-relevant characteristics:

- `descriptiveNonRepeating` contains many single-value display fields and links.
- `indexedStructured` is better suited to filtering and normalized faceting.
- `freetext` preserves display-label text groups.
- Equivalent concepts can appear in more than one section.
- Some fields are arrays even when they contain one value.
- Some fields are absent for many records.
- Natural identifiers exist at multiple levels: EDAN `id`, EDAN `url`, unit `record_ID`,
  `guid`, media `id`, and media `idsId`.

## Smithsonian Units Most Relevant To Artwork

Smithsonian Open Access includes many non-art collections. Artwork-focused implementation
research will likely inspect at least these units:

| Unit code | Why it may matter |
| --- | --- |
| `SAAM` | Smithsonian American Art Museum. |
| `NPG` | National Portrait Gallery. |
| `CHNDM` | Cooper Hewitt, Smithsonian Design Museum. |
| `FSG` | Freer and Sackler Asian art collections. |
| `HMSG` | Hirshhorn modern and contemporary art. |
| `NMAfA` | National Museum of African Art. |
| `NMAI` | Art and cultural objects from National Museum of the American Indian. |
| `NMAAHC` | Art, culture, history, and media records. |
| `ACM` | Art, culture, and community collections. |

This table is not a scope decision. It is a list of units worth researching before a scope is
chosen.

## Rights And Media Fields

Implementation-relevant source facts:

- Smithsonian Open Access is centered on CC0 release of eligible metadata and media.
- Some records expose CC0 metadata but do not include downloadable media.
- Media availability is usually visible through `descriptiveNonRepeating.online_media`.
- Media usage can be represented under `online_media.media[].usage.access`.
- Metadata usage can be represented under `descriptiveNonRepeating.metadata_usage.access`.
- Indexed media type can be represented through `indexedStructured.online_media_type`.
- Freetext rights can appear under groups such as `objectRights`.

Fields an implementer may need to compare:

| Field path | Usefulness |
| --- | --- |
| `content.descriptiveNonRepeating.metadata_usage.access` | Metadata usage statement. |
| `content.descriptiveNonRepeating.online_media.media[].usage.access` | Per-media usage statement. |
| `content.descriptiveNonRepeating.online_media.media[].content` | Delivery service URL. |
| `content.descriptiveNonRepeating.online_media.media[].thumbnail` | Thumbnail URL. |
| `content.descriptiveNonRepeating.online_media.media[].resources[]` | Alternate downloadable resources. |
| `content.indexedStructured.online_media_type[]` | Indexed media availability/type. |
| `content.freetext.objectRights[]` | Display rights text. |

Open questions for implementation:

- Which rights field is authoritative for Bronze filtering, if any?
- Are non-media records in scope for raw storage?
- Are media resources stored exactly as source payload only, separately normalized, or
  both?
- Are high-resolution downloadable resources ingested, linked, or ignored?

## API And Bulk Access Comparison

This comparison lists facts for later design work. It does not choose an approach.

| Dimension | API access | S3 bulk access |
| --- | --- | --- |
| Authentication | Requires api.data.gov key. | Public bucket can be read without AWS credentials. |
| Rate limits | api.data.gov default limit applies unless Smithsonian grants different terms. | No EDAN API key limit; S3 throughput and politeness still matter. |
| Querying | Server-side search by query, category, type, sort, and terms. | Client-side filtering after reading shards. |
| Pagination | `start` plus `rows`, max documented `rows=1000`. | Shard files, line-delimited JSON. |
| Update signal | Sort by `updated`; fields include `lastTimeUpdated` and `docSignature`. | Weekly data refresh; records include `lastTimeUpdated` and `docSignature`. |
| Full snapshot | Possible but API call volume may be high. | Designed for bulk access. |
| Selective unit reads | Search query can filter by unit fields. | Unit directories can be read directly. |
| Error behavior | HTTP/API gateway errors, including 429. | HTTP/S3 transfer errors and partial reads. |

## Implementation Questions For The Next AI

These are questions to answer before coding. They are intentionally not answered here.

1. Is the first Smithsonian load intended to be a full Open Access snapshot, an art/design
   subset, or selected Smithsonian units?
2. Is the primary source of truth expected to be EDAN API search, EDAN content lookup, S3
   bulk metadata shards, or a combination?
3. Does the extractor rely on the existing `RAW_SMITHSONIAN_OBJECTS` table shape, or is
   more Bronze schema needed before implementation?
4. Which identifier is the Bronze natural key: EDAN `id`, EDAN `url`, unit
   `record_ID`, `guid`, or another value?
5. How are archive records such as `ead_collection` and `ead_component` handled if
   they appear in selected units?
6. Are records without `online_media.media` stored?
7. Are records with non-CC0 media but CC0 metadata stored?
8. Is unit-scoped extraction represented as partitions, separate steps, or another
   YAML-supported shape?
9. Does the existing orchestration typed model already support the desired Smithsonian load
   shape without framework changes?
10. Is `SMITHSONIAN_API_KEY` required for all runs, only API runs, or not used for S3
    bulk runs?
11. What RPS limit and retry behavior are appropriate for EDAN API calls under api.data.gov?
12. Does delta detection use `lastTimeUpdated`, `timestamp`, `docSignature`, a shard
    manifest, or Snowflake comparison against raw payloads?
13. Are image URLs from `ids.si.edu` preserved only, validated, enriched, or normalized
    in dbt?
14. Does downstream dbt stage Smithsonian artists, artworks, and images from
    `descriptiveNonRepeating`, `indexedStructured`, `freetext`, or a combination?
15. How do Smithsonian source units map into conformed `source_system` and museum labels
    in marts?

## Local Implementation Surface To Inspect Before Coding

An AI implementing Smithsonian needs current context from these files immediately before
editing:

| File | Reason |
| --- | --- |
| `orchestration/artwork_orchestration/ADDING_A_SOURCE.md` | Source addition checklist and contract. |
| `orchestration/artwork_orchestration/SCHEMA.md` | YAML schema fields and semantics. |
| `orchestration/artwork_orchestration/sources/met.yaml` | Multi-step, batched, rate-limited source pattern. |
| `orchestration/artwork_orchestration/sources/aic.yaml` | Single-step, multi-output snapshot pattern. |
| `orchestration/artwork_orchestration/factories/assets.py` | How CLI commands, env, partitions, metadata, and checks are consumed. |
| `orchestration/artwork_orchestration/factories/jobs.py` | How source jobs and bounded enrichment jobs are assembled. |
| `orchestration/artwork_orchestration/factories/schedules.py` | How schedules are inferred from source config. |
| `infrastructure/create_bronze_tables.sql` | Current raw Smithsonian table definition. |
| `transform/dbt/models/staging/met/` | Example raw-to-staging mapping for Met. |
| `transform/dbt/models/staging/aic/` | Example raw-to-staging mapping for AIC. |
| `transform/dbt/models/marts/` | Current conformed mart union pattern. |

## Useful API Exploration Commands

These commands are examples for discovery only. They are not an implementation plan.

List the public S3 bucket:

```bash
aws s3 ls --no-sign-request s3://smithsonian-open-access/
```

Fetch the unit index over HTTPS:

```bash
curl -fsSL https://smithsonian-open-access.s3-us-west-2.amazonaws.com/metadata/edan/index.txt
```

Fetch a unit shard index:

```bash
curl -fsSL https://smithsonian-open-access.s3-us-west-2.amazonaws.com/metadata/edan/saam/index.txt
```

Preview one JSON-lines shard:

```bash
curl -fsSL https://smithsonian-open-access.s3-us-west-2.amazonaws.com/metadata/edan/saam/00.txt | head
```

Search the API for SAAM records:

```bash
curl -fsSL "https://api.si.edu/openaccess/api/v1.0/search?q=unit_code:SAAM&rows=10&type=edanmdm&api_key=$SMITHSONIAN_API_KEY"
```

Discover unit-code terms:

```bash
curl -fsSL "https://api.si.edu/openaccess/api/v1.0/terms/unit_code?api_key=$SMITHSONIAN_API_KEY"
```

Fetch stats:

```bash
curl -fsSL "https://api.si.edu/openaccess/api/v1.0/stats?api_key=$SMITHSONIAN_API_KEY"
```

## Documentation Sources For Further Research

- [Smithsonian Open Access main page](https://www.si.edu/openaccess)
- [Smithsonian Open Access Dev Tools](https://www.si.edu/openaccess/devtools)
- [Smithsonian EDAN API docs](https://edan.si.edu/openaccess/apidocs/)
- [Smithsonian EDAN docs index](https://edan.si.edu/openaccess/docs/)
- [EDAN data model notes](https://edan.si.edu/openaccess/docs/more.html)
- [EDAN object record schema PDF](https://sirismm.si.edu/siris/EDAN_IMM_OBJECT_RECORDS_1.09.pdf)
- [AWS Registry entry](https://registry.opendata.aws/smithsonian-open-access/)
- [S3 metadata index](https://smithsonian-open-access.s3-us-west-2.amazonaws.com/metadata/edan/index.txt)
- [OpenAccess repository](https://github.com/Smithsonian/OpenAccess)
- [api.data.gov docs](https://api.data.gov/docs/)
