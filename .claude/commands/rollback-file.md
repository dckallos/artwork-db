---
name: rollback-file
description: Rollback a specific infrastructure file using its paired drop script
---

# /rollback-file

Safely rollback a specific DDL file.

## What it does

1. Validates the file exists
2. Shows what will be rolled back
3. Confirms the paired drop script exists
4. Executes the rollback
5. Updates manifest if needed

## Usage

```
/rollback-file infrastructure/create_stages.sql
/rollback-file create_bronze_tables.sql  # Searches for file
```

## Implementation

```bash
#!/bin/bash
set -euo pipefail

FILE="${1:-}"
if [[ -z "$FILE" ]]; then
    echo "ERROR: Specify a file to rollback"
    echo "Usage: /rollback-file infrastructure/create_stages.sql"
    exit 1
fi

# Find the file if only basename given
if [[ ! "$FILE" =~ ^(infrastructure|git-setup)/ ]]; then
    FOUND=$(find infrastructure git-setup -name "$FILE" -type f | head -1)
    if [[ -n "$FOUND" ]]; then
        FILE="$FOUND"
    else
        echo "ERROR: Cannot find file: $FILE"
        exit 1
    fi
fi

# Verify create script exists
if [[ ! -f "$FILE" ]]; then
    echo "ERROR: File not found: $FILE"
    exit 1
fi

# Compute paired drop
DROP_FILE="${FILE/create_/drop_}"
if [[ ! -f "$DROP_FILE" ]]; then
    echo "ERROR: No paired drop script for: $FILE"
    echo "Expected: $DROP_FILE"
    exit 1
fi

echo "==> Will rollback: $FILE"
echo "    Using drop script: $DROP_FILE"
echo ""
echo "==> Drop script contents:"
head -20 "$DROP_FILE"
echo ""
read -p "Proceed with rollback? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Rollback cancelled"
    exit 0
fi

make rollback FILE="$FILE"
```