#!/usr/bin/env bash
# Idempotently mark local helper scripts executable.
set -euo pipefail

chmod +x scripts/setup/*.sh scripts/snowflake_account_defaults.sh
if compgen -G 'tools/github/wrappers/*.sh' >/dev/null; then
  chmod +x tools/github/wrappers/*.sh
fi

echo "helper script permissions refreshed"
