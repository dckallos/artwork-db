# AIC Phase 3: Gold Evolution -- Implementation Plan

> **Status:** Decisions locked. Ready for code implementation.
> **Branch:** `donkey-kong-sandbox`
> **Predecessor:** `docs/prompts/AIC_PHASE3_GOLD_EVOLUTION_PROMPT.md` (design discussion)
> **Account:** `lj10656` (user `PORCHDBT`, role `ARTWORK_TRANSFORMER`)

---

## Table of Contents

1. [Decision Register](#decision-register)
2. [Prerequisites & Current State](#prerequisites--current-state)
3. [Implementation: dim_artists.sql](#implementation-dim_artistssql)
4. [Implementation: dim_artworks.sql](#implementation-dim_artworkssql)
5. [Implementation: fct_artwork_images.sql (Incremental)](#implementation-fct_artwork_imagessql-incremental)
6. [Implementation: openaccess_catalog.sql](#implementation-openaccess_catalogsql)
7. [Implementation: _marts__models.yml (Contract & Tests)](#implementation-_marts__modelsyml-contract--tests)
8. [Governance Tests](#governance-tests)
9. [Cluster Key Documentation](#cluster-key-documentation)
10. [Follow-Up: dim_artworks Incremental Exercise](#follow-up-dim_artworks-incremental-exercise)
11. [Execution Checklist](#execution-checklist)

---

## Decision Register

All decisions from the design document (`aic-silver-gold-implementation.md`) plus
refinements from the Phase 3 design review session.

### Original Design Decisions (Locked)

| ID | Decision | Detail |
|----|----------|--------|
| D1 | `source_system = 'art_institute_chicago'` | Consistent with extraction pipeline naming |
| D2 | Entity resolution = source-partitioned v1 | Same artist from different museums = separate rows until crosswalk built |
| D3 | UNION location = Gold-level CTEs | Each Gold model UNIONs source CTEs internally (no intermediate models) |
| D4 | Met soft-delete = accept asymmetry | AIC has `_is_deleted`; Met does not. Gold does not normalize this. |
| D5 | Gold filters `is_artist = TRUE` | Applied in `dim_artists` AIC CTE (not downstream) |
| D6 | `source_image_id` carried to Gold | Single generic column; Met = NULL, AIC = UUID |
| D7 | Thumbnail on artworks, not images | `thumbnail_width`/`thumbnail_height`/`thumbnail_alt_text` are Silver-only columns on `stg_aic__artworks`; not promoted to Gold |
| D8 | AIC staging tagged `["aic", "staging"]` | Does NOT propagate to Gold (Gold has `["marts"]` tag) |
| D9 | AIC staging as views; Gold as `table` | `fct_artwork_images` upgraded to incremental (see below) |

### Phase 3 Design Review Decisions (New)

| ID | Decision | Rationale |
|----|----------|-----------|
| P3-1 | FK join: String round-trip with QUALIFY guard (Option A) | The round-trip (artwork -> artist integer FK -> get sort_title -> match dim_artists on string) is necessary given dim_artists' surrogate key structure. A `QUALIFY ROW_NUMBER() = 1` guard prevents fan-out if duplicate `sort_title` values exist. |
| P3-2 | Incremental: Only `fct_artwork_images` this phase (Option A) | Append-dominant fact table is the best teaching vehicle. `dim_artworks` incremental captured as follow-up exercise. |
| P3-3 | UNION alignment: Manual discipline with comments (Option A) | CTEs are co-located in the same file; explicit column-order comments provide visual anchor. Risk is low for single-author, same-file code. |
| P3-4 | Cluster keys: Add with documentation (Option C) | Added for learning. At 137k rows they are functionally no-ops, but provide hands-on experience with `SYSTEM$CLUSTERING_INFORMATION` monitoring. |

---

## Prerequisites & Current State

### What Exists in Snowflake (verified 2026-06-12)

| Object | Status |
|--------|--------|
| `ARTWORK_DB.BRONZE.RAW_AIC_ARTWORKS` | Loaded (134,078 rows) |
| `ARTWORK_DB.BRONZE.RAW_AIC_AGENTS` | Loaded (16,051 rows) |
| `ARTWORK_DB.BRONZE.RAW_MET_OBJECTS` | Loaded (503 rows, seed) |
| `ARTWORK_DB.SILVER.STG_MET__*` (4 views) | Materialized |
| `ARTWORK_DB.SILVER.STG_AIC__*` (3 views) | NOT yet created (SQL exists, needs `dbt run`) |
| `ARTWORK_DB.GOLD.*` | EMPTY (no tables exist) |
| `ARTWORK_TRANSFORMER` role | Exists; has CREATE TABLE/VIEW on SILVER+GOLD, SELECT on Bronze |
| `ARTWORK_WH` warehouse | Exists (suspended, auto-resume on) |

### What Happens on First `dbt build`

1. AIC Silver views created (they `ref` Bronze sources that exist)
2. Gold tables created via CREATE TABLE AS SELECT
3. `fct_artwork_images` created as incremental (first run = full table creation)
4. Tests run against materialized tables

---

## Implementation: dim_artists.sql

### Design

- Add an `aic_artists` CTE sourcing from `stg_aic__artists`
- Filter `WHERE is_artist = TRUE` (D5) inside the CTE
- Map AIC columns to Met's schema (column renaming)
- UNION ALL with `met_artists` CTE
- Final SELECT regenerates surrogate key (unchanged formula)

### Column Mapping (AIC -> Gold)

| Gold Column | AIC Source (`stg_aic__artists`) | Notes |
|-------------|---------------------------------|-------|
| `artist_display_name` | `title` | |
| `artist_alpha_sort` | `sort_title` | 83.6% "Last, First"; 16.4% orgs/East Asian |
| `artist_display_bio` | `description` | |
| `artist_nationality` | NULL | AIC does not provide nationality |
| `artist_begin_date` | `birth_date` (cast to STRING) | AIC stores as INT |
| `artist_end_date` | `death_date` (cast to STRING) | AIC stores as INT |
| `artist_gender` | NULL | AIC does not provide gender |
| `artist_ulan_url` | `_ulan_url` | Non-NULL for 1 of 14,105 artists |
| `artist_wikidata_url` | NULL | AIC does not provide Wikidata |
| `source_system` | `'art_institute_chicago'` | Hardcoded literal (D1) |
| `_loaded_at` | `CURRENT_TIMESTAMP()` | Standard |

### SQL Sketch

```sql
-- =============================================================================
-- dim_artists.sql -- Gold: Conformed artist dimension
-- =============================================================================
-- Contract: models/marts/_marts__models.yml (enforced)
-- Grain: one row per artist entity per source system
-- PK: artist_id (MD5 hash of artist_alpha_sort + artist_ulan_url + source_system)
--
-- Sources: stg_met__artists, stg_aic__artists
-- UNION column order: MUST match between met_artists and aic_artists CTEs.
-- =============================================================================

WITH met_artists AS (

    SELECT
        artist_display_name,
        artist_alpha_sort,
        artist_display_bio,
        artist_nationality,
        artist_begin_date,
        artist_end_date,
        artist_gender,
        artist_ulan_url,
        artist_wikidata_url,
        'met_museum' AS source_system,
        CURRENT_TIMESTAMP() AS _loaded_at
    FROM {{ ref('stg_met__artists') }}

),

aic_artists AS (

    SELECT
        title                               AS artist_display_name,
        sort_title                          AS artist_alpha_sort,
        description                         AS artist_display_bio,
        NULL::STRING                        AS artist_nationality,
        birth_date::STRING                  AS artist_begin_date,
        death_date::STRING                  AS artist_end_date,
        NULL::STRING                        AS artist_gender,
        _ulan_url                           AS artist_ulan_url,
        NULL::STRING                        AS artist_wikidata_url,
        'art_institute_chicago'             AS source_system,
        CURRENT_TIMESTAMP()                 AS _loaded_at
    FROM {{ ref('stg_aic__artists') }}
    WHERE is_artist = TRUE

),

unioned AS (

    SELECT * FROM met_artists
    UNION ALL
    SELECT * FROM aic_artists

)

SELECT
    {{ dbt_utils.generate_surrogate_key(['artist_alpha_sort', 'artist_ulan_url', 'source_system']) }}
        AS artist_id,
    artist_display_name,
    artist_alpha_sort,
    artist_display_bio,
    artist_nationality,
    artist_begin_date,
    artist_end_date,
    artist_gender,
    artist_ulan_url,
    artist_wikidata_url,
    source_system,
    _loaded_at
FROM unioned
```

### Key Design Notes

- `artist_id` from `stg_met__artists` is deliberately NOT selected in the Met CTE. The final SELECT regenerates it with `source_system` in the grain. This ensures the Gold surrogate key formula is the single source of truth.
- AIC `birth_date`/`death_date` are INT in staging (e.g., 1840). Cast to STRING for type alignment with Met (which stores "1840" as a string from the CSV).
- NULL columns are explicitly typed (`NULL::STRING`) to satisfy Snowflake's UNION ALL type resolution.

---

## Implementation: dim_artworks.sql

### Design

- Add an `aic_artworks` CTE with a pre-join to `stg_aic__artists` (resolves integer FK to get `sort_title` and `_ulan_url` for the downstream artist FK match)
- QUALIFY guard prevents fan-out if duplicate sort_titles exist
- UNION ALL with the existing `met_artworks` CTE (renamed from `artworks`)
- The final LEFT JOIN to `dim_artists` remains unchanged

### The "Round-Trip" FK Pattern Explained (P3-1)

```
AIC artwork row
    |-- artist_id (integer, e.g. 7422)
    |
    v  [CTE internal join: stg_aic__artworks LEFT JOIN stg_aic__artists ON artist_id = agent_id]
    |
    |-- sort_title (string, e.g. "Monet, Claude")
    |-- _ulan_url (string, usually NULL)
    |
    v  [Final join: ON primary_artist_alpha_sort = artist_alpha_sort
                   AND COALESCE(primary_artist_ulan_url,'') = COALESCE(artist_ulan_url,'')
                   AND source_system = source_system]
    |
    |-- artist_id (surrogate MD5 from dim_artists)
```

Why this is necessary: `dim_artists`'s PK is `MD5(artist_alpha_sort + artist_ulan_url + source_system)`. There is no integer FK column to join on directly. The string match IS the join path.

The QUALIFY guard: If two artists share the same `sort_title` AND both have NULL ULAN (the only collision scenario), the pre-join would fan out. `QUALIFY ROW_NUMBER() OVER (PARTITION BY a.artwork_id ORDER BY art.agent_id) = 1` takes the first match deterministically.

### Column Mapping (AIC -> Gold)

| Gold Column | AIC Source | Notes |
|-------------|-----------|-------|
| `source_object_id` | `artwork_id` (cast to STRING) | AIC uses INT; Met uses INT; both cast to STRING for consistency |
| `title` | `title` | |
| `object_date` | `date_display` | Free-text date string |
| `object_begin_date` | `date_start` | INT |
| `object_end_date` | `date_end` | INT |
| `medium` | `medium_display` | |
| `dimensions` | `dimensions` | |
| `classification` | `artwork_type_title` | Closest semantic match |
| `department` | `department_title` | |
| `culture` | `place_of_origin` | Closest semantic match |
| `period` | NULL | AIC does not expose period |
| `dynasty` | NULL | AIC does not expose dynasty |
| `country` | NULL | AIC does not expose country separately (use place_of_origin) |
| `credit_line` | `credit_line` | |
| `accession_number` | `main_reference_number` | |
| `accession_year` | `fiscal_year` | Closest equivalent |
| `is_public_domain` | `is_public_domain` | Direct map |
| `is_highlight` | `is_boosted` | AIC's "boosted" = editorially promoted |
| `link_resource` | `api_link` | Link back to source |
| `object_wikidata_url` | NULL | AIC does not expose per-artwork Wikidata |
| `primary_artist_alpha_sort` | `art.sort_title` (from pre-join) | Used for FK match |
| `primary_artist_ulan_url` | `art._ulan_url` (from pre-join) | Used for FK match |
| `source_system` | `'art_institute_chicago'` | Hardcoded (D1) |

### SQL Sketch

```sql
-- =============================================================================
-- dim_artworks.sql -- Gold: Conformed artwork dimension
-- =============================================================================
-- Contract: models/marts/_marts__models.yml (enforced)
-- Grain: one row per artwork
-- PK: artwork_id (MD5 hash of source_system + source_object_id)
-- FK: artist_id -> dim_artists
--
-- Sources: stg_met__artworks, stg_aic__artworks (+ stg_aic__artists for FK resolution)
-- UNION column order: MUST match between met_artworks and aic_artworks CTEs.
-- =============================================================================

WITH met_artworks AS (

    SELECT
        object_id::STRING                                                  AS source_object_id,
        title,
        object_date,
        object_begin_date,
        object_end_date,
        medium,
        dimensions,
        classification,
        department,
        culture,
        period,
        dynasty,
        country,
        credit_line,
        accession_number,
        accession_year,
        is_public_domain,
        is_highlight,
        link_resource,
        object_wikidata_url,
        TRIM(GET(SPLIT(artist_alpha_sort, '|'), 0)::STRING)  AS primary_artist_alpha_sort,
        TRIM(GET(SPLIT(artist_ulan_url, '|'), 0)::STRING)    AS primary_artist_ulan_url,
        'met_museum' AS source_system
    FROM {{ ref('stg_met__artworks') }}

),

aic_artworks AS (

    SELECT
        a.artwork_id::STRING                                               AS source_object_id,
        a.title,
        a.date_display                                                     AS object_date,
        a.date_start                                                       AS object_begin_date,
        a.date_end                                                         AS object_end_date,
        a.medium_display                                                   AS medium,
        a.dimensions,
        a.artwork_type_title                                               AS classification,
        a.department_title                                                 AS department,
        a.place_of_origin                                                  AS culture,
        NULL::STRING                                                        AS period,
        NULL::STRING                                                        AS dynasty,
        NULL::STRING                                                        AS country,
        a.credit_line,
        a.main_reference_number                                            AS accession_number,
        a.fiscal_year                                                      AS accession_year,
        a.is_public_domain,
        a.is_boosted                                                       AS is_highlight,
        a.api_link                                                         AS link_resource,
        NULL::STRING                                                        AS object_wikidata_url,
        art.sort_title                                                     AS primary_artist_alpha_sort,
        art._ulan_url                                                      AS primary_artist_ulan_url,
        'art_institute_chicago'                                            AS source_system
    FROM {{ ref('stg_aic__artworks') }} a
    LEFT JOIN {{ ref('stg_aic__artists') }} art
        ON a.artist_id = art.agent_id
    QUALIFY ROW_NUMBER() OVER (PARTITION BY a.artwork_id ORDER BY art.agent_id) = 1

),

all_artworks AS (

    SELECT * FROM met_artworks
    UNION ALL
    SELECT * FROM aic_artworks

),

artists AS (

    SELECT
        artist_id,
        artist_alpha_sort,
        artist_ulan_url,
        source_system
    FROM {{ ref('dim_artists') }}

)

SELECT
    {{ dbt_utils.generate_surrogate_key(['all_artworks.source_system', 'all_artworks.source_object_id']) }}
        AS artwork_id,
    all_artworks.source_object_id,
    artists.artist_id,
    all_artworks.title,
    all_artworks.object_date,
    all_artworks.object_begin_date,
    all_artworks.object_end_date,
    all_artworks.medium,
    all_artworks.dimensions,
    all_artworks.classification,
    all_artworks.department,
    all_artworks.culture,
    all_artworks.period,
    all_artworks.dynasty,
    all_artworks.country,
    all_artworks.credit_line,
    all_artworks.accession_number,
    all_artworks.accession_year,
    all_artworks.is_public_domain,
    all_artworks.is_highlight,
    all_artworks.link_resource,
    all_artworks.object_wikidata_url,
    all_artworks.source_system,
    CURRENT_TIMESTAMP() AS _loaded_at
FROM all_artworks
LEFT JOIN artists
    ON all_artworks.primary_artist_alpha_sort = artists.artist_alpha_sort
    AND COALESCE(all_artworks.primary_artist_ulan_url, '') = COALESCE(artists.artist_ulan_url, '')
    AND all_artworks.source_system = artists.source_system
```

### Key Design Notes

- The `QUALIFY` on the AIC CTE is a safety net. In practice, the `artist_id -> agent_id` FK should be 1:1 (an artwork has one primary artist). But if the data ever has duplicates (e.g., agent table loaded twice), this prevents silent row multiplication.
- `object_id::STRING` cast on Met is new -- previously it was an implicit cast. Making it explicit ensures UNION type alignment.
- The `artists` CTE reads from `dim_artists` (a self-referential DAG dependency). dbt handles this correctly: `dim_artists` materializes first, then `dim_artworks` reads from it.

---

## Implementation: fct_artwork_images.sql (Incremental)

### Design

- Add an `aic_images` CTE sourcing from `stg_aic__images`
- Add `source_image_id` column to both CTEs (Met = NULL, AIC = UUID)
- UNION ALL both source CTEs
- Make incremental with `unique_key = 'image_id'`, strategy `merge`
- Add `is_incremental()` watermark filter to both CTEs
- Add cluster key for learning purposes (P3-4)

### Incremental Mechanics

**Strategy:** `merge` (dbt generates a Snowflake MERGE statement)

**How it works:**
- First run (or `--full-refresh`): Creates table via CREATE TABLE AS SELECT (full dataset)
- Subsequent runs: Compiles a MERGE statement that:
  - Matches on `unique_key` (`image_id`)
  - UPDATES existing rows if the key matches
  - INSERTS new rows if no match
- The `is_incremental()` filter reduces the source scan to only new/changed rows

**Watermark logic:** Compare source `_extracted_at` against target `MAX(_loaded_at)`. This works because:
- `_loaded_at` is `CURRENT_TIMESTAMP()` at materialization time
- New extractions have `_extracted_at` > the last build time
- Re-extracted rows (same image, updated metadata) match on `image_id` and UPDATE

**`on_schema_change: 'fail'`:** With an enforced contract, schema drift is already caught at compile time. This setting is a belt-and-suspenders defense.

### SQL Sketch

```sql
-- =============================================================================
-- fct_artwork_images.sql -- Gold: Image fact table (incremental)
-- =============================================================================
-- Contract: models/marts/_marts__models.yml (enforced)
-- Grain: one row per image per artwork
-- PK: image_id (MD5 hash of artwork_id + image_type + ordinal_position)
-- FK: artwork_id -> dim_artworks
--
-- Sources: stg_met__images, stg_aic__images (via dim_artworks for artwork_id FK)
-- UNION column order: MUST match between met_images and aic_images CTEs.
--
-- Materialization: incremental (merge strategy)
-- Cluster key: [source_system] (learning exercise; see cluster key docs below)
-- =============================================================================

{{
    config(
        materialized='incremental',
        unique_key='image_id',
        incremental_strategy='merge',
        on_schema_change='fail',
        cluster_by=['source_system']
    )
}}

WITH met_images AS (

    SELECT
        object_id::STRING       AS source_object_id,
        NULL::STRING            AS source_image_id,
        image_url,
        image_url_small,
        image_type,
        ordinal_position,
        'met_museum'            AS source_system,
        _extracted_at
    FROM {{ ref('stg_met__images') }}
    {% if is_incremental() %}
    WHERE _extracted_at > (SELECT MAX(_loaded_at) FROM {{ this }})
    {% endif %}

),

aic_images AS (

    SELECT
        artwork_id::STRING      AS source_object_id,
        source_image_id,
        image_url,
        image_url_small,
        image_type,
        ordinal_position,
        'art_institute_chicago' AS source_system,
        _extracted_at
    FROM {{ ref('stg_aic__images') }}
    {% if is_incremental() %}
    WHERE _extracted_at > (SELECT MAX(_loaded_at) FROM {{ this }})
    {% endif %}

),

all_images AS (

    SELECT * FROM met_images
    UNION ALL
    SELECT * FROM aic_images

),

artworks AS (

    SELECT
        artwork_id,
        source_object_id,
        source_system
    FROM {{ ref('dim_artworks') }}

)

SELECT
    {{ dbt_utils.generate_surrogate_key(['artworks.artwork_id', 'all_images.image_type', 'all_images.ordinal_position']) }}
        AS image_id,
    artworks.artwork_id,
    all_images.source_image_id,
    all_images.image_url,
    all_images.image_url_small,
    all_images.image_type,
    all_images.ordinal_position,
    all_images.source_system,
    CURRENT_TIMESTAMP() AS _loaded_at
FROM all_images
INNER JOIN artworks
    ON all_images.source_object_id = artworks.source_object_id
    AND all_images.source_system = artworks.source_system
```

### Key Design Notes

- **`source_image_id` pattern (D6):** Single generic column. Met emits NULL. AIC emits the IIIF UUID (36-char). When CMA arrives, it emits whatever identifier CMA uses. Consumers who need to reconstruct URLs branch on `source_system`.
- **INNER JOIN to `dim_artworks`:** An image without a matching artwork is orphaned and excluded. This is intentional -- if extraction loaded images but not their parent artwork, we don't surface them in Gold.
- **Surrogate key formula:** `MD5(artwork_id + image_type + ordinal_position)`. Since `artwork_id` already encodes `source_system`, there is zero cross-source collision risk.
- **`_extracted_at` column:** NOT in the final SELECT (not in the contract). It's used only for the incremental watermark filter. The target table uses `_loaded_at` (build timestamp) for its own watermark.

---

## Implementation: openaccess_catalog.sql

### Design

**No structural changes required.** This OBT reads from `dim_artworks`, `dim_artists`, and `fct_artwork_images` -- all of which now include AIC data. The existing filters (`is_public_domain = TRUE`, `image_type = 'primary'`, `ordinal_position = 1`) work correctly for both sources.

### Expected Behavior After Phase 3

- Row count jumps from ~500 (Met seed only) to ~58,000 (AIC public-domain with images + Met)
- `image_url` column now contains both Met CDN URLs and AIC IIIF URLs
- `source_system` column now has two distinct values

### Changes Needed

None to the SQL. The model works as-is. The contract in `_marts__models.yml` remains valid.

---

## Implementation: _marts__models.yml (Contract & Tests)

### Contract Change: `fct_artwork_images`

Add `source_image_id` column (nullable VARCHAR):

```yaml
- name: source_image_id
  data_type: varchar(16777216)
  description: "Source system's native image identifier. AIC: IIIF UUID (36-char). Met: NULL. Generic column for all sources (D6)."
```

Insert it between `artwork_id` and `image_url` in the column list (matching the SELECT order in the SQL).

### Full Updated `fct_artwork_images` Contract

```yaml
- name: fct_artwork_images
  description: "One row per image per artwork. Includes primary and additional images from all sources."
  config:
    contract:
      enforced: true
  columns:
    - name: image_id
      data_type: varchar(32)
      description: "Surrogate PK: MD5(artwork_id + image_type + ordinal_position)"
      tests:
        - unique
        - not_null
    - name: artwork_id
      data_type: varchar(32)
      description: "FK to dim_artworks"
      tests:
        - not_null
        - relationships:
            to: ref('dim_artworks')
            field: artwork_id
    - name: source_image_id
      data_type: varchar(16777216)
      description: "Source system's native image identifier. AIC: IIIF UUID. Met: NULL."
    - name: image_url
      data_type: varchar(16777216)
      description: "Full-resolution image URL"
      tests:
        - not_null
    - name: image_url_small
      data_type: varchar(16777216)
      description: "Thumbnail/small image URL"
    - name: image_type
      data_type: varchar(16777216)
      description: "primary or additional"
      tests:
        - not_null
        - accepted_values:
            values: ['primary', 'additional']
    - name: ordinal_position
      data_type: number(38,0)
      description: "Position within image set (primary=1, additional=2+)"
      tests:
        - not_null
    - name: source_system
      data_type: varchar(16777216)
      description: "Source museum identifier"
      tests:
        - not_null
        - accepted_values:
            values: ['met_museum', 'art_institute_chicago']
    - name: _loaded_at
      data_type: timestamp_ntz(9)
      description: "Timestamp of dbt materialization"
      tests:
        - not_null
```

---

## Governance Tests

### Multi-Source Completeness

These tests ensure both sources are present and contributing meaningful data.

**On `dim_artists`:**
```yaml
tests:
  - dbt_expectations.expect_column_distinct_count_to_be_between:
      column_name: source_system
      min_value: 2
      max_value: 2
      config:
        severity: error
```

**On `dim_artworks`:**
```yaml
tests:
  - dbt_expectations.expect_column_distinct_count_to_be_between:
      column_name: source_system
      min_value: 2
      max_value: 2
      config:
        severity: error
```

**On `fct_artwork_images`:**
```yaml
tests:
  - dbt_expectations.expect_column_distinct_count_to_be_between:
      column_name: source_system
      min_value: 2
      max_value: 2
      config:
        severity: error
```

### Per-Source Minimum Row Counts

Singular test (placed in `tests/` directory or as a custom generic test):

```sql
-- tests/assert_minimum_rows_per_source.sql
-- Ensures each source contributes a meaningful number of rows to Gold.
-- Catches silent extraction failures where a source returns 0 rows.

{% test assert_min_rows_per_source(model, column_name, min_rows) %}

SELECT
    {{ column_name }},
    COUNT(*) AS row_count
FROM {{ model }}
GROUP BY {{ column_name }}
HAVING COUNT(*) < {{ min_rows }}

{% endtest %}
```

Applied in YAML:
```yaml
- name: dim_artworks
  tests:
    - assert_min_rows_per_source:
        column_name: source_system
        min_rows: 100
```

### FK Integrity (Orphan Detection)

Already captured via the `relationships` test on `fct_artwork_images.artwork_id -> dim_artworks.artwork_id`. This test fails if any image row has an `artwork_id` not present in `dim_artworks`.

### Artist FK NULL Rate Monitor

```yaml
- name: dim_artworks
  columns:
    - name: artist_id
      tests:
        - dbt_expectations.expect_column_proportion_of_values_to_be_between:
            min_value: 0.75
            max_value: 1.0
            row_condition: "source_system = 'art_institute_chicago'"
            description: "At least 75% of AIC artworks should resolve an artist FK. Lower = possible join logic failure."
```

### What These Tests Catch

| Failure Mode | Test That Catches It |
|--------------|---------------------|
| AIC extraction fails (0 rows in Bronze) | `source_system` distinct count = 1 (FAIL) |
| AIC Silver view breaks (syntax error) | `dbt build` fails at compile time |
| FK join logic broken (all NULL artist_id) | artist_id proportion test (FAIL) |
| Image orphans (artwork not in dim) | relationships test (FAIL) |
| Column type mismatch in UNION | Contract enforcement at materialization |
| Column positional swap in UNION | NOT caught by tests (manual code review) |

---

## Cluster Key Documentation

### Configuration

In `fct_artwork_images.sql`:
```sql
{{ config(cluster_by=['source_system']) }}
```

This tells Snowflake to organize micro-partitions so rows with the same `source_system` value are co-located. Queries that filter on `source_system` can skip entire micro-partitions (partition pruning).

### Why This Is a No-Op at Current Scale

At ~137k rows, Snowflake stores the entire table in 1-3 micro-partitions. Since ALL data fits in a tiny number of partitions, there's nothing to prune -- every query reads everything regardless of cluster key. The cluster key only provides value when data spans MANY micro-partitions (hundreds+).

### The Heuristic: When to Cluster

| Row Count | Recommendation |
|-----------|---------------|
| < 1M | Never cluster. Zero benefit. Maintenance credits wasted. |
| 1M - 10M | Cluster only if query profiles show < 50% partition pruning on a dominant filter |
| 10M - 100M | Strong candidate if queries consistently filter on 1-2 columns |
| > 100M | Almost always benefits. Choose the most selective filter predicate. |

### Monitoring: `SYSTEM$CLUSTERING_INFORMATION`

After the table is materialized, run these queries to observe cluster key behavior:

```sql
-- Basic clustering info: shows average overlap and depth
SELECT SYSTEM$CLUSTERING_INFORMATION('ARTWORK_DB.GOLD.FCT_ARTWORK_IMAGES', '(source_system)');
```

**Output interpretation:**
```json
{
  "cluster_by_keys": "LINEAR(source_system)",
  "total_partition_count": 2,
  "total_constant_partition_count": 2,
  "average_overlaps": 0.0,
  "average_depth": 1.0,
  "partition_depth_histogram": { "00001": 2 }
}
```

- `total_partition_count`: Number of micro-partitions. At 137k rows, expect 1-3.
- `total_constant_partition_count`: Partitions where ALL rows have the same cluster key value. Ideal = total_partition_count.
- `average_overlaps`: How many partitions share the same key value range. 0 = perfect (no overlap). High = poor clustering.
- `average_depth`: Average number of partitions a query must scan for a single key value. 1.0 = perfect. Higher = worse.
- `partition_depth_histogram`: Distribution of partition depths. All in "00001" = every key value hits exactly 1 partition.

```sql
-- Clustering ratio for a specific query pattern
SELECT SYSTEM$CLUSTERING_DEPTH('ARTWORK_DB.GOLD.FCT_ARTWORK_IMAGES', '(source_system, artwork_id)');
```

```sql
-- View DML history (reclustering operations) -- shows if Snowflake is spending
-- credits maintaining this key. At small scale, expect zero reclustering events.
SELECT *
FROM TABLE(INFORMATION_SCHEMA.AUTOMATIC_CLUSTERING_HISTORY(
    DATE_RANGE_START => DATEADD('day', -7, CURRENT_DATE()),
    TABLE_NAME => 'ARTWORK_DB.GOLD.FCT_ARTWORK_IMAGES'
));
```

### When to Remove the Cluster Key

If `AUTOMATIC_CLUSTERING_HISTORY` shows credits being consumed but `SYSTEM$CLUSTERING_INFORMATION` already shows perfect depth (1.0), the cluster key is costing money for no benefit. Remove it:

```sql
ALTER TABLE ARTWORK_DB.GOLD.FCT_ARTWORK_IMAGES DROP CLUSTERING KEY;
```

Or in dbt, remove `cluster_by` from the config and run `--full-refresh`.

---

## Follow-Up: dim_artworks Incremental Exercise

**Deferred to a separate implementation session.** Captured here for continuity.

### Why dim_artworks Is a Good Second Exercise

- Exercises SCD Type 1 (merge with updates) vs append-only (fct_artwork_images)
- The `unique_key` is the surrogate `artwork_id`
- Late-arriving metadata corrections (title change, reclassification) trigger UPDATES
- New extractions add rows (INSERTS)

### Key Questions to Resolve When Implementing

1. **Watermark column:** `_extracted_at` from `stg_aic__artworks` works, but Met staging doesn't have `_extracted_at`. Need to add it or use a different watermark strategy.
2. **dim_artists dependency:** `dim_artworks` refs `dim_artists`. If both are incremental, does dbt handle the DAG ordering correctly? (Yes -- dbt always respects ref ordering regardless of materialization.)
3. **Artist FK re-resolution:** If an artist's `sort_title` changes in a subsequent extraction, the FK join in `dim_artworks` could resolve to a DIFFERENT `artist_id`. With incremental merge on `artwork_id`, this updates correctly. But it means the same artwork could point to different artist_id values across builds if the artist dimension changes.

### Incremental Config (Preview)

```sql
{{
    config(
        materialized='incremental',
        unique_key='artwork_id',
        incremental_strategy='merge',
        on_schema_change='fail'
    )
}}
```

---

## Execution Checklist

Run these steps IN ORDER after code changes are written to the workspace:

```bash
# 1. Compile (validates SQL + Jinja without hitting Snowflake)
dbt compile --project-dir artwork_pipeline --target snowflake

# 2. Run staging first (creates AIC Silver views if not exist)
dbt run --project-dir artwork_pipeline --target snowflake --select tag:staging

# 3. Run Gold models (creates/replaces tables)
dbt run --project-dir artwork_pipeline --target snowflake --select tag:marts

# 4. Run tests (validates contracts, relationships, row counts)
dbt test --project-dir artwork_pipeline --target snowflake --select tag:marts

# 5. Or do it all at once (respects DAG order: staging views -> Gold tables -> tests)
dbt build --project-dir artwork_pipeline --target snowflake
```

### Expected Output (First Run)

| Model | Action | Expected Rows |
|-------|--------|---------------|
| `stg_aic__artists` | CREATE VIEW | ~16,051 (all agents) |
| `stg_aic__artworks` | CREATE VIEW | ~134,078 |
| `stg_aic__images` | CREATE VIEW | ~137,383 |
| `dim_artists` | CREATE TABLE | ~14,266 (14,105 AIC artists + 161 Met) |
| `dim_artworks` | CREATE TABLE | ~134,581 (134,078 AIC + 503 Met) |
| `fct_artwork_images` | CREATE TABLE | ~138,293 (137,383 AIC + 910 Met) |
| `openaccess_catalog` | CREATE TABLE | ~58,000 (public domain + has image) |

### Verification Queries (Post-Build)

```sql
-- Source distribution check
SELECT source_system, COUNT(*) FROM ARTWORK_DB.GOLD.DIM_ARTISTS GROUP BY 1;
SELECT source_system, COUNT(*) FROM ARTWORK_DB.GOLD.DIM_ARTWORKS GROUP BY 1;
SELECT source_system, COUNT(*) FROM ARTWORK_DB.GOLD.FCT_ARTWORK_IMAGES GROUP BY 1;

-- FK join success rate (should be > 75% for AIC)
SELECT
    source_system,
    COUNT(*) AS total,
    COUNT(artist_id) AS matched,
    ROUND(COUNT(artist_id) / COUNT(*) * 100, 1) AS match_pct
FROM ARTWORK_DB.GOLD.DIM_ARTWORKS
GROUP BY 1;

-- Cluster key status
SELECT SYSTEM$CLUSTERING_INFORMATION('ARTWORK_DB.GOLD.FCT_ARTWORK_IMAGES', '(source_system)');

-- openaccess_catalog row count by source
SELECT source_system, COUNT(*) FROM ARTWORK_DB.GOLD.OPENACCESS_CATALOG GROUP BY 1;
```
