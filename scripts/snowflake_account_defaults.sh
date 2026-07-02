#!/usr/bin/env bash
# Shared defaults for connecting this checkout to the KUNHTEL Snowflake account.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

: "${SNOW_ARTWORK_PROFILE:=gl13131}"
: "${SNOW_ARTWORK_ACCOUNT:=KUNHTEL-GL13131}"
: "${SNOW_ARTWORK_ADMIN_USER:=RSKALLOS}"
: "${SNOW_ARTWORK_ADMIN_ROLE:=ACCOUNTADMIN}"
: "${SNOW_ARTWORK_INIT_WAREHOUSE:=COMPUTE_WH}"
: "${SNOW_ARTWORK_PROJECT_WAREHOUSE:=ARTWORK_WH}"
: "${SNOW_ARTWORK_DATABASE:=ARTWORK_DB}"
: "${SNOW_ARTWORK_LOADER_USER:=ARTWORK_LOADER_SVC}"
: "${SNOW_ARTWORK_LOADER_ROLE:=ARTWORK_LOADER}"
: "${SNOW_ARTWORK_TRANSFORMER_USER:=ARTWORK_TRANSFORMER_SVC}"
: "${SNOW_ARTWORK_TRANSFORMER_ROLE:=ARTWORK_TRANSFORMER}"
: "${TOOLKIT_DIR:=${REPO_ROOT}/../snowflake-toolkit}"

COMMON_USAGE=$(cat <<'EOF_USAGE'
Common options:
  --profile NAME          Snowflake CLI connection label. Default: gl13131
  --account IDENTIFIER    Snowflake account identifier. Default: KUNHTEL-GL13131
  --admin-user USER       Human admin login. Default: RSKALLOS
  --admin-role ROLE       Human admin role. Default: ACCOUNTADMIN
  --init-warehouse NAME   Existing bootstrap warehouse. Default: COMPUTE_WH
  --warehouse NAME        Project warehouse after IaC. Default: ARTWORK_WH
  --database NAME         Project database after IaC. Default: ARTWORK_DB
  --loader-user USER      Loader service user. Default: ARTWORK_LOADER_SVC
  --loader-role ROLE      Loader service role. Default: ARTWORK_LOADER
  --transformer-user USER Transformer service user. Default: ARTWORK_TRANSFORMER_SVC
  --transformer-role ROLE Transformer service role. Default: ARTWORK_TRANSFORMER
  --toolkit-dir PATH      snowflake-toolkit clone. Default: ../snowflake-toolkit
  --dry-run               Print actions without calling snowflake-toolkit or snow
EOF_USAGE
)

parse_common_account_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --profile) SNOW_ARTWORK_PROFILE="${2:-}"; shift 2 ;;
            --account) SNOW_ARTWORK_ACCOUNT="${2:-}"; shift 2 ;;
            --admin-user) SNOW_ARTWORK_ADMIN_USER="${2:-}"; shift 2 ;;
            --admin-role|--role) SNOW_ARTWORK_ADMIN_ROLE="${2:-}"; shift 2 ;;
            --init-warehouse) SNOW_ARTWORK_INIT_WAREHOUSE="${2:-}"; shift 2 ;;
            --warehouse) SNOW_ARTWORK_PROJECT_WAREHOUSE="${2:-}"; shift 2 ;;
            --database) SNOW_ARTWORK_DATABASE="${2:-}"; shift 2 ;;
            --loader-user) SNOW_ARTWORK_LOADER_USER="${2:-}"; shift 2 ;;
            --loader-role) SNOW_ARTWORK_LOADER_ROLE="${2:-}"; shift 2 ;;
            --transformer-user) SNOW_ARTWORK_TRANSFORMER_USER="${2:-}"; shift 2 ;;
            --transformer-role) SNOW_ARTWORK_TRANSFORMER_ROLE="${2:-}"; shift 2 ;;
            --toolkit-dir) TOOLKIT_DIR="${2:-}"; shift 2 ;;
            --dry-run) DRY_RUN=1; shift ;;
            *) echo "error: unknown option '$1'" >&2; return 64 ;;
        esac
    done
}

require_non_empty_defaults() {
    local missing=0
    for name in SNOW_ARTWORK_PROFILE SNOW_ARTWORK_ACCOUNT SNOW_ARTWORK_ADMIN_USER \
        SNOW_ARTWORK_ADMIN_ROLE SNOW_ARTWORK_INIT_WAREHOUSE \
        SNOW_ARTWORK_PROJECT_WAREHOUSE SNOW_ARTWORK_DATABASE \
        SNOW_ARTWORK_LOADER_USER SNOW_ARTWORK_LOADER_ROLE \
        SNOW_ARTWORK_TRANSFORMER_USER SNOW_ARTWORK_TRANSFORMER_ROLE TOOLKIT_DIR
    do
        if [[ -z "${!name:-}" ]]; then
            echo "error: ${name} is empty" >&2
            missing=1
        fi
    done
    [[ "${missing}" -eq 0 ]] || exit 64
}

require_toolkit() {
    require_non_empty_defaults
    if [[ ! -f "${TOOLKIT_DIR}/snowflake_cli/setup.sh" ]]; then
        cat >&2 <<EOF_MISSING
error: snowflake-toolkit setup.sh not found:
  ${TOOLKIT_DIR}/snowflake_cli/setup.sh

Clone it as a sibling repo or pass --toolkit-dir:
  git clone git@github.com-dckallos:dckallos/snowflake-toolkit.git "${REPO_ROOT}/../snowflake-toolkit"
EOF_MISSING
        exit 78
    fi
}

connection_account_from_toml() {
    local profile="$1"
    local toml="${HOME}/.snowflake/connections.toml"
    [[ -f "${toml}" ]] || return 0
    awk -v section="${profile}" '
        $0 ~ "^\\[" section "\\]$" { in_section = 1; next }
        $0 ~ "^\\[" && in_section { exit }
        in_section && $1 == "account" {
            sub(/^[^=]*=[[:space:]]*/, "", $0)
            gsub(/^[\"'\'' ]+|[\"'\'' ]+$/, "", $0)
            print $0
            exit
        }
    ' "${toml}"
}

ensure_profile_not_pointing_elsewhere() {
    local existing_account
    existing_account="$(connection_account_from_toml "${SNOW_ARTWORK_PROFILE}")"
    if [[ -n "${existing_account}" && "${existing_account}" != "${SNOW_ARTWORK_ACCOUNT}" ]]; then
        cat >&2 <<EOF_PROFILE
error: profile '${SNOW_ARTWORK_PROFILE}' already points at '${existing_account}', not '${SNOW_ARTWORK_ACCOUNT}'.

Use a different --profile value or edit ~/.snowflake/connections.toml deliberately.
The toolkit init-profile phase is intentionally non-destructive.
EOF_PROFILE
        exit 78
    fi
}

run_toolkit_phase() {
    local phase="$1"
    shift || true
    case "${phase}" in
        promote)
            env -u SNOWFLAKE_ACCOUNT -u SNOWFLAKE_USER -u SNOWFLAKE_ROLE \
                -u SNOWFLAKE_WAREHOUSE -u SNOWFLAKE_DATABASE \
                -u SNOWFLAKE_PRIVATE_KEY_FILE -u SNOWFLAKE_AUTHENTICATOR \
            TARGET_WAREHOUSE="${SNOW_ARTWORK_PROJECT_WAREHOUSE}" \
            SNOW_LIB_DEFAULT_WAREHOUSE="${SNOW_ARTWORK_PROJECT_WAREHOUSE}" \
                bash "${TOOLKIT_DIR}/snowflake_cli/setup.sh" --profile "${SNOW_ARTWORK_PROFILE}" --phase "${phase}" "$@"
            ;;
        loader)
            env -u SNOWFLAKE_ACCOUNT -u SNOWFLAKE_USER -u SNOWFLAKE_ROLE \
                -u SNOWFLAKE_WAREHOUSE -u SNOWFLAKE_DATABASE \
                -u SNOWFLAKE_PRIVATE_KEY_FILE -u SNOWFLAKE_AUTHENTICATOR \
            LOADER_USER="${SNOW_ARTWORK_LOADER_USER}" \
            LOADER_ROLE="${SNOW_ARTWORK_LOADER_ROLE}" \
            LOADER_WAREHOUSE="${SNOW_ARTWORK_PROJECT_WAREHOUSE}" \
            SNOW_LIB_DEFAULT_WAREHOUSE="${SNOW_ARTWORK_PROJECT_WAREHOUSE}" \
                bash "${TOOLKIT_DIR}/snowflake_cli/setup.sh" --profile "${SNOW_ARTWORK_PROFILE}" --phase "${phase}" "$@"
            ;;
        transformer)
            env -u SNOWFLAKE_ACCOUNT -u SNOWFLAKE_USER -u SNOWFLAKE_ROLE \
                -u SNOWFLAKE_WAREHOUSE -u SNOWFLAKE_DATABASE \
                -u SNOWFLAKE_PRIVATE_KEY_FILE -u SNOWFLAKE_AUTHENTICATOR \
            TRANSFORMER_USER="${SNOW_ARTWORK_TRANSFORMER_USER}" \
            TRANSFORMER_ROLE="${SNOW_ARTWORK_TRANSFORMER_ROLE}" \
            TRANSFORMER_WAREHOUSE="${SNOW_ARTWORK_PROJECT_WAREHOUSE}" \
            SNOW_LIB_DEFAULT_WAREHOUSE="${SNOW_ARTWORK_PROJECT_WAREHOUSE}" \
                bash "${TOOLKIT_DIR}/snowflake_cli/setup.sh" --profile "${SNOW_ARTWORK_PROFILE}" --phase "${phase}" "$@"
            ;;
        *)
            SNOW_LIB_DEFAULT_WAREHOUSE="${SNOW_ARTWORK_PROJECT_WAREHOUSE}" \
                bash "${TOOLKIT_DIR}/snowflake_cli/setup.sh" --profile "${SNOW_ARTWORK_PROFILE}" --phase "${phase}" "$@"
            ;;
    esac
}

print_toolkit_phase() {
    local phase="$1"
    case "${phase}" in
        promote)
            printf 'TARGET_WAREHOUSE=%q SNOW_LIB_DEFAULT_WAREHOUSE=%q bash %q --profile %q --phase %q\n' \
                "${SNOW_ARTWORK_PROJECT_WAREHOUSE}" "${SNOW_ARTWORK_PROJECT_WAREHOUSE}" \
                "${TOOLKIT_DIR}/snowflake_cli/setup.sh" "${SNOW_ARTWORK_PROFILE}" "${phase}"
            ;;
        loader)
            printf 'LOADER_USER=%q LOADER_ROLE=%q LOADER_WAREHOUSE=%q SNOW_LIB_DEFAULT_WAREHOUSE=%q bash %q --profile %q --phase %q\n' \
                "${SNOW_ARTWORK_LOADER_USER}" "${SNOW_ARTWORK_LOADER_ROLE}" "${SNOW_ARTWORK_PROJECT_WAREHOUSE}" \
                "${SNOW_ARTWORK_PROJECT_WAREHOUSE}" "${TOOLKIT_DIR}/snowflake_cli/setup.sh" "${SNOW_ARTWORK_PROFILE}" "${phase}"
            ;;
        transformer)
            printf 'TRANSFORMER_USER=%q TRANSFORMER_ROLE=%q TRANSFORMER_WAREHOUSE=%q SNOW_LIB_DEFAULT_WAREHOUSE=%q bash %q --profile %q --phase %q\n' \
                "${SNOW_ARTWORK_TRANSFORMER_USER}" "${SNOW_ARTWORK_TRANSFORMER_ROLE}" "${SNOW_ARTWORK_PROJECT_WAREHOUSE}" \
                "${SNOW_ARTWORK_PROJECT_WAREHOUSE}" "${TOOLKIT_DIR}/snowflake_cli/setup.sh" "${SNOW_ARTWORK_PROFILE}" "${phase}"
            ;;
        *)
            printf 'SNOW_LIB_DEFAULT_WAREHOUSE=%q bash %q --profile %q --phase %q\n' \
                "${SNOW_ARTWORK_PROJECT_WAREHOUSE}" "${TOOLKIT_DIR}/snowflake_cli/setup.sh" "${SNOW_ARTWORK_PROFILE}" "${phase}"
            ;;
    esac
}

loader_key_path() {
    printf '%s/.snowflake/keys/%s_loader_rsa_key.p8\n' "${HOME}" "${SNOW_ARTWORK_PROFILE}"
}

transformer_key_path() {
    printf '%s/.snowflake/keys/%s_transformer_rsa_key.p8\n' "${HOME}" "${SNOW_ARTWORK_PROFILE}"
}

print_connection_summary() {
    cat <<EOF_SUMMARY
Snowflake target:
  profile          ${SNOW_ARTWORK_PROFILE}
  account          ${SNOW_ARTWORK_ACCOUNT}
  admin user       ${SNOW_ARTWORK_ADMIN_USER}
  admin role       ${SNOW_ARTWORK_ADMIN_ROLE}
  init warehouse   ${SNOW_ARTWORK_INIT_WAREHOUSE}
  project wh/db    ${SNOW_ARTWORK_PROJECT_WAREHOUSE} / ${SNOW_ARTWORK_DATABASE}
  loader           ${SNOW_ARTWORK_LOADER_USER} / ${SNOW_ARTWORK_LOADER_ROLE}
  transformer      ${SNOW_ARTWORK_TRANSFORMER_USER} / ${SNOW_ARTWORK_TRANSFORMER_ROLE}
  toolkit          ${TOOLKIT_DIR}
EOF_SUMMARY
}
