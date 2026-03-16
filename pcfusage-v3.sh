#!/bin/bash
# ---------------------------------------------------------------------------
# Cloud Foundry Application Usage Reporter (v3 API)
# Gathers org/space/app/process metadata using CF v3 API
# Usage:
#   ./pcfusage-v3.sh <org_name> [--debug]
# ---------------------------------------------------------------------------

set -euo pipefail

ORG_NAME="${1:-}"
DEBUG="${2:-}"

if [ -z "$ORG_NAME" ]; then
  echo "Usage: $0 <org_name> [--debug]"
  exit 1
fi

if [ "$DEBUG" == "--debug" ]; then
  echo "🔍 Debug mode enabled"
fi

OUTFILE="pcfusage_${ORG_NAME}_$(date +%Y%m%d%H%M%S).csv"
echo "Org,Space,App,Process Type,Instances,Memory(MB),Disk(MB),State,Buildpacks,Buildpack Details,Runtime Version,Routes,Domains,Service Instances,Service Bindings,Env Vars,Security Groups" > "$OUTFILE"

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

function debug() {
  if [ "$DEBUG" == "--debug" ]; then
    echo "DEBUG: $*" >&2
  fi
}

# ---------------------------------------------------------------------------
# Error classification helper
# Distinguishes between permanent errors (don't retry) and transient (retry)
# ---------------------------------------------------------------------------
function classify_error() {
  local response="$1"
  local error_msg="$2"
  local exit_code="$3"

  # Check JSON for CF API error codes
  if echo "$response" | jq -e '.errors' >/dev/null 2>&1; then
    local error_code=$(echo "$response" | jq -r '.errors[0].code // empty')
    case "$error_code" in
      10002|10003) echo "auth_error" ;;      # Unauthorized/Forbidden
      10004|10010) echo "not_found" ;;       # Not found
      1000|10008)  echo "client_error" ;;    # Bad request/Validation
      *) echo "server_error" ;;              # Other API errors, retry-eligible
    esac
    return
  fi

  # Check stderr for network/connection errors
  if echo "$error_msg" | grep -qi "connection refused\|timeout\|network\|DNS"; then
    echo "network_error"
  elif echo "$error_msg" | grep -qi "unauthorized\|401\|403"; then
    echo "auth_error"
  elif echo "$error_msg" | grep -qi "not found\|404"; then
    echo "not_found"
  elif echo "$error_msg" | grep -qi "50[0-9]\|bad gateway\|service unavailable"; then
    echo "server_error"
  else
    echo "server_error"  # Default to retry-eligible for safety
  fi
}

# ---------------------------------------------------------------------------
# Core retry function with exponential backoff
# Returns: JSON on success, __ERROR_PERMANENT__ or __ERROR_TRANSIENT__ on failure
# ---------------------------------------------------------------------------
function cf_curl_with_retry() {
  local endpoint="$1"
  local max_retries="${2:-3}"
  local attempt=0
  local backoff=2

  while [ $attempt -le $max_retries ]; do
    local tmpfile_out=$(mktemp)
    local tmpfile_err=$(mktemp)
    local exit_code=0

    debug "API call attempt $((attempt+1))/$((max_retries+1)): cf curl ${endpoint}"
    cf curl "${endpoint}" > "$tmpfile_out" 2> "$tmpfile_err" || exit_code=$?

    local response=$(cat "$tmpfile_out")
    local error_msg=$(cat "$tmpfile_err")
    rm -f "$tmpfile_out" "$tmpfile_err"

    # Success: valid JSON without errors field
    if [ $exit_code -eq 0 ] && echo "$response" | jq -e 'has("errors") | not' >/dev/null 2>&1; then
      echo "$response"
      return 0
    fi

    # Classify error type
    local error_type=$(classify_error "$response" "$error_msg" "$exit_code")

    case "$error_type" in
      "auth_error"|"not_found"|"client_error")
        # Permanent errors - don't retry
        echo "ERROR: Permanent error calling ${endpoint}: ${error_msg}" >&2
        if [ -n "$response" ] && echo "$response" | jq -e '.errors' >/dev/null 2>&1; then
          echo "$response" | jq -r '.errors[]? | "  \(.title // .detail // .code)"' >&2
        fi
        echo "__ERROR_PERMANENT__"
        return 2
        ;;
      "network_error"|"server_error")
        # Transient errors - retry with backoff
        if [ $attempt -lt $max_retries ]; then
          echo "WARNING: Transient error (attempt $((attempt+1))/$((max_retries+1))): ${error_msg}" >&2
          sleep $backoff
          backoff=$((backoff * 2))
        else
          echo "ERROR: Max retries exceeded for ${endpoint}" >&2
          echo "__ERROR_TRANSIENT__"
          return 1
        fi
        ;;
    esac
    attempt=$((attempt + 1))
  done

  echo "__ERROR_TRANSIENT__"
  return 1
}

# ---------------------------------------------------------------------------
# High-level wrapper: Critical call - exits script on error
# ---------------------------------------------------------------------------
function cf_curl_critical() {
  local endpoint="$1"
  local context="${2:-API call}"
  local result=$(cf_curl_with_retry "$endpoint" 3)

  if [[ "$result" == "__ERROR_"* ]]; then
    echo "❌ Critical error: ${context} failed" >&2
    echo "   Endpoint: ${endpoint}" >&2
    exit 1
  fi
  echo "$result"
}

# ---------------------------------------------------------------------------
# High-level wrapper: Optional call - logs warning and continues
# ---------------------------------------------------------------------------
function cf_curl_optional() {
  local endpoint="$1"
  local context="${2:-Optional data}"
  local result=$(cf_curl_with_retry "$endpoint" 2)  # Fewer retries for optional

  if [[ "$result" == "__ERROR_"* ]]; then
    echo "⚠️  Warning: ${context} unavailable (${endpoint})" >&2
    echo "{}"
    return 0
  fi
  echo "$result"
}

# ---------------------------------------------------------------------------
# High-level wrapper: Safe call - backward compatible, returns {} on error
# ---------------------------------------------------------------------------
function cf_curl_safe() {
  local endpoint="$1"
  local result=$(cf_curl_with_retry "$endpoint" 3)

  if [[ "$result" == "__ERROR_"* ]]; then
    echo "{}"
    return 0
  fi
  echo "$result"
}

# ---------------------------------------------------------------------------
# Environment checks
# ---------------------------------------------------------------------------

for cmd in cf jq; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "❌ $cmd not found in PATH"; exit 1; }
done

if ! cf target >/dev/null 2>&1; then
  echo "❌ Not logged in to Cloud Foundry. Run 'cf login' first."
  exit 1
fi

# ---------------------------------------------------------------------------
# Get Org GUID
# ---------------------------------------------------------------------------

debug "Fetching org GUID for ${ORG_NAME}"
ORG_GUID=$(cf_curl_critical "/v3/organizations?names=${ORG_NAME}" \
           "Organization '${ORG_NAME}' lookup" | jq -r '.resources[0].guid // empty')

if [ -z "$ORG_GUID" ]; then
  echo "❌ Organization '${ORG_NAME}' not found."
  echo "Available orgs:"
  cf curl /v3/organizations | jq -r '.resources[].name'
  exit 1
fi
echo "✅ Organization: ${ORG_NAME} (${ORG_GUID})"

# ---------------------------------------------------------------------------
# List Spaces in Org
# ---------------------------------------------------------------------------

SPACES_JSON=$(cf_curl_critical "/v3/spaces?organization_guids=${ORG_GUID}" \
              "Spaces listing for org '${ORG_NAME}'")
SPACE_COUNT=$(echo "$SPACES_JSON" | jq -r '.pagination.total_results // 0')
echo "📦 Found ${SPACE_COUNT} space(s) in org '${ORG_NAME}'"

if [ "$SPACE_COUNT" -eq 0 ]; then
  echo "⚠️ No spaces found in org '${ORG_NAME}'"
  exit 0
fi

for SPACE_GUID in $(echo "$SPACES_JSON" | jq -r '.resources[].guid'); do
  SPACE_NAME=$(echo "$SPACES_JSON" | jq -r --arg guid "$SPACE_GUID" '.resources[] | select(.guid==$guid) | .name')
  echo "➡️  Processing space: ${SPACE_NAME} (${SPACE_GUID})"
  SPACE_SECURITY_GROUPS=$(cf_curl_safe "/v3/security_groups?space_guids=${SPACE_GUID}" \
    | jq -r '[(.resources // [])[]?.name // empty] | map(select(length>0)) | join(";")')
  if [ "$SPACE_SECURITY_GROUPS" == "null" ]; then
    SPACE_SECURITY_GROUPS=""
  fi

  # -------------------------------------------------------------------------
  # List Apps in Space
  # -------------------------------------------------------------------------
  APPS_JSON=$(cf_curl_critical "/v3/apps?space_guids=${SPACE_GUID}" \
              "Apps listing for space '${SPACE_NAME}'")
  APP_COUNT=$(echo "$APPS_JSON" | jq -r '.pagination.total_results // 0')

  if [ "$APP_COUNT" -eq 0 ]; then
    echo "   ⚠️  No apps found in space '${SPACE_NAME}'"
    continue
  fi
  echo "   📱 Found ${APP_COUNT} app(s) in space '${SPACE_NAME}'"

  for APP_GUID in $(echo "$APPS_JSON" | jq -r '.resources[]?.guid'); do
    APP_NAME=$(echo "$APPS_JSON" | jq -r --arg guid "$APP_GUID" '.resources[] | select(.guid==$guid) | .name')
    APP_STATE=$(echo "$APPS_JSON" | jq -r --arg guid "$APP_GUID" '.resources[] | select(.guid==$guid) | .state')

    # Buildpacks
    APP_DETAILS=$(cf_curl_safe "/v3/apps/${APP_GUID}")
    LIFECYCLE_TYPE=$(echo "$APP_DETAILS" | jq -r '.lifecycle.type // empty')
    BUILDPACKS=""
    BUILDPACK_DETAILS=""
    RUNTIME_VERSION=""

    if [ "$LIFECYCLE_TYPE" == "buildpack" ]; then
      CURRENT_DROPLET_GUID=$(cf_curl_safe "/v3/apps/${APP_GUID}/relationships/current_droplet" | jq -r '.data.guid // empty')
      if [ -n "$CURRENT_DROPLET_GUID" ]; then
        DROPLET_JSON=$(cf_curl_safe "/v3/droplets/${CURRENT_DROPLET_GUID}")
        BUILDPACKS=$(echo "$DROPLET_JSON" | jq -r '[.buildpacks[]?.name] // [] | map(select(length>0)) | join(";")')
        BUILDPACK_DETAILS=$(echo "$DROPLET_JSON" | jq -r '
          [.buildpacks[]? | [.name, (.version // ""), (.detect_output // "")]
           | map(select(length>0)) | join(" ")] | map(select(length>0)) | join(";")')
        RUNTIME_VERSION=$(echo "$DROPLET_JSON" | jq -r '
          (.environment_variables // {}) as $env |
          $env.BP_JVM_VERSION // $env.BP_JAVA_VERSION // $env.JAVA_VERSION // empty')
      fi
    fi

    if [ -z "$BUILDPACKS" ] || [ "$BUILDPACKS" == "null" ]; then
      BUILDPACKS=$(echo "$APP_DETAILS" | jq -r '.lifecycle.data.buildpacks // [] | map(select(length>0)) | join(";")')
    fi
    if [ "$BUILDPACK_DETAILS" == "null" ]; then
      BUILDPACK_DETAILS=""
    fi
    if [ "$RUNTIME_VERSION" == "null" ]; then
      RUNTIME_VERSION=""
    fi

    # Routes & domains
    ROUTES_JSON=$(cf_curl_safe "/v3/routes?app_guids=${APP_GUID}")
    ROUTES=$(echo "$ROUTES_JSON" | jq -r '[(.resources // [])[]?.url // empty] | map(select(length>0)) | join(";")')
    if [ "$ROUTES" == "null" ]; then
      ROUTES=""
    fi
    DOMAINS=""
    DOMAIN_GUIDS=$(echo "$ROUTES_JSON" | jq -r '(.resources // [])[]?.relationships.domain.data.guid | select(length>0)')
    if [ -n "$DOMAIN_GUIDS" ]; then
      while read -r DOMAIN_GUID; do
        [ -z "$DOMAIN_GUID" ] && continue
        DOMAIN_NAME=$(cf_curl_optional "/v3/domains/${DOMAIN_GUID}" \
                      "Domain ${DOMAIN_GUID}" | jq -r '.name // empty')
        if [ -n "$DOMAIN_NAME" ]; then
          if [ -n "$DOMAINS" ]; then
            DOMAINS="${DOMAINS};${DOMAIN_NAME}"
          else
            DOMAINS="$DOMAIN_NAME"
          fi
        fi
      done < <(printf "%s\n" "$DOMAIN_GUIDS" | sort -u)
    fi

    # Services & bindings
    SERVICE_BINDINGS_JSON=$(cf_curl_safe "/v3/service_credential_bindings?app_guids=${APP_GUID}")
    SERVICE_BINDINGS=$(echo "$SERVICE_BINDINGS_JSON" | jq -r '[(.resources // [])[]?.name // empty] | map(select(length>0)) | join(";")')
    if [ "$SERVICE_BINDINGS" == "null" ]; then
      SERVICE_BINDINGS=""
    fi
    SERVICE_INSTANCES=""
    SERVICE_INSTANCE_GUIDS=$(echo "$SERVICE_BINDINGS_JSON" | jq -r '(.resources // [])[]?.relationships.service_instance.data.guid | select(length>0)')
    if [ -n "$SERVICE_INSTANCE_GUIDS" ]; then
      while read -r SERVICE_INSTANCE_GUID; do
        [ -z "$SERVICE_INSTANCE_GUID" ] && continue
        SERVICE_INSTANCE_JSON=$(cf_curl_optional \
          "/v3/service_instances/${SERVICE_INSTANCE_GUID}" \
          "Service instance ${SERVICE_INSTANCE_GUID}")
        SERVICE_INSTANCE_NAME=$(echo "$SERVICE_INSTANCE_JSON" | jq -r '.name // empty')
        SERVICE_INSTANCE_TYPE=$(echo "$SERVICE_INSTANCE_JSON" | jq -r '.type // empty')
        SERVICE_PLAN_GUID=$(echo "$SERVICE_INSTANCE_JSON" | jq -r '.relationships.service_plan.data.guid // empty')
        SERVICE_PLAN_NAME=""
        SERVICE_OFFERING_NAME=""
        if [ -n "$SERVICE_PLAN_GUID" ]; then
          SERVICE_PLAN_JSON=$(cf_curl_optional "/v3/service_plans/${SERVICE_PLAN_GUID}" \
                            "Service plan ${SERVICE_PLAN_GUID}")
          SERVICE_PLAN_NAME=$(echo "$SERVICE_PLAN_JSON" | jq -r '.name // empty')
          SERVICE_OFFERING_GUID=$(echo "$SERVICE_PLAN_JSON" | jq -r '.relationships.service_offering.data.guid // empty')
          if [ -n "$SERVICE_OFFERING_GUID" ]; then
            SERVICE_OFFERING_NAME=$(cf_curl_optional \
              "/v3/service_offerings/${SERVICE_OFFERING_GUID}" \
              "Service offering" | jq -r '.name // empty')
          fi
        fi
        ENTRY="$SERVICE_INSTANCE_NAME"
        if [ -z "$ENTRY" ]; then
          ENTRY="$SERVICE_INSTANCE_GUID"
        fi
        DETAILS=""
        if [ -n "$SERVICE_OFFERING_NAME" ]; then
          DETAILS="$SERVICE_OFFERING_NAME"
        fi
        if [ -n "$SERVICE_PLAN_NAME" ]; then
          if [ -n "$DETAILS" ]; then
            DETAILS="${DETAILS}/${SERVICE_PLAN_NAME}"
          else
            DETAILS="$SERVICE_PLAN_NAME"
          fi
        fi
        if [ -n "$SERVICE_INSTANCE_TYPE" ]; then
          if [ -n "$DETAILS" ]; then
            DETAILS="${DETAILS} (${SERVICE_INSTANCE_TYPE})"
          else
            DETAILS="$SERVICE_INSTANCE_TYPE"
          fi
        fi
        if [ -n "$DETAILS" ]; then
          ENTRY="${ENTRY} [${DETAILS}]"
        fi
        if [ -n "$SERVICE_INSTANCES" ]; then
          SERVICE_INSTANCES="${SERVICE_INSTANCES};${ENTRY}"
        else
          SERVICE_INSTANCES="$ENTRY"
        fi
      done < <(printf "%s\n" "$SERVICE_INSTANCE_GUIDS" | sort -u)
    fi

    # Environment variables (user-provided)
    ENV_VARS=$(cf_curl_optional "/v3/apps/${APP_GUID}/env" \
               "Environment variables for ${APP_NAME}" | jq -r '
      (.environment_variables // {}) | to_entries |
      map("\(.key)=\(.value|tostring)") | join(";")')
    if [ "$ENV_VARS" == "null" ]; then
      ENV_VARS=""
    fi

    # Processes (memory/disk/instances)
    PROCESSES_JSON=$(cf_curl_critical "/v3/processes?app_guids=${APP_GUID}" \
                     "Processes for app '${APP_NAME}'")
    PROC_COUNT=$(echo "$PROCESSES_JSON" | jq -r '.pagination.total_results // 0')

    if [ "$PROC_COUNT" -eq 0 ]; then
      echo "      ⚠️  No processes for app '${APP_NAME}'"
      continue
    fi

    for row in $(echo "$PROCESSES_JSON" | jq -r '.resources[]? | @base64'); do
      _jq() { echo "$row" | base64 --decode | jq -r "$1"; }
      TYPE=$(_jq '.type')
      INSTANCES=$(_jq '.instances')
      MEM=$(_jq '.memory_in_mb')
      DISK=$(_jq '.disk_in_mb')
      echo "${ORG_NAME},${SPACE_NAME},${APP_NAME},${TYPE},${INSTANCES},${MEM},${DISK},${APP_STATE},${BUILDPACKS},${BUILDPACK_DETAILS},${RUNTIME_VERSION},${ROUTES},${DOMAINS},${SERVICE_INSTANCES},${SERVICE_BINDINGS},${ENV_VARS},${SPACE_SECURITY_GROUPS}" >> "$OUTFILE"
    done
  done
done

echo
echo "✅ Report generated: ${OUTFILE}"
if [ "$DEBUG" == "--debug" ]; then
  echo "🔍 CSV preview:"
  head -n 10 "$OUTFILE"
fi
