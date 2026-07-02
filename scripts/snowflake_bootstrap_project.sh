#!/usr/bin/env bash
# Apply project Snowflake infrastructure and register service-user key pairs.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/snowflake_account_defaults.sh
source "${SCRIPT_DIR}/snowflake_account_defaults.sh"

usage() {
    cat <<EOF_USAGE
usage: $0 [common options] [--yes] [--skip-infra] [--env-file PATH]

Runs the project bootstrap steps:
  1. make infra CONN=<profile>
  2. snowflake-toolkit setup.sh --phase promote
  3. snowflake-toolkit setup.sh --phase loader
  4. snowflake-toolkit setup.sh --phase transformer
  5. scripts/snowflake_write_local_env.sh

${COMMON_USAGE}
EOF_USAGE
}

YES=0
SKIP_INFRA=0
ENV_FILE="${REPO_ROOT}/.env"
DRY_RUN=0
COMMON_ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --yes|-y) YES=1; shift ;;
        --skip-infra) SKIP_INFRA=1; shift ;;
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
require_toolkit
if [[ "${DRY_RUN}" -eq 0 ]]; then
    ensure_profile_not_pointing_elsewhere
fi

print_connection_summary
cat <<EOF_INFO

This will mutate Snowflake for the selected account by applying project DDL and
registering service-user public keys. The private keys remain local under
~/.snowflake/keys.

EOF_INFO

if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo "Dry run: would execute:"
    if [[ "${SKIP_INFRA}" -eq 0 ]]; then
        printf 'make -C %q infra TOOLKIT_DIR=%q CONN=%q\n' "${REPO_ROOT}" "${TOOLKIT_DIR}" "${SNOW_ARTWORK_PROFILE}"
    else
        echo "# make infra skipped"
    fi
    print_toolkit_phase promote
    print_toolkit_phase loader
    print_toolkit_phase transformer
    printf 'bash %q --profile %q --account %q --admin-user %q --admin-role %q --init-warehouse %q --warehouse %q --database %q --toolkit-dir %q --env-file %q\n' \
        "${SCRIPT_DIR}/snowflake_write_local_env.sh" "${SNOW_ARTWORK_PROFILE}" "${SNOW_ARTWORK_ACCOUNT}" \
        "${SNOW_ARTWORK_ADMIN_USER}" "${SNOW_ARTWORK_ADMIN_ROLE}" "${SNOW_ARTWORK_INIT_WAREHOUSE}" \
        "${SNOW_ARTWORK_PROJECT_WAREHOUSE}" "${SNOW_ARTWORK_DATABASE}" "${TOOLKIT_DIR}" "${ENV_FILE}"
    exit 0
fi

if [[ "${YES}" -ne 1 ]]; then
    read -r -p "Proceed with project bootstrap for profile '${SNOW_ARTWORK_PROFILE}'? [y/N] " answer
    case "${answer}" in
        y|Y|yes|YES) ;;
        *) echo "Aborted."; exit 0 ;;
    esac
fi

if [[ "${SKIP_INFRA}" -eq 0 ]]; then
    make -C "${REPO_ROOT}" infra TOOLKIT_DIR="${TOOLKIT_DIR}" CONN="${SNOW_ARTWORK_PROFILE}"
else
    echo "Skipping make infra because --skip-infra was supplied."
fi

run_toolkit_phase promote
run_toolkit_phase loader
run_toolkit_phase transformer

bash "${SCRIPT_DIR}/snowflake_write_local_env.sh" \
    --profile "${SNOW_ARTWORK_PROFILE}" --account "${SNOW_ARTWORK_ACCOUNT}" \
    --admin-user "${SNOW_ARTWORK_ADMIN_USER}" --admin-role "${SNOW_ARTWORK_ADMIN_ROLE}" \
    --init-warehouse "${SNOW_ARTWORK_INIT_WAREHOUSE}" --warehouse "${SNOW_ARTWORK_PROJECT_WAREHOUSE}" \
    --database "${SNOW_ARTWORK_DATABASE}" --toolkit-dir "${TOOLKIT_DIR}" --env-file "${ENV_FILE}"

cat <<EOF_DONE

Project Snowflake bootstrap complete if all phases above passed.
Suggested checks:
  snow connection test -c ${SNOW_ARTWORK_PROFILE}
  snow connection test -c ${SNOW_ARTWORK_PROFILE}_loader
  snow connection test -c ${SNOW_ARTWORK_PROFILE}_transformer
  bash scripts/dbt_orchestrate.sh init --connection ${SNOW_ARTWORK_PROFILE}
EOF_DONE
