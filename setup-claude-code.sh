#!/bin/bash
# Setup script for Claude Code optimization kit

set -euo pipefail

echo "==> Setting up Claude Code optimization kit for artwork-db..."

# Make all hook scripts executable
echo "==> Setting hook script permissions..."
chmod +x .claude/hooks/*.sh

# Verify directory structure
echo "==> Verifying structure..."
for dir in .claude .claude/commands .claude/agents .claude/hooks; do
    if [[ -d "$dir" ]]; then
        echo "  ✓ $dir"
    else
        echo "  ✗ $dir missing"
        exit 1
    fi
done

# Check file counts
echo -e "\n==> File inventory:"
echo "  Commands: $(ls -1 .claude/commands/*.md 2>/dev/null | wc -l) files"
echo "  Agents:   $(ls -1 .claude/agents/*.md 2>/dev/null | wc -l) files"
echo "  Hooks:    $(ls -1 .claude/hooks/*.sh 2>/dev/null | wc -l) scripts"

# Validate JSON files
echo -e "\n==> Validating JSON configurations..."
for json in .claude/settings.json .claude/hooks/config.json .mcp.json; do
    if python -m json.tool "$json" > /dev/null 2>&1; then
        echo "  ✓ $json valid"
    else
        echo "  ✗ $json invalid"
        exit 1
    fi
done

# Check for required files
echo -e "\n==> Checking required files..."
REQUIRED_FILES=(
    "CLAUDE.md"
    "infrastructure/CLAUDE.md"
    "extraction/met/CLAUDE.md"
    ".claude/settings.json"
    ".mcp.json"
    "docs/context/claude-code-playbook.md"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [[ -f "$file" ]]; then
        echo "  ✓ $file"
    else
        echo "  ✗ $file missing"
        exit 1
    fi
done

# Git setup
echo -e "\n==> Git configuration..."
# Add .claude to gitignore if not already there
if ! grep -q "^\.claude/settings\.local\.json" .gitignore 2>/dev/null; then
    echo ".claude/settings.local.json" >> .gitignore
    echo "  Added .claude/settings.local.json to .gitignore"
fi

# Summary
echo -e "\n==> Setup complete!"
echo ""
echo "Next steps:"
echo "1. Create GitHub PAT and add to .env: GITHUB_PAT=your_token"
echo "2. Run 'claude' in this directory to test"
echo "3. Try: /apply-iac --check"
echo "4. Review docs/context/claude-code-playbook.md"
echo ""
echo "Optional:"
echo "- Create .claude/settings.local.json for personal overrides"
echo "- Install MCP servers when available"

# Cleanup
rm -f setup-claude-code.sh