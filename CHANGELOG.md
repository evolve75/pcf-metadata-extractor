# Changelog

All notable changes to the PCF Metadata Extractor project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

**Status**: Open

The script currently uses `base64 -D` (macOS syntax) for decoding buildpack metadata. Linux systems require `base64 -d` (lowercase). This causes buildpack extraction to fail on Linux without platform detection.

**Workaround**: Run the script on macOS systems, or manually adjust the base64 flag before execution on Linux.

---

## Release Tags

- **R2.0.0**: Major refactoring and project cleanup (commit: 0e54f73)
- **R1.2.0**: Code quality improvements (commit: 8b042f0)
- **R1.1.0**: Feature-complete release (commit: bb851db)
- **R1.0.0**: Initial buildpack extraction (commit: 5e26ec7)
