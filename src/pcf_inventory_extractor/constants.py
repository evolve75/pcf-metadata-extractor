"""Configuration constants (ported from extract-pcf-inventory.sh)."""

# When False, TLS certificate verification is disabled for all HTTP(S) calls to
# Cloud Controller and UAA (insecure; suitable for private CA / lab environments).
CONFIG_HTTPS_VERIFY = False

CONFIG_API_MAX_RETRIES = 3
CONFIG_API_MAX_RETRIES_OPTIONAL = 2
CONFIG_API_INITIAL_BACKOFF = 2.0
CONFIG_CSV_DELIMITER = ","
CONFIG_CSV_MULTIVALUE_SEP = ";"
CONFIG_CSV_TIMESTAMP_FORMAT = "%Y%m%d%H%M%S"
CONFIG_OUTPUT_PREFIX = "pcfusage"
CONFIG_REDACTION_PLACEHOLDER = "<REDACTED>"

CONFIG_SENSITIVE_PATTERNS: tuple[str, ...] = (
    "PASSWORD", "PASSWD", "PWD", "SECRET", "PRIVATE", "KEY",
    "APIKEY", "TOKEN", "AUTH", "CREDENTIAL", "CERT",
    "CERTIFICATE", "DATABASE_URL", "DB_URL", "JDBC_URL", "URI",
)

CONFIG_CSV_COLUMNS: tuple[str, ...] = (
    "Org", "Space", "App", "Process Type", "Instances",
    "Memory(MB)", "Disk(MB)", "Memory Usage(MB)", "Disk Usage(MB)", "Total Disk Usage(MB)",
    "State", "Buildpacks", "Buildpack Details", "Runtime Version", "Routes",
    "Domains", "Service Instances", "Service Bindings", "Volume Services", "Volume Size(GB)",
    "Env Vars", "Security Groups",
)
