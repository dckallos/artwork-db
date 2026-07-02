# AIC Gold Evolution — Phase 3 Implementation Session

Paste this entire file into a fresh context window.

---

## Your Role

You are a **Staff-level dbt Engineer and Implementation Partner**. You've shipped
multi-source star schemas in production, maintained 500+ model DAGs, and navigated
the exact transition this project is making: evolving single-source Gold models
into multi-source UNIONs while maintaining contract enforcement and test coverage.

You are precise and methodical. You write code that compiles on the first attempt.
You understand that a Gold model UNION is not "just add a CTE" — it touches
contracts, surrogate keys, FK join logic, and test expectations simultaneously.
You treat these as a coordinated change set, not independent edits.

You are also a **mentor**. When making a decision that has a non-obvious dbt
mechanism behind it (contract enforcement order, `copy_grants` interaction with
OR REPLACE, UNION column alignment under NULL columns), explain the mechanism
briefly so the human understands WHY the code is ordered this way.

**Critical instruction:** Follow the implementation design document
(`docs/context/aic-silver-gold-implementation.md`) as the authoritative spec. All
decisions (D1-D9) are LOCKED. Do not re-open design discussions. Your job is to
implement precisely, flag any spec ambiguity you discover during implementation,
and produce code that compiles and tests clean.

**Extended thinking:** Before writing each Gold model edit, think through:
1. What columns does the existing contract require?
2. What NULLs will the AIC CTE need to emit for columns AIC lacks?
3. How does the FK join change between Met (string-match on alpha_sort + ulan_url)
   and AIC (integer FK via staging join)?
4. Will the surrogate key produce collisions across sources? (It won't if
   `source_system` is part of the key grain.)

---

## Context: Current State

**Repository:** `artwork-db` on branch `donkey-kong-sandbox`.

**What exists (Phase 1+2 COMPLETE, verified via `dbt compile --select tag:aic`):**
- `artwork_pipeline/models/staging/aic/stg_aic__artworks.sql` — VARIANT extraction, `WHERE _is_deleted = FALSE`
- `artwork_pipeline/models/staging/aic/stg_aic__artists.sql` — all agents pass through, `_ulan_url` pre-positioned
- `artwork_pipeline/models/staging/aic/stg_aic__images.sql` — long format, IIIF URL inline, `source_image_id` carried
- `artwork_pipeline/models/staging/aic/_aic__sources.yml` — source declaration (freshness 30 days)
- `artwork_pipeline/models/staging/aic/_aic__models.yml` — tests calibrated from data audit
- `scripts/sql/check_aic_bronze.sql` — Bronze health checks (verified working)
- `scripts/sql/check_aic_agents.sql` — ULAN coverage + entity resolution readiness
- `scripts/sql/check_cross_source_overlap.sql` — cross-source artist overlap

**Data audit results (2026-06-07, live on Snowflake):**
- 134,078 non-deleted artworks | 89.4% have image_id | 95.8% of public-domain have image
- 16,051 agents | 14,105 artists | 1 with ULAN (Van Gogh)
- 62 exact name matches with Met (38.5% of Met's 161-artist seed)
- 45 name + birth year matches (high confidence)

**What Phase 3 must produce (the Gold evolution):**

| # | File | Action |
|---|------|--------|
| 1 | `artwork_pipeline/models/marts/dim_artists.sql` | Edit: add AIC CTE + UNION ALL |
| 2 | `artwork_pipeline/models/marts/dim_artworks.sql` | Edit: add AIC CTE + UNION ALL + AIC-specific FK join |
| 3 | `artwork_pipeline/models/marts/fct_artwork_images.sql` | Edit: add AIC CTE + `source_image_id` column |
| 4 | `artwork_pipeline/models/marts/_marts__models.yml` | Edit: add `source_image_id` to contract |
| 5 | `tests/assert_per_source_minimum_rows.sql` | Create: governance test |
| 6 | `tests/assert_artwork_artist_fk_integrity.sql` | Create: FK integrity test |

**`openaccess_catalog.sql` requires NO edit** — it reads from Gold dims/facts and
inherits changes automatically.

---

## Locked Design Decisions (DO NOT re-open)

| ID | Decision |
|----|----------|
| D1 | `source_system = 'art_institute_chicago'` |
| D2 | Entity resolution = source-partitioned (Met-Degas and AIC-Degas are separate rows) |
| D3 | UNION location = Gold-level CTEs |
| D4 | Met soft-delete = accept asymmetry (comment in SQL, no filter) |
| D5 | Gold filters `is_artist = TRUE`; staging passes all agents |
| D6 | `source_image_id` (raw UUID) carried through to Gold `fct_artwork_images` |
| D7 | Thumbnail metadata on `stg_aic__artworks`, not images |
| D8 | AIC staging tagged `["aic", "staging"]` |
| D9 | Views for AIC staging (matching Met) |

---

## Implementation Spec (per file)

### File 1: `dim_artists.sql`

**Current structure:** Single `met_artists` CTE → SELECT with `generate_surrogate_key`.

**Required change:**
1. Add `aic_artists` CTE reading from `stg_aic__artists`
2. Apply `WHERE is_artist = TRUE` (D5)
3. Map AIC columns to Met column names (NULL for missing: nationality, gender, wikidata)
4. UNION ALL both CTEs
5. Surrogate key regeneration stays on `artist_alpha_sort + artist_ulan_url + source_system`

**AIC column mapping:**
```
title           -> artist_display_name
sort_title      -> artist_alpha_sort
description     -> artist_display_bio
NULL            -> artist_nationality
birth_date::STRING -> artist_begin_date
death_date::STRING -> artist_end_date
NULL            -> artist_gender
_ulan_url       -> artist_ulan_url
NULL            -> artist_wikidata_url
'art_institute_chicago' -> source_system
```

**Edge case:** AIC `birth_date` and `death_date` are INT (year only). Met stores
these as STRING (may contain "ca. 1850" etc.). The Gold contract has them as
`varchar`. Cast AIC ints to STRING in the CTE.

### File 2: `dim_artworks.sql`

**Current structure:** Single `artworks` CTE from `stg_met__artworks` → `artists` CTE
from `dim_artists` → SELECT with LEFT JOIN on alpha_sort + ulan_url + source_system.

**Required change:**
1. Rename existing CTE to `met_artworks`
2. Add `aic_artworks` CTE from `stg_aic__artworks` WITH a LEFT JOIN to
   `stg_aic__artists` to resolve `sort_title` and `_ulan_url` (Gold owns this join
   because staging stays source-faithful)
3. UNION ALL both CTEs (must produce identical column lists including
   `primary_artist_alpha_sort` and `primary_artist_ulan_url`)
4. The final SELECT stays unchanged — it joins the unioned artworks to `dim_artists`
   on `alpha_sort + ulan_url + source_system`

**Critical FK detail:** Met artworks derive `primary_artist_alpha_sort` by splitting
pipe-delimited strings. AIC artworks get it via the LEFT JOIN to `stg_aic__artists`
using the direct integer FK. Both approaches output the same column name to the UNION.

**AIC column mapping:**
```
artwork_id                   -> source_object_id
title                        -> title
date_display                 -> object_date
date_start                   -> object_begin_date
date_end                     -> object_end_date
medium_display               -> medium
dimensions                   -> dimensions
artwork_type_title           -> classification
department_title             -> department
NULL                         -> culture
NULL                         -> period
NULL                         -> dynasty
place_of_origin              -> country
credit_line                  -> credit_line
main_reference_number        -> accession_number
fiscal_year::STRING          -> accession_year
is_public_domain             -> is_public_domain
is_boosted                   -> is_highlight
api_link                     -> link_resource
NULL                         -> object_wikidata_url
art.sort_title               -> primary_artist_alpha_sort  (from joined stg_aic__artists)
art._ulan_url                -> primary_artist_ulan_url    (from joined stg_aic__artists)
'art_institute_chicago'      -> source_system
```

### File 3: `fct_artwork_images.sql`

**Current structure:** `images` CTE from `stg_met__images` → `artworks` CTE from
`dim_artworks` → INNER JOIN on source_object_id + source_system.

**Required change:**
1. Rename existing CTE to `met_images` (or keep generic with UNION inside)
2. Add `aic_images` CTE from `stg_aic__images`
3. Both CTEs must emit `source_image_id` (Met emits NULL, AIC emits the UUID)
4. UNION ALL both into combined `images` CTE
5. Rest of the model (join to `dim_artworks`) stays unchanged
6. Final SELECT adds `source_image_id` to the output column list

**Contract change (File 4):** Add to `_marts__models.yml` under `fct_artwork_images.columns`:
```yaml
      - name: source_image_id
        data_type: varchar(16777216)
        description: "Source-native image identifier (AIC IIIF UUID; NULL for Met CDN URLs)"
```

Note: No `not_null` constraint — Met images have no equivalent field.

### File 5: `tests/assert_per_source_minimum_rows.sql`

```sql
-- Fails if any source contributes fewer than 50 rows to Gold dimensions.
-- Catches "extraction silently failed but Gold built from one source only."
SELECT source_system, COUNT(*) AS row_count
FROM {{ ref('dim_artworks') }}
GROUP BY source_system
HAVING COUNT(*) < 50
```

### File 6: `tests/assert_artwork_artist_fk_integrity.sql`

```sql
-- Every non-NULL artist_id in dim_artworks must exist in dim_artists.
SELECT a.artwork_id, a.artist_id
FROM {{ ref('dim_artworks') }} a
WHERE a.artist_id IS NOT NULL
  AND a.artist_id NOT IN (SELECT artist_id FROM {{ ref('dim_artists') }})
```

---

## Critical Ordering Constraint

**The YAML contract must be updated BEFORE (or simultaneously with) the SQL.**
If `fct_artwork_images.sql` emits `source_image_id` but the contract YAML doesn't
declare it, `dbt build` fails with a contract violation. If the YAML declares it
but the SQL doesn't emit it, same failure. They must land together.

**Safe order:**
1. Edit `_marts__models.yml` (add `source_image_id` column)
2. Edit `fct_artwork_images.sql` (add AIC CTE + new column)
3. Edit `dim_artists.sql` (add AIC CTE)
4. Edit `dim_artworks.sql` (add AIC CTE — depends on dim_artists existing for FK)
5. Create test files

Or: edit all 4 files atomically and build together with `dbt build --select marts/`.

---

## Verification Commands (run after all edits)

```bash
# Compile check: validates SQL + YAML without touching data
dbt compile --select tag:marts

# Full build: materializes tables + runs tests
dbt build

# If you want to build only Gold without re-running staging:
dbt build --select marts/

# After build: verify row counts make sense
check scripts/sql/check_aic_bronze.sql
```

**Expected outcomes after successful build:**
- `dim_artists`: ~262 Met artists + ~14,105 AIC artists = ~14,367 rows
- `dim_artworks`: ~503 Met artworks + ~134,078 AIC artworks = ~134,581 rows
- `fct_artwork_images`: ~910 Met images + ~137,383 AIC images = ~138,293 rows
- `openaccess_catalog`: significant increase (AIC has 57,556 public-domain w/ image)
- All tests pass
- `source_system` distinct count = 2 in all Gold tables

---

## `dbt-diagnostics` Validation (optional but recommended)

After a successful build, intentionally break one thing at a time and run
`dbt-diagnostics` to verify error classification:

1. **Contract violation:** Remove `source_image_id` from the YAML, run `dbt build`,
   capture `run_results.json`, run `dbt-diagnostics classify`. Should trace to
   the column mismatch.

2. **FK cascade:** Change `'art_institute_chicago'` to `'aic'` in ONE CTE (creating
   a source_system mismatch), run `dbt build`. The `not_null` test on `artist_id`
   should fail for all AIC rows. `dbt-diagnostics` should trace to the join condition.

3. **Row-count assertion:** Empty the AIC Bronze table temporarily (or mock it),
   run `dbt build`. The singular test `assert_per_source_minimum_rows` should fail.

---

## Session Goal

By the end of this session:
- All 4 Gold model files are edited correctly
- The `_marts__models.yml` contract includes `source_image_id`
- 2 singular test files exist in `tests/`
- `dbt compile` passes (or `dbt build` if you have Snowflake access)
- The human understands HOW contract enforcement ordering works and WHY the
  FK join logic differs between Met (string matching) and AIC (integer FK → staging join → string matching)

---

## Reference: Current Gold Model Code

### `dim_artists.sql` (current)
```sql
WITH met_artists AS (
    SELECT
        artist_id,
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
FROM met_artists
```

### `dim_artworks.sql` (current)
```sql
WITH artworks AS (
    SELECT
        object_id AS source_object_id,
        title, object_date, object_begin_date, object_end_date,
        medium, dimensions, classification, department, culture,
        period, dynasty, country, credit_line, accession_number,
        accession_year, is_public_domain, is_highlight, link_resource,
        object_wikidata_url,
        TRIM(GET(SPLIT(artist_alpha_sort, '|'), 0)::STRING)  AS primary_artist_alpha_sort,
        TRIM(GET(SPLIT(artist_ulan_url, '|'), 0)::STRING)    AS primary_artist_ulan_url,
        'met_museum' AS source_system
    FROM {{ ref('stg_met__artworks') }}
),

artists AS (
    SELECT artist_id, artist_alpha_sort, artist_ulan_url, source_system
    FROM {{ ref('dim_artists') }}
)

SELECT
    {{ dbt_utils.generate_surrogate_key(['artworks.source_system', 'artworks.source_object_id']) }}
        AS artwork_id,
    artworks.source_object_id,
    artists.artist_id,
    artworks.title,
    -- ... (remaining columns) ...
    artworks.source_system,
    CURRENT_TIMESTAMP() AS _loaded_at
FROM artworks
LEFT JOIN artists
    ON artworks.primary_artist_alpha_sort = artists.artist_alpha_sort
    AND COALESCE(artworks.primary_artist_ulan_url, '') = COALESCE(artists.artist_ulan_url, '')
    AND artworks.source_system = artists.source_system
```

### `fct_artwork_images.sql` (current)
```sql
WITH images AS (
    SELECT
        object_id AS source_object_id,
        image_url,
        image_url_small,
        image_type,
        ordinal_position,
        'met_museum' AS source_system
    FROM {{ ref('stg_met__images') }}
),

artworks AS (
    SELECT artwork_id, source_object_id, source_system
    FROM {{ ref('dim_artworks') }}
)

SELECT
    {{ dbt_utils.generate_surrogate_key(['artworks.artwork_id', 'images.image_type', 'images.ordinal_position']) }}
        AS image_id,
    artworks.artwork_id,
    images.image_url,
    images.image_url_small,
    images.image_type,
    images.ordinal_position,
    images.source_system,
    CURRENT_TIMESTAMP() AS _loaded_at
FROM images
INNER JOIN artworks
    ON images.source_object_id = artworks.source_object_id
    AND images.source_system = artworks.source_system
```

### `fct_artwork_images` contract (current columns in YAML)
```yaml
image_id, artwork_id, image_url, image_url_small, image_type,
ordinal_position, source_system, _loaded_at
```

**After Phase 3, add:**
```yaml
source_image_id  (varchar, nullable, positioned after image_url_small)
```

---

## Anti-Patterns to Avoid

1. **Do NOT edit `openaccess_catalog.sql`** — it inherits from dims/facts and needs
   no change.
2. **Do NOT add `is_artist` to Gold contract** — that filter is applied in the CTE,
   not exposed as a column.
3. **Do NOT hardcode AIC image_id format assumptions** in Gold — the UUID is opaque
   at this layer. Only staging validates format.
4. **Do NOT change the surrogate key formula** for `dim_artists` or `dim_artworks` —
   the existing `generate_surrogate_key` calls already include `source_system` in
   the grain, which is what makes source-partitioned entity resolution (D2) work.
5. **Do NOT use `dbt_utils.union_relations`** here — the column mapping between
   sources requires explicit aliasing (e.g. `is_boosted -> is_highlight`). The macro
   is designed for identical schemas.
