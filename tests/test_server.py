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


class TestCallToolGetSession:
    """Tests for get session tool dispatch."""

    @pytest.mark.asyncio
    async def test_get_session_dispatch(self) -> None:
        """Get session should dispatch to client.get_session."""
        mock_client = MagicMock()
        mock_client.clusters_config = MagicMock()
        mock_client.clusters_config.default_cluster = "test"
        mock_client.clusters_config.clusters = {"test": MagicMock(default_project="test-project")}
        mock_client.get_session = AsyncMock(
            return_value={"id": "session-1", "status": "running", "displayName": "My Session"}
        )

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool("acp_get_session", {"project": "test-project", "session": "session-1"})

            assert len(result) == 1
            assert "session-1" in result[0].text


class TestCallToolCreateSessionFromTemplate:
    """Tests for create session from template tool dispatch."""

    @pytest.mark.asyncio
    async def test_create_from_template_dispatch(self) -> None:
        """Should dispatch to client.create_session_from_template."""
        mock_client = MagicMock()
        mock_client.clusters_config = MagicMock()
        mock_client.clusters_config.default_cluster = "test"
        mock_client.clusters_config.clusters = {"test": MagicMock(default_project="test-project")}
        mock_client.create_session_from_template = AsyncMock(
            return_value={
                "created": True,
                "session": "template-abc12",
                "project": "test-project",
                "template": "bugfix",
                "message": "Session 'template-abc12' created from template 'bugfix'",
            }
        )

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool(
                "acp_create_session_from_template",
                {"project": "test-project", "template": "bugfix", "display_name": "Fix bug"},
            )

            assert len(result) == 1
            assert "template-abc12" in result[0].text


class TestCallToolCloneSession:
    """Tests for clone session tool dispatch."""

    @pytest.mark.asyncio
    async def test_clone_session_dispatch(self) -> None:
        """Should dispatch to client.clone_session."""
        mock_client = MagicMock()
        mock_client.clusters_config = MagicMock()
        mock_client.clusters_config.default_cluster = "test"
        mock_client.clusters_config.clusters = {"test": MagicMock(default_project="test-project")}
        mock_client.clone_session = AsyncMock(
            return_value={
                "created": True,
                "session": "cloned-abc12",
                "source_session": "source-1",
                "project": "test-project",
                "message": "Session 'cloned-abc12' cloned from 'source-1'",
            }
        )

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool(
                "acp_clone_session",
                {"project": "test-project", "source_session": "source-1", "new_display_name": "my-clone"},
            )

            assert len(result) == 1
            assert "cloned-abc12" in result[0].text


class TestCallToolUpdateSession:
    """Tests for update session tool dispatch."""

    @pytest.mark.asyncio
    async def test_update_session_dispatch(self) -> None:
        """Should dispatch to client.update_session."""
        mock_client = MagicMock()
        mock_client.clusters_config = MagicMock()
        mock_client.clusters_config.default_cluster = "test"
        mock_client.clusters_config.clusters = {"test": MagicMock(default_project="test-project")}
        mock_client.update_session = AsyncMock(
            return_value={
                "updated": True,
                "message": "Successfully updated session 'session-1'",
                "session": {"id": "session-1"},
            }
        )

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool(
                "acp_update_session",
                {"project": "test-project", "session": "session-1", "display_name": "new-name"},
            )

            assert len(result) == 1
            assert "updated" in result[0].text.lower()


class TestCallToolObservability:
    """Tests for observability tool dispatch (logs, transcript, metrics)."""

    @pytest.mark.asyncio
    async def test_get_session_logs_dispatch(self) -> None:
        """Should dispatch to client.get_session_logs."""
        mock_client = MagicMock()
        mock_client.clusters_config = MagicMock()
        mock_client.clusters_config.default_cluster = "test"
        mock_client.clusters_config.clusters = {"test": MagicMock(default_project="test-project")}
        mock_client.get_session_logs = AsyncMock(
            return_value={"logs": "INFO: started\nINFO: running", "session": "session-1", "tail_lines": 1000}
        )

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool(
                "acp_get_session_logs",
                {"project": "test-project", "session": "session-1"},
            )

            assert len(result) == 1
            assert "started" in result[0].text

    @pytest.mark.asyncio
    async def test_get_session_transcript_dispatch(self) -> None:
        """Should dispatch to client.get_session_transcript."""
        mock_client = MagicMock()
        mock_client.clusters_config = MagicMock()
        mock_client.clusters_config.default_cluster = "test"
        mock_client.clusters_config.clusters = {"test": MagicMock(default_project="test-project")}
        mock_client.get_session_transcript = AsyncMock(
            return_value={
                "session": "session-1",
                "format": "json",
                "messages": [{"role": "user", "content": "hello"}],
            }
        )

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool(
                "acp_get_session_transcript",
                {"project": "test-project", "session": "session-1"},
            )

            assert len(result) == 1
            assert "hello" in result[0].text

    @pytest.mark.asyncio
    async def test_get_session_metrics_dispatch(self) -> None:
        """Should dispatch to client.get_session_metrics."""
        mock_client = MagicMock()
        mock_client.clusters_config = MagicMock()
        mock_client.clusters_config.default_cluster = "test"
        mock_client.clusters_config.clusters = {"test": MagicMock(default_project="test-project")}
        mock_client.get_session_metrics = AsyncMock(
            return_value={"session": "session-1", "total_tokens": 5000, "duration_seconds": 120, "tool_calls": 15}
        )

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool(
                "acp_get_session_metrics",
                {"project": "test-project", "session": "session-1"},
            )

            assert len(result) == 1
            assert "5000" in result[0].text or "5,000" in result[0].text


class TestCallToolLabels:
    """Tests for label tool dispatch."""

    @pytest.mark.asyncio
    async def test_label_resource_dispatch(self) -> None:
        """Should dispatch to client.label_session."""
        mock_client = MagicMock()
        mock_client.clusters_config = MagicMock()
        mock_client.clusters_config.default_cluster = "test"
        mock_client.clusters_config.clusters = {"test": MagicMock(default_project="test-project")}
        mock_client.label_session = AsyncMock(
            return_value={"labeled": True, "labels_added": {"env": "test"}, "message": "Added 1 label(s)"}
        )

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool(
                "acp_label_resource",
                {"project": "test-project", "name": "session-1", "labels": {"env": "test"}},
            )

            assert len(result) == 1
            assert "label" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_unlabel_resource_dispatch(self) -> None:
        """Should dispatch to client.unlabel_session."""
        mock_client = MagicMock()
        mock_client.clusters_config = MagicMock()
        mock_client.clusters_config.default_cluster = "test"
        mock_client.clusters_config.clusters = {"test": MagicMock(default_project="test-project")}
        mock_client.unlabel_session = AsyncMock(
            return_value={"unlabeled": True, "labels_removed": ["env"], "message": "Removed 1 label(s)"}
        )

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool(
                "acp_unlabel_resource",
                {"project": "test-project", "name": "session-1", "label_keys": ["env"]},
            )

            assert len(result) == 1
            assert "label" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_list_sessions_by_label_dispatch(self) -> None:
        """Should dispatch to client.list_sessions_by_label."""
        mock_client = MagicMock()
        mock_client.clusters_config = MagicMock()
        mock_client.clusters_config.default_cluster = "test"
        mock_client.clusters_config.clusters = {"test": MagicMock(default_project="test-project")}
        mock_client.list_sessions_by_label = AsyncMock(
            return_value={
                "total": 1,
                "sessions": [{"id": "session-1", "status": "running", "createdAt": "2024-01-01T00:00:00Z"}],
                "labels_filter": {"env": "test"},
            }
        )

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool(
                "acp_list_sessions_by_label",
                {"project": "test-project", "labels": {"env": "test"}},
            )

            assert len(result) == 1
            assert "session-1" in result[0].text


class TestCallToolBulkLabels:
    """Tests for bulk label/unlabel tool dispatch."""

    @pytest.mark.asyncio
    async def test_bulk_label_requires_confirm(self) -> None:
        """Bulk label without confirm should return validation error."""
        mock_client = MagicMock()
        mock_client.clusters_config = MagicMock()
        mock_client.clusters_config.default_cluster = "test"
        mock_client.clusters_config.clusters = {"test": MagicMock(default_project="test-project")}

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool(
                "acp_bulk_label_resources",
                {"project": "test-project", "sessions": ["s1"], "labels": {"env": "test"}},
            )

            assert "requires confirm=true" in result[0].text

    @pytest.mark.asyncio
    async def test_bulk_label_with_confirm(self) -> None:
        """Bulk label with confirm should dispatch to client."""
        mock_client = MagicMock()
        mock_client.clusters_config = MagicMock()
        mock_client.clusters_config.default_cluster = "test"
        mock_client.clusters_config.clusters = {"test": MagicMock(default_project="test-project")}
        mock_client.bulk_label_sessions = AsyncMock(
            return_value={"labeled": ["s1"], "failed": [], "labels": {"env": "test"}}
        )

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool(
                "acp_bulk_label_resources",
                {"project": "test-project", "sessions": ["s1"], "labels": {"env": "test"}, "confirm": True},
            )

            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_bulk_unlabel_requires_confirm(self) -> None:
        """Bulk unlabel without confirm should return validation error."""
        mock_client = MagicMock()
        mock_client.clusters_config = MagicMock()
        mock_client.clusters_config.default_cluster = "test"
        mock_client.clusters_config.clusters = {"test": MagicMock(default_project="test-project")}

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool(
                "acp_bulk_unlabel_resources",
                {"project": "test-project", "sessions": ["s1"], "label_keys": ["env"]},
            )

            assert "requires confirm=true" in result[0].text

    @pytest.mark.asyncio
    async def test_bulk_unlabel_with_confirm(self) -> None:
        """Bulk unlabel with confirm should dispatch to client."""
        mock_client = MagicMock()
        mock_client.clusters_config = MagicMock()
        mock_client.clusters_config.default_cluster = "test"
        mock_client.clusters_config.clusters = {"test": MagicMock(default_project="test-project")}
        mock_client.bulk_unlabel_sessions = AsyncMock(
            return_value={"unlabeled": ["s1"], "failed": [], "label_keys": ["env"]}
        )

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool(
                "acp_bulk_unlabel_resources",
                {"project": "test-project", "sessions": ["s1"], "label_keys": ["env"], "confirm": True},
            )

            assert len(result) == 1


class TestCallToolBulkByLabel:
    """Tests for bulk-by-label tool dispatch."""

    @pytest.mark.asyncio
    async def test_bulk_restart_requires_confirm(self) -> None:
        """Bulk restart without confirm should return validation error."""
        mock_client = MagicMock()
        mock_client.clusters_config = MagicMock()
        mock_client.clusters_config.default_cluster = "test"
        mock_client.clusters_config.clusters = {"test": MagicMock(default_project="test-project")}

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool(
                "acp_bulk_restart_sessions",
                {"project": "test-project", "sessions": ["s1", "s2"], "confirm": False},
            )

            assert "requires confirm=true" in result[0].text

    @pytest.mark.asyncio
    async def test_bulk_restart_with_confirm(self) -> None:
        """Bulk restart with confirm should dispatch to client."""
        mock_client = MagicMock()
        mock_client.clusters_config = MagicMock()
        mock_client.clusters_config.default_cluster = "test"
        mock_client.clusters_config.clusters = {"test": MagicMock(default_project="test-project")}
        mock_client.bulk_restart_sessions = AsyncMock(return_value={"restarted": ["s1", "s2"], "failed": []})

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool(
                "acp_bulk_restart_sessions",
                {"project": "test-project", "sessions": ["s1", "s2"], "confirm": True},
            )

            assert "Successfully restarted 2" in result[0].text

    @pytest.mark.asyncio
    async def test_bulk_delete_by_label_requires_confirm(self) -> None:
        """Bulk delete by label without confirm should return validation error."""
        mock_client = MagicMock()
        mock_client.clusters_config = MagicMock()
        mock_client.clusters_config.default_cluster = "test"
        mock_client.clusters_config.clusters = {"test": MagicMock(default_project="test-project")}

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool(
                "acp_bulk_delete_sessions_by_label",
                {"project": "test-project", "labels": {"env": "test"}},
            )

            assert "requires confirm=true" in result[0].text

    @pytest.mark.asyncio
    async def test_bulk_delete_by_label_with_confirm(self) -> None:
        """Bulk delete by label with confirm should dispatch to client."""
        mock_client = MagicMock()
        mock_client.clusters_config = MagicMock()
        mock_client.clusters_config.default_cluster = "test"
        mock_client.clusters_config.clusters = {"test": MagicMock(default_project="test-project")}
        mock_client.bulk_delete_sessions_by_label = AsyncMock(
            return_value={"deleted": ["s1"], "failed": [], "labels_filter": {"env": "test"}}
        )

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool(
                "acp_bulk_delete_sessions_by_label",
                {"project": "test-project", "labels": {"env": "test"}, "confirm": True},
            )

            assert len(result) == 1
            assert "Successfully deleted 1" in result[0].text

    @pytest.mark.asyncio
    async def test_bulk_stop_by_label_requires_confirm(self) -> None:
        """Bulk stop by label without confirm should return validation error."""
        mock_client = MagicMock()
        mock_client.clusters_config = MagicMock()
        mock_client.clusters_config.default_cluster = "test"
        mock_client.clusters_config.clusters = {"test": MagicMock(default_project="test-project")}

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool(
                "acp_bulk_stop_sessions_by_label",
                {"project": "test-project", "labels": {"env": "test"}},
            )

            assert "requires confirm=true" in result[0].text

    @pytest.mark.asyncio
    async def test_bulk_stop_by_label_with_confirm(self) -> None:
        """Bulk stop by label with confirm should dispatch to client."""
        mock_client = MagicMock()
        mock_client.clusters_config = MagicMock()
        mock_client.clusters_config.default_cluster = "test"
        mock_client.clusters_config.clusters = {"test": MagicMock(default_project="test-project")}
        mock_client.bulk_stop_sessions_by_label = AsyncMock(
            return_value={"stopped": ["s1"], "failed": [], "labels_filter": {"env": "test"}}
        )

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool(
                "acp_bulk_stop_sessions_by_label",
                {"project": "test-project", "labels": {"env": "test"}, "confirm": True},
            )

            assert len(result) == 1
            assert "Successfully stopped 1" in result[0].text

    @pytest.mark.asyncio
    async def test_bulk_restart_by_label_requires_confirm(self) -> None:
        """Bulk restart by label without confirm should return validation error."""
        mock_client = MagicMock()
        mock_client.clusters_config = MagicMock()
        mock_client.clusters_config.default_cluster = "test"
        mock_client.clusters_config.clusters = {"test": MagicMock(default_project="test-project")}

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool(
                "acp_bulk_restart_sessions_by_label",
                {"project": "test-project", "labels": {"env": "test"}},
            )

            assert "requires confirm=true" in result[0].text

    @pytest.mark.asyncio
    async def test_bulk_restart_by_label_with_confirm(self) -> None:
        """Bulk restart by label with confirm should dispatch to client."""
        mock_client = MagicMock()
        mock_client.clusters_config = MagicMock()
        mock_client.clusters_config.default_cluster = "test"
        mock_client.clusters_config.clusters = {"test": MagicMock(default_project="test-project")}
        mock_client.bulk_restart_sessions_by_label = AsyncMock(
            return_value={"restarted": ["s1"], "failed": [], "labels_filter": {"env": "test"}}
        )

        with patch("mcp_acp.server.get_client", return_value=mock_client):
            result = await call_tool(
                "acp_bulk_restart_sessions_by_label",
                {"project": "test-project", "labels": {"env": "test"}, "confirm": True},
            )

            assert len(result) == 1
            assert "Successfully restarted 1" in result[0].text
