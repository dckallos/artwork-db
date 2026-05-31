#!/bin/bash
# Validate manifest.txt after SQL file changes

set -euo pipefail

# Only run if SQL files were modified
SQL_MODIFIED=0
for file in "$@"; do
    if [[ "$file" == *.sql ]] && [[ "$file" =~ ^(infrastructure|git-setup)/ ]]; then
        SQL_MODIFIED=1
        break
    fi
done

if [[ $SQL_MODIFIED -eq 0 ]]; then
    exit 0
fi

echo "==> Validating manifest.txt..."

MANIFEST="scripts/manifest.txt"
FAILED=0

# Check all infrastructure/git-setup create_*.sql files are in manifest
for create_file in infrastructure/create_*.sql git-setup/create_*.sql; do
    if [[ -f "$create_file" ]]; then
        if ! grep -qF "$create_file" "$MANIFEST"; then
            echo "ERROR: $create_file not found in manifest.txt"
            FAILED=1
        fi
    fi
done

# Check manifest entries exist on disk
while IFS= read -r line; do
    # Skip comments and empty lines
    entry="${line%%#*}"
    entry="${entry#"${entry%%[![:space:]]*}"}"
    entry="${entry%"${entry##*[![:space:]]}"}"
    
    if [[ -n "$entry" ]]; then
        if [[ ! -f "$entry" ]]; then
            echo "ERROR: Manifest entry not found on disk: $entry"
            FAILED=1
        fi
    fi
done < "$MANIFEST"

if [[ $FAILED -eq 1 ]]; then
    echo ""
    echo "Fix: Update scripts/manifest.txt to match filesystem"
    exit 1
fi

echo "Manifest validation passed"