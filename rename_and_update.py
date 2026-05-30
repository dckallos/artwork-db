import os
import subprocess
import re

# Directory containing the SQL files
DIRECTORY = "infrastructure"

# 1. Configuration Set for Git Renames (Old Filename -> New Filename)
FILE_MAPPING = {
    "V001__create_roles.sql": "create_roles.sql",
    "V002__create_warehouses.sql": "create_warehouses.sql",
    "V003__create_databases_and_schemas.sql": "create_databases_and_schemas.sql",
    "V004__create_file_formats.sql": "create_file_formats.sql",
    "V005__create_stages.sql": "create_stages.sql",
    "V006__grant_privileges.sql": "grant_privileges.sql",
    "V007__create_bronze_tables.sql": "create_bronze_tables.sql",
    "V008__create_service_user.sql": "create_service_user.sql",
    "V009__create_tasks.sql": "create_tasks.sql",
    "R001__refresh_grants.sql": "refresh_grants.sql",
    "V001__drop_roles.sql": "drop_roles.sql",
    "V002__drop_warehouses.sql": "drop_warehouses.sql",
    "V003__drop_databases_and_schemas.sql": "drop_databases_and_schemas.sql",
    "V004__drop_file_formats.sql": "drop_file_formats.sql",
    "V005__drop_stages.sql": "drop_stages.sql",
    "V006__drop_grants.sql": "drop_grants.sql",
    "V007__drop_bronze_tables.sql": "drop_bronze_tables.sql",
    "V008__drop_service_user.sql": "drop_service_user.sql",
    "V009__drop_tasks.sql": "drop_tasks.sql",
}

# 2. Configuration Set for Prefixes (Regex Word Boundary -> Primary Forward Script)
PREFIX_MAPPING = {
    r"\bV001\b": "create_roles.sql",
    r"\bV002\b": "create_warehouses.sql",
    r"\bV003\b": "create_databases_and_schemas.sql",
    r"\bV004\b": "create_file_formats.sql",
    r"\bV005\b": "create_stages.sql",
    r"\bV006\b": "grant_privileges.sql",
    r"\bV007\b": "create_bronze_tables.sql",
    r"\bV008\b": "create_service_user.sql",
    r"\bV009\b": "create_tasks.sql",
    r"\bR001\b": "refresh_grants.sql"
}


def main():
    print("Starting Git renames and internal reference updates...")

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

        # Step A: Replace full filenames first (e.g., infrastructure/V001__drop_roles.sql)
        for old_file, new_file in FILE_MAPPING.items():
            content = content.replace(old_file, new_file)

        # Step B: Replace isolated prefixes (e.g., "V001") using regex word boundaries
        for prefix_pattern, replacement in PREFIX_MAPPING.items():
            content = re.sub(prefix_pattern, replacement, content)

        # Write updated content back to the file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        # Phase 3: Stage the text modifications in Git
        # (git mv only stages the rename; modifying the file requires re-staging)
        subprocess.run(["git", "add", file_path], check=True)
        print(f"Updated internal references and staged: {new_name}")

    print("\nAll files renamed, updated, and staged. Ready to commit.")


if __name__ == "__main__":
    main()