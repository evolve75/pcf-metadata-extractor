# Known Issues

This document tracks known issues and potential failure modes in the pcfusage-v3.sh script. Each issue is assigned a numeric ID for selective fixing and tracking.

## Purpose

The pcfusage-v3.sh script extracts metadata from Cloud Foundry environments to facilitate migration planning. However, several failure modes can result in incomplete or missing data. This document catalogs these issues to enable systematic improvements while maintaining the option to selectively address specific problems.

---

## ISSUE-001: API Pagination - Only First Page of Results Captured

**Description:**
The script uses Cloud Foundry v3 API endpoints that return paginated results. Currently, only the first page (typically 50 items) is captured for apps, spaces, and other resources. In large organizations with hundreds of apps or spaces, this results in incomplete data extraction.

**Affected Code:**
- Lines using `cf curl` without pagination handling
- All API calls to `/v3/apps`, `/v3/spaces`, `/v3/organizations`, etc.
- Functions that process API responses without checking for `pagination.next` links

**Impact:**
- **Severity:** High
- Large Cloud Foundry foundations will have incomplete metadata
- Organizations with >50 apps will only capture first 50 apps
- Migration planning based on incomplete data may miss critical applications
- No warning or indication that data is incomplete

**Status:** Fixed

**Resolution:**
Added `fetch_all_pages()` helper function implementing CF v3 API pagination:
- Automatically follows `pagination.next.href` links until all pages retrieved
- Accumulates resources from all pages into single JSON array
- Works with both cf_curl_critical and cf_curl_safe wrappers
- Applied to 6 critical list endpoints: spaces, apps, security groups, routes, service bindings, processes
- Debug mode shows pagination progress (page 1, page 2, etc.)
- Validates fetched count against API's total_results

Large Cloud Foundry environments now extract complete data regardless of volume.

---

## ISSUE-002: Empty/Null Data Handling - Silent Data Loss

**Description:**
When API responses contain null values or empty strings, the script may silently write empty CSV fields without validation. This makes it impossible to distinguish between "no data available" and "data extraction failed."

**Affected Code:**
- All `jq` extraction statements that don't validate for null/empty
- CSV field population without null checks
- Lines using `.fieldname // ""` without validating source data existence

**Impact:**
- **Severity:** Medium
- Silent data loss with no error indication
- Empty fields in CSV could represent valid empty values or extraction failures
- Difficult to identify which records need re-extraction
- Reduces confidence in data completeness

**Status:** Fixed

**Resolution:**
Added comprehensive null/empty data validation system:
- `validate_json_response()` helper function detects `{}` responses from cf_curl_safe
- Validation checks added at 6 critical extraction points:
  - App details (lifecycle type, buildpacks)
  - Droplet details (buildpack versions, runtime)
  - Routes and domains
  - Service bindings and instances
  - Environment variables
- Warning messages emitted to stderr when API responses are empty/invalid
- Data quality summary shows total warning count at completion
- Debug mode provides detailed context for each validation failure

Users can now distinguish between legitimate empty data (app has no routes) and extraction failures (API call failed), improving confidence in data completeness.

---

## ISSUE-003: API Call Failures - cf_curl_safe Returns {} on Error

**Description:**
The `cf_curl_safe` function returns an empty JSON object `{}` when API calls fail due to network issues, authentication problems, or API errors. Downstream processing treats this as valid (but empty) data rather than as an error condition.

**Affected Code:**
- `cf_curl_safe` function definition
- All callers of `cf_curl_safe` that don't validate response structure
- Error handling logic that doesn't distinguish between empty responses and errors

**Impact:**
- **Severity:** High
- Failed API calls go unnoticed
- Intermittent network issues cause silent data loss
- No retry mechanism for transient failures
- Difficult to diagnose partial extraction runs

**Status:** Fixed

**Resolution:**
Implemented comprehensive error handling system with three-tier approach:
- `cf_curl_with_retry()`: Core retry logic with exponential backoff (2s → 4s → 8s)
- `cf_curl_critical()`: For critical calls (org/space/app lookups) - exits on error
- `cf_curl_optional()`: For optional calls (env vars, domains, services) - warns and continues
- `classify_error()`: Distinguishes permanent (401/404) vs transient (network/5xx) errors

Updated 9 call sites to use appropriate error handling. Backward compatible - `cf_curl_safe()` still returns {} on error.

---

## ISSUE-004: Docker/Non-Buildpack Apps - Missing Lifecycle Metadata

**Description:**
Applications using Docker images or non-standard lifecycle types don't have buildpack metadata. The script attempts to extract buildpack information for all apps, resulting in empty/null values for Docker apps without proper identification or alternative metadata extraction.

**Affected Code:**
- Buildpack extraction logic
- Lines assuming all apps have `lifecycle.data.buildpacks`
- Lack of `lifecycle.type` checking before buildpack extraction

**Impact:**
- **Severity:** Medium
- Incomplete metadata for Docker-based applications
- Migration planning may incorrectly categorize Docker apps
- Missing alternative metadata (Docker image, registry, tags)
- No distinction between "no buildpack" and "Docker app"

**Status:** Open

---

## ISSUE-005: Base64 Decoding Platform Issues - macOS vs Linux Compatibility

**Description:**
The script uses `base64 -D` for decoding, which is the macOS syntax. Linux systems use `base64 -d` (lowercase). This causes buildpack metadata extraction to fail silently on Linux systems.

**Affected Code:**
- Line: `base64 -D` usage in buildpack extraction
- Platform detection logic (currently absent)

**Impact:**
- **Severity:** Medium
- Script fails on Linux environments
- Buildpack metadata completely missing on Linux runs
- No platform compatibility detection or warning
- Users on Linux get incomplete data without error messages

**Status:** Open

---

## ISSUE-006: Incomplete Security Group Extraction - Only Space-Level Groups

**Description:**
The script only extracts security groups at the space level. Cloud Foundry also has organization-level and global security groups that affect application connectivity but are not captured.

**Affected Code:**
- Security group extraction logic
- API calls limited to space-scoped security groups
- Missing calls to `/v3/security_groups` with org/global scope

**Impact:**
- **Severity:** Low to Medium
- Incomplete security posture information
- Migration planning may miss critical firewall rules
- Network connectivity issues may arise in target environment
- Compliance requirements may not be fully captured

**Status:** Open

---

## ISSUE-007: Environment Variable Exposure - Sensitive Data in CSV

**Description:**
The script extracts all environment variables (including system-provided and user-defined) and writes them to CSV files. This can expose sensitive information like API keys, passwords, database credentials, and secrets.

**Affected Code:**
- Environment variable extraction logic
- CSV output of `VCAP_SERVICES` and `VCAP_APPLICATION`
- Any lines writing env vars to files without sanitization

**Impact:**
- **Severity:** High (Security)
- Credentials and secrets written to CSV files
- CSV files may be shared, stored in git, or transmitted insecurely
- Potential violation of security policies and compliance requirements
- Risk of credential exposure to unauthorized users

**Status:** Open

---

## ISSUE-008: CSV Field Escaping - Malformed Output with Special Characters

**Description:**
CSV field values containing commas, quotes, newlines, or other special characters are not properly escaped according to RFC 4180. This results in malformed CSV files that break when parsed by Excel, CSV libraries, or other tools.

**Affected Code:**
- All `echo` statements writing CSV rows
- Fields containing JSON, descriptions, or free-text content
- Missing quote escaping and field enclosure logic

**Impact:**
- **Severity:** Medium
- CSV files cannot be reliably parsed
- Excel and other tools misalign columns
- Data import into databases fails
- Manual data cleanup required before use

**Status:** Fixed

**Resolution:**
Added `escape_csv()` function implementing RFC 4180 CSV escaping:
- Detects fields containing commas, quotes, newlines, or carriage returns
- Escapes internal quotes by doubling them (`"` → `""`)
- Encloses affected fields in double quotes
- Applied to all 14 string/text fields in CSV output
- Numeric fields (INSTANCES, MEM, DISK) not escaped for performance

CSV files now parse correctly in Excel, Python csv module, and database imports.

---

## Issue Summary

| ID | Title | Severity | Status |
|----|-------|----------|--------|
| ISSUE-001 | API Pagination | High | **Fixed** |
| ISSUE-002 | Empty/Null Data Handling | Medium | **Fixed** |
| ISSUE-003 | API Call Failures | High | **Fixed** |
| ISSUE-004 | Docker/Non-Buildpack Apps | Medium | Open |
| ISSUE-005 | Base64 Decoding Platform Issues | Medium | Open |
| ISSUE-006 | Incomplete Security Group Extraction | Low-Medium | Open |
| ISSUE-007 | Environment Variable Exposure | High (Security) | Open |
| ISSUE-008 | CSV Field Escaping | Medium | **Fixed** |

---

## Contributing

When addressing issues:
1. Reference the issue ID in commit messages (e.g., "Fix ISSUE-001: Add pagination support")
2. Update the issue status to "In Progress" when work begins
3. Update the issue status to "Fixed" and add resolution details when complete
4. Add test cases to prevent regression
