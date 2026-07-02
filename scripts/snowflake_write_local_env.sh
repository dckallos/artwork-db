#!/usr/bin/env bash
# Write local extraction/dbt connection variables after service keys exist.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/snowflake_account_defaults.sh
source "${SCRIPT_DIR}/snowflake_account_defaults.sh"

usage() {
    cat <<EOF_USAGE
usage: $0 [common options] [--env-file PATH]

Writes the local .env entries needed by:
  extraction/*                  SNOWFLAKE_* loader variables
  artwork_pipeline/profiles.yml DBT_SNOWFLAKE_* transformer variables

${COMMON_USAGE}
EOF_USAGE
}

ENV_FILE="${REPO_ROOT}/.env"
DRY_RUN=0
COMMON_ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --env-file) ENV_FILE="${2:-}"; shift 2 ;;
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

planned_env_values() {
    cat <<EOF_VALUES
SNOWFLAKE_ACCOUNT=${SNOW_ARTWORK_ACCOUNT}
SNOWFLAKE_USER=${SNOW_ARTWORK_LOADER_USER}
SNOWFLAKE_PRIVATE_KEY_FILE=$(loader_key_path)
SNOWFLAKE_ROLE=${SNOW_ARTWORK_LOADER_ROLE}
SNOWFLAKE_WAREHOUSE=${SNOW_ARTWORK_PROJECT_WAREHOUSE}
SNOWFLAKE_DATABASE=${SNOW_ARTWORK_DATABASE}
SNOWFLAKE_SCHEMA=BRONZE
TOOLKIT_DIR=${TOOLKIT_DIR}
SNOW_CONNECTION=${SNOW_ARTWORK_PROFILE}
SNOW_LIB_DEFAULT_WAREHOUSE=${SNOW_ARTWORK_PROJECT_WAREHOUSE}
LOADER_USER=${SNOW_ARTWORK_LOADER_USER}
LOADER_ROLE=${SNOW_ARTWORK_LOADER_ROLE}
TRANSFORMER_USER=${SNOW_ARTWORK_TRANSFORMER_USER}
TRANSFORMER_ROLE=${SNOW_ARTWORK_TRANSFORMER_ROLE}
DBT_SNOWFLAKE_USER=${SNOW_ARTWORK_TRANSFORMER_USER}
DBT_SNOWFLAKE_PRIVATE_KEY_PATH=$(transformer_key_path)
DBT_SNOWFLAKE_ROLE=${SNOW_ARTWORK_TRANSFORMER_ROLE}
EOF_VALUES
}

upsert_env_value() {
    local key="$1"
    local value="$2"
    local tmp
    tmp="$(mktemp)"
    if [[ -f "${ENV_FILE}" ]]; then
        grep -v -E "^${key}=" "${ENV_FILE}" > "${tmp}" || true
    else
        : > "${tmp}"
    fi
    printf '%s=%s\n' "${key}" "${value}" >> "${tmp}"
    mv "${tmp}" "${ENV_FILE}"
    chmod 600 "${ENV_FILE}"
}

if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo "Dry run: would update ${ENV_FILE} with:"
    planned_env_values
    exit 0
fi

mkdir -p "$(dirname "${ENV_FILE}")"
touch "${ENV_FILE}"
chmod 600 "${ENV_FILE}"

while IFS='=' read -r key value; do
    upsert_env_value "${key}" "${value}"
done < <(planned_env_values)

cat <<EOF_DONE
Updated ${ENV_FILE}

Connection values written for profile '${SNOW_ARTWORK_PROFILE}'.
Fill any remaining non-Snowflake secrets manually when needed, such as:
  SMITHSONIAN_API_KEY
  GITHUB_PAT
  GITHUB_OAUTH_CLIENT_ID
  GITHUB_OAUTH_CLIENT_SECRET
EOF_DONE
