-- =============================================================================
-- V008: Create the service user for the Python extraction layer.
--
-- ARTWORK_LOADER_SVC is the runtime identity used by
-- extraction/*/snowflake_uploader.py. It is intentionally distinct from any
-- human user so the credential can be rotated independently and its activity
-- is cleanly auditable in Snowflake's ACCESS_HISTORY / QUERY_HISTORY views.
--
-- Authentication: password by default. Production should rotate to key-pair
-- auth via:  ALTER USER ARTWORK_LOADER_SVC SET RSA_PUBLIC_KEY = '...';
-- Paired rollback: infrastructure/V008__drop_service_user.sql
-- =============================================================================

USE ROLE ACCOUNTADMIN;

CREATE USER IF NOT EXISTS ARTWORK_LOADER_SVC
    PASSWORD             = 'CHANGE_ME_BEFORE_FIRST_RUN'
    LOGIN_NAME           = 'ARTWORK_LOADER_SVC'
    DISPLAY_NAME         = 'Artwork medallion pipeline loader'
    DEFAULT_ROLE         = ARTWORK_LOADER
    DEFAULT_WAREHOUSE    = ARTWORK_WH
    DEFAULT_NAMESPACE    = ARTWORK_DB.BRONZE
    MUST_CHANGE_PASSWORD = FALSE
    COMMENT              = 'Service account used by extraction/*/snowflake_uploader.py';

GRANT ROLE ARTWORK_LOADER TO USER ARTWORK_LOADER_SVC;

-- After applying this migration, rotate the placeholder password immediately:
--   ALTER USER ARTWORK_LOADER_SVC SET PASSWORD = '<strong_random_value>';
-- Then set SNOWFLAKE_PASSWORD in your .env to that same value.
