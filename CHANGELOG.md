# Changelog

All notable changes to the PCF Metadata Extractor project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- **GitHub Actions CI/CD**: Automated shell script validation workflow
  - Syntax validation (`bash -n`) for all shell scripts
  - Standard shellcheck validation
  - Comprehensive shellcheck (`--enable=all`) with error/warning filtering
  - Triggers on push/PR to `main` and `next` branches

### Changed
- Updated CHANGELOG.md with R2.1.0 commit hash reference

### Fixed
- **stdout/stderr redirection in extract_org_guid**: Corrected output redirection to prevent API call failures
  - Status message now properly redirected to stderr (`>&2`) on line 748
  - Fixes issue where `ORG_GUID` variable captured multi-line output including status messages
  - Resolves "Max retries exceeded" errors when fetching organization-scoped resources (security groups, etc.)
  - API endpoints now receive clean GUID values instead of contaminated multi-line strings

### Removed
- REFACTORING-ANALYSIS file (internal working document)

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

- **R2.1.0**: Script renaming and documentation improvements (commit: 3fb6d3b)
- **R2.0.0**: Major refactoring and project cleanup (commit: 0e54f73)
- **R1.2.0**: Code quality improvements (commit: 8b042f0)
- **R1.1.0**: Feature-complete release (commit: bb851db)
- **R1.0.0**: Initial buildpack extraction (commit: 5e26ec7)
