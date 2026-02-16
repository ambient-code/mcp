"""Tests for ACP client."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_acp.client import ACPClient


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = MagicMock()
    settings.config_path = None
    return settings


@pytest.fixture
def mock_clusters_config():
    """Create mock clusters config."""
    cluster = MagicMock()
    cluster.server = "https://public-api-test.apps.example.com"
    cluster.default_project = "test-project"
    cluster.description = "Test Cluster"
    cluster.token = "test-token"

    config = MagicMock()
    config.clusters = {"test-cluster": cluster}
    config.default_cluster = "test-cluster"
    return config


@pytest.fixture
def client(mock_settings, mock_clusters_config):
    """Create client with mocked config."""
    with patch("mcp_acp.client.load_settings", return_value=mock_settings):
        with patch("mcp_acp.client.load_clusters_config", return_value=mock_clusters_config):
            return ACPClient()


class TestACPClientInit:
    """Tests for client initialization."""

    def test_client_init(self, client: ACPClient) -> None:
        """Test client initializes with config."""
        assert client.clusters_config.default_cluster == "test-cluster"
        assert "test-cluster" in client.clusters_config.clusters


class TestInputValidation:
    """Tests for input validation."""

    def test_validate_input_valid(self, client: ACPClient) -> None:
        """Test valid input passes validation."""
        client._validate_input("my-session", "session")
        client._validate_input("project-123", "project")

    def test_validate_input_invalid_chars(self, client: ACPClient) -> None:
        """Test invalid characters rejected."""
        with pytest.raises(ValueError, match="invalid characters"):
            client._validate_input("my_session", "session")

        with pytest.raises(ValueError, match="invalid characters"):
            client._validate_input("My-Session", "session")

    def test_validate_input_too_long(self, client: ACPClient) -> None:
        """Test input exceeding max length rejected."""
        with pytest.raises(ValueError, match="exceeds maximum length"):
            client._validate_input("a" * 254, "session")

    def test_validate_bulk_operation_within_limit(self, client: ACPClient) -> None:
        """Test bulk operation within limit passes."""
        client._validate_bulk_operation(["s1", "s2", "s3"], "delete")

    def test_validate_bulk_operation_exceeds_limit(self, client: ACPClient) -> None:
        """Test bulk operation exceeding limit rejected."""
        with pytest.raises(ValueError, match="limited to 3 items"):
            client._validate_bulk_operation(["s1", "s2", "s3", "s4"], "delete")


class TestServerURLValidation:
    """Tests for server URL validation rejecting K8s API URLs."""

    def test_reject_k8s_api_port(self) -> None:
        """Direct K8s API URL (port 6443) should be rejected."""
        from mcp_acp.settings import ClusterConfig

        with pytest.raises(ValueError, match="port 6443"):
            ClusterConfig(
                server="https://api.test.example.com:6443",
                default_project="test-project",
            )

    def test_accept_gateway_url(self) -> None:
        """Gateway URL should be accepted."""
        from mcp_acp.settings import ClusterConfig

        config = ClusterConfig(
            server="https://public-api-ambient.apps.cluster.example.com",
            default_project="test-project",
        )
        assert config.server == "https://public-api-ambient.apps.cluster.example.com"

    def test_accept_port_443(self) -> None:
        """Standard HTTPS port should be accepted."""
        from mcp_acp.settings import ClusterConfig

        config = ClusterConfig(
            server="https://api.example.com:443",
            default_project="test-project",
        )
        assert config.server == "https://api.example.com:443"


class TestTimeParsing:
    """Tests for time parsing utilities."""

    def test_parse_time_delta_days(self, client: ACPClient) -> None:
        """Test parsing days."""
        now = datetime.now(UTC)
        result = client._parse_time_delta("7d")
        expected = now - timedelta(days=7)
        assert abs((result - expected.replace(tzinfo=None)).total_seconds()) < 5

    def test_parse_time_delta_hours(self, client: ACPClient) -> None:
        """Test parsing hours."""
        now = datetime.now(UTC)
        result = client._parse_time_delta("24h")
        expected = now - timedelta(hours=24)
        assert abs((result - expected.replace(tzinfo=None)).total_seconds()) < 5

    def test_parse_time_delta_invalid(self, client: ACPClient) -> None:
        """Test invalid format rejected."""
        with pytest.raises(ValueError, match="Invalid time format"):
            client._parse_time_delta("7x")

    def test_is_older_than(self, client: ACPClient) -> None:
        """Test age comparison."""
        cutoff = datetime.now(UTC) - timedelta(days=7)
        cutoff_naive = cutoff.replace(tzinfo=None)

        old_timestamp = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        assert client._is_older_than(old_timestamp, cutoff_naive) is True

        new_timestamp = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        assert client._is_older_than(new_timestamp, cutoff_naive) is False


class TestListClusters:
    """Tests for list_clusters."""

    def test_list_clusters(self, client: ACPClient) -> None:
        """Test listing clusters."""
        result = client.list_clusters()

        assert "clusters" in result
        assert len(result["clusters"]) == 1
        assert result["clusters"][0]["name"] == "test-cluster"
        assert result["clusters"][0]["is_default"] is True
        assert result["default_cluster"] == "test-cluster"


class TestSwitchCluster:
    """Tests for switch_cluster."""

    @pytest.mark.asyncio
    async def test_switch_cluster_success(self, client: ACPClient) -> None:
        """Test switching to valid cluster."""
        result = await client.switch_cluster("test-cluster")
        assert result["switched"] is True

    @pytest.mark.asyncio
    async def test_switch_cluster_unknown(self, client: ACPClient) -> None:
        """Test switching to unknown cluster."""
        result = await client.switch_cluster("unknown-cluster")
        assert result["switched"] is False
        assert "Unknown cluster" in result["message"]


class TestWhoami:
    """Tests for whoami."""

    @pytest.mark.asyncio
    async def test_whoami_authenticated(self, client: ACPClient) -> None:
        """Test whoami with valid token."""
        result = await client.whoami()

        assert result["authenticated"] is True
        assert result["token_valid"] is True
        assert result["cluster"] == "test-cluster"
        assert result["server"] == "https://public-api-test.apps.example.com"


class TestHTTPRequests:
    """Tests for HTTP request handling."""

    @pytest.mark.asyncio
    async def test_list_sessions(self, client: ACPClient) -> None:
        """Test list_sessions makes correct HTTP request."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"items": [{"id": "session-1", "status": "running"}]}

        with patch.object(client, "_get_http_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.list_sessions("test-project")

            assert result["total"] == 1
            assert result["sessions"][0]["id"] == "session-1"

    @pytest.mark.asyncio
    async def test_delete_session_dry_run(self, client: ACPClient) -> None:
        """Test delete_session in dry_run mode."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "session-1", "status": "running"}

        with patch.object(client, "_get_http_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.delete_session("test-project", "session-1", dry_run=True)

            assert result["dry_run"] is True
            assert result["success"] is True
            assert "Would delete" in result["message"]

    @pytest.mark.asyncio
    async def test_delete_session_success(self, client: ACPClient) -> None:
        """Test delete_session success."""
        mock_response = MagicMock()
        mock_response.status_code = 204

        with patch.object(client, "_get_http_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.delete_session("test-project", "session-1")

            assert result["deleted"] is True


class TestBulkOperations:
    """Tests for bulk operations."""

    @pytest.mark.asyncio
    async def test_bulk_delete_sessions(self, client: ACPClient) -> None:
        """Test bulk delete sessions."""
        mock_response = MagicMock()
        mock_response.status_code = 204

        with patch.object(client, "_get_http_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.bulk_delete_sessions("test-project", ["s1", "s2"])

            assert len(result["deleted"]) == 2
            assert "s1" in result["deleted"]
            assert "s2" in result["deleted"]


class TestCreateSession:
    """Tests for create_session."""

    @pytest.mark.asyncio
    async def test_create_session_dry_run(self, client: ACPClient) -> None:
        """Dry run should return manifest without hitting API."""
        result = await client.create_session(
            project="test-project",
            initial_prompt="Run all tests",
            display_name="Test Run",
            repos=["https://github.com/org/repo"],
            dry_run=True,
        )

        assert result["dry_run"] is True
        assert result["success"] is True
        assert result["project"] == "test-project"

        manifest = result["manifest"]
        assert manifest["initialPrompt"] == "Run all tests"
        assert manifest["displayName"] == "Test Run"
        assert manifest["repos"] == ["https://github.com/org/repo"]
        assert manifest["interactive"] is False
        assert manifest["llmConfig"]["model"] == "claude-sonnet-4"
        assert manifest["timeout"] == 900

    @pytest.mark.asyncio
    async def test_create_session_dry_run_minimal(self, client: ACPClient) -> None:
        """Dry run with only required fields should omit optional keys."""
        result = await client.create_session(
            project="test-project",
            initial_prompt="hello",
            dry_run=True,
        )

        manifest = result["manifest"]
        assert "displayName" not in manifest
        assert "repos" not in manifest

    @pytest.mark.asyncio
    async def test_create_session_success(self, client: ACPClient) -> None:
        """Successful creation should return session id and project."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "compiled-abc12", "status": "creating"}

        with patch.object(client, "_get_http_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.create_session(
                project="test-project",
                initial_prompt="Implement feature X",
            )

            assert result["created"] is True
            assert result["session"] == "compiled-abc12"
            assert result["project"] == "test-project"

    @pytest.mark.asyncio
    async def test_create_session_api_failure(self, client: ACPClient) -> None:
        """API failure should return created=False with error message."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": "invalid session spec"}
        mock_response.text = "invalid session spec"

        with patch.object(client, "_get_http_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.create_session(
                project="test-project",
                initial_prompt="hello",
            )

            assert result["created"] is False
            assert "invalid session spec" in result["message"]

    @pytest.mark.asyncio
    async def test_create_session_custom_model_and_timeout(self, client: ACPClient) -> None:
        """Custom model and timeout should appear in dry-run manifest."""
        result = await client.create_session(
            project="test-project",
            initial_prompt="hello",
            model="claude-opus-4",
            timeout=3600,
            dry_run=True,
        )

        manifest = result["manifest"]
        assert manifest["llmConfig"]["model"] == "claude-opus-4"
        assert manifest["timeout"] == 3600


class TestRestartSession:
    """Tests for restart_session."""

    @pytest.mark.asyncio
    async def test_restart_session_dry_run(self, client: ACPClient) -> None:
        """Dry run should preview restart without executing."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "session-1", "status": "stopped"}

        with patch.object(client, "_get_http_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.restart_session("test-project", "session-1", dry_run=True)

            assert result["dry_run"] is True
            assert result["success"] is True
            assert "Would restart" in result["message"]

    @pytest.mark.asyncio
    async def test_restart_session_success(self, client: ACPClient) -> None:
        """Restart should PATCH with stopped=False."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "session-1", "status": "running"}

        with patch.object(client, "_get_http_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.restart_session("test-project", "session-1")

            assert result["restarted"] is True
            assert "Successfully restarted" in result["message"]

            call_args = mock_http_client.request.call_args
            assert call_args.kwargs["method"] == "PATCH"
            assert call_args.kwargs["json"] == {"stopped": False}


class TestStopSession:
    """Tests for stop_session."""

    @pytest.mark.asyncio
    async def test_stop_session_dry_run(self, client: ACPClient) -> None:
        """Dry run should preview stop without executing."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "session-1", "status": "running"}

        with patch.object(client, "_get_http_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.stop_session("test-project", "session-1", dry_run=True)

            assert result["dry_run"] is True
            assert result["success"] is True
            assert "Would stop" in result["message"]

    @pytest.mark.asyncio
    async def test_stop_session_success(self, client: ACPClient) -> None:
        """Stop should PATCH with stopped=True."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "session-1", "status": "stopped"}

        with patch.object(client, "_get_http_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.stop_session("test-project", "session-1")

            assert result["stopped"] is True
            assert "Successfully stopped" in result["message"]

            call_args = mock_http_client.request.call_args
            assert call_args.kwargs["method"] == "PATCH"
            assert call_args.kwargs["json"] == {"stopped": True}


class TestCloneSession:
    """Tests for clone_session."""

    @pytest.mark.asyncio
    async def test_clone_session_dry_run(self, client: ACPClient) -> None:
        """Dry run should GET source and return manifest without POSTing."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "source-1",
            "initialPrompt": "original prompt",
            "interactive": False,
            "timeout": 900,
            "llmConfig": {"model": "claude-sonnet-4"},
            "repos": ["https://github.com/org/repo"],
        }

        with patch.object(client, "_get_http_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.clone_session("test-project", "source-1", "clone-name", dry_run=True)

            assert result["dry_run"] is True
            assert result["success"] is True
            assert "Would clone" in result["message"]
            assert result["manifest"]["displayName"] == "clone-name"
            assert result["source_session"] == "source-1"

    @pytest.mark.asyncio
    async def test_clone_session_success(self, client: ACPClient) -> None:
        """Clone should GET source then POST new session."""
        source_response = MagicMock()
        source_response.status_code = 200
        source_response.json.return_value = {
            "id": "source-1",
            "initialPrompt": "original prompt",
            "interactive": False,
            "timeout": 900,
            "llmConfig": {"model": "claude-sonnet-4"},
        }

        create_response = MagicMock()
        create_response.status_code = 201
        create_response.json.return_value = {"id": "cloned-abc12"}

        with patch.object(client, "_get_http_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(side_effect=[source_response, create_response])
            mock_get_client.return_value = mock_http_client

            result = await client.clone_session("test-project", "source-1", "my-clone")

            assert result["created"] is True
            assert result["session"] == "cloned-abc12"
            assert result["source_session"] == "source-1"


class TestUpdateSession:
    """Tests for update_session."""

    @pytest.mark.asyncio
    async def test_update_session_display_name(self, client: ACPClient) -> None:
        """Should update display name via PATCH."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "session-1", "displayName": "new-name"}

        with patch.object(client, "_get_http_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.update_session("test-project", "session-1", display_name="new-name")

            assert result["updated"] is True
            assert "Successfully updated" in result["message"]

    @pytest.mark.asyncio
    async def test_update_session_timeout(self, client: ACPClient) -> None:
        """Should update timeout via PATCH."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "session-1", "timeout": 1800}

        with patch.object(client, "_get_http_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.update_session("test-project", "session-1", timeout=1800)

            assert result["updated"] is True

    @pytest.mark.asyncio
    async def test_update_session_dry_run(self, client: ACPClient) -> None:
        """Dry run should preview update without executing."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "session-1", "displayName": "old-name"}

        with patch.object(client, "_get_http_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.update_session("test-project", "session-1", display_name="new-name", dry_run=True)

            assert result["dry_run"] is True
            assert result["success"] is True
            assert result["patch"] == {"displayName": "new-name"}

    @pytest.mark.asyncio
    async def test_update_session_no_fields_raises(self, client: ACPClient) -> None:
        """Should raise ValueError when no fields provided."""
        with pytest.raises(ValueError, match="No fields to update"):
            await client.update_session("test-project", "session-1")


class TestCreateSessionFromTemplate:
    """Tests for create_session_from_template."""

    @pytest.mark.asyncio
    async def test_create_from_template_dry_run(self, client: ACPClient) -> None:
        """Dry run should return template manifest."""
        result = await client.create_session_from_template(
            project="test-project",
            template="bugfix",
            display_name="Fix login bug",
            dry_run=True,
        )

        assert result["dry_run"] is True
        assert result["success"] is True
        assert "bugfix" in result["message"]
        manifest = result["manifest"]
        assert manifest["displayName"] == "Fix login bug"
        assert manifest["workflow"] == "bugfix"
        assert manifest["llmConfig"]["model"] == "claude-sonnet-4"

    @pytest.mark.asyncio
    async def test_create_from_template_invalid_raises(self, client: ACPClient) -> None:
        """Invalid template name should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown template"):
            await client.create_session_from_template(
                project="test-project",
                template="nonexistent",
                display_name="test",
            )

    @pytest.mark.asyncio
    async def test_create_from_template_success(self, client: ACPClient) -> None:
        """Successful template creation should return session info."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "template-abc12"}

        with patch.object(client, "_get_http_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.create_session_from_template(
                project="test-project",
                template="triage",
                display_name="Triage issue",
            )

            assert result["created"] is True
            assert result["session"] == "template-abc12"
            assert result["template"] == "triage"


class TestGetSessionLogs:
    """Tests for get_session_logs."""

    @pytest.mark.asyncio
    async def test_get_session_logs_success(self, client: ACPClient) -> None:
        """Should return logs text from _request_text."""
        with patch.object(client, "_request_text", new_callable=AsyncMock, return_value="log line 1\nlog line 2"):
            result = await client.get_session_logs("test-project", "session-1")

            assert result["logs"] == "log line 1\nlog line 2"
            assert result["session"] == "session-1"
            assert result["tail_lines"] == 1000

    @pytest.mark.asyncio
    async def test_get_session_logs_error(self, client: ACPClient) -> None:
        """Should return error dict when request fails."""
        with patch.object(client, "_request_text", new_callable=AsyncMock, side_effect=ValueError("Not found")):
            result = await client.get_session_logs("test-project", "session-1")

            assert result["logs"] == ""
            assert "Not found" in result["error"]

    @pytest.mark.asyncio
    async def test_get_session_logs_tail_lines_limit(self, client: ACPClient) -> None:
        """Should reject tail_lines > 10000."""
        with pytest.raises(ValueError, match="tail_lines cannot exceed 10000"):
            await client.get_session_logs("test-project", "session-1", tail_lines=10001)


class TestGetSessionTranscript:
    """Tests for get_session_transcript."""

    @pytest.mark.asyncio
    async def test_get_session_transcript_success(self, client: ACPClient) -> None:
        """Should return transcript data."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "messages": [{"role": "user", "content": "hello"}],
        }

        with patch.object(client, "_get_http_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.get_session_transcript("test-project", "session-1", format="json")

            assert result["session"] == "session-1"
            assert result["format"] == "json"
            assert result["messages"] == [{"role": "user", "content": "hello"}]

    @pytest.mark.asyncio
    async def test_get_session_transcript_invalid_format(self, client: ACPClient) -> None:
        """Invalid format should raise ValueError."""
        with pytest.raises(ValueError, match="format must be"):
            await client.get_session_transcript("test-project", "session-1", format="xml")


class TestGetSessionMetrics:
    """Tests for get_session_metrics."""

    @pytest.mark.asyncio
    async def test_get_session_metrics_success(self, client: ACPClient) -> None:
        """Should return metrics data."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "total_tokens": 5000,
            "duration_seconds": 120,
            "tool_calls": 15,
        }

        with patch.object(client, "_get_http_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.get_session_metrics("test-project", "session-1")

            assert result["session"] == "session-1"
            assert result["total_tokens"] == 5000
            assert result["duration_seconds"] == 120
            assert result["tool_calls"] == 15


class TestLabelSession:
    """Tests for label_session."""

    @pytest.mark.asyncio
    async def test_label_session_success(self, client: ACPClient) -> None:
        """Should add labels via PATCH."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "session-1"}

        with patch.object(client, "_get_http_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.label_session("test-project", "session-1", {"env": "test", "team": "qa"})

            assert result["labeled"] is True
            assert result["labels_added"] == {"env": "test", "team": "qa"}
            assert "2 label(s)" in result["message"]


class TestUnlabelSession:
    """Tests for unlabel_session."""

    @pytest.mark.asyncio
    async def test_unlabel_session_success(self, client: ACPClient) -> None:
        """Should remove labels via PATCH."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "session-1"}

        with patch.object(client, "_get_http_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.unlabel_session("test-project", "session-1", ["env", "team"])

            assert result["unlabeled"] is True
            assert result["labels_removed"] == ["env", "team"]
            assert "2 label(s)" in result["message"]

    @pytest.mark.asyncio
    async def test_unlabel_session_empty_keys_raises(self, client: ACPClient) -> None:
        """Should raise ValueError when label_keys is empty."""
        with pytest.raises(ValueError, match="label_keys must not be empty"):
            await client.unlabel_session("test-project", "session-1", [])


class TestListSessionsByLabel:
    """Tests for list_sessions_by_label."""

    @pytest.mark.asyncio
    async def test_list_sessions_by_label(self, client: ACPClient) -> None:
        """Should list sessions matching label selectors."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [{"id": "session-1", "status": "running"}],
        }

        with patch.object(client, "_get_http_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.list_sessions_by_label("test-project", {"env": "test"})

            assert result["total"] == 1
            assert result["sessions"][0]["id"] == "session-1"
            assert result["labels_filter"] == {"env": "test"}


class TestLabelValidation:
    """Tests for _validate_labels."""

    def test_validate_labels_valid(self, client: ACPClient) -> None:
        """Valid labels should pass validation."""
        client._validate_labels({"env": "production", "team": "qa"})
        client._validate_labels({"app.version": "v1.2.3"})

    def test_validate_labels_empty_raises(self, client: ACPClient) -> None:
        """Empty labels dict should raise ValueError."""
        with pytest.raises(ValueError, match="Labels must not be empty"):
            client._validate_labels({})

    def test_validate_labels_invalid_key(self, client: ACPClient) -> None:
        """Invalid label key should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid label key"):
            client._validate_labels({"invalid key!": "value"})

    def test_validate_labels_key_too_long(self, client: ACPClient) -> None:
        """Label key exceeding 63 chars should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid label key"):
            client._validate_labels({"a" * 64: "value"})

    def test_validate_labels_invalid_value(self, client: ACPClient) -> None:
        """Invalid label value should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid label value"):
            client._validate_labels({"key": "invalid value!"})


class TestBulkDeleteDryRun:
    """Tests for bulk delete dry_run path."""

    @pytest.mark.asyncio
    async def test_bulk_delete_dry_run(self, client: ACPClient) -> None:
        """Dry run should preview deletes without executing."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "s1", "status": "running"}

        with patch.object(client, "_get_http_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.bulk_delete_sessions("test-project", ["s1", "s2"], dry_run=True)

            assert result["dry_run"] is True
            assert len(result["dry_run_info"]["would_execute"]) == 2
            assert result["dry_run_info"]["would_execute"][0]["session"] == "s1"


class TestBulkDeleteFailure:
    """Tests for _run_bulk failure path."""

    @pytest.mark.asyncio
    async def test_bulk_delete_partial_failure(self, client: ACPClient) -> None:
        """Individual failures in bulk delete should be collected."""
        success_response = MagicMock()
        success_response.status_code = 204

        fail_response = MagicMock()
        fail_response.status_code = 404
        fail_response.text = "not found"
        fail_response.json.return_value = {"error": "not found"}

        with patch.object(client, "_get_http_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(side_effect=[success_response, fail_response])
            mock_get_client.return_value = mock_http_client

            result = await client.bulk_delete_sessions("test-project", ["s1", "s2"])

            assert "s1" in result["deleted"]
            assert len(result["failed"]) == 1
            assert result["failed"][0]["session"] == "s2"


class TestBulkByLabel:
    """Tests for _run_bulk_by_label pipeline."""

    @pytest.mark.asyncio
    async def test_bulk_delete_by_label(self, client: ACPClient) -> None:
        """Should resolve labels to sessions, then delete them."""
        list_response = MagicMock()
        list_response.status_code = 200
        list_response.json.return_value = {"items": [{"id": "s1"}, {"id": "s2"}]}

        delete_response = MagicMock()
        delete_response.status_code = 204

        with patch.object(client, "_get_http_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(side_effect=[list_response, delete_response, delete_response])
            mock_get_client.return_value = mock_http_client

            result = await client.bulk_delete_sessions_by_label("test-project", {"env": "test"})

            assert "s1" in result["deleted"]
            assert "s2" in result["deleted"]
            assert result["labels_filter"] == {"env": "test"}

    @pytest.mark.asyncio
    async def test_bulk_delete_by_label_no_matches(self, client: ACPClient) -> None:
        """Should return empty results when no sessions match labels."""
        list_response = MagicMock()
        list_response.status_code = 200
        list_response.json.return_value = {"items": []}

        with patch.object(client, "_get_http_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(return_value=list_response)
            mock_get_client.return_value = mock_http_client

            result = await client.bulk_delete_sessions_by_label("test-project", {"env": "nonexistent"})

            assert result["deleted"] == []
            assert result["failed"] == []
            assert "No sessions match" in result["message"]

    @pytest.mark.asyncio
    async def test_bulk_stop_by_label(self, client: ACPClient) -> None:
        """Should resolve labels to sessions, then stop them."""
        list_response = MagicMock()
        list_response.status_code = 200
        list_response.json.return_value = {"items": [{"id": "s1"}]}

        stop_response = MagicMock()
        stop_response.status_code = 200
        stop_response.json.return_value = {"id": "s1", "status": "stopped"}

        with patch.object(client, "_get_http_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(side_effect=[list_response, stop_response])
            mock_get_client.return_value = mock_http_client

            result = await client.bulk_stop_sessions_by_label("test-project", {"team": "qa"})

            assert "s1" in result["stopped"]
            assert result["labels_filter"] == {"team": "qa"}

    @pytest.mark.asyncio
    async def test_bulk_restart_by_label(self, client: ACPClient) -> None:
        """Should resolve labels to sessions, then restart them."""
        list_response = MagicMock()
        list_response.status_code = 200
        list_response.json.return_value = {"items": [{"id": "s1"}]}

        restart_response = MagicMock()
        restart_response.status_code = 200
        restart_response.json.return_value = {"id": "s1", "status": "running"}

        with patch.object(client, "_get_http_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(side_effect=[list_response, restart_response])
            mock_get_client.return_value = mock_http_client

            result = await client.bulk_restart_sessions_by_label("test-project", {"team": "qa"})

            assert "s1" in result["restarted"]
            assert result["labels_filter"] == {"team": "qa"}


class TestBulkLabelSessions:
    """Tests for bulk_label_sessions."""

    @pytest.mark.asyncio
    async def test_bulk_label_sessions_success(self, client: ACPClient) -> None:
        """Should label multiple sessions."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "s1"}

        with patch.object(client, "_get_http_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.bulk_label_sessions("test-project", ["s1", "s2"], {"env": "test"})

            assert "s1" in result["labeled"]
            assert "s2" in result["labeled"]
            assert result["labels"] == {"env": "test"}

    @pytest.mark.asyncio
    async def test_bulk_label_sessions_dry_run(self, client: ACPClient) -> None:
        """Dry run should preview labeling without executing."""
        result = await client.bulk_label_sessions("test-project", ["s1", "s2"], {"env": "test"}, dry_run=True)

        assert result["dry_run"] is True
        assert result["sessions"] == ["s1", "s2"]
        assert result["labels"] == {"env": "test"}
        assert "Would add 1 label(s) to 2 session(s)" in result["message"]


class TestBulkUnlabelSessions:
    """Tests for bulk_unlabel_sessions."""

    @pytest.mark.asyncio
    async def test_bulk_unlabel_sessions_success(self, client: ACPClient) -> None:
        """Should remove labels from multiple sessions."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "s1"}

        with patch.object(client, "_get_http_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.bulk_unlabel_sessions("test-project", ["s1", "s2"], ["env", "team"])

            assert "s1" in result["unlabeled"]
            assert "s2" in result["unlabeled"]
            assert result["label_keys"] == ["env", "team"]

    @pytest.mark.asyncio
    async def test_bulk_unlabel_sessions_dry_run(self, client: ACPClient) -> None:
        """Dry run should preview unlabeling without executing."""
        result = await client.bulk_unlabel_sessions("test-project", ["s1", "s2"], ["env"], dry_run=True)

        assert result["dry_run"] is True
        assert result["sessions"] == ["s1", "s2"]
        assert result["label_keys"] == ["env"]
        assert "Would remove 1 label(s) from 2 session(s)" in result["message"]


class TestBulkStopSessions:
    """Tests for bulk_stop_sessions."""

    @pytest.mark.asyncio
    async def test_bulk_stop_sessions(self, client: ACPClient) -> None:
        """Should stop multiple sessions."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "s1", "status": "stopped"}

        with patch.object(client, "_get_http_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.bulk_stop_sessions("test-project", ["s1", "s2"])

            assert len(result["stopped"]) == 2
            assert "s1" in result["stopped"]
            assert "s2" in result["stopped"]


class TestBulkRestartSessions:
    """Tests for bulk_restart_sessions."""

    @pytest.mark.asyncio
    async def test_bulk_restart_sessions(self, client: ACPClient) -> None:
        """Should restart multiple sessions."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "s1", "status": "running"}

        with patch.object(client, "_get_http_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.bulk_restart_sessions("test-project", ["s1", "s2"])

            assert len(result["restarted"]) == 2
            assert "s1" in result["restarted"]
            assert "s2" in result["restarted"]


class TestLogin:
    """Tests for login."""

    @pytest.mark.asyncio
    async def test_login_success(self, client: ACPClient) -> None:
        """Should authenticate to a cluster with a token."""
        result = await client.login("test-cluster", token="new-token")

        assert result["authenticated"] is True
        assert result["cluster"] == "test-cluster"
        assert "Successfully authenticated" in result["message"]

    @pytest.mark.asyncio
    async def test_login_unknown_cluster(self, client: ACPClient) -> None:
        """Should fail for unknown cluster."""
        result = await client.login("nonexistent-cluster")

        assert result["authenticated"] is False
        assert "Unknown cluster" in result["message"]
