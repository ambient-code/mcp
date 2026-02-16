"""Tests for MCP server."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_acp.server import call_tool, list_tools


class TestListTools:
    """Tests for list_tools."""

    @pytest.mark.asyncio
    async def test_list_tools_returns_all_tools(self) -> None:
        """Test listing available tools."""
        tools = await list_tools()
        tool_names = [t.name for t in tools]

        # Session management tools
        assert "acp_list_sessions" in tool_names
        assert "acp_get_session" in tool_names
        assert "acp_create_session" in tool_names
        assert "acp_create_session_from_template" in tool_names
        assert "acp_delete_session" in tool_names
        assert "acp_restart_session" in tool_names
        assert "acp_clone_session" in tool_names
        assert "acp_update_session" in tool_names
        assert "acp_stop_session" not in tool_names  # stop is via PATCH, no dedicated tool name

        # Observability tools
        assert "acp_get_session_logs" in tool_names
        assert "acp_get_session_transcript" in tool_names
        assert "acp_get_session_metrics" in tool_names

        # Label tools
        assert "acp_label_resource" in tool_names
        assert "acp_unlabel_resource" in tool_names
        assert "acp_list_sessions_by_label" in tool_names
        assert "acp_bulk_label_resources" in tool_names
        assert "acp_bulk_unlabel_resources" in tool_names

        # Bulk operation tools
        assert "acp_bulk_delete_sessions" in tool_names
        assert "acp_bulk_stop_sessions" in tool_names
        assert "acp_bulk_restart_sessions" in tool_names
        assert "acp_bulk_delete_sessions_by_label" in tool_names
        assert "acp_bulk_stop_sessions_by_label" in tool_names
        assert "acp_bulk_restart_sessions_by_label" in tool_names

        # Cluster tools
        assert "acp_list_clusters" in tool_names
        assert "acp_whoami" in tool_names
        assert "acp_switch_cluster" in tool_names
        assert "acp_login" in tool_names

    @pytest.mark.asyncio
    async def test_list_tools_count(self) -> None:
        """Test correct number of tools."""
        tools = await list_tools()
        assert len(tools) == 26


class TestCallTool:
    """Tests for call_tool."""

    @pytest.mark.asyncio
    async def test_call_tool_list_sessions(self) -> None:
        """Test calling list sessions tool."""
        mock_client = MagicMock()
        mock_client.clusters_config = MagicMock()
        mock_client.clusters_config.default_cluster = "test"
        mock_client.clusters_config.clusters = {"test": MagicMock(default_project="test-project")}
        mock_client.list_sessions = AsyncMock(
            return_value={
                "total": 1,
                "filters_applied": {},
                "sessions": [{"id": "test-session", "status": "running", "createdAt": "2024-01-01T00:00:00Z"}],
            }
        )

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool("acp_list_sessions", {"project": "test-project"})

            assert len(result) == 1
            assert "test-session" in result[0].text

    @pytest.mark.asyncio
    async def test_call_tool_delete_session(self) -> None:
        """Test calling delete session tool."""
        mock_client = MagicMock()
        mock_client.clusters_config = MagicMock()
        mock_client.clusters_config.default_cluster = "test"
        mock_client.clusters_config.clusters = {"test": MagicMock(default_project="test-project")}
        mock_client.delete_session = AsyncMock(return_value={"deleted": True, "message": "Success"})

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool("acp_delete_session", {"project": "test-project", "session": "test-session"})

            assert len(result) == 1
            assert "Success" in result[0].text

    @pytest.mark.asyncio
    async def test_call_tool_create_session(self) -> None:
        """Test calling create session tool."""
        mock_client = MagicMock()
        mock_client.clusters_config = MagicMock()
        mock_client.clusters_config.default_cluster = "test"
        mock_client.clusters_config.clusters = {"test": MagicMock(default_project="test-project")}
        mock_client.create_session = AsyncMock(
            return_value={
                "created": True,
                "session": "compiled-abc12",
                "project": "test-project",
                "message": "Session 'compiled-abc12' created in project 'test-project'",
            }
        )

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool(
                "acp_create_session",
                {"project": "test-project", "initial_prompt": "Run tests"},
            )

            assert len(result) == 1
            assert "compiled-abc12" in result[0].text

    @pytest.mark.asyncio
    async def test_call_tool_bulk_delete_requires_confirm(self) -> None:
        """Test bulk delete requires confirm flag."""
        mock_client = MagicMock()
        mock_client.clusters_config = MagicMock()
        mock_client.clusters_config.default_cluster = "test"
        mock_client.clusters_config.clusters = {"test": MagicMock(default_project="test-project")}

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool(
                "acp_bulk_delete_sessions",
                {"project": "test-project", "sessions": ["s1", "s2"]},
            )

            assert "requires confirm=true" in result[0].text

    @pytest.mark.asyncio
    async def test_call_tool_bulk_delete_with_confirm(self) -> None:
        """Test bulk delete with confirm flag."""
        mock_client = MagicMock()
        mock_client.clusters_config = MagicMock()
        mock_client.clusters_config.default_cluster = "test"
        mock_client.clusters_config.clusters = {"test": MagicMock(default_project="test-project")}
        mock_client.bulk_delete_sessions = AsyncMock(return_value={"deleted": ["s1", "s2"], "failed": []})

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool(
                "acp_bulk_delete_sessions",
                {"project": "test-project", "sessions": ["s1", "s2"], "confirm": True},
            )

            assert len(result) == 1
            assert "Successfully deleted 2" in result[0].text

    @pytest.mark.asyncio
    async def test_call_tool_list_clusters(self) -> None:
        """Test calling list clusters tool."""
        mock_client = MagicMock()
        mock_client.clusters_config = MagicMock()
        mock_client.clusters_config.default_cluster = "test"
        mock_client.clusters_config.clusters = {}
        mock_client.list_clusters = MagicMock(
            return_value={
                "clusters": [{"name": "test", "server": "https://test.com", "is_default": True}],
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
        mock_client.clusters_config = MagicMock()
        mock_client.clusters_config.default_cluster = "test"
        mock_client.clusters_config.clusters = {}
        mock_client.whoami = AsyncMock(
            return_value={
                "authenticated": True,
                "cluster": "test",
                "server": "https://test.com",
                "project": "test-project",
                "token_valid": True,
            }
        )

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool("acp_whoami", {})

            assert len(result) == 1
            assert "test" in result[0].text

    @pytest.mark.asyncio
    async def test_call_tool_switch_cluster(self) -> None:
        """Test calling switch cluster tool."""
        mock_client = MagicMock()
        mock_client.clusters_config = MagicMock()
        mock_client.clusters_config.default_cluster = "test"
        mock_client.clusters_config.clusters = {}
        mock_client.switch_cluster = AsyncMock(
            return_value={"switched": True, "previous": "old", "current": "new", "message": "Switched"}
        )

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool("acp_switch_cluster", {"cluster": "new"})

            assert len(result) == 1
            assert "Switched" in result[0].text

    @pytest.mark.asyncio
    async def test_call_tool_unknown(self) -> None:
        """Test calling unknown tool."""
        mock_client = MagicMock()
        mock_client.clusters_config = MagicMock()
        mock_client.clusters_config.default_cluster = "test"
        mock_client.clusters_config.clusters = {}

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool("unknown_tool", {})

            assert len(result) == 1
            assert "Unknown tool" in result[0].text

    @pytest.mark.asyncio
    async def test_call_tool_error_handling(self) -> None:
        """Test tool error handling."""
        mock_client = MagicMock()
        mock_client.clusters_config = MagicMock()
        mock_client.clusters_config.default_cluster = "test"
        mock_client.clusters_config.clusters = {"test": MagicMock(default_project="test-project")}
        mock_client.delete_session = AsyncMock(side_effect=ValueError("Test error"))

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool("acp_delete_session", {"project": "test-project", "session": "test"})

            assert len(result) == 1
            assert "Test error" in result[0].text


class TestCallToolBulkStop:
    """Tests for bulk stop tool dispatch."""

    @pytest.mark.asyncio
    async def test_bulk_stop_requires_confirm(self) -> None:
        """Bulk stop without confirm should return validation error."""
        mock_client = MagicMock()
        mock_client.clusters_config = MagicMock()
        mock_client.clusters_config.default_cluster = "test"
        mock_client.clusters_config.clusters = {"test": MagicMock(default_project="test-project")}

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool(
                "acp_bulk_stop_sessions",
                {"project": "test-project", "sessions": ["s1", "s2"]},
            )

            assert "requires confirm=true" in result[0].text

    @pytest.mark.asyncio
    async def test_bulk_stop_with_confirm(self) -> None:
        """Bulk stop with confirm should dispatch to client."""
        mock_client = MagicMock()
        mock_client.clusters_config = MagicMock()
        mock_client.clusters_config.default_cluster = "test"
        mock_client.clusters_config.clusters = {"test": MagicMock(default_project="test-project")}
        mock_client.bulk_stop_sessions = AsyncMock(return_value={"stopped": ["s1", "s2"], "failed": []})

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool(
                "acp_bulk_stop_sessions",
                {"project": "test-project", "sessions": ["s1", "s2"], "confirm": True},
            )

            assert "Successfully stopped 2" in result[0].text


class TestCallToolRestartSession:
    """Tests for restart session tool dispatch."""

    @pytest.mark.asyncio
    async def test_restart_session_dispatch(self) -> None:
        """Restart session should dispatch to client.restart_session."""
        mock_client = MagicMock()
        mock_client.clusters_config = MagicMock()
        mock_client.clusters_config.default_cluster = "test"
        mock_client.clusters_config.clusters = {"test": MagicMock(default_project="test-project")}
        mock_client.restart_session = AsyncMock(
            return_value={"restarted": True, "message": "Successfully restarted session 's1'"}
        )

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool(
                "acp_restart_session",
                {"project": "test-project", "session": "s1"},
            )

            assert len(result) == 1
            assert "Successfully restarted" in result[0].text


class TestCallToolLogin:
    """Tests for login tool dispatch."""

    @pytest.mark.asyncio
    async def test_login_dispatch(self) -> None:
        """Login should dispatch to client.login."""
        mock_client = MagicMock()
        mock_client.clusters_config = MagicMock()
        mock_client.clusters_config.default_cluster = "test"
        mock_client.clusters_config.clusters = {}
        mock_client.login = AsyncMock(
            return_value={
                "authenticated": True,
                "cluster": "test",
                "server": "https://test.com",
                "message": "Successfully authenticated to cluster 'test'",
            }
        )

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool(
                "acp_login",
                {"cluster": "test", "token": "my-token"},
            )

            assert len(result) == 1
            assert "Authentication successful" in result[0].text
