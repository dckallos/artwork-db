---
name: reconcile-files
description: Reconcile file-map.md against actual filesystem
---

# /reconcile-files

Check file-map.md accuracy against the actual repository structure.

## What it does

1. Lists all files in the repo
2. Checks which are documented in file-map.md
3. Identifies undocumented files
4. Identifies documented files that don't exist
5. Optionally updates file-map.md

## Usage

```
/reconcile-files         # Check only
/reconcile-files --fix   # Update file-map.md with findings
```

## Implementation

```bash
#!/bin/bash
set -euo pipefail

MODE="${1:---check}"
FILEMAP="docs/context/file-map.md"

echo "==> Scanning repository files..."

# Get all substantive files (exclude common ignores)
ACTUAL_FILES=$(find . -type f \
    -not -path "./.git/*" \
    -not -path "./.claude/*" \
    -not -path "*/target/*" \
    -not -path "*/__pycache__/*" \
    -not -path "*/venv/*" \
    -not -path "*/.venv/*" \
    -not -name ".DS_Store" \
    -not -name "*.pyc" \
    -not -name ".gitignore" \
    -not -name "LICENSE" \
    | sed 's|^\./||' | sort)

echo "==> Checking against file-map.md..."

# Extract documented files from file-map.md
DOCUMENTED_FILES=$(grep -E '^\| `[^`]+` \|' "$FILEMAP" | sed 's/^| `\([^`]*\)`.*/\1/' | sort | uniq)

# Find undocumented files
echo -e "\n==> Files NOT in file-map.md:"
comm -23 <(echo "$ACTUAL_FILES") <(echo "$DOCUMENTED_FILES") | while read f; do
    if [[ -n "$f" ]]; then
        echo "  - $f"
    fi
done

# Find documented but missing files
echo -e "\n==> Files in file-map.md but NOT on disk:"
comm -13 <(echo "$ACTUAL_FILES") <(echo "$DOCUMENTED_FILES") | while read f; do
    if [[ -n "$f" ]]; then
        echo "  - $f (MISSING)"
    fi
done

# Count files by directory
echo -e "\n==> File counts by directory:"
for dir in infrastructure scripts extraction/met git-setup; do
    if [[ -d "$dir" ]]; then
        COUNT=$(find "$dir" -type f -name "*.sql" -o -name "*.py" -o -name "*.sh" | wc -l)
        echo "  $dir: $COUNT files"
    fi
done

if [[ "$MODE" == "--fix" ]]; then
    echo -e "\n==> Updating file-map.md..."
    echo "TODO: Implement file-map.md update logic"
    echo "For now, manually add the undocumented files shown above"
fi
```