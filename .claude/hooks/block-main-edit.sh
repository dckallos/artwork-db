#!/bin/bash
# Prevent edits on main branch

set -euo pipefail

CURRENT_BRANCH=$(git branch --show-current)

if [[ "$CURRENT_BRANCH" == "main" ]]; then
    echo "ERROR: Cannot edit files on main branch"
    echo "Current branch: main"
    echo ""
    echo "Switch to a feature branch:"
    echo "  git checkout donkey-kong-sandbox"
    echo "  git checkout -b new-feature-branch"
    exit 1
fi

echo "Branch check passed (current: $CURRENT_BRANCH)"