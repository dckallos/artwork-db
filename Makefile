# =============================================================================
# Artwork Medallion Pipeline - task runner
# =============================================================================
# IaC runs bash -> sibling snowflake-toolkit -> snow sql.
#   iac / infra / bootstrap     apply all / infra only / git-setup only
#   rollback FILE=path.sql      roll back one forward script via its paired drop
#   down [FROM=create_*.sql]    full teardown / from a point, paired drops in reverse
#   extract[-met|-aic|-smithsonian]   run extractors
#   dbt-init|build|test|full-refresh|docs|teardown   dbt lifecycle (via orchestrator)
#   all / pipeline / setup      full apply / extract+build / infra+init
# =============================================================================

.PHONY: chmod iac bootstrap infra loader transformer rollback down down-from \
        extract extract-met extract-aic extract-smithsonian \
        dbt-init dbt-build dbt-test dbt-full-refresh dbt-docs dbt-teardown dbt-deps \
        all pipeline setup clean

DBT_PROJECT_DIR := artwork_pipeline

# Toolkit lives as a sibling repo (extracted from this monorepo).
# Override via: TOOLKIT_DIR=~/other/path/snowflake-toolkit make iac
TOOLKIT_DIR ?= ../snowflake-toolkit

# --- Fail-fast: toolkit must exist ---
ifeq ($(wildcard $(TOOLKIT_DIR)/snowflake_cli/setup.sh),)
  $(error snowflake-toolkit not found at $(TOOLKIT_DIR). \
    Clone it: git clone git@github.com-dckallos:dckallos/snowflake-toolkit.git $(TOOLKIT_DIR))
endif

# snow CLI connection that IaC targets. Defaults to "admin" (the historical
# single-account behavior). Override to apply infra to a second account whose
# admin connection was set up via `setup.sh --profile <label> --phase all`:
#   make iac CONN=clientb
# Threaded into every sibling toolkit orchestration invocation; the toolkit
# apply path forwards it to snow/sql validation helpers.
CONN ?= admin

# Template variables for DDL substitution (e.g., secrets, tokens)
# Pass as space-separated name=value pairs:
#   make bootstrap CONN=admin VARS="github_pat=${GITHUB_PAT} other_var=value"
# Framework forwards these as -D parameters to snow sql for template substitution.
VARS ?=

# ---------- git-setup credentials from .env (no manual VARS= needed) ----------
# The git-setup SQL templates expect three secrets injected at apply time:
#   github_pat, github_oauth_client_id, github_oauth_client_secret
# Source: an exported environment variable wins; otherwise the value is read
# straight from ENV_FILE (default .env), so `make iac` works whether you ran
# the toolkit's load_profile.sh, `set -a; source .env; set +a`, or nothing.
# This is the fix for the "inert MCP integration" foot-gun: empty creds are
# NEVER injected (see GIT_VARS below) -- a missing key is simply omitted.
ENV_FILE ?= .env

# getenvfile,NAME -> value of NAME= from ENV_FILE (first match), with one layer
# of surrounding single/double quotes stripped (matches load_profile.sh).
getenvfile = $(strip $(shell test -f $(ENV_FILE) && sed -n 's/^$(1)=//p' $(ENV_FILE) | head -n1 | sed -e 's/^"//' -e 's/"$$//' -e "s/^'//" -e "s/'$$//"))

# Simply-expanded (:=) so the self-reference resolves to the EXPORTED env value
# (make imports env vars) and falls back to the file -- no recursion.
GITHUB_PAT                 := $(or $(GITHUB_PAT),$(call getenvfile,GITHUB_PAT))
GITHUB_OAUTH_CLIENT_ID     := $(or $(GITHUB_OAUTH_CLIENT_ID),$(call getenvfile,GITHUB_OAUTH_CLIENT_ID))
GITHUB_OAUTH_CLIENT_SECRET := $(or $(GITHUB_OAUTH_CLIENT_SECRET),$(call getenvfile,GITHUB_OAUTH_CLIENT_SECRET))

# Emit a name=value pair ONLY when the value is non-empty, so an unset OAuth id
# is never injected as ''. This is what keeps the MCP integration from going inert.
GIT_VARS := \
  $(if $(GITHUB_PAT),github_pat=$(GITHUB_PAT)) \
  $(if $(GITHUB_OAUTH_CLIENT_ID),github_oauth_client_id=$(GITHUB_OAUTH_CLIENT_ID)) \
  $(if $(GITHUB_OAUTH_CLIENT_SECRET),github_oauth_client_secret=$(GITHUB_OAUTH_CLIENT_SECRET))

# What the bootstrap (git-setup) phase actually injects. An explicit VARS= fully
# overrides the auto-derived creds (escape hatch); otherwise GIT_VARS is used.
BOOTSTRAP_VARS := $(if $(strip $(VARS)),$(VARS),$(GIT_VARS))

# ---------- Executable bit policy (Phase 0.6 IaC strategy 3.4) ----------
# Idempotent chmod 0755 for every .sh the toolkit shells out to. Prereq of
# every IaC target so a missing +x bit can't break `make iac`. Allow-list lives
# in the toolkit's executable_files.txt. Run via `bash` so it works even when
# that script is itself 0644.

chmod:
	@bash $(TOOLKIT_DIR)/bootstrap_chmod.sh

# ---------- IaC ----------
# Targets that run bootstrap.py depend on `chmod` so the .sh files are +x
# before Python shells out.

iac: chmod
	@echo "==> Applying ALL IaC via sibling snowflake-toolkit -> snow sql --filename..."
	bash $(TOOLKIT_DIR)/orchestrate_modern.sh --ddl-dir infrastructure/ --manifest scripts/manifest.txt --phase infra --connection $(CONN)
	$(call run_bootstrap,$(CONN),$(BOOTSTRAP_VARS))

# git-setup (B) is the optional trailing Git-mirror layer; per the 2026-05-29
# design decision it runs LAST in `make iac` (after V/R). Standalone run needs
# ARTWORK_ADMIN to exist with READ on the repo, so run `make infra`
# first on a fresh account. No infra prereq here, to keep this target composable.
bootstrap: chmod
	@echo "==> Applying git-setup (B) via bash orchestrator -> snow sql --filename..."
	@echo "    NOTE: B is the OPTIONAL trailing Git-mirror layer (runs LAST in 'make iac')."
	@echo "    Standalone 'make bootstrap' presumes ARTWORK_ADMIN already exists"
	@echo "    (created by infrastructure/V001 via 'make infra' or 'make iac')."
	$(call run_bootstrap,$(CONN),$(BOOTSTRAP_VARS))

infra: chmod
	@echo "==> Applying infrastructure via sibling snowflake-toolkit -> snow sql --filename..."
	bash $(TOOLKIT_DIR)/orchestrate_modern.sh --ddl-dir infrastructure/ --manifest scripts/manifest.txt --phase infra --connection $(CONN)

# ---------- Loader credential (key-pair) ----------
# Mint + register the ARTWORK_LOADER_SVC key pair and wire a key-pair snow CLI
# connection for the account whose ADMIN connection is named CONN. Wraps the
# snowflake-toolkit's snowflake_cli suite so the loader credential
# lifecycle runs through the same `make` front door as the rest of IaC:
#   make loader CONN=mk07348
# With --profile <CONN>, setup.sh namespaces BOTH the connection and key file:
#   admin (used to register) : [connections.<CONN>]
#   NEW loader connection    : [connections.<CONN>_loader]
#   NEW loader private key   : ~/.snowflake/keys/<CONN>_loader_rsa_key.p8
# It registers the public key on ARTWORK_LOADER_SVC via the version-controlled
# git-setup/operator/register_loader_public_key.sql. Additive by design: the
# TOML upsert appends a fresh [connections.<CONN>_loader] block and never
# overwrites another account's [connections.loader].
loader: chmod
	@echo "==> Establishing loader key-pair for profile '$(CONN)' (additive; new key + connection)..."
	bash $(TOOLKIT_DIR)/snowflake_cli/setup.sh --profile $(CONN) --phase loader

# ---------- Transformer (dbt) credential (key-pair) ----------
# Same as `loader`, for the ARTWORK_TRANSFORMER_SVC dbt identity. Requires
# `make infra CONN=<conn>` to have created the (TYPE = SERVICE) user first.
#   make transformer CONN=mk07348
# Produces (namespaced): [connections.<CONN>_transformer] +
# ~/.snowflake/keys/<CONN>_transformer_rsa_key.p8, registering the public key on
# ARTWORK_TRANSFORMER_SVC via git-setup/operator/register_transformer_public_key.sql.
transformer: chmod
	@echo "==> Establishing transformer (dbt) key-pair for profile '$(CONN)' (additive; new key + connection)..."
	bash $(TOOLKIT_DIR)/snowflake_cli/setup.sh --profile $(CONN) --phase transformer

rollback: chmod
	@if [ -z "$(FILE)" ]; then \
		echo "usage: make rollback FILE=infrastructure/create_stages.sql"; \
		exit 64; \
	fi
	@PREFIX=$(FILE); \
    echo "==> Rolling back $$PREFIX via paired drop script..."; \
    bash $(TOOLKIT_DIR)/orchestrate_modern.sh --ddl-dir infrastructure/ --manifest scripts/manifest.txt --file $$PREFIX --connection $(CONN)

down: chmod
	@echo "==> Tearing down ALL IaC (paired drops in reverse order)..."
	bash $(TOOLKIT_DIR)/orchestrate_modern.sh --ddl-dir infrastructure/ --manifest scripts/manifest.txt --phase down --connection $(CONN)

down-from: chmod
	@if [ -z "$(FROM)" ]; then echo "usage: make down-from FROM=create_stages.sql"; exit 64; fi
	bash $(TOOLKIT_DIR)/orchestrate_modern.sh --ddl-dir infrastructure/ --manifest scripts/manifest.txt --phase down --from $(FROM) --connection $(CONN)

# ---------- Extraction ----------
# The Met CLI entry point is `python -m extraction.met.run <subcommand>`.
# Current Snowflake-authoritative path: snapshot -> seed-control -> enrich-met.
# (The legacy SQLite path -- bootstrap/enrich/upload/all/status -- still exists in
# the CLI but is superseded and is not wired here.)
#
# AWS_NO_SSO blinds botocore to any ambient AWS SSO profile for one command. The
# snapshot/enrich PUT to an internal stage spins up botocore; if the shell carries a
# (possibly dead) AWS SSO profile, botocore tries to refresh its token and stalls.
# Snowflake key-pair auth is unaffected, and the stage PUT uses scoped credentials
# Snowflake passes the connector directly -- so hiding the personal profile is safe.
AWS_NO_SSO := env -u AWS_PROFILE -u AWS_DEFAULT_PROFILE AWS_CONFIG_FILE=/dev/null AWS_SHARED_CREDENTIALS_FILE=/dev/null

# Optional knobs (empty = CLI default). Override on the command line, e.g.:
#   make extract-met MET_DEPT="European Paintings" MET_ENRICH_LIMIT=500
MET_DEPT ?=
MET_SEED_LIMIT ?=
MET_ENRICH_LIMIT ?=

# `extract` is an alias for the only built extractor today (Met).
extract: extract-met

extract-met:
	$(AWS_NO_SSO) python -m extraction.met.run snapshot
	python -m extraction.met.run seed-control $(if $(MET_DEPT),--department "$(MET_DEPT)") $(if $(MET_SEED_LIMIT),--limit $(MET_SEED_LIMIT))
	$(AWS_NO_SSO) python -m extraction.met.run enrich-met $(if $(MET_ENRICH_LIMIT),--limit $(MET_ENRICH_LIMIT))

# Not yet built -- placeholders for Track 4 (new data sources). Each will gain its
# own extraction/<source>/run.py with the same subcommand shape as Met, then get
# uncommented (with the AWS_NO_SSO prefix on any stage-PUT step).
# extract-aic:
#   $(AWS_NO_SSO) python -m extraction.aic.run snapshot
# extract-smithsonian:
# 	$(AWS_NO_SSO) python -m extraction.smithsonian.run snapshot

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
	bash scripts/dbt_orchestrate.sh --phase teardown --connection $(CONN)

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

# Helper function to run bootstrap with optional variables
define run_bootstrap
  $(if $(2),\
    bash -c 'vars="$(2)"; cmd="bash $(TOOLKIT_DIR)/orchestrate_modern.sh --ddl-dir git-setup/ --manifest scripts/manifest.txt --phase bootstrap --connection $(1)"; for var in $$vars; do cmd="$$cmd --var $$var"; done; eval "$$cmd"',\
    bash $(TOOLKIT_DIR)/orchestrate_modern.sh --ddl-dir git-setup/ --manifest scripts/manifest.txt --phase bootstrap --connection $(1))
endef
