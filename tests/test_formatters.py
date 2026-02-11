"""Tests for output formatters."""

from mcp_acp.formatters import (
    format_bulk_result,
    format_clusters,
    format_result,
    format_sessions_list,
    format_whoami,
)


class TestFormatResult:
    """Tests for format_result."""

    def test_format_result_dry_run(self) -> None:
        """Test formatting dry run result."""
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
        """Test formatting normal result."""
        result = {"message": "Successfully deleted session"}

        output = format_result(result)

        assert "Successfully deleted session" in output


class TestFormatSessionsList:
    """Tests for format_sessions_list."""

    def test_format_sessions_list(self) -> None:
        """Test formatting sessions list."""
        result = {
            "total": 2,
            "filters_applied": {"status": "running"},
            "sessions": [
                {"id": "session-1", "status": "running", "createdAt": "2024-01-20T10:00:00Z"},
                {"id": "session-2", "status": "running", "createdAt": "2024-01-21T10:00:00Z"},
            ],
        }

        output = format_sessions_list(result)

        assert "Found 2 session(s)" in output
        assert "session-1" in output
        assert "session-2" in output
        assert "running" in output

    def test_format_sessions_list_empty(self) -> None:
        """Test formatting empty sessions list."""
        result = {"total": 0, "filters_applied": {}, "sessions": []}

        output = format_sessions_list(result)

        assert "Found 0 session(s)" in output


class TestFormatBulkResult:
    """Tests for format_bulk_result."""

    def test_format_bulk_result_dry_run(self) -> None:
        """Test formatting bulk delete dry run."""
        result = {
            "dry_run": True,
            "dry_run_info": {
                "would_execute": [
                    {"session": "session-1", "info": {"status": "stopped"}},
                    {"session": "session-2", "info": {"status": "stopped"}},
                ],
                "skipped": [],
            },
        }

        output = format_bulk_result(result, "delete")

        assert "DRY RUN MODE" in output
        assert "Would delete 2 session(s)" in output
        assert "session-1" in output
        assert "session-2" in output

    def test_format_bulk_result_success(self) -> None:
        """Test formatting bulk delete success."""
        result = {
            "deleted": ["session-1", "session-2"],
            "failed": [],
        }

        output = format_bulk_result(result, "delete")

        assert "Successfully deleted 2 session(s)" in output
        assert "session-1" in output
        assert "session-2" in output

    def test_format_bulk_result_with_failures(self) -> None:
        """Test formatting bulk delete with failures."""
        result = {
            "deleted": ["session-1"],
            "failed": [{"session": "session-2", "error": "Not found"}],
        }

        output = format_bulk_result(result, "delete")

        assert "Successfully deleted 1 session(s)" in output
        assert "Failed" in output
        assert "session-2" in output
        assert "Not found" in output


class TestFormatClusters:
    """Tests for format_clusters."""

    def test_format_clusters(self) -> None:
        """Test formatting clusters list."""
        result = {
            "clusters": [
                {
                    "name": "test-cluster",
                    "server": "https://api.test.example.com",
                    "description": "Test Cluster",
                    "default_project": "test-workspace",
                    "is_default": True,
                },
            ],
            "default_cluster": "test-cluster",
        }

        output = format_clusters(result)

        assert "test-cluster [DEFAULT]" in output
        assert "https://api.test.example.com" in output
        assert "Test Cluster" in output

    def test_format_clusters_empty(self) -> None:
        """Test formatting empty clusters list."""
        result = {"clusters": [], "default_cluster": None}

        output = format_clusters(result)

        assert "No clusters configured" in output


class TestFormatWhoami:
    """Tests for format_whoami."""

    def test_format_whoami_authenticated(self) -> None:
        """Test formatting whoami when authenticated."""
        result = {
            "authenticated": True,
            "cluster": "test-cluster",
            "server": "https://api.test.example.com",
            "project": "test-workspace",
            "token_valid": True,
        }

        output = format_whoami(result)

        assert "Token Configured: Yes" in output
        assert "Cluster: test-cluster" in output
        assert "Server: https://api.test.example.com" in output
        assert "Project: test-workspace" in output

    def test_format_whoami_not_authenticated(self) -> None:
        """Test formatting whoami when not authenticated."""
        result = {
            "authenticated": False,
            "cluster": "test-cluster",
            "server": "https://api.test.example.com",
            "project": "unknown",
            "token_valid": False,
        }

        output = format_whoami(result)

        assert "Token Configured: No" in output
        assert "Set token" in output
