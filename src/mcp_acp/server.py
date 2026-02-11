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
    format_result,
    format_sessions_list,
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


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available ACP tools for managing AgenticSession resources."""
    return [
        Tool(
            name="acp_list_sessions",
            description="List and filter AgenticSessions in a project. Filter by status (running/stopped/failed), age. Sort and limit results.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {
                        "type": "string",
                        "description": "Project/namespace name (uses default if not provided)",
                    },
                    "status": {
                        "type": "string",
                        "description": "Filter by status",
                        "enum": ["running", "stopped", "creating", "failed"],
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
                "required": [],
            },
        ),
        Tool(
            name="acp_get_session",
            description="Get details of a specific session by ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {
                        "type": "string",
                        "description": "Project/namespace name (uses default if not provided)",
                    },
                    "session": {
                        "type": "string",
                        "description": "Session ID",
                    },
                },
                "required": ["session"],
            },
        ),
        Tool(
            name="acp_delete_session",
            description="Delete an AgenticSession. Supports dry-run mode for preview.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {
                        "type": "string",
                        "description": "Project/namespace name (uses default if not provided)",
                    },
                    "session": {
                        "type": "string",
                        "description": "Session name",
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "Preview without deleting (default: false)",
                        "default": False,
                    },
                },
                "required": ["session"],
            },
        ),
        Tool(
            name="acp_bulk_delete_sessions",
            description="Delete multiple sessions (max 3). DESTRUCTIVE: requires confirm=true. Use dry_run=true first!",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {
                        "type": "string",
                        "description": "Project/namespace name (uses default if not provided)",
                    },
                    "sessions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of session names",
                    },
                    "confirm": {
                        "type": "boolean",
                        "description": "Required for destructive operations (default: false)",
                        "default": False,
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "Preview without deleting (default: false)",
                        "default": False,
                    },
                },
                "required": ["sessions"],
            },
        ),
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
                "properties": {
                    "cluster": {
                        "type": "string",
                        "description": "Cluster alias name",
                    },
                },
                "required": ["cluster"],
            },
        ),
    ]


TOOLS_WITHOUT_PROJECT = {
    "acp_list_clusters",
    "acp_whoami",
    "acp_switch_cluster",
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

        # Dispatch to handler
        if name == "acp_list_sessions":
            result = await client.list_sessions(
                project=arguments.get("project", ""),
                status=arguments.get("status"),
                older_than=arguments.get("older_than"),
                sort_by=arguments.get("sort_by"),
                limit=arguments.get("limit"),
            )
            text = format_sessions_list(result)

        elif name == "acp_get_session":
            result = await client.get_session(
                project=arguments.get("project", ""),
                session=arguments["session"],
            )
            text = format_result(result)

        elif name == "acp_delete_session":
            result = await client.delete_session(
                project=arguments.get("project", ""),
                session=arguments["session"],
                dry_run=arguments.get("dry_run", False),
            )
            text = format_result(result)

        elif name == "acp_bulk_delete_sessions":
            if not arguments.get("dry_run") and not arguments.get("confirm"):
                raise ValueError("Bulk delete requires confirm=true. Use dry_run=true to preview first.")
            result = await client.bulk_delete_sessions(
                project=arguments.get("project", ""),
                sessions=arguments["sessions"],
                dry_run=arguments.get("dry_run", False),
            )
            text = format_bulk_result(result, "delete")

        elif name == "acp_list_clusters":
            result = client.list_clusters()
            text = format_clusters(result)

        elif name == "acp_whoami":
            result = await client.whoami()
            text = format_whoami(result)

        elif name == "acp_switch_cluster":
            result = await client.switch_cluster(arguments["cluster"])
            text = format_result(result)

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
