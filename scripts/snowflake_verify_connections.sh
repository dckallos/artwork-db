#!/usr/bin/env bash
# Verify the admin, loader, and transformer Snowflake CLI connections.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/snowflake_account_defaults.sh
source "${SCRIPT_DIR}/snowflake_account_defaults.sh"

usage() {
    cat <<EOF_USAGE
usage: $0 [common options]

Runs:
  snow connection test -c <profile>
  snow connection test -c <profile>_loader
  snow connection test -c <profile>_transformer

${COMMON_USAGE}
EOF_USAGE
}

DRY_RUN=0
COMMON_ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        *)
            COMMON_ARGS+=("$1")
            if [[ $# -gt 1 && "${2:-}" != --* ]]; then
                COMMON_ARGS+=("$2")
                shift 2
            else
                shift
            fi
            ;;
    esac
done

if [[ "${#COMMON_ARGS[@]}" -gt 0 ]]; then
    parse_common_account_args "${COMMON_ARGS[@]}"
else
    parse_common_account_args
fi
require_non_empty_defaults

for conn in "${SNOW_ARTWORK_PROFILE}" "${SNOW_ARTWORK_PROFILE}_loader" "${SNOW_ARTWORK_PROFILE}_transformer"; do
    if [[ "${DRY_RUN}" -eq 1 ]]; then
        printf 'snow connection test -c %q\n' "${conn}"
    else
        echo "==> snow connection test -c ${conn}"
        env -u SNOWFLAKE_ROLE -u SNOWFLAKE_USER -u SNOWFLAKE_ACCOUNT \
            -u SNOWFLAKE_WAREHOUSE -u SNOWFLAKE_DATABASE \
            -u SNOWFLAKE_PRIVATE_KEY_FILE -u SNOWFLAKE_AUTHENTICATOR \
            snow connection test -c "${conn}"
    fi
done
