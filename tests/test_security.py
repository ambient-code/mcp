"""Security tests for MCP ACP Server."""

import pytest

from mcp_acp.client import ACPClient


class TestInputValidation:
    """Test input validation and security controls."""

    def test_validate_input_valid_names(self):
        """Test that valid Kubernetes names pass validation."""
        client = ACPClient()

        valid_names = [
            "test-session",
            "my-project-123",
            "a",
            "session-with-many-dashes",
            "123-numeric-start",
        ]

        for name in valid_names:
            # Should not raise
            client._validate_input(name, "test")

    def test_validate_input_invalid_names(self):
        """Test that invalid names are rejected."""
        client = ACPClient()

        invalid_names = [
            "Test-Session",  # uppercase
            "my_project",  # underscore
            "session.name",  # dot
            "session name",  # space
            "session;name",  # semicolon
            "../../../etc/passwd",  # path traversal
            "session|name",  # pipe
            "session&name",  # ampersand
            "-starts-dash",  # starts with dash
            "ends-dash-",  # ends with dash
            "a" * 254,  # too long
        ]

        for name in invalid_names:
            with pytest.raises(ValueError):
                client._validate_input(name, "test")

    def test_config_validation(self):
        """Test configuration validation."""
        # Valid config should pass
        client = ACPClient()
        client.config = {
            "clusters": {"test": {"server": "https://api.example.com:6443", "description": "Test cluster"}},
            "default_cluster": "test",
        }
        client._validate_config()  # Should not raise

    def test_config_validation_invalid_server(self):
        """Test that invalid server URLs are rejected."""
        client = ACPClient()
        client.config = {
            "clusters": {
                "test": {
                    "server": "not-a-url",  # Invalid
                }
            }
        }
        with pytest.raises(ValueError, match="invalid server URL"):
            client._validate_config()

    def test_config_validation_missing_server(self):
        """Test that missing server field is rejected."""
        client = ACPClient()
        client.config = {"clusters": {"test": {"description": "Missing server"}}}
        with pytest.raises(ValueError, match="missing 'server' field"):
            client._validate_config()


class TestCommandInjectionPrevention:
    """Test command injection prevention."""

    @pytest.mark.asyncio
    async def test_run_oc_command_rejects_metacharacters(self):
        """Test that shell metacharacters in arguments are rejected."""
        client = ACPClient()

        malicious_args = [
            "test; rm -rf /",
            "test | cat /etc/passwd",
            "test && whoami",
            "test `ls`",
            "test $HOME",
            "test\nrm -rf /",
        ]

        for arg in malicious_args:
            with pytest.raises(ValueError, match="suspicious characters"):
                await client._run_oc_command(["get", "pods", arg])

    def test_resource_type_whitelist(self):
        """Test that only whitelisted resource types are allowed."""
        client = ACPClient()

        # Allowed types should work
        assert "agenticsession" in client.ALLOWED_RESOURCE_TYPES
        assert "pods" in client.ALLOWED_RESOURCE_TYPES
        assert "event" in client.ALLOWED_RESOURCE_TYPES

        # Disallowed types should fail
        assert "secrets" not in client.ALLOWED_RESOURCE_TYPES
        assert "configmaps" not in client.ALLOWED_RESOURCE_TYPES

    @pytest.mark.asyncio
    async def test_get_resource_json_validates_resource_type(self):
        """Test that _get_resource_json validates resource types."""
        client = ACPClient()

        with pytest.raises(ValueError, match="not allowed"):
            await client._get_resource_json("secrets", "test", "default")


class TestResourceLimits:
    """Test resource exhaustion protection."""

    def test_max_log_lines_limit(self):
        """Test that log line limits are enforced."""
        client = ACPClient()

        # Should accept valid values
        assert 100 <= client.MAX_LOG_LINES

    @pytest.mark.asyncio
    async def test_get_session_logs_validates_tail_lines(self):
        """Test that tail_lines is validated."""
        client = ACPClient()

        # Too large
        result = await client.get_session_logs("test", "session", tail_lines=999999)
        assert "error" in result
        assert "tail_lines" in result["error"].lower()

        # Negative
        result = await client.get_session_logs("test", "session", tail_lines=-1)
        assert "error" in result

    def test_timeout_constants(self):
        """Test that timeout constants are reasonable."""
        client = ACPClient()

        # Should have a max command timeout
        assert hasattr(client, "MAX_COMMAND_TIMEOUT")
        assert client.MAX_COMMAND_TIMEOUT > 0
        assert client.MAX_COMMAND_TIMEOUT <= 600  # Not more than 10 minutes


class TestDataProtection:
    """Test sensitive data protection."""

    @pytest.mark.asyncio
    async def test_list_workflows_validates_url(self):
        """Test that workflow repository URLs are validated."""
        client = ACPClient()

        # Invalid URLs should be rejected
        invalid_urls = [
            "file:///etc/passwd",
            "ftp://example.com",
            "javascript:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "https://example.com; rm -rf /",
            "https://example.com | cat",
        ]

        for url in invalid_urls:
            result = await client.list_workflows(url)
            assert "error" in result

    def test_add_cluster_validates_inputs(self):
        """Test that add_cluster validates all inputs."""
        client = ACPClient()

        # Invalid cluster name
        result = client.add_cluster("Invalid Name", "https://example.com")
        assert not result.get("added")
        assert "error" in result.get("message", "").lower() or not result.get("added")

        # Invalid server URL
        result = client.add_cluster("valid-name", "not-a-url")
        assert not result.get("added")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
