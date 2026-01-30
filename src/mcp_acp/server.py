"""MCP server for Ambient Code Platform management."""

import asyncio
import os
from typing import Any, Callable, Dict, Optional, Tuple

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from utils.pylogger import get_python_logger
from .client import ACPClient
from .settings import load_settings
from .formatters import (
    format_bulk_result,
    format_cluster_operation,
    format_clusters,
    format_export,
    format_logs,
    format_metrics,
    format_result,
    format_sessions_list,
    format_transcript,
    format_whoami,
    format_workflows,
)

# Initialize structured logger
logger = get_python_logger()

# Create MCP server instance
app = Server("mcp-acp")

# Global client instance
_client: Optional[ACPClient] = None

# Schema fragments for reuse
SCHEMA_FRAGMENTS = {
    "project": {
        "type": "string",
        "description": "Project/namespace name (optional - uses default_project from clusters.yaml if not provided)",
    },
    "session": {
        "type": "string",
        "description": "Session name",
    },
    "dry_run": {
        "type": "boolean",
        "description": "Preview without actually executing (default: false)",
        "default": False,
    },
    "sessions_list": {
        "type": "array",
        "items": {"type": "string"},
        "description": "List of session names",
    },
    "container": {
        "type": "string",
        "description": "Container name (e.g., 'runner', 'sidecar')",
    },
    "tail_lines": {
        "type": "integer",
        "description": "Number of lines to retrieve from the end",
        "minimum": 1,
    },
    "display_name": {
        "type": "string",
        "description": "Display name for the session",
    },
    "cluster": {
        "type": "string",
        "description": "Cluster alias name or server URL",
    },
    "repos_list": {
        "type": "array",
        "items": {"type": "string"},
        "description": "List of repository URLs",
    },
}


def create_tool_schema(properties: Dict[str, Any], required: list[str]) -> Dict[str, Any]:
    """Build tool input schema from property references.

    Args:
        properties: Dict mapping property names to fragment keys or schema dicts
        required: List of required property names

    Returns:
        JSON schema dict
    """
    schema_properties = {}
    for prop_name, fragment_key in properties.items():
        if isinstance(fragment_key, str) and fragment_key in SCHEMA_FRAGMENTS:
            # Reference to a schema fragment - use a copy to avoid mutation
            schema_properties[prop_name] = SCHEMA_FRAGMENTS[fragment_key].copy()
        elif isinstance(fragment_key, dict):
            # Inline schema definition - use a copy to avoid mutation
            schema_properties[prop_name] = fragment_key.copy()
        else:
            # String reference not in fragments - treat as-is
            schema_properties[prop_name] = fragment_key

    return {
        "type": "object",
        "properties": schema_properties,
        "required": required,
    }


def get_client() -> ACPClient:
    """Get or create ACP client instance with error handling."""
    global _client
    if _client is None:
        config_path = os.getenv("ACP_CLUSTER_CONFIG")
        try:
            logger.info("acp_client_initializing", config_path=config_path or "default")
            _client = ACPClient(config_path=config_path)
            logger.info("acp_client_initialized")
        except ValueError as e:
            logger.error("acp_client_init_failed", error=str(e))
            raise
        except Exception as e:
            logger.error("acp_client_init_unexpected_error", error=str(e), exc_info=True)
            raise
    return _client


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available ACP (Ambient Code Platform) tools for managing AgenticSession resources on OpenShift/Kubernetes."""
    return [
        # P0 Priority Tools
        Tool(
            name="acp_delete_session",
            description="Delete an ACP (Ambient Code Platform) AgenticSession from an OpenShift project/namespace. Supports dry-run mode for safe preview before deletion.",
            inputSchema=create_tool_schema(
                properties={
                    "project": "project",
                    "session": "session",
                    "dry_run": "dry_run",
                },
                required=["session"],
            ),
        ),
        Tool(
            name="acp_list_sessions",
            description="List and filter ACP (Ambient Code Platform) AgenticSessions in an OpenShift project. Filter by status (running/stopped/failed), age, display name. Sort and limit results.",
            inputSchema=create_tool_schema(
                properties={
                    "project": "project",
                    "status": {
                        "type": "string",
                        "description": "Filter by status",
                        "enum": ["running", "stopped", "creating", "failed"],
                    },
                    "has_display_name": {
                        "type": "boolean",
                        "description": "Filter by display name presence",
                    },
                    "older_than": {
                        "type": "string",
                        "description": "Filter by age (e.g., '7d', '24h', '30m')",
                    },
                    "sort_by": {
                        "type": "string",
                        "description": "Sort field",
                        "enum": ["created", "stopped", "name"],
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results",
                        "minimum": 1,
                    },
                },
                required=[],
            ),
        ),
        # P1 Priority Tools
        Tool(
            name="acp_restart_session",
            description="Restart a stopped session. Supports dry-run mode.",
            inputSchema=create_tool_schema(
                properties={
                    "project": "project",
                    "session": "session",
                    "dry_run": "dry_run",
                },
                required=["session"],
            ),
        ),
        Tool(
            name="acp_bulk_delete_sessions",
            description="Delete multiple sessions at once. Supports dry-run mode.",
            inputSchema=create_tool_schema(
                properties={
                    "project": "project",
                    "sessions": "sessions_list",
                    "dry_run": "dry_run",
                },
                required=["sessions"],
            ),
        ),
        Tool(
            name="acp_bulk_stop_sessions",
            description="Stop multiple running sessions at once. Supports dry-run mode.",
            inputSchema=create_tool_schema(
                properties={
                    "project": "project",
                    "sessions": "sessions_list",
                    "dry_run": "dry_run",
                },
                required=["sessions"],
            ),
        ),
        Tool(
            name="acp_get_session_logs",
            description="Retrieve container logs for a session for debugging purposes.",
            inputSchema=create_tool_schema(
                properties={
                    "project": "project",
                    "session": "session",
                    "container": "container",
                    "tail_lines": "tail_lines",
                },
                required=["session"],
            ),
        ),
        Tool(
            name="acp_list_clusters",
            description="List configured cluster aliases from clusters.yaml configuration.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="acp_whoami",
            description="Get current authentication status and user information.",
            inputSchema={"type": "object", "properties": {}},
        ),
        # P2 Priority Tools
        Tool(
            name="acp_clone_session",
            description="Clone a session with its configuration. Supports dry-run mode.",
            inputSchema=create_tool_schema(
                properties={
                    "project": "project",
                    "source_session": "session",
                    "new_display_name": "display_name",
                    "dry_run": "dry_run",
                },
                required=["source_session", "new_display_name"],
            ),
        ),
        Tool(
            name="acp_get_session_transcript",
            description="Get session transcript/conversation history.",
            inputSchema=create_tool_schema(
                properties={
                    "project": "project",
                    "session": "session",
                    "format": {
                        "type": "string",
                        "description": "Output format",
                        "enum": ["json", "markdown"],
                        "default": "json",
                    },
                },
                required=["session"],
            ),
        ),
        Tool(
            name="acp_update_session",
            description="Update session metadata (display name, timeout). Supports dry-run mode.",
            inputSchema=create_tool_schema(
                properties={
                    "project": "project",
                    "session": "session",
                    "display_name": "display_name",
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds",
                    },
                    "dry_run": "dry_run",
                },
                required=["session"],
            ),
        ),
        Tool(
            name="acp_export_session",
            description="Export session configuration and transcript for archival.",
            inputSchema=create_tool_schema(
                properties={
                    "project": "project",
                    "session": "session",
                },
                required=["session"],
            ),
        ),
        # P3 Priority Tools
        Tool(
            name="acp_get_session_metrics",
            description="Get session metrics (token usage, duration, tool calls).",
            inputSchema=create_tool_schema(
                properties={
                    "project": "project",
                    "session": "session",
                },
                required=["session"],
            ),
        ),
        Tool(
            name="acp_list_workflows",
            description="List available workflows from repository.",
            inputSchema=create_tool_schema(
                properties={
                    "repo_url": {
                        "type": "string",
                        "description": "Repository URL (defaults to ootb-ambient-workflows)",
                    },
                },
                required=[],
            ),
        ),
        Tool(
            name="acp_create_session_from_template",
            description="Create session from predefined template (triage, bugfix, feature, exploration). Supports dry-run mode.",
            inputSchema=create_tool_schema(
                properties={
                    "project": "project",
                    "template": {
                        "type": "string",
                        "description": "Template name",
                        "enum": ["triage", "bugfix", "feature", "exploration"],
                    },
                    "display_name": "display_name",
                    "repos": "repos_list",
                    "dry_run": "dry_run",
                },
                required=["template", "display_name"],
            ),
        ),
        # Auth Enhancement Tools
        Tool(
            name="acp_login",
            description="Authenticate to OpenShift cluster via web or token.",
            inputSchema=create_tool_schema(
                properties={
                    "cluster": "cluster",
                    "web": {
                        "type": "boolean",
                        "description": "Use web login flow (default: true)",
                        "default": True,
                    },
                    "token": {
                        "type": "string",
                        "description": "Direct token for authentication",
                    },
                },
                required=["cluster"],
            ),
        ),
        Tool(
            name="acp_switch_cluster",
            description="Switch to a different cluster context.",
            inputSchema=create_tool_schema(
                properties={
                    "cluster": "cluster",
                },
                required=["cluster"],
            ),
        ),
        Tool(
            name="acp_add_cluster",
            description="Add a new cluster to configuration.",
            inputSchema=create_tool_schema(
                properties={
                    "name": {
                        "type": "string",
                        "description": "Cluster alias name",
                    },
                    "server": {
                        "type": "string",
                        "description": "Server URL",
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional description",
                    },
                    "default_project": {
                        "type": "string",
                        "description": "Optional default project",
                    },
                    "set_default": {
                        "type": "boolean",
                        "description": "Set as default cluster",
                        "default": False,
                    },
                },
                required=["name", "server"],
            ),
        ),
    ]


# Tool dispatch table: maps tool names to (handler, formatter) pairs
def create_dispatch_table(client: ACPClient) -> Dict[str, Tuple[Callable, Callable]]:
    """Create tool dispatch table.

    Args:
        client: ACP client instance

    Returns:
        Dict mapping tool names to (handler, formatter) tuples
    """
    return {
        "acp_delete_session": (
            client.delete_session,
            format_result,
        ),
        "acp_list_sessions": (
            client.list_sessions,
            format_sessions_list,
        ),
        "acp_restart_session": (
            client.restart_session,
            format_result,
        ),
        "acp_bulk_delete_sessions": (
            client.bulk_delete_sessions,
            lambda r: format_bulk_result(r, "delete"),
        ),
        "acp_bulk_stop_sessions": (
            client.bulk_stop_sessions,
            lambda r: format_bulk_result(r, "stop"),
        ),
        "acp_get_session_logs": (
            client.get_session_logs,
            format_logs,
        ),
        "acp_list_clusters": (
            client.list_clusters,
            format_clusters,
        ),
        "acp_whoami": (
            client.whoami,
            format_whoami,
        ),
        # P2 Tools
        "acp_clone_session": (
            client.clone_session,
            format_result,
        ),
        "acp_get_session_transcript": (
            client.get_session_transcript,
            format_transcript,
        ),
        "acp_update_session": (
            client.update_session,
            format_result,
        ),
        "acp_export_session": (
            client.export_session,
            format_export,
        ),
        # P3 Tools
        "acp_get_session_metrics": (
            client.get_session_metrics,
            format_metrics,
        ),
        "acp_list_workflows": (
            client.list_workflows,
            format_workflows,
        ),
        "acp_create_session_from_template": (
            client.create_session_from_template,
            format_result,
        ),
        # Auth Tools
        "acp_login": (
            client.login,
            format_cluster_operation,
        ),
        "acp_switch_cluster": (
            client.switch_cluster,
            format_cluster_operation,
        ),
        "acp_add_cluster": (
            client.add_cluster,
            format_cluster_operation,
        ),
    }


@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> list[TextContent]:
    """Handle tool calls with dispatch table.

    Args:
        name: Tool name
        arguments: Tool arguments

    Returns:
        List of text content responses
    """
    import time
    start_time = time.time()

    # Security: Sanitize arguments for logging (remove sensitive data)
    safe_args = {k: v for k, v in arguments.items() if k not in ['token', 'password', 'secret']}
    logger.info("tool_call_started", tool=name, arguments=safe_args)

    client = get_client()
    dispatch_table = create_dispatch_table(client)

    try:
        handler, formatter = dispatch_table.get(name, (None, None))

        if not handler:
            logger.warning("unknown_tool_requested", tool=name)
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

        # Auto-fill project from default_project if not provided or empty
        if not arguments.get("project"):
            # Get default project from current cluster config
            default_cluster = client.config.get("default_cluster")
            if default_cluster:
                cluster_config = client.config.get("clusters", {}).get(default_cluster, {})
                default_project = cluster_config.get("default_project")
                if default_project:
                    arguments["project"] = default_project
                    logger.info("project_autofilled", project=default_project, cluster=default_cluster)

        # Call handler (async or sync)
        if asyncio.iscoroutinefunction(handler):
            result = await handler(**arguments)
        else:
            result = handler(**arguments)

        # Log execution time
        elapsed = time.time() - start_time
        logger.info("tool_call_completed", tool=name, elapsed_seconds=round(elapsed, 2))

        # Check for errors in result
        if isinstance(result, dict):
            if result.get("error"):
                logger.warning("tool_returned_error", tool=name, error=result.get("error"))
            elif not result.get("success", True) and "message" in result:
                logger.warning("tool_failed", tool=name, message=result.get("message"))

        return [TextContent(type="text", text=formatter(result))]

    except ValueError as e:
        # Validation errors - these are expected for invalid input
        elapsed = time.time() - start_time
        logger.warning("tool_validation_error", tool=name, elapsed_seconds=round(elapsed, 2), error=str(e))
        return [TextContent(type="text", text=f"Validation Error: {str(e)}")]
    except asyncio.TimeoutError as e:
        elapsed = time.time() - start_time
        logger.error("tool_timeout", tool=name, elapsed_seconds=round(elapsed, 2), error=str(e))
        return [TextContent(type="text", text=f"Timeout Error: {str(e)}")]
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error("tool_unexpected_error", tool=name, elapsed_seconds=round(elapsed, 2), error=str(e), exc_info=True)
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def main() -> None:
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


def run() -> None:
    """Entry point for the MCP server."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
