# Changelog

All notable changes to the PCF Metadata Extractor project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

---

## [R2.1.1] - 2026-04-23

All changes in this section are since R2.1.0.

### Added
- **Actual resource usage extraction** for OpenShift migration planning
  - `Memory Usage(MB)` column: real-time memory consumption from running instances
  - `Disk Usage(MB)` column: real-time ephemeral disk usage per instance
  - `Total Disk Usage(MB)` column: pre-calculated total (Disk Usage × instances) for cluster capacity planning
  - Uses `/v3/processes/{guid}/stats` to read actual usage vs allocated quotas
  - Helps right-size OpenShift pod `ephemeral-storage` requests and limits; avoids summing per-instance values incorrectly
- **Volume service detection** for persistent storage requirements
  - `Volume Services` column: flags apps with persistent storage needs
  - `Volume Size(GB)` column: capacity for PVC-style planning
  - Detects volume-tagged user-provided services; maps to OpenShift PVC planning
- **GitHub Actions CI**: shell script validation on push/PR to `main` and `next`
  - `bash -n`, `shellcheck`, and `shellcheck --enable=all` (with the project’s expected filtering)
- **Hardening for large foundations**: graceful behavior when the stats API is unavailable (e.g. stopped apps), optional calls where data is non-critical, suitable for many hundreds of applications

### Changed
- **CSV schema (17 → 22 columns)**: new columns for memory and disk usage, total disk usage, and volume service fields; backward compatible for prior columns; `Total Disk Usage(MB)` is pre-calculated to avoid capacity planning mistakes
- **README.md**: OpenShift migration guidance, table layout, and structure
- **`.gitignore`**: ignore repository root `test-data/` (local test fixtures, not tracked)

### Fixed
- **Security groups API**: `CF-UnprocessableEntity` when using unsupported `organization_guids` / `space_guids` filters; align with CF v3 behavior and rely on global security groups where org/space scoping is not supported
- **`extract_org_guid`**: status output sent to stderr so `ORG_GUID` is a single clean GUID, fixing “max retries” and bad requests for org-scoped resources (including security groups)
- **API response handling**: first-load / mixed GUID-and-status responses from endpoints
- **ShellCheck SC2155** in `extract-pcf-inventory.sh` (no masked exit status in assignments)

### Removed
- `REFACTORING-ANALYSIS` (internal working document)

---

## [R2.1.0] - 2026-03-16

### Changed
- **Script renamed**: `pcfusage-v3.sh` → `extract-pcf-inventory.sh` for clarity (verb-noun naming convention)
- Script name references now use dynamic basename (`$SCRIPT_NAME`) instead of hardcoded values
- Updated README.md with new script name and improved CLI documentation

### Added
- Comprehensive CLI options documentation in README.md
- Multiple usage examples showing new flags (`-o`, `-d`, `-h`)

---

## [R2.0.0] - 2026-03-16

### Added
- Help flag (`-h`/`--help`) with comprehensive usage documentation
- CHANGELOG.md for tracking release history
- DRY utility functions for code reuse

### Changed
- **Major refactoring**: Comprehensive code restructuring in three phases
  - Phase 1: Added DRY utilities and reduced function complexity
  - Phase 2: Decomposed long functions into focused helpers
  - Phase 3 & 4: Null coalescing utilities and CLI improvements
- Migrated issue tracking from ISSUES.md to CHANGELOG.md

### Removed
- ISSUES.md (content migrated to CHANGELOG.md)

---

## [R1.2.0] - 2025-12-10

### Changed
- **Full shellcheck compliance**: Fixed all issues with `shellcheck --enable=all`
- Comprehensive style improvements across entire codebase
- Updated README.md to accurately reflect current script capabilities

---

## [R1.1.0] - 2025-12-09

### Added
- **API pagination support**: Automatically fetches all pages for large datasets (fixes incomplete data extraction)
- **Data validation system**: Detects empty/null responses with warning messages
- **Environment variable sanitization**: Protects credentials and secrets in CSV output with pattern-based redaction
- **Docker application support**: Extracts image and registry metadata for non-buildpack apps
- **Complete security group extraction**: Captures space-level, org-level, and global security groups
- `fetch_all_pages()` helper function for automatic CF v3 API pagination
- `validate_json_response()` helper for detecting empty API responses
- Data quality summary with warning count at completion
- Debug logging for redacted environment variables

### Fixed
- **API error handling**: Three-tier error handling with retry logic (exponential backoff)
  - `cf_curl_critical()` for required calls (exits on error)
  - `cf_curl_optional()` for optional calls (warns and continues)
  - `cf_curl_with_retry()` with transient error detection
- **CSV field escaping**: RFC 4180 compliant escaping for commas, quotes, and newlines
  - Added `escape_csv()` function applied to all text fields
  - Fixes parsing issues in Excel and CSV libraries

---

## [R1.0.0] - 2025-11-25

### Added
- Initial release of PCF Metadata Extractor using Cloud Foundry v3 API
- Buildpack extraction functionality for Cloud Foundry applications
- CSV output format for migration planning
- Basic organization, space, and application metadata extraction

---

## Known Limitations

### ISSUE-005: Base64 Decoding Platform Compatibility

**Status**: Fixed (R1.1.0+)

Platform detection for base64 decoding has been implemented via `util_base64_decode()` function. The script automatically uses the correct flag based on the operating system (`-D` for macOS, `-d` for Linux).

---

## Release Tags

- **R2.1.1**: OpenShift usage and volume columns, GHA, security group and parsing fixes, `test-data/` gitignore
- **R2.1.0**: Script renaming and documentation improvements (commit: 3fb6d3b)
- **R2.0.0**: Major refactoring and project cleanup (commit: 0e54f73)
- **R1.2.0**: Code quality improvements (commit: 8b042f0)
- **R1.1.0**: Feature-complete release (commit: bb851db)
- **R1.0.0**: Initial buildpack extraction (commit: 5e26ec7)
