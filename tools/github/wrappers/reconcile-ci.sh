#!/usr/bin/env bash
#
# reconcile-ci.sh -- thin wrapper for `ghclient ci reconcile`.
#
# No arg memorization: dry-run by default (previews the current-vs-desired required
# checks and the exact PATCH, changing nothing). Pass --apply to set the branch's
# required check to the aggregate `ci-required` context. Extra args are forwarded
# (e.g. --branch main).
#
# Usage:
#   tools/github/wrappers/reconcile-ci.sh            # dry-run preview
#   tools/github/wrappers/reconcile-ci.sh --apply    # reconcile all configured branches
#   tools/github/wrappers/reconcile-ci.sh --branch main --apply
set -euo pipefail
exec ghclient ci reconcile "$@"
