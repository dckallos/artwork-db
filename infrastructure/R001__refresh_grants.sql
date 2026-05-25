-- =============================================================================
-- R001: Repeatable grant refresh
-- Re-run anytime to ensure roles have access to all current and future objects.
-- No paired drop (repeatable scripts are pure idempotent re-runs).
-- =============================================================================

USE ROLE ARTWORK_ADMIN;

-- Re-grant on all current Bronze objects
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA ARTWORK_DB.BRONZE TO ROLE ARTWORK_LOADER;
GRANT READ, WRITE ON ALL STAGES IN SCHEMA ARTWORK_DB.BRONZE TO ROLE ARTWORK_LOADER;

-- Re-grant transformer read on Bronze
GRANT SELECT ON ALL TABLES IN SCHEMA ARTWORK_DB.BRONZE TO ROLE ARTWORK_TRANSFORMER;

-- Re-grant transformer write on Silver
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA ARTWORK_DB.SILVER TO ROLE ARTWORK_TRANSFORMER;
GRANT SELECT ON ALL VIEWS IN SCHEMA ARTWORK_DB.SILVER TO ROLE ARTWORK_TRANSFORMER;

-- Re-grant transformer write on Gold
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA ARTWORK_DB.GOLD TO ROLE ARTWORK_TRANSFORMER;
GRANT SELECT ON ALL VIEWS IN SCHEMA ARTWORK_DB.GOLD TO ROLE ARTWORK_TRANSFORMER;
