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

-- -----------------------------------------------------------------------------
-- CONVERGENCE (idempotent) -- close the `CREATE ... IF NOT EXISTS` gap.
--
-- `CREATE USER IF NOT EXISTS` above is a NO-OP when the user already exists, so
-- on an account where ARTWORK_LOADER_SVC was first created as a PERSON/password
-- user, the TYPE = SERVICE clause and the absence of a password are NEVER
-- applied -- DESCRIBE USER keeps showing TYPE = PERSON + PASSWORD = ********,
-- and password auth stays live. These ALTERs make the file CONVERGE on the
-- intended end state whether the user is brand-new or pre-existing.
--
--   * SET TYPE = SERVICE makes the account programmatic-only. A SERVICE user
--     cannot authenticate with a password or MFA, so this statement ALONE
--     disables password login (any stored password becomes inert).
--   * UNSET PASSWORD then removes the stored credential outright, so there is
--     no secret at rest. (Equivalent: SET PASSWORD = NULL.) Order is not
--     enforced -- TYPE-first is Snowflake's documented service-conversion idiom.
--
-- Both ALTERs are idempotent: re-running SET TYPE = SERVICE on a SERVICE user
-- and UNSET PASSWORD on a user with no password are no-op successes.
ALTER USER IF EXISTS ARTWORK_LOADER_SVC SET TYPE = SERVICE;
ALTER USER IF EXISTS ARTWORK_LOADER_SVC UNSET PASSWORD;
ALTER USER IF EXISTS ARTWORK_LOADER_SVC SET COMMENT =
    'Service account (key-pair only) used by extraction/*/snowflake_uploader.py';

-- Next step (NOT part of `make iac`): register the loader RSA public key so the
-- service user can authenticate. This is automated by:
--   ./scripts/snowflake_cli/setup.sh --phase loader
