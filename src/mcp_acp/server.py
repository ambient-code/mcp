"""MCP server for Ambient Code Platform management."""

import asyncio
import os
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from utils.pylogger import get_python_logger

from .client import ACPClient
from .formatters import (
    format_bulk_result,
    format_clusters,
    format_labels,
    format_login,
    format_logs,
    format_metrics,
    format_result,
    format_session_created,
    format_sessions_list,
    format_transcript,
    format_whoami,
)

logger = get_python_logger()

app = Server("mcp-acp")

_client: ACPClient | None = None


def get_client() -> ACPClient:
    """Get or create ACP client instance."""
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


# ── Shared schema fragments ─────────────────────────────────────────────

_PROJECT = {"type": "string", "description": "Project/namespace name (uses default if not provided)"}
_SESSION = {"type": "string", "description": "Session ID"}
_DRY_RUN = {"type": "boolean", "description": "Preview without executing (default: false)", "default": False}
_CONFIRM = {"type": "boolean", "description": "Required for destructive operations (default: false)", "default": False}
_SESSIONS_ARRAY = {"type": "array", "items": {"type": "string"}, "description": "List of session names (max 3)"}
_LABELS_OBJECT = {
    "type": "object",
    "additionalProperties": {"type": "string"},
    "description": 'Labels as key-value pairs (e.g., {"env": "test", "team": "qa"})',
}
_LABEL_KEYS_ARRAY = {"type": "array", "items": {"type": "string"}, "description": "List of label keys to remove"}


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available ACP tools for managing AgenticSession resources."""
    return [
        # ── Session Management ───────────────────────────────────────────
        Tool(
            name="acp_list_sessions",
            description="List and filter AgenticSessions in a project. Filter by status (running/stopped/failed), age. Sort and limit results.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": _PROJECT,
                    "status": {
                        "type": "string",
                        "description": "Filter by status",
                        "enum": ["running", "stopped", "creating", "failed"],
                    },
                    "older_than": {"type": "string", "description": "Filter by age (e.g., '7d', '24h', '30m')"},
                    "sort_by": {"type": "string", "description": "Sort field", "enum": ["created", "stopped", "name"]},
                    "limit": {"type": "integer", "description": "Maximum number of results", "minimum": 1},
                },
                "required": [],
            },
        ),
        Tool(
            name="acp_get_session",
            description="Get details of a specific session by ID.",
            inputSchema={
                "type": "object",
                "properties": {"project": _PROJECT, "session": _SESSION},
                "required": ["session"],
            },
        ),
        Tool(
            name="acp_create_session",
            description="Create an ACP AgenticSession with a custom prompt. Supports dry-run mode.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": _PROJECT,
                    "initial_prompt": {
                        "type": "string",
                        "description": "The prompt/instructions to send to the session",
                    },
                    "display_name": {"type": "string", "description": "Human-readable display name"},
                    "repos": {"type": "array", "items": {"type": "string"}, "description": "Repository URLs to clone"},
                    "interactive": {
                        "type": "boolean",
                        "description": "Create an interactive session",
                        "default": False,
                    },
                    "model": {"type": "string", "description": "LLM model to use", "default": "claude-sonnet-4"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 900, "minimum": 60},
                    "dry_run": _DRY_RUN,
                },
                "required": ["initial_prompt"],
            },
        ),
        Tool(
            name="acp_create_session_from_template",
            description="Create a session from a predefined template (triage/bugfix/feature/exploration). Each template has optimized settings.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": _PROJECT,
                    "template": {
                        "type": "string",
                        "description": "Template name",
                        "enum": ["triage", "bugfix", "feature", "exploration"],
                    },
                    "display_name": {"type": "string", "description": "Display name for the session"},
                    "repos": {"type": "array", "items": {"type": "string"}, "description": "Repository URLs to clone"},
                    "dry_run": _DRY_RUN,
                },
                "required": ["template", "display_name"],
            },
        ),
        Tool(
            name="acp_delete_session",
            description="Delete an AgenticSession. Supports dry-run mode.",
            inputSchema={
                "type": "object",
                "properties": {"project": _PROJECT, "session": _SESSION, "dry_run": _DRY_RUN},
                "required": ["session"],
            },
        ),
        Tool(
            name="acp_restart_session",
            description="Restart a stopped session. Supports dry-run mode.",
            inputSchema={
                "type": "object",
                "properties": {"project": _PROJECT, "session": _SESSION, "dry_run": _DRY_RUN},
                "required": ["session"],
            },
        ),
        Tool(
            name="acp_clone_session",
            description="Clone an existing session's configuration into a new session.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": _PROJECT,
                    "source_session": {"type": "string", "description": "Session ID to clone from"},
                    "new_display_name": {"type": "string", "description": "Display name for the cloned session"},
                    "dry_run": _DRY_RUN,
                },
                "required": ["source_session", "new_display_name"],
            },
        ),
        Tool(
            name="acp_update_session",
            description="Update session metadata (display name, timeout). Supports dry-run mode.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": _PROJECT,
                    "session": _SESSION,
                    "display_name": {"type": "string", "description": "New display name"},
                    "timeout": {"type": "integer", "description": "New timeout in seconds", "minimum": 60},
                    "dry_run": _DRY_RUN,
                },
                "required": ["session"],
            },
        ),
        # ── Observability ────────────────────────────────────────────────
        Tool(
            name="acp_get_session_logs",
            description="Retrieve container logs for a session. Useful for debugging.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": _PROJECT,
                    "session": _SESSION,
                    "container": {"type": "string", "description": "Container name (optional)"},
                    "tail_lines": {
                        "type": "integer",
                        "description": "Number of log lines (default: 1000, max: 10000)",
                        "default": 1000,
                        "maximum": 10000,
                    },
                },
                "required": ["session"],
            },
        ),
        Tool(
            name="acp_get_session_transcript",
            description="Retrieve conversation history for a session in JSON or Markdown format.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": _PROJECT,
                    "session": _SESSION,
                    "format": {
                        "type": "string",
                        "description": "Output format",
                        "enum": ["json", "markdown"],
                        "default": "json",
                    },
                },
                "required": ["session"],
            },
        ),
        Tool(
            name="acp_get_session_metrics",
            description="Get usage statistics for a session (tokens, duration, tool calls).",
            inputSchema={
                "type": "object",
                "properties": {"project": _PROJECT, "session": _SESSION},
                "required": ["session"],
            },
        ),
        # ── Labels ───────────────────────────────────────────────────────
        Tool(
            name="acp_label_resource",
            description="Add labels to a session. Labels are key-value pairs for organizing and filtering.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": _PROJECT,
                    "name": {"type": "string", "description": "Session name"},
                    "resource_type": {
                        "type": "string",
                        "description": "Resource type",
                        "enum": ["agenticsession"],
                        "default": "agenticsession",
                    },
                    "labels": _LABELS_OBJECT,
                },
                "required": ["name", "labels"],
            },
        ),
        Tool(
            name="acp_unlabel_resource",
            description="Remove labels from a session by key.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": _PROJECT,
                    "name": {"type": "string", "description": "Session name"},
                    "resource_type": {
                        "type": "string",
                        "description": "Resource type",
                        "enum": ["agenticsession"],
                        "default": "agenticsession",
                    },
                    "label_keys": _LABEL_KEYS_ARRAY,
                },
                "required": ["name", "label_keys"],
            },
        ),
        Tool(
            name="acp_list_sessions_by_label",
            description="List sessions matching label selectors.",
            inputSchema={
                "type": "object",
                "properties": {"project": _PROJECT, "labels": _LABELS_OBJECT},
                "required": ["labels"],
            },
        ),
        Tool(
            name="acp_bulk_label_resources",
            description="Add labels to multiple sessions (max 3). DESTRUCTIVE: requires confirm=true.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": _PROJECT,
                    "sessions": _SESSIONS_ARRAY,
                    "labels": _LABELS_OBJECT,
                    "confirm": _CONFIRM,
                    "dry_run": _DRY_RUN,
                },
                "required": ["sessions", "labels"],
            },
        ),
        Tool(
            name="acp_bulk_unlabel_resources",
            description="Remove labels from multiple sessions (max 3). DESTRUCTIVE: requires confirm=true.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": _PROJECT,
                    "sessions": _SESSIONS_ARRAY,
                    "label_keys": _LABEL_KEYS_ARRAY,
                    "confirm": _CONFIRM,
                    "dry_run": _DRY_RUN,
                },
                "required": ["sessions", "label_keys"],
            },
        ),
        # ── Bulk Operations ──────────────────────────────────────────────
        Tool(
            name="acp_bulk_delete_sessions",
            description="Delete multiple sessions (max 3). DESTRUCTIVE: requires confirm=true. Use dry_run=true first!",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": _PROJECT,
                    "sessions": _SESSIONS_ARRAY,
                    "confirm": _CONFIRM,
                    "dry_run": _DRY_RUN,
                },
                "required": ["sessions"],
            },
        ),
        Tool(
            name="acp_bulk_stop_sessions",
            description="Stop multiple running sessions (max 3). DESTRUCTIVE: requires confirm=true.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": _PROJECT,
                    "sessions": _SESSIONS_ARRAY,
                    "confirm": _CONFIRM,
                    "dry_run": _DRY_RUN,
                },
                "required": ["sessions"],
            },
        ),
        Tool(
            name="acp_bulk_restart_sessions",
            description="Restart multiple stopped sessions (max 3). Requires confirm=true.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": _PROJECT,
                    "sessions": _SESSIONS_ARRAY,
                    "confirm": _CONFIRM,
                    "dry_run": _DRY_RUN,
                },
                "required": ["sessions"],
            },
        ),
        Tool(
            name="acp_bulk_delete_sessions_by_label",
            description="Delete sessions matching label selectors (max 3 matches). DESTRUCTIVE: requires confirm=true.",
            inputSchema={
                "type": "object",
                "properties": {"project": _PROJECT, "labels": _LABELS_OBJECT, "confirm": _CONFIRM, "dry_run": _DRY_RUN},
                "required": ["labels"],
            },
        ),
        Tool(
            name="acp_bulk_stop_sessions_by_label",
            description="Stop sessions matching label selectors (max 3 matches). DESTRUCTIVE: requires confirm=true.",
            inputSchema={
                "type": "object",
                "properties": {"project": _PROJECT, "labels": _LABELS_OBJECT, "confirm": _CONFIRM, "dry_run": _DRY_RUN},
                "required": ["labels"],
            },
        ),
        Tool(
            name="acp_bulk_restart_sessions_by_label",
            description="Restart sessions matching label selectors (max 3 matches). Requires confirm=true.",
            inputSchema={
                "type": "object",
                "properties": {"project": _PROJECT, "labels": _LABELS_OBJECT, "confirm": _CONFIRM, "dry_run": _DRY_RUN},
                "required": ["labels"],
            },
        ),
        # ── Cluster Management ───────────────────────────────────────────
        Tool(
            name="acp_list_clusters",
            description="List configured cluster aliases from clusters.yaml.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="acp_whoami",
            description="Get current configuration and authentication status.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="acp_switch_cluster",
            description="Switch to a different cluster context.",
            inputSchema={
                "type": "object",
                "properties": {"cluster": {"type": "string", "description": "Cluster alias name"}},
                "required": ["cluster"],
            },
        ),
        Tool(
            name="acp_login",
            description="Authenticate to a cluster with a Bearer token. Sets the token in memory and verifies it works.",
            inputSchema={
                "type": "object",
                "properties": {
                    "cluster": {"type": "string", "description": "Cluster alias name"},
                    "token": {"type": "string", "description": "Bearer token for authentication"},
                },
                "required": ["cluster"],
            },
        ),
    ]


TOOLS_WITHOUT_PROJECT = {
    "acp_list_clusters",
    "acp_whoami",
    "acp_switch_cluster",
    "acp_login",
}

# Tools that require confirm=true for non-dry-run execution
TOOLS_REQUIRING_CONFIRMATION = {
    "acp_bulk_delete_sessions",
    "acp_bulk_stop_sessions",
    "acp_bulk_restart_sessions",
    "acp_bulk_delete_sessions_by_label",
    "acp_bulk_stop_sessions_by_label",
    "acp_bulk_restart_sessions_by_label",
    "acp_bulk_label_resources",
    "acp_bulk_unlabel_resources",
}


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    import time

    start_time = time.time()

    safe_args = {k: v for k, v in arguments.items() if k not in ["token", "password", "secret"]}
    logger.info("tool_call_started", tool=name, arguments=safe_args)

    client = get_client()

    try:
        # Auto-fill project from default if not provided
        if name not in TOOLS_WITHOUT_PROJECT and not arguments.get("project"):
            cluster_name = client.clusters_config.default_cluster
            if cluster_name:
                cluster = client.clusters_config.clusters.get(cluster_name)
                if cluster and cluster.default_project:
                    arguments["project"] = cluster.default_project
                    logger.info("project_autofilled", project=cluster.default_project)

        # Confirmation enforcement for destructive bulk operations
        if name in TOOLS_REQUIRING_CONFIRMATION:
            if not arguments.get("dry_run") and not arguments.get("confirm"):
                op = name.replace("acp_bulk_", "").replace("_", " ")
                raise ValueError(f"Bulk {op} requires confirm=true. Use dry_run=true to preview first.")

        # ── Dispatch ─────────────────────────────────────────────────
        project = arguments.get("project", "")

        # Session management
        if name == "acp_list_sessions":
            result = await client.list_sessions(
                project=project,
                status=arguments.get("status"),
                older_than=arguments.get("older_than"),
                sort_by=arguments.get("sort_by"),
                limit=arguments.get("limit"),
            )
            text = format_sessions_list(result)

        elif name == "acp_get_session":
            result = await client.get_session(project=project, session=arguments["session"])
            text = format_result(result)

        elif name == "acp_create_session":
            result = await client.create_session(
                project=project,
                initial_prompt=arguments["initial_prompt"],
                display_name=arguments.get("display_name"),
                repos=arguments.get("repos"),
                interactive=arguments.get("interactive", False),
                model=arguments.get("model", "claude-sonnet-4"),
                timeout=arguments.get("timeout", 900),
                dry_run=arguments.get("dry_run", False),
            )
            text = format_session_created(result)

        elif name == "acp_create_session_from_template":
            result = await client.create_session_from_template(
                project=project,
                template=arguments["template"],
                display_name=arguments["display_name"],
                repos=arguments.get("repos"),
                dry_run=arguments.get("dry_run", False),
            )
            text = format_session_created(result)

        elif name == "acp_delete_session":
            result = await client.delete_session(
                project=project, session=arguments["session"], dry_run=arguments.get("dry_run", False)
            )
            text = format_result(result)

        elif name == "acp_restart_session":
            result = await client.restart_session(
                project=project, session=arguments["session"], dry_run=arguments.get("dry_run", False)
            )
            text = format_result(result)

        elif name == "acp_clone_session":
            result = await client.clone_session(
                project=project,
                source_session=arguments["source_session"],
                new_display_name=arguments["new_display_name"],
                dry_run=arguments.get("dry_run", False),
            )
            text = format_session_created(result)

        elif name == "acp_update_session":
            result = await client.update_session(
                project=project,
                session=arguments["session"],
                display_name=arguments.get("display_name"),
                timeout=arguments.get("timeout"),
                dry_run=arguments.get("dry_run", False),
            )
            text = format_result(result)

        # Observability
        elif name == "acp_get_session_logs":
            result = await client.get_session_logs(
                project=project,
                session=arguments["session"],
                container=arguments.get("container"),
                tail_lines=arguments.get("tail_lines", 1000),
            )
            text = format_logs(result)

        elif name == "acp_get_session_transcript":
            result = await client.get_session_transcript(
                project=project,
                session=arguments["session"],
                format=arguments.get("format", "json"),
            )
            text = format_transcript(result)

        elif name == "acp_get_session_metrics":
            result = await client.get_session_metrics(project=project, session=arguments["session"])
            text = format_metrics(result)

        # Labels
        elif name == "acp_label_resource":
            result = await client.label_session(project=project, session=arguments["name"], labels=arguments["labels"])
            text = format_labels(result)

        elif name == "acp_unlabel_resource":
            result = await client.unlabel_session(
                project=project, session=arguments["name"], label_keys=arguments["label_keys"]
            )
            text = format_labels(result)

        elif name == "acp_list_sessions_by_label":
            result = await client.list_sessions_by_label(project=project, labels=arguments["labels"])
            text = format_sessions_list(result)

        elif name == "acp_bulk_label_resources":
            result = await client.bulk_label_sessions(
                project=project,
                sessions=arguments["sessions"],
                labels=arguments["labels"],
                dry_run=arguments.get("dry_run", False),
            )
            text = format_labels(result)

        elif name == "acp_bulk_unlabel_resources":
            result = await client.bulk_unlabel_sessions(
                project=project,
                sessions=arguments["sessions"],
                label_keys=arguments["label_keys"],
                dry_run=arguments.get("dry_run", False),
            )
            text = format_labels(result)

        # Bulk operations (named)
        elif name == "acp_bulk_delete_sessions":
            result = await client.bulk_delete_sessions(
                project=project, sessions=arguments["sessions"], dry_run=arguments.get("dry_run", False)
            )
            text = format_bulk_result(result, "delete")

        elif name == "acp_bulk_stop_sessions":
            result = await client.bulk_stop_sessions(
                project=project, sessions=arguments["sessions"], dry_run=arguments.get("dry_run", False)
            )
            text = format_bulk_result(result, "stop")

        elif name == "acp_bulk_restart_sessions":
            result = await client.bulk_restart_sessions(
                project=project, sessions=arguments["sessions"], dry_run=arguments.get("dry_run", False)
            )
            text = format_bulk_result(result, "restart")

        # Bulk operations (by label)
        elif name == "acp_bulk_delete_sessions_by_label":
            result = await client.bulk_delete_sessions_by_label(
                project=project, labels=arguments["labels"], dry_run=arguments.get("dry_run", False)
            )
            text = format_bulk_result(result, "delete")

        elif name == "acp_bulk_stop_sessions_by_label":
            result = await client.bulk_stop_sessions_by_label(
                project=project, labels=arguments["labels"], dry_run=arguments.get("dry_run", False)
            )
            text = format_bulk_result(result, "stop")

        elif name == "acp_bulk_restart_sessions_by_label":
            result = await client.bulk_restart_sessions_by_label(
                project=project, labels=arguments["labels"], dry_run=arguments.get("dry_run", False)
            )
            text = format_bulk_result(result, "restart")

        # Cluster management
        elif name == "acp_list_clusters":
            result = client.list_clusters()
            text = format_clusters(result)

        elif name == "acp_whoami":
            result = await client.whoami()
            text = format_whoami(result)

        elif name == "acp_switch_cluster":
            result = await client.switch_cluster(arguments["cluster"])
            text = format_result(result)

        elif name == "acp_login":
            result = await client.login(cluster=arguments["cluster"], token=arguments.get("token"))
            text = format_login(result)

        else:
            logger.warning("unknown_tool_requested", tool=name)
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

        elapsed = time.time() - start_time
        logger.info("tool_call_completed", tool=name, elapsed_seconds=round(elapsed, 2))

        return [TextContent(type="text", text=text)]

    except ValueError as e:
        elapsed = time.time() - start_time
        logger.warning("tool_validation_error", tool=name, elapsed_seconds=round(elapsed, 2), error=str(e))
        return [TextContent(type="text", text=f"Validation Error: {str(e)}")]
    except TimeoutError as e:
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
