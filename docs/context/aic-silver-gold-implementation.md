# AIC Silver/Gold Implementation Design

> **Status: ACTIVE -- implemented architecture reference.**
> Supersedes the legacy AIC design archived under `docs/bin/repo-cleanup-20260702/stale-context/aic-dbt-silver-gold-design.md`.
>
> Decisions are LOCKED unless explicitly marked OPEN. Each swim lane is
> independently implementable. File creation order at the bottom.

---

## Locked Decisions (cross-cutting)

| ID | Decision | Rationale |
|----|----------|-----------|
| D1 | `source_system = 'art_institute_chicago'` everywhere | Matches Bronze DDL default; self-documenting in Gold results |
| D2 | Entity resolution v1 = source-partitioned (Option D) | Avoids false merges; ULAN coverage unproven at scale |
| D3 | UNION location = Gold-level CTEs (not intermediates) | Appropriate at 2 sources; extract to `int_*` at source #4 |
| D4 | Met soft-delete = accept asymmetry, document in SQL | Retrofit when Met extraction adds deaccession detection |
| D5 | Gold filters by `is_artist`; staging passes all agents | Maximum flexibility; Gold owns business logic |
| D6 | `stg_aic__images` carries raw UUID (`source_image_id`) through to Gold | Enables downstream IIIF variants; remove if proven noise |
| D7 | Thumbnail metadata lives on `stg_aic__artworks`, not images | 1:1 with artwork grain; `lqip` base64 dropped (rendering infra, not analytics) |
| D8 | AIC staging models tagged `["aic", "staging"]` | Parallel to Met; enables `dbt build --select tag:aic` |
| D9 | All AIC staging materialized as views (matching Met M1) | Defer incremental until volume/cost justifies |

---

## Swim Lane 1: Images

### Model: `stg_aic__images`

**Grain:** `(artwork_id, image_type, ordinal_position)` -- one row per image per artwork.

**Structural parity with `stg_met__images`:** long format, `UNION ALL` of primary + alternates via `LATERAL FLATTEN`.

**URL construction:** Inline in staging SQL. IIIF template:
```
https://www.artic.edu/iiif/2/{image_id}/full/{width},/0/default.jpg
```
- Standard: `843,` (AIC recommendation, matches their website)
- Small: `200,` (semantic parity with Met's `image_url_small`)

**Output columns:**

| Column | Type | Notes |
|--------|------|-------|
| `artwork_id` | INT | FK to `RAW_AIC_ARTWORKS.artwork_id` |
| `source_image_id` | VARCHAR | Raw IIIF UUID -- carried through to Gold per D6 |
| `image_url` | VARCHAR | Computed full-size IIIF URL |
| `image_url_small` | VARCHAR | Computed 200px IIIF URL |
| `image_type` | VARCHAR | `'primary'` or `'additional'` |
| `ordinal_position` | INT | 1 = primary, 2+ = additional |
| `_extracted_at` | TIMESTAMP_NTZ | Pass-through from Bronze |
| `_source_system` | VARCHAR | Always `'art_institute_chicago'` |

**SQL sketch:**

```sql
WITH source AS (
    SELECT
        artwork_id,
        raw_payload:image_id::STRING       AS primary_image_id,
        raw_payload:alt_image_ids           AS alt_image_ids,
        _extracted_at,
        _source_system
    FROM {{ source('aic', 'raw_aic_artworks') }}
    WHERE _is_deleted = FALSE
      AND raw_payload:image_id::STRING IS NOT NULL
),

primary_images AS (
    SELECT
        artwork_id,
        primary_image_id                   AS source_image_id,
        'https://www.artic.edu/iiif/2/' || primary_image_id || '/full/843,/0/default.jpg'
                                           AS image_url,
        'https://www.artic.edu/iiif/2/' || primary_image_id || '/full/200,/0/default.jpg'
                                           AS image_url_small,
        'primary'                          AS image_type,
        1                                  AS ordinal_position,
        _extracted_at,
        _source_system
    FROM source
),

alt_images AS (
    SELECT
        s.artwork_id,
        f.value::STRING                    AS source_image_id,
        'https://www.artic.edu/iiif/2/' || f.value::STRING || '/full/843,/0/default.jpg'
                                           AS image_url,
        'https://www.artic.edu/iiif/2/' || f.value::STRING || '/full/200,/0/default.jpg'
                                           AS image_url_small,
        'additional'                       AS image_type,
        f.index + 2                        AS ordinal_position,
        s._extracted_at,
        s._source_system
    FROM source s,
        LATERAL FLATTEN(input => s.alt_image_ids) f
    WHERE f.value::STRING IS NOT NULL
)

SELECT * FROM primary_images
UNION ALL
SELECT * FROM alt_images
```

**Key design notes:**
- `WHERE _is_deleted = FALSE` applied at source CTE (D4 -- AIC tracks deletions natively).
- Artworks with NULL `image_id` excluded entirely (no row emitted). This is correct: no image, no image row.
- `alt_image_ids` FLATTEN produces zero rows when array is empty -- no special handling needed.

### Gold Impact: `fct_artwork_images` contract change

The contract must add `source_image_id` (nullable VARCHAR -- Met has no equivalent):

```yaml
- name: source_image_id
  data_type: varchar(16777216)
  description: "Source-native image identifier (AIC IIIF UUID; NULL for Met CDN URLs)"
```

Met's CTE in `fct_artwork_images` will emit `NULL AS source_image_id`.

---

## Swim Lane 2: Artists / Agents

### Model: `stg_aic__artists`

**Grain:** `(agent_id)` -- one row per AIC agent entity.

**All agents pass through staging** (D5). Gold applies `WHERE is_artist = TRUE` for `dim_artists`; separate Gold models may consume non-artist agents later.

**Output columns:**

| Column | Type | Notes |
|--------|------|-------|
| `agent_id` | INT | PK from `RAW_AIC_AGENTS.agent_id` |
| `title` | VARCHAR | Display name (e.g. "Edgar Degas") |
| `sort_title` | VARCHAR | "Last, First" format -- maps to Met's `artist_alpha_sort` |
| `alt_titles` | ARRAY | Alternate names (kept as-is for future resolution) |
| `is_artist` | BOOLEAN | Determines Gold filtering (D5) |
| `birth_date` | INT | Extracted year (nullable) |
| `death_date` | INT | Extracted year (nullable) |
| `description` | VARCHAR | Biographical text |
| `ulan_id` | NUMBER | Getty ULAN numeric ID (often NULL; pre-positioned for D2 upgrade) |
| `_ulan_url` | VARCHAR | Computed: `'http://vocab.getty.edu/page/ulan/' \|\| ulan_id` when non-null |
| `_extracted_at` | TIMESTAMP_NTZ | Pass-through |
| `_source_system` | VARCHAR | Always `'art_institute_chicago'` |

**SQL sketch:**

```sql
WITH source AS (
    SELECT
        agent_id,
        raw_payload,
        _extracted_at,
        _source_system
    FROM {{ source('aic', 'raw_aic_agents') }}
),

typed AS (
    SELECT
        agent_id,
        raw_payload:title::STRING                          AS title,
        raw_payload:sort_title::STRING                     AS sort_title,
        raw_payload:alt_titles                             AS alt_titles,
        raw_payload:is_artist::BOOLEAN                     AS is_artist,
        raw_payload:birth_date::INT                        AS birth_date,
        raw_payload:death_date::INT                        AS death_date,
        raw_payload:description::STRING                    AS description,
        raw_payload:ulan_id::NUMBER                        AS ulan_id,
        CASE
            WHEN raw_payload:ulan_id IS NOT NULL
            THEN 'http://vocab.getty.edu/page/ulan/' || raw_payload:ulan_id::STRING
        END                                                AS _ulan_url,
        _extracted_at,
        _source_system
    FROM source
)

SELECT * FROM typed
```

### Entity Resolution: Source-Partitioned v1 (D2)

**What this means concretely:**
- `dim_artists` surrogate key remains `generate_surrogate_key(['artist_alpha_sort', 'artist_ulan_url', 'source_system'])`.
- Met-Degas and AIC-Degas are **two rows** with different `artist_id` values.
- `dim_artworks.artist_id` FK points to the source-specific artist.
- Gold queries that count "unique artists across museums" will overcount. This is documented and accepted.

**Pre-positioned columns for upgrade:**
- `_ulan_url` in `stg_aic__artists` (synthetic from numeric `ulan_id`)
- `_ulan_numeric_id` to add to `stg_met__artists` (extracted from URL string): `NULLIF(SPLIT_PART(artist_ulan_url, '/', -1), '')::NUMBER`

**Upgrade criteria (execute when ANY is true):**
1. ULAN coverage audit shows >10% match rate across Met x AIC
2. Third source (CMA) arrives with meaningful ULAN coverage
3. Owner decides cross-source artist analytics are needed

**Upgrade path:**
1. Create `int_artist_crosswalk` intermediate model
2. Crosswalk outputs `(canonical_artist_id, source_system, source_artist_id)`
3. `dim_artists` reads from crosswalk, deduplicating confirmed matches
4. `dim_artworks.artist_id` FK changes to canonical -- BREAKING CHANGE (contract catches it)
5. Start with Tier 1 (deterministic ULAN match) + Tier 3 (normalized name + birth/death year)
6. Add fuzzy (Tier 4: `JAROWINKLER_SIMILARITY`) only for ambiguous remainder

### Gold Impact: `dim_artists` evolution

The AIC CTE added to `dim_artists.sql`:

```sql
aic_artists AS (
    SELECT
        agent_id                   AS source_artist_id,
        title                      AS artist_display_name,
        sort_title                 AS artist_alpha_sort,
        description                AS artist_display_bio,
        NULL                       AS artist_nationality,  -- AIC doesn't provide this field
        birth_date::STRING         AS artist_begin_date,
        death_date::STRING         AS artist_end_date,
        NULL                       AS artist_gender,       -- AIC doesn't provide this field
        _ulan_url                  AS artist_ulan_url,
        NULL                       AS artist_wikidata_url, -- Not in AIC payload
        'art_institute_chicago'    AS source_system,
        CURRENT_TIMESTAMP()        AS _loaded_at
    FROM {{ ref('stg_aic__artists') }}
    WHERE is_artist = TRUE  -- D5: Gold filters
)
```

**NULL columns note:** AIC agent payload lacks nationality, gender, and wikidata. These emit NULL. The `dim_artists` contract allows NULLs on these columns (no `not_null` constraint). No contract change needed.

---

## Swim Lane 3: Artworks

### Model: `stg_aic__artworks`

**Grain:** `(artwork_id)` -- one row per AIC artwork.

**Soft-delete filter applied here** (D4): `WHERE _is_deleted = FALSE`.

**Output columns (curated -- not exhaustive VARIANT dump):**

| Column | Type | Maps to Gold | Notes |
|--------|------|-------------|-------|
| `artwork_id` | INT | `source_object_id` | PK |
| `title` | VARCHAR | `title` | NOT NULL expected |
| `date_display` | VARCHAR | `object_date` | Human-readable date string |
| `date_start` | INT | `object_begin_date` | Earliest year |
| `date_end` | INT | `object_end_date` | Latest year |
| `medium_display` | VARCHAR | `medium` | Materials/technique |
| `dimensions` | VARCHAR | `dimensions` | Physical size string |
| `artwork_type_title` | VARCHAR | `classification` | Maps to Met's classification |
| `department_title` | VARCHAR | `department` | Curatorial department |
| `place_of_origin` | VARCHAR | `country` | Geographic origin |
| `credit_line` | VARCHAR | `credit_line` | |
| `main_reference_number` | VARCHAR | `accession_number` | AIC's accession equivalent |
| `fiscal_year` | INT | `accession_year` | Cast to STRING in Gold for contract |
| `is_public_domain` | BOOLEAN | `is_public_domain` | |
| `is_boosted` | BOOLEAN | `is_highlight` | AIC's "boost" ~ Met's "highlight" |
| `api_link` | VARCHAR | `link_resource` | URL to AIC API endpoint |
| `artist_id` | INT | (FK lookup) | FK to `RAW_AIC_AGENTS`; used in Gold join |
| `artist_title` | VARCHAR | (denorm) | Denormalized artist name for fallback |
| `thumbnail_width` | INT | -- | D7: thumbnail metadata on artworks |
| `thumbnail_height` | INT | -- | D7: thumbnail metadata on artworks |
| `thumbnail_alt_text` | VARCHAR | -- | D7: thumbnail metadata on artworks |
| `_extracted_at` | TIMESTAMP_NTZ | `_loaded_at` | |
| `_source_system` | VARCHAR | `source_system` | |
| `_batch_id` | VARCHAR | -- | Lineage |

**SQL sketch (core extraction from VARIANT):**

```sql
WITH source AS (
    SELECT
        artwork_id,
        raw_payload,
        _extracted_at,
        _source_system,
        _batch_id
    FROM {{ source('aic', 'raw_aic_artworks') }}
    WHERE _is_deleted = FALSE  -- D4: AIC tracks deletions natively
),

typed AS (
    SELECT
        artwork_id,
        raw_payload:title::STRING                          AS title,
        raw_payload:date_display::STRING                   AS date_display,
        raw_payload:date_start::INT                        AS date_start,
        raw_payload:date_end::INT                          AS date_end,
        raw_payload:medium_display::STRING                 AS medium_display,
        raw_payload:dimensions::STRING                     AS dimensions,
        raw_payload:artwork_type_title::STRING             AS artwork_type_title,
        raw_payload:department_title::STRING               AS department_title,
        raw_payload:place_of_origin::STRING                AS place_of_origin,
        raw_payload:credit_line::STRING                    AS credit_line,
        raw_payload:main_reference_number::STRING          AS main_reference_number,
        raw_payload:fiscal_year::INT                       AS fiscal_year,
        raw_payload:is_public_domain::BOOLEAN              AS is_public_domain,
        raw_payload:is_boosted::BOOLEAN                    AS is_boosted,
        raw_payload:api_link::STRING                       AS api_link,
        -- FK to agents table
        raw_payload:artist_id::INT                         AS artist_id,
        raw_payload:artist_title::STRING                   AS artist_title,
        -- Thumbnail metadata (D7: 1:1 with artwork)
        raw_payload:thumbnail:width::INT                   AS thumbnail_width,
        raw_payload:thumbnail:height::INT                  AS thumbnail_height,
        raw_payload:thumbnail:alt_text::STRING             AS thumbnail_alt_text,
        -- Metadata pass-through
        _extracted_at,
        _source_system,
        _batch_id
    FROM source
)

SELECT * FROM typed
```

### Gold Impact: `dim_artworks` evolution

AIC CTE maps staging columns to the Gold contract:

```sql
aic_artworks AS (
    SELECT
        artwork_id                         AS source_object_id,
        title,
        date_display                       AS object_date,
        date_start                         AS object_begin_date,
        date_end                           AS object_end_date,
        medium_display                     AS medium,
        dimensions,
        artwork_type_title                 AS classification,
        department_title                   AS department,
        NULL                               AS culture,         -- AIC uses place_of_origin instead
        NULL                               AS period,          -- Not in AIC payload
        NULL                               AS dynasty,         -- Not in AIC payload
        place_of_origin                    AS country,
        credit_line,
        main_reference_number              AS accession_number,
        fiscal_year::STRING                AS accession_year,
        is_public_domain,
        is_boosted                         AS is_highlight,
        api_link                           AS link_resource,
        NULL                               AS object_wikidata_url,  -- Not in AIC payload
        'art_institute_chicago'            AS source_system
    FROM {{ ref('stg_aic__artworks') }}
)
```

**FK join in Gold:** AIC artworks join to `dim_artists` on:
```sql
artworks.source_system = artists.source_system
AND artworks.artist_alpha_sort = artists.artist_alpha_sort
AND COALESCE(artworks.artist_ulan_url, '') = COALESCE(artists.artist_ulan_url, '')
```

But AIC's FK is simpler -- direct `artist_id` integer lookup. The Gold join logic for AIC will use `sort_title` (artist's `sort_title`) matched against the `artist_alpha_sort` column in `dim_artists`. This requires `stg_aic__artworks` to expose the artist's `sort_title` via join or denormalization.

**Resolution:** `stg_aic__artworks` carries `artist_title` (display name). In Gold, the AIC artwork CTE joins `stg_aic__artists` to get `sort_title`:

```sql
aic_artworks AS (
    SELECT
        a.artwork_id        AS source_object_id,
        ...
        art.sort_title      AS primary_artist_alpha_sort,
        art._ulan_url       AS primary_artist_ulan_url,
        'art_institute_chicago' AS source_system
    FROM {{ ref('stg_aic__artworks') }} a
    LEFT JOIN {{ ref('stg_aic__artists') }} art
        ON a.artist_id = art.agent_id
)
```

This pre-join in Gold's CTE (not staging) is acceptable because:
1. Staging stays source-faithful (no cross-entity joins)
2. Gold owns the dimensional modeling logic
3. The join is on a direct FK (not fuzzy) -- clean and fast

---

## Swim Lane 4: Gold Evolution

### Contract Changes Required

| Model | Change | Breaking? |
|-------|--------|-----------|
| `fct_artwork_images` | Add `source_image_id` (nullable VARCHAR) | YES -- column addition |
| `dim_artists` | None (existing contract allows NULLs on all new-source gaps) | No |
| `dim_artworks` | None (`source_object_id` type is `number(38,0)` -- AIC uses INT, compatible) | No |
| `openaccess_catalog` | None (reads from Gold dims/facts; inherits changes) | No |

**Contract enforcement note:** Adding `source_image_id` to `fct_artwork_images` is a compile-time schema change. The YAML contract must be updated BEFORE the SQL, or dbt refuses to build. This is the correct enforcement direction.

### Per-Source Governance Tests (D8/Governance)

Add to `_marts__models.yml`:

```yaml
# Under dim_artworks tests:
- dbt_expectations.expect_column_distinct_count_to_be_between:
    column_name: source_system
    min_value: 2
    max_value: 10

# Under dim_artists tests:
- dbt_expectations.expect_column_distinct_count_to_be_between:
    column_name: source_system
    min_value: 2
    max_value: 10
```

Add a singular test file `tests/assert_per_source_minimum_rows.sql`:

```sql
-- Fails if any source contributes fewer than 50 rows to Gold dimensions.
-- Catches "extraction silently failed but Gold built from one source only."
WITH counts AS (
    SELECT source_system, COUNT(*) AS row_count
    FROM {{ ref('dim_artworks') }}
    GROUP BY source_system
)
SELECT source_system, row_count
FROM counts
WHERE row_count < 50
```

### Source Tags in `dbt_project.yml`

```yaml
models:
  artwork_pipeline:
    staging:
      aic:
        +tags: ["aic", "staging"]
```

---

## Swim Lane 5: Monitoring & Data Quality

### Philosophy

> "75% of all functionality is monitoring."

This means: every extraction run, every dbt model, every Gold materialization has
observable health signals. The monitoring strategy is layered:

| Layer | Scope | Tool | Cadence |
|-------|-------|------|---------|
| L0: Extraction pre-flight | Before data lands in Snowflake | Python assertions + ad-hoc SQL | Every run |
| L1: Bronze health | After ingestion, before dbt | Ad-hoc SQL check files | On-demand |
| L2: dbt tests | Silver/Gold schema + data quality | `dbt test` / `dbt build` | Every build |
| L3: Gold assertions | Cross-source consistency | Singular tests + `dbt_expectations` | Every build |
| L4: Operational alerting | Pipeline failure / staleness | Source freshness + custom | Scheduled |

### L0: Extraction Pre-Flight (AIC -- extensible to all sources)

**Design principle:** Validate BEFORE upload. Catch problems at the cheapest layer (local Python) before they become expensive (Snowflake compute + broken Gold tables).

**Checks to implement in `extraction/aic/` Python code:**

| Check | What it catches | Implementation |
|-------|----------------|----------------|
| Row-count sanity | Truncated download, corrupt archive | `assert len(records) > 100_000` for full snapshot |
| Schema completeness | API field removal, format change | Assert required keys present in sample of records |
| PK uniqueness (local) | Duplicate IDs in dump | `assert len(ids) == len(set(ids))` |
| Null-rate thresholds | Source degradation | `title` NULL rate < 1%; `image_id` NULL rate < 70% |
| Type coercion failures | Unexpected data shapes | Track cast failures during VARIANT assembly |
| Batch manifest | Partial uploads | Write `{entity: count, checksum}` per batch |

**Pre-flight report format** (stdout + optional JSON file):

```
AIC Extraction Pre-Flight Report
=================================
Entity: artworks
  Records parsed:    131,245
  PK unique:         PASS (131,245 distinct)
  Required keys:     PASS (all 15 present in 100% sample)
  title NULL rate:   0.2% (< 1% threshold)  PASS
  image_id NULL:     34.1% (< 70% threshold) PASS
  Type failures:     0                        PASS
Entity: agents
  Records parsed:    15,312
  PK unique:         PASS
  ...
```

**Extensibility:** The pre-flight framework should be source-agnostic. A base class or config dict defines thresholds per source:

```python
# extraction/quality/preflight.py (future)
PREFLIGHT_RULES = {
    "art_institute_chicago": {
        "artworks": {
            "min_rows": 100_000,
            "required_keys": ["id", "title", "image_id", "artist_id"],
            "null_thresholds": {"title": 0.01, "image_id": 0.70},
        },
        "agents": {
            "min_rows": 10_000,
            "required_keys": ["id", "title", "sort_title"],
            "null_thresholds": {"title": 0.01},
        },
    },
}
```

### L1: Bronze Health (Ad-Hoc SQL Check Files)

**Pattern:** `scripts/sql/check_*.sql` files, runnable via toolkit's `check.sh`:
```bash
bash ../snowflake-toolkit/check.sh scripts/sql/check_aic_bronze.sql
```

**Files to create:**

1. **`scripts/sql/check_aic_bronze.sql`** -- Row counts, batch recency, image_id coverage
2. **`scripts/sql/check_aic_agents.sql`** -- Agent counts, ULAN coverage audit, is_artist distribution
3. **`scripts/sql/check_cross_source_overlap.sql`** -- Artist name overlap between Met and AIC (pre-positions entity resolution)

**Example: `check_aic_bronze.sql`:**

```sql
-- =============================================================================
-- check_aic_bronze.sql -- READ-ONLY: AIC Bronze health snapshot
-- Run via: bash ../snowflake-toolkit/check.sh scripts/sql/check_aic_bronze.sql
-- =============================================================================

-- 1) Row counts
SELECT 'RAW_AIC_ARTWORKS' AS table_name, COUNT(*) AS rows,
       COUNT_IF(_is_deleted) AS deleted_rows,
       MAX(_extracted_at) AS last_load
FROM ARTWORK_DB.BRONZE.RAW_AIC_ARTWORKS
UNION ALL
SELECT 'RAW_AIC_AGENTS', COUNT(*), NULL, MAX(_extracted_at)
FROM ARTWORK_DB.BRONZE.RAW_AIC_AGENTS;

-- 2) Image coverage (the critical data quality question)
SELECT
    COUNT(*)                                              AS total_artworks,
    COUNT_IF(raw_payload:image_id IS NOT NULL)            AS has_image_id,
    ROUND(has_image_id / total_artworks * 100, 1)        AS image_pct,
    COUNT_IF(raw_payload:is_public_domain::BOOLEAN)      AS public_domain,
    COUNT_IF(raw_payload:is_public_domain::BOOLEAN
             AND raw_payload:image_id IS NOT NULL)        AS public_with_image,
    ROUND(public_with_image / NULLIF(public_domain, 0) * 100, 1)
                                                         AS public_image_pct
FROM ARTWORK_DB.BRONZE.RAW_AIC_ARTWORKS
WHERE _is_deleted = FALSE;

-- 3) alt_image_ids distribution
SELECT
    CASE
        WHEN ARRAY_SIZE(raw_payload:alt_image_ids) = 0 THEN '0 (none)'
        WHEN ARRAY_SIZE(raw_payload:alt_image_ids) BETWEEN 1 AND 3 THEN '1-3'
        WHEN ARRAY_SIZE(raw_payload:alt_image_ids) BETWEEN 4 AND 10 THEN '4-10'
        ELSE '11+'
    END AS alt_image_bucket,
    COUNT(*) AS artworks
FROM ARTWORK_DB.BRONZE.RAW_AIC_ARTWORKS
WHERE _is_deleted = FALSE
GROUP BY 1
ORDER BY 1;

-- 4) Batch provenance
SELECT _batch_id, _source_system, COUNT(*) AS rows, MIN(_extracted_at), MAX(_extracted_at)
FROM ARTWORK_DB.BRONZE.RAW_AIC_ARTWORKS
GROUP BY 1, 2
ORDER BY MAX(_extracted_at) DESC
LIMIT 5;
```

**Example: `check_aic_agents.sql` (ULAN coverage audit):**

```sql
-- =============================================================================
-- check_aic_agents.sql -- READ-ONLY: AIC agent data quality + ULAN coverage
-- Critical for entity resolution upgrade criteria (D2).
-- =============================================================================

-- 1) Overview
SELECT
    COUNT(*)                                          AS total_agents,
    COUNT_IF(raw_payload:is_artist::BOOLEAN)          AS artists,
    COUNT_IF(NOT raw_payload:is_artist::BOOLEAN)      AS non_artists,
    COUNT_IF(raw_payload:ulan_id IS NOT NULL)         AS has_ulan,
    ROUND(has_ulan / total_agents * 100, 1)           AS ulan_pct,
    COUNT_IF(raw_payload:is_artist::BOOLEAN
             AND raw_payload:ulan_id IS NOT NULL)     AS artists_with_ulan,
    ROUND(artists_with_ulan / NULLIF(artists, 0) * 100, 1)
                                                     AS artist_ulan_pct
FROM ARTWORK_DB.BRONZE.RAW_AIC_AGENTS;

-- 2) ULAN overlap with Met (entity resolution signal strength)
-- Requires both sources loaded. Returns count of shared ULAN IDs.
SELECT
    COUNT(*) AS shared_ulan_count
FROM (
    SELECT DISTINCT
        NULLIF(SPLIT_PART(raw_payload:csv:artist_ulan_url::STRING, '/', -1), '')
            AS ulan_numeric
    FROM ARTWORK_DB.BRONZE.RAW_MET_OBJECTS
    WHERE raw_payload:csv:artist_ulan_url::STRING IS NOT NULL
) met
INNER JOIN (
    SELECT DISTINCT raw_payload:ulan_id::STRING AS ulan_numeric
    FROM ARTWORK_DB.BRONZE.RAW_AIC_AGENTS
    WHERE raw_payload:ulan_id IS NOT NULL
) aic
ON met.ulan_numeric = aic.ulan_numeric;

-- 3) Name overlap (fuzzy signal -- sort_title vs artist_alpha_sort)
-- Top 20 exact matches on normalized "Last, First" name
SELECT
    aic.sort_title,
    met.artist_alpha_sort,
    aic.birth_date AS aic_birth,
    met.artist_begin_date AS met_birth
FROM (
    SELECT DISTINCT
        raw_payload:sort_title::STRING AS sort_title,
        raw_payload:birth_date::STRING AS birth_date
    FROM ARTWORK_DB.BRONZE.RAW_AIC_AGENTS
    WHERE raw_payload:is_artist::BOOLEAN
) aic
INNER JOIN (
    SELECT DISTINCT
        TRIM(GET(SPLIT(raw_payload:csv:artist_alpha_sort::STRING, '|'), 0)::STRING)
            AS artist_alpha_sort,
        TRIM(GET(SPLIT(raw_payload:csv:artist_begin_date::STRING, '|'), 0)::STRING)
            AS artist_begin_date
    FROM ARTWORK_DB.BRONZE.RAW_MET_OBJECTS
    WHERE raw_payload:csv:artist_alpha_sort::STRING IS NOT NULL
) met
ON UPPER(TRIM(aic.sort_title)) = UPPER(TRIM(met.artist_alpha_sort))
LIMIT 20;
```

### L2: dbt Tests (Silver Layer)

**AIC staging YAML (`_aic__models.yml`) tests:**

```yaml
models:
  - name: stg_aic__artworks
    columns:
      - name: artwork_id
        tests: [unique, not_null]
      - name: title
        tests: [not_null]
      - name: _source_system
        tests:
          - accepted_values:
              values: ['art_institute_chicago']
    tests:
      - dbt_expectations.expect_table_row_count_to_be_between:
          min_value: 100000
          max_value: 200000

  - name: stg_aic__artists
    columns:
      - name: agent_id
        tests: [unique, not_null]
      - name: title
        tests: [not_null]
      - name: sort_title
        tests: [not_null]
    tests:
      - dbt_expectations.expect_table_row_count_to_be_between:
          min_value: 10000
          max_value: 50000

  - name: stg_aic__images
    columns:
      - name: source_image_id
        tests:
          - not_null
          # UUID format validation (AIC uses v4 UUIDs without hyphens)
          - dbt_expectations.expect_column_values_to_match_regex:
              regex: '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
              row_condition: "source_image_id IS NOT NULL"
    tests:
      - dbt_expectations.expect_compound_columns_to_be_unique:
          column_list: ["artwork_id", "image_type", "ordinal_position"]
```

### L3: Gold Assertions

Already covered in Swim Lane 4 (per-source row counts, source_system distinct count). Additionally:

**FK integrity test** (singular test):

```sql
-- tests/assert_artwork_artist_fk_integrity.sql
-- Every non-NULL artist_id in dim_artworks must exist in dim_artists.
SELECT a.artwork_id, a.artist_id
FROM {{ ref('dim_artworks') }} a
WHERE a.artist_id IS NOT NULL
  AND a.artist_id NOT IN (SELECT artist_id FROM {{ ref('dim_artists') }})
```

### L4: Source Freshness

Add to `_aic__sources.yml`:

```yaml
sources:
  - name: aic
    database: ARTWORK_DB
    schema: BRONZE
    freshness:
      warn_after: {count: 30, period: day}
      # AIC data dump is periodic (not real-time). 30-day warning is reasonable.
    loaded_at_field: _EXTRACTED_AT
    tables:
      - name: raw_aic_artworks
        identifier: RAW_AIC_ARTWORKS
      - name: raw_aic_agents
        identifier: RAW_AIC_AGENTS
```

Note: AIC freshness cadence is fundamentally different from Met (which has a live API). The warn threshold reflects this -- 30 days vs Met's 7 days.

### `dbt-diagnostics` Integration Points

Specific scenarios to exercise against the new AIC pipeline:

| Scenario | How to trigger | What `dbt-diagnostics` should report |
|----------|---------------|--------------------------------------|
| Contract column mismatch | Omit `source_image_id` from `fct_artwork_images` SQL but keep it in YAML | "Column `source_image_id` declared in contract but not present in model output" + trace to the CTE that's missing it |
| FK null cascade | Use wrong source_system literal (e.g. `'aic'` instead of `'art_institute_chicago'`) in Gold join | "test `not_null` on `artist_id` failed with N rows" + trace to the join condition mismatch |
| Type coercion failure | Cast `fiscal_year` to STRING in staging but Gold contract expects NUMBER | "Type mismatch: column `accession_year` is VARCHAR in SQL output but NUMBER in contract" |
| Source row-count violation | Empty AIC Bronze (extraction failure) | "test `expect_table_row_count_to_be_between` failed: actual 0, expected 100000-200000" |

---

## OPEN Items (require data audit before closing)

| ID | Question | Resolution SQL | Blocks |
|----|----------|---------------|--------|
| OPEN-1 | What % of AIC artworks have non-null `image_id`? | `check_aic_bronze.sql` query 2 | UUID regex pattern in tests (hyphenated vs bare hex?) |
| OPEN-2 | What % of AIC agents have non-null `ulan_id`? | `check_aic_agents.sql` query 1 | Entity resolution upgrade timeline |
| OPEN-3 | Does AIC `sort_title` consistently use "Last, First" format? | Sample query + regex check | `artist_alpha_sort` mapping confidence |
| OPEN-4 | Are `alt_image_ids` UUIDs in the same format as `image_id`? | Regex check on flattened array | Image test regex pattern |
| OPEN-5 | What is the AIC `image_id` format -- UUID with hyphens or bare hex? | `SELECT DISTINCT LENGTH(raw_payload:image_id::STRING) ...` | IIIF URL construction (hyphenated UUIDs work fine in URLs) |

**These queries should be run BEFORE writing final model code.** They gate test threshold values and regex patterns. The SQL is pre-written above; run them after confirming Bronze data is loaded.

---

## File Creation Order (Dependency Graph)

```
Phase 1: Sources + Staging (no Gold changes)
  1. artwork_pipeline/models/staging/aic/_aic__sources.yml
  2. artwork_pipeline/models/staging/aic/_aic__models.yml
  3. artwork_pipeline/models/staging/aic/stg_aic__artworks.sql
  4. artwork_pipeline/models/staging/aic/stg_aic__artists.sql
  5. artwork_pipeline/models/staging/aic/stg_aic__images.sql

Phase 2: Monitoring (independent of Phase 1 SQL correctness)
  6. scripts/sql/check_aic_bronze.sql
  7. scripts/sql/check_aic_agents.sql
  8. scripts/sql/check_cross_source_overlap.sql

Phase 3: Gold evolution (depends on Phase 1 compiling)
  9. artwork_pipeline/models/marts/dim_artists.sql        (edit: add AIC CTE + UNION ALL)
 10. artwork_pipeline/models/marts/dim_artworks.sql       (edit: add AIC CTE + UNION ALL)
 11. artwork_pipeline/models/marts/fct_artwork_images.sql (edit: add AIC CTE + source_image_id)
 12. artwork_pipeline/models/marts/_marts__models.yml     (edit: add source_image_id to contract)
 13. artwork_pipeline/models/marts/openaccess_catalog.sql (no edit needed -- inherits)

Phase 4: Tests
 14. tests/assert_per_source_minimum_rows.sql
 15. tests/assert_artwork_artist_fk_integrity.sql

Phase 5: dbt_project.yml update
 16. artwork_pipeline/dbt_project.yml (add aic staging tags)

Phase 6: Extraction pre-flight (Python)
 17. extraction/quality/__init__.py
 18. extraction/quality/preflight.py
 19. extraction/aic/loader.py (integrate preflight call before upload)
```

**Build verification sequence after all phases:**
```bash
# Compile check (no execution)
cd artwork_pipeline && dbt compile --select tag:aic

# Full build with tests
dbt build --select tag:aic

# Then: full project build to verify Gold integration
dbt build

# Then: run check scripts against live data
bash ../snowflake-toolkit/check.sh scripts/sql/check_aic_bronze.sql
```

---

## Appendix: Column Mapping Quick Reference

### Met -> Gold -> AIC (alignment table for UNION columns)

| Gold Column | Met Source | AIC Source | Notes |
|-------------|-----------|-----------|-------|
| `source_object_id` | `object_id` | `artwork_id` | Both INT |
| `title` | `raw_payload:csv:title` | `raw_payload:title` | |
| `object_date` | `raw_payload:csv:object_date` | `raw_payload:date_display` | |
| `object_begin_date` | `raw_payload:csv:object_begin_date` | `raw_payload:date_start` | |
| `object_end_date` | `raw_payload:csv:object_end_date` | `raw_payload:date_end` | |
| `medium` | `raw_payload:csv:medium` | `raw_payload:medium_display` | |
| `dimensions` | `raw_payload:csv:dimensions` | `raw_payload:dimensions` | |
| `classification` | `raw_payload:csv:classification` | `raw_payload:artwork_type_title` | |
| `department` | `raw_payload:csv:department` | `raw_payload:department_title` | |
| `culture` | `raw_payload:csv:culture` | NULL | AIC lacks this field |
| `period` | `raw_payload:csv:period` | NULL | AIC lacks this field |
| `dynasty` | `raw_payload:csv:dynasty` | NULL | AIC lacks this field |
| `country` | `raw_payload:csv:country` | `raw_payload:place_of_origin` | Semantic mapping |
| `credit_line` | `raw_payload:csv:credit_line` | `raw_payload:credit_line` | |
| `accession_number` | `raw_payload:csv:object_number` | `raw_payload:main_reference_number` | |
| `accession_year` | `raw_payload:csv:accession_year` | `raw_payload:fiscal_year::STRING` | Type coercion |
| `is_public_domain` | `raw_payload:csv:is_public_domain` | `raw_payload:is_public_domain` | |
| `is_highlight` | `raw_payload:csv:is_highlight` | `raw_payload:is_boosted` | Semantic mapping |
| `link_resource` | `raw_payload:csv:link_resource` | `raw_payload:api_link` | |
| `object_wikidata_url` | `raw_payload:csv:object_wikidata_url` | NULL | AIC lacks this |
| `source_system` | `'met_museum'` | `'art_institute_chicago'` | D1 |
