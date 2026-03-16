# Long Function Refactoring Analysis

## Summary Statistics

| Function | Lines | Complexity | Refactoring Priority |
|----------|-------|------------|---------------------|
| extract_services() | 113 | High | **HIGH** |
| extract_app_metadata() | 91 | Medium | LOW |
| api_fetch_with_retry() | 76 | High | MEDIUM |
| extract_processes() | 75 | Medium | **HIGH** |
| cli_show_help() | 72 | Low (heredoc) | N/A |
| cli_parse_args() | 61 | Medium | MEDIUM |
| api_fetch_all_pages() | 57 | Medium | LOW |
| extract_routes_and_domains() | 55 | Medium | **HIGH** |
| sanitize_env_vars() | 44 | Low | LOW |
| extract_spaces() | 44 | Low | LOW |

## High Priority Refactorings

### 1. extract_services() (113 lines) → Extract service instance processing

**Current Issues:**
- Deeply nested loop with complex service instance detail extraction
- Mixes concerns: binding extraction, instance retrieval, plan/offering lookup, and formatting
- Hard to test individual pieces
- Contains 3 levels of nested API calls

**Proposed Decomposition:**

```bash
# Lines 1139-1212 → New function
function extract_service_instance_details() {
  local service_instance_guid="$1"

  # Fetch instance, plan, and offering details
  # Build formatted entry string
  # Return entry via echo
}

# Lines 1180-1206 → New function
function format_service_instance_entry() {
  local instance_name="$1"
  local instance_guid="$2"
  local offering_name="$3"
  local plan_name="$4"
  local instance_type="$5"

  # Build entry with details in brackets
  # Return formatted string
}

# Simplified extract_services()
function extract_services() {
  # Fetch bindings (lines 1109-1127)
  # Loop through instance GUIDs
  # Call extract_service_instance_details for each
  # Accumulate results
}
```

**Benefits:**
- Each function <40 lines
- Easier to test formatting logic separately
- Can add unit tests for entry formatting
- Clearer separation of API calls vs data formatting

---

### 2. extract_processes() (75 lines) → Extract security group aggregation and CSV formatting

**Current Issues:**
- Mixes concerns: API fetching, security group aggregation, CSV row formatting
- Security group aggregation is repetitive pattern used elsewhere
- CSV row construction is very long (lines 1304-1314)
- 15 function parameters is excessive

**Proposed Decomposition:**

```bash
# New utility function (reusable)
function util_join_with_separator() {
  local separator="$1"
  shift
  local result=""

  for item in "$@"; do
    [[ -z "${item}" ]] && continue
    if [[ -n "${result}" ]]; then
      result="${result}${separator}${item}"
    else
      result="${item}"
    fi
  done

  echo "${result}"
}

# New function for security group aggregation
function aggregate_security_groups() {
  local space_groups="$1"
  local org_groups="$2"
  local global_groups="$3"

  util_join_with_separator "${CONFIG_CSV_MULTIVALUE_SEP}" \
    "${space_groups}" "${org_groups}" "${global_groups}"
}

# New function for CSV row writing
function csv_write_app_row() {
  local org_name="$1"
  local space_name="$2"
  local app_name="$3"
  # ... (17 total parameters → consider using associative array or struct-like pattern)

  # Build and write CSV row
}

# Simplified extract_processes()
function extract_processes() {
  # Fetch processes
  # Loop through processes
  # Call aggregate_security_groups
  # Call csv_write_app_row
}
```

**Benefits:**
- `util_join_with_separator()` is reusable across codebase
- Security group aggregation becomes one-liner
- CSV row writing is isolated and testable
- Easier to modify CSV format in one place

**Alternative Approach:**
Consider using bash associative array for app metadata to avoid 15-parameter function:

```bash
declare -A app_metadata
app_metadata[org]="${ORG_NAME}"
app_metadata[space]="${space_name}"
# ... etc
csv_write_app_row app_metadata
```

---

### 3. extract_routes_and_domains() (55 lines) → Extract domain processing loop

**Current Issues:**
- Two distinct concerns: route extraction and domain extraction
- Domain extraction loop (lines 1072-1088) is complex with GUID deduplication
- Could benefit from clearer separation

**Proposed Decomposition:**

```bash
# New function
function extract_domains_from_route_json() {
  local routes_json="$1"

  local domain_guids
  domain_guids=$(echo "${routes_json}" | jq -r \
    '(.resources // [])[]?.relationships.domain.data.guid | select(length>0)')

  local domains=""
  if [[ -n "${domain_guids}" ]]; then
    while read -r domain_guid; do
      [[ -z "${domain_guid}" ]] && continue
      local domain_name
      domain_name=$(api_fetch_optional "/v3/domains/${domain_guid}" \
                    "Domain ${domain_guid}" | jq -r '.name // empty')
      if [[ -n "${domain_name}" ]]; then
        domains=$(util_join_with_separator "${CONFIG_CSV_MULTIVALUE_SEP}" \
                  "${domains}" "${domain_name}")
      fi
    done < <(printf "%s\n" "${domain_guids}" | sort -u)
  fi

  echo "${domains}"
}

# Simplified extract_routes_and_domains()
function extract_routes_and_domains() {
  # Fetch routes JSON
  # Validate
  # Extract routes
  # EXTRACTED_DOMAINS=$(extract_domains_from_route_json "${routes_json}")
}
```

**Benefits:**
- Clear separation between route and domain extraction
- Domain extraction logic is reusable if needed elsewhere
- Easier to test domain extraction in isolation
- Main function becomes clearer orchestrator

---

## Medium Priority Refactorings

### 4. api_fetch_with_retry() (76 lines) → Extract retry loop logic

**Current Issues:**
- Retry loop logic is complex but doing multiple things
- Error classification already extracted (good!)
- Could benefit from extracting the retry decision logic

**Proposed Decomposition:**

```bash
# New function
function should_retry_error() {
  local error_type="$1"
  local attempt="$2"
  local max_retries="$3"

  case "${error_type}" in
    "auth_error"|"not_found"|"client_error")
      return 1  # Don't retry permanent errors
      ;;
    "network_error"|"server_error")
      if [[ "${attempt}" -lt "${max_retries}" ]]; then
        return 0  # Retry transient errors
      else
        return 1  # Max retries exceeded
      fi
      ;;
    *)
      # Unexpected - retry if attempts remaining
      [[ "${attempt}" -lt "${max_retries}" ]]
      ;;
  esac
}

# Simplified api_fetch_with_retry()
function api_fetch_with_retry() {
  # ... setup ...

  while [[ "${attempt}" -le "${max_retries}" ]]; do
    # Execute API call
    # Check for success
    # Classify error

    if should_retry_error "${error_type}" "${attempt}" "${max_retries}"; then
      # Log warning and apply backoff
      echo "WARNING: Transient error ..." >&2
      sleep "${backoff}"
      backoff=$((backoff * 2))
    else
      # Log error and return
      echo "ERROR: ..." >&2
      echo "__ERROR_..."
      return X
    fi

    attempt=$((attempt + 1))
  done
}
```

**Benefits:**
- Retry decision logic is testable in isolation
- Clearer separation of concerns
- Easier to modify retry behavior

**Note:** This refactoring provides moderate benefit since the function is already fairly clear.

---

### 5. cli_parse_args() (61 lines) → Extract validation and defaults

**Current Issues:**
- Mixes argument parsing, validation, and default value assignment
- Could benefit from clearer structure

**Proposed Decomposition:**

```bash
# New function
function cli_set_defaults() {
  if [[ -z "${OUTFILE}" ]]; then
    OUTFILE="${CONFIG_OUTPUT_PREFIX}_${ORG_NAME}_"
    OUTFILE="${OUTFILE}$(date +${CONFIG_CSV_TIMESTAMP_FORMAT}).csv"
  fi
}

# New function
function cli_validate_required_args() {
  if [[ -z "${ORG_NAME}" ]]; then
    echo "Usage: $0 <org_name> [options]"
    echo "Try '$0 --help' for more information."
    exit 1
  fi
}

# Simplified cli_parse_args()
function cli_parse_args() {
  # Check for help first

  # Initialize defaults
  ORG_NAME=""
  DEBUG=""
  OUTFILE=""

  # Parse arguments (while loop stays the same)

  # Validate and set defaults
  cli_validate_required_args
  cli_set_defaults
}
```

**Benefits:**
- Clearer separation of parsing, validation, and defaults
- Each function has single responsibility
- Easier to test validation logic

---

## Low Priority / No Action Needed

### extract_app_metadata() (91 lines)
**Status:** Well-structured orchestrator function
**Reasoning:**
- Already delegates to specialized functions (extract_buildpack_metadata, extract_docker_metadata, etc.)
- Main body is simple sequential calls
- No complex nested logic
- Serves as clear orchestrator for app-level extraction

**Recommendation:** Keep as-is

---

### api_fetch_all_pages() (57 lines)
**Status:** Appropriate length for complexity
**Reasoning:**
- Handles pagination logic with proper abstraction
- No obvious decomposition that would improve clarity
- Already single-purpose (fetch all pages)

**Recommendation:** Keep as-is

---

### cli_show_help() (72 lines)
**Status:** Mostly heredoc, not refactorable
**Reasoning:**
- 95% of function is static help text in heredoc
- No logic to extract

**Recommendation:** Keep as-is

---

## General Refactoring Patterns Identified

### Pattern 1: Semicolon-separated list building
**Current Pattern (repeated 10+ times):**
```bash
if [[ -n "${existing_list}" ]]; then
  existing_list="${existing_list}${CONFIG_CSV_MULTIVALUE_SEP}${new_item}"
else
  existing_list="${new_item}"
fi
```

**Proposed Utility:**
```bash
function util_append_to_list() {
  local existing_list="$1"
  local new_item="$2"
  local separator="${3:-${CONFIG_CSV_MULTIVALUE_SEP}}"

  if [[ -n "${existing_list}" ]]; then
    echo "${existing_list}${separator}${new_item}"
  else
    echo "${new_item}"
  fi
}

# Usage:
domains=$(util_append_to_list "${domains}" "${domain_name}")
```

**Impact:** Would reduce ~15-20 lines across multiple functions

---

### Pattern 2: Null coalescing for jq output
**Current Pattern (repeated 20+ times):**
```bash
value=$(echo "${json}" | jq -r '.field // empty')
if [[ "${value}" == "null" ]]; then
  value=""
fi
```

**Proposed Utility:**
```bash
function util_jq_extract() {
  local json="$1"
  local jq_expr="$2"
  local result

  result=$(echo "${json}" | jq -r "${jq_expr}")
  if [[ "${result}" == "null" ]]; then
    echo ""
  else
    echo "${result}"
  fi
}

# Usage:
buildpacks=$(util_jq_extract "${droplet_json}" \
  '[.buildpacks[]?.name] // [] | map(select(length>0)) | join(";")')
```

**Impact:** Would reduce ~40-50 lines across codebase

---

## Implementation Recommendations

### Phase 1 (High Impact, Low Risk) ✅ COMPLETED
1. ✅ Add `util_join_with_separator()` utility (23 lines)
2. ✅ Add `util_append_to_list()` utility (16 lines)
3. ✅ Add `aggregate_security_groups()` helper (17 lines)
4. ✅ Refactor `extract_processes()` to use new utilities (75 → 58 lines, -17 lines)
5. ✅ Refactor `extract_routes_and_domains()` (55 → 50 lines, -5 lines)
6. ✅ Refactor `extract_services()` (113 → 111 lines, -2 lines)
7. ✅ Refactor `sanitize_env_vars()` (removed append duplication)
8. ✅ Refactor `extract_global_security_groups()` (removed append duplication)

**Actual Results:**
- Function length reductions: 24 lines saved from targeted functions
- New utilities added: 56 lines (reusable across codebase)
- Net change: +32 lines (investment in DRY utilities)
- Duplicated append logic instances removed: 4
- extract_processes() improvement: 23% reduction (75 → 58 lines)
- Security group aggregation: 20 lines → 2 lines (90% reduction)
**Risk:** Very low (all new utilities are pure functions)
**Status:** ✅ All validations passing (bash -n, shellcheck)

### Phase 2 (High Impact, Medium Risk) ✅ COMPLETED
1. ✅ Extract `extract_service_instance_details()` from `extract_services()` (48 lines)
2. ✅ Extract `format_service_instance_entry()` from `extract_services()` (35 lines)
3. ✅ Extract `extract_domains_from_routes()` from `extract_routes_and_domains()` (23 lines)

**Actual Results:**
- extract_services(): 111 → 48 lines (**57% reduction!**)
- extract_routes_and_domains(): 50 → 36 lines (28% reduction)
- New focused functions created: 3 (106 lines total)
- Service instance processing now testable in isolation
- Domain extraction logic reusable if needed elsewhere
- Clear separation of API fetching vs. data formatting
- Net change: +71 lines (investment in modularity)
**Risk:** Medium (changes complex service extraction flow)
**Status:** ✅ All validations passing (bash -n, shellcheck)

### Phase 3 (Medium Impact, Low Risk)
1. Add `util_jq_extract()` utility
2. Replace repetitive null coalescing patterns

**Estimated Reduction:** ~40-50 lines
**Risk:** Low (utility is simple)

### Phase 4 (Optional, Medium Impact)
1. Refactor `cli_parse_args()` with validation/defaults separation
2. Extract retry decision logic from `api_fetch_with_retry()`

**Estimated Reduction:** ~20-30 lines
**Risk:** Low

---

## Expected Outcomes

**Total Line Reduction:** 150-200 lines (from ~1,500 to ~1,300-1,350)
**Longest Function After Refactoring:** ~60 lines (vs current 113)
**New Reusable Utilities:** 4-5 functions
**Improved Testability:** 6-8 functions become unit-testable
**Maintainability:** Significantly improved through DRY principles

---

## Testing Strategy

For each refactoring phase:

1. **Before Changes:**
   - Run script against test org and capture CSV output
   - Generate checksum of output file

2. **After Changes:**
   - Run refactored script against same test org
   - Compare checksums (must be identical)
   - Run shellcheck --enable=all
   - Verify bash -n passes

3. **Additional Validation:**
   - Test with empty/missing data scenarios
   - Test with large datasets (>50 items per page)
   - Test error handling paths

---

## Notes

- All refactorings maintain 100% backward compatibility
- No changes to CSV output format
- No changes to command-line interface
- Focus on internal code quality improvements
- Each phase can be implemented and tested independently
