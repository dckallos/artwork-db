-- =============================================================================
-- Register the loader RSA public key on the ARTWORK_LOADER_SVC service user so
-- the snow CLI 'loader' connection and the Python extractor can authenticate
-- with SNOWFLAKE_JWT against the configured private_key_file.
--
-- Applied automatically by scripts/snowflake_cli/06_setup_loader_keypair.sh
-- over the ADMIN JWT connection (the loader has no chicken-and-egg problem: a
-- working admin connection already exists, so no password one-shot is needed):
--
--   PUBKEY=$(awk 'NR>1 && !/-----END/ {printf "%s", $0}' \
--       ~/.snowflake/keys/loader_rsa_key.pub)
--   snow sql -c admin \
--       --filename git-setup/operator/register_loader_public_key.sql \
--       --variable loader_user=ARTWORK_LOADER_SVC \
--       --variable rsa_public_key="$PUBKEY" \
--       --enhanced-exit-codes
--
-- The 'loader_user' and 'rsa_public_key' variables are substituted at runtime
-- by the snow CLI. After this script runs, DESCRIBE USER reports a populated
-- RSA_PUBLIC_KEY_FP and 'snow connection test -c loader' succeeds.
--
-- Prerequisite: `make iac` must have already created ARTWORK_LOADER_SVC via
-- infrastructure/create_service_user.sql (TYPE = SERVICE).
--
-- Idempotent: re-running with the same key value is a no-op; re-running with a
-- new key rotates the credential.
-- =============================================================================

ALTER USER &{ loader_user }
    SET RSA_PUBLIC_KEY = '&{ rsa_public_key }';

DESCRIBE USER &{ loader_user };
