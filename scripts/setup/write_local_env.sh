#!/usr/bin/env bash
# Generate a complete local .env from the checked-in template.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TARGET="${REPO_ROOT}/.env"
APPLY=0
FORCE=0

usage() {
  cat <<'EOF_USAGE'
usage: bash scripts/setup/write_local_env.sh [--target FILE] [--apply] [--force]

Dry-run by default. With --apply, writes a full local env file from .env.example.
If the target exists, it is backed up first; --force is required to overwrite it.
EOF_USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET="${2:-}"; shift 2 ;;
    --apply) APPLY=1; shift ;;
    --force) FORCE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "error: unknown option '$1'" >&2; usage; exit 64 ;;
  esac
done

TEMPLATE="${REPO_ROOT}/.env.example"
if [[ ! -f "${TEMPLATE}" ]]; then
  echo "error: template missing: ${TEMPLATE}" >&2
  exit 66
fi

if (( APPLY == 0 )); then
  cat <<EOF_DRY
DRY-RUN: would write ${TARGET} from ${TEMPLATE}
Nothing changed. Re-run with:
  bash scripts/setup/write_local_env.sh --target ${TARGET} --apply --force
EOF_DRY
  exit 0
fi

if [[ -e "${TARGET}" && "${FORCE}" != "1" ]]; then
  cat >&2 <<EOF_EXISTS
error: ${TARGET} already exists.
Review it, then re-run with --force to back it up and replace it:
  bash scripts/setup/write_local_env.sh --target ${TARGET} --apply --force
EOF_EXISTS
  exit 73
fi

if [[ -e "${TARGET}" ]]; then
  backup="${TARGET}.bak.$(date -u +%Y%m%dT%H%M%SZ)"
  cp -p "${TARGET}" "${backup}"
  echo "backed up ${TARGET} -> ${backup}"
fi

install -m 600 "${TEMPLATE}" "${TARGET}"
echo "wrote ${TARGET} (mode 600)"
echo "Edit SMITHSONIAN_API_KEY and GitHub git-setup values before using those integrations."
