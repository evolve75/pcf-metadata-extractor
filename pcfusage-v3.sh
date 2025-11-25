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

function cf_curl_safe() {
  local endpoint="$1"
  debug "Calling: cf curl ${endpoint}"
  cf curl "${endpoint}" 2>/dev/null || echo "{}"
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
ORG_GUID=$(cf_curl_safe "/v3/organizations?names=${ORG_NAME}" | jq -r '.resources[0].guid // empty')

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

SPACES_JSON=$(cf_curl_safe "/v3/spaces?organization_guids=${ORG_GUID}")
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
  APPS_JSON=$(cf_curl_safe "/v3/apps?space_guids=${SPACE_GUID}")
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
        DOMAIN_NAME=$(cf_curl_safe "/v3/domains/${DOMAIN_GUID}" | jq -r '.name // empty')
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
        SERVICE_INSTANCE_JSON=$(cf_curl_safe "/v3/service_instances/${SERVICE_INSTANCE_GUID}")
        SERVICE_INSTANCE_NAME=$(echo "$SERVICE_INSTANCE_JSON" | jq -r '.name // empty')
        SERVICE_INSTANCE_TYPE=$(echo "$SERVICE_INSTANCE_JSON" | jq -r '.type // empty')
        SERVICE_PLAN_GUID=$(echo "$SERVICE_INSTANCE_JSON" | jq -r '.relationships.service_plan.data.guid // empty')
        SERVICE_PLAN_NAME=""
        SERVICE_OFFERING_NAME=""
        if [ -n "$SERVICE_PLAN_GUID" ]; then
          SERVICE_PLAN_JSON=$(cf_curl_safe "/v3/service_plans/${SERVICE_PLAN_GUID}")
          SERVICE_PLAN_NAME=$(echo "$SERVICE_PLAN_JSON" | jq -r '.name // empty')
          SERVICE_OFFERING_GUID=$(echo "$SERVICE_PLAN_JSON" | jq -r '.relationships.service_offering.data.guid // empty')
          if [ -n "$SERVICE_OFFERING_GUID" ]; then
            SERVICE_OFFERING_NAME=$(cf_curl_safe "/v3/service_offerings/${SERVICE_OFFERING_GUID}" | jq -r '.name // empty')
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
    ENV_VARS=$(cf_curl_safe "/v3/apps/${APP_GUID}/env" | jq -r '
      (.environment_variables // {}) | to_entries |
      map("\(.key)=\(.value|tostring)") | join(";")')
    if [ "$ENV_VARS" == "null" ]; then
      ENV_VARS=""
    fi

    # Processes (memory/disk/instances)
    PROCESSES_JSON=$(cf_curl_safe "/v3/processes?app_guids=${APP_GUID}")
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
