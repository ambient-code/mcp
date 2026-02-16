"""Output formatters for MCP responses."""

import json
from typing import Any


def format_result(result: dict[str, Any]) -> str:
    """Format a simple result dictionary."""
    if result.get("dry_run"):
        output = "DRY RUN MODE - No changes made\n\n"
        output += result.get("message", "")
        if "session_info" in result:
            output += f"\n\nSession Info:\n{json.dumps(result['session_info'], indent=2)}"
        if "patch" in result:
            output += f"\n\nPatch:\n{json.dumps(result['patch'], indent=2)}"
        if "current" in result:
            output += f"\n\nCurrent:\n{json.dumps(result['current'], indent=2)}"
        return output

    return result.get("message", json.dumps(result, indent=2))


def format_sessions_list(result: dict[str, Any]) -> str:
    """Format sessions list with filtering info."""
    output = f"Found {result['total']} session(s)"

    filters = result.get("filters_applied", {})
    labels_filter = result.get("labels_filter")

    if filters:
        output += f"\nFilters applied: {json.dumps(filters)}"
    if labels_filter:
        output += f"\nLabel filter: {json.dumps(labels_filter)}"

    output += "\n\nSessions:\n"

    for session in result["sessions"]:
        # Handle both public-api DTO format and raw K8s format
        session_id = session.get("id") or session.get("metadata", {}).get("name", "unknown")
        status = session.get("status") or session.get("status", {}).get("phase", "unknown")
        created = session.get("createdAt") or session.get("metadata", {}).get("creationTimestamp", "unknown")
        task = session.get("task", "")

        output += f"\n- {session_id}"
        output += f"\n  Status: {status}"
        output += f"\n  Created: {created}"
        if task:
            output += f"\n  Task: {task[:50]}{'...' if len(task) > 50 else ''}"
        output += "\n"

    return output


def format_bulk_result(result: dict[str, Any], operation: str) -> str:
    """Format bulk operation results."""
    if result.get("dry_run"):
        output = "DRY RUN MODE - No changes made\n\n"

        dry_run_info = result.get("dry_run_info", {})
        would_execute = dry_run_info.get("would_execute", [])
        skipped = dry_run_info.get("skipped", [])

        if would_execute:
            output += f"Would {operation} {len(would_execute)} session(s):\n"
            for item in would_execute:
                output += f"  - {item['session']}\n"
                if item.get("info") and "status" in item["info"]:
                    output += f"    Status: {item['info']['status']}\n"

        if skipped:
            output += f"\nSkipped ({len(skipped)} session(s)):\n"
            for item in skipped:
                output += f"  - {item['session']}"
                if "reason" in item:
                    output += f": {item['reason']}"
                output += "\n"

        # Handle label/unlabel dry run (different format)
        if result.get("message") and not would_execute and not skipped:
            output += result["message"] + "\n"

        if result.get("labels_filter"):
            output += f"\nLabel filter: {json.dumps(result['labels_filter'])}\n"

        return output

    success_key_map = {
        "delete": "deleted",
        "stop": "stopped",
        "restart": "restarted",
        "label": "labeled",
        "unlabel": "unlabeled",
    }
    success_key = success_key_map.get(operation, operation)
    success = result.get(success_key, [])
    failed = result.get("failed", [])

    output = f"Successfully {success_key} {len(success)} session(s)"

    if success:
        output += ":\n"
        for session in success:
            output += f"  - {session}\n"

    if failed:
        output += f"\nFailed ({len(failed)} session(s)):\n"
        for item in failed:
            output += f"  - {item['session']}: {item['error']}\n"

    if result.get("labels_filter"):
        output += f"\nLabel filter: {json.dumps(result['labels_filter'])}\n"

    if not success and result.get("message"):
        output = result["message"]

    return output


def format_clusters(result: dict[str, Any]) -> str:
    """Format clusters list."""
    clusters = result.get("clusters", [])
    default = result.get("default_cluster")

    if not clusters:
        return "No clusters configured. Create ~/.config/acp/clusters.yaml to add clusters."

    output = f"Configured Clusters (default: {default or 'none'}):\n\n"

    for cluster in clusters:
        name = cluster["name"]
        is_default = cluster.get("is_default", False)
        marker = " [DEFAULT]" if is_default else ""

        output += f"- {name}{marker}\n"
        output += f"  Server: {cluster.get('server', 'N/A')}\n"

        if cluster.get("description"):
            output += f"  Description: {cluster['description']}\n"

        if cluster.get("default_project"):
            output += f"  Default Project: {cluster['default_project']}\n"

        output += "\n"

    return output


def format_whoami(result: dict[str, Any]) -> str:
    """Format whoami information."""
    output = "Configuration Status:\n\n"

    authenticated = result.get("authenticated", False)
    output += f"Token Configured: {'Yes' if authenticated else 'No'}\n"

    output += f"Cluster: {result.get('cluster', 'unknown')}\n"
    output += f"Server: {result.get('server', 'unknown')}\n"
    output += f"Project: {result.get('project', 'unknown')}\n"

    if not authenticated:
        output += "\nSet token in clusters.yaml or ACP_TOKEN environment variable.\n"

    if result.get("error"):
        output += f"\nError: {result['error']}\n"

    return output


def format_session_created(result: dict[str, Any]) -> str:
    """Format session creation result with follow-up commands."""
    if result.get("dry_run"):
        output = "DRY RUN MODE - No changes made\n\n"
        output += result.get("message", "")
        if "manifest" in result:
            output += f"\n\nManifest:\n{json.dumps(result['manifest'], indent=2)}"
        return output

    if not result.get("created"):
        return f"Failed to create session: {result.get('message', 'unknown error')}"

    session = result.get("session", "unknown")
    project = result.get("project", "unknown")

    output = f"Session created: {session}\n"
    output += f"Project: {project}\n"

    if result.get("template"):
        output += f"Template: {result['template']}\n"
    if result.get("source_session"):
        output += f"Cloned from: {result['source_session']}\n"

    output += "\nCheck status:\n"
    output += f'  acp_list_sessions(project="{project}")\n'
    output += f'  acp_get_session(project="{project}", session="{session}")\n'

    return output


def format_logs(result: dict[str, Any]) -> str:
    """Format session logs output."""
    if result.get("error"):
        return f"Error retrieving logs for session '{result.get('session', 'unknown')}': {result['error']}"

    session = result.get("session", "unknown")
    tail_lines = result.get("tail_lines", "unknown")
    logs = result.get("logs", "")

    output = f"Logs for session '{session}' (tail: {tail_lines}):\n\n"
    output += logs if logs else "(no logs available)"
    return output


def format_transcript(result: dict[str, Any]) -> str:
    """Format session transcript output."""
    session = result.get("session", "unknown")
    fmt = result.get("format", "json")

    output = f"Transcript for session '{session}' (format: {fmt}):\n\n"

    if fmt == "markdown":
        output += result.get("transcript", result.get("text", "(no transcript available)"))
    else:
        # JSON format — pretty-print the transcript data
        transcript_data = result.get("messages", result.get("transcript", []))
        if transcript_data:
            output += json.dumps(transcript_data, indent=2)
        else:
            output += "(no transcript available)"

    return output


def format_metrics(result: dict[str, Any]) -> str:
    """Format session metrics output."""
    session = result.get("session", "unknown")

    output = f"Metrics for session '{session}':\n\n"

    for key, value in result.items():
        if key == "session":
            continue
        label = key.replace("_", " ").title()
        output += f"  {label}: {value}\n"

    return output


def format_labels(result: dict[str, Any]) -> str:
    """Format label operation results."""
    if result.get("labeled"):
        if isinstance(result["labeled"], bool):
            return result.get("message", "Labels updated")
        # bulk label result
        return format_bulk_result(result, "label")

    if result.get("unlabeled"):
        if isinstance(result["unlabeled"], bool):
            return result.get("message", "Labels removed")
        return format_bulk_result(result, "unlabel")

    return result.get("message", json.dumps(result, indent=2))


def format_login(result: dict[str, Any]) -> str:
    """Format login result."""
    if result.get("authenticated"):
        output = "Authentication successful\n\n"
        output += f"Cluster: {result.get('cluster', 'unknown')}\n"
        output += f"Server: {result.get('server', 'unknown')}\n"
    else:
        output = "Authentication failed\n\n"
        output += f"Cluster: {result.get('cluster', 'unknown')}\n"
        output += f"Error: {result.get('message', 'unknown error')}\n"

    return output
