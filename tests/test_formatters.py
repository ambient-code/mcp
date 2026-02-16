"""Tests for output formatters."""

from mcp_acp.formatters import (
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


class TestFormatLogs:
    """Tests for format_logs."""

    def test_format_logs_with_content(self) -> None:
        """Test formatting logs with actual content."""
        result = {
            "logs": "2024-01-20 Starting session\n2024-01-20 Running tests",
            "session": "session-1",
            "tail_lines": 1000,
        }

        output = format_logs(result)

        assert "Logs for session 'session-1'" in output
        assert "tail: 1000" in output
        assert "Starting session" in output
        assert "Running tests" in output

    def test_format_logs_empty(self) -> None:
        """Test formatting logs with no content."""
        result = {"logs": "", "session": "session-1", "tail_lines": 100}

        output = format_logs(result)

        assert "(no logs available)" in output

    def test_format_logs_error(self) -> None:
        """Test formatting logs with error."""
        result = {"logs": "", "error": "Session not found", "session": "session-1"}

        output = format_logs(result)

        assert "Error retrieving logs" in output
        assert "Session not found" in output


class TestFormatTranscript:
    """Tests for format_transcript."""

    def test_format_transcript_json(self) -> None:
        """Test formatting transcript in JSON format."""
        result = {
            "session": "session-1",
            "format": "json",
            "messages": [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi there"},
            ],
        }

        output = format_transcript(result)

        assert "Transcript for session 'session-1'" in output
        assert "format: json" in output
        assert '"role": "user"' in output
        assert '"content": "hello"' in output

    def test_format_transcript_markdown(self) -> None:
        """Test formatting transcript in Markdown format."""
        result = {
            "session": "session-1",
            "format": "markdown",
            "transcript": "## User\nhello\n\n## Assistant\nhi there",
        }

        output = format_transcript(result)

        assert "Transcript for session 'session-1'" in output
        assert "format: markdown" in output
        assert "## User" in output

    def test_format_transcript_empty(self) -> None:
        """Test formatting empty transcript."""
        result = {"session": "session-1", "format": "json"}

        output = format_transcript(result)

        assert "(no transcript available)" in output


class TestFormatMetrics:
    """Tests for format_metrics."""

    def test_format_metrics(self) -> None:
        """Test formatting session metrics."""
        result = {
            "session": "session-1",
            "total_tokens": 5000,
            "duration_seconds": 120,
            "tool_calls": 15,
        }

        output = format_metrics(result)

        assert "Metrics for session 'session-1'" in output
        assert "Total Tokens: 5000" in output
        assert "Duration Seconds: 120" in output
        assert "Tool Calls: 15" in output


class TestFormatLabels:
    """Tests for format_labels."""

    def test_format_labels_single_label(self) -> None:
        """Test formatting single label result."""
        result = {
            "labeled": True,
            "session": "session-1",
            "labels_added": {"env": "test"},
            "message": "Added 1 label(s) to session 'session-1'",
        }

        output = format_labels(result)

        assert "Added 1 label(s)" in output

    def test_format_labels_single_unlabel(self) -> None:
        """Test formatting single unlabel result."""
        result = {
            "unlabeled": True,
            "session": "session-1",
            "labels_removed": ["env"],
            "message": "Removed 1 label(s) from session 'session-1'",
        }

        output = format_labels(result)

        assert "Removed 1 label(s)" in output

    def test_format_labels_bulk(self) -> None:
        """Test formatting bulk label result."""
        result = {
            "labeled": ["s1", "s2"],
            "failed": [],
            "labels": {"env": "test"},
        }

        output = format_labels(result)

        assert "Successfully labeled 2 session(s)" in output


class TestFormatLogin:
    """Tests for format_login."""

    def test_format_login_success(self) -> None:
        """Test formatting successful login."""
        result = {
            "authenticated": True,
            "cluster": "test-cluster",
            "server": "https://api.test.example.com",
            "message": "Successfully authenticated",
        }

        output = format_login(result)

        assert "Authentication successful" in output
        assert "Cluster: test-cluster" in output
        assert "Server: https://api.test.example.com" in output

    def test_format_login_failure(self) -> None:
        """Test formatting failed login."""
        result = {
            "authenticated": False,
            "cluster": "test-cluster",
            "message": "Invalid token",
        }

        output = format_login(result)

        assert "Authentication failed" in output
        assert "Invalid token" in output


class TestFormatSessionCreated:
    """Tests for format_session_created."""

    def test_format_session_created_from_template(self) -> None:
        """Test formatting session created from template."""
        result = {
            "created": True,
            "session": "template-abc12",
            "project": "test-project",
            "template": "bugfix",
            "message": "Session created from template",
        }

        output = format_session_created(result)

        assert "Session created: template-abc12" in output
        assert "Project: test-project" in output
        assert "Template: bugfix" in output

    def test_format_session_created_from_clone(self) -> None:
        """Test formatting session created from clone."""
        result = {
            "created": True,
            "session": "cloned-abc12",
            "project": "test-project",
            "source_session": "source-1",
            "message": "Session cloned",
        }

        output = format_session_created(result)

        assert "Session created: cloned-abc12" in output
        assert "Cloned from: source-1" in output

    def test_format_session_created_dry_run(self) -> None:
        """Test formatting session creation dry run."""
        result = {
            "dry_run": True,
            "success": True,
            "message": "Would create session",
            "manifest": {"initialPrompt": "test", "timeout": 900},
        }

        output = format_session_created(result)

        assert "DRY RUN MODE" in output
        assert "Would create session" in output
        assert "Manifest:" in output

    def test_format_session_created_failure(self) -> None:
        """Test formatting session creation failure."""
        result = {
            "created": False,
            "message": "Invalid spec",
        }

        output = format_session_created(result)

        assert "Failed to create session" in output
        assert "Invalid spec" in output
