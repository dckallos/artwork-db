#!/usr/bin/env bash
# =============================================================================
# dbt_orchestrate_modern.sh — Modernized dbt orchestrator using domain-agnostic framework
# =============================================================================
#
# CONTEXT: Legacy script modernization for domain-agnostic framework
# PURPOSE: Modernized version of scripts/dbt_orchestrate.sh using framework components
# MAINTAINER: Facebook staff-level implementation
#
# This script provides modernized dbt orchestration using the domain-agnostic
# framework components. It provides unified connection handling across all dbt
# phases and enables multi-domain dbt deployments. Once thoroughly tested,
# this will replace scripts/dbt_orchestrate.sh.
#
# ARCHITECTURE:
#   - Uses scripts/lib/dbt_orchestrator.sh for core functionality
#   - Unified connection parameter support across all phases
#   - Domain configuration support via --config parameter
#   - Dynamic profile generation from domain config
#
# USAGE:
#   scripts/dbt_orchestrate_modern.sh --phase build --connection transformer
#   scripts/dbt_orchestrate_modern.sh --config config/artwork_domain.yml --phase build --connection mk07348
#   scripts/dbt_orchestrate_modern.sh --phase teardown --connection admin
#
# TESTING STATUS: New implementation - requires thorough testing before replacing legacy script
#
# =============================================================================

set -euo pipefail

# Framework component metadata
readonly DBT_ORCHESTRATE_MODERN_VERSION="1.0.0"
readonly DBT_ORCHESTRATE_MODERN_CREATED="2026-06-02"

# Script configuration
readonly MODERN_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly REPO_ROOT="$(cd "${MODERN_SCRIPT_DIR}/.." && pwd)"

# Source framework components
source "${MODERN_SCRIPT_DIR}/lib/dbt_orchestrator.sh"

# Default values for backward compatibility
DEFAULT_CONFIG="${REPO_ROOT}/config/artwork_domain.yml"

# =============================================================================
# MAIN ORCHESTRATION FUNCTION
# =============================================================================

# main
#
# Primary entry point for modernized dbt orchestration.
# Provides unified connection handling and domain-agnostic deployment.
main() {
    local config_file=""
    local phase=""
    local connection=""
    local target=""
    local show_help=false
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --config)
                config_file="$2"
                shift 2
                ;;
            --phase)
                phase="$2"
                shift 2
                ;;
            --connection)
                connection="$2"
                shift 2
                ;;
            --target)
                target="$2"
                shift 2
                ;;
            -h|--help|help)
                show_help=true
                shift
                ;;
            *)
                _log_error "Unknown argument: $1"
                _show_usage
                exit 1
                ;;
        esac
    done
    
    # Show help if requested
    if [[ "$show_help" == true ]]; then
        _show_usage
        exit 0
    fi
    
    # Validate and set defaults
    if [[ -z "$config_file" ]]; then
        if [[ -f "$DEFAULT_CONFIG" ]]; then
            config_file="$DEFAULT_CONFIG"
            _log_info "Using default configuration: $config_file"
        else
            _log_error "No configuration specified and default not found: $DEFAULT_CONFIG"
            _log_error "Specify configuration with: --config CONFIG_FILE"
            exit 1
        fi
    fi
    
    if [[ -z "$phase" ]]; then
        _log_error "Phase is required. Use --help for usage information."
        exit 1
    fi
    
    # Execute dbt phase using framework
    _log_info "Modernized dbt Orchestrator v${DBT_ORCHESTRATE_MODERN_VERSION}"
    _log_info "Domain-agnostic framework execution"
    
    # Build arguments for framework call
    local framework_args=()
    framework_args+=(--config "$config_file")
    framework_args+=(--phase "$phase")
    
    if [[ -n "$connection" ]]; then
        framework_args+=(--connection "$connection")
    fi
    
    if [[ -n "$target" ]]; then
        framework_args+=(--target "$target")
    fi
    
    # Execute via framework component
    execute_dbt_phase "${framework_args[@]}"
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

# Show usage information with modernization benefits
_show_usage() {
    cat <<EOF
dbt_orchestrate_modern.sh — Modernized dbt orchestrator using domain-agnostic framework

DESCRIPTION:
    Modernized version of scripts/dbt_orchestrate.sh that uses domain-agnostic framework
    components. Provides unified connection handling and enables multi-domain deployments.

USAGE:
    scripts/dbt_orchestrate_modern.sh [OPTIONS]

OPTIONS:
    --config FILE       Domain configuration file (default: config/artwork_domain.yml)
    --phase PHASE       dbt phase to execute (required)
    --connection CONN   Snowflake connection name (optional)
    --target TARGET     dbt target override (optional, default: prod)
    --help              Show this help message

PHASES:
    init                Generate profile, install deps, verify connectivity
    deps                Install dbt package dependencies
    build               Execute models and tests
    test                Execute tests only
    docs                Generate and serve documentation
    teardown            Drop all dbt-managed objects (requires confirmation)
    full-refresh        Rebuild all models from scratch

MODERNIZATION BENEFITS:
    ✓ Unified connection parameter across ALL phases (not just teardown)
    ✓ Domain configuration support for multi-account deployments
    ✓ Dynamic profile generation from domain config
    ✓ Enhanced error handling and validation
    ✓ Framework integration for consistency

BACKWARD COMPATIBILITY:
    # Legacy dbt_orchestrate.sh command format
    scripts/dbt_orchestrate.sh --phase build
    
    # Modern equivalent with explicit connection
    scripts/dbt_orchestrate_modern.sh --phase build --connection transformer
    
    # Multi-domain deployment (new capability)
    scripts/dbt_orchestrate_modern.sh --config config/customer_domain.yml --phase build --connection prod-transformer

FRAMEWORK INTEGRATION:
    - Uses scripts/lib/dbt_orchestrator.sh for core functionality
    - Dynamic profiles.yml generation from domain configuration
    - Connection capability validation (transformer role requirements)
    - Template-driven configuration for any Snowflake account
    - Comprehensive logging and error reporting

MIGRATION NOTES:
    1. All dbt phases now support --connection parameter consistently
    2. Profiles are generated dynamically (no static .env dependency)
    3. Domain configuration enables deployment to any account
    4. Connection resolution follows framework priority system

EXAMPLES:
    # Initialize dbt with explicit connection
    scripts/dbt_orchestrate_modern.sh --phase init --connection mk07348
    
    # Build models using domain configuration
    scripts/dbt_orchestrate_modern.sh --config config/artwork_domain.yml --phase build --connection mk07348
    
    # Run tests with custom target
    scripts/dbt_orchestrate_modern.sh --phase test --connection transformer --target dev
    
    # Teardown with confirmation (works with any connection now)
    scripts/dbt_orchestrate_modern.sh --phase teardown --connection admin
    
    # Generate and serve docs
    scripts/dbt_orchestrate_modern.sh --phase docs --connection transformer

EOF
}

# Logging functions
_log_info() {
    echo "==> [dbt_orchestrate_modern] $*" >&2
}

_log_error() {
    echo "ERROR [dbt_orchestrate_modern] $*" >&2
}

# =============================================================================
# EXECUTION
# =============================================================================

# Execute main function if script is run directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi