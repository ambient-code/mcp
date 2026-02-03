"""Output formatters for MCP responses."""

import json
from typing import Any


def format_result(result: dict[str, Any]) -> str:
    """Format a simple result dictionary.

    Args:
        result: Result dictionary from operation

    Returns:
        Formatted string for display
    """
    if result.get("dry_run"):
        output = "DRY RUN MODE - No changes made\n\n"
        output += result.get("message", "")
        if "session_info" in result:
            output += f"\n\nSession Info:\n{json.dumps(result['session_info'], indent=2)}"
        return output

    return result.get("message", json.dumps(result, indent=2))


def format_sessions_list(result: dict[str, Any]) -> str:
    """Format sessions list with filtering info.

    Args:
        result: Result dictionary with sessions list

    Returns:
        Formatted string for display
    """
    output = f"Found {result['total']} session(s)"

    filters = result.get("filters_applied", {})
    if filters:
        output += f"\nFilters applied: {json.dumps(filters, indent=2)}"

    output += "\n\nSessions:\n"

    for session in result["sessions"]:
        metadata = session.get("metadata", {})
        spec = session.get("spec", {})
        status = session.get("status", {})

        name = metadata.get("name", "unknown")
        display_name = spec.get("displayName", "")
        phase = status.get("phase", "unknown")
        created = metadata.get("creationTimestamp", "unknown")

        output += f"\n- {name}"
        if display_name:
            output += f' ("{display_name}")'
        output += f"\n  Status: {phase}\n  Created: {created}\n"

    return output


def format_bulk_result(result: dict[str, Any], operation: str) -> str:
    """Format bulk operation results.

    Args:
        result: Result dictionary from bulk operation
        operation: Operation name (e.g., "delete", "stop")

    Returns:
        Formatted string for display
    """
    if result.get("dry_run"):
        output = "DRY RUN MODE - No changes made\n\n"

        # Handle enhanced dry-run for label-based operations
        if "matched_sessions" in result:
            matched = result.get("matched_sessions", [])
            output += f"Matched {result.get('matched_count', len(matched))} sessions with label selector:\n"
            output += f"  {result.get('label_selector', 'N/A')}\n\n"
            if matched:
                output += "Matched sessions:\n"
                for session in matched:
                    output += f"  - {session}\n"
            output += f"\n{result.get('message', '')}\n"
            return output

        dry_run_info = result.get("dry_run_info", {})

        would_execute = dry_run_info.get("would_execute", [])
        skipped = dry_run_info.get("skipped", [])

        if would_execute:
            output += f"Would {operation} {len(would_execute)} session(s):\n"
            for item in would_execute:
                output += f"  - {item['session']}\n"
                if item.get("info"):
                    info = item["info"]
                    if "status" in info:
                        output += f"    Status: {info['status']}\n"

        if skipped:
            output += f"\nSkipped ({len(skipped)} session(s)):\n"
            for item in skipped:
                output += f"  - {item['session']}"
                if "reason" in item:
                    output += f": {item['reason']}"
                output += "\n"

        return output

    # Normal mode
    # Map operation to success key
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

    # Determine if we're working with sessions or resources
    resource_type = "session(s)" if "session" in str(failed) else "resource(s)"
    output = f"Successfully {operation}d {len(success)} {resource_type}"

    if success:
        output += ":\n"
        for session in success:
            output += f"  - {session}\n"

    if failed:
        output += f"\nFailed ({len(failed)} session(s)):\n"
        for item in failed:
            output += f"  - {item['session']}: {item['error']}\n"

    return output


def format_logs(result: dict[str, Any]) -> str:
    """Format session logs.

    Args:
        result: Result dictionary with logs

    Returns:
        Formatted string for display
    """
    if "error" in result:
        error_msg = result["error"]
        # Check if this is an expected state rather than an error
        error_lower = error_msg.lower()
        if any(phrase in error_lower for phrase in ["no pods found", "not found", "no running pods"]):
            return f"No logs available: {error_msg}\n\nNote: This is expected for stopped sessions or sessions without active pods."
        return f"Error retrieving logs: {error_msg}"

    output = f"Logs from container '{result.get('container', 'default')}'"
    output += f" ({result.get('lines', 0)} lines):\n\n"
    output += result.get("logs", "")

    return output


def format_clusters(result: dict[str, Any]) -> str:
    """Format clusters list.

    Args:
        result: Result dictionary with clusters list

    Returns:
        Formatted string for display
    """
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
    """Format whoami information.

    Args:
        result: Result dictionary with auth info

    Returns:
        Formatted string for display
    """
    output = "Current Authentication Status:\n\n"

    authenticated = result.get("authenticated", False)
    output += f"Authenticated: {'Yes' if authenticated else 'No'}\n"

    if authenticated:
        output += f"User: {result.get('user', 'unknown')}\n"
        output += f"Cluster: {result.get('cluster', 'unknown')}\n"
        output += f"Server: {result.get('server', 'unknown')}\n"
        output += f"Project: {result.get('project', 'unknown')}\n"

        token_valid = result.get("token_valid", False)
        output += f"Token Valid: {'Yes' if token_valid else 'No'}\n"

        if result.get("token_expires"):
            output += f"Token Expires: {result['token_expires']}\n"
    else:
        output += "\nYou are not authenticated. Use 'acp_login' to authenticate.\n"

    return output


def format_transcript(result: dict[str, Any]) -> str:
    """Format session transcript.

    Args:
        result: Result dictionary with transcript

    Returns:
        Formatted string for display
    """
    if "error" in result:
        error_msg = result["error"]
        error_lower = error_msg.lower()
        # Check if this is an expected state (no transcript available)
        if any(phrase in error_lower for phrase in ["no transcript", "transcript not found", "no data"]):
            return f"No transcript available: {error_msg}\n\nNote: Sessions may not have transcript data if they are newly created, stopped, or haven't processed messages yet."
        return f"Error retrieving transcript: {error_msg}"

    format_type = result.get("format", "json")
    message_count = result.get("message_count", 0)

    if message_count == 0:
        return "Session Transcript: No messages yet.\n\nNote: This session may be newly created or hasn't processed any messages."

    if format_type == "markdown":
        output = f"Session Transcript ({message_count} messages):\n\n"
        output += result.get("transcript", "")
        return output
    else:
        output = f"Session Transcript ({message_count} messages):\n\n"
        output += json.dumps(result.get("transcript", []), indent=2)
        return output


def format_metrics(result: dict[str, Any]) -> str:
    """Format session metrics.

    Args:
        result: Result dictionary with metrics

    Returns:
        Formatted string for display
    """
    if "error" in result:
        error_msg = result["error"]
        error_lower = error_msg.lower()
        # Check if this is an expected state (no metrics available)
        if any(phrase in error_lower for phrase in ["no transcript", "no data", "not found"]):
            return f"No metrics available: {error_msg}\n\nNote: Metrics are calculated from transcript data. Sessions without transcript data (new, stopped, or inactive sessions) will not have metrics."
        return f"Error retrieving metrics: {error_msg}"

    output = "Session Metrics:\n\n"
    message_count = result.get("message_count", 0)

    if message_count == 0:
        output += "No metrics available yet.\n\nNote: This session has no message history. Metrics will be available after the session processes messages."
        return output

    output += f"Message Count: {message_count}\n"
    output += f"Token Count (approx): {result.get('token_count', 0)}\n"
    output += f"Duration: {result.get('duration_seconds', 0)} seconds\n"
    output += f"Status: {result.get('status', 'unknown')}\n"

    tool_calls = result.get("tool_calls", {})
    if tool_calls:
        output += "\nTool Usage:\n"
        for tool_name, count in sorted(tool_calls.items(), key=lambda x: x[1], reverse=True):
            output += f"  - {tool_name}: {count}\n"

    return output


def format_workflows(result: dict[str, Any]) -> str:
    """Format workflows list.

    Args:
        result: Result dictionary with workflows

    Returns:
        Formatted string for display
    """
    if "error" in result:
        error_msg = result["error"]
        error_lower = error_msg.lower()
        # Check if this is an expected state (no workflows found)
        if any(phrase in error_lower for phrase in ["no workflows", "not found", "no .github/workflows"]):
            return f"No workflows found: {error_msg}\n\nNote: This repository may not have GitHub Actions workflows configured yet."
        return f"Error retrieving workflows: {error_msg}"

    workflows = result.get("workflows", [])
    repo_url = result.get("repo_url", "")
    count = result.get("count", 0)

    if not workflows:
        return f"No workflows found in {repo_url}\n\nNote: This repository does not have any GitHub Actions workflows in .github/workflows/"

    output = f"Available Workflows ({count} found):\n"
    output += f"Repository: {repo_url}\n\n"

    for workflow in workflows:
        output += f"- {workflow['name']}\n"
        output += f"  Path: {workflow['path']}\n"
        if workflow.get("description"):
            output += f"  Description: {workflow['description']}\n"
        output += "\n"

    return output


def format_export(result: dict[str, Any]) -> str:
    """Format session export data.

    Args:
        result: Result dictionary with export data

    Returns:
        Formatted string for display
    """
    if "error" in result:
        error_msg = result["error"]
        error_lower = error_msg.lower()
        # Check if this is a partial export (some data unavailable)
        if any(phrase in error_lower for phrase in ["no transcript", "no data", "partially exported"]):
            return f"Partial export: {error_msg}\n\nNote: Some session data may be unavailable for stopped or inactive sessions. Exported data reflects what was accessible."
        return f"Error exporting session: {error_msg}"

    if not result.get("exported"):
        return result.get("message", "Export failed")

    data = result.get("data", {})
    output = "Session Export:\n\n"
    output += "Configuration:\n"
    output += json.dumps(data.get("config", {}), indent=2)
    output += "\n\nMetadata:\n"
    output += json.dumps(data.get("metadata", {}), indent=2)

    transcript = data.get("transcript", [])
    transcript_count = len(transcript)
    output += f"\n\nTranscript: {transcript_count} messages"

    if transcript_count == 0:
        output += " (no transcript data available - this is expected for new/stopped sessions)"

    output += "\n\n" + result.get("message", "")

    return output


def format_cluster_operation(result: dict[str, Any]) -> str:
    """Format cluster operation results (add, switch, login).

    Args:
        result: Result dictionary from cluster operation

    Returns:
        Formatted string for display
    """
    return result.get("message", json.dumps(result, indent=2))
