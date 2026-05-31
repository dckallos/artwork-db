#!/usr/bin/env bash
# ============================================================
# orchestrate.sh -- IaC execution orchestrator (bash entry point).
#
# Replaces scripts/bootstrap.py as the IaC entry point (H4, 2026-05-29;
# operator chose "bash driver + thin Python preflight"). Reads
# scripts/manifest.txt as the ordered apply list, classifies each entry's
# phase by directory, derives paired drops by swapping create_ -> drop_,
# and shells out to apply_sql.sh (forward) / rollback_sql.sh (paired drop)
# one file at a time. The snow CLI is the only thing that talks to Snowflake;
# it reads connection details from ~/.snowflake/config.toml.
#
# The privilege preflight stays in Python: this driver invokes
# scripts/bootstrap.py (now a thin preflight) for the static contract check
# (verify-contract) and the post-create_roles account-grant assertion
# (assert-account-privileges). JSON parsing + set logic are exactly what
# bash handles poorly, so they stay in a tiny no-dependency Python helper.
#
# Phases (ordering per the 2026-05-29 "Git mirror runs last" decision):
#   bootstrap   Apply the git-setup create scripts in manifest order. OPTIONAL
#               in-Snowflake Git-mirror layer; presumes infra roles exist.
#   infra       Apply the infrastructure create scripts in manifest order.
#   all         infra FIRST, then the git-setup Git mirror LAST.
#   down        Apply paired drop scripts in REVERSE manifest order
#               (combine with --from <filename> to start from a given script).
#
# Per-script rollback (no phase):
#   --down --file create_stages.sql   Apply the paired drop for that script.
#
# Connection selection:
#   --connection NAME   snow CLI connection (default "admin"); all migrations
#                       run as ACCOUNTADMIN via "admin".
#
# .env is sourced (set -a) so child processes (apply_sql.sh / rollback_sql.sh
# and the snow CLI) inherit any SNOWFLAKE_* / GITHUB_PAT vars, mirroring the
# old bootstrap.py dotenv behavior. Credentials otherwise live in
# ~/.snowflake/config.toml or are pulled from env by the snow CLI directly.
#
# Forward/rollback symmetry, the manifest as the single ordered source, the
# create_ -> drop_ pairing, and filename/path-based single-script rollback are
# all preserved verbatim from the previous Python orchestrator.
#
# 'make' runs scripts/bootstrap_chmod.sh first (the canonical chmod policy),
# so apply_sql.sh / rollback_sql.sh are mode 0755 before this driver execs
# them. Run via 'bash scripts/orchestrate.sh ...' if invoking outside make.
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

INFRA_DIR="${REPO_ROOT}/infrastructure"
GIT_SETUP_DIR="${REPO_ROOT}/git-setup"
APPLY_SH="${SCRIPT_DIR}/apply_sql.sh"
ROLLBACK_SH="${SCRIPT_DIR}/rollback_sql.sh"
MANIFEST="${SCRIPT_DIR}/manifest.txt"
SECRET_BEARING_LIST="${SCRIPT_DIR}/secret_bearing.txt"
PREFLIGHT_PY="${SCRIPT_DIR}/bootstrap.py"
PAT_TEMPLATE_MARKER='<% github_pat %>'

DEFAULT_CONNECTION="admin"
CONN="${DEFAULT_CONNECTION}"
PHASE=""
FROM_FILE=""
DOWN_ONE=0
FILE_NAME=""

MANIFEST_ENTRIES=()
SECRET_DECLARED=()
SECRET_FLAG=0
FOUND_CREATE=""

usage() {
    cat <<'EOF'
usage: orchestrate.sh --phase {bootstrap|infra|all|down} [--from FILE] [--connection NAME]
       orchestrate.sh --down --file FILE [--connection NAME]

  --phase all        infra (create_*) first, then git-setup last
  --phase infra      infrastructure create scripts only
  --phase bootstrap  git-setup create scripts only
  --phase down       teardown: paired drops in reverse manifest order
       --from FILE   start teardown at FILE's paired drop (filename or path)
  --down --file FILE roll back ONE script via its paired drop (filename/path)
  --connection NAME  snow CLI connection (default "admin")
EOF
    exit 64
}

# ------------------------------------------------------------
# load_env -- source .env so children inherit SNOWFLAKE_* / GITHUB_PAT.
# Mirrors the old bootstrap.py dotenv_values behavior. A missing .env is
# tolerated (the snow CLI may resolve everything from config.toml).
# ------------------------------------------------------------
load_env() {
    local env_file="${REPO_ROOT}/.env"
    if [[ -f "${env_file}" ]]; then
        set -a
        # shellcheck disable=SC1090
        source "${env_file}"
        set +a
    fi
}

# ------------------------------------------------------------
# load_manifest_entries -- populate MANIFEST_ENTRIES from manifest.txt.
# One repo-relative path per line; blank lines and #-comments ignored.
# Fail fast on a missing/empty manifest, a listed path absent on disk, or an
# entry outside infrastructure/ or git-setup/. This file -- not a glob -- is
# the single source of truth for forward order AND teardown reversal.
# ------------------------------------------------------------
load_manifest_entries() {
    MANIFEST_ENTRIES=()
    [[ -f "${MANIFEST}" ]] || { echo "error: cannot read ordering manifest ${MANIFEST}" >&2; exit 1; }
    local line entry dir
    while IFS= read -r line || [[ -n "${line}" ]]; do
        entry="${line%%#*}"
        entry="${entry#"${entry%%[![:space:]]*}"}"
        entry="${entry%"${entry##*[![:space:]]}"}"
        [[ -z "${entry}" ]] && continue
        [[ -f "${REPO_ROOT}/${entry}" ]] || {
            echo "error: manifest.txt lists ${entry} but no such file exists on disk" >&2
            exit 1
        }
        dir="$(dirname "${entry}")"
        if [[ "${dir}" != "infrastructure" && "${dir}" != "git-setup" ]]; then
            echo "error: manifest entry ${entry} is not under infrastructure/ or git-setup/" >&2
            exit 1
        fi
        MANIFEST_ENTRIES+=("${entry}")
    done < "${MANIFEST}"
    [[ ${#MANIFEST_ENTRIES[@]} -gt 0 ]] || { echo "error: ordering manifest ${MANIFEST} has no entries" >&2; exit 1; }
}

# ------------------------------------------------------------
# phase_of -- echo 'infra' or 'bootstrap' for a manifest entry, by directory.
# Directories are validated in load_manifest_entries, so this is total
# here -- no error branch is needed.
phase_of() {
    case "$(dirname "$1")" in
        infrastructure) printf 'infra' ;;
        git-setup)      printf 'bootstrap' ;;
    esac
}

# ------------------------------------------------------------
# load_secret_declared -- populate SECRET_DECLARED from secret_bearing.txt.
# One repo-relative path per line; blank lines and #-comments ignored. A
# missing file yields the empty set (the fail-closed sniff is the backstop).
# ------------------------------------------------------------
load_secret_declared() {
    SECRET_DECLARED=()
    [[ -f "${SECRET_BEARING_LIST}" ]] || return 0
    local line entry
    while IFS= read -r line || [[ -n "${line}" ]]; do
        entry="${line%%#*}"
        entry="${entry#"${entry%%[![:space:]]*}"}"
        entry="${entry%"${entry##*[![:space:]]}"}"
        [[ -z "${entry}" ]] && continue
        SECRET_DECLARED+=("${entry}")
    done < "${SECRET_BEARING_LIST}"
}

# ------------------------------------------------------------
# compute_secret_bearing -- set SECRET_FLAG=1 if $1 (repo-relative path) must
# be applied with stdout suppressed. Explicit declaration, not sniffing: a
# file is secret-bearing iff listed in secret_bearing.txt. Fail-closed: an
# UNdeclared file that nonetheless renders the github_pat marker aborts the
# run rather than risk a cleartext echo. Called in the main shell so the
# abort actually terminates the orchestrator.
# ------------------------------------------------------------
compute_secret_bearing() {
    local rel="$1" declared
    SECRET_FLAG=0
    for declared in "${SECRET_DECLARED[@]:-}"; do
        if [[ "${declared}" == "${rel}" ]]; then
            SECRET_FLAG=1
            return 0
        fi
    done
    if grep -qF "${PAT_TEMPLATE_MARKER}" "${REPO_ROOT}/${rel}" 2>/dev/null; then
        echo "error: refusing to apply ${rel}: it renders the github_pat template but is" >&2
        echo "       not listed in scripts/secret_bearing.txt. Add it there so its stdout" >&2
        echo "       is suppressed, then re-run." >&2
        exit 1
    fi
}

# ------------------------------------------------------------
# paired_drop -- echo the drop-script path paired with a create-script path,
# swapping the first create_ in the basename to drop_ (H2 pairing rule).
# ------------------------------------------------------------
paired_drop() {
    local entry="$1" dir base
    dir="$(dirname "${entry}")"
    base="$(basename "${entry}")"
    printf '%s/%s' "${dir}" "${base/create_/drop_}"
}

# ------------------------------------------------------------
# find_create_script -- resolve a create script by full filename or path,
# setting FOUND_CREATE to its repo-relative path. Matches on basename only;
# searches infrastructure/ then git-setup/. Aborts if none is found. Called
# in the main shell so the abort terminates the orchestrator.
# ------------------------------------------------------------
find_create_script() {
    local base; base="$(basename "$1")"
    if [[ -f "${INFRA_DIR}/${base}" ]]; then
        FOUND_CREATE="infrastructure/${base}"
        return 0
    fi
    if [[ -f "${GIT_SETUP_DIR}/${base}" ]]; then
        FOUND_CREATE="git-setup/${base}"
        return 0
    fi
    echo "error: no create script found for '$1'" >&2
    exit 1
}

# ------------------------------------------------------------
# run_apply -- invoke apply_sql.sh on one forward .sql ($1 repo-relative).
# When $2 == 1, export SNOW_SUPPRESS_STDOUT=1 so apply_sql.sh discards the
# CLI's per-statement echo and a rendered secret never leaks. set -e aborts
# on any non-zero wrapper exit.
# ------------------------------------------------------------
run_apply() {
    local entry="$1" suppress="$2"
    echo "==> apply_sql.sh [${CONN}] ${entry}"
    if [[ "${suppress}" == "1" ]]; then
        echo "    (stdout suppressed: secret-bearing script)"
        SNOW_CONNECTION="${CONN}" SNOW_SUPPRESS_STDOUT=1 \
            "${APPLY_SH}" "${REPO_ROOT}/${entry}" "${CONN}"
    else
        SNOW_CONNECTION="${CONN}" \
            "${APPLY_SH}" "${REPO_ROOT}/${entry}" "${CONN}"
    fi
    echo "    OK"
}

# ------------------------------------------------------------
# run_rollback -- invoke rollback_sql.sh on one drop .sql ($1 repo-relative).
# ------------------------------------------------------------
run_rollback() {
    local entry="$1"
    echo "==> rollback_sql.sh [${CONN}] ${entry}  [ROLLBACK]"
    SNOW_CONNECTION="${CONN}" \
        "${ROLLBACK_SH}" "${REPO_ROOT}/${entry}" "${CONN}"
    echo "    OK"
}

# ------------------------------------------------------------
# preflight_contract -- static account-privilege contract check (Python).
# preflight_account  -- runtime SHOW GRANTS preflight (Python), after roles.
# Both delegate to the thin scripts/bootstrap.py preflight so the JSON parse
# and set logic stay in Python (no new dependency).
# ------------------------------------------------------------
preflight_contract() {
    echo "==> privilege contract check (python preflight)"
    python3 "${PREFLIGHT_PY}" verify-contract
}

preflight_account() {
    echo "==> account-privilege preflight (python preflight)"
    python3 "${PREFLIGHT_PY}" assert-account-privileges --connection "${CONN}"
}

# ------------------------------------------------------------
# apply_phase -- apply every forward script for the requested phase, in
# manifest order. Runs the static contract check first; after
# create_roles.sql applies (which creates ARTWORK_ADMIN and its account
# grants) and BEFORE create_warehouses.sql issues the first
# ARTWORK_ADMIN-owned CREATE WAREHOUSE, runs the account-privilege preflight.
# This converts a cryptic 003001 (42501) several scripts deep into one
# immediate error carrying the exact remediation GRANT.
# ------------------------------------------------------------
apply_phase() {
    local phase="$1" entry p
    preflight_contract
    local -a scripts=()
    for entry in "${MANIFEST_ENTRIES[@]}"; do
        if [[ "${phase}" == "all" ]]; then
            scripts+=("${entry}")
        else
            p="$(phase_of "${entry}")"
            [[ "${p}" == "${phase}" ]] && scripts+=("${entry}")
        fi
    done
    if [[ ${#scripts[@]} -eq 0 ]]; then
        echo "WARN: no forward scripts matched phase=${phase}" >&2
        return 0
    fi
    for entry in "${scripts[@]}"; do
        compute_secret_bearing "${entry}"
        run_apply "${entry}" "${SECRET_FLAG}"
        if [[ "$(basename "${entry}")" == "create_roles.sql" ]]; then
            preflight_account
        fi
    done
    echo "==> phase '${phase}' complete (${#scripts[@]} script(s))."
}

# ------------------------------------------------------------
# teardown -- apply paired drops in REVERSE manifest order. Only create_*
# entries are torn down. create_grants.sql (formerly grant_privileges.sql) now
# pairs to drop_grants.sql via the create_ -> drop_ rule; refresh_grants.sql is
# a non-create_ entry with no paired drop and is skipped (its grants cascade
# with the dropped parents). With --from FILE, start at FILE's paired drop and
# continue to the end.
# ------------------------------------------------------------
teardown() {
    local from_file="$1" entry
    local -a creates=()
    for entry in "${MANIFEST_ENTRIES[@]}"; do
        [[ "$(basename "${entry}")" == create_* ]] && creates+=("${entry}")
    done
    if [[ ${#creates[@]} -eq 0 ]]; then
        echo "WARN: no create_* scripts in the manifest to tear down" >&2
        return 0
    fi
    local -a rev=()
    local i
    for (( i=${#creates[@]}-1; i>=0; i-- )); do
        rev+=("${creates[i]}")
    done
    if [[ -n "${from_file}" ]]; then
        local target start=-1 idx=0
        target="$(basename "${from_file}")"
        for entry in "${rev[@]}"; do
            if [[ "$(basename "${entry}")" == "${target}" ]]; then
                start=${idx}
                break
            fi
            idx=$((idx + 1))
        done
        [[ ${start} -ge 0 ]] || { echo "error: --from '${from_file}': no matching create script in the manifest" >&2; exit 1; }
        rev=("${rev[@]:${start}}")
    fi
    local applied=0 drop
    for entry in "${rev[@]}"; do
        drop="$(paired_drop "${entry}")"
        if [[ ! -f "${REPO_ROOT}/${drop}" ]]; then
            echo "WARN: skipping ${entry}: no paired drop script" >&2
            continue
        fi
        run_rollback "${drop}"
        applied=$((applied + 1))
    done
    echo "==> teardown complete (${applied} script(s))."
}

# ------------------------------------------------------------
# rollback_one -- apply the paired drop for a single create script, located
# by full filename or path.
# ------------------------------------------------------------
rollback_one() {
    local name="$1" drop
    find_create_script "${name}"
    drop="$(paired_drop "${FOUND_CREATE}")"
    [[ -f "${REPO_ROOT}/${drop}" ]] || { echo "error: no paired drop script for $(basename "${FOUND_CREATE}")" >&2; exit 1; }
    run_rollback "${drop}"
}

# ------------------------------------------------------------
# Argument parsing.
# ------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --phase)      PHASE="${2:-}"; shift 2 ;;
        --from)       FROM_FILE="${2:-}"; shift 2 ;;
        --down)       DOWN_ONE=1; shift ;;
        --file)       FILE_NAME="${2:-}"; shift 2 ;;
        --connection) CONN="${2:-}"; shift 2 ;;
        -h|--help|help) usage ;;
        *) echo "error: unknown argument '$1'" >&2; usage ;;
    esac
done

load_env
load_secret_declared

if [[ ${DOWN_ONE} -eq 1 && -n "${FILE_NAME}" ]]; then
    rollback_one "${FILE_NAME}"
elif [[ "${PHASE}" == "down" ]]; then
    load_manifest_entries
    teardown "${FROM_FILE}"
elif [[ "${PHASE}" == "bootstrap" || "${PHASE}" == "infra" || "${PHASE}" == "all" ]]; then
    load_manifest_entries
    apply_phase "${PHASE}"
else
    echo "error: specify --phase {bootstrap|infra|all|down} or --down --file <FILENAME>." >&2
    usage
fi
