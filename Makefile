# =============================================================================
# Artwork Medallion Pipeline - Task Runner
# =============================================================================
# IaC (python -> bash -> snow sql --filename):
#   make iac                       Apply ALL: git-setup (B) + infra (V + R)
#   make bootstrap                 Apply git-setup (B) only
#   make infra                     Apply infrastructure (V + R) only
#   make rollback FILE=path.sql    Roll back ONE forward script via its paired drop
#   make down                      Full teardown: every paired drop in reverse order
#   make down-from FROM=V005       Teardown from V005 onward in reverse order
#
# Extraction:
#   make extract                   Run all extractors
#   make extract-met               Met Museum only
#
# dbt:
#   make dbt-deps / dbt-run / dbt-test / dbt-freshness / dbt-docs
#
# Compound:
#   make pipeline                  extract -> dbt run -> dbt test
#   make setup                     infra + dbt deps
# =============================================================================

.PHONY: chmod iac bootstrap infra rollback down down-from \
        extract extract-met extract-aic extract-cma extract-smithsonian \
        dbt-deps dbt-run dbt-test dbt-freshness dbt-docs pipeline setup clean

DBT_PROJECT_DIR := artwork_pipeline

# ---------- Executable bit policy (see Phase 0.6 IaC strategy § 3.4) ----------
# Idempotent chmod 0755 for every .sh in the bootstrap.py call graph.
# Wired in as a prereq of every IaC target so `make iac` cannot fail on a
# missing +x bit. The canonical allow-list lives in
# scripts/bootstrap_chmod.sh -- never duplicate it elsewhere.
# Invoked via `bash ...` so it works even when bootstrap_chmod.sh itself
# is mode 0644 (the bootstrap workaround for its own executable bit).
# Phony-target prereq pattern: https://www.gnu.org/software/make/manual/html_node/Phony-Targets.html

chmod:
	@bash scripts/bootstrap_chmod.sh

# ---------- IaC ----------
# Every target that invokes bootstrap.py depends on `chmod` so the executable
# bit on apply_sql.sh / rollback_sql.sh / scripts/snowflake_cli/*.sh is
# guaranteed before Python shells out via subprocess.run(...).

iac: chmod
	@echo "==> Applying ALL IaC (B + V + R) via python -> bash -> snow sql --filename..."
	python scripts/bootstrap.py --phase all

bootstrap: chmod
	@echo "==> Applying git-setup (B) via python -> bash -> snow sql --filename..."
	python scripts/bootstrap.py --phase bootstrap

infra: chmod
	@echo "==> Applying infrastructure (V + R) via python -> bash -> snow sql --filename..."
	python scripts/bootstrap.py --phase infra

rollback: chmod
	@if [ -z "$(FILE)" ]; then \
		echo "usage: make rollback FILE=infrastructure/V005__create_stages.sql"; \
		exit 64; \
	fi
	@PREFIX=$$(basename $(FILE) | cut -d_ -f1); \
		echo "==> Rolling back $$PREFIX via paired drop script..."; \
		python scripts/bootstrap.py --down --file $$PREFIX

down: chmod
	@echo "==> Tearing down ALL IaC (paired drops in reverse order)..."
	python scripts/bootstrap.py --phase down

down-from: chmod
	@if [ -z "$(FROM)" ]; then echo "usage: make down-from FROM=V005"; exit 64; fi
	python scripts/bootstrap.py --phase down --from $(FROM)

# ---------- Extraction ----------

extract:
	python -m extraction.run

extract-met:
	python -m extraction.run --source met

extract-aic:
	python -m extraction.run --source aic

extract-cma:
	python -m extraction.run --source cma

extract-smithsonian:
	python -m extraction.run --source smithsonian

# ---------- dbt ----------

dbt-deps:
	dbt deps --project-dir $(DBT_PROJECT_DIR)

dbt-run:
	dbt run --project-dir $(DBT_PROJECT_DIR)

dbt-test:
	dbt test --project-dir $(DBT_PROJECT_DIR)

dbt-freshness:
	dbt source freshness --project-dir $(DBT_PROJECT_DIR)

dbt-docs:
	dbt docs generate --project-dir $(DBT_PROJECT_DIR)
	dbt docs serve --project-dir $(DBT_PROJECT_DIR)

# ---------- Compound ----------

pipeline: extract dbt-run dbt-test
	@echo "==> Pipeline complete."

setup: infra dbt-deps
	@echo "==> Setup complete. Run 'make extract' to populate Bronze."

clean:
	rm -rf $(DBT_PROJECT_DIR)/target $(DBT_PROJECT_DIR)/dbt_packages $(DBT_PROJECT_DIR)/logs
