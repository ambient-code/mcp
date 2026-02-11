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
    cluster.server = "https://api.test.example.com"
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
        assert result["server"] == "https://api.test.example.com"


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
