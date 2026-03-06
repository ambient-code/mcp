"""End-to-end tests for MCP server exercising all tools with mocked HTTP responses.

This module tests the complete flow from tool call through the client to HTTP requests,
mocking only the HTTP transport layer to verify the full integration.

Test Categories:
- Session Management: CRUD operations for AgenticSessions
- Observability: Logs, transcripts, and metrics retrieval
- Labels: Adding, removing, and filtering by labels
- Bulk Operations: Multi-session operations with confirmation
- Cluster Management: Multi-cluster configuration and auth
- Error Handling: HTTP errors, validation, and edge cases
"""

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from mcp_acp.client import ACPClient
from mcp_acp.server import call_tool, list_tools

# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_clusters_config():
    """Create mock clusters configuration with a single test cluster."""
    cluster = MagicMock()
    cluster.server = "https://api.test.example.com"
    cluster.default_project = "test-project"
    cluster.description = "Test Cluster"
    cluster.token = "test-token-abc123"

    config = MagicMock()
    config.clusters = {"test-cluster": cluster}
    config.default_cluster = "test-cluster"
    return config


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = MagicMock()
    settings.config_path = None
    return settings


def make_response(status_code: int = 200, json_data: dict | None = None, text: str = "") -> httpx.Response:
    """Create a mock httpx Response.

    Args:
        status_code: HTTP status code
        json_data: JSON response body (takes precedence over text)
        text: Plain text response body
    """
    if json_data is not None:
        content = json.dumps(json_data).encode()
        headers = {"content-type": "application/json"}
    else:
        content = text.encode()
        headers = {"content-type": "text/plain"}

    return httpx.Response(
        status_code=status_code,
        content=content,
        headers=headers,
        request=httpx.Request("GET", "https://api.test.example.com"),
    )


class MockHTTPClient:
    """Mock HTTP client that returns predefined responses based on method and path.

    Supports:
    - Setting responses for specific method/path combinations
    - Recording all HTTP calls for verification
    - Default successful response for unconfigured paths
    """

    def __init__(self):
        self.responses: dict[tuple[str, str], httpx.Response] = {}
        self.calls: list[dict] = []
        self.is_closed = False

    def set_response(self, method: str, path_contains: str, response: httpx.Response):
        """Set a response for a specific method/path combination."""
        self.responses[(method.upper(), path_contains)] = response

    async def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Mock request that returns configured responses."""
        self.calls.append({"method": method, "url": url, "kwargs": kwargs})

        # Try to find a matching response (more specific paths first)
        for (m, path), response in sorted(
            self.responses.items(), key=lambda x: len(x[0][1]), reverse=True
        ):
            if method.upper() == m and path in url:
                return response

        # Default successful response
        return make_response(200, {"success": True})

    async def aclose(self):
        """Close the mock client."""
        self.is_closed = True

    def get_calls_for(self, method: str, path_contains: str = "") -> list[dict]:
        """Get all recorded calls matching method and optional path substring."""
        return [
            c
            for c in self.calls
            if c["method"].upper() == method.upper() and path_contains in c["url"]
        ]

    def assert_called_with(self, method: str, path_contains: str):
        """Assert that at least one call was made with the given method and path."""
        matching = self.get_calls_for(method, path_contains)
        assert matching, f"No {method} call to '{path_contains}' found. Calls: {self.calls}"


@pytest.fixture
def mock_http_client():
    """Create a fresh mock HTTP client for each test."""
    return MockHTTPClient()


@pytest.fixture
def client_with_mock_http(mock_settings, mock_clusters_config, mock_http_client):
    """Create an ACP client with mocked HTTP transport."""
    with patch("mcp_acp.client.load_settings", return_value=mock_settings):
        with patch("mcp_acp.client.load_clusters_config", return_value=mock_clusters_config):
            client = ACPClient()
            client._http_client = mock_http_client
            return client


# ── Test: List Tools ─────────────────────────────────────────────────────────


class TestListToolsE2E:
    """Verify all expected tools are registered."""

    @pytest.mark.asyncio
    async def test_all_tools_registered(self):
        """All 26 tools should be available."""
        tools = await list_tools()
        assert len(tools) == 26

        tool_names = {t.name for t in tools}
        expected_tools = {
            # Session management
            "acp_list_sessions",
            "acp_get_session",
            "acp_create_session",
            "acp_create_session_from_template",
            "acp_delete_session",
            "acp_restart_session",
            "acp_clone_session",
            "acp_update_session",
            # Observability
            "acp_get_session_logs",
            "acp_get_session_transcript",
            "acp_get_session_metrics",
            # Labels
            "acp_label_resource",
            "acp_unlabel_resource",
            "acp_list_sessions_by_label",
            "acp_bulk_label_resources",
            "acp_bulk_unlabel_resources",
            # Bulk operations
            "acp_bulk_delete_sessions",
            "acp_bulk_stop_sessions",
            "acp_bulk_restart_sessions",
            "acp_bulk_delete_sessions_by_label",
            "acp_bulk_stop_sessions_by_label",
            "acp_bulk_restart_sessions_by_label",
            # Cluster management
            "acp_list_clusters",
            "acp_whoami",
            "acp_switch_cluster",
            "acp_login",
        }
        assert tool_names == expected_tools


# ── Test: Session Management Tools ───────────────────────────────────────────


class TestSessionManagementE2E:
    """E2E tests for session management tools."""

    @pytest.mark.asyncio
    async def test_list_sessions(self, client_with_mock_http, mock_http_client):
        """Test listing sessions with HTTP mock."""
        mock_http_client.set_response(
            "GET",
            "/v1/sessions",
            make_response(
                200,
                {
                    "items": [
                        {
                            "id": "session-001",
                            "status": "running",
                            "displayName": "Test Session",
                            "createdAt": "2024-01-15T10:30:00Z",
                        },
                        {
                            "id": "session-002",
                            "status": "stopped",
                            "displayName": "Stopped Session",
                            "createdAt": "2024-01-14T08:00:00Z",
                        },
                    ]
                },
            ),
        )

        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool("acp_list_sessions", {"project": "test-project"})

        assert len(result) == 1
        assert "session-001" in result[0].text
        assert "session-002" in result[0].text

    @pytest.mark.asyncio
    async def test_list_sessions_with_filters(self, client_with_mock_http, mock_http_client):
        """Test listing sessions with status filter."""
        mock_http_client.set_response(
            "GET",
            "/v1/sessions",
            make_response(
                200,
                {
                    "items": [
                        {"id": "running-session", "status": "running", "createdAt": "2024-01-15T10:30:00Z"},
                        {"id": "stopped-session", "status": "stopped", "createdAt": "2024-01-14T08:00:00Z"},
                    ]
                },
            ),
        )

        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool("acp_list_sessions", {"project": "test-project", "status": "running", "limit": 10})

        assert len(result) == 1
        # Only running session should be shown after client-side filter
        assert "running-session" in result[0].text

    @pytest.mark.asyncio
    async def test_get_session(self, client_with_mock_http, mock_http_client):
        """Test getting a single session."""
        mock_http_client.set_response(
            "GET",
            "/v1/sessions/session-001",
            make_response(
                200,
                {
                    "id": "session-001",
                    "status": "running",
                    "displayName": "My Test Session",
                    "model": "claude-sonnet-4",
                    "createdAt": "2024-01-15T10:30:00Z",
                    "task": "Fix the bug in auth module",
                },
            ),
        )

        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool("acp_get_session", {"project": "test-project", "session": "session-001"})

        assert len(result) == 1
        assert "session-001" in result[0].text
        assert "running" in result[0].text.lower() or "My Test Session" in result[0].text

    @pytest.mark.asyncio
    async def test_create_session(self, client_with_mock_http, mock_http_client):
        """Test creating a new session."""
        mock_http_client.set_response(
            "POST",
            "/v1/sessions",
            make_response(
                201,
                {
                    "id": "new-session-xyz",
                    "status": "creating",
                    "displayName": "Bug Fix Session",
                },
            ),
        )

        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool(
                "acp_create_session",
                {
                    "project": "test-project",
                    "initial_prompt": "Fix the authentication bug",
                    "display_name": "Bug Fix Session",
                    "model": "claude-sonnet-4",
                },
            )

        assert len(result) == 1
        assert "new-session-xyz" in result[0].text

    @pytest.mark.asyncio
    async def test_create_session_dry_run(self, client_with_mock_http, mock_http_client):
        """Test create session dry run mode."""
        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool(
                "acp_create_session",
                {
                    "project": "test-project",
                    "initial_prompt": "Test prompt",
                    "dry_run": True,
                },
            )

        assert len(result) == 1
        assert "dry" in result[0].text.lower() or "would" in result[0].text.lower()
        # No HTTP calls should be made for dry run
        assert len([c for c in mock_http_client.calls if "POST" in c["method"]]) == 0

    @pytest.mark.asyncio
    async def test_create_session_from_template(self, client_with_mock_http, mock_http_client):
        """Test creating session from template."""
        mock_http_client.set_response(
            "POST",
            "/v1/sessions",
            make_response(201, {"id": "template-session-abc"}),
        )

        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool(
                "acp_create_session_from_template",
                {
                    "project": "test-project",
                    "template": "bugfix",
                    "display_name": "Fix auth bug",
                },
            )

        assert len(result) == 1
        assert "template-session-abc" in result[0].text

    @pytest.mark.asyncio
    async def test_delete_session(self, client_with_mock_http, mock_http_client):
        """Test deleting a session."""
        mock_http_client.set_response("DELETE", "/v1/sessions/session-to-delete", make_response(204))

        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool(
                "acp_delete_session",
                {"project": "test-project", "session": "session-to-delete"},
            )

        assert len(result) == 1
        assert "delete" in result[0].text.lower() or "success" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_delete_session_dry_run(self, client_with_mock_http, mock_http_client):
        """Test delete session dry run."""
        mock_http_client.set_response(
            "GET",
            "/v1/sessions/session-001",
            make_response(200, {"id": "session-001", "status": "running", "createdAt": "2024-01-15T10:30:00Z"}),
        )

        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool(
                "acp_delete_session",
                {"project": "test-project", "session": "session-001", "dry_run": True},
            )

        assert len(result) == 1
        assert "dry" in result[0].text.lower() or "would" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_restart_session(self, client_with_mock_http, mock_http_client):
        """Test restarting a stopped session."""
        mock_http_client.set_response(
            "PATCH",
            "/v1/sessions/stopped-session",
            make_response(200, {"id": "stopped-session", "status": "running"}),
        )

        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool(
                "acp_restart_session",
                {"project": "test-project", "session": "stopped-session"},
            )

        assert len(result) == 1
        assert "restart" in result[0].text.lower() or "success" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_clone_session(self, client_with_mock_http, mock_http_client):
        """Test cloning a session."""
        # First GET to fetch source session config
        mock_http_client.set_response(
            "GET",
            "/v1/sessions/source-session",
            make_response(
                200,
                {
                    "id": "source-session",
                    "task": "Original task",
                    "model": "claude-sonnet-4",
                    "repos": [{"url": "https://github.com/test/repo"}],
                },
            ),
        )
        # Then POST to create clone
        mock_http_client.set_response(
            "POST",
            "/v1/sessions",
            make_response(201, {"id": "cloned-session-xyz"}),
        )

        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool(
                "acp_clone_session",
                {
                    "project": "test-project",
                    "source_session": "source-session",
                    "new_display_name": "My Clone",
                },
            )

        assert len(result) == 1
        assert "cloned-session-xyz" in result[0].text

    @pytest.mark.asyncio
    async def test_update_session(self, client_with_mock_http, mock_http_client):
        """Test updating session metadata."""
        mock_http_client.set_response(
            "PATCH",
            "/v1/sessions/session-001",
            make_response(200, {"id": "session-001", "displayName": "New Name"}),
        )

        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool(
                "acp_update_session",
                {
                    "project": "test-project",
                    "session": "session-001",
                    "display_name": "New Name",
                    "timeout": 3600,
                },
            )

        assert len(result) == 1
        assert "update" in result[0].text.lower()


# ── Test: Observability Tools ────────────────────────────────────────────────


class TestObservabilityE2E:
    """E2E tests for observability tools (logs, transcript, metrics)."""

    @pytest.mark.asyncio
    async def test_get_session_logs(self, client_with_mock_http, mock_http_client):
        """Test retrieving session logs."""
        log_content = """2024-01-15 10:30:00 INFO Starting session
2024-01-15 10:30:01 INFO Loading model claude-sonnet-4
2024-01-15 10:30:05 INFO Processing initial prompt
2024-01-15 10:31:00 INFO Tool call: Read file.py"""

        mock_http_client.set_response(
            "GET",
            "/v1/sessions/session-001/logs",
            make_response(200, None, log_content),
        )

        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool(
                "acp_get_session_logs",
                {"project": "test-project", "session": "session-001", "tail_lines": 100},
            )

        assert len(result) == 1
        assert "Starting session" in result[0].text or "session-001" in result[0].text

    @pytest.mark.asyncio
    async def test_get_session_transcript(self, client_with_mock_http, mock_http_client):
        """Test retrieving session transcript."""
        mock_http_client.set_response(
            "GET",
            "/v1/sessions/session-001/transcript",
            make_response(
                200,
                {
                    "messages": [
                        {"role": "user", "content": "Fix the login bug"},
                        {"role": "assistant", "content": "I'll analyze the auth module..."},
                    ]
                },
            ),
        )

        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool(
                "acp_get_session_transcript",
                {"project": "test-project", "session": "session-001", "format": "json"},
            )

        assert len(result) == 1
        assert "login bug" in result[0].text or "auth module" in result[0].text

    @pytest.mark.asyncio
    async def test_get_session_metrics(self, client_with_mock_http, mock_http_client):
        """Test retrieving session metrics."""
        mock_http_client.set_response(
            "GET",
            "/v1/sessions/session-001/metrics",
            make_response(
                200,
                {
                    "total_tokens": 15000,
                    "input_tokens": 5000,
                    "output_tokens": 10000,
                    "duration_seconds": 300,
                    "tool_calls": 25,
                    "api_calls": 8,
                },
            ),
        )

        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool(
                "acp_get_session_metrics",
                {"project": "test-project", "session": "session-001"},
            )

        assert len(result) == 1
        # Check that metrics values appear in output
        text = result[0].text
        assert "15000" in text or "15,000" in text or "tokens" in text.lower()


# ── Test: Label Tools ────────────────────────────────────────────────────────


class TestLabelToolsE2E:
    """E2E tests for label management tools."""

    @pytest.mark.asyncio
    async def test_label_resource(self, client_with_mock_http, mock_http_client):
        """Test adding labels to a session."""
        mock_http_client.set_response(
            "PATCH",
            "/v1/sessions/session-001",
            make_response(200, {"id": "session-001", "labels": {"env": "prod", "team": "platform"}}),
        )

        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool(
                "acp_label_resource",
                {
                    "project": "test-project",
                    "name": "session-001",
                    "labels": {"env": "prod", "team": "platform"},
                },
            )

        assert len(result) == 1
        assert "label" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_unlabel_resource(self, client_with_mock_http, mock_http_client):
        """Test removing labels from a session."""
        mock_http_client.set_response(
            "PATCH",
            "/v1/sessions/session-001",
            make_response(200, {"id": "session-001"}),
        )

        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool(
                "acp_unlabel_resource",
                {
                    "project": "test-project",
                    "name": "session-001",
                    "label_keys": ["env", "team"],
                },
            )

        assert len(result) == 1
        assert "label" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_list_sessions_by_label(self, client_with_mock_http, mock_http_client):
        """Test listing sessions filtered by labels."""
        mock_http_client.set_response(
            "GET",
            "/v1/sessions",
            make_response(
                200,
                {
                    "items": [
                        {"id": "labeled-session-1", "status": "running", "createdAt": "2024-01-15T10:30:00Z"},
                        {"id": "labeled-session-2", "status": "stopped", "createdAt": "2024-01-14T08:00:00Z"},
                    ]
                },
            ),
        )

        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool(
                "acp_list_sessions_by_label",
                {"project": "test-project", "labels": {"env": "prod"}},
            )

        assert len(result) == 1
        assert "labeled-session" in result[0].text


# ── Test: Bulk Operations ────────────────────────────────────────────────────


class TestBulkOperationsE2E:
    """E2E tests for bulk operation tools."""

    @pytest.mark.asyncio
    async def test_bulk_delete_requires_confirm(self, client_with_mock_http):
        """Test that bulk delete requires confirmation."""
        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool(
                "acp_bulk_delete_sessions",
                {"project": "test-project", "sessions": ["s1", "s2"]},
            )

        assert "requires confirm=true" in result[0].text

    @pytest.mark.asyncio
    async def test_bulk_delete_with_confirm(self, client_with_mock_http, mock_http_client):
        """Test bulk delete with confirmation."""
        mock_http_client.set_response("DELETE", "/v1/sessions/s1", make_response(204))
        mock_http_client.set_response("DELETE", "/v1/sessions/s2", make_response(204))

        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool(
                "acp_bulk_delete_sessions",
                {"project": "test-project", "sessions": ["s1", "s2"], "confirm": True},
            )

        assert len(result) == 1
        assert "deleted" in result[0].text.lower() or "2" in result[0].text

    @pytest.mark.asyncio
    async def test_bulk_delete_dry_run(self, client_with_mock_http, mock_http_client):
        """Test bulk delete dry run mode."""
        mock_http_client.set_response(
            "GET", "/v1/sessions/s1", make_response(200, {"id": "s1", "status": "running", "createdAt": "2024-01-01"})
        )
        mock_http_client.set_response(
            "GET", "/v1/sessions/s2", make_response(200, {"id": "s2", "status": "stopped", "createdAt": "2024-01-01"})
        )

        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool(
                "acp_bulk_delete_sessions",
                {"project": "test-project", "sessions": ["s1", "s2"], "dry_run": True},
            )

        assert len(result) == 1
        # Dry run should not require confirm
        assert "requires confirm" not in result[0].text

    @pytest.mark.asyncio
    async def test_bulk_stop_sessions(self, client_with_mock_http, mock_http_client):
        """Test bulk stop sessions."""
        mock_http_client.set_response("PATCH", "/v1/sessions/s1", make_response(200, {"id": "s1", "status": "stopped"}))
        mock_http_client.set_response("PATCH", "/v1/sessions/s2", make_response(200, {"id": "s2", "status": "stopped"}))

        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool(
                "acp_bulk_stop_sessions",
                {"project": "test-project", "sessions": ["s1", "s2"], "confirm": True},
            )

        assert len(result) == 1
        assert "stopped" in result[0].text.lower() or "2" in result[0].text

    @pytest.mark.asyncio
    async def test_bulk_restart_sessions(self, client_with_mock_http, mock_http_client):
        """Test bulk restart sessions."""
        mock_http_client.set_response("PATCH", "/v1/sessions/s1", make_response(200, {"id": "s1", "status": "running"}))
        mock_http_client.set_response("PATCH", "/v1/sessions/s2", make_response(200, {"id": "s2", "status": "running"}))

        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool(
                "acp_bulk_restart_sessions",
                {"project": "test-project", "sessions": ["s1", "s2"], "confirm": True},
            )

        assert len(result) == 1
        assert "restart" in result[0].text.lower() or "2" in result[0].text

    @pytest.mark.asyncio
    async def test_bulk_label_resources(self, client_with_mock_http, mock_http_client):
        """Test bulk labeling."""
        mock_http_client.set_response("PATCH", "/v1/sessions/s1", make_response(200, {"id": "s1"}))
        mock_http_client.set_response("PATCH", "/v1/sessions/s2", make_response(200, {"id": "s2"}))

        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool(
                "acp_bulk_label_resources",
                {
                    "project": "test-project",
                    "sessions": ["s1", "s2"],
                    "labels": {"env": "test"},
                    "confirm": True,
                },
            )

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_bulk_unlabel_resources(self, client_with_mock_http, mock_http_client):
        """Test bulk unlabeling."""
        mock_http_client.set_response("PATCH", "/v1/sessions/s1", make_response(200, {"id": "s1"}))
        mock_http_client.set_response("PATCH", "/v1/sessions/s2", make_response(200, {"id": "s2"}))

        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool(
                "acp_bulk_unlabel_resources",
                {
                    "project": "test-project",
                    "sessions": ["s1", "s2"],
                    "label_keys": ["env"],
                    "confirm": True,
                },
            )

        assert len(result) == 1


# ── Test: Bulk Operations by Label ───────────────────────────────────────────


class TestBulkByLabelE2E:
    """E2E tests for bulk operations filtered by label."""

    @pytest.mark.asyncio
    async def test_bulk_delete_by_label(self, client_with_mock_http, mock_http_client):
        """Test bulk delete sessions matching labels."""
        # List sessions by label
        mock_http_client.set_response(
            "GET",
            "/v1/sessions",
            make_response(
                200,
                {
                    "items": [
                        {"id": "labeled-1", "status": "stopped", "createdAt": "2024-01-01"},
                        {"id": "labeled-2", "status": "stopped", "createdAt": "2024-01-01"},
                    ]
                },
            ),
        )
        mock_http_client.set_response("DELETE", "/v1/sessions/labeled-1", make_response(204))
        mock_http_client.set_response("DELETE", "/v1/sessions/labeled-2", make_response(204))

        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool(
                "acp_bulk_delete_sessions_by_label",
                {"project": "test-project", "labels": {"env": "test"}, "confirm": True},
            )

        assert len(result) == 1
        assert "deleted" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_bulk_stop_by_label(self, client_with_mock_http, mock_http_client):
        """Test bulk stop sessions matching labels."""
        mock_http_client.set_response(
            "GET",
            "/v1/sessions",
            make_response(200, {"items": [{"id": "running-1", "status": "running", "createdAt": "2024-01-01"}]}),
        )
        mock_http_client.set_response(
            "PATCH", "/v1/sessions/running-1", make_response(200, {"id": "running-1", "status": "stopped"})
        )

        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool(
                "acp_bulk_stop_sessions_by_label",
                {"project": "test-project", "labels": {"team": "qa"}, "confirm": True},
            )

        assert len(result) == 1
        assert "stopped" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_bulk_restart_by_label(self, client_with_mock_http, mock_http_client):
        """Test bulk restart sessions matching labels."""
        mock_http_client.set_response(
            "GET",
            "/v1/sessions",
            make_response(200, {"items": [{"id": "stopped-1", "status": "stopped", "createdAt": "2024-01-01"}]}),
        )
        mock_http_client.set_response(
            "PATCH", "/v1/sessions/stopped-1", make_response(200, {"id": "stopped-1", "status": "running"})
        )

        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool(
                "acp_bulk_restart_sessions_by_label",
                {"project": "test-project", "labels": {"priority": "high"}, "confirm": True},
            )

        assert len(result) == 1
        assert "restart" in result[0].text.lower()


# ── Test: Cluster Management Tools ───────────────────────────────────────────


class TestClusterManagementE2E:
    """E2E tests for cluster management tools."""

    @pytest.mark.asyncio
    async def test_list_clusters(self, client_with_mock_http):
        """Test listing configured clusters."""
        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool("acp_list_clusters", {})

        assert len(result) == 1
        assert "test-cluster" in result[0].text

    @pytest.mark.asyncio
    async def test_whoami(self, client_with_mock_http):
        """Test whoami shows current config."""
        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool("acp_whoami", {})

        assert len(result) == 1
        text = result[0].text.lower()
        assert "cluster" in text or "authenticated" in text or "test" in text

    @pytest.mark.asyncio
    async def test_switch_cluster(self, client_with_mock_http):
        """Test switching cluster context."""
        # Add a second cluster to switch to
        second_cluster = MagicMock()
        second_cluster.server = "https://api.prod.example.com"
        second_cluster.default_project = "prod-project"
        second_cluster.token = "prod-token"
        client_with_mock_http.clusters_config.clusters["prod-cluster"] = second_cluster

        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool("acp_switch_cluster", {"cluster": "prod-cluster"})

        assert len(result) == 1
        assert "switched" in result[0].text.lower() or "prod" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_switch_cluster_unknown(self, client_with_mock_http):
        """Test switching to unknown cluster fails gracefully."""
        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool("acp_switch_cluster", {"cluster": "nonexistent"})

        assert len(result) == 1
        assert "unknown" in result[0].text.lower() or "not found" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_login(self, client_with_mock_http):
        """Test login to cluster."""
        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool(
                "acp_login",
                {"cluster": "test-cluster", "token": "new-auth-token"},
            )

        assert len(result) == 1
        assert "authenticated" in result[0].text.lower() or "success" in result[0].text.lower()


# ── Test: Error Handling ─────────────────────────────────────────────────────


class TestErrorHandlingE2E:
    """E2E tests for error handling scenarios."""

    @pytest.mark.asyncio
    async def test_http_error_response(self, client_with_mock_http, mock_http_client):
        """Test handling of HTTP error responses."""
        mock_http_client.set_response(
            "GET",
            "/v1/sessions/nonexistent",
            make_response(404, {"error": "Session not found"}),
        )

        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool(
                "acp_get_session",
                {"project": "test-project", "session": "nonexistent"},
            )

        assert len(result) == 1
        assert "error" in result[0].text.lower() or "not found" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_unknown_tool(self, client_with_mock_http):
        """Test calling an unknown tool."""
        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool("acp_unknown_tool", {})

        assert len(result) == 1
        assert "unknown tool" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_validation_error_invalid_project(self, client_with_mock_http):
        """Test validation error for invalid project name."""
        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool(
                "acp_list_sessions",
                {"project": "INVALID_PROJECT_NAME!@#"},
            )

        assert len(result) == 1
        # Should show validation error about invalid characters
        assert "error" in result[0].text.lower() or "invalid" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_bulk_operation_limit_exceeded(self, client_with_mock_http):
        """Test that bulk operations enforce max item limit."""
        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool(
                "acp_bulk_delete_sessions",
                {
                    "project": "test-project",
                    "sessions": ["s1", "s2", "s3", "s4", "s5"],  # More than max 3
                    "confirm": True,
                },
            )

        assert len(result) == 1
        # Should fail with limit error
        assert "limit" in result[0].text.lower() or "3" in result[0].text


# ── Test: Project Auto-fill ──────────────────────────────────────────────────


class TestProjectAutoFillE2E:
    """E2E tests for automatic project filling from cluster config."""

    @pytest.mark.asyncio
    async def test_project_auto_filled_from_cluster(self, client_with_mock_http, mock_http_client):
        """Test that project is auto-filled when not provided."""
        mock_http_client.set_response(
            "GET",
            "/v1/sessions",
            make_response(200, {"items": []}),
        )

        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            # Call without project - should use default from cluster config
            result = await call_tool("acp_list_sessions", {})

        assert len(result) == 1
        # Verify the request used the default project from cluster config
        assert any("test-project" in str(call.get("kwargs", {}).get("headers", {})) for call in mock_http_client.calls)


# ── Test: Complete Workflow ──────────────────────────────────────────────────


class TestCompleteWorkflowE2E:
    """E2E tests simulating complete user workflows."""

    @pytest.mark.asyncio
    async def test_session_lifecycle(self, client_with_mock_http, mock_http_client):
        """Test complete session lifecycle: create -> get -> update -> stop -> delete."""
        # 1. Create session
        mock_http_client.set_response("POST", "/v1/sessions", make_response(201, {"id": "lifecycle-session"}))

        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            create_result = await call_tool(
                "acp_create_session",
                {"project": "test-project", "initial_prompt": "Test workflow"},
            )
        assert "lifecycle-session" in create_result[0].text

        # 2. Get session details
        mock_http_client.set_response(
            "GET",
            "/v1/sessions/lifecycle-session",
            make_response(
                200, {"id": "lifecycle-session", "status": "running", "displayName": "Test", "createdAt": "2024-01-01"}
            ),
        )

        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            get_result = await call_tool(
                "acp_get_session",
                {"project": "test-project", "session": "lifecycle-session"},
            )
        assert "lifecycle-session" in get_result[0].text

        # 3. Update session
        mock_http_client.set_response(
            "PATCH",
            "/v1/sessions/lifecycle-session",
            make_response(200, {"id": "lifecycle-session", "displayName": "Updated Name"}),
        )

        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            update_result = await call_tool(
                "acp_update_session",
                {"project": "test-project", "session": "lifecycle-session", "display_name": "Updated Name"},
            )
        assert "update" in update_result[0].text.lower()

        # 4. Delete session
        mock_http_client.set_response("DELETE", "/v1/sessions/lifecycle-session", make_response(204))

        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            delete_result = await call_tool(
                "acp_delete_session",
                {"project": "test-project", "session": "lifecycle-session"},
            )
        assert "delete" in delete_result[0].text.lower() or "success" in delete_result[0].text.lower()


# ── Test: Additional Edge Cases ──────────────────────────────────────────────


class TestAdditionalEdgeCasesE2E:
    """Additional edge case tests for comprehensive coverage."""

    @pytest.mark.asyncio
    async def test_create_session_with_repos(self, client_with_mock_http, mock_http_client):
        """Test creating a session with repository URLs."""
        mock_http_client.set_response("POST", "/v1/sessions", make_response(201, {"id": "repo-session"}))

        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool(
                "acp_create_session",
                {
                    "project": "test-project",
                    "initial_prompt": "Review the code",
                    "repos": ["https://github.com/org/repo1", "https://github.com/org/repo2"],
                },
            )

        assert len(result) == 1
        assert "repo-session" in result[0].text
        mock_http_client.assert_called_with("POST", "/v1/sessions")

    @pytest.mark.asyncio
    async def test_invalid_template_name(self, client_with_mock_http):
        """Test validation error for invalid template name."""
        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool(
                "acp_create_session_from_template",
                {
                    "project": "test-project",
                    "template": "nonexistent-template",
                    "display_name": "Test",
                },
            )

        assert len(result) == 1
        assert "unknown template" in result[0].text.lower() or "error" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_update_session_no_fields(self, client_with_mock_http):
        """Test update session fails when no fields provided."""
        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool(
                "acp_update_session",
                {"project": "test-project", "session": "session-001"},
            )

        assert len(result) == 1
        assert "no fields" in result[0].text.lower() or "error" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_bulk_by_label_no_matches(self, client_with_mock_http, mock_http_client):
        """Test bulk operation by label when no sessions match."""
        mock_http_client.set_response("GET", "/v1/sessions", make_response(200, {"items": []}))

        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool(
                "acp_bulk_delete_sessions_by_label",
                {"project": "test-project", "labels": {"env": "nonexistent"}, "confirm": True},
            )

        assert len(result) == 1
        assert "no sessions" in result[0].text.lower() or "0" in result[0].text

    @pytest.mark.asyncio
    async def test_empty_sessions_list(self, client_with_mock_http, mock_http_client):
        """Test listing sessions returns empty list gracefully."""
        mock_http_client.set_response("GET", "/v1/sessions", make_response(200, {"items": []}))

        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            result = await call_tool("acp_list_sessions", {"project": "test-project"})

        assert len(result) == 1
        assert "0" in result[0].text or "no" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_delete_verifies_http_call(self, client_with_mock_http, mock_http_client):
        """Test delete session makes correct HTTP call."""
        mock_http_client.set_response("DELETE", "/v1/sessions/verify-delete", make_response(204))

        with patch("mcp_acp.server.get_client", return_value=client_with_mock_http):
            await call_tool(
                "acp_delete_session",
                {"project": "test-project", "session": "verify-delete"},
            )

        mock_http_client.assert_called_with("DELETE", "/v1/sessions/verify-delete")
