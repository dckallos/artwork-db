# Phase 0 Refactoring Progress

## Group 1: Toolkit Generalization
- [x] Item 1: `scripts/snowflake_cli/_lib.sh` -- remove ARTWORK_WH default
- [x] Item 2: `scripts/snowflake_cli/06_setup_loader_keypair.sh` -- :? guards for LOADER_USER/ROLE
- [x] Item 3: `scripts/snowflake_cli/06_setup_loader_keypair.sh` -- generic SQL_FILE path + create template
- [x] Item 4: `scripts/snowflake_cli/09_setup_transformer_keypair.sh` -- :? guards for TRANSFORMER_USER/ROLE
- [x] Item 5: `scripts/snowflake_cli/09_setup_transformer_keypair.sh` -- generic SQL_FILE path
- [x] Item 6: `scripts/lib/framework_integration_test.sh` -- parameterize database assertion
- [x] Item 7: `scripts/bootstrap.py` -- add --role-name argument, remove ARTWORK_ADMIN hardcoding
- [x] Item 8: `scripts/activate_mac.sh` -- generalize artwork-specific text

## Group 2: dbt-diagnostics Decoupling
- [DEFERRED] Item 9: `dbt_diagnostics/pyproject.toml` -- deferred to extraction (where=["."] breaks editable install while pyproject.toml is nested inside the package dir)
- [x] Item 10: `dbt_diagnostics/config.yml` -- dbt_project_dir to .
- [x] Item 11: `dbt_diagnostics/config.yml` -- profile_name to default
- [x] Item 12: `dbt_diagnostics/LINEAGE_TRAIL_PLAN.md` -- genericize examples

## Group 3: artwork-db Preparation
- [x] Item 13: `.env.example` -- add TOOLKIT_DIR and toolkit config vars
- [x] Item 14: `Makefile` -- add TOOLKIT_DIR variable
