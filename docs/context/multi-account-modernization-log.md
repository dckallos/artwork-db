# Multi-Account Modernization Progress Log — ARCHITECTURE RESET

> **CRITICAL ARCHITECTURE REVIEW (2026-06-03)**  
> Principal Engineer review identified fundamental separation of concerns violations.  
> Phase 3.2 DDL template conversion approach **CANCELLED** due to framework overreach.  
> Complete architectural reset required to maintain Facebook staff-level engineering standards.

## 🚨 PRINCIPAL ENGINEER FINDINGS: CATEGORY 1 VIOLATION

### **Root Problem: Framework Overreach**
The domain-agnostic framework crossed critical architectural boundaries by attempting to **own and modify domain-specific DDL**. This violates the fundamental principle that **orchestration tools should coordinate existing artifacts, not generate or modify business logic**.

### **Evidence of Boundary Violation**
1. **Template Substitution in DDL**: Planned modification of `infrastructure/create_databases_and_schemas.sql`
2. **Framework Domain Assumptions**: `config/artwork_domain.yml` contains business schema logic
3. **DDL Content Modification**: `ddl_orchestrator.sh` performing template processing on SQL

## CORRECTED ARCHITECTURAL VISION

### **Framework Responsibilities** ✅ (Legitimate)
1. **Connection Management**: Resolve which Snowflake connection to use
2. **Authentication Setup**: SSH keys, JWT tokens, connection validation  
3. **Execution Orchestration**: Apply user's DDL files in manifest order
4. **Environment Bootstrap**: User/role/warehouse setup for new accounts

### **User Project Responsibilities** ✅ (Must Remain)
1. **DDL Definition**: All SQL files in `infrastructure/` (unchanged)
2. **Domain Schema**: Database names, role names, business logic
3. **Manifest Ordering**: Which scripts to run in what order
4. **Application Code**: Extraction, transformation, domain-specific logic

### **Framework MUST NOT**
- ❌ Modify DDL file contents
- ❌ Know about specific database/role names
- ❌ Perform template substitution on SQL
- ❌ Contain domain-specific configuration

## REVISED IMPLEMENTATION STRATEGY

### **Pure Orchestration Framework**
```bash
# ✅ CORRECT: Framework provides connection utilities
./scripts/setup_connection.sh --account OBANOYY-MK07348 --user PORCHFLAKE
./scripts/orchestrate.sh --connection mk07348 --ddl-dir infrastructure/

# ❌ WRONG: Framework modifying DDL content
./scripts/orchestrate_modern.sh --config config/artwork_domain.yml --phase infra
```

## FRAMEWORK COMPONENT AUDIT

### **Keep (Pure Utilities)**
- ✅ `connection_resolver.sh` - Connection management utility
- ✅ `dbt_orchestrator.sh` - dbt execution utility (simplified)

### **Remove (Violates Separation)**
- ❌ `domain_config_loader.sh` - Framework shouldn't know domain details
- ❌ `config/artwork_domain.yml` - Domain config doesn't belong in framework
- ❌ Template substitution in `ddl_orchestrator.sh`

### **Simplify (Remove Domain Awareness)**
- ⚠️ `ddl_orchestrator.sh` - Remove template processing, keep file execution

## PHASE RESET PLAN

### **Phase R1: Strip Framework to Core** 
**Objective**: Remove all domain-specific logic from framework components

**Actions**:
1. Remove template substitution from `ddl_orchestrator.sh`
2. Delete `domain_config_loader.sh` (violates separation)
3. Delete `config/artwork_domain.yml` (domain logic doesn't belong in framework)
4. Simplify `orchestrate_modern.sh` to pure connection + file execution

### **Phase R2: Pure Connection Framework**
**Objective**: Framework provides ONLY connection/auth utilities

**Framework Interface**:
```bash
# User specifies their DDL directory and connection
./scripts/orchestrate.sh --connection mk07348 --ddl-dir infrastructure/ --manifest scripts/manifest.txt

# Framework executes user's DDL files unchanged
snow sql -f infrastructure/create_databases_and_schemas.sql -c mk07348
```

### **Phase R3: Multi-Account via Connection Only**
**Objective**: Multi-account deployment through connection switching, not DDL modification

**User Workflow**:
1. User has their DDL (unchanged): `infrastructure/create_databases_and_schemas.sql`
2. User configures connection for new account: `scripts/setup_connection.sh --account NEW_ACCOUNT`
3. User runs same DDL on new account: `./scripts/orchestrate.sh --connection new_account`

## PRESERVED ARTIFACTS

### **What We Keep from Current Work** ✅
- Connection resolution logic (pure utility)
- Multi-account connection setup
- Framework modular design principles
- CLI interface patterns
- Error handling standards

### **What We Remove** ❌
- All domain configuration (`config/artwork_domain.yml`)
- DDL template processing
- Framework knowledge of artwork-specific details
- Domain-agnostic configuration schemas

## BENEFITS OF CORRECTED ARCHITECTURE

### **Separation of Concerns** ✅
- Framework: Connection/auth utilities
- User project: Business logic and DDL

### **True Reusability** ✅
- Framework works with ANY Snowflake project
- No domain-specific knowledge required
- Users provide their own DDL unchanged

### **Maintainability** ✅
- Framework has single responsibility
- No domain-specific testing required
- Clear interface boundaries

## NEXT STEPS

1. **STOP Phase 3.2** - Do not modify DDL files
2. **Begin Phase R1** - Strip domain logic from framework
3. **Preserve DDL unchanged** - `infrastructure/` files remain as-is
4. **Focus on connection utilities** - Framework's legitimate purpose

## CRITICAL PRINCIPLE

> **The framework should orchestrate user artifacts, not generate them.**  
> **DDL files belong to the user's domain, not the framework.**

This reset maintains the valuable connection/orchestration work while fixing the fundamental architectural violation. The result will be a truly reusable framework that respects proper separation of concerns.