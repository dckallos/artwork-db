#!/usr/bin/env bash
#
# protect.sh -- thin wrapper for `ghclient branch-protection apply`.
#
# No arg memorization: dry-run by default (previews the exact PUT body and
# changes nothing). Pass --apply to mutate GitHub. Any extra args are forwarded
# to the CLI (e.g. --branch main, --config path).
#
# Usage:
#   tools/github/wrappers/protect.sh              # dry-run preview
#   tools/github/wrappers/protect.sh --apply      # apply to all configured branches
#   tools/github/wrappers/protect.sh --branch main --apply
set -euo pipefail
exec ghclient branch-protection apply "$@"
