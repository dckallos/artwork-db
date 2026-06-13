-- =============================================================================
-- assert_aic_artist_match_rate.sql
-- =============================================================================
-- Singular test: fails if fewer than 75% of AIC artworks resolve an artist FK.
--
-- WHY this test exists:
--   dim_artworks uses a string-match LEFT JOIN to resolve artist_id from
--   dim_artists (the "round-trip" FK pattern, P3-1). If the join logic breaks
--   silently (e.g., sort_title format changes, ULAN coalesce mismatch), the
--   symptom is a spike in NULL artist_id values for AIC rows. This test catches
--   that degradation before it propagates to openaccess_catalog.
--
-- Threshold rationale:
--   AIC has ~134k artworks. Nearly all have an artist_id FK in Bronze. After
--   filtering to is_artist=TRUE and the string-match join, we expect >90% to
--   resolve. The 75% threshold gives headroom for edge cases (anonymous works,
--   corporate entities filtered out by is_artist=TRUE) while still catching
--   catastrophic join failures.
--
-- Returns 0 rows = PASS. Returns 1 row = FAIL.
-- =============================================================================

WITH stats AS (
    SELECT
        COUNT(*) AS total,
        COUNT(artist_id) AS matched
    FROM {{ ref('dim_artworks') }}
    WHERE source_system = 'art_institute_chicago'
)

SELECT *
FROM stats
WHERE matched < total * 0.75
