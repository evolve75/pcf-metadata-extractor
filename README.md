# Cloud Foundry Application Metadata Extractor (v3 API)

`pcfusage-v3.sh` collects comprehensive Cloud Foundry org, space, app, and process metadata using the **v3 API**.
It produces detailed CSV reports for auditing, reporting, and migration analysis (e.g., CF → OpenShift).

## Features
- **v3 API Support:** Works on foundations with v2 API disabled
- **Comprehensive Metadata:** Org, space, app, processes, buildpacks, routes, domains, services, security groups
- **Docker Support:** Extracts Docker image and registry information for containerized apps
- **Security:** Sanitizes sensitive environment variables (passwords, tokens, secrets, keys)
- **Robust Error Handling:** Retry logic with exponential backoff for transient failures
- **Pagination:** Automatically handles large datasets (>50 items per page)
- **Security Groups:** Captures org-level, space-level, and global security group assignments
- **RFC 4180 CSV:** Proper CSV escaping for special characters (commas, quotes, newlines)
- **Data Quality Tracking:** Reports warnings for incomplete data
- **Debug Mode:** Optional `--debug` flag for verbose diagnostic output  

## Requirements
- Logged into Cloud Foundry (`cf login`)  
- `cf` CLI and `jq` installed  

## Usage
```bash
chmod +x pcfusage-v3.sh
./pcfusage-v3.sh <org_name> [--debug]
```

Example:
```bash
./pcfusage-v3.sh abc-company
```

## Output
Generates a timestamped CSV file such as:
```
pcfusage_abc-company_20260316143022.csv
```

### CSV Columns
The report includes the following columns:
- **Org** - Organization name
- **Space** - Space name
- **App** - Application name
- **Process Type** - Process type (web, worker, etc.)
- **Instances** - Number of instances
- **Memory(MB)** - Memory allocation in MB
- **Disk(MB)** - Disk allocation in MB
- **State** - Application state (STARTED, STOPPED)
- **Buildpacks** - Buildpack names or Docker image
- **Buildpack Details** - Buildpack versions or Docker registry
- **Runtime Version** - Runtime version (Java, Node.js, etc.)
- **Routes** - Application routes (URLs)
- **Domains** - Associated domains
- **Service Instances** - Bound service instances with plan details
- **Service Bindings** - Service binding names
- **Env Vars** - Environment variables (sensitive values redacted)
- **Security Groups** - Space, org, and global security groups

### Sample Output
```csv
Org,Space,App,Process Type,Instances,Memory(MB),Disk(MB),State,Buildpacks,Buildpack Details,Runtime Version,Routes,Domains,Service Instances,Service Bindings,Env Vars,Security Groups
abc-company,production,api-service,web,3,1024,2048,STARTED,java_buildpack,java_buildpack 4.45,11,api.example.com,example.com,mysql [cleardb/spark (managed)],mysql-binding,DATABASE_URL=<REDACTED>,space:app-sg;global-running:public_networks
abc-company,production,nginx,web,1,512,512,STARTED,nginx:1.21.0,registry:docker.io,,nginx.example.com,example.com,,,NGINX_WORKER_PROCESSES=4,global-running:public_networks
```

## Common Uses
- **Migration Planning:** Complete inventory for CF → OpenShift/Kubernetes migrations
- **Resource Auditing:** Memory, disk, and instance usage across org
- **Buildpack Analysis:** Identify buildpack versions and upgrade candidates
- **Security Review:** Audit security group assignments and environment variable usage
- **Service Mapping:** Document service dependencies and bindings
- **Docker Adoption:** Identify containerized vs buildpack-based applications
- **Compliance Reporting:** Extract configuration data for compliance reviews


