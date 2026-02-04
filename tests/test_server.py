"""Tests for MCP server."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_acp.formatters import (
    format_bulk_result,
    format_clusters,
    format_logs,
    format_result,
    format_sessions_list,
    format_whoami,
)
from mcp_acp.server import call_tool, list_tools


class TestServerFormatters:
    """Tests for server formatting functions."""

    def test_format_result_dry_run(self) -> None:
        """Test formatting dry run results."""
        result = {
            "dry_run": True,
            "message": "Would delete session",
            "session_info": {"name": "test-session", "status": "running"},
        }

        output = format_result(result)

        assert "DRY RUN MODE" in output
        assert "Would delete session" in output
        assert "test-session" in output

    def test_format_result_normal(self) -> None:
        """Test formatting normal results."""
        result = {"deleted": True, "message": "Successfully deleted session"}

        output = format_result(result)

        assert "Successfully deleted session" in output

    def test_format_sessions_list(self) -> None:
        """Test formatting sessions list."""
        result = {
            "total": 2,
            "filters_applied": {"status": "running"},
            "sessions": [
                {
                    "metadata": {
                        "name": "session-1",
                        "creationTimestamp": "2024-01-20T10:00:00Z",
                    },
                    "spec": {"displayName": "Test Session"},
                    "status": {"phase": "running"},
                },
                {
                    "metadata": {
                        "name": "session-2",
                        "creationTimestamp": "2024-01-21T10:00:00Z",
                    },
                    "spec": {},
                    "status": {"phase": "running"},
                },
            ],
        }

        output = format_sessions_list(result)

        assert "Found 2 session(s)" in output
        assert "session-1" in output
        assert "Test Session" in output
        assert "session-2" in output
        assert "running" in output

    def test_format_bulk_result_delete_dry_run(self) -> None:
        """Test formatting bulk delete dry run."""
        result = {
            "dry_run": True,
            "dry_run_info": {
                "would_delete": [
                    {"session": "session-1", "info": {"status": "stopped"}},
                    {"session": "session-2", "info": {"status": "stopped"}},
                ],
                "not_found": ["session-3"],
            },
        }

        output = format_bulk_result(result, "delete")

        assert "DRY RUN MODE" in output
        assert "Would delete 2 session(s)" in output
        assert "session-1" in output
        assert "session-2" in output
        assert "Not found" in output
        assert "session-3" in output

    def test_format_bulk_result_delete_normal(self) -> None:
        """Test formatting bulk delete normal mode."""
        result = {
            "deleted": ["session-1", "session-2"],
            "failed": [{"session": "session-3", "error": "Not found"}],
        }

        output = format_bulk_result(result, "delete")

        assert "Successfully deleted 2 session(s)" in output
        assert "session-1" in output
        assert "session-2" in output
        assert "Failed" in output
        assert "session-3" in output
        assert "Not found" in output

    def test_format_bulk_result_stop_dry_run(self) -> None:
        """Test formatting bulk stop dry run."""
        result = {
            "dry_run": True,
            "dry_run_info": {
                "would_stop": [
                    {"session": "session-1", "current_status": "running"},
                ],
                "not_running": [
                    {"session": "session-2", "current_status": "stopped"},
                ],
            },
        }

        output = format_bulk_result(result, "stop")

        assert "DRY RUN MODE" in output
        assert "Would stop 1 session(s)" in output
        assert "session-1" in output
        assert "Not running" in output
        assert "session-2" in output

    def test_format_logs(self) -> None:
        """Test formatting logs."""
        result = {
            "logs": "2024-01-20 10:00:00 INFO Starting\n2024-01-20 10:00:01 INFO Ready\n",
            "container": "runner",
            "lines": 3,
        }

        output = format_logs(result)

        assert "container 'runner'" in output
        assert "3 lines" in output
        assert "Starting" in output
        assert "Ready" in output

    def test_format_logs_error(self) -> None:
        """Test formatting logs with error."""
        result = {"error": "Pod not found"}

        output = format_logs(result)

        assert "Error: Pod not found" in output

    def test_format_clusters(self) -> None:
        """Test formatting clusters list."""
        result = {
            "clusters": [
                {
                    "name": "test-cluster",
                    "server": "https://api.test.example.com:443",
                    "description": "Test Cluster",
                    "default_project": "test-workspace",
                    "is_default": True,
                },
                {
                    "name": "prod-cluster",
                    "server": "https://api.prod.example.com:443",
                    "description": "Production Cluster",
                    "default_project": "prod-workspace",
                    "is_default": False,
                },
            ],
            "default_cluster": "test-cluster",
        }

        output = format_clusters(result)

        assert "test-cluster [DEFAULT]" in output
        assert "prod-cluster" in output
        assert "Test Cluster" in output
        assert "Production Cluster" in output
        assert "https://api.test.example.com:443" in output

    def test_format_clusters_empty(self) -> None:
        """Test formatting empty clusters list."""
        result = {"clusters": [], "default_cluster": None}

        output = format_clusters(result)

        assert "No clusters configured" in output

    def test_format_whoami_authenticated(self) -> None:
        """Test formatting whoami when authenticated."""
        result = {
            "authenticated": True,
            "user": "testuser",
            "server": "https://api.test.example.com:443",
            "project": "test-workspace",
            "token_valid": True,
        }

        output = format_whoami(result)

        assert "Authenticated: Yes" in output
        assert "User: testuser" in output
        assert "Server: https://api.test.example.com:443" in output
        assert "Project: test-workspace" in output
        assert "Token Valid: Yes" in output

    def test_format_whoami_not_authenticated(self) -> None:
        """Test formatting whoami when not authenticated."""
        result = {
            "authenticated": False,
            "user": "unknown",
            "server": "unknown",
            "project": "unknown",
            "token_valid": False,
        }

        output = format_whoami(result)

        assert "Authenticated: No" in output
        assert "not authenticated" in output


class TestServerTools:
    """Tests for server tool handling."""

    @pytest.mark.asyncio
    async def test_list_tools(self) -> None:
        """Test listing available tools."""
        tools = await list_tools()

        tool_names = [t.name for t in tools]

        # Check P0 tools
        assert "acp_delete_session" in tool_names
        assert "acp_list_sessions" in tool_names

        # Check P1 tools
        assert "acp_restart_session" in tool_names
        assert "acp_bulk_delete_sessions" in tool_names
        assert "acp_bulk_stop_sessions" in tool_names
        assert "acp_get_session_logs" in tool_names
        assert "acp_list_clusters" in tool_names
        assert "acp_whoami" in tool_names

    @pytest.mark.asyncio
    async def test_call_tool_delete_session(self) -> None:
        """Test calling delete session tool."""
        mock_client = MagicMock()
        mock_client.delete_session = AsyncMock(return_value={"deleted": True, "message": "Success"})

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool(
                "acp_delete_session",
                {"project": "test-project", "session": "test-session"},
            )

            assert len(result) == 1
            assert "Success" in result[0].text

            mock_client.delete_session.assert_called_once_with(
                project="test-project", session="test-session", dry_run=False
            )

    @pytest.mark.asyncio
    async def test_call_tool_list_sessions(self) -> None:
        """Test calling list sessions tool."""
        mock_client = MagicMock()
        mock_client.list_sessions = AsyncMock(
            return_value={
                "total": 1,
                "filters_applied": {},
                "sessions": [
                    {
                        "metadata": {"name": "test-session"},
                        "spec": {},
                        "status": {"phase": "running"},
                    }
                ],
            }
        )

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool(
                "acp_list_sessions",
                {"project": "test-project", "status": "running"},
            )

            assert len(result) == 1
            assert "test-session" in result[0].text

            mock_client.list_sessions.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_tool_restart_session(self) -> None:
        """Test calling restart session tool."""
        mock_client = MagicMock()
        mock_client.restart_session = AsyncMock(return_value={"status": "restarting", "message": "Success"})

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool(
                "acp_restart_session",
                {"project": "test-project", "session": "test-session", "dry_run": True},
            )

            assert len(result) == 1

            mock_client.restart_session.assert_called_once_with(
                project="test-project", session="test-session", dry_run=True
            )

    @pytest.mark.asyncio
    async def test_call_tool_bulk_delete(self) -> None:
        """Test calling bulk delete tool."""
        mock_client = MagicMock()
        mock_client.bulk_delete_sessions = AsyncMock(return_value={"deleted": ["s1", "s2"], "failed": []})

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool(
                "acp_bulk_delete_sessions",
                {
                    "project": "test-project",
                    "sessions": ["s1", "s2"],
                },
            )

            assert len(result) == 1
            assert "Successfully deleted 2 session(s)" in result[0].text

    @pytest.mark.asyncio
    async def test_call_tool_bulk_stop(self) -> None:
        """Test calling bulk stop tool."""
        mock_client = MagicMock()
        mock_client.bulk_stop_sessions = AsyncMock(return_value={"stopped": ["s1", "s2"], "failed": []})

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool(
                "acp_bulk_stop_sessions",
                {
                    "project": "test-project",
                    "sessions": ["s1", "s2"],
                },
            )

            assert len(result) == 1
            assert "Successfully stopd 2 session(s)" in result[0].text

    @pytest.mark.asyncio
    async def test_call_tool_get_logs(self) -> None:
        """Test calling get logs tool."""
        mock_client = MagicMock()
        mock_client.get_session_logs = AsyncMock(
            return_value={
                "logs": "test logs",
                "container": "runner",
                "lines": 1,
            }
        )

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool(
                "acp_get_session_logs",
                {
                    "project": "test-project",
                    "session": "test-session",
                    "tail_lines": 100,
                },
            )

            assert len(result) == 1
            assert "test logs" in result[0].text

    @pytest.mark.asyncio
    async def test_call_tool_list_clusters(self) -> None:
        """Test calling list clusters tool."""
        mock_client = MagicMock()
        mock_client.list_clusters = MagicMock(
            return_value={
                "clusters": [
                    {
                        "name": "test",
                        "server": "https://test.com",
                        "is_default": True,
                    }
                ],
                "default_cluster": "test",
            }
        )

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool("acp_list_clusters", {})

            assert len(result) == 1
            assert "test" in result[0].text

    @pytest.mark.asyncio
    async def test_call_tool_whoami(self) -> None:
        """Test calling whoami tool."""
        mock_client = MagicMock()
        mock_client.whoami = AsyncMock(
            return_value={
                "authenticated": True,
                "user": "testuser",
                "server": "https://test.com",
                "project": "test-project",
                "token_valid": True,
            }
        )

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool("acp_whoami", {})

            assert len(result) == 1
            assert "testuser" in result[0].text

    @pytest.mark.asyncio
    async def test_call_tool_error_handling(self) -> None:
        """Test tool error handling."""
        mock_client = MagicMock()
        mock_client.delete_session = AsyncMock(side_effect=Exception("Test error"))

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool(
                "acp_delete_session",
                {"project": "test-project", "session": "test-session"},
            )

            assert len(result) == 1
            assert "Error: Test error" in result[0].text

    @pytest.mark.asyncio
    async def test_call_tool_unknown(self) -> None:
        """Test calling unknown tool."""
        mock_client = MagicMock()

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool("unknown_tool", {})

            assert len(result) == 1
            assert "Unknown tool" in result[0].text
