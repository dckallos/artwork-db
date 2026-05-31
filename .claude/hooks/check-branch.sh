#!/bin/bash
# Show current branch context on file reads

set -euo pipefail

CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")

if [[ "$CURRENT_BRANCH" != "donkey-kong-sandbox" ]] && [[ "$CURRENT_BRANCH" != "unknown" ]]; then
    echo "NOTE: Currently on branch '$CURRENT_BRANCH' (active design branch is 'donkey-kong-sandbox')"
fi