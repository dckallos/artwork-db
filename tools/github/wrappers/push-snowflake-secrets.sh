#!/usr/bin/env bash
#
# push-snowflake-secrets.sh -- thin wrapper for `ghclient secrets publish`.
#
# No arg memorization: dry-run by default (verifies the target GitHub Environment
# exists, reads current secrets/variables, and previews the exact create/update/delete
# plan -- changing nothing). Pass --apply to publish. Secret values are read at apply
# time and handed to `gh` on stdin; they never appear on argv or in the preview (H5).
#
# The required publish set names a `snowflake_secrets.profiles.<name>` block in
# config/github-client-config.yml. Extra args are forwarded (e.g. --env, --force).
#
# Usage:
#   tools/github/wrappers/push-snowflake-secrets.sh --profile-set staging            # dry-run
#   tools/github/wrappers/push-snowflake-secrets.sh --profile-set staging --apply    # publish
#   tools/github/wrappers/push-snowflake-secrets.sh --profile-set prod --env prod --force --apply
set -euo pipefail
exec ghclient secrets publish "$@"
