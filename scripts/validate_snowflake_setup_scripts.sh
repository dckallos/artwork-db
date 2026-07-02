#!/usr/bin/env bash
# Validate the Snowflake setup wrapper scripts without creating Snowflake profiles.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TOOLKIT_DIR_DEFAULT="${TOOLKIT_DIR:-${REPO_ROOT}/../snowflake-toolkit}"

assert_contains() {
    local file="$1"
    local expected="$2"
    if ! grep -Fq "${expected}" "${file}"; then
        echo "error: expected '${expected}' in ${file}" >&2
        echo "--- ${file} ---" >&2
        cat "${file}" >&2
        exit 1
    fi
}

scripts=(
    scripts/snowflake_account_defaults.sh
    scripts/snowflake_connect_admin.sh
    scripts/snowflake_write_local_env.sh
    scripts/snowflake_bootstrap_project.sh
    scripts/snowflake_verify_connections.sh
    scripts/validate_snowflake_setup_scripts.sh
)

echo "==> bash syntax checks"
for script in "${scripts[@]}"; do
    bash -n "${REPO_ROOT}/${script}"
done

echo "==> bash 3 empty-array compatibility checks"
for script in \
    scripts/snowflake_connect_admin.sh \
    scripts/snowflake_write_local_env.sh \
    scripts/snowflake_bootstrap_project.sh \
    scripts/snowflake_verify_connections.sh
do
    assert_contains "${REPO_ROOT}/${script}" 'if [[ "${#COMMON_ARGS[@]}" -gt 0 ]]; then'
    assert_contains "${REPO_ROOT}/${script}" 'parse_common_account_args "${COMMON_ARGS[@]}"'
    assert_contains "${REPO_ROOT}/${script}" 'parse_common_account_args'
done

echo "==> help paths"
bash "${REPO_ROOT}/scripts/snowflake_connect_admin.sh" --help >/dev/null
bash "${REPO_ROOT}/scripts/snowflake_write_local_env.sh" --help >/dev/null
bash "${REPO_ROOT}/scripts/snowflake_bootstrap_project.sh" --help >/dev/null
bash "${REPO_ROOT}/scripts/snowflake_verify_connections.sh" --help >/dev/null

echo "==> dry-run paths with isolated HOME"
tmp_home="$(mktemp -d)"
trap 'rm -rf "${tmp_home}" "${tmp_env:-}" "${tmp_bootstrap_dry_run:-}"' EXIT
HOME="${tmp_home}" bash "${REPO_ROOT}/scripts/snowflake_connect_admin.sh" --dry-run --toolkit-dir "${TOOLKIT_DIR_DEFAULT}" --phase all >/dev/null
tmp_bootstrap_dry_run="$(mktemp)"
HOME="${tmp_home}" bash "${REPO_ROOT}/scripts/snowflake_bootstrap_project.sh" --dry-run --yes --toolkit-dir "${TOOLKIT_DIR_DEFAULT}" >"${tmp_bootstrap_dry_run}"
assert_contains "${tmp_bootstrap_dry_run}" "LOADER_USER=ARTWORK_LOADER_SVC"
assert_contains "${tmp_bootstrap_dry_run}" "LOADER_ROLE=ARTWORK_LOADER"
assert_contains "${tmp_bootstrap_dry_run}" "TRANSFORMER_USER=ARTWORK_TRANSFORMER_SVC"
assert_contains "${tmp_bootstrap_dry_run}" "TRANSFORMER_ROLE=ARTWORK_TRANSFORMER"
HOME="${tmp_home}" bash "${REPO_ROOT}/scripts/snowflake_verify_connections.sh" --dry-run >/dev/null

echo "==> temp .env generation"
tmp_env="$(mktemp)"
HOME="${tmp_home}" bash "${REPO_ROOT}/scripts/snowflake_write_local_env.sh" --env-file "${tmp_env}" --toolkit-dir "${TOOLKIT_DIR_DEFAULT}" >/dev/null
assert_contains "${tmp_env}" "SNOWFLAKE_ACCOUNT=KUNHTEL-GL13131"
assert_contains "${tmp_env}" "SNOWFLAKE_USER=ARTWORK_LOADER_SVC"
assert_contains "${tmp_env}" "SNOWFLAKE_ROLE=ARTWORK_LOADER"
assert_contains "${tmp_env}" "DBT_SNOWFLAKE_USER=ARTWORK_TRANSFORMER_SVC"
assert_contains "${tmp_env}" "SNOW_CONNECTION=gl13131"
assert_contains "${tmp_env}" "${tmp_home}/.snowflake/keys/gl13131_loader_rsa_key.p8"
assert_contains "${tmp_env}" "${tmp_home}/.snowflake/keys/gl13131_transformer_rsa_key.p8"

echo "==> Makefile parse checks"
make -C "${REPO_ROOT}" -n infra TOOLKIT_DIR="${TOOLKIT_DIR_DEFAULT}" CONN=gl13131 >/dev/null
make -C "${REPO_ROOT}" -n rollback FILE=infrastructure/create_warehouses.sql TOOLKIT_DIR="${TOOLKIT_DIR_DEFAULT}" CONN=gl13131 >/dev/null

echo "OK: Snowflake setup scripts validate without creating profiles."
