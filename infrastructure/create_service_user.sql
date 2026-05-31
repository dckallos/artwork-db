-- =============================================================================
-- create_service_user.sql: Create the service user for the Python extraction layer.
--
-- ARTWORK_LOADER_SVC is the runtime identity used by
-- extraction/*/snowflake_uploader.py. It is intentionally distinct from any
-- human user so the credential can be rotated independently and its activity
-- is cleanly auditable in Snowflake's ACCESS_HISTORY / QUERY_HISTORY views.
--
-- Authentication: KEY-PAIR ONLY. The user is created as TYPE = SERVICE, which
-- is Snowflake's programmatic-only account type -- it CANNOT hold a password
-- and CANNOT use MFA, so the only way in is the RSA key registered after this
-- migration. This removes the placeholder-password smell entirely: there is no
-- credential at rest in this DDL.
--
-- The RSA public key is NOT set here. DDL stays free of key material so this
-- file is idempotent and secret-free. The key is registered out-of-band by the
-- loader bootstrap, which runs AFTER `make iac` over the already-working admin
-- JWT connection:
--   ./scripts/snowflake_cli/setup.sh --phase loader
--       -> 06_setup_loader_keypair.sh
--          (generates the loader key pair, then applies
--           git-setup/operator/register_loader_public_key.sql via `-c admin`)
--
-- Until that key is registered the user exists but cannot authenticate, which
-- is the desired safe default.
--
-- Paired rollback: infrastructure/drop_service_user.sql
-- =============================================================================

USE ROLE ACCOUNTADMIN;

CREATE USER IF NOT EXISTS ARTWORK_LOADER_SVC
    TYPE              = SERVICE
    DISPLAY_NAME      = 'Artwork medallion pipeline loader'
    DEFAULT_ROLE      = ARTWORK_LOADER
    DEFAULT_WAREHOUSE = ARTWORK_WH
    DEFAULT_NAMESPACE = ARTWORK_DB.BRONZE
    COMMENT           = 'Service account (key-pair only) used by extraction/*/snowflake_uploader.py';

GRANT ROLE ARTWORK_LOADER TO USER ARTWORK_LOADER_SVC;

-- Next step (NOT part of `make iac`): register the loader RSA public key so the
-- service user can authenticate. This is automated by:
--   ./scripts/snowflake_cli/setup.sh --phase loader
