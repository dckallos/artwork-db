# Batch A1: Silver Staging (artists + images)

> Started: 2026-06-06  |  Completed: 2026-06-06 (workspace; awaiting Mac sync + dbt run)

## Objective

Complete the Met Silver staging layer in one batch: `stg_met__artists` (deduplicated
artist entities) + `stg_met__images` (primary image URLs, wide format). This collapses
the old per-unit cadence into a single batch build to accelerate the medallion spine.

## Models Authored

### stg_met__artists

- **Grain:** one row per distinct artist entity (keyed on `artist_alpha_sort` +
  `artist_ulan_url`).
- **Surrogate key:** `dbt_utils.generate_surrogate_key(['artist_alpha_sort', 'artist_ulan_url'])`.
- **Split strategy:** `SPLIT_TO_TABLE` on `artist_display_name` only (never NULL),
  then `GET(SPLIT(...), index-1)` for all other pipe-delimited fields. This avoids the
  NULL-kills-cross-join trap where `SPLIT_TO_TABLE(NULL, '|')` returns 0 rows.
- **Dedup:** `QUALIFY ROW_NUMBER() OVER (PARTITION BY alpha_sort, COALESCE(ulan_url, '') ORDER BY _extracted_at DESC) = 1`.
- **Result:** 262 distinct artists from 503+1 source rows (504 after split).

### stg_met__images

- **Grain:** one row per image per object -- `(object_id, image_type, ordinal_position)`.
- **Columns:** `image_url`, `image_url_small`, `image_type` (primary/additional),
  `ordinal_position` (1 = primary, 2+ = additional).
- **Design choice:** Long format via LATERAL FLATTEN on `additional_images` array, UNION ALL
  with the primary image row. Owner initially chose wide (misread "long" as "wide"), then
  corrected -- long preserves all image data without sparse columns.
- **Result:** 910 rows (503 primary + 407 additional), 0 grain duplicates.

## Key Learnings / Teaching Moments

1. **SPLIT_TO_TABLE + NULL = silent row loss.** The initial design used 10 cross-joined
   `SPLIT_TO_TABLE` calls with index alignment. This silently dropped 492/503 rows because
   any NULL field (gender, begin_date, ulan_url) produces 0 rows from SPLIT_TO_TABLE,
   making the cross-join empty for that source row. The fix: split only the anchor field
   (display_name, never NULL) and use `GET(SPLIT(...), pos-1)` for the rest.

2. **Surrogate key collision risk.** With NULL ULAN URLs (46 objects), two artists sharing
   the same alpha_sort would collide. At 503 rows this is safe; at full-collection scale
   (480k+ objects), add `artist_display_bio` to the key grain if collisions appear.

3. **Wide vs. long terminology matters.** "Long" = one row per image (good, preserves data).
   "Wide" = one column per image slot (bad, sparse, rigid). Long is the correct dimensional
   answer at staging -- it feeds Gold naturally and loses nothing. LATERAL FLATTEN + UNION ALL
   is the Snowflake idiom for exploding a JSON array into long format.

## Tests Declared

| Model | Column | Test |
|-------|--------|------|
| stg_met__artists | artist_id | unique, not_null |
| stg_met__artists | artist_display_name | not_null |
| stg_met__artists | artist_alpha_sort | not_null |
| stg_met__images | object_id | not_null, relationships(stg_met__artworks.object_id) |
| stg_met__images | image_url | not_null |
| stg_met__images | image_type | not_null, accepted_values(primary, additional) |
| stg_met__images | ordinal_position | not_null |

## Run Commands (for owner on Mac)

```bash
# After syncing workspace -> Mac:
cd artwork_pipeline
dbt run --select stg_met__artists stg_met__images
dbt test --select stg_met__artists stg_met__images
```

## Status

- [x] Models authored (workspace)
- [x] YAML tests declared
- [x] SQL validated against live data (262 artists, 910 images [503 primary + 407 additional], 0 grain dupes)
- [ ] Owner syncs to Mac
- [ ] Owner runs `dbt run` (materializes views in SILVER)
- [ ] Owner runs `dbt test` (all tests pass)
