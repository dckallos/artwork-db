#!/bin/bash
# Check for non-ASCII characters in staged files

set -euo pipefail

echo "==> Checking for non-ASCII characters..."

FAILED=0
for file in "$@"; do
    if [[ -f "$file" ]]; then
        # Check for non-ASCII bytes
        if LC_ALL=C grep -q '[^[:print:][:space:]]' "$file"; then
            echo "ERROR: Non-ASCII characters found in $file"
            # Show the offending lines
            LC_ALL=C grep -n '[^[:print:][:space:]]' "$file" | head -5
            FAILED=1
        fi
        
        # Check for smart quotes and dashes
        if grep -qE '[""''—–]' "$file"; then
            echo "ERROR: Smart quotes or em-dashes found in $file"
            grep -nE '[""''—–]' "$file" | head -5
            FAILED=1
        fi
    fi
done

if [[ $FAILED -eq 1 ]]; then
    echo ""
    echo "Fix: Replace smart quotes with straight quotes, em-dashes with --"
    exit 1
fi

echo "ASCII check passed"