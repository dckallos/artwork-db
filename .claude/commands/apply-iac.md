---
name: apply-iac
description: Apply infrastructure as code with manifest preflight check
---

# /apply-iac

Safely apply infrastructure changes with preflight checks.

## What it does

1. Shows current git status and branch
2. Lists files that will be applied from manifest.txt
3. Runs preflight contract check
4. Executes `make infra` or `make iac` based on your choice
5. Shows post-apply status

## Usage

```
/apply-iac           # Apply infrastructure only
/apply-iac --all     # Apply infrastructure + git-setup
/apply-iac --check   # Dry run - show what would be applied
```

## Implementation

```bash
#!/bin/bash
set -euo pipefail

# Show current state
echo "==> Current branch:"
git branch --show-current

echo -e "\n==> Git status:"
git status --short

echo -e "\n==> Files in manifest that will be applied:"
grep -E '^(infrastructure|git-setup)/' scripts/manifest.txt | grep -v '^#'

# Run preflight
echo -e "\n==> Running preflight check..."
python scripts/bootstrap.py verify-contract

# Apply based on flag
if [[ "${1:-}" == "--check" ]]; then
    echo -e "\n==> DRY RUN - would run: make infra"
elif [[ "${1:-}" == "--all" ]]; then
    echo -e "\n==> Applying ALL (infra + git-setup)..."
    make iac
else
    echo -e "\n==> Applying infrastructure only..."
    make infra
fi

# Show results
echo -e "\n==> Post-apply check:"
scripts/check.sh scripts/sql/show_pipeline_status.sql
```