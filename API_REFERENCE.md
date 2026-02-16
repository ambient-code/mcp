# ACP MCP Server - API Reference

Complete reference for all 26 tools available in the ACP MCP Server.

---

## Table of Contents

1. [Session Management](#session-management)
   - [acp_list_sessions](#acp_list_sessions)
   - [acp_get_session](#acp_get_session)
   - [acp_create_session](#acp_create_session)
   - [acp_create_session_from_template](#acp_create_session_from_template)
   - [acp_delete_session](#acp_delete_session)
   - [acp_restart_session](#acp_restart_session)
   - [acp_clone_session](#acp_clone_session)
   - [acp_update_session](#acp_update_session)

2. [Observability](#observability)
   - [acp_get_session_logs](#acp_get_session_logs)
   - [acp_get_session_transcript](#acp_get_session_transcript)
   - [acp_get_session_metrics](#acp_get_session_metrics)

3. [Labels](#labels)
   - [acp_label_resource](#acp_label_resource)
   - [acp_unlabel_resource](#acp_unlabel_resource)
   - [acp_list_sessions_by_label](#acp_list_sessions_by_label)
   - [acp_bulk_label_resources](#acp_bulk_label_resources)
   - [acp_bulk_unlabel_resources](#acp_bulk_unlabel_resources)

4. [Bulk Operations](#bulk-operations)
   - [acp_bulk_delete_sessions](#acp_bulk_delete_sessions)
   - [acp_bulk_stop_sessions](#acp_bulk_stop_sessions)
   - [acp_bulk_restart_sessions](#acp_bulk_restart_sessions)
   - [acp_bulk_delete_sessions_by_label](#acp_bulk_delete_sessions_by_label)
   - [acp_bulk_stop_sessions_by_label](#acp_bulk_stop_sessions_by_label)
   - [acp_bulk_restart_sessions_by_label](#acp_bulk_restart_sessions_by_label)

5. [Cluster Management](#cluster-management)
   - [acp_list_clusters](#acp_list_clusters)
   - [acp_whoami](#acp_whoami)
   - [acp_switch_cluster](#acp_switch_cluster)
   - [acp_login](#acp_login)

---

## Session Management

### acp_list_sessions

List sessions with advanced filtering, sorting, and limiting.

**Input Schema:**
```json
{
  "project": "string (optional, uses default if not provided)",
  "status": "string (optional) - running|stopped|creating|failed",
  "older_than": "string (optional) - e.g., '7d', '24h', '30m'",
  "sort_by": "string (optional) - created|stopped|name",
  "limit": "integer (optional, minimum: 1)"
}
```

**Output:**
```json
{
  "sessions": [
    {
      "id": "session-1",
      "status": "running",
      "createdAt": "2026-01-29T10:00:00Z"
    }
  ],
  "total": 10,
  "filters_applied": {"status": "running", "limit": 10}
}
```

**Behavior:**
- Calls `GET /v1/sessions` on the public-api gateway
- Builds filter predicates based on parameters
- Single-pass filtering: `all(f(s) for f in filters)`
- Sorts results if `sort_by` specified (reverse for created/stopped, normal for name)
- Applies limit after filtering and sorting

---

### acp_get_session

Get details of a specific session by ID.

**Input Schema:**
```json
{
  "project": "string (optional, uses default if not provided)",
  "session": "string (required) - Session ID"
}
```

**Output:**
```json
{
  "id": "session-1",
  "status": "running",
  "displayName": "My Session",
  "createdAt": "2026-01-29T10:00:00Z"
}
```

**Behavior:**
- Calls `GET /v1/sessions/{session}` on the public-api gateway
- Validates session name (DNS-1123 format)

---

### acp_create_session

Create an ACP AgenticSession with a custom prompt.

**Input Schema:**
```json
{
  "project": "string (optional, uses default if not provided)",
  "initial_prompt": "string (required) - The prompt/instructions for the session",
  "display_name": "string (optional) - Human-readable display name",
  "repos": "array[string] (optional) - Repository URLs to clone",
  "interactive": "boolean (optional, default: false)",
  "model": "string (optional, default: 'claude-sonnet-4')",
  "timeout": "integer (optional, default: 900, minimum: 60) - seconds",
  "dry_run": "boolean (optional, default: false)"
}
```

**Output:**
```json
{
  "created": true,
  "session": "compiled-abc12",
  "project": "my-workspace",
  "message": "Session 'compiled-abc12' created in project 'my-workspace'"
}
```

**Dry-Run Output:**
```json
{
  "dry_run": true,
  "success": true,
  "message": "Would create session with custom prompt",
  "manifest": {
    "initialPrompt": "...",
    "interactive": false,
    "llmConfig": {"model": "claude-sonnet-4"},
    "timeout": 900
  },
  "project": "my-workspace"
}
```

**Behavior:**
- Validates project name (DNS-1123 format)
- If dry_run: Returns the manifest without calling the API
- Calls `POST /v1/sessions` on the public-api gateway

---

### acp_delete_session

Delete a session with optional dry-run.

**Input Schema:**
```json
{
  "project": "string (optional, uses default if not provided)",
  "session": "string (required)",
  "dry_run": "boolean (optional, default: false)"
}
```

**Output:**
```json
{
  "deleted": true,
  "message": "Successfully deleted session 'foo' from project 'bar'"
}
```

**Dry-Run Output:**
```json
{
  "dry_run": true,
  "success": true,
  "message": "Would delete session 'foo' in project 'bar'",
  "session_info": {
    "name": "foo",
    "status": "running",
    "created": "2026-01-29T10:00:00Z"
  }
}
```

**Behavior:**
- If dry_run: Calls `GET /v1/sessions/{session}` to verify existence
- If not dry_run: Calls `DELETE /v1/sessions/{session}`

---

### acp_create_session_from_template

Create a session from a predefined template with optimized settings.

**Input Schema:**
```json
{
  "project": "string (optional, uses default if not provided)",
  "template": "string (required) - triage|bugfix|feature|exploration",
  "display_name": "string (required) - Display name for the session",
  "repos": "array[string] (optional) - Repository URLs to clone",
  "dry_run": "boolean (optional, default: false)"
}
```

**Output:**
```json
{
  "created": true,
  "session": "compiled-abc12",
  "project": "my-workspace",
  "template": "bugfix",
  "message": "Session 'compiled-abc12' created from template 'bugfix'"
}
```

**Behavior:**
- Available templates: `triage` (temp 0.7), `bugfix` (temp 0.3), `feature` (temp 0.5), `exploration` (temp 0.8)
- Each template sets workflow type, model, and temperature
- Calls `POST /v1/sessions` on the public-api gateway

---

### acp_restart_session

Restart a stopped session.

**Input Schema:**
```json
{
  "project": "string (optional, uses default if not provided)",
  "session": "string (required)",
  "dry_run": "boolean (optional, default: false)"
}
```

**Output:**
```json
{
  "restarted": true,
  "message": "Successfully restarted session 'my-session'"
}
```

**Behavior:**
- Calls `PATCH /v1/sessions/{session}` with `{"stopped": false}`
- If dry_run: Calls `GET /v1/sessions/{session}` to verify existence
- Validates session name (DNS-1123 format)

---

### acp_clone_session

Clone an existing session's configuration into a new session.

**Input Schema:**
```json
{
  "project": "string (optional, uses default if not provided)",
  "source_session": "string (required) - Session ID to clone from",
  "new_display_name": "string (required) - Display name for the cloned session",
  "dry_run": "boolean (optional, default: false)"
}
```

**Output:**
```json
{
  "created": true,
  "session": "compiled-xyz99",
  "source_session": "compiled-abc12",
  "project": "my-workspace",
  "message": "Session 'compiled-xyz99' cloned from 'compiled-abc12'"
}
```

**Behavior:**
- Fetches source session configuration via `GET /v1/sessions/{source_session}`
- Copies prompt, interactive flag, timeout, llmConfig, and repos
- Creates new session via `POST /v1/sessions`

---

### acp_update_session

Update session metadata (display name, timeout).

**Input Schema:**
```json
{
  "project": "string (optional, uses default if not provided)",
  "session": "string (required)",
  "display_name": "string (optional) - New display name",
  "timeout": "integer (optional, minimum: 60) - New timeout in seconds",
  "dry_run": "boolean (optional, default: false)"
}
```

**Output:**
```json
{
  "updated": true,
  "message": "Successfully updated session 'my-session'",
  "session": { "id": "my-session", "displayName": "New Name", "timeout": 1800 }
}
```

**Behavior:**
- At least one of `display_name` or `timeout` must be provided
- Calls `PATCH /v1/sessions/{session}` with the patch data
- If dry_run: Shows current state and proposed patch

---

## Observability

### acp_get_session_logs

Retrieve container logs for a session.

**Input Schema:**
```json
{
  "project": "string (optional, uses default if not provided)",
  "session": "string (required)",
  "container": "string (optional) - Container name",
  "tail_lines": "integer (optional, default: 1000, max: 10000)"
}
```

**Output:**
```json
{
  "logs": "2026-01-29T10:00:00Z Starting session...\n2026-01-29T10:00:01Z Running prompt...",
  "session": "my-session",
  "tail_lines": 1000
}
```

**Behavior:**
- Calls `GET /v1/sessions/{session}/logs` with `tailLines` query parameter
- Returns plain text logs from the session container
- Optionally filter by container name

---

### acp_get_session_transcript

Retrieve conversation history for a session.

**Input Schema:**
```json
{
  "project": "string (optional, uses default if not provided)",
  "session": "string (required)",
  "format": "string (optional, default: 'json') - json|markdown"
}
```

**Output (JSON format):**
```json
{
  "messages": [
    {"role": "user", "content": "Run unit tests"},
    {"role": "assistant", "content": "Running pytest..."}
  ],
  "session": "my-session",
  "format": "json"
}
```

**Behavior:**
- Calls `GET /v1/sessions/{session}/transcript` with `format` query parameter
- JSON format returns structured message objects
- Markdown format returns rendered conversation text

---

### acp_get_session_metrics

Get usage statistics for a session (tokens, duration, tool calls).

**Input Schema:**
```json
{
  "project": "string (optional, uses default if not provided)",
  "session": "string (required)"
}
```

**Output:**
```json
{
  "session": "my-session",
  "total_tokens": 15420,
  "input_tokens": 8200,
  "output_tokens": 7220,
  "duration_seconds": 342,
  "tool_calls": 12
}
```

**Behavior:**
- Calls `GET /v1/sessions/{session}/metrics`
- Returns all available usage statistics from the API

---

## Labels

### acp_label_resource

Add labels to a session. Labels are key-value pairs for organizing and filtering.

**Input Schema:**
```json
{
  "project": "string (optional, uses default if not provided)",
  "name": "string (required) - Session name",
  "resource_type": "string (optional, default: 'agenticsession')",
  "labels": "object (required) - Labels as key-value pairs, e.g. {\"env\": \"test\"}"
}
```

**Output:**
```json
{
  "labeled": true,
  "session": "my-session",
  "labels_added": {"env": "test", "team": "platform"},
  "message": "Added 2 label(s) to session 'my-session'"
}
```

**Behavior:**
- Validates label keys and values (1-63 chars, alphanumeric/dashes/dots/underscores)
- Calls `PATCH /v1/sessions/{session}` with `{"labels": {...}}`

---

### acp_unlabel_resource

Remove labels from a session by key.

**Input Schema:**
```json
{
  "project": "string (optional, uses default if not provided)",
  "name": "string (required) - Session name",
  "resource_type": "string (optional, default: 'agenticsession')",
  "label_keys": "array[string] (required) - List of label keys to remove"
}
```

**Output:**
```json
{
  "unlabeled": true,
  "session": "my-session",
  "labels_removed": ["env", "team"],
  "message": "Removed 2 label(s) from session 'my-session'"
}
```

**Behavior:**
- Calls `PATCH /v1/sessions/{session}` with `{"removeLabels": [...]}`
- Validates that label_keys is not empty

---

### acp_list_sessions_by_label

List sessions matching label selectors.

**Input Schema:**
```json
{
  "project": "string (optional, uses default if not provided)",
  "labels": "object (required) - Labels to match, e.g. {\"env\": \"test\"}"
}
```

**Output:**
```json
{
  "sessions": [
    {"id": "session-1", "status": "running", "createdAt": "2026-01-29T10:00:00Z"}
  ],
  "total": 1,
  "labels_filter": {"env": "test"}
}
```

**Behavior:**
- Builds label selector query string: `key1=value1,key2=value2`
- Calls `GET /v1/sessions?labelSelector=...`
- Validates label keys and values

---

### acp_bulk_label_resources

Add labels to multiple sessions (max 3). Requires `confirm=true`.

**Input Schema:**
```json
{
  "project": "string (optional, uses default if not provided)",
  "sessions": "array[string] (required) - max 3 items",
  "labels": "object (required) - Labels to add",
  "confirm": "boolean (optional, default: false)",
  "dry_run": "boolean (optional, default: false)"
}
```

**Output:**
```json
{
  "labeled": ["session-1", "session-2"],
  "failed": [],
  "labels": {"env": "test"}
}
```

**Behavior:**
- Validates bulk limit (max 3 sessions)
- Validates label keys and values
- Server enforces `confirm=true` for non-dry-run execution

---

### acp_bulk_unlabel_resources

Remove labels from multiple sessions (max 3). Requires `confirm=true`.

**Input Schema:**
```json
{
  "project": "string (optional, uses default if not provided)",
  "sessions": "array[string] (required) - max 3 items",
  "label_keys": "array[string] (required) - Label keys to remove",
  "confirm": "boolean (optional, default: false)",
  "dry_run": "boolean (optional, default: false)"
}
```

**Output:**
```json
{
  "unlabeled": ["session-1", "session-2"],
  "failed": [],
  "label_keys": ["env"]
}
```

**Behavior:**
- Validates bulk limit (max 3 sessions)
- Server enforces `confirm=true` for non-dry-run execution

---

## Bulk Operations

### acp_bulk_delete_sessions

Delete multiple sessions (max 3). Requires `confirm=true` for non-dry-run execution.

**Input Schema:**
```json
{
  "project": "string (optional, uses default if not provided)",
  "sessions": "array[string] (required) - max 3 items",
  "confirm": "boolean (optional, default: false) - required for destructive operations",
  "dry_run": "boolean (optional, default: false)"
}
```

**Output:**
```json
{
  "deleted": ["session-1", "session-2"],
  "failed": [
    {"session": "session-3", "error": "not found"}
  ]
}
```

**Behavior:**
- Validates bulk limit (max 3 sessions)
- Server enforces `confirm=true` for non-dry-run execution
- Iterates through sessions, calling `delete_session()` for each

---

### acp_bulk_stop_sessions

Stop multiple running sessions (max 3). Requires `confirm=true`.

**Input Schema:**
```json
{
  "project": "string (optional, uses default if not provided)",
  "sessions": "array[string] (required) - max 3 items",
  "confirm": "boolean (optional, default: false)",
  "dry_run": "boolean (optional, default: false)"
}
```

**Output:**
```json
{
  "stopped": ["session-1", "session-2"],
  "failed": []
}
```

**Behavior:**
- Validates bulk limit (max 3 sessions)
- Server enforces `confirm=true` for non-dry-run execution
- Iterates through sessions, calling `stop_session()` for each

---

### acp_bulk_restart_sessions

Restart multiple stopped sessions (max 3). Requires `confirm=true`.

**Input Schema:**
```json
{
  "project": "string (optional, uses default if not provided)",
  "sessions": "array[string] (required) - max 3 items",
  "confirm": "boolean (optional, default: false)",
  "dry_run": "boolean (optional, default: false)"
}
```

**Output:**
```json
{
  "restarted": ["session-1", "session-2"],
  "failed": []
}
```

**Behavior:**
- Validates bulk limit (max 3 sessions)
- Server enforces `confirm=true` for non-dry-run execution
- Iterates through sessions, calling `restart_session()` for each

---

### acp_bulk_delete_sessions_by_label

Delete sessions matching label selectors (max 3 matches). Requires `confirm=true`.

**Input Schema:**
```json
{
  "project": "string (optional, uses default if not provided)",
  "labels": "object (required) - Label selectors, e.g. {\"env\": \"test\"}",
  "confirm": "boolean (optional, default: false)",
  "dry_run": "boolean (optional, default: false)"
}
```

**Output:**
```json
{
  "deleted": ["session-1"],
  "failed": [],
  "labels_filter": {"env": "test"}
}
```

**Behavior:**
- Finds sessions matching labels via `list_sessions_by_label()`
- Validates bulk limit (max 3 matching sessions)
- Iterates through matched sessions, calling `delete_session()` for each

---

### acp_bulk_stop_sessions_by_label

Stop sessions matching label selectors (max 3 matches). Requires `confirm=true`.

**Input Schema:**
```json
{
  "project": "string (optional, uses default if not provided)",
  "labels": "object (required) - Label selectors",
  "confirm": "boolean (optional, default: false)",
  "dry_run": "boolean (optional, default: false)"
}
```

**Output:**
```json
{
  "stopped": ["session-1"],
  "failed": [],
  "labels_filter": {"env": "test"}
}
```

**Behavior:**
- Finds sessions matching labels via `list_sessions_by_label()`
- Validates bulk limit (max 3 matching sessions)
- Iterates through matched sessions, calling `stop_session()` for each

---

### acp_bulk_restart_sessions_by_label

Restart sessions matching label selectors (max 3 matches). Requires `confirm=true`.

**Input Schema:**
```json
{
  "project": "string (optional, uses default if not provided)",
  "labels": "object (required) - Label selectors",
  "confirm": "boolean (optional, default: false)",
  "dry_run": "boolean (optional, default: false)"
}
```

**Output:**
```json
{
  "restarted": ["session-1"],
  "failed": [],
  "labels_filter": {"env": "test"}
}
```

**Behavior:**
- Finds sessions matching labels via `list_sessions_by_label()`
- Validates bulk limit (max 3 matching sessions)
- Iterates through matched sessions, calling `restart_session()` for each

---

## Cluster Management

### acp_list_clusters

List configured cluster aliases from clusters.yaml.

**Input Schema:**
```json
{}
```

**Output:**
```json
{
  "clusters": [
    {
      "name": "vteam-stage",
      "server": "https://public-api-ambient.apps.vteam-stage.example.com",
      "description": "Staging cluster",
      "default_project": "my-workspace",
      "is_default": true
    }
  ],
  "default_cluster": "vteam-stage"
}
```

**Behavior:**
- Reads from clusters.yaml configuration
- Marks default cluster with `is_default: true`
- Synchronous operation (no API call)

---

### acp_whoami

Get current configuration and authentication status.

**Input Schema:**
```json
{}
```

**Output:**
```json
{
  "cluster": "vteam-stage",
  "server": "https://public-api-ambient.apps.vteam-stage.example.com",
  "project": "my-workspace",
  "token_valid": true,
  "authenticated": true
}
```

**Behavior:**
- Reads current cluster configuration
- Checks if Bearer token is configured
- Returns cluster, server, project, and authentication status

---

### acp_switch_cluster

Switch to a different cluster context.

**Input Schema:**
```json
{
  "cluster": "string (required) - cluster alias name"
}
```

**Output:**
```json
{
  "switched": true,
  "previous": "vteam-stage",
  "current": "vteam-prod",
  "message": "Switched from vteam-stage to vteam-prod"
}
```

**Behavior:**
- Verifies cluster exists in configuration
- Updates the active cluster context

---

### acp_login

Authenticate to a cluster with a Bearer token.

**Input Schema:**
```json
{
  "cluster": "string (required) - Cluster alias name",
  "token": "string (optional) - Bearer token for authentication"
}
```

**Output:**
```json
{
  "authenticated": true,
  "cluster": "vteam-stage",
  "server": "https://public-api-ambient.apps.vteam-stage.example.com",
  "message": "Successfully authenticated to cluster 'vteam-stage'"
}
```

**Behavior:**
- Sets the token on the cluster config in memory (not persisted to disk)
- Verifies the token is valid by checking configuration
- If no token provided, checks for existing token or `ACP_TOKEN` environment variable

---

## Error Handling

**Validation errors:**
```
Validation Error: Field 'session' contains invalid characters
```

**Timeout errors:**
```
Timeout Error: Request timed out: /v1/sessions
```

**API errors:**
```
Error: HTTP 404: session not found
```

---

## Configuration

**Config File Location:** `~/.config/acp/clusters.yaml`

**Format:**
```yaml
clusters:
  vteam-stage:
    server: https://public-api-ambient.apps.vteam-stage.example.com
    token: your-bearer-token-here
    description: Staging cluster
    default_project: my-workspace

default_cluster: vteam-stage
```

**Environment Variables:**
- `ACP_CLUSTER_CONFIG`: Override config file path
- `ACP_TOKEN`: Override Bearer token

---

## Tool Inventory Summary

**Total: 26 Tools**

| Category | Count | Tools |
|----------|-------|-------|
| Session Management | 8 | list_sessions, get_session, create_session, create_session_from_template, delete_session, restart_session, clone_session, update_session |
| Observability | 3 | get_session_logs, get_session_transcript, get_session_metrics |
| Labels | 5 | label_resource, unlabel_resource, list_sessions_by_label, bulk_label_resources, bulk_unlabel_resources |
| Bulk Operations | 6 | bulk_delete_sessions, bulk_stop_sessions, bulk_restart_sessions, bulk_delete_sessions_by_label, bulk_stop_sessions_by_label, bulk_restart_sessions_by_label |
| Cluster Management | 4 | list_clusters, whoami, switch_cluster, login |

---

## MCP Protocol

- Transport: stdio
- Protocol Version: MCP 1.0.0+
- All responses: wrapped in TextContent with type="text"
- Tool definitions include inputSchema with JSON Schema

---

End of API Reference
