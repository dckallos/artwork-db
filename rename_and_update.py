import os
import subprocess
import re

# Update to the new subdirectory
DIRECTORY = "git-setup"

# 1. Configuration Set for Git Renames
FILE_MAPPING = {
    "B001__create_git_ops_db.sql": "create_git_ops_db.sql",
    "B001__drop_git_ops_db.sql": "drop_git_ops_db.sql",
    "B002__create_api_integration.sql": "create_api_integration.sql",
    "B002__drop_api_integration.sql": "drop_api_integration.sql",
    "B003__create_git_repository.sql": "create_git_repository.sql",
    "B003__drop_git_repository.sql": "drop_git_repository.sql",
}

# 2. Configuration Set for Prefixes
# Maps isolated prefixes (e.g., "B001") to the primary forward script name
PREFIX_MAPPING = {
    r"\bB001\b": "create_git_ops_db.sql",
    r"\bB002\b": "create_api_integration.sql",
    r"\bB003\b": "create_git_repository.sql",
}


def main():
    print(f"Starting Git renames and internal reference updates for {DIRECTORY}...")

    # Phase 1: Perform Git Renames
    for old_name, new_name in FILE_MAPPING.items():
        old_path = os.path.join(DIRECTORY, old_name)
        new_path = os.path.join(DIRECTORY, new_name)

        if os.path.exists(old_path):
            print(f"Renaming via Git: {old_name} -> {new_name}")
            subprocess.run(["git", "mv", old_path, new_path], check=True)
        else:
            print(f"Skipping (not found): {old_path}")

    # Phase 2: Find and Replace inside the newly renamed files
    for new_name in FILE_MAPPING.values():
        file_path = os.path.join(DIRECTORY, new_name)

        if not os.path.exists(file_path):
            continue

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Step A: Replace full filenames first
        for old_file, new_file in FILE_MAPPING.items():
            content = content.replace(old_file, new_file)

        # Step B: Replace isolated prefixes using regex word boundaries
        for prefix_pattern, replacement in PREFIX_MAPPING.items():
            content = re.sub(prefix_pattern, replacement, content)

        # Write updated content back to the file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        # Phase 3: Stage the text modifications in Git
        subprocess.run(["git", "add", file_path], check=True)
        print(f"Updated internal references and staged: {new_name}")

    print("\nAll files renamed, updated, and staged. Ready to commit.")


if __name__ == "__main__":
    main()
