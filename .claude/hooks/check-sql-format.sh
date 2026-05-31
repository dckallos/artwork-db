#!/bin/bash
# Validate SQL file conventions

set -euo pipefail

echo "==> Checking SQL formatting..."

FAILED=0
for file in "$@"; do
    if [[ "$file" == *.sql ]]; then
        # Check for lowercase Snowflake keywords
        if grep -qE '\b(create|table|database|schema|or replace|if not exists)\b' "$file"; then
            echo "ERROR: Lowercase SQL keywords in $file"
            echo "Fix: Use UPPERCASE for SQL keywords"
            FAILED=1
        fi
        
        # Check create/drop pairing
        if [[ "$file" =~ create_.*\.sql$ ]]; then
            DROP_FILE="${file/create_/drop_}"
            if [[ ! -f "$DROP_FILE" ]]; then
                echo "ERROR: Missing paired drop script for $file"
                echo "Expected: $DROP_FILE"
                FAILED=1
            fi
        fi
        
        # Check for inline SQL in comments
        if grep -qE '(INSERT|UPDATE|DELETE|SELECT).*;.*--' "$file"; then
            echo "WARNING: Possible inline SQL in comments in $file"
        fi
        
        # Check idempotency
        if [[ "$file" =~ create_.*\.sql$ ]]; then
            # Check if it's a table/database/user (should use IF NOT EXISTS)
            if grep -qE 'CREATE (TABLE|DATABASE|SCHEMA|USER|ROLE|WAREHOUSE)' "$file"; then
                if ! grep -qE 'IF NOT EXISTS' "$file"; then
                    echo "ERROR: Stateful object in $file missing IF NOT EXISTS"
                    FAILED=1
                fi
            fi
            # Check if it's a view/task/format (should use OR REPLACE)
            if grep -qE 'CREATE (VIEW|TASK|FILE FORMAT|STAGE)' "$file"; then
                if ! grep -qE 'OR REPLACE' "$file"; then
                    echo "ERROR: Stateless object in $file missing OR REPLACE"
                    FAILED=1
                fi
            fi
        fi
    fi
done

if [[ $FAILED -eq 1 ]]; then
    exit 1
fi

echo "SQL format check passed"