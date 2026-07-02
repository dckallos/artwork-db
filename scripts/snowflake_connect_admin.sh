#!/usr/bin/env bash
# Create and verify the admin Snowflake CLI profile for this computer.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/snowflake_account_defaults.sh
source "${SCRIPT_DIR}/snowflake_account_defaults.sh"

usage() {
    cat <<EOF_USAGE
usage: $0 [common options] [--phase PHASE]

Creates/verifies the admin Snowflake CLI profile through snowflake-toolkit.

Default phase:
  all                 prereq + admin verification, without applying project IaC

Allowed phases:
  prereq              local Snowflake CLI/key/profile setup only
  init-profile        seed ~/.snowflake/connections.toml only
  admin               register admin public key and verify JWT auth
  all                 prereq + admin
  list                list local Snowflake CLI profiles
  switch              set default_connection_name to this profile

${COMMON_USAGE}
EOF_USAGE
}

PHASE="all"
DRY_RUN=0
COMMON_ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --phase) PHASE="${2:-}"; shift 2 ;;
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

case "${PHASE}" in
    prereq|init-profile|admin|all|list|switch) ;;
    *) echo "error: unsupported phase '${PHASE}'" >&2; usage >&2; exit 64 ;;
esac

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

No Snowflake objects are created by this script. The admin password is not
stored; snowflake-toolkit prompts for it only during the admin phase.

EOF_INFO

if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo "Dry run: would run with environment:"
    printf '  SNOWFLAKE_ACCOUNT=%q\n' "${SNOW_ARTWORK_ACCOUNT}"
    printf '  SNOWFLAKE_ADMIN_USER=%q\n' "${SNOW_ARTWORK_ADMIN_USER}"
    printf '  SNOWFLAKE_ROLE=%q\n' "${SNOW_ARTWORK_ADMIN_ROLE}"
    printf '  SNOWFLAKE_WAREHOUSE=%q\n' "${SNOW_ARTWORK_INIT_WAREHOUSE}"
    echo "Dry run: would execute:"
    print_toolkit_phase "${PHASE}"
    exit 0
fi

SNOWFLAKE_ACCOUNT="${SNOW_ARTWORK_ACCOUNT}" \
SNOWFLAKE_ADMIN_USER="${SNOW_ARTWORK_ADMIN_USER}" \
SNOWFLAKE_ROLE="${SNOW_ARTWORK_ADMIN_ROLE}" \
SNOWFLAKE_WAREHOUSE="${SNOW_ARTWORK_INIT_WAREHOUSE}" \
    run_toolkit_phase "${PHASE}"

cat <<EOF_DONE

Admin profile '${SNOW_ARTWORK_PROFILE}' is ready if the verification above passed.
Next project step:
  bash scripts/snowflake_bootstrap_project.sh --profile ${SNOW_ARTWORK_PROFILE}
EOF_DONE
