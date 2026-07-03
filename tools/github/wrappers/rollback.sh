#!/usr/bin/env bash
#
# rollback.sh -- thin wrapper for `ghclient branch-protection rollback`.
#
# Restores each branch from its last snapshot in policies/exports/. Dry-run by
# default (previews the DELETE/PUT plan and changes nothing); pass --apply to
# mutate GitHub. Extra args are forwarded (e.g. --branch main).
#
# Usage:
#   tools/github/wrappers/rollback.sh             # dry-run preview
#   tools/github/wrappers/rollback.sh --apply     # roll back all configured branches
set -euo pipefail
exec ghclient branch-protection rollback "$@"
