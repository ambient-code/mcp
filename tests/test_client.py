"""Tests for ACP client."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from mcp_acp.client import ACPClient


@pytest.fixture
def mock_config(tmp_path: Path) -> str:
    """Create a temporary cluster configuration."""
    config_dir = tmp_path / ".config" / "acp"
    config_dir.mkdir(parents=True)

    config_file = config_dir / "clusters.yaml"
    config = {
        "clusters": {
            "test-cluster": {
                "server": "https://api.test.example.com:443",
                "description": "Test Cluster",
                "default_project": "test-workspace",
            },
            "prod-cluster": {
                "server": "https://api.prod.example.com:443",
                "description": "Production Cluster",
                "default_project": "prod-workspace",
            },
        },
        "default_cluster": "test-cluster",
    }

    with open(config_file, "w") as f:
        yaml.dump(config, f)

    return str(config_file)


@pytest.fixture
def client(mock_config: str) -> ACPClient:
    """Create ACP client with mock config."""
    return ACPClient(config_path=mock_config)


class TestACPClient:
    """Tests for ACPClient."""

    def test_load_config(self, client: ACPClient) -> None:
        """Test configuration loading."""
        assert "test-cluster" in client.config["clusters"]
        assert "prod-cluster" in client.config["clusters"]
        assert client.config["default_cluster"] == "test-cluster"

    def test_parse_time_delta(self, client: ACPClient) -> None:
        """Test time delta parsing."""
        now = datetime.utcnow()

        # Test days
        result = client._parse_time_delta("7d")
        expected = now - timedelta(days=7)
        assert abs((result - expected).total_seconds()) < 1

        # Test hours
        result = client._parse_time_delta("24h")
        expected = now - timedelta(hours=24)
        assert abs((result - expected).total_seconds()) < 1

        # Test minutes
        result = client._parse_time_delta("30m")
        expected = now - timedelta(minutes=30)
        assert abs((result - expected).total_seconds()) < 1

    def test_parse_time_delta_invalid(self, client: ACPClient) -> None:
        """Test invalid time delta format."""
        with pytest.raises(ValueError, match="Invalid time format"):
            client._parse_time_delta("invalid")

    def test_is_older_than(self, client: ACPClient) -> None:
        """Test timestamp comparison."""
        cutoff = datetime.utcnow() - timedelta(days=7)

        # Older timestamp
        old_time = (cutoff - timedelta(days=1)).isoformat() + "Z"
        assert client._is_older_than(old_time, cutoff) is True

        # Newer timestamp
        new_time = (cutoff + timedelta(days=1)).isoformat() + "Z"
        assert client._is_older_than(new_time, cutoff) is False

        # None timestamp
        assert client._is_older_than(None, cutoff) is False

    @pytest.mark.asyncio
    async def test_list_sessions_basic(self, client: ACPClient) -> None:
        """Test basic session listing."""
        mock_response = {
            "items": [
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
                    "status": {"phase": "stopped"},
                },
            ]
        }

        with patch.object(
            client,
            "_run_oc_command",
            new_callable=AsyncMock,
            return_value=MagicMock(returncode=0, stdout=json.dumps(mock_response).encode()),
        ):
            result = await client.list_sessions(project="test-project")

            assert result["total"] == 2
            assert len(result["sessions"]) == 2
            assert result["filters_applied"] == {}

    @pytest.mark.asyncio
    async def test_list_sessions_with_status_filter(self, client: ACPClient) -> None:
        """Test session listing with status filter."""
        mock_response = {
            "items": [
                {
                    "metadata": {"name": "session-1"},
                    "status": {"phase": "running"},
                },
                {
                    "metadata": {"name": "session-2"},
                    "status": {"phase": "stopped"},
                },
            ]
        }

        with patch.object(
            client,
            "_run_oc_command",
            new_callable=AsyncMock,
            return_value=MagicMock(returncode=0, stdout=json.dumps(mock_response).encode()),
        ):
            result = await client.list_sessions(project="test-project", status="running")

            assert result["total"] == 1
            assert result["sessions"][0]["metadata"]["name"] == "session-1"
            assert result["filters_applied"]["status"] == "running"

    @pytest.mark.asyncio
    async def test_list_sessions_with_limit(self, client: ACPClient) -> None:
        """Test session listing with limit."""
        mock_response = {"items": [{"metadata": {"name": f"session-{i}"}} for i in range(10)]}

        with patch.object(
            client,
            "_run_oc_command",
            new_callable=AsyncMock,
            return_value=MagicMock(returncode=0, stdout=json.dumps(mock_response).encode()),
        ):
            result = await client.list_sessions(project="test-project", limit=5)

            assert result["total"] == 5
            assert len(result["sessions"]) == 5
            assert result["filters_applied"]["limit"] == 5

    @pytest.mark.asyncio
    async def test_delete_session_success(self, client: ACPClient) -> None:
        """Test successful session deletion."""
        with patch.object(
            client,
            "_run_oc_command",
            new_callable=AsyncMock,
            return_value=MagicMock(returncode=0, stderr=b""),
        ):
            result = await client.delete_session(project="test-project", session="test-session")

            assert result["deleted"] is True
            assert "Successfully deleted" in result["message"]

    @pytest.mark.asyncio
    async def test_delete_session_dry_run(self, client: ACPClient) -> None:
        """Test session deletion dry run."""
        mock_session = {
            "metadata": {"name": "test-session", "creationTimestamp": "2024-01-20T10:00:00Z"},
            "status": {"phase": "running"},
        }

        with patch.object(
            client,
            "_run_oc_command",
            new_callable=AsyncMock,
            return_value=MagicMock(returncode=0, stdout=json.dumps(mock_session).encode()),
        ):
            result = await client.delete_session(
                project="test-project", session="test-session", dry_run=True
            )

            assert result["deleted"] is False
            assert result["dry_run"] is True
            assert "Would delete" in result["message"]
            assert "session_info" in result

    @pytest.mark.asyncio
    async def test_restart_session_success(self, client: ACPClient) -> None:
        """Test successful session restart."""
        mock_session = {
            "metadata": {"name": "test-session"},
            "status": {"phase": "stopped"},
        }

        with patch.object(
            client,
            "_run_oc_command",
            new_callable=AsyncMock,
        ) as mock_cmd:
            # First call: get session status
            # Second call: patch session
            mock_cmd.side_effect = [
                MagicMock(returncode=0, stdout=json.dumps(mock_session).encode()),
                MagicMock(returncode=0, stderr=b""),
            ]

            result = await client.restart_session(project="test-project", session="test-session")

            assert result["status"] == "restarting"
            assert "Successfully restarted" in result["message"]

    @pytest.mark.asyncio
    async def test_restart_session_dry_run(self, client: ACPClient) -> None:
        """Test session restart dry run."""
        mock_session = {
            "metadata": {"name": "test-session"},
            "status": {"phase": "stopped", "stoppedAt": "2024-01-20T10:00:00Z"},
        }

        with patch.object(
            client,
            "_run_oc_command",
            new_callable=AsyncMock,
            return_value=MagicMock(returncode=0, stdout=json.dumps(mock_session).encode()),
        ):
            result = await client.restart_session(
                project="test-project", session="test-session", dry_run=True
            )

            assert result["dry_run"] is True
            assert "Would restart" in result["message"]
            assert result["session_info"]["current_status"] == "stopped"

    @pytest.mark.asyncio
    async def test_bulk_delete_sessions(self, client: ACPClient) -> None:
        """Test bulk session deletion."""
        sessions = ["session-1", "session-2", "session-3"]

        with patch.object(client, "delete_session", new_callable=AsyncMock) as mock_delete:
            # Simulate 2 successful and 1 failed deletion
            mock_delete.side_effect = [
                {"deleted": True, "message": "Success"},
                {"deleted": True, "message": "Success"},
                {"deleted": False, "message": "Session not found"},
            ]

            result = await client.bulk_delete_sessions(project="test-project", sessions=sessions)

            assert len(result["deleted"]) == 2
            assert len(result["failed"]) == 1
            assert result["failed"][0]["session"] == "session-3"

    @pytest.mark.asyncio
    async def test_bulk_stop_sessions(self, client: ACPClient) -> None:
        """Test bulk session stop."""
        sessions = ["session-1", "session-2"]

        with patch.object(
            client,
            "_run_oc_command",
            new_callable=AsyncMock,
        ) as mock_cmd:
            # Both patches succeed
            mock_cmd.return_value = MagicMock(returncode=0, stderr=b"")

            result = await client.bulk_stop_sessions(project="test-project", sessions=sessions)

            assert len(result["stopped"]) == 2
            assert len(result["failed"]) == 0

    @pytest.mark.asyncio
    async def test_get_session_logs(self, client: ACPClient) -> None:
        """Test getting session logs."""
        mock_pods = {
            "items": [
                {
                    "metadata": {"name": "test-session-pod-12345"},
                }
            ]
        }

        mock_logs = (
            "2024-01-20 10:00:00 INFO Starting session\n2024-01-20 10:00:01 INFO Session ready\n"
        )

        with patch.object(
            client,
            "_run_oc_command",
            new_callable=AsyncMock,
        ) as mock_cmd:
            # First call: get pods
            # Second call: get logs
            mock_cmd.side_effect = [
                MagicMock(returncode=0, stdout=json.dumps(mock_pods).encode()),
                MagicMock(returncode=0, stdout=mock_logs.encode()),
            ]

            result = await client.get_session_logs(
                project="test-project", session="test-session", tail_lines=100
            )

            assert result["logs"] == mock_logs
            assert result["lines"] == 3  # Including trailing newline

    def test_list_clusters(self, client: ACPClient) -> None:
        """Test listing clusters."""
        result = client.list_clusters()

        assert len(result["clusters"]) == 2
        assert result["default_cluster"] == "test-cluster"

        # Check first cluster
        test_cluster = next(c for c in result["clusters"] if c["name"] == "test-cluster")
        assert test_cluster["is_default"] is True
        assert test_cluster["server"] == "https://api.test.example.com:443"
        assert test_cluster["default_project"] == "test-workspace"

    @pytest.mark.asyncio
    async def test_whoami(self, client: ACPClient) -> None:
        """Test whoami command."""
        with patch.object(
            client,
            "_run_oc_command",
            new_callable=AsyncMock,
        ) as mock_cmd:
            # Mock responses for user, server, project, token
            mock_cmd.side_effect = [
                MagicMock(returncode=0, stdout=b"testuser"),
                MagicMock(returncode=0, stdout=b"https://api.test.example.com:443"),
                MagicMock(returncode=0, stdout=b"test-workspace"),
                MagicMock(returncode=0, stdout=b"sha256~..."),
            ]

            result = await client.whoami()

            assert result["user"] == "testuser"
            assert result["server"] == "https://api.test.example.com:443"
            assert result["project"] == "test-workspace"
            assert result["token_valid"] is True
            assert result["authenticated"] is True


class TestBulkSafety:
    """Tests for bulk operation safety limits."""

    def test_validate_bulk_operation_within_limit(self, client: ACPClient) -> None:
        """Should pass with 3 or fewer items."""
        client._validate_bulk_operation(["s1", "s2", "s3"], "delete")  # Should not raise

    def test_validate_bulk_operation_exceeds_limit(self, client: ACPClient) -> None:
        """Should raise ValueError with >3 items."""
        with pytest.raises(ValueError, match="limited to 3 items"):
            client._validate_bulk_operation(["s1", "s2", "s3", "s4"], "delete")


class TestLabelOperations:
    """Tests for label operations."""

    @pytest.mark.asyncio
    async def test_label_resource_success(self, client: ACPClient) -> None:
        """Should label resource successfully."""
        with patch.object(
            client, "_run_oc_command", new_callable=AsyncMock, return_value=MagicMock(returncode=0)
        ):
            result = await client.label_resource(
                "agenticsession",
                "test-session",
                "test-project",
                labels={"env": "dev", "team": "api"},
            )

            assert result["labeled"] is True
            assert result["labels"] == {"env": "dev", "team": "api"}

    @pytest.mark.asyncio
    async def test_label_resource_invalid_key(self, client: ACPClient) -> None:
        """Should reject invalid label keys."""
        with pytest.raises(ValueError, match="Invalid label key"):
            await client.label_resource(
                "agenticsession", "test", "test-project", labels={"bad key!": "value"}
            )

    @pytest.mark.asyncio
    async def test_unlabel_resource_success(self, client: ACPClient) -> None:
        """Should remove labels successfully."""
        with patch.object(
            client, "_run_oc_command", new_callable=AsyncMock, return_value=MagicMock(returncode=0)
        ):
            result = await client.unlabel_resource(
                "agenticsession", "test-session", "test-project", label_keys=["env", "team"]
            )

            assert result["unlabeled"] is True
            assert result["removed_keys"] == ["env", "team"]

    @pytest.mark.asyncio
    async def test_bulk_label_resources(self, client: ACPClient) -> None:
        """Should label multiple resources."""
        with patch.object(client, "label_resource", new_callable=AsyncMock) as mock_label:
            mock_label.return_value = {"labeled": True}

            result = await client.bulk_label_resources(
                "agenticsession", ["s1", "s2"], "test-project", labels={"env": "dev"}
            )

            assert len(result["labeled"]) == 2
            assert len(result["failed"]) == 0

    @pytest.mark.asyncio
    async def test_list_sessions_by_label(self, client: ACPClient) -> None:
        """Should list sessions by label selector."""
        mock_response = {"items": [{"metadata": {"name": "session-1"}}]}

        with patch.object(
            client,
            "_run_oc_command",
            new_callable=AsyncMock,
            return_value=MagicMock(returncode=0, stdout=json.dumps(mock_response).encode()),
        ):
            result = await client.list_sessions_by_user_labels(
                "test-project", labels={"env": "dev"}
            )

            assert result["total"] == 1

    @pytest.mark.asyncio
    async def test_bulk_delete_by_label_exceeds_limit(self, client: ACPClient) -> None:
        """Should reject when label selector matches >3 sessions."""
        mock_response = {"items": [{"metadata": {"name": f"s{i}"}} for i in range(5)]}

        with patch.object(
            client,
            "_run_oc_command",
            new_callable=AsyncMock,
            return_value=MagicMock(returncode=0, stdout=json.dumps(mock_response).encode()),
        ):
            with pytest.raises(ValueError, match="Max 3 allowed"):
                await client.bulk_delete_sessions_by_label(
                    "test-project", labels={"cleanup": "true"}
                )
