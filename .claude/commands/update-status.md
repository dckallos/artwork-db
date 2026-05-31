---
name: update-status
description: Update the Status table in AGENTS.md with current state
---

# /update-status

Update the Status table in AGENTS.md based on current work.

## What it does

1. Shows current Status table from AGENTS.md
2. Prompts for updates to specific domains
3. Updates the table maintaining format
4. Commits the change with appropriate message

## Usage

```
/update-status                          # Interactive update
/update-status "extraction" "Complete"  # Update specific domain
```

## Implementation

```python
#!/usr/bin/env python3
import re
import sys
from pathlib import Path

AGENTS_FILE = Path("AGENTS.md")

def read_agents():
    return AGENTS_FILE.read_text()

def extract_status_table(content):
    # Find the Status section
    match = re.search(r'## Status\s*\n\s*\n(\|[^\n]+\|\s*\n\|[-\s|]+\|\s*\n(?:\|[^\n]+\|\s*\n)*)', content, re.MULTILINE)
    if not match:
        raise ValueError("Cannot find Status table in AGENTS.md")
    return match.group(1), match.start(1), match.end(1)

def parse_status_table(table_text):
    lines = table_text.strip().split('\n')
    # Skip header and separator
    status_lines = lines[2:]
    
    status_dict = {}
    for line in status_lines:
        if line.strip():
            parts = line.split('|')
            if len(parts) >= 3:
                domain = parts[1].strip().strip('`')
                state = parts[2].strip()
                status_dict[domain] = state
    return status_dict

def rebuild_status_table(status_dict):
    lines = ["| Domain doc | State |", "|---|---|"]
    for domain, state in status_dict.items():
        lines.append(f"| `{domain}` | {state} |")
    return '\n'.join(lines)

def main():
    if len(sys.argv) == 3:
        # Direct update mode
        domain_to_update = sys.argv[1]
        new_state = sys.argv[2]
        
        content = read_agents()
        table_text, start_pos, end_pos = extract_status_table(content)
        status_dict = parse_status_table(table_text)
        
        # Update the specific domain
        found = False
        for domain in status_dict:
            if domain_to_update in domain:
                status_dict[domain] = new_state
                found = True
                print(f"Updated {domain} to: {new_state}")
                break
        
        if not found:
            print(f"ERROR: Domain '{domain_to_update}' not found in Status table")
            sys.exit(1)
            
        # Rebuild content
        new_table = rebuild_status_table(status_dict)
        new_content = content[:start_pos] + new_table + content[end_pos:]
        
        # Write back
        AGENTS_FILE.write_text(new_content)
        print("Status table updated successfully")
        
    else:
        # Interactive mode
        content = read_agents()
        table_text, _, _ = extract_status_table(content)
        
        print("Current Status table:")
        print(table_text)
        print("\nUse: /update-status <domain> <new_state>")
        print("Example: /update-status extraction 'Complete (read 2026-05-31)'")

if __name__ == "__main__":
    main()
```