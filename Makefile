# =============================================================================
# Artwork Medallion Pipeline - task runner
# =============================================================================
# IaC runs bash -> bash -> snow sql. Apply order: infra (V + R) then git-setup (B).
#   iac / infra / bootstrap     apply all / infra only / git-setup only (B runs last)
#   rollback FILE=path.sql      roll back one forward script via its paired drop
#   down [FROM=V005]            full teardown / from a point, paired drops in reverse
#   extract[-met|-aic|-cma|-smithsonian]   run extractors
#   dbt-init|build|test|full-refresh|docs|teardown   dbt lifecycle (via orchestrator)
#   all / pipeline / setup      full apply / extract+build / infra+init
# =============================================================================

.PHONY: chmod iac bootstrap infra rollback down down-from \
        extract extract-met extract-aic extract-cma extract-smithsonian \
        dbt-init dbt-build dbt-test dbt-full-refresh dbt-docs dbt-teardown dbt-deps \
        all pipeline setup clean

DBT_PROJECT_DIR := artwork_pipeline

# ---------- Executable bit policy (Phase 0.6 IaC strategy 3.4) ----------
# Idempotent chmod 0755 for every .sh bootstrap.py shells out to. Prereq of
# every IaC target so a missing +x bit can't break `make iac`. Allow-list lives
# in scripts/bootstrap_chmod.sh (don't duplicate). Run via `bash` so it works
# even when that script is itself 0644.

chmod:
	@bash scripts/bootstrap_chmod.sh

# ---------- IaC ----------
# Targets that run bootstrap.py depend on `chmod` so the .sh files are +x
# before Python shells out.

iac: chmod
	@echo "==> Applying ALL IaC (B + V + R) via bash orchestrator -> snow sql --filename..."
	bash scripts/orchestrate.sh --phase all

# git-setup (B) is the optional trailing Git-mirror layer; per the 2026-05-29
# design decision it runs LAST in `make iac` (after V/R). Standalone run needs
# ARTWORK_ADMIN to exist (B003 grants it READ on the repo), so run `make infra`
# first on a fresh account. No infra prereq here, to keep this target composable.
bootstrap: chmod
	@echo "==> Applying git-setup (B) via bash orchestrator -> snow sql --filename..."
	@echo "    NOTE: B is the OPTIONAL trailing Git-mirror layer (runs LAST in 'make iac')."
	@echo "    Standalone 'make bootstrap' presumes ARTWORK_ADMIN already exists"
	@echo "    (created by infrastructure/V001 via 'make infra' or 'make iac')."
	bash scripts/orchestrate.sh --phase bootstrap

infra: chmod
	@echo "==> Applying infrastructure (V + R) via bash orchestrator -> snow sql --filename..."
	bash scripts/orchestrate.sh --phase infra

rollback: chmod
	@if [ -z "$(FILE)" ]; then \
		echo "usage: make rollback FILE=infrastructure/create_stages.sql"; \
		exit 64; \
	fi
	@PREFIX=$(FILE); \
		echo "==> Rolling back $$PREFIX via paired drop script..."; \
		bash scripts/orchestrate.sh --down --file $$PREFIX

down: chmod
	@echo "==> Tearing down ALL IaC (paired drops in reverse order)..."
	bash scripts/orchestrate.sh --phase down

down-from: chmod
	@if [ -z "$(FROM)" ]; then echo "usage: make down-from FROM=V005"; exit 64; fi
	bash scripts/orchestrate.sh --phase down --from $(FROM)

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

# ---------- dbt (via dbt_orchestrate.sh) ----------
# The orchestrator sources .env, validates vars, and calls dbt with correct
# --project-dir and --profiles-dir. Use these targets on the Mac.

dbt-init:
	bash scripts/dbt_orchestrate.sh --phase init

dbt-build:
	bash scripts/dbt_orchestrate.sh --phase build

dbt-test:
	bash scripts/dbt_orchestrate.sh --phase test

dbt-full-refresh:
	bash scripts/dbt_orchestrate.sh --phase full-refresh

dbt-docs:
	bash scripts/dbt_orchestrate.sh --phase docs

dbt-teardown:
	bash scripts/dbt_orchestrate.sh --phase teardown

# Direct dbt commands (bypass orchestrator; assumes env is already set)
dbt-deps:
	dbt deps --project-dir $(DBT_PROJECT_DIR) --profiles-dir $(DBT_PROJECT_DIR)

# ---------- Compound ----------

all: infra dbt-build bootstrap
	@echo "==> Full pipeline applied (infra + dbt + git-setup)."

pipeline: extract dbt-build
	@echo "==> Pipeline complete (extract + dbt build)."

setup: infra dbt-init
	@echo "==> Setup complete. Run 'make extract' then 'make dbt-build'."

clean:
	rm -rf $(DBT_PROJECT_DIR)/target $(DBT_PROJECT_DIR)/dbt_packages $(DBT_PROJECT_DIR)/logs
